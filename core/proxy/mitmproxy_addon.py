# mitmproxy addon code
import logging
import traceback
import sys
import os
from pathlib import Path

# Add project root to sys.path so mitmproxy can find our modules
# Get the directory where this file is located
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent  # Go up from core/proxy/mitmproxy_addon.py to project root
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from mitmproxy import http

from core.http_processor.http_flow_processor import process_http_response
from core.logger.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

class ImageFilterAddon:
    async def request(self, flow: http.HTTPFlow):
        logger.debug(f"HTTP Request - Method: {flow.request.method}, URL: {flow.request.pretty_url}")
        return

    async def response(self, flow: http.HTTPFlow):
        url = flow.request.pretty_url if flow.request else "Unknown URL"
        logger.info(f"HTTP Response received - URL: {url}, Status: {flow.response.status_code}")
        logger.debug(f"Response headers: {dict(flow.response.headers)}")
        try:
            process_http_response(flow)
            logger.debug(f"Response processing completed for URL: {url}")
            return
        except Exception as e:
            url = flow.request.pretty_url if flow.request else "Unknown URL"
            error_msg = (
                f"Error in processing HTTP response for {url}:\n"
                f"  Error type: {type(e).__name__}\n"
                f"  Error message: {str(e)}\n"
            )
            logger.exception(error_msg)
            
            # Print to console for immediate visibility
            print(f"\n{'='*80}")
            print(f"[RESPONSE PROCESSING ERROR]")
            print(f"  URL: {url}")
            print(f"  Error: {type(e).__name__}: {str(e)}")
            traceback.print_exc()
            print(f"{'='*80}\n")
            
            flow.response = http.Response.make(
                500,
                b"Internal Server Error",
                {"Content-Type": "text/plain"}
            )
    
    def error(self, flow: http.HTTPFlow) -> None:
        """
        Handle errors that occur during request/response processing.
        This includes SSL errors, connection errors, etc.
        """
        error_msg = flow.error
        if error_msg:
            # Extract detailed error information
            error_type = type(error_msg).__name__
            error_str = str(error_msg)
            
            # Get request details if available
            url = flow.request.pretty_url if flow.request else "Unknown URL"
            method = flow.request.method if flow.request else "Unknown"
            host = flow.request.host if flow.request else "Unknown"
            port = flow.request.port if flow.request else "Unknown"
            
            # Check if this is an HTTP/2 protocol error (common and usually non-critical)
            is_http2_error = "HTTP/2 protocol error" in error_str or "ConnectionState" in error_str
            
            # Build detailed error message
            error_details = []
            error_details.append(f"Error Type: {error_type}")
            error_details.append(f"Error Message: {error_str}")
            error_details.append(f"URL: {url}")
            error_details.append(f"Method: {method}")
            error_details.append(f"Host: {host}:{port}")
            # Check if flow has state attribute (some versions of mitmproxy don't have it)
            if hasattr(flow, 'state'):
                error_details.append(f"Flow State: {flow.state}")
            
            # Add error args if available
            if hasattr(error_msg, 'args') and error_msg.args:
                error_details.append(f"Error Args: {error_msg.args}")
            
            # Try to get traceback if it's an exception
            if isinstance(error_msg, Exception):
                try:
                    tb_str = ''.join(traceback.format_exception(type(error_msg), error_msg, error_msg.__traceback__))
                    error_details.append(f"Traceback:\n{tb_str}")
                except:
                    pass
            
            # Log to logger
            full_error_msg = "\n  ".join(error_details)
            if is_http2_error:
                # HTTP/2 protocol errors are usually non-critical - log as warning
                logger.warning(f"[MITMPROXY HTTP/2 PROTOCOL ERROR (usually non-critical)]\n  {full_error_msg}")
            else:
                logger.error(f"[MITMPROXY ERROR]\n  {full_error_msg}")
            
            # Also print to console for immediate visibility
            print(f"\n{'='*80}")
            if is_http2_error:
                print(f"[MITMPROXY HTTP/2 PROTOCOL ERROR] {error_type} (usually non-critical)")
                print(f"  ⚠️  This is typically a server-side issue, not a problem with your code")
            else:
                print(f"[MITMPROXY ERROR] {error_type}")
            print(f"  Message: {error_str}")
            print(f"  URL: {url}")
            print(f"  Method: {method}")
            print(f"  Host: {host}:{port}")
            if hasattr(flow, 'state'):
                print(f"  Flow State: {flow.state}")
            if hasattr(error_msg, 'args') and error_msg.args:
                print(f"  Error Args: {error_msg.args}")
            if isinstance(error_msg, Exception) and hasattr(error_msg, '__traceback__') and error_msg.__traceback__:
                print(f"  Traceback:")
                traceback.print_exception(type(error_msg), error_msg, error_msg.__traceback__)
            print(f"{'='*80}\n")


logger.info("Initializing ImageFilterAddon")
addons = [ImageFilterAddon()]
logger.info("ImageFilterAddon initialized and registered")
