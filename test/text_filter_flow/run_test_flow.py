#!/usr/bin/env python3
"""
בדיקת שלבי סינון המלל – בלי mitmproxy.
מריצים כל שלב ומדפיסים תוצאה / חריגה כדי לאתר היכן זה נכשל.

הרצה:
  cd /path/to/goallm
  python3 -m test.text_filter_flow.run_test_flow [TEST_URL]

אם לא מעבירים TEST_URL – משתמשים ב־http://127.0.0.1:9876/
"""
import gzip
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# טעינת text_filter בלי mitmproxy (בלי core.http_processor.__init__)
def _load_text_filter():
    base = ROOT / "core" / "filters" / "text"
    spec_c = importlib.util.spec_from_file_location("tfc", base / "text_filter_config.py")
    tfc = importlib.util.module_from_spec(spec_c)
    spec_c.loader.exec_module(tfc)
    sys.modules["core.filters.text.text_filter_config"] = tfc
    spec_t = importlib.util.spec_from_file_location("tf", base / "text_filter.py")
    tf = importlib.util.module_from_spec(spec_t)
    spec_t.loader.exec_module(tf)
    return tf


def step(name, fn):
    print(f"\n--- {name} ---")
    try:
        result = fn()
        print(f"OK: {result}")
        return result
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    test_url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:9876/"
    print(f"Test URL: {test_url}")

    # 1. Policy resolver
    def get_resolver():
        from core.policy.policy_loader import get_policy_resolver
        r = get_policy_resolver()
        return "resolver loaded"

    step("1. get_policy_resolver()", get_resolver)

    # 2. Resolve URL (html)
    def resolve():
        from core.policy.policy_loader import get_policy_resolver
        r = get_policy_resolver()
        rule = r.resolve(test_url, "html")
        if rule is None:
            return {"state": None, "text_filter_enabled": None, "note": "rule=None → דף יוצג כ־send-for-review (הוסף לרשימה הגלובלית)"}
        return {"state": rule.get("state"), "text_filter_enabled": rule.get("text_filter_enabled"), "domain": rule.get("domain")}

    r2 = step("2. resolver.resolve(url, 'html')", resolve)
    if r2 and r2.get("state") != "allow":
        print("  ⚠ אם state != allow – הסינון מלל לא יופעל (הדף יוצג כ־review/block). הוסף את הכתובת לרשימה הגלובלית עם allow.")

    # 3–5: Filter (טעינת text_filter בלי mitmproxy)
    sample_html = b"<!DOCTYPE html><html><body><p>Hello. I love ice cream.</p></body></html>"
    tf = _load_text_filter()

    def filter_plain():
        out, block, reason, debug_info = tf.filter_text_content(sample_html, url=test_url, content_type="text/html; charset=utf-8")
        return {"len_out": len(out), "block_page": block, "block_reason": reason, "preview": out[:80]}

    step("3. filter_text_content(plain HTML bytes)", filter_plain)

    def filter_gzip():
        gzip_bytes = gzip.compress(sample_html)
        out, block, reason, _ = tf.filter_text_content(gzip_bytes, url=test_url, content_type="text/html; charset=utf-8")
        return {"input_len": len(gzip_bytes), "output_len": len(out), "block_page": block, "block_reason": reason, "preview": out[:80], "is_garbage": b"<html>" not in out}

    step("4. filter_text_content(GZIP bytes – כמו raw_content)", filter_gzip)

    def filter_decompressed():
        out, block, reason, _ = tf.filter_text_content(sample_html, url=test_url, content_type="text/html; charset=utf-8")
        return {"len_out": len(out), "block_page": block, "block_reason": reason, "is_valid_html": b"<html>" in out and b"</body>" in out}

    step("5. filter_text_content(decompressed – כמו flow.response.content)", filter_decompressed)

    def decode_like_mitm():
        gzip_bytes = gzip.compress(sample_html)
        with gzip.GzipFile(fileobj=__import__("io").BytesIO(gzip_bytes), mode="rb") as f:
            decoded = f.read()
        return {"decoded_len": len(decoded), "equals_original": decoded == sample_html}

    step("6. gzip.decompress (כמו flow.response.content)", decode_like_mitm)

    print("\n--- סיום ---")
    print("• שלב 2 state=review → הוסף 127.0.0.1 (או הדומיין) לרשימה הגלובלית עם allow וסינון מלל מופעל.")
    print("• שלב 4 is_garbage=True → הבעיה ש־raw_content דחוס; בפרוקסי חייבים flow.response.content.")
    print("• שלב 5 is_valid_html=True → הסינון עובד; אם הדף עדיין לא נפתח – בדוק לוגים ב־.storage/app.log.")


if __name__ == "__main__":
    main()
