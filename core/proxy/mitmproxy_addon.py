"""
mitmproxy addon: intercepts HTTP traffic and processes responses (e.g. image filtering).
When FILTER_BIND_BASE_URL is set, requests from IPs not bound to a user are redirected to the bind flow.
"""
from pathlib import Path
import sys
import os
from urllib.parse import quote, urlparse

# Ensure project root is on path for mitmproxy
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import logging
import traceback

from mitmproxy import http

from core.http_processor.http_flow_processor import process_http_response
from core.logger.logging_config import setup_logging
from core.policy_processor.policy_database import get_user_id_for_ip
from core.proxy.utils import format_flow_error, format_response_error

setup_logging()
logger = logging.getLogger(__name__)

# Base URL for the bind page. Unbound IPs are redirected here. Default: CRM on same machine (dev).
# Set to "off" or "0" to disable redirect (old behavior: use first user's rules for all).
_raw = (os.environ.get("FILTER_BIND_BASE_URL") or "http://localhost:5173").strip().rstrip("/")
FILTER_BIND_BASE_URL = None if _raw.lower() in ("off", "0", "false", "") else _raw

# Same secret as CRM for internal touch endpoint (last_used_at).
CRM_PROXY_SECRET = os.environ.get("CRM_PROXY_SECRET", "dev-secret").strip()


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


class FilterAddon:
    """mitmproxy addon that processes HTTP responses (e.g. image filtering)."""

    async def request(self, flow: http.HTTPFlow) -> None:
        if not hasattr(flow, "metadata"):
            flow.metadata = {}
        client_ip = None
        if flow.client_conn and getattr(flow.client_conn, "peername", None):
            try:
                client_ip = flow.client_conn.peername[0]
            except (IndexError, TypeError):
                pass
        # Redirect before any filtering: every request from an unbound IP goes to bind (except requests to the bind host itself).
        if FILTER_BIND_BASE_URL is not None and client_ip and not _is_request_to_bind_host(flow):
            user_id = get_user_id_for_ip(client_ip)
            if user_id is None:
                return_url = flow.request.pretty_url if flow.request else ""
                bind_url = f"{FILTER_BIND_BASE_URL}/bind?return_url={quote(return_url, safe='')}"
                logger.info("Unbound IP %s → redirect to bind: %s", client_ip, bind_url)
                flow.response = http.Response.make(
                    302,
                    b"",
                    {"Location": bind_url, "Content-Type": "text/html; charset=utf-8"},
                )
                flow.metadata["redirected_to_bind"] = True  # so response() skips processing and does not overwrite
                return
            flow.metadata["user_id"] = user_id
            logger.info("Bound connection: IP=%s -> user_id=%s (filter settings apply to this user)", client_ip, user_id)
            # Update last_used_at for this binding (fire-and-forget to CRM).
            try:
                import urllib.request
                import json
                req = urllib.request.Request(
                    f"{FILTER_BIND_BASE_URL}/api/internal/touch-ip",
                    data=json.dumps({"ip": client_ip, "secret": CRM_PROXY_SECRET}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                urllib.request.urlopen(req, timeout=2)
            except Exception as e:
                logger.debug("Touch IP failed (non-fatal): %s", e)
        else:
            flow.metadata["user_id"] = get_user_id_for_ip(client_ip) if client_ip else None
            if client_ip and flow.metadata.get("user_id") is None:
                logger.debug("Unbound IP %s (no user_id); redirect or default rules will apply", client_ip)

        logger.debug(
            "HTTP Request - Method: %s, URL: %s",
            flow.request.method,
            flow.request.pretty_url,
        )

    async def response(self, flow: http.HTTPFlow) -> None:
        # Do not process redirects we set in request() (unbound IP → bind page); otherwise they get overwritten with send-for-review page
        if flow.metadata.get("redirected_to_bind"):
            logger.debug("Skipping response processing (redirect to bind)")
            return

        url = flow.request.pretty_url if flow.request else "Unknown URL"
        logger.info(
            "HTTP Response received - URL: %s, Status: %s",
            url,
            flow.response.status_code,
        )
        logger.debug("Response headers: %s", dict(flow.response.headers))

        try:
            process_http_response(flow)
            logger.debug("Response processing completed for URL: %s", url)
        except Exception as e:
            logger.exception(format_response_error(url, e))
            print(f"\n{'=' * 80}")
            print("[RESPONSE PROCESSING ERROR]")
            print(f"  URL: {url}")
            print(f"  Error: {type(e).__name__}: {e}")
            traceback.print_exc()
            print(f"{'=' * 80}\n")

            flow.response = http.Response.make(
                500,
                b"Internal Server Error",
                {"Content-Type": "text/plain"},
            )

    def error(self, flow: http.HTTPFlow) -> None:
        """Handle errors during request/response (e.g. SSL, connection)."""
        if not flow.error:
            return

        details = format_flow_error(flow)
        if not details:
            return

        full_msg = "\n  ".join(details)
        error_str = str(flow.error)
        is_http2 = "HTTP/2 protocol error" in error_str or "ConnectionState" in error_str

        if is_http2:
            logger.warning(
                "[MITMPROXY HTTP/2 PROTOCOL ERROR (usually non-critical)]\n  %s",
                full_msg,
            )
        else:
            logger.error("[MITMPROXY ERROR]\n  %s", full_msg)

        url = flow.request.pretty_url if flow.request else "Unknown URL"
        method = flow.request.method if flow.request else "Unknown"
        host = flow.request.host if flow.request else "Unknown"
        port = flow.request.port if flow.request else "Unknown"

        print(f"\n{'=' * 80}")
        if is_http2:
            print(
                f"[MITMPROXY HTTP/2 PROTOCOL ERROR] {type(flow.error).__name__} "
                "(usually non-critical)"
            )
            print("  ⚠️  This is typically a server-side issue, not a problem with your code")
        else:
            print(f"[MITMPROXY ERROR] {type(flow.error).__name__}")
        print(f"  Message: {error_str}")
        print(f"  URL: {url}")
        print(f"  Method: {method}")
        print(f"  Host: {host}:{port}")
        if hasattr(flow, "state"):
            print(f"  Flow State: {flow.state}")
        if hasattr(flow.error, "args") and flow.error.args:
            print(f"  Error Args: {flow.error.args}")
        if isinstance(flow.error, Exception) and getattr(
            flow.error, "__traceback__", None
        ):
            print("  Traceback:")
            traceback.print_exception(
                type(flow.error), flow.error, flow.error.__traceback__
            )
        print(f"{'=' * 80}\n")


logger.info("Initializing FilterAddon")
addons = [FilterAddon()]
logger.info("FilterAddon initialized and registered")
