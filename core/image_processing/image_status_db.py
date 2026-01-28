"""
SQLite persistence for image status (allowed/blocked/pending) and analysis results.
"""
import logging
import os
import sqlite3
import time
from typing import Any

from data.constants import IMAGE_STATUS_TABLE_NAME

logger = logging.getLogger(__name__)

os.makedirs(".storage", exist_ok=True)
_db = sqlite3.connect(".storage/image_status.db", check_same_thread=False)
_db.execute("PRAGMA journal_mode=WAL;")
_db.execute("PRAGMA synchronous=NORMAL;")


def init_schema() -> None:
    """Create or migrate image_status table."""
    logger.info("Initializing image status database schema")
    logger.debug("Table name: %s", IMAGE_STATUS_TABLE_NAME)

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

    for col, ctype in (("mime_type", "TEXT"), ("width", "INTEGER"), ("height", "INTEGER")):
        try:
            _db.execute(
                f"ALTER TABLE {IMAGE_STATUS_TABLE_NAME} ADD COLUMN {col} {ctype}"
            )
            logger.debug("Added column %s", col)
        except sqlite3.OperationalError:
            logger.debug("Column %s already exists", col)

    _db.commit()
    logger.info("Image status schema initialized")


def get_image_status(image_hash: str) -> dict[str, Any] | None:
    """Return status dict (status, mime_type, width, height) or None."""
    logger.debug("Checking image status for hash: %s...", _h8(image_hash))
    cur = _db.execute(
        f"SELECT status, mime_type, width, height FROM {IMAGE_STATUS_TABLE_NAME} "
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
    """Persist analysis result and set status to blocked/allowed."""
    logger.info("Saving analysis result for hash: %s...", _h8(image_hash))
    logger.debug("URL: %s, MIME: %s, Size: %sx%s", image_url, mime_type, width, height)
    logger.debug("Result: %s", result)

    blocked = any(v == "Yes" for v in result.values())
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
            image_hash, status, image_url, mime_type, width, height, updated_at
        ) VALUES (?, 'pending', ?, ?, ?, ?, ?)
        ON CONFLICT(image_hash) DO UPDATE SET
            status = 'pending',
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


init_schema()
