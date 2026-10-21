"""
Thumbnails for the human review queue (uncertain images, failed analyses, video evidence frames).

Stored under STORAGE_DIR/review/<kind>/<sha256(key)>.jpg, max side 1024. Deleted when an admin decides.
Only admins can read them (CRM endpoints); the proxy never serves them.
"""
from __future__ import annotations

import hashlib
import logging
from io import BytesIO
from pathlib import Path
from typing import Optional

from PIL import Image

from data.constants import STORAGE_DIR

logger = logging.getLogger(__name__)

_ROOT = STORAGE_DIR / "review"
_MAX_SIDE = 1024


def _path(kind: str, key: str) -> Path:
    safe_kind = "videos" if kind == "videos" else "images"
    return _ROOT / safe_kind / (hashlib.sha256(key.encode("utf-8")).hexdigest() + ".jpg")


def save_thumbnail(kind: str, key: str, image: "Image.Image | bytes", mime: Optional[str] = None) -> Optional[Path]:
    try:
        if isinstance(image, (bytes, bytearray)):
            from core.filters.image.image_preprocess import prepare_frames

            data = prepare_frames(bytes(image), mime)[0]
            img = Image.open(BytesIO(data))
        else:
            img = image.convert("RGB")
        img.thumbnail((_MAX_SIDE, _MAX_SIDE))
        path = _path(kind, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(path, format="JPEG", quality=85)
        return path
    except Exception as e:
        logger.warning("review thumbnail save failed (%s %s): %s", kind, key[:16], e)
        return None


def thumbnail_path(kind: str, key: str) -> Optional[Path]:
    p = _path(kind, key)
    return p if p.is_file() else None


def delete_thumbnail(kind: str, key: str) -> None:
    try:
        _path(kind, key).unlink(missing_ok=True)
    except OSError:
        pass
