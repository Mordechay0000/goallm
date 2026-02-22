"""
Process HTTP flows: site-level policy (HTML), then image filtering.
- HTML/document: policy_url → blocked page / send-for-review page / pass through; then text filter if allowed.
- Images: policy + image status → placeholder or real image.
"""
import json
import logging
from typing import Tuple, Optional, Any
from urllib.parse import urlparse

from mitmproxy import http

from core.filters.image.image_extraction import extract_image_content
from core.flow.site_policy_pages import (
    get_blocked_page_bytes,
    get_send_for_review_page_bytes,
    get_send_for_review_file_page_bytes,
)
from core.filters.image.embedded_image_filter import filter_embedded_images_in_html
from core.filters.text.text_filter import filter_text_content, _encode_debug_b64
from core.filters.image.image_status_manager import get_image_with_status
from core.policy.policy_loader import get_policy_resolver
from core.policy.policy_database import get_profile_mode, get_filter_switches
from data.constants import CRM_FRONTEND_URL

logger = logging.getLogger(__name__)

_CRM_FRONTEND_HOST = ""
try:
    _parsed_crm = urlparse(
        CRM_FRONTEND_URL
        if "://" in (CRM_FRONTEND_URL or "")
        else f"https://{CRM_FRONTEND_URL}"
    )
    _CRM_FRONTEND_HOST = (_parsed_crm.hostname or "").lower().rstrip(".")
except Exception:
    _CRM_FRONTEND_HOST = ""


def _is_crm_frontend_request(url: str) -> bool:
    """Return True אם הבקשה שייכת לדומיין של ממשק ה-CRM עצמו.

    על בקשות אלה לא מפעילים שום סינון (מדיניות, טקסט, תמונות, קבצים),
    כדי שממשק הניהול של הסינון לא ייפגע מהסינון.
    """
    if not _CRM_FRONTEND_HOST or not url:
        return False
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        host = (parsed.hostname or "").lower().rstrip(".")
        return host == _CRM_FRONTEND_HOST
    except Exception:
        return False


def _is_html_response(flow: http.HTTPFlow) -> bool:
    ct = (flow.response.headers.get("content-type") or "").lower()
    return "text/html" in ct or (flow.response.raw_content and ct.startswith("text/") and "html" in ct)


def _is_text_or_json_response(flow: http.HTTPFlow) -> bool:
    """True for text/plain or application/json (and variants)."""
    ct = (flow.response.headers.get("content-type") or "").lower()
    return "text/plain" in ct or "application/json" in ct or ct.strip().startswith("application/json")


def _is_file_download_response(flow: http.HTTPFlow) -> bool:
    """True when response is meant to be saved as a file (Content-Disposition: attachment).

    We only treat 'attachment' as file download so that site assets are not blocked:
    - Many sites send Content-Disposition: inline; filename=... for HTML/JS/CSS – those must pass.
    - Only 'attachment' means the server intends the user to download/save the file.
    """
    cd = (flow.response.headers.get("content-disposition") or "").strip()
    if not cd:
        return False
    cd_lower = cd.lower()
    # Only attachment = real file download. "inline" or "inline; filename=..." = display in browser.
    if "attachment" not in cd_lower:
        return False
    # Do not treat page assets as file download even if server wrongly sends attachment
    ct = (flow.response.headers.get("content-type") or "").lower().split(";")[0].strip()
    if ct in (
        "text/html",
        "text/css",
        "application/javascript",
        "application/x-javascript",
        "text/javascript",
        "application/json",
    ) or ct.startswith("text/plain"):
        return False
    return True


def _get_filename_from_response(flow: http.HTTPFlow) -> str:
    """Extract filename from Content-Disposition or from URL path. Returns empty string if none."""
    cd = (flow.response.headers.get("content-disposition") or "").strip()
    if cd:
        for part in cd.split(";"):
            part = part.strip()
            if part.lower().startswith("filename="):
                val = part.split("=", 1)[1].strip().strip('"\'')
                if val:
                    return val
    from urllib.parse import unquote
    path = (flow.request.path or "").split("?")[0]
    if path and "/" in path:
        name = path.rsplit("/", 1)[-1]
        if name:
            return unquote(name)
    return ""


def _is_content_type_already_filtered(flow: http.HTTPFlow) -> bool:
    """True when response type is already handled by another filter (e.g. images)."""
    ct = (flow.response.headers.get("content-type") or "").lower().split(";")[0].strip()
    if not ct:
        return False
    if ct.startswith("image/"):
        return True
    return False


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
                if getattr(flow, "metadata", None) is not None:
                    flow.metadata["traffic_status"] = "blocked"
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
                if getattr(flow, "metadata", None) is not None:
                    flow.metadata["traffic_status"] = "review"
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
        if getattr(flow, "metadata", None) is not None:
            flow.metadata["traffic_status"] = "review"
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
    When flow.metadata has user_id (from IP binding), that user's profile and rules are used.
    Sets flow.metadata['traffic_status'] for traffic recording: open, blocked, review, cert_missing."""
    url = flow.request.url
    referer_url = flow.request.headers.get("Referer")
    method = flow.request.method
    switches = get_filter_switches()
    user_id: Optional[int] = None
    if getattr(flow, "metadata", None) is not None:
        user_id = flow.metadata.get("user_id")
    if not hasattr(flow, "metadata") or flow.metadata is None:
        flow.metadata = {}
    flow.metadata["traffic_status"] = "open"

    # CRM frontend (UI) traffic should לעולם לא לעבור סינון,
    # כדי שממשק ניהול הסינון עצמו לא ייחסם או ישתבש.
    if _is_crm_frontend_request(url):
        logger.debug(
            "Skipping all filtering for CRM frontend request - URL: %s (user_id=%s)",
            url,
            user_id,
        )
        return

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
        replaced = False
        if flow.metadata.get("policy_handled_in_request"):
            # Policy already applied at request time (e.g. document navigation block for SPA).
            replaced = True
            logger.debug("HTML response: policy already applied in request, skipped")
        elif switches.get("url_policy", True):
            replaced, rule = _apply_site_policy_for_html(flow, user_id)
            logger.debug("HTML response: replaced=%s rule=%s", replaced, (rule.get("domain") if rule else None))
            # When replaced (block/send-for-review), do not return: continue so we inject surf widget into the replacement page.
        else:
            logger.debug("URL policy filter disabled - passing HTML through policy check")
        # Text filter (independent: run when switch on; if we have a rule also respect rule's text_filter_enabled)
        body_to_send = None
        if replaced:
            # Replaced page (block/send-for-review): use it as body so we inject surf widget below; skip text filter for our own pages.
            try:
                body_to_send = flow.response.content
            except ValueError:
                body_to_send = flow.response.raw_content
        text_switch_on = switches.get("text_filter", True)
        rule_text_ok = (rule is None) or rule.get("text_filter_enabled", True)
        text_filter_on = text_switch_on and rule_text_ok and not replaced
        has_content = bool(flow.response.raw_content)
        logger.debug("text_filter check: switch=%s rule_ok=%s replaced=%s has_content=%s content_len=%s", text_switch_on, rule_text_ok, replaced, has_content, len(flow.response.raw_content) if flow.response.raw_content else 0)
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
                        if getattr(flow, "metadata", None) is not None:
                            flow.metadata["traffic_status"] = "blocked"
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
            content_type_h = (flow.response.headers.get("content-type") or "").strip()
            enc = "utf-8"
            if "charset=" in content_type_h:
                for part in content_type_h.split(";"):
                    part = part.strip().lower()
                    if part.startswith("charset="):
                        enc = part.split("=", 1)[1].strip().strip('"')
                        break
            if switches.get("surf_widget", True):
                from core.proxy.surf_widget import inject_surf_widget, get_surf_user_is_admin
                is_admin = get_surf_user_is_admin(user_id)
                body_before_len = len(body_to_send)
                body_to_send = inject_surf_widget(
                    body_to_send, url, user_id, rule, encoding=enc, is_admin=is_admin
                )
                logger.info(
                    "surf_widget: injected url=%s user_id=%s is_admin=%s body_before=%s body_after=%s",
                    url[:80] if url else "",
                    user_id,
                    is_admin,
                    body_before_len,
                    len(body_to_send),
                )
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
            except Exception as e:
                logger.warning("Policy resolution failed for text/json %s: %s", url, e)
        text_switch_on = switches.get("text_filter", True)
        if not url_policy_on:
            text_filter_on = text_switch_on
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
                    flow.response.headers.pop("transfer-encoding", None)
                    flow.response.headers.pop("content-encoding", None)
                    flow.response.raw_content = filtered
                    flow.response.headers["Content-Length"] = str(len(filtered))
                    logger.debug("Text/JSON filter applied - URL: %s", url)
            except Exception as e:
                logger.warning("Text filter failed for text/json %s: %s", url, e, exc_info=True)
        return

    # File download (non-image): always return send-for-review page instead of the file
    if _is_file_download_response(flow) and not _is_content_type_already_filtered(flow):
        if get_filter_switches().get("file_download_filter", True):
            file_url = url
            filename = _get_filename_from_response(flow) or "קובץ"
            body = get_send_for_review_file_page_bytes(file_url=file_url, filename=filename)
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
            if getattr(flow, "metadata", None) is not None:
                flow.metadata["traffic_status"] = "review"
            logger.info(
                "File download intercepted, showing send-for-review - URL: %s, filename: %s",
                url,
                filename,
            )
            return

    # Direct image responses
    extracted = extract_image_content(flow)
    if extracted is None:
        logger.debug("Response is not an image, skipping processing for URL: %s", url)
        return

    rule = None
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
    if image_status in ("checking", "pending", "error"):
        flow.response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        flow.response.headers["Pragma"] = "no-cache"
        flow.response.headers["Expires"] = "0"
    logger.info("Image processing complete for URL: %s", url)
