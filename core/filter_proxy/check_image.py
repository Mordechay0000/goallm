from client_llama import classify_image_with_llm
from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room
import hashlib
import base64


app = Flask(__name__)
# הפעלת SocketIO עם תמיכה ב-CORS לכל המקורות (כדי לאפשר התחברות מהדף המשורשר)
socketio = SocketIO(app, cors_allowed_origins="*")

# מבני נתונים לשמירת מצב הסינון
images_status = {}  # מיפוי: hash -> {"status": "pending/approved/blocked", "urls": [list of URLs]}
url_to_hash = {}    # מיפוי: URL -> hash (מאפשר למצוא hash לפי כתובת)
 
@app.route('/check_image', methods=['POST'])
def check_image():
    """נתיב לקבלת תמונה מה-proxy לצורך בדיקה (סינון)."""
    img_hash = request.form.get('hash')
    url = request.form.get('url')
    file = request.files.get('image')
    if not img_hash or not file:
        return "Bad Request", 400

    # ודא שקראת את תוכן הקובץ (לצורך חשיש עצמאי אם צריך או כדי לשלוח למערכת סינון אמיתית)
    content = file.read()
    # אימות/חישוב hash באופן זהה ל-proxy, במידה ורוצים לוודא עקביות (כאן MD5):
    calc_hash = hashlib.md5(content).hexdigest()
    if img_hash != calc_hash:
        img_hash = calc_hash  # השתמש ב-hash המחושב במקרה של אי-התאמה (ליתר ביטחון)

    # עדכון מבני הנתונים עם התמונה שהתקבלה
    if img_hash not in images_status:
        images_status[img_hash] = {"status": "pending", "urls": []}
    # הוספת ה-URL לרשימת ה-URLs המשויכים לתמונה זו (אם לא קיים כבר)
    if url not in images_status[img_hash]["urls"]:
        images_status[img_hash]["urls"].append(url)
    url_to_hash[url] = img_hash

    # אם התמונה במצב pending טרם החלה תהליך סינון – התחל אותו (הדמיה)
    if images_status[img_hash]["status"] == "pending":
        # סימולציית תהליך סינון שרץ ברקע (ללא חסימת הבקשה HTTP)
        def run_filter(image_hash, image_bytes):
            conditions = classify_image_with_llm(image_bytes)

            blocked = any(conditions.values())
            verdict = "blocked" if blocked else "approved"

            images_status[image_hash]["status"] = verdict
            images_status[image_hash]["conditions"] = conditions

            for url in images_status[image_hash]["urls"]:
                socketio.emit(
                    "image_status",
                    {"url": url, "status": verdict},
                    to=url
                )
            images_status[image_hash]["running"] = False



        if images_status[img_hash]["status"] == "pending" and not images_status[img_hash].get("running"):
            images_status[img_hash]["running"] = True
            socketio.start_background_task(run_filter, img_hash, content)

    else:
        # אם התמונה כבר לא במצב pending (אולי כבר סוננה בעבר), נשלח עדכון מיידי ללקוחות שמחכים
        verdict = images_status[img_hash]["status"]
        socketio.emit("image_status", {"url": url, "status": verdict}, to=url)
    return "OK", 200

@socketio.on('register_image')
def handle_register_image(data):
    """מטפל בהרשמה של לקוח (דפדפן) למעקב אחר תמונה מסוימת."""
    url = data.get("url")
    if not url:
        return
    # אפשר להציב את הלקוח בחדר ייחודי לפי כתובת התמונה, כדי שיוכל לקבל עדכונים ספציפיים
    join_room(url)
    if url in url_to_hash:
        # אם התמונה כבר מוכרת (כבר יש hash וחוותה סינון)
        img_hash = url_to_hash[url]
        status = images_status.get(img_hash, {}).get("status", None)
        if status and status != "pending":
            # שלח את הסטטוס הנוכחי באופן מיידי ללקוח זה
            emit("image_status", {"url": url, "status": status})
        # אם status הוא "pending", לא שולחים כלום עכשיו (הלקוח יקבל עדכון כשיושלם הסינון)
    else:
        # אם ה-URL עדיין לא הגיע מה-proxy (לא ידוע לנו hash עדיין):
        # נרשום את הלקוח בחדר ה-URL (כבר נעשה עם join_room), והוא יקבל עדכון כאשר התמונה תטופל.
        # כאן אין תגובה מיידית, כי ייתכן שהסינון עוד לא התחיל. 
        # כשהתמונה תגיע מ-mitmproxy, תהליך הסינון יופעל והעדכון יישלח.
        pass

if __name__ == "__main__":
    # הפעלת השרת Flask עם SocketIO (האזנה לכל הכתובות, פורט 5000)
    socketio.run(app, host="0.0.0.0", port=5000)
