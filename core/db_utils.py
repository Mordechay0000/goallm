"""
SQLite helpers shared by the proxy (mitmproxy + image worker threads) and the CRM.

A single sqlite3.Connection shared between threads is unsafe at the Python level:
one thread's commit() can commit another thread's half-done writes, and cursors interleave.
ThreadLocalSQLite keeps the old "module-level db_connection" API but opens one real
connection per thread.

transaction() defers every inner commit() until the outermost block exits, so a
multi-step sync (delete + re-insert) becomes atomic: with WAL, readers in other
processes keep seeing the previous committed snapshot until the whole batch commits.
"""
from __future__ import annotations

import contextlib
import sqlite3
import threading
from typing import Callable, Iterator, Optional, Sequence


class ThreadLocalSQLite:
    def __init__(
        self,
        path: str,
        *,
        timeout: float = 30.0,
        pragmas: Sequence[str] = ("PRAGMA journal_mode=WAL;", "PRAGMA synchronous=NORMAL;"),
        row_factory: Optional[Callable] = None,
    ) -> None:
        self._path = str(path)
        self._timeout = timeout
        self._pragmas = tuple(pragmas)
        self._row_factory = row_factory
        self._local = threading.local()
        # Open once eagerly so a bad path fails at import time (callers rely on that for fallbacks).
        self._conn()

    @property
    def path(self) -> str:
        return self._path

    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._path, timeout=self._timeout, check_same_thread=False)
            for pragma in self._pragmas:
                conn.execute(pragma)
            if self._row_factory is not None:
                conn.row_factory = self._row_factory
            self._local.conn = conn
            self._local.depth = 0
        return conn

    # --- sqlite3.Connection-compatible surface used across the codebase ---
    def execute(self, sql: str, parameters=()):
        return self._conn().execute(sql, parameters)

    def executemany(self, sql: str, seq_of_parameters):
        return self._conn().executemany(sql, seq_of_parameters)

    def commit(self) -> None:
        if getattr(self._local, "depth", 0) > 0:
            return  # deferred: the enclosing transaction() commits once at the end
        self._conn().commit()

    def rollback(self) -> None:
        if getattr(self._local, "depth", 0) > 0:
            # A partial rollback would silently drop earlier writes of the batch; fail the batch instead.
            raise RuntimeError("rollback() inside ThreadLocalSQLite.transaction(); raise to abort the batch")
        self._conn().rollback()

    def __getattr__(self, name: str):
        return getattr(self._conn(), name)

    @contextlib.contextmanager
    def transaction(self) -> Iterator["ThreadLocalSQLite"]:
        """Group writes into one commit. Nested blocks join the outer one."""
        conn = self._conn()
        self._local.depth += 1
        try:
            yield self
        except BaseException:
            self._local.depth -= 1
            if self._local.depth == 0:
                conn.rollback()
            raise
        else:
            self._local.depth -= 1
            if self._local.depth == 0:
                conn.commit()
