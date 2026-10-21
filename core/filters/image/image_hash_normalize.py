"""
נורמליזציה קלה לתמונה לפני חישוב hash – כדי ששינוי רק ב־meta (EXIF וכו') לא ייצור בדיקה חדשה.
קל משאבים: decode, strip metadata, re-encode ל־format קבוע. אופציונלי: resize למקסימום כדי לחסוך זיכרון.
"""
import logging
from io import BytesIO
from typing import Optional

from PIL import Image

from data.constants import MAX_SIDE_FOR_HASH, JPEG_QUALITY

logger = logging.getLogger(__name__)


def normalize_image_for_hash(image_data: bytes, mime_type: Optional[str] = None) -> Optional[bytes]:
    """
    מחזיר bytes מנורמליים לחישוב hash: ללא EXIF/meta, פורמט קבוע (RGB → JPEG).
    אם נכשל (תמונה פגומה וכו') – מחזיר None (יש ליפול ל־hash על ה־bytes המקוריים).
    קל משאבים: decode אחד, resize רק אם גדול, encode אחד.
    """
    if mime_type == "image/svg+xml":
        return None  # vector: hash the exact bytes
    try:
        img = Image.open(BytesIO(image_data))
        if getattr(img, "is_animated", False):
            # Normalizing would keep only the first frame: two animations sharing a harmless first frame
            # would share one verdict. Hash the exact bytes instead.
            return None
        img.load()
    except Exception as e:
        logger.debug("Image open failed for hash normalization: %s", e)
        return None

    try:
        if img.mode != "RGB":
            img = img.convert("RGB")

        w, h = img.size
        if max(w, h) > MAX_SIDE_FOR_HASH:
            ratio = MAX_SIDE_FOR_HASH / max(w, h)
            new_w = max(1, int(w * ratio))
            new_h = max(1, int(h * ratio))
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        out = BytesIO()
        img.save(out, format="JPEG", quality=JPEG_QUALITY)
        return out.getvalue()
    except Exception as e:
        logger.debug("Image normalize failed: %s", e)
        return None
