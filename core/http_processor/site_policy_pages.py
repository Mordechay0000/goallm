"""
HTML replacement pages for site-level policy: blocked and send-for-review.
- Button links to CRM account to add request (user must be logged in).
- Requests are submitted from within the user's account.
"""
import os
import html
from urllib.parse import quote

_default_crm_api = "http://127.0.0.1:8000"
_default_crm_frontend = "http://127.0.0.1:5173"
CRM_API_URL = (os.environ.get("CRM_API_URL") or _default_crm_api).rstrip("/")
# Frontend URL for login/requests links (default: 5173 in dev, same as API in production)
CRM_FRONTEND_URL = (os.environ.get("CRM_FRONTEND_URL") or _default_crm_frontend).rstrip("/")

def _crm_request_link(request_url: str, request_type: str) -> str:
    """Build CRM login URL with redirect to requests page (prefilled)."""
    url_param = (request_url or "").strip()
    redirect_path = f"/requests?url={quote(url_param, safe='')}&request_type={request_type}"
    return f"{CRM_FRONTEND_URL}/login?redirect={quote(redirect_path, safe='')}"

_COMMON_STYLES = """
* { box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: #eee; margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 1rem; }
.card { background: rgba(255,255,255,0.08); border-radius: 16px; padding: 2.5rem; max-width: 520px; width: 100%; border: 1px solid rgba(255,255,255,0.12); text-align: right; }
h1 { font-size: 1.75rem; margin: 0 0 0.5rem; color: #fff; }
h2 { font-size: 1.1rem; margin: 1.25rem 0 0.5rem; color: #ccc; }
p { margin: 0; line-height: 1.6; color: #ccc; }
.rule { margin: 0.5rem 0; padding: 0.5rem; background: rgba(0,0,0,0.2); border-radius: 8px; font-size: 0.9rem; }
.form { margin-top: 1rem; text-align: right; }
.form label { display: block; margin: 0.5rem 0 0.2rem; color: #ccc; font-size: 0.9rem; }
.form input[type=text], .form select { width: 100%; padding: 0.5rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.3); background: rgba(0,0,0,0.2); color: #fff; font-size: 1rem; }
.form select option { background: #1a1a2e; color: #fff; }
.form .row { margin: 0.75rem 0; }
.form .checkbox { display: flex; align-items: center; gap: 0.5rem; margin: 0.75rem 0; }
.form .checkbox input { width: auto; }
.btn { display: inline-block; margin-top: 1rem; padding: 0.6rem 1.2rem; background: #4a90d9; color: #fff; border: none; border-radius: 8px; font-size: 1rem; cursor: pointer; text-decoration: none; }
.btn:hover { background: #357abd; }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-secondary { background: rgba(255,255,255,0.15); margin-left: 0.5rem; }
.btn-secondary:hover { background: rgba(255,255,255,0.25); }
.error { color: #f44336; font-size: 0.9rem; margin-top: 0.5rem; }
.success { color: #4caf50; font-size: 1rem; margin-top: 1rem; font-weight: 500; }
.tag-box { display: flex; flex-wrap: wrap; align-items: center; gap: 0.4rem; min-height: 42px; padding: 0.4rem; border: 1px solid rgba(255,255,255,0.3); border-radius: 8px; background: rgba(0,0,0,0.2); }
.tag-box:focus-within { border-color: #4a90d9; }
.tag-chip { display: inline-flex; align-items: center; gap: 0.25rem; padding: 0.2rem 0.5rem; background: rgba(74,144,217,0.4); border-radius: 6px; font-size: 0.9rem; }
.tag-chip .tag-remove { cursor: pointer; padding: 0 0.2rem; color: #ccc; font-size: 1.1rem; line-height: 1; }
.tag-chip .tag-remove:hover { color: #fff; }
.tag-box input { flex: 1; min-width: 120px; padding: 0.35rem 0.5rem; border: none; background: transparent; color: #fff; font-size: 1rem; outline: none; }
.tag-box-readonly { cursor: default; }
.tag-box-readonly .tag-chip { padding: 0.25rem 0.5rem; }
.form-section { display: none; }
.form-section.visible { display: block; }
.info-url { color: #aaa; font-size: 0.9rem; margin-top: 0.25rem; }
"""


def _url_to_domain_only(url: str) -> str:
    """Extract domain only (no path) from URL for form prefill. e.g. https://example.com/path -> example.com"""
    if not url or not url.strip():
        return ""
    u = url.strip()
    for prefix in ("https://", "http://"):
        if u.startswith(prefix):
            u = u[len(prefix):]
            break
    u = u.split("/")[0].lower().rstrip(".")
    return u


def _blocked_page_html(
    request_url: str = "",
    rule_domain: str = "",
    rule_path: str = "",
    rule_state: str = "block",
    rule_type: str = "*",
    tags_list: list = None,
    block_reason: str = "",
) -> str:
    tags_list = tags_list or []
    is_user_settings = (block_reason or "").strip().lower() == "user_settings"
    title_msg = "נחסם בגלל הגדרות משתמש" if is_user_settings else "האתר נחסם"
    body_msg = "הגישה לאתר זה חסומה בהתאם להגדרות הפרופיל שלך (האתר פתוח ברשימה הגלובלית)." if is_user_settings else "הגישה לאתר זה חסומה בהתאם להגדרות המדיניות."
    full_request_url = request_url.replace("https://", "").replace("http://", "").strip() if request_url else ""
    prefilled_url = (rule_domain or "").strip() or full_request_url
    full_url_display = html.escape(full_request_url, quote=False) if full_request_url else "—"
    crm_link = _crm_request_link(prefilled_url or full_request_url, "change")
    crm_link_esc = html.escape(crm_link, quote=True)
    return f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{html.escape(title_msg)}</title>
    <style>{_COMMON_STYLES}</style>
</head>
<body>
    <div class="card">
        <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">🚫</div>
        <h1>{html.escape(title_msg)}</h1>
        <p>{html.escape(body_msg)}</p>
        <p class="rule"><strong>כלל:</strong> {rule_domain or "—"}{rule_path or ""} (מצב: {rule_state or "block"})</p>
        <p class="rule info-url"><strong>הכתובת שניגש אליה:</strong> {full_url_display}</p>
        <div class="rule"><strong>תגיות:</strong>
        <span class="tag-box tag-box-readonly">{''.join('<span class="tag-chip">' + html.escape(t) + '</span>' for t in tags_list) if tags_list else '<span style="color:#888">—</span>'}</span>
        </div>

        <p style="margin-top: 1.5rem; color: #ccc;">לשליחת בקשה לשינוי – התחבר לחשבון וצור בקשה מתוך הממשק.</p>
        <a href="{crm_link_esc}" class="btn" style="{'display:none;' if is_user_settings else 'margin-top:1rem;'}">הוסף בקשה בחשבון שלי</a>
    </div>
</body>
</html>"""


def _send_for_review_page_html(request_url: str = "") -> str:
    full_request_url = request_url.replace("https://", "").replace("http://", "").strip() if request_url else ""
    prefilled_url = _url_to_domain_only(request_url) if request_url else full_request_url
    full_url_display = html.escape(full_request_url, quote=False) if full_request_url else "—"
    crm_link = _crm_request_link(prefilled_url, "open")
    crm_link_esc = html.escape(crm_link, quote=True)
    return f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>נא לשלוח לבדיקה</title>
    <style>{_COMMON_STYLES}</style>
</head>
<body>
    <div class="card">
        <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">⏳</div>
        <h1>נא לשלוח לבדיקה</h1>
        <p>עדיין לא הוגדר כלל לאתר זה. התחבר לחשבון וצור בקשה לפתיחה מתוך הממשק.</p>
        <p class="rule info-url"><strong>הכתובת שניגש אליה:</strong> {full_url_display}</p>

        <p style="margin-top: 1.5rem; color: #ccc;">לשליחת בקשה לפתיחת אתר – התחבר לחשבון וצור בקשה מתוך הממשק.</p>
        <a href="{crm_link_esc}" class="btn" style="margin-top:1rem;">הוסף בקשה בחשבון שלי</a>
    </div>
</body>
</html>"""


def get_blocked_page_bytes(
    request_url: str = "",
    rule: dict = None,
    tags: list = None,
    block_reason: str = "",
) -> bytes:
    rule = rule or {}
    tags_list = list(tags) if tags else (rule.get("tags") or [])
    if isinstance(tags_list, str):
        tags_list = [t.strip() for t in tags_list.split(",") if t.strip()]
    html_str = _blocked_page_html(
        request_url=request_url,
        rule_domain=rule.get("domain", ""),
        rule_path=rule.get("path", ""),
        rule_state=rule.get("state", "block"),
        rule_type=rule.get("type", "*"),
        tags_list=tags_list,
        block_reason=block_reason or rule.get("block_reason", ""),
    )
    return html_str.encode("utf-8")


def get_send_for_review_page_bytes(request_url: str = "") -> bytes:
    html_str = _send_for_review_page_html(request_url=request_url)
    return html_str.encode("utf-8")
