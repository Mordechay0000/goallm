"""
HTML replacement pages for site-level policy: blocked and send-for-review.
- Button links to CRM account to add request (user must be logged in).
- Requests are submitted from within the user's account.
"""
import os
import html
from urllib.parse import quote

_default_crm_api = "http://127.0.0.1:8000"
_default_crm_frontend = "http://localhost:5173"
CRM_API_URL = (os.environ.get("CRM_API_URL") or _default_crm_api).rstrip("/")
# Frontend URL for login/requests links (default: 5173 in dev, same as API in production)
CRM_FRONTEND_URL = (os.environ.get("CRM_FRONTEND_URL") or _default_crm_frontend).rstrip("/")

def _crm_request_link(request_url: str, request_type: str) -> str:
    """Build CRM login URL with redirect to new support ticket (פנייה) with attached request (open/change)."""
    url_param = (request_url or "").strip()
    redirect_path = f"/support/new?attach={quote(request_type, safe='')}&url={quote(url_param, safe='')}"
    return f"{CRM_FRONTEND_URL}/login?redirect={quote(redirect_path, safe='')}"


def _crm_request_file_link(file_url: str, filename: str) -> str:
    """Build CRM login URL with redirect to new support ticket (פנייה) with attached file request."""
    file_url_param = (file_url or "").strip()
    filename_param = (filename or "").strip()
    redirect_path = f"/support/new?attach=file&file_url={quote(file_url_param, safe='')}&filename={quote(filename_param, safe='')}"
    return f"{CRM_FRONTEND_URL}/login?redirect={quote(redirect_path, safe='')}"

# Design language: ניקיון עסקי, טאצ' מודרני עדין (תואם ל-CRM)
# Primary #0D1A3B, Accent #2F6CFF, Border #E4E7EC, Text #1A1A1A, Shadow עדין
_COMMON_STYLES = """
* { box-sizing: border-box; }
body {
  font-family: "Heebo", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  margin: 0;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2.5rem 1.5rem;
  text-align: right;
  line-height: 1.6;
  color: #1A1A1A;
  -webkit-font-smoothing: antialiased;
}
.page-wrap {
  max-width: 520px;
  width: 100%;
  padding: 0;
}
.status-badge {
  display: inline-block;
  font-size: 0.8rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  padding: 0.35rem 0.9rem;
  border-radius: 20px;
  margin-bottom: 1rem;
  text-transform: uppercase;
  border: 1px solid #E4E7EC;
  box-shadow: 0 4px 18px rgba(0, 0, 0, 0.05);
}
.page-head { margin-bottom: 0.5rem; }
h1 {
  font-family: "Heebo", sans-serif;
  font-size: 2rem;
  font-weight: 700;
  margin: 0 0 1rem;
  line-height: 1.3;
  letter-spacing: -0.02em;
  color: #0D1A3B;
}
.lead {
  font-size: 1.1rem;
  margin: 0 0 2rem;
  color: #1A1A1A;
  opacity: 0.92;
  line-height: 1.55;
}
.details-head {
  font-size: 0.8rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  margin: 0 0 0.6rem;
  color: #0D1A3B;
  opacity: 0.85;
  text-transform: uppercase;
}
.detail {
  font-size: 0.95rem;
  margin: 0.4rem 0;
  padding: 0.5rem 0;
  border-bottom: 1px solid #E4E7EC;
  background: none;
}
.detail:last-of-type { border-bottom: none; }
.detail strong {
  font-weight: 600;
  display: inline-block;
  min-width: 4.5em;
  color: #0D1A3B;
}
.info-url { color: #1A1A1A; opacity: 0.85; }
.actions { margin-top: 2rem; }
.btn {
  display: inline-block;
  padding: 0.7rem 1.5rem;
  border-radius: 24px;
  font-size: 1rem;
  font-weight: 500;
  font-family: "Heebo", sans-serif;
  cursor: pointer;
  text-decoration: none;
  border: none;
  transition: background-color 0.2s ease, box-shadow 0.2s ease;
  box-shadow: 0 4px 18px rgba(0, 0, 0, 0.05);
}
.btn:hover { opacity: 0.95; box-shadow: 0 4px 18px rgba(47, 108, 255, 0.2); }
.btn:active { transform: none; }
.tag-chip {
  display: inline-block;
  padding: 0.2rem 0.55rem;
  border-radius: 16px;
  font-size: 0.88rem;
  margin: 0.15rem 0.15rem 0 0;
  border: 1px solid #E4E7EC;
  background: #F7F8FA;
  color: #0D1A3B;
}
textarea.readonly-debug {
  width: 100%; min-height: 80px; font-size: 0.75rem;
  border-radius: 20px; padding: 0.6rem; margin-top: 0.5rem;
  resize: vertical; border: 1px solid #E4E7EC;
  background: #FFFFFF;
  box-shadow: 0 4px 18px rgba(0, 0, 0, 0.05);
}
"""

def _svg_bg_uri(svg: str) -> str:
    """Encode SVG for use as CSS background-image data URI. Single quotes so style=\"...\" is valid."""
    return "url('data:image/svg+xml," + quote(svg, safe="") + "')"

# Heebo font – תואם לשפה העיצובית של ה-CRM
_FONT_LINK = '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Heebo:wght@400;500;700&display=swap" rel="stylesheet">'

# Overlay: מרכז בהיר לקריאות, שוליים נותנים לצבע המצב לבלוט
_BG_OVERLAY = "radial-gradient(ellipse 85% 75% at 50% 50%, rgba(255,255,255,0.94), transparent 65%), "

# מיפוי צבע לפי מצב (מזוהה במבט): אדום=חסום | כחול=הגדרות שלי | כתום=תוכן מסונן | צהוב/ענבר=ממתין לבדיקה
# חסום מדיניות (אין גישה): אדום/קורל רך
_BG_DANGER = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 600"><defs><linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" style="stop-color:#fef2f2"/><stop offset="50%" style="stop-color:#fee2e2"/><stop offset="100%" style="stop-color:#fecaca"/></linearGradient><pattern id="stripes" patternUnits="userSpaceOnUse" width="32" height="16"><path d="M0 0L16 16M16 0L32 16" stroke="#dc2626" stroke-width="1.5" opacity="0.15"/></pattern></defs><rect width="600" height="600" fill="url(#g)"/><rect width="600" height="600" fill="url(#stripes)"/></svg>"""
# חסום בהגדרות המשתמש: כחול רך – "ההגדרות שלי"
_BG_USER = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 600"><defs><linearGradient id="u" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" style="stop-color:#eff6ff"/><stop offset="50%" style="stop-color:#dbeafe"/><stop offset="100%" style="stop-color:#bfdbfe"/></linearGradient><pattern id="dots" patternUnits="userSpaceOnUse" width="40" height="40"><circle cx="20" cy="20" r="2" fill="#2F6CFF" opacity="0.2"/></pattern></defs><rect width="600" height="600" fill="url(#u)"/><rect width="600" height="600" fill="url(#dots)"/></svg>"""
# סינון תוכן (הדף נחסם): כתום/ענבר רך – "תוכן מסונן"
_BG_FILTER = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 600"><defs><linearGradient id="f" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" style="stop-color:#fff7ed"/><stop offset="50%" style="stop-color:#ffedd5"/><stop offset="100%" style="stop-color:#fed7aa"/></linearGradient><pattern id="lines" patternUnits="userSpaceOnUse" width="6" height="20"><line x1="0" y1="4" x2="6" y2="4" stroke="#ea580c" stroke-width="1.2" opacity="0.25"/><line x1="0" y1="12" x2="5" y2="12" stroke="#c2410c" stroke-width="0.8" opacity="0.2"/></pattern></defs><rect width="600" height="600" fill="url(#f)"/><rect width="600" height="600" fill="url(#lines)"/></svg>"""
# ממתין לבדיקה: צהוב/ענבר רך – "בהמתנה"
_BG_PENDING = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 600"><defs><linearGradient id="p" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" style="stop-color:#fffbeb"/><stop offset="50%" style="stop-color:#fef3c7"/><stop offset="100%" style="stop-color:#fde68a"/></linearGradient><pattern id="waves" patternUnits="userSpaceOnUse" width="60" height="30"><path d="M0 15 Q15 8 30 15 T60 15" stroke="#d97706" stroke-width="1" fill="none" opacity="0.25"/><path d="M0 22 Q15 15 30 22 T60 22" stroke="#b45309" stroke-width="0.8" fill="none" opacity="0.15"/></pattern></defs><rect width="600" height="600" fill="url(#p)"/><rect width="600" height="600" fill="url(#waves)"/></svg>"""


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
    block_reason_detail: str = "",
    block_debug_b64: str = "",
) -> str:
    tags_list = tags_list or []
    reason = (block_reason or "").strip().lower()
    is_user_settings = reason == "user_settings"
    is_text_filter = reason == "text_filter"
    reason_detail = (block_reason_detail or "").strip()
    debug_b64 = (block_debug_b64 or "").strip()

    if is_text_filter:
        full_request_url = request_url.replace("https://", "").replace("http://", "").strip() if request_url else ""
        full_url_display = html.escape(full_request_url, quote=False) if full_request_url else "—"
        reason_detail_html = ""
        if reason_detail:
            reason_detail_esc = html.escape(reason_detail, quote=False)
            reason_detail_html = f'<p class="detail"><strong>מידע נוסף לשירות הלקוחות:</strong> <code style="word-break:break-all;">{reason_detail_esc}</code></p>'
        debug_section = ""
        if debug_b64:
            debug_b64_esc = html.escape(debug_b64, quote=False)
            debug_section = f'<p class="detail" style="margin-top:1rem;"><strong>מידע נוסף לשירות הלקוחות:</strong></p><textarea readonly class="readonly-debug" id="debug-b64">{debug_b64_esc}</textarea>'
        return f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>הדף נחסם – תוכן לא מתאים</title>
    {_FONT_LINK}
    <style>{_COMMON_STYLES}</style>
</head>
<body style="background: {_BG_OVERLAY}{_svg_bg_uri(_BG_FILTER)} center/cover no-repeat; color: #1A1A1A;">
    <div class="page-wrap">
        <div class="page-head">
            <span class="status-badge" style="background: #ffedd5; color: #c2410c; border-color: #ea580c;">הדף נחסם</span>
        </div>
        <h1>התוכן בדף הזה לא מתאים</h1>
        <p class="lead">המערכת חסמה את הדף כי התוכן שבו לא עבר את הבדיקה (למשל מילים או תוכן שלא מותרים). האתר עצמו יכול להיות פתוח בדפים אחרים.</p>
        <p class="details-head">פרטים</p>
        <p class="detail info-url"><strong>כתובת הדף:</strong> {full_url_display}</p>
        {reason_detail_html}
        {debug_section}
    </div>
</body>
</html>"""

    # Blocked by policy or by user settings – תגית ורקע מסמנים מצב במבט
    if is_user_settings:
        badge_text = "חסום בהגדרות שלך"
        title_msg = "אתר זה חסום אצלך"
        body_msg = "בהגדרות שבחרת בחשבון, אתר זה מוגדר כחסום. אפשר לשנות את זה בהגדרות החשבון."
        badge_style = "background: #dbeafe; color: #1d4ed8; border-color: #2F6CFF;"
        body_color = "#1A1A1A"
        btn_style = "background: #2F6CFF; color: #fff;"
    else:
        badge_text = "האתר חסום"
        title_msg = "אין גישה לאתר הזה"
        body_msg = "האתר חסום במערכת. אם אתה חושב שצריך לפתוח אותו – אפשר לשלוח בקשה מהחשבון שלך."
        badge_style = "background: #fee2e2; color: #b91c1c; border-color: #dc2626;"
        body_color = "#1A1A1A"
        btn_style = "background: #2F6CFF; color: #fff;"
    full_request_url = request_url.replace("https://", "").replace("http://", "").strip() if request_url else ""
    prefilled_url = (rule_domain or "").strip() or full_request_url
    full_url_display = html.escape(full_request_url, quote=False) if full_request_url else "—"
    crm_link = _crm_request_link(prefilled_url or full_request_url, "change")
    crm_link_esc = html.escape(crm_link, quote=True)
    tags_html = "".join(f'<span class="tag-chip">{html.escape(t)}</span>' for t in tags_list) if tags_list else '<span style="opacity:0.6;">—</span>'
    actions_html = (
        f'<div class="actions"><a href="{crm_link_esc}" class="btn" style="{btn_style}">שלח בקשה לפתיחה</a></div>'
        if not is_user_settings
        else ""
    )
    return f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{html.escape(title_msg)}</title>
    {_FONT_LINK}
    <style>{_COMMON_STYLES}</style>
</head>
<body style="background: {_BG_OVERLAY}{_svg_bg_uri(_BG_USER if is_user_settings else _BG_DANGER)} center/cover no-repeat; color: {body_color};">
    <div class="page-wrap">
        <div class="page-head">
            <span class="status-badge" style="{badge_style}">{html.escape(badge_text)}</span>
        </div>
        <h1>{html.escape(title_msg)}</h1>
        <p class="lead">{html.escape(body_msg)}</p>
        <p class="details-head">פרטים</p>
        <p class="detail"><strong>אתר שחסום:</strong> {html.escape(rule_domain or "—")}{html.escape(rule_path or "")}</p>
        <p class="detail info-url"><strong>כתובת:</strong> {full_url_display}</p>
        <p class="detail"><strong>תגיות:</strong> {tags_html}</p>
        {actions_html}
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
    <title>האתר עדיין לא נבדק</title>
    {_FONT_LINK}
    <style>{_COMMON_STYLES}</style>
</head>
<body style="background: {_BG_OVERLAY}{_svg_bg_uri(_BG_PENDING)} center/cover no-repeat; color: #1A1A1A;">
    <div class="page-wrap">
        <div class="page-head">
            <span class="status-badge" style="background: #fef3c7; color: #b45309; border-color: #d97706;">האתר עדיין לא נבדק</span>
        </div>
        <h1>האתר עדיין לא נבדק</h1>
        <p class="lead">המערכת עדיין לא בדקה את האתר הזה. אפשר לשלוח בקשה לבדיקה – אחרי שאישרו, האתר ייפתח.</p>
        <p class="details-head">פרטים</p>
        <p class="detail info-url"><strong>כתובת:</strong> {full_url_display}</p>
        <div class="actions">
            <a href="{crm_link_esc}" class="btn" style="background: #2F6CFF; color: #fff;">שלח בקשה לבדיקה</a>
        </div>
    </div>
</body>
</html>"""


def _send_for_review_file_page_html(file_url: str = "", filename: str = "") -> str:
    """HTML page for file download: ask user to send for review with link to request-file (title: פתיחת קובץ + filename)."""
    file_url_esc = html.escape((file_url or "").strip(), quote=False) or "—"
    filename_display = html.escape((filename or "").strip(), quote=False) or "—"
    crm_link = _crm_request_file_link(file_url, filename)
    crm_link_esc = html.escape(crm_link, quote=True)
    return f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>פתיחת קובץ – {filename_display}</title>
    {_FONT_LINK}
    <style>{_COMMON_STYLES}</style>
</head>
<body style="background: {_BG_OVERLAY}{_svg_bg_uri(_BG_PENDING)} center/cover no-repeat; color: #1A1A1A;">
    <div class="page-wrap">
        <div class="page-head">
            <span class="status-badge" style="background: #fef3c7; color: #b45309; border-color: #d97706;">הורדת קובץ – נדרשת בדיקה</span>
        </div>
        <h1>פתיחת קובץ – {filename_display}</h1>
        <p class="lead">הורדת קבצים דורשת שליחה לבדיקה. לחץ על הכפתור למטה ומילוי הפרטים (כולל תיאור הקובץ: מה הוא מכיל, סוג, איך פותחים, מאיפה הורדת) – אחרי האישור ניתן יהיה לפתוח קבצים מסוג זה.</p>
        <p class="details-head">פרטים</p>
        <p class="detail info-url"><strong>קישור לקובץ:</strong> {file_url_esc}</p>
        <p class="detail"><strong>שם הקובץ:</strong> {filename_display}</p>
        <div class="actions">
            <a href="{crm_link_esc}" class="btn" style="background: #2F6CFF; color: #fff;">שלח לבדיקה</a>
        </div>
    </div>
</body>
</html>"""


def get_send_for_review_file_page_bytes(file_url: str = "", filename: str = "") -> bytes:
    """Return HTML bytes for file send-for-review page (title: פתיחת קובץ + filename)."""
    html_str = _send_for_review_file_page_html(file_url=file_url, filename=filename)
    return html_str.encode("utf-8")


def get_blocked_page_bytes(
    request_url: str = "",
    rule: dict = None,
    tags: list = None,
    block_reason: str = "",
    block_reason_detail: str = "",
    block_debug_b64: str = "",
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
        block_reason_detail=block_reason_detail or rule.get("block_reason_detail", ""),
        block_debug_b64=block_debug_b64 or rule.get("block_debug_b64", ""),
    )
    return html_str.encode("utf-8")


def get_send_for_review_page_bytes(request_url: str = "") -> bytes:
    html_str = _send_for_review_page_html(request_url=request_url)
    return html_str.encode("utf-8")
