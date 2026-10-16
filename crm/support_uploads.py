"""
Support ticket/reply file uploads. Saves to .storage/uploads/support/.
"""
import os
import uuid
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

from data.constants import STORAGE_DIR
from data.upload_config import SUPPORT_MAX_BYTES, SUPPORT_ALLOWED_EXTENSIONS

logger = logging.getLogger(__name__)

SUPPORT_UPLOADS_DIR = STORAGE_DIR / "uploads" / "support"


def _normalize_ext(ext: str) -> str:
    ext = (ext or "").strip().lower()
    if ext and not ext.startswith("."):
        ext = "." + ext
    return ext


def validate_support_file(content: bytes, filename: str) -> str:
    """
    Validate file for support upload. Returns safe extension or raises ValueError.
    """
    if len(content) > SUPPORT_MAX_BYTES:
        raise ValueError("גודל הקובץ חורג מהמגבלה (25MB)")
    if not content:
        raise ValueError("קובץ ריק")
    base = os.path.basename((filename or "").strip())
    if ".." in base or not base:
        raise ValueError("שם קובץ לא תקין")
    ext = _normalize_ext(os.path.splitext(base)[1])
    # Allowlist: HTML/SVG/XML/JS would be served from the CRM origin and could run as a page there.
    if ext not in SUPPORT_ALLOWED_EXTENSIONS:
        raise ValueError("סוג קובץ לא נתמך. מותרים: " + ", ".join(sorted(SUPPORT_ALLOWED_EXTENSIONS)))
    return ext


def save_support_file(content: bytes, filename: str, user_id: int) -> Dict[str, str]:
    """
    Save file to support uploads. Returns { "url": "/uploads/support/...", "name": "original name" }.
    """
    ext = validate_support_file(content, filename)
    SUPPORT_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = os.path.basename((filename or "file").strip())[:200]
    if not safe_name or safe_name.startswith("."):
        safe_name = "file" + ext
    stored = f"{user_id}_{uuid.uuid4().hex}{ext}"
    path = SUPPORT_UPLOADS_DIR / stored
    path.write_bytes(content)
    return {"url": f"/uploads/support/{stored}", "name": safe_name}


def attachments_to_json(attachments: List[Dict[str, str]] | None) -> str | None:
    """Serialize attachments for DB. None or empty -> None."""
    if not attachments:
        return None
    return json.dumps(attachments, ensure_ascii=False)


def attachments_from_json(raw: str | None) -> List[Dict[str, str]]:
    """Parse attachments from DB."""
    if not raw or not raw.strip():
        return []
    try:
        out = json.loads(raw)
        if not isinstance(out, list):
            return []
        return [{"name": str(x.get("name", "")), "url": str(x.get("url", ""))} for x in out if isinstance(x, dict)]
    except Exception:
        return []