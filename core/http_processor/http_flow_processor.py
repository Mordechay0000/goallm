"""
Process HTTP flows: detect images, run status check, and replace when needed.
"""
import logging

from mitmproxy import http

from core.http_processor.image_extraction import extract_image_content
from core.image_processing.image_status_manager import get_image_with_status

logger = logging.getLogger(__name__)


def process_http_response(flow: http.HTTPFlow) -> None:
    """Process HTTP response and filter/replace images based on status."""
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

    extracted = extract_image_content(flow)
    if extracted is None:
        logger.debug("Response is not an image, skipping processing for URL: %s", url)
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

    image_result, flow_response = get_image_with_status(
        image_data=image_content,
        image_url=url,
        referer_url=referer_url,
        image_mime_type=mime_type,
    )
    logger.debug("Got image result, size: %s bytes", len(image_result))

    flow.response.raw_content = image_result
    if flow_response is not None:
        logger.debug("Updating flow response with new response object")
        flow.response = flow_response

    logger.info("Image processing complete for URL: %s", url)
