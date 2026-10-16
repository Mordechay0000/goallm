"""
Extract image content from HTTP response bodies (magic-bytes detection, plus SVG by content type).

Formats that used to slip through unfiltered: AVIF (served by many CDNs to Chrome), HEIC/HEIF,
JPEG XL and SVG. Anything we recognise as an image goes through the image pipeline; a format we
can recognise but not decode ends up as a placeholder (fail-closed), never as the original.
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
    (b"\xff\x0a", "image/jxl"),
    (b"\x00\x00\x00\x0cJXL \r\n\x87\n", "image/jxl"),
]

# ISO-BMFF ("ftyp" box) brands of still/animated images. Video brands (isom, mp42, avc1…) are not here.
_AVIF_BRANDS = {b"avif", b"avis"}
_HEIF_BRANDS = {b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"mif1", b"msf1"}


def _iso_bmff_image_mime(head: bytes) -> str | None:
    if len(head) < 16 or head[4:8] != b"ftyp":
        return None
    box_size = int.from_bytes(head[0:4], "big")
    brands = {head[8:12]}
    end = min(len(head), box_size if 16 <= box_size <= 256 else 32)
    for i in range(16, end - 3, 4):
        brands.add(head[i : i + 4])
    if brands & _AVIF_BRANDS:
        return "image/avif"
    if head[8:12] in _HEIF_BRANDS or (brands & _HEIF_BRANDS and head[8:12] not in (b"isom", b"mp41", b"mp42")):
        return "image/heif"
    return None


def _looks_like_svg(data: bytes, content_type: str) -> bool:
    ct = (content_type or "").lower()
    if "svg" not in ct:
        return False
    head = data[:2048].lstrip().lower()
    return b"<svg" in head


def detect_image_mime(data: bytes, content_type: str = "") -> str | None:
    """Return the image MIME type for these bytes, or None if not an image."""
    if not data or len(data) < 16:
        return None
    head = data[:64]
    for sig, mime in _SIGNATURES:
        if head.startswith(sig):
            return mime
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return "image/webp"
    bmff = _iso_bmff_image_mime(data[:256])
    if bmff:
        return bmff
    if _looks_like_svg(data, content_type):
        return "image/svg+xml"
    return None


def extract_image_content(flow) -> Tuple[bytes, str] | None:
    """
    Detect image from response body.

    Returns:
        (image_bytes, mime_type) if image detected, else None.
    """
    data = flow.response.raw_content
    if not data or len(data) < 16:
        return None
    content_type = flow.response.headers.get("content-type") or ""
    if flow.response.headers.get("content-encoding"):
        # Compressed body (normal for SVG, and a way to hide a raster image from magic-byte checks):
        # decode in place so everything downstream works on the real bytes.
        try:
            decoded = flow.response.content
        except ValueError:
            decoded = None
        if decoded is None or detect_image_mime(decoded, content_type) is None:
            return None
        flow.response.decode()
        data = flow.response.raw_content
    mime = detect_image_mime(data, content_type)
    if mime is None:
        return None
    logger.debug("Detected %s image", mime)
    return data, mime
