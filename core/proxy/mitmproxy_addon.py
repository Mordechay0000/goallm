"""
mitmproxy addon: intercepts HTTP traffic and processes responses (policy, text, images, PDF, video).

Identity of the surfer:
- Personal proxy credentials (created in the CRM, "חיבורים" page) → that user. Works behind shared/NAT IPs.
- Legacy shared credential (PROXY_AUTH) or no auth (PROXY_REQUIRE_AUTH=0) → user bound to the client IP.
  Unbound IPs are redirected to the bind page (FILTER_BIND_BASE_URL) or get a 403 page.

The client IP is the TCP peer. X-Forwarded-For / X-Real-IP are honored only when the peer is a trusted
proxy (TRUSTED_PROXY_IPS) – otherwise any client could claim another family's IP.
"""
from pathlib import Path
import sys
from urllib.parse import quote, urlparse

# Ensure project root is on path for mitmproxy
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import asyncio
import json
import logging
import threading
import time
import urllib.request

from mitmproxy import http, tls

from core.flow.http_flow_processor import process_http_response, rewrite_request_accept_header
from core.flow.traffic_utils import blocked_traffic_status
from core.flow.site_policy_pages import (
    get_blocked_page_bytes,
    get_send_for_review_page_bytes,
)
from core.filters.video.video_filter import (
    block_response_headers,
    dash_children,
    hls_child_urls,
    is_dash_manifest,
    is_hls_manifest,
    is_media_segment,
    is_streamable_media,
    is_video_request,
    video_allowed_for_rule,
)
from core.filters.video.youtube import is_googlevideo_playback
from core.logger.logging_config import setup_logging
from core.net_utils import resolve_client_ip
from core.policy.policy_cache import (
    get_active_traffic_session_id,
    get_filter_switches,
    get_learned_passthrough,
    get_policy_resolver,
    get_user_id_for_ip,
    is_media_approved,
)
from core.policy.policy_database import (
    add_approved_media_children,
    add_approved_media_patterns,
    add_traffic_log_entry,
    canonical_media_key,
    record_blocked_media,
    record_tls_client_failure,
)
from core.proxy.image_refresh import STATUS_PATH, strip_reload_param_from_request
from core.proxy.proxy_auth import ProxyAuthenticator
from core.proxy.video_overlay import (
    VIDEO_REVIEW_PATH,
    VIDEO_STATUS_PATH,
    ReviewRateLimiter,
    parse_payload as parse_video_payload,
    request_review as request_video_review_from_overlay,
    video_status,
)
from core.proxy_identity import HEADER as PROXY_USER_HEADER, sign_user
from core.filters.image.data_uri_filter import filter_data_uri_images
from core.filters.image.image_extraction import detect_image_mime
from core.filters.image.image_status_manager import get_image_with_status, get_url_statuses
from core.proxy.utils import format_flow_error, format_response_error
from data.constants import (
    AUTO_PASSTHROUGH_MIN_FAILURES,
    AUTO_PASSTHROUGH_PINNED_APPS,
    FILTER_BIND_BASE_URL,
    CRM_PROXY_SECRET,
    CRM_BASE_URL,
    FILTER_DIAGNOSTIC_HOST,
    FILTER_DIAGNOSTIC_HOST_ALIAS,
    FILTER_BLOCKED_OR_REVIEW_HTTP_STATUS,
    SENSITIVE_PASSTHROUGH_DOMAINS,
    TOUCH_IP_MIN_INTERVAL_SEC,
)
from data.landing_pages import UNBOUND_IP_HTML

setup_logging()
logger = logging.getLogger(__name__)


def _peer_ip(flow: http.HTTPFlow) -> str | None:
    if flow.client_conn and getattr(flow.client_conn, "peername", None):
        try:
            return flow.client_conn.peername[0]
        except (IndexError, TypeError):
            return None
    return None


def _client_ip_from_flow(flow: http.HTTPFlow) -> str | None:
    """IP of the surfer. Forwarding headers count only when the TCP peer is a trusted proxy."""
    headers = flow.request.headers if flow.request else {}
    return resolve_client_ip(
        _peer_ip(flow),
        headers.get("x-forwarded-for") if headers else None,
        headers.get("x-real-ip") if headers else None,
    )


def _request_host_normalized(flow: http.HTTPFlow) -> str:
    """Host from request without port (e.g. '1.2.3.4:80' -> '1.2.3.4')."""
    raw = (flow.request.host or "").strip()
    if ":" in raw:
        return raw.split(":")[0].strip()
    return raw


def _is_request_to_diagnostic_host(flow: http.HTTPFlow) -> bool:
    """True if this request is for the filter diagnostic page (1.2.3.4 or filter.check)."""
    if not flow.request:
        return False
    host = _request_host_normalized(flow).lower()
    return host == (FILTER_DIAGNOSTIC_HOST or "").lower() or host == (
        FILTER_DIAGNOSTIC_HOST_ALIAS or ""
    ).lower()


def _is_request_to_bind_host(flow: http.HTTPFlow) -> bool:
    """True if this request is going to the bind server (avoid redirect loop)."""
    if not FILTER_BIND_BASE_URL or not flow.request:
        return False
    try:
        parsed = urlparse(FILTER_BIND_BASE_URL)
        bind_host = (parsed.hostname or "").lower()
        bind_port = parsed.port or (443 if parsed.scheme == "https" else 80)
        req_host = (flow.request.host or "").lower()
        req_port = flow.request.port or 80
        return req_host == bind_host and req_port == bind_port
    except Exception:
        return False


def _looks_like_file_request(flow: http.HTTPFlow) -> bool:
    """True if the request URL/path suggests a file (download/document). Used for traffic_status file_blocked/file_review."""
    if not flow.request or not flow.request.path:
        return False
    path = (flow.request.path or "").split("?")[0].lower()
    if path.endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".rar", ".7z", ".exe", ".dmg", ".pkg")):
        return True
    if any(x in path for x in ("/file/", "/download", "/attachment", "/open?id=", "/export?", "/uc?export=download")):
        return True
    return False


def _host_matches(host: str, domains) -> bool:
    host = (host or "").lower().rstrip(".")
    return any(host == d or host.endswith("." + d) for d in domains)


def _html_response(status: int, body: bytes, no_cache: bool = False) -> http.Response:
    headers = {"Content-Type": "text/html; charset=utf-8", "Content-Length": str(len(body))}
    if no_cache:
        headers.update({"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache", "Expires": "0"})
    return http.Response.make(status, body, headers)


class FilterAddon:
    """mitmproxy addon: identity, request-time URL policy, response filtering."""

    def __init__(self) -> None:
        self.auth = ProxyAuthenticator()
        self._touch_lock = threading.Lock()
        self._touched: dict[str, float] = {}
        self._recorded_media: dict[tuple, float] = {}
        self._review_limiter = ReviewRateLimiter()

    # ---------- identity ----------

    def http_connect(self, flow: http.HTTPFlow) -> None:
        self.auth.http_connect(flow)

    def requestheaders(self, flow: http.HTTPFlow) -> None:
        self.auth.requestheaders(flow)

    def _resolve_user(self, flow: http.HTTPFlow, client_ip: str | None) -> int | None:
        identity = flow.metadata.get("goallm_identity")
        if identity is not None and identity.kind == "user":
            return identity.user_id
        return get_user_id_for_ip(client_ip) if client_ip else None

    def _touch_ip(self, client_ip: str) -> None:
        """Update the binding's last_used_at – at most once per TOUCH_IP_MIN_INTERVAL_SEC per IP
        (was: a new thread + HTTP request to the CRM for every single request)."""
        if FILTER_BIND_BASE_URL is None:
            return
        now = time.monotonic()
        with self._touch_lock:
            last = self._touched.get(client_ip)
            if last is not None and now - last < TOUCH_IP_MIN_INTERVAL_SEC:
                return
            self._touched[client_ip] = now
            if len(self._touched) > 100000:
                self._touched.clear()

        def _send():
            try:
                req = urllib.request.Request(
                    f"{FILTER_BIND_BASE_URL}/api/internal/touch-ip",
                    data=json.dumps({"ip": client_ip, "secret": CRM_PROXY_SECRET}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                urllib.request.urlopen(req, timeout=2)
            except Exception as e:
                logger.debug("Touch IP failed (non-fatal): %s", e)

        threading.Thread(target=_send, daemon=True).start()

    # ---------- TLS passthrough for sensitive sites ----------

    def tls_clienthello(self, data: tls.ClientHelloData) -> None:
        """Banks / HMOs / gov: pass the encrypted connection through without opening it – if the site is allowed.
        (Privacy, and apps with certificate pinning.) A site that is not allowed is intercepted as usual so the
        block page can be shown."""
        sni = (data.client_hello.sni or "").lower()
        if not sni:
            return
        sensitive = bool(SENSITIVE_PASSTHROUGH_DOMAINS) and _host_matches(sni, SENSITIVE_PASSTHROUGH_DOMAINS)
        learned = AUTO_PASSTHROUGH_PINNED_APPS and sni in get_learned_passthrough()
        if not (sensitive or learned):
            return
        try:
            client = data.context.client
            identity = self.auth.identity_for_conn(client)
            user_id = identity.user_id if identity is not None and identity.kind == "user" else None
            if user_id is None:
                ip = resolve_client_ip(client.peername[0] if client.peername else None)
                user_id = get_user_id_for_ip(ip) if ip else None
            if user_id is None:
                return
            rule = get_policy_resolver(user_id).resolve(f"https://{sni}/", "*")
            if rule is not None and rule.get("state") == "allow":
                data.ignore_connection = True
                logger.info("TLS passthrough for %s allowed site %s (user_id=%s)",
                            "sensitive" if sensitive else "pinned-app", sni, user_id)
        except Exception as e:
            logger.debug("tls_clienthello passthrough check failed for %s: %s", sni, e)

    def tls_failed_client(self, data: tls.TlsData) -> None:
        """An app with certificate pinning rejected our certificate. Learned (AUTO_PASSTHROUGH_PINNED_APPS):
        after a few failures the host is passed through – but only where the user's list explicitly allows it."""
        if not AUTO_PASSTHROUGH_PINNED_APPS:
            return
        sni = (data.context.client.sni or "").lower()
        err = str(getattr(data.conn, "error", "") or "")
        if not sni or "trust" not in err:
            return
        try:
            if record_tls_client_failure(sni, AUTO_PASSTHROUGH_MIN_FAILURES):
                logger.warning("Host %s rejects the proxy certificate (pinning) – passthrough where the site is allowed", sni)
        except Exception as e:
            logger.debug("record_tls_client_failure failed for %s: %s", sni, e)

    # ---------- request ----------

    async def request(self, flow: http.HTTPFlow) -> None:
        if flow.response is not None:
            return  # e.g. 407 set by authentication
        flow.metadata["request_start_time"] = time.perf_counter()
        client_ip = _client_ip_from_flow(flow)

        # Diagnostic host (filter.check / 1.2.3.4) – redirect to CRM /diagnostic.
        if _is_request_to_diagnostic_host(flow):
            flow.metadata["user_id"] = self._resolve_user(flow, client_ip)
            diagnostic_url = f"{CRM_BASE_URL.rstrip('/')}/diagnostic"
            flow.response = http.Response.make(
                302,
                b"",
                {"Location": diagnostic_url, "Content-Type": "text/html; charset=utf-8"},
            )
            flow.metadata["redirected_to_bind"] = True
            return

        if _is_request_to_bind_host(flow):
            # The CRM must see the real client IP. Overwrite (not prepend to) whatever the client sent,
            # so a forged X-Forwarded-For can never reach the CRM's binding logic.
            if client_ip:
                flow.request.headers["x-forwarded-for"] = client_ip
                flow.request.headers["x-real-ip"] = client_ip
            else:
                flow.request.headers.pop("x-forwarded-for", None)
                flow.request.headers.pop("x-real-ip", None)
            # Signed proof for the CRM that this connection is filtered (needed for credential-based users,
            # who have no IP binding). Any client-supplied copy is dropped first.
            flow.request.headers.pop(PROXY_USER_HEADER, None)
            identity = flow.metadata.get("goallm_identity")
            if identity is not None and identity.kind == "user":
                flow.request.headers[PROXY_USER_HEADER] = sign_user(identity.user_id)
            flow.metadata["crm_user_id"] = self._resolve_user(flow, client_ip)
            return

        rewrite_request_accept_header(flow)
        strip_reload_param_from_request(flow)

        user_id = self._resolve_user(flow, client_ip)
        if user_id is None:
            if FILTER_BIND_BASE_URL is not None:
                return_url = flow.request.pretty_url if flow.request else ""
                bind_url = f"{FILTER_BIND_BASE_URL}/bind?return_url={quote(return_url, safe='')}"
                logger.info("Unbound IP %s → redirect to bind", client_ip)
                flow.response = http.Response.make(
                    302,
                    b"",
                    {"Location": bind_url, "Content-Type": "text/html; charset=utf-8"},
                )
            else:
                logger.warning("Unbound IP %s → blocking (connection not filtered by us)", client_ip)
                flow.response = _html_response(403, UNBOUND_IP_HTML.encode("utf-8"))
            flow.metadata["redirected_to_bind"] = True
            return

        flow.metadata["user_id"] = user_id
        req_path = flow.request.path.split("?", 1)[0]
        if req_path == STATUS_PATH and flow.request.method == "POST":
            self._answer_image_status(flow)
            return
        if req_path in (VIDEO_STATUS_PATH, VIDEO_REVIEW_PATH) and flow.request.method == "POST":
            await self._answer_video(flow, req_path, user_id)
            return
        identity = flow.metadata.get("goallm_identity")
        if client_ip and (identity is None or identity.kind != "user"):
            self._touch_ip(client_ip)

        # Request-time URL policy for every request type: only allowed URLs may load.
        if not get_filter_switches().get("url_policy", True):
            return
        try:
            rule = get_policy_resolver(user_id).resolve(flow.request.url, "*")
        except Exception as e:
            # Fail closed: an error must never open a URL that would otherwise be blocked.
            logger.warning("Request-time policy check failed for %s: %s – blocking", flow.request.url, e)
            body = get_send_for_review_page_bytes(request_url=flow.request.url)
            flow.response = _html_response(FILTER_BLOCKED_OR_REVIEW_HTTP_STATUS, body, no_cache=True)
            flow.metadata["policy_handled_in_request"] = True
            flow.metadata["traffic_status"] = "error"
            return
        if rule is None:
            return
        state = rule.get("state", "block")
        if state == "block":
            body = get_blocked_page_bytes(
                request_url=flow.request.url,
                rule=rule,
                tags=rule.get("tags") or [],
                block_reason=rule.get("block_reason") or "",
            )
            flow.response = _html_response(FILTER_BLOCKED_OR_REVIEW_HTTP_STATUS, body)
            flow.metadata["policy_handled_in_request"] = True
            flow.metadata["traffic_status"] = blocked_traffic_status(rule, _looks_like_file_request(flow))
            logger.info("Request blocked by policy - URL: %s", flow.request.url)
            return
        if state == "review":
            body = get_send_for_review_page_bytes(request_url=flow.request.url)
            flow.response = _html_response(FILTER_BLOCKED_OR_REVIEW_HTTP_STATUS, body, no_cache=True)
            flow.metadata["policy_handled_in_request"] = True
            flow.metadata["traffic_status"] = "file_review" if _looks_like_file_request(flow) else "review"
            logger.info("Request send-for-review by policy - URL: %s", flow.request.url)
            return
        flow.metadata["request_rule"] = rule

    @staticmethod
    def _answer_image_status(flow: http.HTTPFlow) -> None:
        """Answered by the proxy itself (never forwarded): which placeholder images are now decided."""
        try:
            payload = json.loads(flow.request.get_text() or "{}")
            urls = [u for u in (payload.get("urls") or []) if isinstance(u, str)]
            statuses = get_url_statuses(urls)
        except Exception as e:
            logger.debug("image-status request failed: %s", e)
            statuses = {}
        body = json.dumps(statuses).encode("utf-8")
        flow.response = http.Response.make(
            200, body, {"Content-Type": "application/json", "Cache-Control": "no-store", "Content-Length": str(len(body))}
        )
        flow.metadata["redirected_to_bind"] = True  # skip response processing
        flow.metadata["traffic_status"] = "internal"

    async def _answer_video(self, flow: http.HTTPFlow, path: str, user_id: int) -> None:
        """Blocked-video overlay: status of the page's videos, or "send for review" (answered by the proxy itself)."""
        payload = parse_video_payload(flow.request.get_text(strict=False))
        try:
            if path == VIDEO_STATUS_PATH:
                code, data = 200, await asyncio.to_thread(video_status, payload, user_id)
            else:
                code, data = await asyncio.to_thread(request_video_review_from_overlay, payload, user_id, self._review_limiter)
        except Exception as e:
            logger.warning("video overlay request failed: %s", e)
            code, data = 500, {"error": "שגיאה"}
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        flow.response = http.Response.make(
            code, body, {"Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", "Content-Length": str(len(body))}
        )
        flow.metadata["redirected_to_bind"] = True  # skip response processing
        flow.metadata["traffic_status"] = "internal"

    # ---------- response ----------

    def responseheaders(self, flow: http.HTTPFlow) -> None:
        """Decide on video/streaming media before the body is read: blocked video is discarded unbuffered,
        allowed media is streamed instead of being held whole in proxy memory."""
        if flow.metadata.get("redirected_to_bind") or flow.metadata.get("user_id") is None or not flow.response:
            return
        ct = (flow.response.headers.get("content-type") or "")
        url = flow.request.url
        path = flow.request.path or ""
        if not is_video_request(ct, url, path):
            return
        switches = get_filter_switches()
        rule = flow.metadata.get("request_rule")
        approved = False
        if not video_allowed_for_rule(rule, switches.get("video_filter", True)):
            try:
                approved = is_media_approved(url)
            except Exception as e:
                logger.warning("approved-media lookup failed for %s: %s", url, e)
            if not approved:
                block_response_headers(flow, FILTER_BLOCKED_OR_REVIEW_HTTP_STATUS)
                flow.metadata["streamed"] = True
                flow.metadata["traffic_status"] = "video_blocked"
                self._remember_blocked_media(flow, ct, path)
                logger.info("Video blocked (headers stage) - URL: %s", flow.request.pretty_url)
                return
        if approved and (is_hls_manifest(ct, path) or is_dash_manifest(ct, path)):
            # Keep the (small) playlist body so its segments can be registered as approved too.
            flow.metadata["approved_manifest"] = True
            return
        if is_streamable_media(ct):
            flow.response.stream = True
            flow.metadata["streamed"] = True

    def _remember_blocked_media(self, flow: http.HTTPFlow, ct: str, path: str) -> None:
        """Record what was blocked, so the user can send exactly this video for review (MSE players hide the URL)."""
        if is_media_segment(ct, path) or is_googlevideo_playback(flow.request.url):
            return  # (YouTube: the watch URL is recorded when its player response is blocked)
        user_id = flow.metadata.get("user_id")
        key = (user_id, canonical_media_key(flow.request.url))
        now = time.monotonic()
        last = self._recorded_media.get(key)
        if last is not None and now - last < 600:  # (monotonic() may be < 600 right after boot)
            return
        self._recorded_media[key] = now
        if len(self._recorded_media) > 50000:
            self._recorded_media.clear()
        try:
            record_blocked_media(user_id, flow.request.url, flow.request.headers.get("referer"), ct)
        except Exception as e:
            logger.debug("record_blocked_media failed: %s", e)

    async def response(self, flow: http.HTTPFlow) -> None:
        url = flow.request.pretty_url if flow.request else "Unknown URL"
        if flow.metadata.get("approved_manifest") and flow.response is not None:
            try:
                text = flow.response.get_text(strict=False) or ""
                parent = canonical_media_key(flow.request.url)
                ct = flow.response.headers.get("content-type") or ""
                if is_dash_manifest(ct, flow.request.path or "") and len(text) < 5_000_000:
                    children, patterns = dash_children(text, flow.request.url)
                    await asyncio.to_thread(add_approved_media_patterns, parent, patterns)
                else:
                    children = hls_child_urls(text, flow.request.url)
                await asyncio.to_thread(add_approved_media_children, parent, children)
            except Exception as e:
                logger.warning("Could not register manifest children for %s: %s", url, e)
            flow.metadata["streamed"] = True  # nothing else to filter in a playlist
        # Only identified users' traffic is processed: a 407 (auth required), the diagnostic redirect or a
        # request to the CRM itself must reach the client untouched (the 407 used to be replaced by a block page).
        if (
            flow.metadata.get("user_id") is not None
            and not flow.metadata.get("redirected_to_bind")
            and not flow.metadata.get("streamed")
        ):
            try:
                # Heavy work (HTML parsing, image hashing, PDF) runs in a worker thread so one large page
                # does not stall every other user's traffic on the event loop.
                await asyncio.to_thread(process_http_response, flow)
            except Exception as e:
                logger.exception(format_response_error(url, e))
                flow.response = http.Response.make(
                    500,
                    b"Internal Server Error",
                    {"Content-Type": "text/plain"},
                )

        # Traffic recording: log every request when the user has an active session.
        user_id = flow.metadata.get("user_id")
        if user_id is None or flow.metadata.get("traffic_status") == "internal":
            return
        session_id = get_active_traffic_session_id(user_id)
        if session_id is None:
            return
        try:
            t0 = flow.metadata.get("request_start_time")
            time_sec = (time.perf_counter() - t0) if isinstance(t0, (int, float)) else 0.0
            content_type = (flow.response.headers.get("content-type") or "").strip() if flow.response else ""
            await asyncio.to_thread(
                add_traffic_log_entry,
                session_id=session_id,
                user_id=user_id,
                url=url,
                protocol=(flow.request.scheme or "https") if flow.request else "",
                status=flow.metadata.get("traffic_status", "open"),
                time_sec=time_sec,
                content_type=content_type or None,
                http_status_code=flow.response.status_code if flow.response else None,
            )
        except Exception as log_err:
            logger.debug("Traffic log entry failed: %s", log_err)

    # ---------- WebSocket ----------

    async def websocket_message(self, flow: http.HTTPFlow) -> None:
        """Images pushed over a WebSocket (chat apps, live feeds) never become an image request, so they are
        checked here: a binary message that IS an image, and base64 data-URI images inside text messages.
        Only server → client messages of identified users; an image not yet approved is replaced."""
        if flow.websocket is None or not flow.websocket.messages:
            return
        message = flow.websocket.messages[-1]
        user_id = flow.metadata.get("user_id")
        if message.from_client or user_id is None or not message.content:
            return
        switches = get_filter_switches()
        if not switches.get("image_filter", True):
            return
        rule = flow.metadata.get("request_rule")
        if rule is not None and not rule.get("image_filter_enabled", True):
            return
        url = flow.request.pretty_url
        try:
            if message.is_text:
                if b"data:image/" not in message.content or not switches.get("embedded_image_filter", True):
                    return
                new_body, n = await asyncio.to_thread(filter_data_uri_images, message.content, url, None)
                if n:
                    message.content = new_body
                return
            mime = detect_image_mime(message.content)
            if mime is None:
                return
            data = message.content
            result, _ct, status = await asyncio.to_thread(
                get_image_with_status, data, f"ws:{url[:200]}", None, mime
            )
            if status != "allowed":
                message.content = result
        except Exception as e:
            # fail closed for a binary image (never forward it unchecked); a text message is left as is
            logger.warning("WebSocket image check failed on %s: %s", url[:80], e)
            if not message.is_text and detect_image_mime(message.content):
                message.drop()

    def error(self, flow: http.HTTPFlow) -> None:
        """Handle errors during request/response (e.g. SSL, connection)."""
        if not flow.error:
            return
        user_id = flow.metadata.get("user_id") if getattr(flow, "metadata", None) else None
        if user_id is None and getattr(flow, "request", None):
            client_ip = _client_ip_from_flow(flow)
            if client_ip:
                user_id = self._resolve_user(flow, client_ip)
        if user_id is not None:
            session_id = get_active_traffic_session_id(user_id)
            if session_id is not None:
                try:
                    t0 = flow.metadata.get("request_start_time")
                    time_sec = (time.perf_counter() - t0) if isinstance(t0, (int, float)) else 0.0
                    err_str = str(flow.error)
                    status = "cert_missing" if "certificate" in err_str.lower() or "ssl" in err_str.lower() else "error"
                    add_traffic_log_entry(
                        session_id=session_id,
                        user_id=user_id,
                        url=flow.request.pretty_url if flow.request else "Unknown URL",
                        protocol=(flow.request.scheme or "") if flow.request else "",
                        status=status,
                        time_sec=time_sec,
                        content_type=None,
                        http_status_code=None,
                    )
                except Exception as log_err:
                    logger.debug("Traffic log entry (error) failed: %s", log_err)

        details = format_flow_error(flow)
        if not details:
            return
        full_msg = "\n  ".join(details)
        error_str = str(flow.error)
        if "HTTP/2 protocol error" in error_str or "ConnectionState" in error_str:
            logger.warning("[MITMPROXY HTTP/2 PROTOCOL ERROR (usually non-critical)]\n  %s", full_msg)
        else:
            logger.error("[MITMPROXY ERROR]\n  %s", full_msg)


logger.info("Initializing FilterAddon")
addons = [FilterAddon()]
logger.info("FilterAddon initialized and registered")
