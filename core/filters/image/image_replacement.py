"""
Build replacement images (block/checking/error) from SVG templates.
Now uses blurred versions of the actual image instead of placeholders,
with status text overlay (e.g. "נחסם", "נשלח לבדיקה", "שגיאה").
"""
import logging
import os
import re
from io import BytesIO
from typing import Tuple

from PIL import Image, ImageDraw, ImageFont

from data.image_placeholders import BLOCK_IMAGE, CHECKING_IMAGE, ERROR_IMAGE

logger = logging.getLogger(__name__)

# Status labels in Hebrew
STATUS_LABELS = {
    "blocked": "נחסם",
    "checking": "נשלח לבדיקה",
    "error": "שגיאה",
}

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


def _get_hebrew_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a font that supports Hebrew. Falls back to default if none found."""
    font_paths = [
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Hebrew.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
    ]
    for path in font_paths:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception as e:
                logger.debug("Could not load font %s: %s", path, e)
    return ImageFont.load_default()


def _get_text_color_for_image(img: Image.Image) -> Tuple[int, int, int]:
    """Return white or black depending on image brightness for best contrast."""
    img_rgb = img.convert("RGB")
    pixels = list(img_rgb.getdata())
    if not pixels:
        return (255, 255, 255)
    avg = sum(sum(p) for p in pixels) / (3 * len(pixels))
    return (0, 0, 0) if avg > 128 else (255, 255, 255)


def _draw_status_overlay(
    img: Image.Image, text: str, status_type: str
) -> Image.Image:
    """
    Draw a simple monochrome geometric icon + status text centered on image.

    Icons (all non‑צבעוני, באותו צבע כמו הטקסט):
    - blocked: עיגול עם קו אלכסוני (סמל איסור)
    - checking: עיגול עם נקודה במרכז (בהמתנה)
    - error:  X   (שגיאה)
    """
    draw = ImageDraw.Draw(img)
    w, h = img.size
    # Proportional sizes: ~12–14% of smaller dimension for text, ~20–25% for icon
    min_dim = min(w, h)
    text_font_size = max(20, min_dim // 7)
    icon_box_size = max(32, min_dim // 4)
    text_font = _get_hebrew_font(text_font_size)
    color = _get_text_color_for_image(img)
    outline = (255 - color[0], 255 - color[1], 255 - color[2])

    # Text bbox (for width/height)
    text_bbox = draw.textbbox((0, 0), text, font=text_font)
    text_w = text_bbox[2] - text_bbox[0]
    text_h = text_bbox[3] - text_bbox[1]

    icon_h = icon_box_size
    gap = max(4, min_dim // 50)
    total_h = icon_h + gap + text_h
    start_y = (h - total_h) // 2

    # --- Draw icon (מונוכרומטי) ---
    icon_top = start_y
    icon_bottom = icon_top + icon_box_size
    icon_left = (w - icon_box_size) // 2
    icon_right = icon_left + icon_box_size
    cx = (icon_left + icon_right) / 2
    cy = (icon_top + icon_bottom) / 2
    r = icon_box_size * 0.4

    # helper to draw with outline for better visibility
    def _draw_line(x1, y1, x2, y2, width: int = 4) -> None:
        draw.line((x1, y1, x2, y2), fill=color, width=width)

    def _draw_circle(x1, y1, x2, y2, width: int = 4, fill_center: bool = False) -> None:
        draw.ellipse((x1, y1, x2, y2), outline=color, width=width)
        if fill_center:
            inner_r = (x2 - x1) * 0.18
            draw.ellipse(
                (cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r),
                fill=color,
            )

    if status_type == "blocked":
        # Circle with diagonal line
        _draw_circle(
            cx - r,
            cy - r,
            cx + r,
            cy + r,
            width=max(3, icon_box_size // 18),
        )
        _draw_line(
            cx - r * 0.8,
            cy - r * 0.8,
            cx + r * 0.8,
            cy + r * 0.8,
            width=max(3, icon_box_size // 18),
        )
    elif status_type == "checking":
        # Circle with center dot (pending)
        _draw_circle(
            cx - r,
            cy - r,
            cx + r,
            cy + r,
            width=max(3, icon_box_size // 18),
            fill_center=True,
        )
    elif status_type == "error":
        # X shape
        margin = icon_box_size * 0.25
        _draw_line(
            icon_left + margin,
            icon_top + margin,
            icon_right - margin,
            icon_bottom - margin,
            width=max(3, icon_box_size // 18),
        )
        _draw_line(
            icon_left + margin,
            icon_bottom - margin,
            icon_right - margin,
            icon_top + margin,
            width=max(3, icon_box_size // 18),
        )

    # --- Draw text under icon ---
    text_x = (w - text_w) // 2
    text_y = start_y + icon_h + gap
    for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1), (0, -1), (0, 1), (-1, 0), (1, 0)]:
        draw.text((text_x + dx, text_y + dy), text, font=text_font, fill=outline)
    draw.text((text_x, text_y), text, font=text_font, fill=color)
    return img


def _blur_image(
    image_data: bytes,
    blur_size: Tuple[int, int],
    mime_type: str,
    status_type: str | None = None,
) -> bytes:
    """
    Blur an image by resizing it to a very small size and scaling it back up.
    Optionally draws icon + status text (e.g. ⊘ "נחסם", ⏳ "נשלח לבדיקה") centered on the image.

    Args:
        image_data: Original image bytes
        blur_size: Target size for blur (width, height) - e.g., (3, 3) or (5, 5)
        mime_type: MIME type of the image
        status_type: Optional status key ("blocked", "checking", "error") for icon + label overlay

    Returns:
        Blurred image bytes in the same format
    """
    try:
        img = Image.open(BytesIO(image_data))
        original_size = img.size

        logger.debug(
            "Blurring image from %s to %s pixels (blur size: %s)",
            original_size,
            blur_size,
            blur_size,
        )

        # Resize to very small size (creates blur effect)
        blurred = img.resize(blur_size, Image.Resampling.LANCZOS)

        # Scale back up to original size
        blurred = blurred.resize(original_size, Image.Resampling.NEAREST)

        # Ensure format compatibility for drawing
        blurred = blurred.convert("RGB")

        # Draw icon + status text if provided
        if status_type and status_type in STATUS_LABELS:
            blurred = _draw_status_overlay(
                blurred, STATUS_LABELS[status_type], status_type
            )

        fmt = _MIME_TO_FORMAT.get(mime_type, "png")
        blurred = _ensure_format_mode(blurred, fmt)

        # Save to bytes
        buf = BytesIO()
        blurred.save(buf, format=fmt.upper())
        return buf.getvalue()
    except Exception as e:
        logger.warning("Failed to blur image, falling back to placeholder: %s", e)
        return create_image_content(CHECKING_IMAGE, mime_type, None)


def get_checking_image(
    mime_type: str,
    size: Tuple[int, int] | None = None,
    image_data: bytes | None = None,
) -> bytes:
    """
    Return a blurred version of the image (5x5 blur) if image_data is provided,
    otherwise return the 'checking' placeholder image.
    """
    if image_data is not None:
        try:
            return _blur_image(
                image_data, (5, 5), mime_type, status_type="checking"
            )
        except Exception as e:
            logger.warning("Failed to process image for checking blur: %s", e)
            return create_image_content(CHECKING_IMAGE, mime_type, size)
    return create_image_content(CHECKING_IMAGE, mime_type, size)


def get_blocked_image(
    mime_type: str,
    size: Tuple[int, int] | None = None,
    image_data: bytes | None = None,
) -> bytes:
    """
    Return a blurred version of the image (3x3 blur) if image_data is provided,
    otherwise return the 'blocked' placeholder image.
    """
    if image_data is not None:
        try:
            return _blur_image(
                image_data, (3, 3), mime_type, status_type="blocked"
            )
        except Exception as e:
            logger.warning("Failed to process image for blocked blur: %s", e)
            return create_image_content(BLOCK_IMAGE, mime_type, size)
    return create_image_content(BLOCK_IMAGE, mime_type, size)


def get_error_image(
    mime_type: str,
    size: Tuple[int, int] | None = None,
    image_data: bytes | None = None,
) -> bytes:
    """
    Return a blurred version with "שגיאה" overlay if image_data is provided,
    otherwise return the 'error' placeholder image.
    """
    if image_data is not None:
        try:
            return _blur_image(
                image_data, (5, 5), mime_type, status_type="error"
            )
        except Exception as e:
            logger.warning("Failed to process image for error blur: %s", e)
            return create_image_content(ERROR_IMAGE, mime_type, size)
    return create_image_content(ERROR_IMAGE, mime_type, size)
