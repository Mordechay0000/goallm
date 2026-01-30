"""
mitmproxy addon: intercepts HTTP traffic and processes responses (e.g. image filtering).
"""
from pathlib import Path
import sys

# Ensure project root is on path for mitmproxy
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import logging
import traceback

from mitmproxy import http

from core.http_processor.http_flow_processor import process_http_response
from core.logger.logging_config import setup_logging
from core.proxy.utils import format_flow_error, format_response_error

setup_logging()
logger = logging.getLogger(__name__)


class FilterAddon:
    """mitmproxy addon that processes HTTP responses (e.g. image filtering)."""

    async def request(self, flow: http.HTTPFlow) -> None:
        logger.debug(
            "HTTP Request - Method: %s, URL: %s",
            flow.request.method,
            flow.request.pretty_url,
        )

    async def response(self, flow: http.HTTPFlow) -> None:
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
