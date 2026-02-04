"""
Process HTTP flows: site-level policy (HTML), then image filtering.
- HTML/document: policy_url → blocked page / send-for-review page / pass through; then text filter if allowed.
- Images: policy + image status → placeholder or real image.
"""
import json
import logging
from typing import Tuple, Optional, Any

from mitmproxy import http

from core.http_processor.image_extraction import extract_image_content
from core.http_processor.site_policy_pages import (
    get_blocked_page_bytes,
    get_send_for_review_page_bytes,
)
from core.http_processor.embedded_image_filter import filter_embedded_images_in_html
from core.http_processor.text_filter import filter_text_content, _encode_debug_b64
from core.image_processing.image_status_manager import get_image_with_status
from core.policy_processor.policy_loader import get_policy_resolver
from core.policy_processor.policy_database import get_profile_mode, get_filter_switches

logger = logging.getLogger(__name__)


def _is_html_response(flow: http.HTTPFlow) -> bool:
    ct = (flow.response.headers.get("content-type") or "").lower()
    return "text/html" in ct or (flow.response.raw_content and ct.startswith("text/") and "html" in ct)


def _is_text_or_json_response(flow: http.HTTPFlow) -> bool:
    """True for text/plain or application/json (and variants)."""
    ct = (flow.response.headers.get("content-type") or "").lower()
    return "text/plain" in ct or "application/json" in ct or ct.strip().startswith("application/json")


def _apply_site_policy_for_html(flow: http.HTTPFlow, user_id: Optional[int] = None) -> Tuple[bool, Optional[dict]]:
    """Apply site policy for HTML responses. Returns (replaced, rule). If allow: (False, rule); else (True, None)."""
    url = flow.request.url
    try:
        resolver = get_policy_resolver(user_id)
        rule = resolver.resolve(url, "html")
        if rule is not None:
            state = rule.get("state", "block")
            if state == "block":
                body = get_blocked_page_bytes(
                    request_url=url,
                    rule=rule,
                    tags=rule.get("tags") or [],
                    block_reason=rule.get("block_reason") or "",
                )
                flow.response = http.Response.make(
                    200,
                    body,
                    {"Content-Type": "text/html; charset=utf-8", "Content-Length": str(len(body))},
                )
                logger.info(
                    "Site blocked by policy - URL: %s - rule: %s - reason: %s",
                    url,
                    rule.get("domain") or rule.get("path") or "—",
                    rule.get("block_reason") or "policy",
                )
                return (True, None)
            if state == "review":
                body = get_send_for_review_page_bytes(request_url=url)
                flow.response = http.Response.make(
                    200,
                    body,
                    {
                        "Content-Type": "text/html; charset=utf-8",
                        "Content-Length": str(len(body)),
                        "Cache-Control": "no-store, no-cache, must-revalidate",
                        "Pragma": "no-cache",
                        "Expires": "0",
                    },
                )
                current_mode = get_profile_mode(user_id)
                logger.info(
                    "Site not in list, showing send-for-review - URL: %s (profile_mode in core: %s)",
                    url,
                    current_mode,
                )
                return (True, None)
            if state == "allow":
                if "domain" not in rule:
                    logger.info("Site open (blacklist mode, not in list) - URL: %s", url)
                else:
                    logger.debug("Site allowed by policy - URL: %s", url)
                return (False, rule)
        body = get_send_for_review_page_bytes(request_url=url)
        flow.response = http.Response.make(
            200,
            body,
            {
                "Content-Type": "text/html; charset=utf-8",
                "Content-Length": str(len(body)),
                "Cache-Control": "no-store, no-cache, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
        logger.info("No policy for site (treat as review), showing send-for-review - URL: %s", url)
        return (True, None)
    except Exception as e:
        logger.warning("Policy resolution failed for HTML %s: %s; showing send-for-review", url, e)
        body = get_send_for_review_page_bytes(request_url=url)
        flow.response = http.Response.make(
            200,
            body,
            {
                "Content-Type": "text/html; charset=utf-8",
                "Content-Length": str(len(body)),
                "Cache-Control": "no-store, no-cache, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
        return (True, None)


def process_http_response(flow: http.HTTPFlow) -> None:
    """Process HTTP response. Each filter (URL policy, text, image, embedded image) works independently per global switches.
    When flow.metadata has user_id (from IP binding), that user's profile and rules are used."""
    url = flow.request.url
    referer_url = flow.request.headers.get("Referer")
    method = flow.request.method
    switches = get_filter_switches()
    user_id: Optional[int] = None
    if getattr(flow, "metadata", None) is not None:
        user_id = flow.metadata.get("user_id")

    logger.info("Processing HTTP response - Method: %s, URL: %s (user_id=%s)", method, url, user_id)
    logger.debug(
        "Response status: %s, Content-Type: %s, Content-Length: %s bytes",
        flow.response.status_code,
        flow.response.headers.get("content-type"),
        len(flow.response.raw_content) if flow.response.raw_content else 0,
    )

    # HTML/document requests
    if _is_html_response(flow):
        rule = None
        if switches.get("url_policy", True):
            replaced, rule = _apply_site_policy_for_html(flow, user_id)
            logger.debug("HTML response: replaced=%s rule=%s", replaced, (rule.get("domain") if rule else None))
            if replaced:
                return
        else:
            logger.debug("URL policy filter disabled - passing HTML through policy check")
        # Text filter (independent: run when switch on; if we have a rule also respect rule's text_filter_enabled)
        body_to_send = None
        text_switch_on = switches.get("text_filter", True)
        rule_text_ok = (rule is None) or rule.get("text_filter_enabled", True)
        text_filter_on = text_switch_on and rule_text_ok
        has_content = bool(flow.response.raw_content)
        logger.debug("text_filter check: switch=%s rule_ok=%s has_content=%s content_len=%s", text_switch_on, rule_text_ok, has_content, len(flow.response.raw_content) if flow.response.raw_content else 0)
        if text_filter_on and has_content:
            try:
                try:
                    body_bytes = flow.response.content
                except ValueError:
                    body_bytes = flow.response.raw_content
                if body_bytes:
                    content_type = (flow.response.headers.get("content-type") or "").strip()
                    logger.info("text_filter: applying to URL: %s (content_len=%s)", url, len(body_bytes))
                    filtered, block_page, block_reason, debug_info = filter_text_content(
                        body_bytes,
                        url=url,
                        content_type=content_type,
                        text_filter_enabled=True,
                        rule_context=rule,
                    )
                    logger.debug("text_filter: result block_page=%s filtered_len=%s reason=%s", block_page, len(filtered), block_reason)
                    if block_page:
                        block_debug_b64 = _encode_debug_b64(debug_info) if debug_info else ""
                        body = get_blocked_page_bytes(
                            request_url=url,
                            rule=rule,
                            tags=(rule.get("tags") or []) if rule else [],
                            block_reason="text_filter",
                            block_reason_detail=block_reason,
                            block_debug_b64=block_debug_b64,
                        )
                        flow.response = http.Response.make(
                            200,
                            body,
                            {"Content-Type": "text/html; charset=utf-8", "Content-Length": str(len(body))},
                        )
                        logger.info(
                            "Page blocked by text filter - URL: %s - cause: %s",
                            url,
                            block_reason or "(no reason)",
                        )
                        if debug_info:
                            logger.debug("Text filter block debug_info: %s", json.dumps(debug_info, ensure_ascii=False))
                        return
                    body_to_send = filtered
            except Exception as e:
                logger.warning("Text filter failed for %s: %s", url, e, exc_info=True)
        if body_to_send is None and has_content:
            try:
                body_to_send = flow.response.content
            except ValueError:
                body_to_send = flow.response.raw_content
        embedded_switch = switches.get("embedded_image_filter", True)
        rule_image_ok = (rule is None) or rule.get("image_filter_enabled", True)
        if body_to_send and embedded_switch and rule_image_ok:
            # Embedded image filter (independent): data:image URLs in HTML
            try:
                content_type = (flow.response.headers.get("content-type") or "").strip()
                enc = "utf-8"
                if "charset=" in content_type:
                    for part in content_type.split(";"):
                        part = part.strip().lower()
                        if part.startswith("charset="):
                            enc = part.split("=", 1)[1].strip().strip('"')
                            break
                body_to_send = filter_embedded_images_in_html(
                    body_to_send,
                    page_url=url,
                    referer_url=referer_url,
                    encoding=enc,
                )
            except Exception as e:
                logger.warning("Embedded image filter failed for %s: %s", url, e)
        if body_to_send:
            flow.response.headers.pop("transfer-encoding", None)
            flow.response.headers.pop("content-encoding", None)
            flow.response.raw_content = body_to_send
            flow.response.headers["Content-Length"] = str(len(body_to_send))
            logger.debug("HTML response sent - URL: %s", url)
        return

    # Text/plain or application/json: text filter independent of url_policy switch
    if _is_text_or_json_response(flow):
        rule = None
        url_policy_on = switches.get("url_policy", True)
        if url_policy_on:
            try:
                resolver = get_policy_resolver(user_id)
                rule = resolver.resolve(url, "html")
                if rule is not None and rule.get("state") in ("block", "review"):
                    logger.debug("Text/JSON response: policy block/review - URL: %s (pass through)", url)
                    rule = None
                    # Don't replace with blocked page (would break API clients); pass through
            except Exception as e:
                logger.warning("Policy resolution failed for text/json %s: %s", url, e)
        # Text filter independent: when url_policy OFF run on all; when ON run only when site allowed
        text_switch_on = switches.get("text_filter", True)
        if not url_policy_on:
            text_filter_on = text_switch_on  # Independent: filter all when switch on
        else:
            text_filter_on = (
                text_switch_on
                and rule is not None
                and rule.get("state") == "allow"
                and rule.get("text_filter_enabled", True)
            )
        has_content = bool(flow.response.raw_content)
        if text_filter_on and has_content:
            try:
                try:
                    body_bytes = flow.response.content
                except ValueError:
                    body_bytes = flow.response.raw_content
                if body_bytes:
                    content_type = (flow.response.headers.get("content-type") or "").strip()
                    logger.info("text_filter (text/json): applying to URL: %s (content_len=%s)", url, len(body_bytes))
                    filtered, block_page, block_reason, debug_info = filter_text_content(
                        body_bytes,
                        url=url,
                        content_type=content_type,
                        text_filter_enabled=True,
                        rule_context=rule,
                    )
                    logger.debug("text_filter text/json: block_page=%s filtered_len=%s", block_page, len(filtered))
                    # For text/json we don't replace with blocked HTML page (preserve type)
                    flow.response.headers.pop("transfer-encoding", None)
                    flow.response.headers.pop("content-encoding", None)
                    flow.response.raw_content = filtered
                    flow.response.headers["Content-Length"] = str(len(filtered))
                    logger.debug("Text/JSON filter applied - URL: %s", url)
            except Exception as e:
                logger.warning("Text filter failed for text/json %s: %s", url, e, exc_info=True)
        return

    # Direct image responses
    extracted = extract_image_content(flow)
    if extracted is None:
        logger.debug("Response is not an image, skipping processing for URL: %s", url)
        return

    rule = None
    # URL policy for images (independent): if on and rule allows, pass through
    if switches.get("url_policy", True):
        try:
            resolver = get_policy_resolver(user_id)
            rule = resolver.resolve(url, "image")
            if rule is not None and rule.get("state") == "allow":
                if "domain" not in rule:
                    logger.info("Image open (blacklist mode, not in list) - URL: %s", url)
                else:
                    logger.info("URL allowed by policy, passing through - URL: %s", url)
                return
        except Exception as e:
            logger.warning("Policy resolution failed for %s: %s; applying filter", url, e)
    else:
        logger.debug("URL policy filter disabled - continuing to image filter check")

    # Image filter (independent): analyze and replace with placeholder when on; respect rule's image_filter_enabled
    if not switches.get("image_filter", True):
        logger.debug("Image filter disabled - passing image through - URL: %s", url)
        return
    if rule is None:
        try:
            resolver = get_policy_resolver(user_id)
            rule = resolver.resolve(url, "image")
        except Exception:
            pass
    if rule is not None and not rule.get("image_filter_enabled", True):
        logger.debug("Image filter disabled for this rule - URL: %s", url)
        return

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
