"""
Support ticket/reply file uploads. Saves to .storage/uploads/support/.
"""
import os
import uuid
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

SUPPORT_UPLOADS_DIR = Path(__file__).resolve().parent.parent / ".storage" / "uploads" / "support"
SUPPORT_MAX_BYTES = 25 * 1024 * 1024  # 25MB per file
# Allow images, pdf, audio/video (webm), text
ALLOWED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp",
    ".pdf",
    ".webm", ".mp4", ".ogg", ".mp3", ".wav", ".m4a",
    ".txt", ".md", ".csv",
    ".doc", ".docx", ".xls", ".xlsx",
}
# Block executables and scripts
BLOCKED_EXTENSIONS = {".exe", ".bat", ".cmd", ".sh", ".ps1", ".js", ".vbs", ".jar", ".py", ".php"}


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
    if ext in BLOCKED_EXTENSIONS:
        raise ValueError("סוג קובץ לא מורשה")
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("סוג קובץ לא נתמך. מותרים: תמונות, PDF, וידאו/אודיו (webm), מסמכים")
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
    stored = f"{user_id}_{uuid.uuid4().hex[:14]}{ext}"
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