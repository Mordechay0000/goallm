"""
שרת בדיקה לסינון מלל – מגיש דף HTML אחד.
מריצים את השרת, מוסיפים את הכתובת לרשימה הגלובלית (סינון מלל מופעל),
מגדירים פרוקסי ל־mitmproxy ופותחים את הכתובת בדפדפן.

הרצה:
  cd /path/to/goallm
  python3 -m test.text_filter_flow.server [PORT]
  # ברירת מחדל פורט 9876

בדפדפן (דרך הפרוקסי): http://127.0.0.1:9876/
"""
import gzip
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 9876

SAMPLE_HTML = """<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
  <meta charset="UTF-8">
  <title>בדיקת סינון מלל</title>
</head>
<body>
  <h1>דף בדיקה</h1>
  <p>זה דף תמים. אני אוהב גלידה.</p>
  <p>אם אתה רואה את הדף – הסינון עובד (או שאין התאמות).</p>
</body>
</html>
""".encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            accept_encoding = self.headers.get("Accept-Encoding", "") or ""
            use_gzip = "gzip" in accept_encoding.lower()
            body = gzip.compress(SAMPLE_HTML) if use_gzip else SAMPLE_HTML
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            if use_gzip:
                self.send_header("Content-Encoding", "gzip")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        print(f"[text_filter_test_server] {args[0]}")


def main():
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Text filter test server: http://127.0.0.1:{PORT}/")
    print("Add 127.0.0.1 to global whitelist, set proxy, then open the URL.")
    server.serve_forever()


if __name__ == "__main__":
    main()
