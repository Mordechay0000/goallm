"""
Secure avatar upload. Validates file type (no executables).
"""
import os
import uuid
import logging
from pathlib import Path
from typing import Tuple

logger = logging.getLogger(__name__)

UPLOADS_DIR = Path(__file__).resolve().parent.parent / ".storage" / "uploads" / "avatars"
AVATAR_MAX_BYTES = 5 * 1024 * 1024  # 5MB
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
ALLOWED_MIMES = {"image/jpeg", "image/png", "image/gif", "image/webp"}

# Magic bytes (file signatures). No executables.
MAGIC = {
    b"\xff\xd8\xff": ".jpg",
    b"\x89PNG\r\n\x1a\n": ".png",
    b"GIF87a": ".gif",
    b"GIF89a": ".gif",
    b"RIFF": None,  # webp starts with RIFF....WEBP
}


def _ext_from_magic(data: bytes) -> str | None:
    if data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WEBP":
        return ".webp"
    for sig, ext in MAGIC.items():
        if ext and data.startswith(sig):
            return ext
    return None


def _normalize_ext(ext: str) -> str:
    ext = (ext or "").strip().lower()
    if ext and not ext.startswith("."):
        ext = "." + ext
    return ext


def validate_avatar_file(content: bytes, filename: str, content_type: str | None) -> Tuple[str, str]:
    """
    Validate avatar file. Returns (normalized_ext, mime) or raises ValueError.
    Rejects executables, double extensions, etc.
    """
    if len(content) > AVATAR_MAX_BYTES:
        raise ValueError("גודל הקובץ חורג מהמגבלה (5MB)")
    if not content:
        raise ValueError("קובץ ריק")

    # No path traversal, no double extension
    base = os.path.basename((filename or "").strip())
    if ".." in base or base != (filename or "").strip():
        raise ValueError("שם קובץ לא תקין")
    ext = _normalize_ext(os.path.splitext(base)[1])
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("סוג קובץ לא נתמך. מותרים: JPG, PNG, GIF, WEBP")

    # MIME
    mime = (content_type or "").strip().lower().split(";")[0].strip()
    if mime and mime not in ALLOWED_MIMES:
        raise ValueError("סוג קובץ לא נתמך")

    # Magic bytes (real content, not renamed .exe etc.)
    detected = _ext_from_magic(content)
    if not detected:
        raise ValueError("קובץ לא מזוהה כתמונה תקינה")
    # .jpeg and .jpg both map to jpeg magic
    if detected == ".jpg" and ext == ".jpeg":
        ext = ".jpg"
    elif detected != ext:
        raise ValueError("תוכן הקובץ לא תואם לסיומת")

    return ext, mime or "application/octet-stream"


def save_avatar(content: bytes, ext: str, user_id: int | None) -> str:
    """
    Save avatar to disk. Returns URL path like /uploads/avatars/xxx.ext
    """
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{user_id or 'temp'}_{uuid.uuid4().hex[:12]}{ext}"
    path = UPLOADS_DIR / name
    path.write_bytes(content)
    return f"/uploads/avatars/{name}"
