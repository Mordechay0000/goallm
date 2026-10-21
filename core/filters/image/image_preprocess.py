"""
Prepare image bytes for a vision model.

- Every format is decoded with Pillow and re-encoded as JPEG: llama.cpp / most VLM servers decode only
  JPEG/PNG/BMP/GIF (no WebP, AVIF, ICO, TIFF), so those used to end up as analysis errors.
- SVG is rasterized (vector drawings can depict people too).
- Animated GIF/WebP/APNG/AVIF: several frames are sampled across the animation – the old code looked only
  at the first frame, so a harmless first frame let the rest through.
- Transparent images are composited on white; tiny images are upscaled a little so the model can see them;
  huge images are capped at VLM_MAX_SIDE to bound token cost (small/background people need resolution:
  raise VLM_MAX_SIDE rather than lowering it if recall on small figures is too low).
"""
from __future__ import annotations

import logging
from io import BytesIO
from typing import List

from PIL import Image, ImageSequence

from data.constants import VLM_MAX_ANIMATION_FRAMES, VLM_MAX_SIDE, VLM_MIN_SIDE

logger = logging.getLogger(__name__)


class UnsupportedImageError(ValueError):
    pass


def _rasterize_svg(data: bytes) -> bytes:
    import cairosvg

    return cairosvg.svg2png(bytestring=data, output_width=None, output_height=None, unsafe=False)


def _to_rgb(frame: Image.Image) -> Image.Image:
    if frame.mode in ("RGBA", "LA") or (frame.mode == "P" and "transparency" in frame.info):
        rgba = frame.convert("RGBA")
        bg = Image.new("RGB", rgba.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.split()[-1])
        return bg
    return frame.convert("RGB")


def _resize(img: Image.Image) -> Image.Image:
    w, h = img.size
    longest = max(w, h)
    shortest = min(w, h)
    if longest > VLM_MAX_SIDE:
        ratio = VLM_MAX_SIDE / longest
        return img.resize((max(1, int(w * ratio)), max(1, int(h * ratio))), Image.Resampling.LANCZOS)
    if shortest < VLM_MIN_SIDE:
        ratio = min(VLM_MIN_SIDE / shortest, VLM_MAX_SIDE / longest)
        if ratio > 1:
            return img.resize((max(1, int(w * ratio)), max(1, int(h * ratio))), Image.Resampling.BICUBIC)
    return img


def _sample_indices(n: int, k: int) -> List[int]:
    if n <= k:
        return list(range(n))
    return sorted({round(i * (n - 1) / (k - 1)) for i in range(k)})


def prepare_frames(image_bytes: bytes, mime_type: str | None) -> List[bytes]:
    """Return JPEG frames ready for the model (1 for still images, up to VLM_MAX_ANIMATION_FRAMES for animations)."""
    data = image_bytes
    if mime_type == "image/svg+xml":
        try:
            data = _rasterize_svg(image_bytes)
        except Exception as e:
            raise UnsupportedImageError(f"SVG rasterization failed: {e}") from e
    try:
        img = Image.open(BytesIO(data))
    except Exception as e:
        raise UnsupportedImageError(f"cannot decode image ({mime_type}): {e}") from e

    n_frames = int(getattr(img, "n_frames", 1) or 1)
    wanted = set(_sample_indices(n_frames, max(1, VLM_MAX_ANIMATION_FRAMES)))
    frames: List[bytes] = []
    for idx, frame in enumerate(ImageSequence.Iterator(img)):
        if idx not in wanted:
            continue
        rgb = _resize(_to_rgb(frame))
        buf = BytesIO()
        rgb.save(buf, format="JPEG", quality=92)
        frames.append(buf.getvalue())
        if len(frames) >= len(wanted):
            break
    if not frames:
        raise UnsupportedImageError("no decodable frames")
    return frames
