"""
סינון תמונות מוטמעות ב־HTML – תמונות ב־data: URLs (inline).

מריץ את אותו סינון תמונות כמו על בקשות תמונה ישירות: get_image_with_status,
ומחליף את ה־src של כל <img src="data:image/..."> בתמונה המסוננת (או placeholder).
"""
import base64
import hashlib
import logging
import re
from typing import Tuple

logger = logging.getLogger(__name__)

# מקסימום תמונות מוטמעות לעיבוד בדף (למניעת עומס)
MAX_EMBEDDED_IMAGES_PER_PAGE = 100


def _parse_data_url(src: str) -> Tuple[bytes, str] | None:
    """Parse data: URL. Returns (raw_bytes, mime_type) or None."""
    if not src:
        return None
    src = src.strip()
    # תמיכה ב־data: גם עם רווח/שורה בהתחלה (לאחר strip)
    if not src.lower().startswith("data:image/"):
        return None
    # data:image/png;base64,XXXX or data:image/png,XXXX (rare)
    match = re.match(r"data:([^;,]+)(?:;base64)?\s*,\s*(.+)", src, re.DOTALL | re.IGNORECASE)
    if not match:
        return None
    mime = match.group(1).strip().lower()
    if not mime.startswith("image/"):
        return None
    # הסרת רווחים/שורות מתוך ה־base64 (תקן RFC מאפשר)
    payload = re.sub(r"\s+", "", match.group(2))
    try:
        raw = base64.b64decode(payload)
    except Exception as e:
        logger.debug("Failed to decode data URL base64: %s", e)
        return None
    if not raw or len(raw) < 4:
        return None
    return raw, mime


def _to_data_url(data: bytes, mime_type: str) -> str:
    """Encode bytes as data: URL."""
    b64 = base64.b64encode(data).decode("ascii")
    return "data:%s;base64,%s" % (mime_type, b64)


def _is_data_image_url(s: str) -> bool:
    """Check if string looks like a data:image/ URL (possibly with leading/trailing whitespace)."""
    return bool(s and s.strip().lower().startswith("data:image/"))


def _replace_data_url_in_attr(
    url: str,
    page_url: str,
    referer_url: str | None,
    get_image_with_status_fn,
) -> str | None:
    """If url is data:image/..., filter and return new data URL; else return None."""
    parsed = _parse_data_url(url)
    if not parsed:
        return None
    image_data, mime_type = parsed
    h = hashlib.sha256(image_data).hexdigest()
    inline_url = "inline-%s" % h[:16]
    try:
        result_bytes, _, status = get_image_with_status_fn(
            image_data=image_data,
            image_url=inline_url,
            referer_url=referer_url or page_url,
            image_mime_type=mime_type,
        )
    except Exception as e:
        logger.warning("get_image_with_status failed for embedded image %s: %s", inline_url[:20], e)
        return None
    return _to_data_url(result_bytes, mime_type)


def _process_src_or_srcset(
    elem,
    attr: str,
    page_url: str,
    referer_url: str | None,
    get_image_with_status_fn,
) -> int:
    """
    Process src or srcset attribute; replace each data:image/ URL with filtered version.
    srcset format: "url1 1x, url2 2x" or "url1 100w, url2 200w". Returns number of replacements.
    """
    val = elem.get(attr)
    if not val:
        return 0
    val = val.strip()
    if attr == "src":
        if not _is_data_image_url(val):
            return 0
        new_url = _replace_data_url_in_attr(val, page_url, referer_url, get_image_with_status_fn)
        if new_url is None:
            return 0
        elem[attr] = new_url
        return 1
    # srcset: comma-separated list of "url descriptor" or "url width"
    if attr != "srcset":
        return 0
    parts = [p.strip() for p in val.split(",") if p.strip()]
    new_parts = []
    replaced = 0
    for part in parts:
        # descriptor is optional: "url 1x" or "url 100w" or just "url"
        tok = part.split()
        url_part = tok[0] if tok else part
        descriptor = " " + " ".join(tok[1:]) if len(tok) > 1 else ""
        if not _is_data_image_url(url_part):
            new_parts.append(part)
            continue
        new_url = _replace_data_url_in_attr(url_part, page_url, referer_url, get_image_with_status_fn)
        if new_url is not None:
            new_parts.append(new_url + descriptor)
            replaced += 1
        else:
            new_parts.append(part)
    if replaced:
        elem[attr] = ",".join(new_parts)
    return replaced


def filter_embedded_images_in_html(
    html_bytes: bytes,
    page_url: str = "",
    referer_url: str | None = None,
    encoding: str = "utf-8",
) -> bytes:
    """
    מצא כל <img src="data:image/..."> (וגם srcset, ו־<source>) ב־HTML,
    הרץ על כל תמונה את get_image_with_status (בדיוק כמו על בקשות תמונה),
    והחלף בתמונה המסוננת (או placeholder).

    Returns:
        HTML bytes עם תמונות מוטמעות מסוננות.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.warning("BeautifulSoup4 not available; skipping embedded image filter")
        return html_bytes

    try:
        from core.image_processing.image_status_manager import get_image_with_status
    except Exception as e:
        logger.warning("Could not import get_image_with_status: %s", e)
        return html_bytes

    try:
        text = html_bytes.decode(encoding, errors="replace")
    except Exception as e:
        logger.warning("Failed to decode HTML for embedded image filter: %s", e)
        return html_bytes

    soup = BeautifulSoup(text, "html.parser")
    count = 0

    # img: src ו־srcset
    for img in soup.find_all("img"):
        if count >= MAX_EMBEDDED_IMAGES_PER_PAGE:
            break
        for attr in ("src", "srcset"):
            if img.get(attr) and _is_data_image_url(img.get(attr) or ""):
                n = _process_src_or_srcset(img, attr, page_url, referer_url, get_image_with_status)
                count += n
                if count >= MAX_EMBEDDED_IMAGES_PER_PAGE:
                    break

    # picture/source: src ו־srcset
    for source in soup.find_all("source", src=True):
        if count >= MAX_EMBEDDED_IMAGES_PER_PAGE:
            break
        n = _process_src_or_srcset(source, "src", page_url, referer_url, get_image_with_status)
        count += n
    for source in soup.find_all("source", srcset=True):
        if count >= MAX_EMBEDDED_IMAGES_PER_PAGE:
            break
        n = _process_src_or_srcset(source, "srcset", page_url, referer_url, get_image_with_status)
        count += n

    if count:
        logger.info("Filtered %d embedded image(s) in HTML", count)
    else:
        logger.debug("No embedded data:image/ URLs found in HTML (or limit reached)")

    out = str(soup)
    if soup.original_encoding:
        return out.encode(soup.original_encoding)
    return out.encode(encoding)
