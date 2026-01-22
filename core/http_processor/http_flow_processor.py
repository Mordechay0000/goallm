import logging
import re

from bs4 import BeautifulSoup

from mitmproxy import http
from core.image_processing.image_status_manager import get_image_with_status

logger = logging.getLogger(__name__)


def extract_image_content(flow):
    """
    Try to extract image content from response.
    Returns:
        bytes  -> binary image
        str    -> SVG text
        None   -> not an image
    """
    logger.debug("Extracting image content from HTTP response")
    data = flow.response.raw_content
    if not data or len(data) < 16:
        logger.debug(f"Response too small or empty ({len(data) if data else 0} bytes), not an image")
        return None

    head = data[:32]
    logger.debug(f"Checking image signature, first 32 bytes: {head[:16].hex()}...")

    # --- Raster formats (fast magic-bytes check) ---

    if head.startswith(b"\xff\xd8\xff"):  # JPEG
        logger.debug("Detected JPEG image")
        return data, "image/jpeg"

    elif head.startswith(b"\x89PNG\r\n\x1a\n"):  # PNG
        logger.debug("Detected PNG image")
        return data, "image/png"

    elif head.startswith(b"GIF87a") or head.startswith(b"GIF89a"):  # GIF
        logger.debug("Detected GIF image")
        return data, "image/gif"

    elif head.startswith(b"BM"):  # BMP
        logger.debug("Detected BMP image")
        return data, "image/bmp"

    elif head.startswith(b"\x00\x00\x01\x00"):  # ICO
        logger.debug("Detected ICO image")
        return data, "image/x-icon"

    elif head.startswith(b"II*\x00") or head.startswith(b"MM\x00*"):  # TIFF
        logger.debug("Detected TIFF image")
        return data, "image/tiff"
    elif head.startswith(b"RIFF") and b"WEBP" in head:  # WEBP
        logger.debug("Detected WEBP image")
        return data, "image/webp"


def extract_images_from_html(flow):
    """
    Detect HTML response and extract image references from it.

    Returns:
        List[Tuple[str, str]]  -> [(image_source, mime_type), ...]
        None                  -> not HTML or no images
    """

    resp = flow.response
    if not resp or not resp.raw_content:
        return None

    content_type = resp.headers.get("content-type", "").lower()
    if "text/html" not in content_type:
        return None  # not HTML

    try:
        html = resp.raw_content.decode("utf-8", errors="ignore")
    except Exception:
        return None

    soup = BeautifulSoup(html, "html.parser")
    results = []

    # --- <img src=...> ---
    for img in soup.find_all("img"):
        src = img.get("src")
        if not src:
            continue

        # data:image/...;base64,...
        if src.startswith("data:image/"):
            match = re.match(r"data:(image/[^;]+);base64,(.+)", src, re.DOTALL)
            if match:
                mime = match.group(1)
                results.append((src[:64] + "...", mime))
        else:
            results.append((src, "image/unknown"))

    # --- CSS background-image: url(...) ---
    for tag in soup.find_all(style=True):
        style = tag["style"]
        for match in re.findall(r'url\(["\']?(.*?)["\']?\)', style):
            if match.startswith("data:image/"):
                m = re.match(r"data:(image/[^;]+);base64,", match)
                if m:
                    results.append((match[:64] + "...", m.group(1)))
            else:
                results.append((match, "image/unknown"))

    return results if results else None


    # --- SVG (text-based, cheap validation) ---
    """ 
    ct = flow.response.headers.get("content-type", "").lower()
    if "svg" in ct or data.lstrip().startswith(b"<"):
        try:
            text = data.decode("utf-8", errors="ignore")
            if "<svg" in text[:1000]:
                return text, "image/svg+xml"
        except Exception:
            pass
 """
    logger.debug("No image format detected")
    return None

def is_video(flow):
    logger.debug("Checking if response is a video")
    content_type = flow.response.headers.get("content-type", "").lower()
    if content_type.startswith("video/"):
        logger.info(f"Blocking video by content-type: {content_type}")
        flow.response = http.Response.make(
            403,
            b"Video blocked",
            {"Content-Type": "text/plain"}
        )
        return
    
    url = flow.request.pretty_url.lower()
    VIDEO_EXTENSIONS = (
        ".mp4", ".webm", ".avi", ".mov",
        ".m3u8", ".mpd", ".ts", ".m4s"
    )

    if any(ext in url for ext in VIDEO_EXTENSIONS):
        logger.info(f"Blocking video by URL extension: {url}")
        flow.response = http.Response.make(
            403,
            b"Video blocked",
            {"Content-Type": "text/plain"}
        )
        return
    
    logger.debug("Response is not a video")


def process_http_response(flow: http.HTTPFlow):
    """
    Process HTTP response flow and filter images if needed.
    """
    url = flow.request.url
    referer_url = flow.request.headers.get("Referer")
    method = flow.request.method
    
    logger.info(f"Processing HTTP response - Method: {method}, URL: {url}")
    logger.debug(f"Response status: {flow.response.status_code}, Content-Type: {flow.response.headers.get('content-type')}, "
                 f"Content-Length: {len(flow.response.raw_content) if flow.response.raw_content else 0} bytes")

    extract_result = extract_image_content(flow)
    image_content, mime_type = extract_result if extract_result else (None, None)
    
    if image_content is not None:
        logger.info(f"Image detected in response - MIME: {mime_type}, Size: {len(image_content)} bytes")
        logger.debug(f"Processing image with status check - URL: {url}, Referer: {referer_url}")
        image_result, flow_response = get_image_with_status(image_data=image_content, image_url=url, referer_url=referer_url, image_mime_type=mime_type)
        logger.debug(f"Got image result, size: {len(image_result)} bytes")
        flow.response.raw_content = image_result
        if flow_response is not None:
            logger.debug("Updating flow response with new response object")
            flow.response = flow_response
        logger.info(f"Image processing complete for URL: {url}")
        return

    logger.debug(f"Response is not an image, skipping processing for URL: {url}")
    return
