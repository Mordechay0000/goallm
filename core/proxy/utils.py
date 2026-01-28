"""
Shared utilities for the proxy addon.
"""
from urllib.parse import urlparse

import ipaddress
import logging
import traceback
from typing import Any

import tldextract

logger = logging.getLogger(__name__)


def normalize_domain(url: str) -> str | None:
    """Normalize URL to a canonical domain form. Returns None if invalid."""
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        if not host:
            return None

        host = host.lower().rstrip(".")

        try:
            ipaddress.ip_address(host)
            return host
        except ValueError:
            pass

        host = host.encode("ascii").decode("idna")
        if host.startswith("www."):
            host = host[4:]

        ext = tldextract.extract(host)
        if not ext.suffix:
            return None

        return f"{ext.domain}.{ext.suffix}"
    except Exception:
        return None


def format_flow_error(flow: Any) -> list[str]:
    """Build a list of error detail lines for a flow."""
    details = []
    error_msg = flow.error
    if not error_msg:
        return details

    url = flow.request.pretty_url if flow.request else "Unknown URL"
    method = flow.request.method if flow.request else "Unknown"
    host = flow.request.host if flow.request else "Unknown"
    port = flow.request.port if flow.request else "Unknown"

    details.append(f"Error Type: {type(error_msg).__name__}")
    details.append(f"Error Message: {str(error_msg)}")
    details.append(f"URL: {url}")
    details.append(f"Method: {method}")
    details.append(f"Host: {host}:{port}")

    if hasattr(flow, "state"):
        details.append(f"Flow State: {flow.state}")
    if hasattr(error_msg, "args") and error_msg.args:
        details.append(f"Error Args: {error_msg.args}")
    if isinstance(error_msg, Exception) and getattr(error_msg, "__traceback__", None):
        tb = "".join(
            traceback.format_exception(
                type(error_msg), error_msg, error_msg.__traceback__
            )
        )
        details.append(f"Traceback:\n{tb}")

    return details


def format_response_error(url: str, exc: Exception) -> str:
    """Build error message for response processing failures."""
    return (
        f"Error in processing HTTP response for {url}:\n"
        f"  Error type: {type(exc).__name__}\n"
        f"  Error message: {str(exc)}\n"
    )
