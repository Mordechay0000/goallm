"""
HTML replacement pages for site-level policy: blocked and send-for-review.
- Button links to CRM account to add request (user must be logged in).
- Requests are submitted from within the user's account.
"""
import html
from urllib.parse import quote, urlparse, urlunparse, parse_qs, urlencode

from data.constants import CRM_API_URL, CRM_FRONTEND_URL
from data.landing_pages import (
    COMMON_STYLES,
    FONT_LINK,
    BG_OVERLAY,
    BG_DANGER,
    BG_USER,
    BG_FILTER,
    BG_PENDING,
)

def _crm_request_link(request_url_full: str, request_type: str, url_domain: str | None = None) -> str:
    """Build CRM login URL with redirect to new support ticket (פנייה) with attached request (open/change).
    request_url_full = full URL with path (כתובת מלאה). url_domain = domain only for the rule (כתובת אתר); if None, derived from request_url_full."""
    full_param = (request_url_full or "").strip()
    domain_param = (url_domain or _url_to_domain_only(request_url_full) or full_param).strip()
    redirect_path = f"/support/new?attach={quote(request_type, safe='')}&url={quote(domain_param, safe='')}&request_url={quote(full_param, safe='')}"
    return f"{CRM_FRONTEND_URL}/login?redirect={quote(redirect_path, safe='')}"


def _crm_request_file_link(file_url: str, filename: str) -> str:
    """Build CRM login URL with redirect to new support ticket (פנייה) with attached file request."""
    file_url_param = (file_url or "").strip()
    filename_param = (filename or "").strip()
    redirect_path = f"/support/new?attach=file&file_url={quote(file_url_param, safe='')}&filename={quote(filename_param, safe='')}"
    return f"{CRM_FRONTEND_URL}/login?redirect={quote(redirect_path, safe='')}"

def _svg_bg_uri(svg: str) -> str:
    """Encode SVG for use as CSS background-image data URI. Single quotes so style=\"...\" is valid."""
    return "url('data:image/svg+xml," + quote(svg, safe="") + "')"


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
    block_debug_readable: str = "",
) -> str:
    tags_list = tags_list or []
    reason = (block_reason or "").strip().lower()
    is_user_settings = reason == "user_settings"
    is_text_filter = reason == "text_filter"
    reason_detail = (block_reason_detail or "").strip()
    debug_b64 = (block_debug_b64 or "").strip()
    debug_readable = (block_debug_readable or "").strip()

    if is_text_filter:
        full_request_url = request_url.replace("https://", "").replace("http://", "").strip() if request_url else ""
        full_url_display = html.escape(full_request_url, quote=False) if full_request_url else "—"
        reason_detail_html = ""
        if reason_detail:
            reason_detail_esc = html.escape(reason_detail, quote=False)
            reason_detail_html = f'<p class="detail"><strong>סיבת חסימה:</strong> <code style="word-break:break-all;">{reason_detail_esc}</code></p>'
        debug_readable_section = ""
        if debug_readable:
            debug_readable_esc = html.escape(debug_readable, quote=False)
            debug_readable_section = f'<p class="detail" style="margin-top:0.75rem;"><strong>למה נחסם (דיבאג):</strong></p><pre class="detail" style="white-space:pre-wrap;word-break:break-word;background:#f5f5f5;padding:0.75rem;border-radius:8px;font-size:0.9rem;margin:0.25rem 0;">{debug_readable_esc}</pre>'
        debug_section = ""
        if debug_b64:
            debug_b64_esc = html.escape(debug_b64, quote=False)
            debug_section = f'<p class="detail" style="margin-top:1rem;"><strong>מידע מלא (base64 לשירות):</strong></p><textarea readonly class="readonly-debug" id="debug-b64">{debug_b64_esc}</textarea>'
        return f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>הדף נחסם – תוכן לא מתאים</title>
    {FONT_LINK}
    <style>{COMMON_STYLES}</style>
</head>
<body style="background: {BG_OVERLAY}{_svg_bg_uri(BG_FILTER)} center/cover no-repeat; color: #1A1A1A;">
    <div class="page-wrap">
        <div class="page-head">
            <span class="status-badge" style="background: #ffedd5; color: #c2410c; border-color: #ea580c;">הדף נחסם</span>
        </div>
        <h1>התוכן בדף הזה לא מתאים</h1>
        <p class="lead">המערכת חסמה את הדף כי התוכן שבו לא עבר את הבדיקה (למשל מילים או תוכן שלא מותרים). האתר עצמו יכול להיות פתוח בדפים אחרים.</p>
        <p class="details-head">פרטים</p>
        <p class="detail info-url"><strong>כתובת הדף:</strong> {full_url_display}</p>
        {reason_detail_html}
        {debug_readable_section}
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
    url_domain = (rule_domain or "").strip() or _url_to_domain_only(request_url or "")
    full_url_display = html.escape(full_request_url, quote=False) if full_request_url else "—"
    crm_link = _crm_request_link(full_request_url, "change", url_domain=url_domain or None)
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
    {FONT_LINK}
    <style>{COMMON_STYLES}</style>
</head>
<body style="background: {BG_OVERLAY}{_svg_bg_uri(BG_USER if is_user_settings else BG_DANGER)} center/cover no-repeat; color: {body_color};">
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
    full_url_display = html.escape(full_request_url, quote=False) if full_request_url else "—"
    # url = domain only (כתובת אתר), request_url = full (כתובת מלאה)
    crm_link = _crm_request_link(full_request_url, "open")
    crm_link_esc = html.escape(crm_link, quote=True)
    return f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>האתר עדיין לא נבדק</title>
    {FONT_LINK}
    <style>{COMMON_STYLES}</style>
</head>
<body style="background: {BG_OVERLAY}{_svg_bg_uri(BG_PENDING)} center/cover no-repeat; color: #1A1A1A;">
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
    {FONT_LINK}
    <style>{COMMON_STYLES}</style>
</head>
<body style="background: {BG_OVERLAY}{_svg_bg_uri(BG_PENDING)} center/cover no-repeat; color: #1A1A1A;">
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


def _pdf_continue_url(pdf_url: str) -> str:
    """Add goallm_pdf_confirm=1 to the PDF URL for the 'continue to PDF' button."""
    if not (pdf_url or "").strip():
        return "#"
    u = (pdf_url or "").strip()
    if "://" not in u:
        u = "https://" + u
    try:
        parsed = urlparse(u)
        qs = parse_qs(parsed.query, keep_blank_values=True)
        qs["goallm_pdf_confirm"] = ["1"]
        new_query = urlencode(qs, doseq=True)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
    except Exception:
        return pdf_url + ("&" if "?" in pdf_url else "?") + "goallm_pdf_confirm=1"


def _pdf_warning_page_html(pdf_url: str = "") -> str:
    """HTML page shown before opening a PDF: distortion warning + button to continue to PDF."""
    continue_url = _pdf_continue_url(pdf_url)
    continue_url_esc = html.escape(continue_url, quote=True)
    return f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>אזהרה – פתיחת קובץ PDF</title>
    {FONT_LINK}
    <style>{COMMON_STYLES}</style>
</head>
<body style="background: {BG_OVERLAY}{_svg_bg_uri(BG_PENDING)} center/cover no-repeat; color: #1A1A1A;">
    <div class="page-wrap">
        <div class="page-head">
            <span class="status-badge" style="background: #fef3c7; color: #b45309; border-color: #d97706;">אזהרה</span>
        </div>
        <h1>פתיחת קובץ PDF</h1>
        <p class="lead">יתכן שהקובץ ייצא משובש – הסינון שינה תמונות או טקסט בתוך הקובץ. אם אתה מעדיף להמשיך בכל זאת, לחץ על הכפתור למטה.</p>
        <div class="actions">
            <a href="{continue_url_esc}" class="btn" style="background: #2F6CFF; color: #fff;">המשך ל-PDF</a>
        </div>
    </div>
</body>
</html>"""


def get_pdf_warning_page_bytes(pdf_url: str = "") -> bytes:
    """Return HTML bytes for PDF distortion warning page (before opening PDF)."""
    html_str = _pdf_warning_page_html(pdf_url=pdf_url)
    return html_str.encode("utf-8")


def get_blocked_page_bytes(
    request_url: str = "",
    rule: dict = None,
    tags: list = None,
    block_reason: str = "",
    block_reason_detail: str = "",
    block_debug_b64: str = "",
    block_debug_readable: str = "",
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
        block_debug_readable=block_debug_readable or rule.get("block_debug_readable", ""),
    )
    return html_str.encode("utf-8")


def get_send_for_review_page_bytes(request_url: str = "") -> bytes:
    html_str = _send_for_review_page_html(request_url=request_url)
    return html_str.encode("utf-8")
