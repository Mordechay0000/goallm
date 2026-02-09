"""
Build replacement images (block/checking/error) from SVG templates.
"""
import logging
import re
from io import BytesIO
from typing import Tuple

from PIL import Image

from data.image_placeholders import BLOCK_IMAGE, CHECKING_IMAGE, ERROR_IMAGE

logger = logging.getLogger(__name__)

_DEFAULT_SIZE: Tuple[int, int] = (800, 600)
_MIME_TO_FORMAT = {
    "image/png": "png",
    "image/jpeg": "jpeg",
    "image/jpg": "jpeg",
    "image/webp": "webp",
    "image/bmp": "bmp",
}


def create_image_content(
    svg_content: str,
    mime_type: str,
    size: Tuple[int, int] | None = None,
) -> bytes:
    """
    Render SVG to image bytes in the given MIME format and size.

    Args:
        svg_content: SVG markup string.
        mime_type: Target MIME (e.g. image/png, image/jpeg, image/webp).
        size: (width, height). Default (800, 600) if None.

    Returns:
        Image bytes in the requested format.
    """
    if size is None:
        logger.warning(
            "create_image_content called without size (MIME: %s). Using default %s.",
            mime_type,
            _DEFAULT_SIZE,
        )
        size = _DEFAULT_SIZE
    logger.debug("Creating image content - MIME: %s, size: %s", mime_type, size)

    fmt = _MIME_TO_FORMAT.get(mime_type, "png")
    logger.debug("Target format: %s (from MIME: %s)", fmt, mime_type)

    try:
        import cairosvg
    except ImportError:
        raise ImportError(
            "cairosvg is required for SVG replacement. Install with: pip install cairosvg"
        )

    svg_str = svg_content if isinstance(svg_content, str) else svg_content.decode("utf-8")
    if "preserveAspectRatio=" in svg_str:
        svg_str = re.sub(
            r'preserveAspectRatio="[^"]*"',
            'preserveAspectRatio="none"',
            svg_str,
        )
    else:
        svg_str = re.sub(
            r"(<svg[^>]*)>",
            r'\1 preserveAspectRatio="none">',
            svg_str,
            count=1,
        )
    svg_bytes = svg_str.encode("utf-8")

    out = BytesIO()
    cairosvg.svg2png(
        bytestring=svg_bytes,
        write_to=out,
        output_width=size[0],
        output_height=size[1],
    )
    out.seek(0)
    img = Image.open(out)
    if img.size != size:
        logger.debug("Size mismatch: got %s, expected %s. Resizing.", img.size, size)
        img = img.resize(size, Image.Resampling.LANCZOS)
        out = BytesIO()
        img.save(out, format="PNG")
        out.seek(0)
        img = Image.open(out)

    if fmt != "png":
        img = _ensure_format_mode(img, fmt)
        buf = BytesIO()
        img.save(buf, format=fmt.upper())
        data = buf.getvalue()
        logger.debug("Created %s image, %s bytes", fmt.upper(), len(data))
        return data

    data = out.getvalue()
    logger.debug("Created PNG image, %s bytes", len(data))
    return data


def _ensure_format_mode(img: Image.Image, fmt: str) -> Image.Image:
    """Convert image to a mode suitable for the target format."""
    if fmt == "jpeg":
        if img.mode == "RGBA":
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3])
            return bg
        if img.mode != "RGB":
            return img.convert("RGB")
        return img
    if fmt == "bmp":
        if img.mode == "RGBA":
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3])
            return bg
        if img.mode not in ("RGB", "RGBA"):
            return img.convert("RGB")
        return img
    if fmt == "webp":
        return img
    # default: RGB
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        return bg
    if img.mode != "RGB":
        return img.convert("RGB")
    return img


def get_checking_image(mime_type: str, size: Tuple[int, int] | None = None) -> bytes:
    """Return the 'checking' placeholder image."""
    return create_image_content(CHECKING_IMAGE, mime_type, size)


def get_blocked_image(mime_type: str, size: Tuple[int, int] | None = None) -> bytes:
    """Return the 'blocked' placeholder image."""
    return create_image_content(BLOCK_IMAGE, mime_type, size)


def get_error_image(mime_type: str, size: Tuple[int, int] | None = None) -> bytes:
    """Return the 'error' placeholder image."""
    return create_image_content(ERROR_IMAGE, mime_type, size)
