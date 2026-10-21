"""
Per-user proxy authentication.

Identity used to come only from the client IP. That breaks behind carrier-grade NAT (many families share
one public IP: whoever binds last "owns" it, sees the others' traffic recording and filters them with
their own settings). Now every user gets personal proxy credentials (created in the CRM, stored hashed),
and a connection is identified by them. IP binding stays as a fallback for the legacy shared credential
(PROXY_AUTH) or when PROXY_REQUIRE_AUTH=0.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import threading
import time
import weakref
from dataclasses import dataclass
from typing import Optional

from mitmproxy import http
from mitmproxy.addons.proxyauth import is_http_proxy, parse_http_basic_auth

from core.policy.policy_database import get_proxy_credential
from data.constants import PROXY_AUTH, PROXY_REQUIRE_AUTH

logger = logging.getLogger(__name__)

REALM = "goallm"


@dataclass(frozen=True)
class Identity:
    kind: str  # "user" (personal credentials) | "shared" (legacy PROXY_AUTH) | "anonymous" (auth not required)
    user_id: Optional[int] = None


def hash_proxy_secret(secret: str) -> str:
    """Secrets are random 128+ bit tokens, so a plain SHA-256 is enough (no slow KDF needed per connection)."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


class _CredentialCache:
    """Small TTL cache so a page with 100 connections does not hit SQLite 100 times."""

    def __init__(self, ttl: float = 30.0) -> None:
        self._ttl = ttl
        self._lock = threading.Lock()
        self._items: dict[tuple[str, str], tuple[Optional[int], float]] = {}

    def lookup(self, username: str, password: str) -> Optional[int]:
        key = (username, hash_proxy_secret(password))
        now = time.monotonic()
        with self._lock:
            hit = self._items.get(key)
            if hit and now - hit[1] < self._ttl:
                return hit[0]
        user_id = None
        cred = get_proxy_credential(username)
        if cred is not None and hmac.compare_digest(cred[1], key[1]):
            user_id = cred[0]
        with self._lock:
            if len(self._items) > 10000:
                self._items.clear()
            self._items[key] = (user_id, now)
        return user_id


class ProxyAuthenticator:
    def __init__(self) -> None:
        self._by_conn: "weakref.WeakKeyDictionary" = weakref.WeakKeyDictionary()
        self._cache = _CredentialCache()
        self._shared_user, self._shared_pass = (PROXY_AUTH.split(":", 1) + [""])[:2] if PROXY_AUTH else ("", "")

    def _check(self, username: str, password: str) -> Optional[Identity]:
        if not username or not password:
            return None
        user_id = self._cache.lookup(username, password)
        if user_id is not None:
            return Identity("user", user_id)
        if self._shared_user and hmac.compare_digest(username, self._shared_user) and hmac.compare_digest(password, self._shared_pass):
            return Identity("shared")
        return None

    def _authenticate(self, flow: http.HTTPFlow) -> Optional[Identity]:
        if not is_http_proxy(flow):
            # Transparent / reverse modes cannot carry proxy credentials: identity by IP.
            return Identity("anonymous")
        raw = flow.request.headers.get("Proxy-Authorization", "")
        identity = None
        if raw:
            try:
                _scheme, username, password = parse_http_basic_auth(raw)
                identity = self._check(username, password)
            except Exception:
                identity = None
            # Never forward our proxy credentials to the destination website.
            del flow.request.headers["Proxy-Authorization"]
        if identity is None and not PROXY_REQUIRE_AUTH:
            identity = Identity("anonymous")
        return identity

    @staticmethod
    def _deny(flow: http.HTTPFlow) -> None:
        flow.response = http.Response.make(
            407,
            "<html><body dir=\"rtl\"><h1>נדרשת הזדהות לפרוקסי</h1><p>יש להזין את שם המשתמש והסיסמה האישיים מעמוד \"חיבורים\" באתר הניהול.</p></body></html>",
            {"Proxy-Authenticate": f'Basic realm="{REALM}"', "Content-Type": "text/html; charset=utf-8"},
        )

    # mitmproxy hooks (called from the main addon)
    def http_connect(self, flow: http.HTTPFlow) -> None:
        identity = self._authenticate(flow)
        if identity is None:
            self._deny(flow)
            return
        self._by_conn[flow.client_conn] = identity
        flow.metadata["goallm_identity"] = identity

    def requestheaders(self, flow: http.HTTPFlow) -> None:
        identity = self._by_conn.get(flow.client_conn)
        if identity is None:
            identity = self._authenticate(flow)
            if identity is None:
                self._deny(flow)
                return
            if is_http_proxy(flow):
                # Plain-HTTP proxy requests carry the header every time; keep the connection authenticated.
                self._by_conn[flow.client_conn] = identity
        flow.metadata["goallm_identity"] = identity

    def identity_for_conn(self, client_conn) -> Optional[Identity]:
        return self._by_conn.get(client_conn)
