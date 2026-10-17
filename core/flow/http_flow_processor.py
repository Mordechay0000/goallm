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
from core.flow.traffic_utils import blocked_traffic_status
from core.proxy.csp import add_nonce, prepare_csp_nonce
from core.proxy.image_refresh import REFRESH_SCRIPT
from core.filters.image.data_uri_filter import filter_data_uri_images
from core.filters.text.text_filter import filter_text_content, _encode_debug_b64, format_text_filter_debug_readable
from core.filters.image.image_status_manager import get_image_with_status
from core.filters.pdf.pdf_filter import filter_pdf_response
from core.filters.search.google_search_filter import filter_google_search_html, is_google_search_page
from core.policy.policy_cache import (
    get_filter_switches,
    get_policy_resolver,
    get_profile_mode,
    get_site_injection_for_url,
)
from data.constants import CRM_FRONTEND_URL, PUBLIC_FILE_SHARE_DOMAINS, FILTER_BLOCKED_OR_REVIEW_HTTP_STATUS

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


_UNANALYZABLE_ACCEPT_TYPES = ("image/avif", "image/jxl", "image/heic", "image/heif")


def rewrite_request_accept_header(flow: http.HTTPFlow) -> None:
    """Ask servers for JPEG/PNG/WebP instead of AVIF/JPEG-XL/HEIC (content negotiation).
    Those formats are still detected and filtered if a server sends them anyway, but the common formats
    are cheaper to decode and every VLM server accepts them."""
    accept = flow.request.headers.get("accept")
    if not accept or "image/" not in accept:
        return
    parts = [p for p in accept.split(",") if p.strip().split(";")[0].strip().lower() not in _UNANALYZABLE_ACCEPT_TYPES]
    if len(parts) != len(accept.split(",")):
        flow.request.headers["accept"] = ",".join(p.strip() for p in parts) or "*/*"


def _is_html_response(flow: http.HTTPFlow) -> bool:
    ct = (flow.response.headers.get("content-type") or "").lower()
    return "text/html" in ct or (flow.response.raw_content and ct.startswith("text/") and "html" in ct)


def _is_text_or_json_response(flow: http.HTTPFlow) -> bool:
    """True for text/plain or application/json (and variants)."""
    ct = (flow.response.headers.get("content-type") or "").lower()
    return "text/plain" in ct or "application/json" in ct or ct.strip().startswith("application/json")


def _is_javascript_response(flow: http.HTTPFlow) -> bool:
    ct = (flow.response.headers.get("content-type") or "").lower().split(";")[0].strip()
    return ct in ("application/javascript", "text/javascript", "application/x-javascript", "application/ecmascript")


def _filter_embedded_data_uris(flow: http.HTTPFlow, url: str, referer_url, switches: dict, rule) -> None:
    """Replace base64 data-URI images in a non-HTML body (JSON / text / JavaScript) in place."""
    if not (switches.get("image_filter", True) and switches.get("embedded_image_filter", True)):
        return
    if rule is not None and not rule.get("image_filter_enabled", True):
        return
    try:
        body = flow.response.content
    except ValueError:
        return
    if not body or b"data:image/" not in body:
        return
    try:
        new_body, n = filter_data_uri_images(body, page_url=url, referer_url=referer_url)
    except Exception as e:
        logger.warning("data-uri filter failed for %s: %s", url, e)
        return
    if n:
        flow.response.headers.pop("transfer-encoding", None)
        flow.response.headers.pop("content-encoding", None)
        flow.response.raw_content = new_body
        flow.response.headers["Content-Length"] = str(len(new_body))


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


def _is_pdf_response(flow: http.HTTPFlow) -> bool:
    """True when response is application/pdf."""
    ct = (flow.response.headers.get("content-type") or "").lower().split(";")[0].strip()
    return ct == "application/pdf"


def _is_public_file_share_request(url: str) -> bool:
    """True when request URL is a public file-share link (domain in list and path/query indicates file)."""
    if not url or not PUBLIC_FILE_SHARE_DOMAINS:
        return False
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        host = (parsed.hostname or "").lower().rstrip(".")
        if host.startswith("www."):
            host = host[4:]
        if host not in PUBLIC_FILE_SHARE_DOMAINS:
            return False
        path = (parsed.path or "").lower()
        query = (parsed.query or "").lower()
        # Paths that indicate file/view: drive /file/d/, /open, dropbox /s/, we.tl/xxx, etc.
        if "/file/" in path or "/open" in path or "/view" in path or "/sharing/" in path:
            return True
        if path.startswith("/s/") or path.count("/") >= 2:  # dropbox.com/s/xxx, transfer.sh/xxx
            return True
        if "id=" in query or "url=" in query:  # drive open?id=, etc.
            return True
        # For domains that are purely file-sharing (we.tl, file.io, transfer.sh), any path is a file link
        if host in ("we.tl", "file.io", "transfer.sh", "tmpfiles.org", "send.any.run"):
            return len(path) > 1
        return False
    except Exception:
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
                    FILTER_BLOCKED_OR_REVIEW_HTTP_STATUS,
                    body,
                    {"Content-Type": "text/html; charset=utf-8", "Content-Length": str(len(body))},
                )
                if getattr(flow, "metadata", None) is not None:
                    flow.metadata["traffic_status"] = blocked_traffic_status(rule, is_file=False)
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
                    FILTER_BLOCKED_OR_REVIEW_HTTP_STATUS,
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
            FILTER_BLOCKED_OR_REVIEW_HTTP_STATUS,
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
        # Fail closed (this used to return None, which crashed the caller into a 500).
        logger.warning("Policy resolution failed for HTML %s: %s; showing send-for-review", url, e)
        body = get_send_for_review_page_bytes(request_url=url)
        flow.response = http.Response.make(
            FILTER_BLOCKED_OR_REVIEW_HTTP_STATUS,
            body,
            {"Content-Type": "text/html; charset=utf-8", "Content-Length": str(len(body)), "Cache-Control": "no-store"},
        )
        if getattr(flow, "metadata", None) is not None:
            flow.metadata["traffic_status"] = "error"
        return (True, None)


def _inject_before_body_end(body: bytes, encoding: str, snippet: str) -> bytes:
    try:
        text = body.decode(encoding, errors="replace")
    except LookupError:
        encoding = "utf-8"
        text = body.decode(encoding, errors="replace")
    idx = text.lower().rfind("</body")
    text = text[:idx] + snippet + text[idx:] if idx >= 0 else text + snippet
    try:
        return text.encode(encoding, errors="replace")
    except LookupError:
        return text.encode("utf-8", errors="replace")


def _strip_elements_by_selectors(html_text: str, selectors: list) -> str:
    """Remove from HTML all elements matching the given CSS selectors (server-side, before response is sent)."""
    if not selectors:
        return html_text
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.warning("BeautifulSoup4 not available; skipping server-side hide_selectors")
        return html_text
    try:
        soup = BeautifulSoup(html_text, "html.parser")
        for sel in selectors:
            sel = (sel or "").strip()
            if not sel:
                continue
            try:
                for el in soup.select(sel):
                    el.decompose()
            except Exception as e:
                logger.debug("Selector %r failed: %s", sel, e)
        return str(soup)
    except Exception as e:
        logger.warning("Server-side strip by selectors failed: %s", e)
        return html_text


def _apply_site_injections(html_body: bytes, url: str, encoding: str, injection: dict, nonce: Optional[str] = None) -> bytes:
    """Apply site injection: (1) strip hide_selectors from HTML in proxy, (2) head_code, (3) body_code, (4) hide script as fallback for dynamic content."""
    try:
        text = html_body.decode(encoding, errors="replace")
    except Exception:
        text = html_body.decode("utf-8", errors="replace")
    head_code = add_nonce((injection.get("head_code") or "").strip(), nonce)
    body_code = add_nonce((injection.get("body_code") or "").strip(), nonce)
    hide_selectors = injection.get("hide_selectors") or []
    if not head_code and not body_code and not hide_selectors:
        return html_body
    # 1) Remove matching elements from HTML in the proxy response (page already comes back without them)
    if hide_selectors:
        text = _strip_elements_by_selectors(text, hide_selectors)
    import re
    if head_code:
        # Insert before </head> (case-insensitive)
        head_close = re.compile(re.escape("</head>"), re.IGNORECASE)
        if head_close.search(text):
            text = head_close.sub(head_code + "\n</head>", text, count=1)
        else:
            # No </head>: append after <head>
            head_open = re.compile(re.escape("<head>"), re.IGNORECASE)
            if head_open.search(text):
                text = head_open.sub("<head>\n" + head_code, text, count=1)
            else:
                text = head_code + "\n" + text
    hide_script = ""
    if hide_selectors:
        # Run on DOMContentLoaded + MutationObserver so dynamically added content (SPA/NodeBB) is also hidden
        selectors_js = json.dumps(hide_selectors)
        hide_script = (
            "<script>(function(){var s=%s;function hide(){try{s.forEach(function(sel){"
            "document.querySelectorAll(sel).forEach(function(el){el.style.setProperty('display','none','important');});"
            "});}catch(e){}}"
            "function run(){hide();if(document.body){var o=new MutationObserver(hide);o.observe(document.body,{childList:true,subtree:true});}}"
            "if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',run);}else{setTimeout(run,0);}"
            "})();</script>"
        ) % selectors_js
    hide_script = add_nonce(hide_script, nonce)
    body_inject = (body_code + "\n" + hide_script) if (body_code and hide_script) else (body_code or hide_script)
    if body_inject:
        body_close = re.compile(re.escape("</body>"), re.IGNORECASE)
        if body_close.search(text):
            text = body_close.sub(body_inject + "\n</body>", text, count=1)
        else:
            text = text + "\n" + body_inject
    try:
        return text.encode(encoding, errors="replace")
    except Exception:
        return text.encode("utf-8", errors="replace")


def process_http_response(flow: http.HTTPFlow) -> None:
    """Process HTTP response. Filters are independent: each runs when its switch is on, regardless of other switches.
    When all are on, order is: (1) URL policy – block/review then no further filters; (2) text; (3) embedded images; (4) file-share; (5) PDF; (6) file download; (7) direct images.
    When flow.metadata has user_id (from IP binding), that user's profile and rules are used.
    Sets flow.metadata['traffic_status'] for traffic recording: open, blocked, review, text_filter_blocked, file_review, file_blocked, cert_missing, error."""
    url = flow.request.url
    referer_url = flow.request.headers.get("Referer")
    method = flow.request.method
    if getattr(flow.response, "stream", False):
        return  # body was streamed (allowed media) or discarded (blocked video) at headers time
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

    # Public file-share: when file_share_block is on, show "שלח לבדיקה" for any file-share URL (unless rule disables file filter for this site)
    if switches.get("file_share_block", True) and _is_public_file_share_request(url):
        file_rule = None
        if switches.get("url_policy", True):
            try:
                file_rule = get_policy_resolver(user_id).resolve(url, "html") or get_policy_resolver(user_id).resolve(url, "*")
            except Exception:
                pass
        if file_rule is None or file_rule.get("file_filter_enabled", True):
            filename = _get_filename_from_response(flow) or "קובץ"
            body = get_send_for_review_file_page_bytes(file_url=url, filename=filename)
            flow.response = http.Response.make(
                FILTER_BLOCKED_OR_REVIEW_HTTP_STATUS,
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
                flow.metadata["traffic_status"] = "file_review"
            logger.info(
                "Public file-share: showing send-for-review - URL: %s",
                url[:80] if url else "",
            )
            return
        logger.debug("Public file-share: skipped (file_filter_enabled=False for rule) - URL: %s", url[:80] if url else "")

    extracted = extract_image_content(flow)
    if extracted is not None:
        _process_image(flow, extracted, url, referer_url, switches, user_id)
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
                        block_debug_readable = format_text_filter_debug_readable(block_reason, debug_info or {}) if debug_info else ""
                        body = get_blocked_page_bytes(
                            request_url=url,
                            rule=rule,
                            tags=(rule.get("tags") or []) if rule else [],
                            block_reason="text_filter",
                            block_reason_detail=block_reason,
                            block_debug_b64=block_debug_b64,
                            block_debug_readable=block_debug_readable,
                        )
                        flow.response = http.Response.make(
                            FILTER_BLOCKED_OR_REVIEW_HTTP_STATUS,
                            body,
                            {"Content-Type": "text/html; charset=utf-8", "Content-Length": str(len(body))},
                        )
                        if getattr(flow, "metadata", None) is not None:
                            flow.metadata["traffic_status"] = "text_filter_blocked"
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
        if body_to_send and embedded_switch and rule_image_ok and not replaced:
            # base64 images anywhere in the page: <img>/srcset, inline <script> (search thumbnails), <style>.
            try:
                body_to_send, _n = filter_data_uri_images(body_to_send, page_url=url, referer_url=referer_url)
            except Exception as e:
                logger.warning("Embedded image filter failed for %s: %s", url, e)
        if body_to_send:
            # Strict CSP pages: give our injected scripts a nonce (None when no CSP or inline already allowed).
            csp_nonce = prepare_csp_nonce(flow)
            content_type_h = (flow.response.headers.get("content-type") or "").strip()
            enc = "utf-8"
            if "charset=" in content_type_h:
                for part in content_type_h.split(";"):
                    part = part.strip().lower()
                    if part.startswith("charset="):
                        enc = part.split("=", 1)[1].strip().strip('"')
                        break
            if switches.get("google_search_filter", True) and is_google_search_page(url):
                try:
                    body_to_send = filter_google_search_html(
                        body_to_send,
                        page_url=url,
                        encoding=enc,
                        user_id=user_id,
                    )
                    logger.debug("Google search filter applied - URL: %s", url[:80] if url else "")
                except Exception as e:
                    logger.warning("Google search filter failed for %s: %s", url, e)
            if switches.get("surf_widget", True) and (rule is None or rule.get("surf_widget_enabled", True)):
                from core.proxy.surf_widget import inject_surf_widget, get_surf_user_is_admin
                is_admin = get_surf_user_is_admin(user_id)
                inject_video = rule is None or rule.get("video_filter_enabled", True)
                body_before_len = len(body_to_send)
                body_to_send = inject_surf_widget(
                    body_to_send, url, user_id, rule, encoding=enc, is_admin=is_admin, inject_video=inject_video,
                    nonce=csp_nonce,
                )
                logger.info(
                    "surf_widget: injected url=%s user_id=%s is_admin=%s body_before=%s body_after=%s",
                    url[:80] if url else "",
                    user_id,
                    is_admin,
                    body_before_len,
                    len(body_to_send),
                )
            # Reload "checking" placeholders automatically once their analysis finishes.
            if (
                not replaced
                and user_id is not None
                and switches.get("image_filter", True)
                and (rule is None or rule.get("image_filter_enabled", True))
            ):
                body_to_send = _inject_before_body_end(body_to_send, enc, add_nonce(REFRESH_SCRIPT, csp_nonce))
            # Site injections (admin-defined head/body code and hide selectors per site)
            try:
                injection = get_site_injection_for_url(url)
                if injection:
                    body_to_send = _apply_site_injections(body_to_send, url, enc, injection, nonce=csp_nonce)
                    logger.debug("site_injection applied for url=%s", url[:80] if url else "")
            except Exception as e:
                logger.warning("Site injection failed for %s: %s", url[:80] if url else "", e)
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
            except Exception as e:
                logger.warning("Policy resolution failed for text/json %s: %s – blocking", url, e)
                rule = {"state": "review"}
            if rule is not None and rule.get("state") in ("block", "review"):
                # Normally stopped at request time; if not (e.g. that check failed), never pass it through.
                flow.response = http.Response.make(
                    FILTER_BLOCKED_OR_REVIEW_HTTP_STATUS, b"", {"Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store"}
                )
                flow.metadata["traffic_status"] = "blocked_global" if rule.get("state") == "block" else "review"
                logger.debug("Text/JSON response blocked by policy - URL: %s", url)
                return
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
        if has_content:
            _filter_embedded_data_uris(flow, url, referer_url, switches, rule)
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

    # PDF: apply URL policy (block/review), then extract text + images, filter text and images, optional distortion warning
    if _is_pdf_response(flow):
        has_pdf_content = bool(flow.response.raw_content)
        rule = None
        if switches.get("url_policy", True) and has_pdf_content:
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
                            FILTER_BLOCKED_OR_REVIEW_HTTP_STATUS,
                            body,
                            {"Content-Type": "text/html; charset=utf-8", "Content-Length": str(len(body))},
                        )
                        if getattr(flow, "metadata", None) is not None:
                            flow.metadata["traffic_status"] = blocked_traffic_status(rule, is_file=True)
                        logger.info("PDF blocked by policy - URL: %s", url)
                        return
                    if state == "review":
                        filename = _get_filename_from_response(flow) or "מסמך.pdf"
                        body = get_send_for_review_file_page_bytes(file_url=url, filename=filename)
                        flow.response = http.Response.make(
                            FILTER_BLOCKED_OR_REVIEW_HTTP_STATUS,
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
                            flow.metadata["traffic_status"] = "file_review"
                        logger.info("PDF send-for-review by policy - URL: %s", url)
                        return
            except Exception as e:
                logger.warning("Policy resolution failed for PDF %s: %s", url, e)
        # PDF filter: run when at least one of pdf_filter_text / pdf_filter_images is on. When both off, no PDF editing.
        pdf_filter_text = switches.get("pdf_filter_text", True)
        pdf_filter_images = switches.get("pdf_filter_images", True)
        if (pdf_filter_text or pdf_filter_images) and has_pdf_content and (rule is None or rule.get("state") == "allow") and (rule is None or rule.get("pdf_filter_enabled", True)):
            try:
                body_bytes = flow.response.content if hasattr(flow.response, "content") else flow.response.raw_content
                if body_bytes:
                    filtered_pdf, blocked_html, _ = filter_pdf_response(
                        body_bytes,
                        pdf_url=url,
                        referer_url=referer_url,
                        rule_context=rule,
                        distortion_warning_enabled=False,
                        filter_text=pdf_filter_text,
                        filter_images=pdf_filter_images,
                    )
                    if blocked_html is not None:
                        flow.response = http.Response.make(
                            FILTER_BLOCKED_OR_REVIEW_HTTP_STATUS,
                            blocked_html,
                            {"Content-Type": "text/html; charset=utf-8", "Content-Length": str(len(blocked_html))},
                        )
                        if getattr(flow, "metadata", None) is not None:
                            flow.metadata["traffic_status"] = "text_filter_blocked"
                        logger.info("PDF blocked by text filter - URL: %s", url)
                        return
                    if filtered_pdf is not None and filtered_pdf != body_bytes:
                        flow.response.headers.pop("transfer-encoding", None)
                        flow.response.headers.pop("content-encoding", None)
                        flow.response.raw_content = filtered_pdf
                        flow.response.headers["Content-Length"] = str(len(filtered_pdf))
                        logger.info("PDF filtered (images/text) - URL: %s", url)
                        return
            except Exception as e:
                logger.warning("PDF filter failed for %s: %s", url, e, exc_info=True)
        return

    # JavaScript (and other text) responses: base64 images inside strings (single-page apps, search widgets)
    if _is_javascript_response(flow) and flow.response.raw_content:
        rule = None
        try:
            rule = get_policy_resolver(user_id).resolve(url, "*")
        except Exception:
            pass
        _filter_embedded_data_uris(flow, url, referer_url, switches, rule)
        return

    # File download (non-image): return send-for-review page unless global switch or per-rule file_filter_enabled is off
    if _is_file_download_response(flow) and not _is_content_type_already_filtered(flow):
        if get_filter_switches().get("file_download_filter", True):
            file_rule = None
            if switches.get("url_policy", True):
                try:
                    file_rule = get_policy_resolver(user_id).resolve(url, "html") or get_policy_resolver(user_id).resolve(url, "*")
                except Exception:
                    pass
            if file_rule is None or file_rule.get("file_filter_enabled", True):
                file_url = url
                filename = _get_filename_from_response(flow) or "קובץ"
                body = get_send_for_review_file_page_bytes(file_url=file_url, filename=filename)
                flow.response = http.Response.make(
                    FILTER_BLOCKED_OR_REVIEW_HTTP_STATUS,
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
                    flow.metadata["traffic_status"] = "file_review"
                logger.info(
                    "File download intercepted, showing send-for-review - URL: %s, filename: %s",
                    url,
                    filename,
                )
                return
        logger.debug("File download: passed through (file_download_filter off or file_filter_enabled=False for rule) - URL: %s", url[:80] if url else "")

    return


def _process_image(flow: http.HTTPFlow, extracted, url: str, referer_url, switches: dict, user_id) -> None:
    """Images (any declared content type – detection is by content, so an image labelled text/html or
    application/octet-stream does not skip the filter)."""

    # URL policy for images: when url_policy is on and site is block/review, image filter still runs and returns placeholder.
    # When site is "allow" we no longer skip – image filter always runs when its switch is on (independent).
    rule = None
    if switches.get("url_policy", True):
        try:
            resolver = get_policy_resolver(user_id)
            rule = resolver.resolve(url, "image")
        except Exception as e:
            logger.warning("Policy resolution failed for %s: %s; applying filter", url, e)
    else:
        logger.debug("URL policy filter disabled - continuing to image filter check")

    if not switches.get("image_filter", True):
        logger.debug("Image filter disabled - passing image through - URL: %s", url)
        return
    # Only skip by rule (image_filter_enabled) when url_policy is on – so filters work independently
    if switches.get("url_policy", True):
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

    image_result, content_type_override, image_status = get_image_with_status(
        image_data=image_content,
        image_url=url,
        referer_url=referer_url,
        image_mime_type=mime_type,
    )
    logger.debug("Got image result, size: %s bytes, status: %s", len(image_result), image_status)

    if image_status != "allowed":
        flow.response.headers.pop("content-encoding", None)
        if content_type_override:
            flow.response.headers["Content-Type"] = content_type_override
        flow.response.headers["X-Goallm-Image-Status"] = image_status
    flow.response.raw_content = image_result
    flow.response.headers["Content-Length"] = str(len(image_result))
    if image_status in ("checking", "pending", "error"):
        flow.response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        flow.response.headers["Pragma"] = "no-cache"
        flow.response.headers["Expires"] = "0"
    logger.info("Image processing complete for URL: %s", url)
