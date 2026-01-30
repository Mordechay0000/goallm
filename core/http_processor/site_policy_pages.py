"""
HTML replacement pages for site-level policy: blocked and send-for-review.
- Button to show the request form; form submits to CRM API (from-blocked-page).
- Tags UI: chips (comma/Enter add, backspace/× remove).
- On success: show "הבקשה נשלחה בהצלחה" and hide form.
"""
import os
import html
import json

_default_crm_api = "http://127.0.0.1:8000"
CRM_API_URL = (os.environ.get("CRM_API_URL") or _default_crm_api).rstrip("/")
# Must match CRM backend CRM_PROXY_SECRET. Default for local dev only.
CRM_PROXY_SECRET = os.environ.get("CRM_PROXY_SECRET", "dev-secret").strip()

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
    api_url: str = "",
    secret: str = "",
) -> str:
    tags_list = tags_list or []
    # Form field = rule that blocked (domain only). Info = full URL user tried to access.
    prefilled_url = (rule_domain or "").strip()
    full_request_url = request_url.replace("https://", "").replace("http://", "").strip() if request_url else ""
    include_sub = "1" if (rule_domain or "").startswith("*.") else "0"
    url_attr = html.escape(prefilled_url, quote=True)
    full_url_display = html.escape(full_request_url, quote=False) if full_request_url else "—"
    secret_esc = html.escape(secret, quote=True)
    api_esc = html.escape(api_url, quote=True)
    request_url_js = json.dumps(full_request_url).replace("</", "<\\/")
    initial_tags_js = json.dumps(tags_list).replace("</", "<\\/")
    return f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>האתר נחסם</title>
    <style>{_COMMON_STYLES}</style>
</head>
<body>
    <div class="card">
        <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">🚫</div>
        <h1>האתר נחסם</h1>
        <p>הגישה לאתר זה חסומה בהתאם להגדרות המדיניות.</p>
        <p class="rule"><strong>כלל:</strong> {rule_domain or "—"}{rule_path or ""} (מצב: {rule_state or "block"})</p>
        <p class="rule info-url"><strong>הכתובת שניגש אליה:</strong> {full_url_display}</p>
        <div class="rule"><strong>תגיות:</strong>
        <span class="tag-box tag-box-readonly">{''.join('<span class="tag-chip">' + html.escape(t) + '</span>' for t in tags_list) if tags_list else '<span style="color:#888">—</span>'}</span>
        </div>

        <p id="successMsg" class="success" style="display:none;">הבקשה נשלחה בהצלחה</p>
        <button type="button" class="btn" id="showFormBtn">בקשה לשינוי</button>

        <div id="formSection" class="form-section">
            <h2>בקשה לשינוי כלל</h2>
            <form id="f" class="form">
                <div class="row">
                    <label for="url">כתובת אתר (דומיין הכלל)</label>
                    <input type="text" id="url" value="{url_attr}" placeholder="example.com או *.example.com" required />
                </div>
                <div class="row">
                    <label for="action">פעולה</label>
                    <select id="action">
                        <option value="block" {"selected" if rule_state == "block" else ""}>חסום</option>
                        <option value="allow" {"selected" if rule_state == "allow" else ""}>אפשר</option>
                    </select>
                </div>
                <div class="row">
                    <label for="type">סוג</label>
                    <select id="type">
                        <option value="*" {"selected" if rule_type == "*" else ""}>הכל</option>
                        <option value="image" {"selected" if rule_type == "image" else ""}>תמונה</option>
                        <option value="video" {"selected" if rule_type == "video" else ""}>וידאו</option>
                    </select>
                </div>
                <div class="checkbox">
                    <input type="checkbox" id="subdomains" {"checked" if include_sub == "1" else ""} />
                    <label for="subdomains" style="display:inline;margin:0">כולל סאב-דומיינים</label>
                </div>
                <div class="row">
                    <label>תגיות</label>
                    <div class="tag-box" id="tagBox">
                        <span id="tagChips"></span>
                        <input type="text" id="tagInput" placeholder="הקלד תגית והקש פסיק או Enter" autocomplete="off" />
                    </div>
                </div>
                <p id="err" class="error" style="display:none"></p>
                <button type="submit" class="btn" id="submitBtn">שלח בקשה</button>
                <button type="button" class="btn btn-secondary" id="hideFormBtn">סגור</button>
            </form>
        </div>
    </div>
    <script>
    (function() {{
        var apiUrl = "{api_esc}";
        var secret = "{secret_esc}";
        var requestUrlFull = {request_url_js};
        var tags = {initial_tags_js};
        var tagChipsEl = document.getElementById("tagChips");
        var tagInputEl = document.getElementById("tagInput");
        var formSection = document.getElementById("formSection");
        var showFormBtn = document.getElementById("showFormBtn");
        var hideFormBtn = document.getElementById("hideFormBtn");
        var successMsg = document.getElementById("successMsg");

        function renderTags() {{
            tagChipsEl.innerHTML = tags.map(function(t, i) {{
                return '<span class="tag-chip">' + escapeHtml(t) + '<span class="tag-remove" data-i="' + i + '">×</span></span>';
            }}).join('');
            tagChipsEl.querySelectorAll(".tag-remove").forEach(function(el) {{
                el.addEventListener("click", function() {{
                    var i = parseInt(this.getAttribute("data-i"), 10);
                    tags.splice(i, 1);
                    renderTags();
                }});
            }});
        }}
        function escapeHtml(s) {{ var d = document.createElement("div"); d.textContent = s; return d.innerHTML; }}
        function addTag(v) {{
            v = v.trim();
            if (v && tags.indexOf(v) === -1) {{ tags.push(v); renderTags(); }}
        }}
        renderTags();
        tagInputEl.addEventListener("keydown", function(e) {{
            if (e.key === "," || e.key === "Enter") {{
                e.preventDefault();
                addTag(this.value);
                this.value = "";
            }} else if (e.key === "Backspace" && !this.value && tags.length > 0) {{
                tags.pop();
                renderTags();
            }}
        }});

        showFormBtn.addEventListener("click", function() {{ formSection.classList.add("visible"); showFormBtn.style.display = "none"; }});
        hideFormBtn.addEventListener("click", function() {{ formSection.classList.remove("visible"); showFormBtn.style.display = "inline-block"; }});

        document.getElementById("f").addEventListener("submit", function(e) {{
            e.preventDefault();
            var url = document.getElementById("url").value.trim();
            if (!url) {{ document.getElementById("err").textContent = "נא להזין כתובת"; document.getElementById("err").style.display = "block"; return; }}
            document.getElementById("err").style.display = "none";
            var submitBtn = document.getElementById("submitBtn");
            submitBtn.disabled = true;
            fetch(apiUrl + "/api/rule-requests/from-blocked-page", {{
                method: "POST",
                headers: {{ "Content-Type": "application/json" }},
                body: JSON.stringify({{
                    secret: secret,
                    request_type: "change",
                    url: url,
                    request_url: requestUrlFull || undefined,
                    action: document.getElementById("action").value,
                    type: document.getElementById("type").value,
                    include_subdomains: document.getElementById("subdomains").checked,
                    tags: tags
                }})
            }}).then(function(r) {{
                if (r.ok) {{
                    formSection.classList.remove("visible");
                    formSection.style.display = "none";
                    showFormBtn.style.display = "none";
                    successMsg.style.display = "block";
                }} else {{
                    return r.json().then(function(d) {{ throw new Error(typeof d.detail === "string" ? d.detail : (d.detail && String(d.detail)) || "שגיאה"); }}, function() {{ throw new Error("שגיאה " + r.status); }});
                }}
            }}).catch(function(err) {{
                document.getElementById("err").textContent = (err && err.message) ? err.message : "שגיאה בשליחה";
                document.getElementById("err").style.display = "block";
                submitBtn.disabled = false;
            }});
        }});
    }})();
    </script>
</body>
</html>"""


def _send_for_review_page_html(
    request_url: str = "",
    api_url: str = "",
    secret: str = "",
) -> str:
    # Form field = domain only (no path). Info = full URL user tried to access.
    full_request_url = request_url.replace("https://", "").replace("http://", "").strip() if request_url else ""
    prefilled_url = _url_to_domain_only(request_url) if request_url else ""
    url_attr = html.escape(prefilled_url, quote=True)
    full_url_display = html.escape(full_request_url, quote=False) if full_request_url else "—"
    request_url_js = json.dumps(full_request_url).replace("</", "<\\/")
    secret_esc = html.escape(secret, quote=True)
    api_esc = html.escape(api_url, quote=True)
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
        <p>עדיין לא הוגדר כלל לאתר זה. לחץ "בקשה לפתיחה" ומלא את הטופס.</p>
        <p class="rule info-url"><strong>הכתובת שניגש אליה:</strong> {full_url_display}</p>

        <p id="successMsg" class="success" style="display:none;">הבקשה נשלחה בהצלחה</p>
        <button type="button" class="btn" id="showFormBtn">בקשה לפתיחה</button>

        <div id="formSection" class="form-section">
            <h2>בקשה לפתיחת אתר</h2>
            <form id="f" class="form">
                <div class="row">
                    <label for="url">כתובת אתר (דומיין בלבד)</label>
                    <input type="text" id="url" value="{url_attr}" placeholder="example.com או *.example.com" required />
                </div>
                <div class="row">
                    <label for="action">פעולה</label>
                    <select id="action">
                        <option value="allow" selected>אפשר</option>
                        <option value="block">חסום</option>
                    </select>
                </div>
                <div class="row">
                    <label for="type">סוג</label>
                    <select id="type">
                        <option value="*" selected>הכל</option>
                        <option value="image">תמונה</option>
                        <option value="video">וידאו</option>
                    </select>
                </div>
                <div class="checkbox">
                    <input type="checkbox" id="subdomains" />
                    <label for="subdomains" style="display:inline;margin:0">כולל סאב-דומיינים</label>
                </div>
                <div class="row">
                    <label>תגיות</label>
                    <div class="tag-box" id="tagBox">
                        <span id="tagChips"></span>
                        <input type="text" id="tagInput" placeholder="הקלד תגית והקש פסיק או Enter" autocomplete="off" />
                    </div>
                </div>
                <p id="err" class="error" style="display:none"></p>
                <button type="submit" class="btn" id="submitBtn">שלח בקשה</button>
                <button type="button" class="btn btn-secondary" id="hideFormBtn">סגור</button>
            </form>
        </div>
    </div>
    <script>
    (function() {{
        var apiUrl = "{api_esc}";
        var secret = "{secret_esc}";
        var requestUrlFull = {request_url_js};
        var tags = [];
        var tagChipsEl = document.getElementById("tagChips");
        var tagInputEl = document.getElementById("tagInput");
        var formSection = document.getElementById("formSection");
        var showFormBtn = document.getElementById("showFormBtn");
        var hideFormBtn = document.getElementById("hideFormBtn");
        var successMsg = document.getElementById("successMsg");

        function renderTags() {{
            tagChipsEl.innerHTML = tags.map(function(t, i) {{
                return '<span class="tag-chip">' + escapeHtml(t) + '<span class="tag-remove" data-i="' + i + '">×</span></span>';
            }}).join('');
            tagChipsEl.querySelectorAll(".tag-remove").forEach(function(el) {{
                el.addEventListener("click", function() {{
                    var i = parseInt(this.getAttribute("data-i"), 10);
                    tags.splice(i, 1);
                    renderTags();
                }});
            }});
        }}
        function escapeHtml(s) {{ var d = document.createElement("div"); d.textContent = s; return d.innerHTML; }}
        function addTag(v) {{
            v = v.trim();
            if (v && tags.indexOf(v) === -1) {{ tags.push(v); renderTags(); }}
        }}
        renderTags();
        tagInputEl.addEventListener("keydown", function(e) {{
            if (e.key === "," || e.key === "Enter") {{
                e.preventDefault();
                addTag(this.value);
                this.value = "";
            }} else if (e.key === "Backspace" && !this.value && tags.length > 0) {{
                tags.pop();
                renderTags();
            }}
        }});

        showFormBtn.addEventListener("click", function() {{ formSection.classList.add("visible"); showFormBtn.style.display = "none"; }});
        hideFormBtn.addEventListener("click", function() {{ formSection.classList.remove("visible"); showFormBtn.style.display = "inline-block"; }});

        document.getElementById("f").addEventListener("submit", function(e) {{
            e.preventDefault();
            var url = document.getElementById("url").value.trim();
            if (!url) {{ document.getElementById("err").textContent = "נא להזין כתובת"; document.getElementById("err").style.display = "block"; return; }}
            document.getElementById("err").style.display = "none";
            var submitBtn = document.getElementById("submitBtn");
            submitBtn.disabled = true;
            fetch(apiUrl + "/api/rule-requests/from-blocked-page", {{
                method: "POST",
                headers: {{ "Content-Type": "application/json" }},
                body: JSON.stringify({{
                    secret: secret,
                    request_type: "open",
                    url: url,
                    request_url: requestUrlFull || undefined,
                    action: document.getElementById("action").value,
                    type: document.getElementById("type").value,
                    include_subdomains: document.getElementById("subdomains").checked,
                    tags: tags
                }})
            }}).then(function(r) {{
                if (r.ok) {{
                    formSection.classList.remove("visible");
                    formSection.style.display = "none";
                    showFormBtn.style.display = "none";
                    successMsg.style.display = "block";
                }} else {{
                    return r.json().then(function(d) {{ throw new Error(d.detail || "שגיאה"); }});
                }}
            }}).catch(function(err) {{
                document.getElementById("err").textContent = (err && err.message) ? err.message : "שגיאה בשליחה";
                document.getElementById("err").style.display = "block";
                submitBtn.disabled = false;
            }});
        }});
    }})();
    </script>
</body>
</html>"""


def get_blocked_page_bytes(
    request_url: str = "",
    rule: dict = None,
    tags: list = None,
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
        api_url=CRM_API_URL,
        secret=CRM_PROXY_SECRET,
    )
    return html_str.encode("utf-8")


def get_send_for_review_page_bytes(request_url: str = "") -> bytes:
    html_str = _send_for_review_page_html(
        request_url=request_url,
        api_url=CRM_API_URL,
        secret=CRM_PROXY_SECRET,
    )
    return html_str.encode("utf-8")
