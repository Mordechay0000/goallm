"""
Process HTTP flows: site-level policy (HTML), then image filtering.
- HTML/document: policy_url → blocked page / send-for-review page / pass through.
- Images: policy + image status → placeholder or real image.
"""
import logging

from mitmproxy import http

from core.http_processor.image_extraction import extract_image_content
from core.http_processor.site_policy_pages import (
    get_blocked_page_bytes,
    get_send_for_review_page_bytes,
)
from core.image_processing.image_status_manager import get_image_with_status
from core.policy_processor.policy_loader import get_policy_resolver
from core.policy_processor.policy_database import get_profile_mode

logger = logging.getLogger(__name__)


def _is_html_response(flow: http.HTTPFlow) -> bool:
    ct = (flow.response.headers.get("content-type") or "").lower()
    return "text/html" in ct or (flow.response.raw_content and ct.startswith("text/") and "html" in ct)


def _apply_site_policy_for_html(flow: http.HTTPFlow) -> bool:
    """Apply site policy for HTML responses. Returns True if response was replaced (caller should return)."""
    url = flow.request.url
    try:
        resolver = get_policy_resolver()
        rule = resolver.resolve(url, "html")
        if rule is not None:
            state = rule.get("state", "block")
            if state == "block":
                body = get_blocked_page_bytes(
                    request_url=url,
                    rule=rule,
                    tags=rule.get("tags") or [],
                )
                flow.response = http.Response.make(
                    200,
                    body,
                    {"Content-Type": "text/html; charset=utf-8", "Content-Length": str(len(body))},
                )
                logger.info("Site blocked by policy - URL: %s", url)
                return True
            if state == "review":
                body = get_send_for_review_page_bytes(request_url=url)
                flow.response = http.Response.make(
                    200,
                    body,
                    {"Content-Type": "text/html; charset=utf-8", "Content-Length": str(len(body))},
                )
                current_mode = get_profile_mode()
                logger.info(
                    "Site not in list, showing send-for-review - URL: %s (profile_mode in core: %s)",
                    url,
                    current_mode,
                )
                return True
            if state == "allow":
                if "domain" not in rule:
                    logger.info("Site open (blacklist mode, not in list) - URL: %s", url)
                else:
                    logger.debug("Site allowed by policy - URL: %s", url)
                return False
        body = get_send_for_review_page_bytes(request_url=url)
        flow.response = http.Response.make(
            200,
            body,
            {"Content-Type": "text/html; charset=utf-8", "Content-Length": str(len(body))},
        )
        logger.info("No policy for site (treat as review), showing send-for-review - URL: %s", url)
        return True
    except Exception as e:
        logger.warning("Policy resolution failed for HTML %s: %s; showing send-for-review", url, e)
        body = get_send_for_review_page_bytes(request_url=url)
        flow.response = http.Response.make(
            200,
            body,
            {"Content-Type": "text/html; charset=utf-8", "Content-Length": str(len(body))},
        )
        return True


def process_http_response(flow: http.HTTPFlow) -> None:
    """Process HTTP response: site policy for HTML, then image filtering."""
    url = flow.request.url
    referer_url = flow.request.headers.get("Referer")
    method = flow.request.method

    logger.info("Processing HTTP response - Method: %s, URL: %s", method, url)
    logger.debug(
        "Response status: %s, Content-Type: %s, Content-Length: %s bytes",
        flow.response.status_code,
        flow.response.headers.get("content-type"),
        len(flow.response.raw_content) if flow.response.raw_content else 0,
    )

    # Site-level policy for HTML/document requests
    if _is_html_response(flow):
        if _apply_site_policy_for_html(flow):
            return
        return  # Allowed: pass through, leave response unchanged

    extracted = extract_image_content(flow)
    if extracted is None:
        logger.debug("Response is not an image, skipping processing for URL: %s", url)
        return

    # Policy routing: if URL matches an "allow" rule for type image, pass through
    try:
        resolver = get_policy_resolver()
        rule = resolver.resolve(url, "image")
        if rule is not None and rule.get("state") == "allow":
            if "domain" not in rule:
                logger.info("Image open (blacklist mode, not in list) - URL: %s", url)
            else:
                logger.info("URL allowed by policy, passing through - URL: %s", url)
            return
    except Exception as e:
        logger.warning("Policy resolution failed for %s: %s; applying filter", url, e)

    image_content, mime_type = extracted
    logger.info(
        "Image detected in response - MIME: %s, Size: %s bytes",
        mime_type,
        len(image_content),
    )
    logger.debug(
        "Processing image with status check - URL: %s, Referer: %s",
        url,
        referer_url,
    )

    image_result, _, image_status = get_image_with_status(
        image_data=image_content,
        image_url=url,
        referer_url=referer_url,
        image_mime_type=mime_type,
    )
    logger.debug("Got image result, size: %s bytes, status: %s", len(image_result), image_status)

    flow.response.raw_content = image_result
    flow.response.headers["Content-Length"] = str(len(image_result))
    # Only disable cache for "checking" placeholders so refresh re-requests and shows final image
    if image_status in ("checking", "pending", "error"):
        flow.response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        flow.response.headers["Pragma"] = "no-cache"
        flow.response.headers["Expires"] = "0"
    logger.info("Image processing complete for URL: %s", url)
