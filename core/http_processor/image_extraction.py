"""
Extract image content from HTTP response bodies (binary and magic-bytes detection).
"""
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# Magic bytes for raster formats (first bytes)
_SIGNATURES = [
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"BM", "image/bmp"),
    (b"\x00\x00\x01\x00", "image/x-icon"),
    (b"II*\x00", "image/tiff"),
    (b"MM\x00*", "image/tiff"),
]


def extract_image_content(flow) -> Tuple[bytes, str] | None:
    """
    Detect image from response body via magic bytes.

    Returns:
        (image_bytes, mime_type) if image detected, else None.
    """
    logger.debug("Extracting image content from HTTP response")
    data = flow.response.raw_content
    if not data or len(data) < 16:
        logger.debug(
            "Response too small or empty (%s bytes), not an image",
            len(data) if data else 0,
        )
        return None

    head = data[:32]
    logger.debug("Checking image signature, first 32 bytes: %s...", head[:16].hex())

    for sig, mime in _SIGNATURES:
        if head.startswith(sig):
            logger.debug("Detected %s image", mime)
            return data, mime

    if head.startswith(b"RIFF") and b"WEBP" in head:
        logger.debug("Detected WEBP image")
        return data, "image/webp"

    logger.debug("No image format detected")
    return None
