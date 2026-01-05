# mitmproxy addon code
import asyncio
import hashlib
from collections import defaultdict
from io import BytesIO
import time
from urllib.parse import urlparse
import os
import magic

from PIL import Image
import httpx
from mitmproxy import http
from mitmproxy import ctx

from core.image_filter.filter_image import FilterImage
from core.image_filter.image_queue import ImageProcessingQueue
from data import const
import sqlite3

# --- הגדרות ---
FLASK_NOTIFY_URL = "https://127.0.0.1:8081/notify"

IS_INJECT_REFRESH_IMAGE = False

try:
    ADDON_DIR = os.path.dirname(__file__)
    JS_SCRIPT_PATH = os.path.join(ADDON_DIR, "static", "image-monitor.js")
except NameError:
    JS_SCRIPT_PATH = "image-monitor.js"
    print(
        "[Warning] Could not determine addon directory automatically. Assuming image-monitor.js is in the current directory."
    )


conn = sqlite3.connect(".storage/image_status.db", check_same_thread=False)
conn.execute("PRAGMA journal_mode=WAL;")
conn.execute("PRAGMA synchronous=NORMAL;")


# Reusable async HTTP client
HTTP_CLIENT = httpx.AsyncClient(
    verify=False
)  # Note: verify=False is insecure for production

# --- קריאת תוכן קובץ ה-JS פעם אחת בהתחלה ---
IMAGE_MONITOR_JS_CONTENT = ""
try:
    with open(JS_SCRIPT_PATH, "r", encoding="utf-8") as f:
        IMAGE_MONITOR_JS_CONTENT = f.read()
    print(f"[Init] Successfully loaded script content from: {JS_SCRIPT_PATH}")
except FileNotFoundError:
    print(f"[Init Error] Script file not found at: {JS_SCRIPT_PATH}")
    IMAGE_MONITOR_JS_CONTENT = "console.error('Error: image-monitor.js content could not be loaded by mitmproxy addon.');"
except Exception as e:
    print(f"[Init Error] Failed to read script file {JS_SCRIPT_PATH}: {e}")
    IMAGE_MONITOR_JS_CONTENT = f"console.error('Error reading script file: {e}');"


def is_valid_image(data: bytes) -> bool:
    try:
        Image.open(BytesIO(data)).verify()
        return True
    except Exception:
        return False


def on_analyze_done(task_id, status: str, result: dict, image_details: dict, error: str | None):
    """Callback כאשר משימת עיבוד תמונה מסתיימת."""
    print(
        f"[Image Analysis Done] Hash: {image_details['image_hash']}, Status: {status}, Error: {error}, Result: {result}"
    )
    save_analysis_result(image_details['image_hash'], result, image_details.get('image_url'))

    # !!! שליחת URL ל-Flask !!!
    """
    if IS_INJECT_REFRESH_IMAGE:
        response = await HTTP_CLIENT.post(FLASK_NOTIFY_URL, json={
            "image_hash": image_hash, # אפשר להשאיר ללוגים בצד שרת Flask אם רוצים
            "image_url": image_url,   # <-- ה-URL שזוהה על ידי mitmproxy
            "status": status
        })
        response.raise_for_status() # בדוק שגיאות HTTP

        log_func = ctx.log.info if 'ctx' in globals() else print
        log_func(f"Notified Flask for URL {image_url} (hash {image_hash}): Status {status} -> Flask response {response.status_code}")
        """


image_filter = ImageProcessingQueue(
    filter_image=FilterImage(), on_task_done=on_analyze_done
)
TABLE_NAME = "image_status"


def get_image_status(image_hash: str):
    cur = conn.execute(f"SELECT status FROM {TABLE_NAME} WHERE image_hash = ?", (image_hash,))
    row = cur.fetchone()
    return row[0] if row else None


def mark_pending(image_hash: str, image_url: str | None = None):
    conn.execute(
        f"""
        INSERT INTO {TABLE_NAME} (
            image_hash,
            status,
            image_url,
            updated_at
        ) VALUES (?, 'pending', ?, ?)
        ON CONFLICT(image_hash) DO UPDATE SET
            status = 'pending',
            image_url = COALESCE(excluded.image_url, image_url),
            updated_at = excluded.updated_at
        """,
        (
            image_hash,
            image_url,
            int(time.time()),
        ),
    )
    conn.commit()



def save_analysis_result(image_hash: str, result: dict, image_url: str | None = None):
    blocked = any(v == "Yes" for v in result.values())

    conn.execute(
        f"""
        INSERT INTO {TABLE_NAME} (
            image_hash,
            image_url,
            status,
            female_visible_9_plus,
            female_3_to_9_partial_clothing,
            female_under_3_minimal_clothing,
            boys_teens_men_exposed_or_bathing,
            any_visible_body_exposure,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(image_hash) DO UPDATE SET
            image_url = excluded.image_url,
            status = excluded.status,
            female_visible_9_plus = excluded.female_visible_9_plus,
            female_3_to_9_partial_clothing = excluded.female_3_to_9_partial_clothing,
            female_under_3_minimal_clothing = excluded.female_under_3_minimal_clothing,
            boys_teens_men_exposed_or_bathing = excluded.boys_teens_men_exposed_or_bathing,
            any_visible_body_exposure = excluded.any_visible_body_exposure,
            updated_at = excluded.updated_at
        """,
        (
            image_hash,
            image_url,
            "blocked" if blocked else "allowed",
            result.get("female_visible_9_plus") == "Yes",
            result.get("female_3_to_9_partial_clothing") == "Yes",
            result.get("female_under_3_minimal_clothing") == "Yes",
            result.get("boys_teens_men_exposed_or_bathing") == "Yes",
            result.get("any_visible_body_exposure") == "Yes",
            int(time.time()),
        ),
    )
    conn.commit()



def detect_image_mime(data: bytes) -> str | None:
    """זיהוי סוג MIME של תמונה מבוסס על חתימה בינארית."""
    head = data[:512]
    low = head.lstrip().lower()
    if b"\x00" not in head and (
        low.startswith(b"<svg")
        or (low.startswith(b"<?xml") and b"<svg" in low)
        or b'xmlns="http://www.w3.org/2000/svg"' in low
    ):
        return "image/svg+xml"

    elif data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"

    elif data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"

    elif data.startswith(b"GIF8"):
        return "image/gif"

    elif data.startswith(b"BM"):
        return "image/bmp"

    elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"

    elif data.startswith(b"\x00\x00\x01\x00"):
        return "image/x-icon"

    elif data.startswith((b"II*\x00", b"MM\x00*")):
        return "image/tiff"

    # fallback – only if everything above failed
    elif data:
        try:
            return magic.from_buffer(data, mime=True)
        except Exception:
            return "application/octet-stream"

    return "application/octet-stream"


# --- !!! שינוי חתימת הפונקציה והודעת ה-POST !!! ---
async def analyze_image(image_hash, image_content, image_url):
    """פונקציה לאנליזת תמונה אסינכרונית."""

    mime_type = detect_image_mime(image_content)
    print(f"[analyze_image] Detected MIME type: {mime_type} for hash {image_hash} and URL {image_url}")
    image_filter.enqueue(
        image_content=image_content, image_details={'image_hash': image_hash, 'image_url': image_url}, image_mime_type=mime_type
    )


class ImageHashFilter:
    async def request(self, flow: http.HTTPFlow):
        if IS_INJECT_REFRESH_IMAGE:
            if flow.request.pretty_url.endswith("/__image_monitor.js"):
                flow.response = http.Response.make(
                    200,
                    IMAGE_MONITOR_JS_CONTENT.encode("utf-8"),
                    {"Content-Type": "application/javascript"},
                )
                return

    async def response(self, flow: http.HTTPFlow):
        content_type = flow.response.headers.get("Content-Type", "")

        if IS_INJECT_REFRESH_IMAGE:
            # --- חלק הזרקת HTML ---
            if "text/html" in content_type:
                # --- CSP override ---
                for h in list(flow.response.headers):
                    if h.lower().startswith("content-security-policy"):
                        del flow.response.headers[h]

                flow.response.headers["Content-Security-Policy"] = (
                    "default-src * data: blob:; "
                    "script-src * data: blob: 'unsafe-inline' 'unsafe-eval'; "
                    "style-src * 'unsafe-inline'; "
                    "img-src * data: blob:; "
                    "connect-src * data: blob: wss: https:;"
                )

                # --- בניית קוד ההזרקה ---
                # שינוי קל: WS_URL מוגדר ישירות בתוך הסקריפט שמוזרק, ליתר ביטחון
                script_injection = f"""
                <script src="/__image_monitor.js"></script>
                """
                html = flow.response.get_text()
                if "</body>" in html:
                    html = html.replace("</body>", script_injection + "</body>", 1)
                    flow.response.set_text(html)
            return  # צא אחרי טיפול ב-HTML

        # --- חלק עיבוד התמונות ---
        if content_type.startswith("image/"):
            # --- שמירת URL ---
            image_url = flow.request.pretty_url  # כתובת ה-URL המלאה של הבקשה

            referer_url = flow.request.headers.get("Referer")
            allowed_origin = "*"
            if referer_url:
                try:
                    parsed_uri = urlparse(referer_url)
                    origin = f"{parsed_uri.scheme}://{parsed_uri.netloc}"
                    allowed_origin = origin
                except Exception:
                    pass

            if "Access-Control-Allow-Origin" not in flow.response.headers:
                flow.response.headers["Access-Control-Allow-Origin"] = allowed_origin

            svg_headers = {
                "Content-Type": "image/svg+xml",
                "X-Mitmproxy-Tag": "image-placeholder",
                "Access-Control-Allow-Origin": flow.response.headers.get(
                    "Access-Control-Allow-Origin", allowed_origin
                ),
            }

            # אל תעבד מחדש פלייסהולדרים
            if flow.response.headers.get("X-Mitmproxy-Tag") == "image-placeholder":
                flow.response.headers["Access-Control-Allow-Origin"] = svg_headers[
                    "Access-Control-Allow-Origin"
                ]
                return

            image_content = flow.response.content
            if not image_content:
                return

            # חישוב hash נדרש ללוגיקה בצד שרת
            image_hash = hashlib.sha256(image_content).hexdigest()
            status = get_image_status(image_hash)

            print("image status " + status if status is not None else "None")
            if status == "allowed":
                flow.response.headers["Access-Control-Allow-Origin"] = svg_headers[
                    "Access-Control-Allow-Origin"
                ]
                return

            elif status == "blocked":
                flow.response = http.Response.make(
                    200, const.BLOCK_IMAGE.encode("utf-8"), svg_headers
                )
                return
            elif status == "pending":
                flow.response = http.Response.make(
                    200, const.CHECKING_IMAGE.encode("utf-8"), svg_headers
                )
                return
            elif status is None:
                # !!! שליחת URL ל-analyze_image !!!
                mark_pending(image_hash, image_url)
                asyncio.get_running_loop().create_task(
                    analyze_image(image_hash, image_content, image_url)
                )
                flow.response = http.Response.make(
                    200, const.CHECKING_IMAGE.encode("utf-8"), svg_headers
                )
                return
            else:
                pass
            return
        if content_type.startswith("video/"):
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
            flow.response = http.Response.make(
                403,
                b"Video blocked",
                {"Content-Type": "text/plain"}
            )
            return

    def done(self):
        """נקראת כאשר ה-addon נסגר."""
        ctx.log.info("Addon shutting down, attempting to close HTTP client...")
        try:
            loop = asyncio.get_event_loop()
            if loop and loop.is_running():
                loop.create_task(self.close_http_client())
            else:
                ctx.log.warn(
                    "Event loop not running, attempting synchronous close (might fail)."
                )
                asyncio.run(self.close_http_client())
        except Exception as e:
            ctx.log.error(f"Error during HTTP client cleanup scheduling: {e}")

    async def close_http_client(self):
        """סוגר את לקוח ה-HTTP האסינכרוני."""
        if (
            HTTP_CLIENT
            and hasattr(HTTP_CLIENT, "is_closed")
            and not HTTP_CLIENT.is_closed
        ):
            ctx.log.info("Closing HTTPX client...")
            await HTTP_CLIENT.aclose()
            ctx.log.info("HTTPX client closed.")
        elif HTTP_CLIENT:
            ctx.log.info("HTTPX client already closed or in an unexpected state.")
        else:
            ctx.log.info("HTTPX client was not initialized.")


addons = [ImageHashFilter()]
