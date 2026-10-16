"""
SQLite persistence for image status (allowed/blocked/pending) and analysis results.
Uses project-root .storage so proxy (run from any CWD) and CRM share the same DB.
"""
import logging
import sqlite3
import time
from typing import Any

from core.db_utils import ThreadLocalSQLite
from data.constants import IMAGE_STATUS_TABLE_NAME, STORAGE_DIR

logger = logging.getLogger(__name__)

STORAGE_DIR.mkdir(parents=True, exist_ok=True)
_db_path = STORAGE_DIR / "image_status.db"
# One connection per thread: the proxy thread pool and the analysis workers write concurrently.
_db = ThreadLocalSQLite(str(_db_path))


# גרסת אלגוריתם ה־hash: 1 = raw bytes, 2 = normalized (strip meta, canonical format)
HASH_VERSION = 2

# Expected analysis result keys (must match analyzers). Used to validate before persist.
EXPECTED_RESULT_KEYS = (
    "female_visible_9_plus",
    "female_3_to_9_partial_clothing",
    "female_under_3_minimal_clothing",
    "boys_teens_men_exposed_or_bathing",
    "any_visible_body_exposure",
)


def init_schema() -> None:
    """Create or migrate image_status table. On hash version upgrade, clear table (old hashes invalid)."""
    logger.info("Initializing image status database schema")
    logger.debug("Table name: %s", IMAGE_STATUS_TABLE_NAME)

    _db.execute(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )

    _db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {IMAGE_STATUS_TABLE_NAME} (
            image_hash TEXT PRIMARY KEY,
            image_url TEXT,
            status TEXT,
            mime_type TEXT,
            width INTEGER,
            height INTEGER,
            female_visible_9_plus INTEGER,
            female_3_to_9_partial_clothing INTEGER,
            female_under_3_minimal_clothing INTEGER,
            boys_teens_men_exposed_or_bathing INTEGER,
            any_visible_body_exposure INTEGER,
            updated_at INTEGER
        )
        """
    )
    logger.debug("Created table if not exists")

    for col, ctype in (("mime_type", "TEXT"), ("width", "INTEGER"), ("height", "INTEGER"), ("attempts", "INTEGER NOT NULL DEFAULT 0")):
        try:
            _db.execute(
                f"ALTER TABLE {IMAGE_STATUS_TABLE_NAME} ADD COLUMN {col} {ctype}"
            )
            logger.debug("Added column %s", col)
        except sqlite3.OperationalError:
            logger.debug("Column %s already exists", col)

    cur = _db.execute("SELECT value FROM meta WHERE key = 'hash_version'")
    row = cur.fetchone()
    stored_version = int(row[0]) if row and row[0].strip().isdigit() else 1
    if stored_version < HASH_VERSION:
        _db.execute(f"DELETE FROM {IMAGE_STATUS_TABLE_NAME}")
        _db.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('hash_version', ?)",
            (str(HASH_VERSION),),
        )
        logger.info(
            "Image status table cleared (hash version upgrade %s -> %s); hashes are now normalized",
            stored_version,
            HASH_VERSION,
        )

    _db.commit()
    logger.info("Image status schema initialized")


def get_image_status(image_hash: str) -> dict[str, Any] | None:
    """Return status dict (status, mime_type, width, height) or None."""
    logger.debug("Checking image status for hash: %s...", _h8(image_hash))
    cur = _db.execute(
        f"SELECT status, mime_type, width, height, updated_at, COALESCE(attempts, 0) FROM {IMAGE_STATUS_TABLE_NAME} "
        "WHERE image_hash = ?",
        (image_hash,),
    )
    row = cur.fetchone()
    if not row:
        logger.debug("No status found for hash %s", _h8(image_hash))
        return None
    out = {
        "status": row[0],
        "mime_type": row[1],
        "width": row[2],
        "height": row[3],
        "updated_at": row[4],
        "attempts": row[5],
    }
    logger.debug("Found status for hash %s: %s", _h8(image_hash), out)
    return out


def save_analysis_result(
    image_hash: str,
    result: dict,
    image_url: str | None = None,
    mime_type: str | None = None,
    width: int | None = None,
    height: int | None = None,
) -> None:
    """Persist analysis result and set status to blocked/allowed. Validates result shape."""
    logger.info("Saving analysis result for hash: %s...", _h8(image_hash))
    logger.debug("URL: %s, MIME: %s, Size: %sx%s", image_url, mime_type, width, height)
    logger.debug("Result: %s", result)

    if not isinstance(result, dict):
        raise ValueError(f"result must be a dict, got {type(result).__name__}")
    missing = set(EXPECTED_RESULT_KEYS) - set(result.keys())
    if missing:
        raise ValueError(f"result missing required keys: {missing}")
    for k in EXPECTED_RESULT_KEYS:
        if result[k] not in ("Yes", "No"):
            raise ValueError(f"result[{k!r}] must be 'Yes' or 'No', got {result[k]!r}")

    blocked = any(result[k] == "Yes" for k in EXPECTED_RESULT_KEYS)
    logger.info("Image blocked: %s", blocked)

    _db.execute(
        f"""
        INSERT INTO {IMAGE_STATUS_TABLE_NAME} (
            image_hash, image_url, status, mime_type, width, height,
            female_visible_9_plus, female_3_to_9_partial_clothing,
            female_under_3_minimal_clothing, boys_teens_men_exposed_or_bathing,
            any_visible_body_exposure, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(image_hash) DO UPDATE SET
            image_url = COALESCE(excluded.image_url, image_url),
            status = excluded.status,
            mime_type = COALESCE(excluded.mime_type, mime_type),
            width = COALESCE(excluded.width, width),
            height = COALESCE(excluded.height, height),
            female_visible_9_plus = excluded.female_visible_9_plus,
            female_3_to_9_partial_clothing = excluded.female_3_to_9_partial_clothing,
            female_under_3_minimal_clothing = excluded.female_under_3_minimal_clothing,
            boys_teens_men_exposed_or_bathing = excluded.boys_teens_men_exposed_or_bathing,
            any_visible_body_exposure = excluded.any_visible_body_exposure,
            updated_at = excluded.updated_at
        """,
        (
            image_hash,
            image_url,
            "blocked" if blocked else "allowed",
            mime_type,
            width,
            height,
            result.get("female_visible_9_plus") == "Yes",
            result.get("female_3_to_9_partial_clothing") == "Yes",
            result.get("female_under_3_minimal_clothing") == "Yes",
            result.get("boys_teens_men_exposed_or_bathing") == "Yes",
            result.get("any_visible_body_exposure") == "Yes",
            int(time.time()),
        ),
    )
    _db.commit()


def mark_pending(
    image_hash: str,
    image_url: str | None = None,
    mime_type: str | None = None,
    width: int | None = None,
    height: int | None = None,
) -> None:
    """Mark image as pending analysis."""
    logger.info(
        "Marking pending - Hash: %s, URL: %s, MIME: %s, Size: %sx%s",
        _h8(image_hash),
        image_url,
        mime_type,
        width,
        height,
    )
    _db.execute(
        f"""
        INSERT INTO {IMAGE_STATUS_TABLE_NAME} (
            image_hash, status, image_url, mime_type, width, height, updated_at, attempts
        ) VALUES (?, 'pending', ?, ?, ?, ?, ?, 1)
        ON CONFLICT(image_hash) DO UPDATE SET
            status = 'pending',
            attempts = COALESCE(attempts, 0) + 1,
            image_url = COALESCE(excluded.image_url, image_url),
            mime_type = COALESCE(excluded.mime_type, mime_type),
            width = COALESCE(excluded.width, width),
            height = COALESCE(excluded.height, height),
            updated_at = excluded.updated_at
        """,
        (image_hash, image_url, mime_type, width, height, int(time.time())),
    )
    _db.commit()


def mark_error(
    image_hash: str,
    error_message: str | None = None,
    image_url: str | None = None,
    mime_type: str | None = None,
    width: int | None = None,
    height: int | None = None,
) -> None:
    """Mark image as error (e.g. analysis failed or timed out)."""
    logger.info(
        "Marking error - Hash: %s, URL: %s, error: %s",
        _h8(image_hash),
        image_url,
        (error_message or "")[:200],
    )
    _db.execute(
        f"""
        INSERT INTO {IMAGE_STATUS_TABLE_NAME} (
            image_hash, status, image_url, mime_type, width, height, updated_at
        ) VALUES (?, 'error', ?, ?, ?, ?, ?)
        ON CONFLICT(image_hash) DO UPDATE SET
            status = 'error',
            image_url = COALESCE(excluded.image_url, image_url),
            mime_type = COALESCE(excluded.mime_type, mime_type),
            width = COALESCE(excluded.width, width),
            height = COALESCE(excluded.height, height),
            updated_at = excluded.updated_at
        """,
        (image_hash, image_url, mime_type, width, height, int(time.time())),
    )
    _db.commit()


def _h8(h: str) -> str:
    return h[:8] + "..." if isinstance(h, str) and len(h) >= 8 else "unknown"


def clear_all_image_status() -> int:
    """Empty the image_status table (e.g. after hash algorithm change). Returns number of rows deleted."""
    cur = _db.execute(f"SELECT COUNT(*) FROM {IMAGE_STATUS_TABLE_NAME}")
    count = cur.fetchone()[0] if cur else 0
    _db.execute(f"DELETE FROM {IMAGE_STATUS_TABLE_NAME}")
    _db.commit()
    logger.info("Cleared all image status rows: %s", count)
    return count


init_schema()
