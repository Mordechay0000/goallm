# mitmproxy addon code
import asyncio
import hashlib
from collections import defaultdict
from urllib.parse import urlparse
import os

import httpx
from mitmproxy import http
from mitmproxy import ctx

# --- הגדרות ---
FLASK_WS_URL = "wss://127.0.0.1:8081/"
FLASK_NOTIFY_URL = "https://127.0.0.1:8081/notify"

try:
    ADDON_DIR = os.path.dirname(__file__)
    JS_SCRIPT_PATH = os.path.join(ADDON_DIR, "static", "image-monitor.js")
except NameError:
    JS_SCRIPT_PATH = "image-monitor.js"
    print("[Warning] Could not determine addon directory automatically. Assuming image-monitor.js is in the current directory.")

# Database for image status (still based on hash for server-side logic)
IMAGE_STATUS_DB = defaultdict(lambda: "pending")

# Reusable async HTTP client
HTTP_CLIENT = httpx.AsyncClient(verify=False) # Note: verify=False is insecure for production

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


# --- !!! שינוי חתימת הפונקציה והודעת ה-POST !!! ---
async def analyze_image(image_hash, image_content, image_url):
    """
    בודק את התמונה (סימולציה), מעדכן סטטוס פנימי (מבוסס hash)
    ושולח עדכון ל-Flask עם ה-URL והסטטוס.
    """
    try:
        await asyncio.sleep(2) # סימולציית עיבוד
        is_safe = int(image_hash, 16) % 2 == 0 # לוגיקה לדוגמה (נשארת מבוססת hash)
        status = "allowed" if is_safe else "blocked"
        IMAGE_STATUS_DB[image_hash] = status # עדכון DB פנימי עדיין לפי hash

        # !!! שליחת URL ל-Flask !!!
        response = await HTTP_CLIENT.post(FLASK_NOTIFY_URL, json={
            "image_hash": image_hash, # אפשר להשאיר ללוגים בצד שרת Flask אם רוצים
            "image_url": image_url,   # <-- ה-URL שזוהה על ידי mitmproxy
            "status": status
        })
        response.raise_for_status() # בדוק שגיאות HTTP

        log_func = ctx.log.info if 'ctx' in globals() else print
        log_func(f"Notified Flask for URL {image_url} (hash {image_hash}): Status {status} -> Flask response {response.status_code}")

    except httpx.RequestError as exc:
        log_func = ctx.log.error if 'ctx' in globals() else print
        log_func(f"Error notifying Flask for URL {image_url} (hash {image_hash}): {exc}")
    except Exception as e:
        log_func = ctx.log.error if 'ctx' in globals() else print
        log_func(f"Unexpected error in analyze_image for URL {image_url} (hash {image_hash}): {e}")
        IMAGE_STATUS_DB[image_hash] = "error" # סמן כשגיאה (עדיין לפי hash)

# ----------------------------------------------------

class ImageHashFilter:
    async def response(self, flow: http.HTTPFlow):
        content_type = flow.response.headers.get("Content-Type", "")

        # --- חלק הזרקת HTML ---
        if "text/html" in content_type:
            # --- בניית קוד ההזרקה ---
            # שינוי קל: WS_URL מוגדר ישירות בתוך הסקריפט שמוזרק, ליתר ביטחון
            script_injection = f"""
            <script>
            const WS_URL_FROM_PROXY = "{FLASK_WS_URL}"; // הגדרת משתנה גלובלי
            </script>
            <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
            <script>
            // --- הדבקת התוכן של image-monitor.js ישירות כאן ---
            {IMAGE_MONITOR_JS_CONTENT}
            // --- סוף התוכן המוזרק ---
            </script>
            """
            html = flow.response.get_text()
            if "</body>" in html:
                html = html.replace("</body>", script_injection + "</body>", 1)
                flow.response.set_text(html)
            return # צא אחרי טיפול ב-HTML

        # --- חלק עיבוד התמונות ---
        if content_type.startswith("image/"):
            # --- שמירת URL ---
            image_url = flow.request.pretty_url # כתובת ה-URL המלאה של הבקשה

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
                "Access-Control-Allow-Origin": flow.response.headers.get("Access-Control-Allow-Origin", allowed_origin)
            }

            # אל תעבד מחדש פלייסהולדרים
            if flow.response.headers.get("X-Mitmproxy-Tag") == "image-placeholder":
                flow.response.headers["Access-Control-Allow-Origin"] = svg_headers["Access-Control-Allow-Origin"]
                return

            image_content = flow.response.content
            if not image_content: return

            # חישוב hash עדיין נדרש ללוגיקה בצד שרת
            image_hash = hashlib.sha256(image_content).hexdigest()
            status = IMAGE_STATUS_DB[image_hash] # בדיקת סטטוס עדיין לפי hash

            if status == "allowed":
                flow.response.headers["Access-Control-Allow-Origin"] = svg_headers["Access-Control-Allow-Origin"]
                return

            if status == "blocked":
                flow.response = http.Response.make(200,
                                                   b"<svg xmlns='http://www.w3.org/2000/svg' width='100' height='30'><text x='5' y='20' fill='red'>Blocked</text></svg>",
                                                   svg_headers)
                return

            if status == "pending":
                 # !!! שליחת URL ל-analyze_image !!!
                asyncio.get_running_loop().create_task(analyze_image(image_hash, image_content, image_url))
                flow.response = http.Response.make(200,
                                                   b"<svg xmlns='http://www.w3.org/2000/svg' width='100' height='30'><text x='5' y='20' fill='orange'>Checking...</text></svg>",
                                                   svg_headers)
                return

    def done(self):
        """נקראת כאשר ה-addon נסגר."""
        ctx.log.info("Addon shutting down, attempting to close HTTP client...")
        try:
            loop = asyncio.get_event_loop()
            if loop and loop.is_running():
                loop.create_task(self.close_http_client())
            else:
                ctx.log.warn("Event loop not running, attempting synchronous close (might fail).")
                asyncio.run(self.close_http_client())
        except Exception as e:
            ctx.log.error(f"Error during HTTP client cleanup scheduling: {e}")

    async def close_http_client(self):
        """סוגר את לקוח ה-HTTP האסינכרוני."""
        if HTTP_CLIENT and hasattr(HTTP_CLIENT, 'is_closed') and not HTTP_CLIENT.is_closed:
            ctx.log.info("Closing HTTPX client...")
            await HTTP_CLIENT.aclose()
            ctx.log.info("HTTPX client closed.")
        elif HTTP_CLIENT:
            ctx.log.info("HTTPX client already closed or in an unexpected state.")
        else:
            ctx.log.info("HTTPX client was not initialized.")


addons = [ImageHashFilter()]