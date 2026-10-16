"""
Orchestrates image status checks: DB lookup, analysis queue, and replacement images.
"""
import hashlib
import logging
import threading
import time
from collections import OrderedDict
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
from data.constants import ERROR_RETRY_SECONDS, MAX_ANALYSIS_ATTEMPTS, PENDING_STALE_SECONDS

logger = logging.getLogger(__name__)

def _create_image_analyzer():
    """Choose analyzer by IMAGE_ANALYZER: openai (production: vLLM/SGLang/llama-server), llama_cpp (local), simulated (dev)."""
    from data.constants import IMAGE_ANALYZER
    if IMAGE_ANALYZER == "openai":
        from core.filters.image.analyzers.openai_compat import OpenAICompatImageAnalyzer
        logger.info("Using OpenAI-compatible VLM analyzer")
        return OpenAICompatImageAnalyzer()
    if IMAGE_ANALYZER == "llama_cpp":
        try:
            from core.filters.image.llm_image_analyzer import LLMImageAnalyzer
            logger.info("Using local llama.cpp VLM analyzer")
            return LLMImageAnalyzer()
        except Exception as e:
            logger.error("llama.cpp analyzer unavailable (%s) – falling back to SIMULATED analyzer (dev only!)", e)
    logger.warning("Using SIMULATED image analyzer – results are NOT based on image content (development only)")
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


# raw sha256 → normalized hash. Normalizing (decode + resize + JPEG encode) on every image request was the
# most expensive step of the hot path, even for images already decided long ago.
_RAW_HASH_CACHE_MAX = 50000
_raw_hash_cache: "OrderedDict[str, str]" = OrderedDict()
_raw_hash_lock = threading.Lock()


def _image_hash(image_data: bytes, mime_type: str) -> str:
    raw = hashlib.sha256(image_data).hexdigest()
    with _raw_hash_lock:
        h = _raw_hash_cache.get(raw)
        if h is not None:
            _raw_hash_cache.move_to_end(raw)
            return h
    to_hash = normalize_image_for_hash(image_data, mime_type)
    h = hashlib.sha256(to_hash).hexdigest() if to_hash is not None else raw
    with _raw_hash_lock:
        _raw_hash_cache[raw] = h
        if len(_raw_hash_cache) > _RAW_HASH_CACHE_MAX:
            _raw_hash_cache.popitem(last=False)
    return h


# URLs that just received a "checking" placeholder → hash, so the page script can ask "is it ready?"
_PENDING_URLS_MAX = 20000
_pending_urls: "OrderedDict[str, str]" = OrderedDict()
_pending_lock = threading.Lock()


def _remember_pending_url(url: str, h: str) -> None:
    with _pending_lock:
        _pending_urls[url] = h
        _pending_urls.move_to_end(url)
        if len(_pending_urls) > _PENDING_URLS_MAX:
            _pending_urls.popitem(last=False)


def get_url_statuses(urls) -> dict:
    """For the in-page refresh script: {url: "ready"|"pending"} for URLs we served a placeholder for."""
    out = {}
    for url in list(urls)[:300]:
        with _pending_lock:
            h = _pending_urls.get(url)
        if h is None:
            continue
        info = get_image_status(h)
        if info is not None and info["status"] in ("allowed", "blocked", "error"):
            out[url] = "ready"
            with _pending_lock:
                _pending_urls.pop(url, None)
        else:
            out[url] = "pending"
    return out


def _should_retry(info: dict) -> bool:
    """Pending too long (queue is in memory – lost on restart) or a failed analysis that may succeed now."""
    if _image_queue.is_inflight(info.get("_hash", "")):
        return False
    age = time.time() - int(info.get("updated_at") or 0)
    attempts = int(info.get("attempts") or 0)
    if info["status"] == "pending":
        return age > PENDING_STALE_SECONDS
    if info["status"] == "error":
        return age > ERROR_RETRY_SECONDS and attempts < MAX_ANALYSIS_ATTEMPTS
    return False


def _enqueue(image_data: bytes, image_url: str, mime: str, h: str, w, hi) -> None:
    task_id = _image_queue.enqueue(
        image_content=image_data,
        image_mime_type=mime,
        image_details={"image_hash": h, "image_url": image_url, "mime_type": mime, "width": w, "height": hi},
    )
    if task_id is not None:
        mark_pending(h, image_url, mime, w, hi)


def _placeholder(kind: str, mime: str, size, image_data: bytes) -> bytes:
    if mime == "image/svg+xml":
        # Cannot blur vector source; fall back to the generic placeholder (rendered as PNG).
        image_data = None
        mime = "image/png"
    if kind == "blocked":
        return get_blocked_image(mime, size, image_data)
    if kind == "error":
        return get_error_image(mime, size, image_data)
    return get_checking_image(mime, size, image_data)


def get_image_with_status(
    image_data: bytes,
    image_url: str,
    referer_url: str | None,
    image_mime_type: str,
) -> Tuple[bytes, Any, str]:
    """
    Resolve image status and return (image_bytes, content_type_override, status).
    content_type_override is set when the returned bytes are not of the original type (SVG placeholders are PNG).

    status: "checking" | "blocked" | "allowed" | "pending" | "error"
    - unknown → enqueue for analysis, return checking placeholder
    - blocked → blocked placeholder; allowed → original image
    - pending → checking placeholder (re-enqueued if stale); error → error placeholder (retried a few times)
    """
    h = _image_hash(image_data, image_mime_type)
    h8 = h[:8] + "..."
    info = get_image_status(h)
    if info is not None:
        info["_hash"] = h
    w, hi = _size_key(info)
    if info is None or w is None or hi is None:
        w, hi = _dimensions(image_data)
    size = (w, hi) if (w and hi) else None
    ct_override = "image/png" if image_mime_type == "image/svg+xml" else None

    if info is None:
        logger.info("New image (hash: %s), enqueueing for analysis", h8)
        _enqueue(image_data, image_url, image_mime_type, h, w, hi)
        _remember_pending_url(image_url, h)
        return _placeholder("checking", image_mime_type, size, image_data), ct_override, "checking"

    status = info["status"]
    mime = info.get("mime_type") or image_mime_type
    if status == "allowed":
        return image_data, None, "allowed"
    if status == "blocked":
        return _placeholder("blocked", image_mime_type, size, image_data), ct_override, "blocked"
    if status in ("pending", "error") and _should_retry(info):
        logger.info("Re-enqueueing %s image (hash: %s, attempts=%s)", status, h8, info.get("attempts"))
        _enqueue(image_data, image_url, image_mime_type, h, w, hi)
        _remember_pending_url(image_url, h)
        return _placeholder("checking", image_mime_type, size, image_data), ct_override, "pending"
    if status == "pending":
        _remember_pending_url(image_url, h)
        return _placeholder("checking", image_mime_type, size, image_data), ct_override, "pending"
    logger.warning("Status %r for hash %s (mime %s), returning ERROR image", status, h8, mime)
    return _placeholder("error", image_mime_type, size, image_data), ct_override, "error"
