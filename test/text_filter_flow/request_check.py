#!/usr/bin/env python3
"""
בדיקת בקשה אמיתית – פותח URL (דרך פרוקסי או ישיר), מריץ policy + text filter ומדפיס אבחון.

מטרה: לאתר למה סינון המלל "עדיין לא עובד" – לראות מה ה־resolver מחזיר, מה התגובה מהשרת/פרוקסי,
ומה הסינון היה עושה על התוכן.

שימוש:
  # רק אבחון policy + סינון (בלי לפתוח רשת)
  python3 -m test.text_filter_flow.request_check http://127.0.0.1:9876/

  # בקשת HTTP ישירה (בלי פרוקסי)
  python3 -m test.text_filter_flow.request_check --fetch http://127.0.0.1:9876/

  # בקשת HTTP דרך פרוקסי (כמו בדפדפן)
  HTTP_PROXY=http://127.0.0.1:8080 python3 -m test.text_filter_flow.request_check --fetch http://127.0.0.1:9876/

  # פרוקסי מותאם
  python3 -m test.text_filter_flow.request_check --fetch --proxy http://127.0.0.1:8080 http://example.com/
"""
import gzip
import io
import os
import sys
import importlib.util
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_text_filter():
    """Load text_filter without pulling in mitmproxy (avoid core.http_processor.__init__)."""
    base = ROOT / "core" / "filters" / "text"
    spec_c = importlib.util.spec_from_file_location("tfc", base / "text_filter_config.py")
    tfc = importlib.util.module_from_spec(spec_c)
    spec_c.loader.exec_module(tfc)
    sys.modules["core.filters.text.text_filter_config"] = tfc
    spec_t = importlib.util.spec_from_file_location("tf", base / "text_filter.py")
    tf = importlib.util.module_from_spec(spec_t)
    spec_t.loader.exec_module(tf)
    return tf


def _rule_summary(rule):
    if rule is None:
        return None
    return {
        "state": rule.get("state"),
        "text_filter_enabled": rule.get("text_filter_enabled"),
        "domain": rule.get("domain"),
        "block_reason": rule.get("block_reason"),
    }


def main():
    args = sys.argv[1:]
    do_fetch = "--fetch" in args
    if do_fetch:
        args = [a for a in args if a != "--fetch"]
    proxy = None
    for i, a in enumerate(args):
        if a == "--proxy" and i + 1 < len(args):
            proxy = args[i + 1]
            args = args[:i] + args[i + 2 :]
            break
    url = (args[0] if args else "http://127.0.0.1:9876/").strip()

    print("=" * 60)
    print("בדיקת בקשה – סינון מלל (Text Filter)")
    print("=" * 60)
    print("URL:", url)
    print("בקשת HTTP (--fetch):", do_fetch)
    if proxy:
        print("פרוקסי:", proxy)
    elif do_fetch and os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY"):
        print("פרוקסי (מהסביבה):", os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY"))
    print()

    # ---- 1. Policy resolver ----
    print("--- 1. Policy (resolver.resolve(url, 'html')) ---")
    try:
        from core.policy.policy_loader import get_policy_resolver

        resolver = get_policy_resolver()
        rule = resolver.resolve(url, "html")
        summary = _rule_summary(rule)
        print("תוצאה:", summary)
        if rule is None:
            print("  → אין כלל: בהתאם ל־default_mode יוצג review או allow.")
        elif rule.get("state") == "review":
            print("  → הדף יוצג כ־send-for-review (לא ברשימה הגלובלית או לא allow).")
            print("  → סינון מלל לא רץ – הוסף את האתר לרשימה הגלובלית עם allow וסינון מלל מופעל.")
        elif rule.get("state") == "block":
            print("  → הדף ייחסם (policy block). סינון מלל לא רץ.")
        elif rule.get("state") == "allow":
            tf = rule.get("text_filter_enabled", True)
            print("  → הדף מורשה (allow). סינון מלל:", "מופעל" if tf else "כבוי")
        print()
    except Exception as e:
        print("שגיאה:", type(e).__name__, e)
        import traceback
        traceback.print_exc()
        print()
        rule = None

    # ---- 2. Fetch (optional) ----
    body_bytes = None
    content_type = ""
    if do_fetch:
        print("--- 2. בקשת HTTP (GET) ---")
        req = Request(url, headers={"User-Agent": "TextFilterRequestCheck/1.0", "Accept-Encoding": "gzip"})
        try:
            if proxy:
                from urllib.request import ProxyHandler, build_opener
                opener = build_opener(ProxyHandler({"http": proxy, "https": proxy}))
                resp = opener.open(req, timeout=10)
            else:
                resp = urlopen(req, timeout=10)
            content_type = resp.headers.get("Content-Type") or ""
            raw = resp.read()
            # Decompress like mitmproxy flow.response.content
            ce = (resp.headers.get("Content-Encoding") or "").strip().lower()
            if ce == "gzip":
                body_bytes = gzip.GzipFile(fileobj=io.BytesIO(raw), mode="rb").read()
                print("Content-Encoding: gzip → פוענח, גודל גוף:", len(body_bytes))
            else:
                body_bytes = raw
                print("גודל גוף:", len(body_bytes))
            print("Content-Type:", content_type)
            print("תצוגה (100 תווים ראשונים):", repr(body_bytes[:100]))
            print()
        except (URLError, HTTPError, OSError) as e:
            print("שגיאה בבקשה:", type(e).__name__, e)
            print()
        except Exception as e:
            print("שגיאה:", type(e).__name__, e)
            import traceback
            traceback.print_exc()
            print()

    # ---- 3. Text filter on body ----
    if body_bytes is None and rule and rule.get("state") == "allow":
        # No fetch: use sample HTML for filter test
        body_bytes = b"<!DOCTYPE html><html><body><p>Hello. Test.</p></body></html>"
        content_type = "text/html; charset=utf-8"
        print("--- 2. (ללא fetch) שימוש ב־HTML לדוגמה ---")
        print()

    if body_bytes is not None:
        print("--- 3. סינון מלל (filter_text_content) ---")
        try:
            tf_module = _load_text_filter()
            filter_text_content = tf_module.filter_text_content
            text_filter_on = rule and rule.get("text_filter_enabled", True) if rule else True
            filtered, block_page, block_reason, debug_info = filter_text_content(
                body_bytes,
                url=url,
                content_type=content_type,
                text_filter_enabled=text_filter_on,
                rule_context=rule,
            )
            print("block_page:", block_page)
            if block_reason:
                print("גורם לחסימה (לדיבוג):", block_reason)
            if block_page and debug_info:
                import json
                print("דיבוג מלא:", json.dumps(debug_info, ensure_ascii=False, indent=2))
            print("אורך לפני:", len(body_bytes), "אחרי:", len(filtered))
            print("תצוגה (100 תווים):", repr(filtered[:100]))
            if block_page:
                print("  → הסינון היה חוסם את הדף (text_filter block).")
            elif filtered != body_bytes:
                print("  → הסינון החליף תוכן (לא חסימה).")
            else:
                print("  → אין התאמות בסינון.")
            print()
        except Exception as e:
            print("שגיאה:", type(e).__name__, e)
            import traceback
            traceback.print_exc()
            print()

    # ---- Summary ----
    print("--- סיכום ---")
    if rule and rule.get("state") != "allow":
        print("• אם הדף לא נפתח / לא מסתנן: וודא שהאתר ברשימה הגלובלית עם state=allow וסינון מלל מופעל.")
    if do_fetch and body_bytes is not None:
        try:
            body_preview = body_bytes[:2000].decode("utf-8", errors="replace")
        except Exception:
            body_preview = ""
        if "send-for-review" in body_preview or "לבדיקה" in body_preview:
            print("• התגובה נראית כמו דף send-for-review – הפרוקסי החזיר review (אין allow ל־URL).")
        if "נחסם" in body_preview or "blocked" in body_preview.lower():
            print("• התגובה נראית כמו דף חסימה – policy או text filter חסמו.")
    print("• להפעלת פרוקסי: mitmdump -s path/to/addon.py ואז בדפדפן Proxy=127.0.0.1:8080.")
    print("• לוגים: .storage/app.log (אם ה־addon כותב לשם).")


if __name__ == "__main__":
    main()
