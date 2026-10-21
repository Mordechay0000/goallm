"""
Images embedded as base64 data URIs – anywhere in a body: HTML attributes, inline <script>/<style>,
JSON API responses, JavaScript files, WebSocket messages.

Search-result thumbnails and many single-page apps ship pictures this way; they never cause a separate image
request, so the normal image filter never saw them. The previous HTML-only filter (BeautifulSoup over
<img src/srcset>) missed scripts, styles and JSON entirely.

Works on raw bytes with a bytes regex: no decoding, so the page's charset (UTF-8, windows-1255…) is never touched.
Handles the escaped forms used inside JSON / JS strings: "\\/" for "/", and "\\x3d" / "\\u003d" / "%3D" for "=".
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import logging
import re
from typing import Optional, Tuple

from data.constants import MAX_EMBEDDED_IMAGES_PER_PAGE

logger = logging.getLogger(__name__)

_DATA_URI_RE = re.compile(
    rb"data:image/(png|jpe?g|gif|webp|avif|bmp|x-icon|svg\+xml);base64,"
    rb"((?:[A-Za-z0-9+/=]|\\/|\\x3[dD]|\\u003[dD]|%3[dD]){16,})"
)
_UNESCAPES = ((rb"\/", b"/"), (rb"\x3d", b"="), (rb"\x3D", b"="), (rb"=", b"="), (rb"=", b"="), (b"%3d", b"="), (b"%3D", b"="))

# Smaller than this cannot show a person (spacers, 1×1 trackers, tiny icons): not worth a model call.
_MIN_IMAGE_BYTES = 200

# Served when the per-body cap is exceeded: a 1×1 grey GIF (fail-closed – never the unchecked original).
_CAP_PLACEHOLDER = b"R0lGODlhAQABAIAAAMzMzAAAACH5BAAAAAAALAAAAAABAAEAAAICRAEAOw=="


def _decode(b64: bytes) -> Optional[bytes]:
    for esc, plain in _UNESCAPES:
        b64 = b64.replace(esc, plain)
    try:
        return base64.b64decode(b64 + b"=" * (-len(b64) % 4), validate=True)
    except (binascii.Error, ValueError):
        return None


def filter_data_uri_images(
    body: bytes,
    page_url: str,
    referer_url: Optional[str] = None,
    max_images: int = MAX_EMBEDDED_IMAGES_PER_PAGE,
) -> Tuple[bytes, int]:
    """Return (new_body, number_of_images_replaced). Allowed images are left byte-for-byte as they were."""
    if b"data:image/" not in body:
        return body, 0
    from core.filters.image.image_extraction import detect_image_mime
    from core.filters.image.image_status_manager import get_image_with_status

    seen = 0
    replaced = 0

    def _sub(m: re.Match) -> bytes:
        nonlocal seen, replaced
        declared = "image/" + m.group(1).decode("ascii").replace("jpg", "jpeg")
        data = _decode(m.group(2))
        if data is None or len(data) < _MIN_IMAGE_BYTES:
            return m.group(0)
        mime = detect_image_mime(data, declared) or (declared if declared == "image/svg+xml" else None)
        if mime is None:
            return m.group(0)
        seen += 1
        if seen > max_images:
            replaced += 1
            return b"data:image/gif;base64," + _CAP_PLACEHOLDER
        digest = hashlib.sha256(data).hexdigest()[:16]
        try:
            result, ct_override, status = get_image_with_status(
                image_data=data,
                image_url=f"data-uri:{digest}@{page_url[:200]}",
                referer_url=referer_url,
                image_mime_type=mime,
            )
        except Exception as e:
            logger.warning("data-uri image check failed on %s: %s", page_url[:80], e)
            replaced += 1
            return b"data:image/gif;base64," + _CAP_PLACEHOLDER
        if status == "allowed":
            return m.group(0)
        replaced += 1
        out_mime = (ct_override or mime).encode("ascii")
        return b"data:" + out_mime + b";base64," + base64.b64encode(result)

    new_body = _DATA_URI_RE.sub(_sub, body)
    if replaced:
        logger.info("data-uri filter: %s image(s) replaced on %s", replaced, page_url[:80])
    return new_body, replaced
