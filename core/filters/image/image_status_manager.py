"""
Orchestrates image status checks: DB lookup, analysis queue, and replacement images.
"""
import hashlib
import logging
import os
from io import BytesIO
from typing import Tuple, Any

from PIL import Image

from core.filters.image import simulated_image_analyzer
from core.filters.image.image_processing_queue import ImageProcessingQueue
from core.filters.image.image_status_db import (
    get_image_status,
    save_analysis_result,
    mark_pending,
    mark_error,
)
from core.filters.image.image_replacement import (
    get_checking_image,
    get_blocked_image,
    get_error_image,
)
from core.filters.image.image_hash_normalize import normalize_image_for_hash

logger = logging.getLogger(__name__)

try:
    from core.filters.image.llm_image_analyzer import LLMImageAnalyzer
except ImportError:
    LLMImageAnalyzer = None  # optional


def _create_image_analyzer():
    """Choose analyzer: LLM if USE_LLM_IMAGE_ANALYZER=1 and available, else simulated."""
    from data.constants import USE_LLM_IMAGE_ANALYZER
    if USE_LLM_IMAGE_ANALYZER and LLMImageAnalyzer is not None:
        logger.info("Using LLM image analyzer (USE_LLM_IMAGE_ANALYZER=1)")
        return LLMImageAnalyzer()
    logger.info("Using simulated image analyzer")
    return simulated_image_analyzer.SimulatedImageAnalyzer()


def _on_analysis_done(
    task_id: str,
    status: Any,
    result: dict | None,
    image_details: dict,
    error: str | None,
) -> None:
    """Callback when an image analysis task completes. Must not raise so queue can always call task_done()."""
    if not image_details or not isinstance(image_details.get("image_hash"), str):
        logger.error(
            "on_analysis_done: missing or invalid image_hash in details (task_id=%s), skipping persist",
            task_id,
        )
        return

    status_str = status.value if hasattr(status, "value") else str(status)
    h = image_details["image_hash"]
    h8 = h[:8] + "..." if len(h) >= 8 else "unknown"

    logger.info(
        "Image analysis complete - Task: %s, Hash: %s, Status: %s",
        task_id,
        h8,
        status_str,
    )
    logger.debug(
        "Task details - URL: %s, MIME: %s, Size: %sx%s",
        image_details.get("image_url"),
        image_details.get("mime_type"),
        image_details.get("width"),
        image_details.get("height"),
    )

    if error:
        logger.warning("Analysis error for hash %s: %s", h8, error)

    try:
        if result is not None:
            logger.debug("Analysis result: %s", result)
            save_analysis_result(
                h,
                result,
                image_details.get("image_url"),
                image_details.get("mime_type"),
                image_details.get("width"),
                image_details.get("height"),
            )
            logger.info("Saved analysis for hash %s", h8)
        else:
            logger.error("Image analysis failed for hash %s: %s", h8, error)
            mark_error(
                h,
                error_message=error,
                image_url=image_details.get("image_url"),
                mime_type=image_details.get("mime_type"),
                width=image_details.get("width"),
                height=image_details.get("height"),
            )
    except Exception as e:
        logger.exception(
            "Failed to persist analysis result for task %s (hash %s): %s",
            task_id,
            h8,
            e,
        )


_image_queue = ImageProcessingQueue(
    image_analyzer=_create_image_analyzer(),
    on_task_done=_on_analysis_done,
)


def _dimensions(data: bytes) -> Tuple[int | None, int | None]:
    """Return (width, height) from image bytes, or (None, None) on error."""
    try:
        img = Image.open(BytesIO(data))
        return img.size
    except Exception as e:
        logger.warning("Could not get image dimensions: %s", e)
        return None, None


def _size_key(info: dict | None) -> Tuple[int | None, int | None]:
    """(width, height) from status info or (None, None)."""
    if not info:
        return None, None
    return info.get("width"), info.get("height")


def get_image_with_status(
    image_data: bytes,
    image_url: str,
    referer_url: str | None,
    image_mime_type: str,
) -> Tuple[bytes, Any, str]:
    """
    Resolve image status and return (image_bytes, reserved, status).
    The second value is always None (kept for API compatibility).

    status: "checking" | "blocked" | "allowed" | "pending" | "error"
    - If unknown: enqueue for analysis, return checking placeholder (status "checking").
    - If blocked: return blocked placeholder (status "blocked").
    - If allowed: return original image (status "allowed").
    - If pending: return checking placeholder (status "pending").
    - On error: return error placeholder (status "error").
    """
    logger.info(
        "Processing image request - URL: %s, MIME: %s, Referer: %s",
        image_url,
        image_mime_type,
        referer_url,
    )
    logger.debug("Image data size: %s bytes", len(image_data))

    to_hash = normalize_image_for_hash(image_data, image_mime_type)
    if to_hash is None:
        to_hash = image_data
    h = hashlib.sha256(to_hash).hexdigest()
    h8 = h[:8] + "..."
    logger.debug("Image hash: %s", h8)

    info = get_image_status(h)
    w, hi = _size_key(info)
    if info is None or w is None or hi is None:
        w, hi = _dimensions(image_data)

    if info is None:
        logger.info("New image (hash: %s), enqueueing for analysis", h8)
        _image_queue.enqueue(
            image_content=image_data,
            image_mime_type=image_mime_type,
            image_details={
                "image_hash": h,
                "image_url": image_url,
                "mime_type": image_mime_type,
                "width": w,
                "height": hi,
            },
        )
        mark_pending(h, image_url, image_mime_type, w, hi)
        size = (w, hi) if (w and hi) else None
        out = get_checking_image(image_mime_type, size)
        logger.info("Returning CHECKING image for new image (hash: %s)", h8)
        return out, None, "checking"

    status = info["status"]
    mime = info.get("mime_type") or image_mime_type
    sw, sh = info.get("width"), info.get("height")
    logger.info(
        "Image status: %s for hash %s (stored size: %sx%s, MIME: %s)",
        status,
        h8,
        sw,
        sh,
        mime,
    )

    size = (sw, sh) if (sw and sh) else None

    if status == "blocked":
        logger.info("Returning BLOCKED image for hash %s", h8)
        return get_blocked_image(mime, size), None, "blocked"
    if status == "allowed":
        logger.info("Returning original image for hash %s", h8)
        return image_data, None, "allowed"
    if status == "pending":
        logger.info("Returning CHECKING image for pending hash %s", h8)
        return get_checking_image(mime, size), None, "pending"

    logger.warning("Unknown status %r for hash %s, returning ERROR image", status, h8)
    return get_error_image(mime, size), None, "error"
