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
    is_streamable_media,
    is_video_response,
    video_allowed_for_rule,
)
from core.logger.logging_config import setup_logging
from core.net_utils import resolve_client_ip
from core.policy.policy_cache import (
    get_active_traffic_session_id,
    get_filter_switches,
    get_policy_resolver,
    get_user_id_for_ip,
)
from core.policy.policy_database import add_traffic_log_entry
from core.proxy.image_refresh import STATUS_PATH, strip_reload_param_from_request
from core.proxy.proxy_auth import ProxyAuthenticator
from core.proxy_identity import HEADER as PROXY_USER_HEADER, sign_user
from core.filters.image.image_status_manager import get_url_statuses
from core.proxy.utils import format_flow_error, format_response_error
from data.constants import (
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
            last = self._touched.get(client_ip, 0.0)
            if now - last < TOUCH_IP_MIN_INTERVAL_SEC:
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
        if not sni or not SENSITIVE_PASSTHROUGH_DOMAINS or not _host_matches(sni, SENSITIVE_PASSTHROUGH_DOMAINS):
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
                logger.info("TLS passthrough for sensitive allowed site %s (user_id=%s)", sni, user_id)
        except Exception as e:
            logger.debug("tls_clienthello passthrough check failed for %s: %s", sni, e)

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
        if flow.request.path.split("?", 1)[0] == STATUS_PATH and flow.request.method == "POST":
            self._answer_image_status(flow)
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

    # ---------- response ----------

    def responseheaders(self, flow: http.HTTPFlow) -> None:
        """Decide on video/streaming media before the body is read: blocked video is discarded unbuffered,
        allowed media is streamed instead of being held whole in proxy memory."""
        if flow.metadata.get("redirected_to_bind") or flow.metadata.get("user_id") is None or not flow.response:
            return
        ct = (flow.response.headers.get("content-type") or "")
        if not is_video_response(ct, flow.request.path if flow.request else ""):
            return
        switches = get_filter_switches()
        rule = flow.metadata.get("request_rule")
        if video_allowed_for_rule(rule, switches.get("video_filter", True)):
            if is_streamable_media(ct):
                flow.response.stream = True
                flow.metadata["streamed"] = True
            return
        block_response_headers(flow, FILTER_BLOCKED_OR_REVIEW_HTTP_STATUS)
        flow.metadata["streamed"] = True
        flow.metadata["traffic_status"] = "video_blocked"
        logger.info("Video blocked (headers stage) - URL: %s", flow.request.pretty_url if flow.request else "")

    async def response(self, flow: http.HTTPFlow) -> None:
        url = flow.request.pretty_url if flow.request else "Unknown URL"
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
