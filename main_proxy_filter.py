import base64
import threading
import requests
from mitmproxy import http

# תוכן פלייסהולדר – 1x1 פיקסל שקוף (פורמט GIF) בבסיס64
PLACEHOLDER_IMG_DATA = base64.b64decode("R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=")
# תוכן תמונת חסימה – (10x10 פיקסל אדום) בבסיס64
BLOCKED_IMG_DATA = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAIAAAACUFjqAAAAEklEQVR4nGP8z4APMOGVHbHSAEEs"
    "AROxCnMTAAAAAElFTkSuQmCC"
)

# זיכרון מטמון לשמירת תוכן תמונות שכבר הורדו, לפי Hash
images_cache = {}      # מיפוי: hash -> dict עם keys: content, content_type
url_to_hash = {}       # מיפוי: URL -> hash של תוכן התמונה

# הגדרת כתובת השרת (Flask) אליו נשלחות התמונות לבדיקה
FLASK_SERVER_URL = "http://localhost:5000/check_image"

class ImageFilterAddon:
    def __init__(self):
        """אתחול התוסף - ניתן להוסיף כאן הגדרות נוספות לפי הצורך."""
        pass

    def request(self, flow: http.HTTPFlow):
        """מיירט בקשות HTTP יוצאות."""
        # אם הבקשה היא לתמונה ויש לנו כבר תוצאה במטמון, נחזיר מהמקומי במקום לגשת לרשת
        if flow.request.headers.get("accept", "").startswith("image"):
            url = flow.request.url
            if url in url_to_hash:
                img_hash = url_to_hash[url]
                # אם התוכן קיים במטמון (אושר בעבר), נחזירו מייד ללקוח
                if img_hash in images_cache:
                    cached = images_cache[img_hash]
                    # יצירת תגובת HTTP עם התוכן מהמטמון
                    flow.response = http.Response.make(
                        200,  # קוד OK
                        cached["content"], 
                        {
                            "Content-Type": cached["content_type"],
                            "Cache-Control": "no-store"  # למנוע אגירת התשובה בצד הדפדפן
                        }
                    )
                    return  # סיום הטיפול בבקשה (לא פונה לשרת המקורי)
                # אם ה-URL ידוע אבל התוכן לא קיים במטמון, ייתכן שמדובר בתמונה חסומה.
                # במקרה זה נחזיר תמונת חסימה:
                flow.response = http.Response.make(
                    200,
                    BLOCKED_IMG_DATA,
                    {
                        "Content-Type": "image/png",
                        "Cache-Control": "no-store"
                    }
                )
                return

    def response(self, flow: http.HTTPFlow):
        """מיירט תגובות נכנסות מהשרת המקורי."""
        # אם התגובה היא דף HTML – נזריק את קוד ה-JS הדרוש לפני </body>
        content_type = flow.response.headers.get("Content-Type", "")
        if "text/html" in content_type:
            text = flow.response.text
            inject_script = (
                # טעינת ספריית Socket.IO מה-CDN
                '<script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>'
                '<script>'
                '  // התחברות ל-WebSocket של השרת (שינוי ה-URL לפי כתובת השרת בפועל)\n'
                '  const socket = io("http://localhost:5000");\n'
                '  const observedImages = new Set();\n'
                '  // פונקציה הסורקת ושולחת לשרת את כל התמונות בעמוד\n'
                '  function sendAllImages() {\n'
                '    document.querySelectorAll("img").forEach(img => {\n'
                '      const src = img.src;\n'
                '      if (src && !observedImages.has(src)) {\n'
                '        socket.emit("register_image", {url: src});\n'
                '        observedImages.add(src);\n'
                '      }\n'
                '    });\n'
                '  }\n'
                '  // עם פתיחת החיבור – שלח את כל התמונות הקיימות\n'
                '  socket.on("connect", sendAllImages);\n'
                '  // עקוב אחר שינויים ב-DOM כדי לשלוח תמונות חדשות שנוספו או השתנו\n'
                '  const observer = new MutationObserver(mutations => {\n'
                '    for (const mutation of mutations) {\n'
                '      if (mutation.type === "childList") {\n'
                '        mutation.addedNodes.forEach(node => {\n'
                '          if (node.tagName === "IMG" || (node.nodeType === 1 && node.querySelectorAll)) {\n'
                '            const imgs = node.tagName === "IMG" ? [node] : node.querySelectorAll("img");\n'
                '            imgs.forEach(img => {\n'
                '              const src = img.src;\n'
                '              if (src && !observedImages.has(src)) {\n'
                '                socket.emit("register_image", {url: src});\n'
                '                observedImages.add(src);\n'
                '              }\n'
                '            });\n'
                '          }\n'
                '        });\n'
                '      }\n'
                '      if (mutation.type === "attributes" && mutation.target.tagName === "IMG" && mutation.attributeName === "src") {\n'
                '        const img = mutation.target;\n'
                '        const src = img.src;\n'
                '        if (src && !observedImages.has(src)) {\n'
                '          socket.emit("register_image", {url: src});\n'
                '          observedImages.add(src);\n'
                '        }\n'
                '      }\n'
                '    }\n'
                '  });\n'
                '  observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["src"] });\n'
                '  // קבלת עדכון מצב תמונה מהשרת\n'
                '  socket.on("image_status", data => {\n'
                '    const imgUrl = data.url;\n'
                '    const status = data.status;\n'
                '    const imgs = document.querySelectorAll(`img[src="${imgUrl}"]`);\n'
                '    imgs.forEach(img => {\n'
                '      if (status === "approved") {\n'
                '        // טעינה מחדש של התמונה המקורית (הוספת פרמטר פיקטיבי כדי לעקוף cache)\n'
                '        const originalSrc = img.src;\n'
                '        img.src = originalSrc + (originalSrc.includes("?") ? "&" : "?") + "reload=" + Date.now();\n'
                '      } else if (status === "blocked") {\n'
                '        // החלפת ה-src לתמונת חסימה\n'
                '        img.src = "data:image/png;base64,' + base64.b64encode(BLOCKED_IMG_DATA).decode() + '";\n'
                '      }\n'
                '    });\n'
                '  });\n'
                '</script>'
            )
            # הוספת קוד ה-JS לפני הסגירה של תגית </body> (או בסוף המסמך אם לא נמצא)
            if "</body>" in text:
                text = text.replace("</body>", inject_script + "</body>")
            else:
                text += inject_script
            flow.response.text = text

        # אם זו תגובת תמונה (image/*)
        if flow.response.headers.get("Content-Type", "").startswith("image"):
            url = flow.request.url
            content_type = flow.response.headers.get("Content-Type")
            original_content = flow.response.content
            # חישוב Hash (לדוגמה MD5) של תוכן התמונה לזיהוי ייחודי
            import hashlib
            img_hash = hashlib.md5(original_content).hexdigest()
            # שמירת תוכן התמונה במטמון לפי ה-hash
            images_cache[img_hash] = {"content": original_content, "content_type": content_type}
            url_to_hash[url] = img_hash
            # החלפת התוכן בפלייסהולדר (תמונה ריקה/בסיסית)
            # עדכון כותרות Content-Type ו-Content-Length בהתאם לפלייסהולדר
            flow.response.content = PLACEHOLDER_IMG_DATA
            flow.response.headers["Content-Type"] = "image/gif"
            flow.response.headers["Content-Length"] = str(len(PLACEHOLDER_IMG_DATA))
            flow.response.headers["Cache-Control"] = "no-store"
            # ביטול כותרות קידוד אם קיימות (אין צורך ב-content-encoding עבור התמונה החדשה)
            if "Content-Encoding" in flow.response.headers:
                del flow.response.headers["Content-Encoding"]
            # שליחת בקשה לשרת Flask לבדיקת התמונה (א-סינכרוני באמצעות thread)
            def send_to_server(img_hash, url, content):
                try:
                    # שולח את ה-hash, ה-URL והתוכן המקורי (כקובץ) לשרת הבדיקה
                    files = {"image": ("image", content)}
                    data = {"hash": img_hash, "url": url}
                    requests.post(FLASK_SERVER_URL, files=files, data=data, timeout=5)
                except Exception as e:
                    # במקרה של שגיאה ניתן להדפיס ל-log של mitmproxy
                    # ctx.log.error(f"Error sending image to server: {e}")
                    pass
            # יצירת thread לשליחת התמונה לשרת מבלי לחסום את זרימת התגובה ללקוח
            threading.Thread(target=send_to_server, args=(img_hash, url, original_content)).start()

# יצירת מופע מהתוסף עבור mitmproxy
addons = [ImageFilterAddon()]
