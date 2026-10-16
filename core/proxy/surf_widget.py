"""
Surf widget: inject a collapsible sidebar into every allowed HTML page.
- Small tab on the left edge opens a panel with:
  - "דיווח" = link to request block (CRM request-change with action=block)
  - For admin (from the core DB is_admin flag): quick allow/block rule via a CRM page.
No secret/token is placed in the page: anything injected into a third-party page can be read by that
page's own scripts (ads, analytics). Admin actions are links to a CRM page that uses the admin's normal
login and asks for an explicit confirmation click.
"""
import html
import json
import logging
import re
from urllib.parse import quote, urlparse
from typing import Optional

from core.flow.site_policy_pages import CRM_API_URL, CRM_FRONTEND_URL
from core.policy.policy_cache import get_user_is_admin

logger = logging.getLogger(__name__)


def get_surf_user_is_admin(user_id: Optional[int]) -> bool:
    """True if user_id is an admin. Read from the core DB (synced by the CRM) – no HTTP call on the hot path."""
    if user_id is None:
        return False
    try:
        return get_user_is_admin(user_id)
    except Exception as e:
        logger.warning("surf_widget: is_admin lookup failed for user_id=%s: %s", user_id, e)
        return False


def _url_to_domain_path(url: str) -> tuple[str, str]:
    """Extract exact domain and path from URL (no subdomains in pattern). Normalizes www. -> no www."""
    u = (url or "").strip()
    if not u or "://" not in u:
        return "", "/"
    try:
        p = urlparse(u)
        domain = (p.hostname or "").lower().rstrip(".")
        if domain.startswith("www."):
            domain = domain[4:]
        path = (p.path or "").strip() or "/"
        path = "/" + path.lstrip("/") if path != "/" else "/"
        return domain, path
    except Exception:
        return "", "/"

def _request_change_link(request_url: str, action: str = "block") -> str:
    """CRM link to request-change page with URL and action prefilled."""
    url_param = (request_url or "").strip()
    if not url_param:
        return f"{CRM_FRONTEND_URL}/request-change"
    # Strip protocol for display; keep full URL for request_url (query must be URL-encoded)
    domain_part = url_param.replace("https://", "").replace("http://", "").split("/")[0]
    return f"{CRM_FRONTEND_URL}/request-change?url={quote(domain_part, safe='')}&request_url={quote(url_param, safe='')}&action={action}"


def _rule_display(rule: Optional[dict]) -> str:
    """Human-readable rule summary for display in widget."""
    if not rule:
        return "אין כלל (האתר פתוח – רשימה שחורה)"
    domain = (rule.get("domain") or rule.get("domain_pattern") or "").strip()
    path = (rule.get("path") or rule.get("path_pattern") or "").strip()
    if path and path != "/":
        return html.escape(f"{domain}{path}")
    return html.escape(domain or "—")


def inject_surf_widget(
    html_body: bytes,
    current_url: str,
    user_id: Optional[int],
    rule: Optional[dict],
    encoding: str = "utf-8",
    is_admin: bool = False,
    inject_video: bool = True,
) -> bytes:
    """
    Inject the surf widget (tab + panel) and config script before </body>.
    Only injects when user_id is set (bound connection). Preserves encoding.
    - is_admin=False: only "דיווח" (report) link.
    - is_admin=True: full panel with admin quick-rule; "החל" opens a new page that applies and shows summary.
    - inject_video=False: do not inject the video "שלח לבדיקה" buttons (per-rule video_filter_enabled).
    """
    if user_id is None:
        logger.debug("surf_widget: skip inject (user_id is None) url=%s", (current_url or "")[:80])
        return html_body

    try:
        text = html_body.decode(encoding, errors="replace")
    except Exception as e:
        logger.warning("surf_widget: decode failed url=%s err=%s", (current_url or "")[:80], e)
        return html_body

    crm_api = json.dumps(CRM_API_URL)
    crm_frontend = json.dumps(CRM_FRONTEND_URL)
    current_url_esc = json.dumps(current_url)
    rule_json = json.dumps(rule, ensure_ascii=False) if rule else "null"
    rule_domain_js = json.dumps((rule.get("domain") or rule.get("domain_pattern") or "").strip()) if rule else '""'
    rule_path_js = json.dumps((rule.get("path") or rule.get("path_pattern") or "/").strip() or "/") if rule else '"/"'
    request_change_url = _request_change_link(current_url, "block")
    request_change_url_attr = request_change_url.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")
    rule_display = _rule_display(rule)
    current_domain, current_path = _url_to_domain_path(current_url)
    current_domain_js = json.dumps(current_domain)
    current_path_js = json.dumps(current_path)
    # "החל" opens a CRM page (admin login + confirmation click). No token in the URL or the page.
    surf_rule_apply_base = f"{CRM_FRONTEND_URL.rstrip('/')}/admin/surf-quick-rule?source=surf"
    surf_rule_apply_base_js = json.dumps(surf_rule_apply_base)

    logger.info(
        "surf_widget: injecting url=%s user_id=%s is_admin=%s mode=%s",
        (current_url or "")[:80],
        user_id,
        is_admin,
        "full" if is_admin else "minimal",
    )
    if not is_admin:
        # Minimal widget: report only (no admin panel, no fetch).
        widget_html = f"""<script>
(function(){{
  var root = document.createElement("div");
  root.id = "goallm-surf-root";
  if (document.body) document.body.appendChild(root);
  else if (document.documentElement) document.documentElement.appendChild(root);
  try {{
  var config = {{ requestChangeUrlAttr: {json.dumps(request_change_url_attr)}, crmFrontend: {crm_frontend} }};
  if (config.crmFrontend) try {{ window.__goallm_crm_frontend = config.crmFrontend; }} catch (e) {{}}
  var open = false;
  root.innerHTML = '<div id="goallm-surf-wrap" style="position:fixed;left:0;top:50%;transform:translateY(-50%);width:' + (open ? '312px' : '32px') + ';z-index:2147483646;font-family:system-ui,-apple-system,sans-serif;font-size:14px;direction:rtl;">' +
    '<div id="goallm-surf-tab" style="position:absolute;left:0;top:50%;transform:translateY(-50%);width:32px;height:64px;background:#0D1A3B;color:#fff;border-radius:0 8px 8px 0;display:flex;align-items:center;justify-content:center;cursor:pointer;box-shadow:2px 0 8px rgba(0,0,0,0.2);user-select:none;" title="סרגל דיווח">' + (open ? "&#xAB;" : "&#xBB;") + '</div>' +
    '<div id="goallm-surf-panel" style="display:' + (open ? 'block' : 'none') + ';position:absolute;left:32px;top:0;width:280px;max-width:calc(90vw - 32px);background:#fff;border:1px solid #E4E7EC;border-right:none;border-radius:12px 0 0 12px;box-shadow:-4px 0 20px rgba(0,0,0,0.08);padding:16px;overflow:auto;max-height:80vh;">' +
    '<div style="font-weight:700;color:#0D1A3B;margin-bottom:12px;">סרגל דיווח</div>' +
    '<a href="' + config.requestChangeUrlAttr + '" target="_blank" rel="noopener" style="display:block;width:100%;padding:10px 14px;background:#2F6CFF;color:#fff;text-align:center;border-radius:8px;text-decoration:none;font-weight:500;box-sizing:border-box;">דיווח – בקש לחסום את האתר</a>' +
    '</div></div>';
  var wrap = document.getElementById("goallm-surf-wrap");
  var tab = document.getElementById("goallm-surf-tab");
  var panel = document.getElementById("goallm-surf-panel");
  if (tab) tab.onclick = function() {{ open = !open; if (wrap) wrap.style.width = open ? "312px" : "32px"; if (panel) panel.style.display = open ? "block" : "none"; tab.innerHTML = open ? "&#xAB;" : "&#xBB;"; }};
  }} catch (e) {{
  var errMsg = (e && e.message) ? String(e.message).replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;") : "שגיאה";
  root.innerHTML = '<div style="position:fixed;left:0;top:50%;transform:translateY(-50%);z-index:2147483646;background:#0D1A3B;color:#fff;padding:12px 16px;border-radius:0 8px 8px 0;font-size:13px;font-family:system-ui;direction:rtl;">סרגל דיווח – שגיאה: ' + errMsg + '</div>';
  }}
}})();
</script>"""
    video_script = """
<script>
(function(){{
  var crmBase = (typeof window !== "undefined" && window.__goallm_crm_frontend) ? window.__goallm_crm_frontend : "";
  if (!crmBase) return;
  function filenameFromUrl(url) {{
    try {{
      var path = (url || "").split("?")[0];
      if (path && path.indexOf("/") !== -1) path = path.split("/").pop();
      return (path && path.length) ? decodeURIComponent(path) : "וידאו";
    }} catch (e) {{ return "וידאו"; }}
  }}
  function addButton(video) {{
    if (video.dataset.goallmSendReview) return;
    video.dataset.goallmSendReview = "1";
    var src = video.currentSrc || video.src || "";
    if (!src && video.querySelector) {{
      var first = video.querySelector("source");
      if (first && first.src) src = first.src;
    }}
    if (!src || src.indexOf("data:") === 0 || src.indexOf("blob:") === 0) return;
    var filename = filenameFromUrl(src);
    var redirect = "/support/new?attach=file&file_url=" + encodeURIComponent(src) + "&filename=" + encodeURIComponent(filename);
    var href = crmBase.replace(/\\/$/, "") + "/login?redirect=" + encodeURIComponent(redirect);
    var wrapper = document.createElement("div");
    wrapper.style.cssText = "position:relative;display:inline-block;max-width:100%;";
    var parent = video.parentNode;
    if (parent) {{
      parent.insertBefore(wrapper, video);
      wrapper.appendChild(video);
      var btnWrap = document.createElement("div");
      btnWrap.style.cssText = "position:absolute;bottom:8px;left:8px;right:8px;z-index:10;display:flex;justify-content:center;pointer-events:none;";
      var a = document.createElement("a");
      a.href = href;
      a.target = "_blank";
      a.rel = "noopener";
      a.textContent = "שלח לבדיקה";
      a.style.cssText = "pointer-events:auto;padding:6px 12px;background:#2F6CFF;color:#fff;border-radius:6px;text-decoration:none;font-size:13px;font-family:system-ui,-apple-system,sans-serif;box-shadow:0 2px 8px rgba(0,0,0,0.2);direction:rtl;";
      btnWrap.appendChild(a);
      wrapper.appendChild(btnWrap);
    }}
  }}
  function run() {{
    try {{
      document.querySelectorAll("video").forEach(function(v) {{ addButton(v); }});
    }} catch (e) {{}}
  }}
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", run);
  else run();
  if (typeof MutationObserver !== "undefined" && document.body) {{
    var obs = new MutationObserver(function(mutations) {{
      mutations.forEach(function(m) {{
        if (m.addedNodes)
          m.addedNodes.forEach(function(n) {{
            if (n && n.nodeType === 1) {{
              if (n.tagName === "VIDEO") addButton(n);
              if (n.querySelectorAll) n.querySelectorAll("video").forEach(addButton);
            }}
          }});
      }});
    }});
    obs.observe(document.body, {{ childList: true, subtree: true }});
  }}
}})();
</script>"""
    if not is_admin:
        pass  # widget_html = minimal widget (set above)
    else:
        # Full widget: admin panel visible; "החל" opens new page to apply and show summary.
        widget_html = f"""<script>
(function(){{
  var root = document.createElement("div");
  root.id = "goallm-surf-root";
  if (document.body) document.body.appendChild(root);
  else if (document.documentElement) document.documentElement.appendChild(root);
  try {{
  var config = {{
    crmApi: {crm_api},
    crmFrontend: {crm_frontend},
    surfRuleApplyBase: {surf_rule_apply_base_js},
    currentUrl: {current_url_esc},
    rule: {rule_json},
    ruleDomain: {rule_domain_js},
    rulePath: {rule_path_js},
    currentDomain: {current_domain_js},
    currentPath: {current_path_js},
    requestChangeUrlAttr: {json.dumps(request_change_url_attr)},
    ruleDisplay: {json.dumps(rule_display, ensure_ascii=False)}
  }};
  var open = false;
  function render() {{
    root.innerHTML = '<div id="goallm-surf-wrap" style="position:fixed;left:0;top:50%;transform:translateY(-50%);width:' + (open ? '312px' : '32px') + ';z-index:2147483646;font-family:system-ui,-apple-system,sans-serif;font-size:14px;direction:rtl;">' +
      '<div id="goallm-surf-tab" style="position:absolute;left:0;top:50%;transform:translateY(-50%);width:32px;height:64px;background:#0D1A3B;color:#fff;border-radius:0 8px 8px 0;display:flex;align-items:center;justify-content:center;cursor:pointer;box-shadow:2px 0 8px rgba(0,0,0,0.2);user-select:none;" title="סרגל דיווח">' +
        (open ? "&#xAB;" : "&#xBB;") +
      '</div>' +
      '<div id="goallm-surf-panel" style="display:' + (open ? 'block' : 'none') + ';position:absolute;left:32px;top:0;width:280px;max-width:calc(90vw - 32px);background:#fff;border:1px solid #E4E7EC;border-right:none;border-radius:12px 0 0 12px;box-shadow:-4px 0 20px rgba(0,0,0,0.08);padding:16px;overflow:auto;max-height:80vh;">' +
        '<div style="font-weight:700;color:#0D1A3B;margin-bottom:12px;">סרגל דיווח</div>' +
        '<a id="goallm-surf-report-link" href="' + config.requestChangeUrlAttr + '" target="_blank" rel="noopener" style="display:block;width:100%;padding:10px 14px;background:#2F6CFF;color:#fff;text-align:center;border-radius:8px;text-decoration:none;font-weight:500;margin-bottom:12px;box-sizing:border-box;">דיווח – בקש לחסום את האתר</a>' +
        '<div id="goallm-surf-admin" style="display:block;margin-top:12px;padding-top:12px;border-top:1px solid #E4E7EC;">' +
          '<div style="font-weight:600;color:#0D1A3B;margin-bottom:8px;">הוסף/עדכן כלל (מנהל)</div>' +
          '<div id="goallm-surf-quick-step1" style="margin-bottom:10px;">' +
            '<div style="font-size:12px;color:#5f6368;margin-bottom:6px;">שלב 1 – פעולה:</div>' +
            '<div style="display:flex;gap:8px;flex-wrap:wrap;">' +
              '<button type="button" id="goallm-surf-action-block" style="flex:1;min-width:80px;padding:8px 12px;background:#dc2626;color:#fff;border:none;border-radius:8px;font-weight:500;cursor:pointer;font-size:13px;">חסום</button>' +
              '<button type="button" id="goallm-surf-action-allow" style="flex:1;min-width:80px;padding:8px 12px;background:#16a34a;color:#fff;border:none;border-radius:8px;font-weight:500;cursor:pointer;font-size:13px;">אפשר</button>' +
            '</div>' +
          '</div>' +
          '<div id="goallm-surf-quick-step2" style="display:none;margin-bottom:10px;">' +
            '<div style="font-size:12px;color:#5f6368;margin-bottom:6px;">שלב 2 – היקף הכלל:</div>' +
            '<div style="display:flex;flex-direction:column;gap:6px;">' +
              '<button type="button" id="goallm-surf-scope-domain" style="width:100%;padding:8px 12px;background:#f1f5f9;color:#0D1A3B;border:1px solid #E4E7EC;border-radius:8px;font-weight:500;cursor:pointer;font-size:13px;text-align:right;">רק הדומיין</button>' +
              '<button type="button" id="goallm-surf-scope-subdomains" style="width:100%;padding:8px 12px;background:#f1f5f9;color:#0D1A3B;border:1px solid #E4E7EC;border-radius:8px;font-weight:500;cursor:pointer;font-size:13px;text-align:right;">דומיין + תת-דומיינים</button>' +
              '<button type="button" id="goallm-surf-scope-exact" style="width:100%;padding:8px 12px;background:#f1f5f9;color:#0D1A3B;border:1px solid #E4E7EC;border-radius:8px;font-weight:500;cursor:pointer;font-size:13px;text-align:right;">כתובת ישירה</button>' +
            '</div>' +
            '<button type="button" id="goallm-surf-quick-apply" style="display:none;width:100%;padding:10px 14px;background:#2F6CFF;color:#fff;border:none;border-radius:8px;font-weight:500;cursor:pointer;margin-top:8px;">החל</button>' +
          '</div>' +
        '</div>' +
        '<div id="goallm-surf-toast" style="display:none;position:fixed;bottom:24px;left:24px;max-width:320px;padding:12px 14px;background:#0D1A3B;color:#fff;border-radius:8px;font-size:13px;line-height:1.4;box-shadow:0 4px 12px rgba(0,0,0,0.25);z-index:2147483647;direction:rtl;text-align:right;"></div>' +
      '</div>' +
    '</div>';
    var wrap = document.getElementById("goallm-surf-wrap");
    var tab = document.getElementById("goallm-surf-tab");
    var panel = document.getElementById("goallm-surf-panel");
    if (tab) tab.onclick = function() {{ open = !open; if (wrap) wrap.style.width = open ? "312px" : "32px"; if (panel) panel.style.display = open ? "block" : "none"; tab.innerHTML = open ? "&#xAB;" : "&#xBB;"; }};
    var adminEl = document.getElementById("goallm-surf-admin");
    var step1 = document.getElementById("goallm-surf-quick-step1");
    var step2 = document.getElementById("goallm-surf-quick-step2");
    var applyBtn = document.getElementById("goallm-surf-quick-apply");
    var quickAction = null;
    var quickScope = null;
    function setStep2Visible(show) {{ if (step2) step2.style.display = show ? "block" : "none"; }}
    function setApplyVisible(show) {{ if (applyBtn) applyBtn.style.display = show ? "block" : "none"; }}
    function clearScopeSelection() {{
      quickScope = null;
      setApplyVisible(false);
      ["domain", "subdomains", "exact"].forEach(function(s) {{
        var b = document.getElementById("goallm-surf-scope-" + s);
        if (b) {{ b.style.background = "#f1f5f9"; b.style.borderColor = "#E4E7EC"; }}
      }});
    }}
    function clearActionSelection() {{
      quickAction = null;
      var blockB = document.getElementById("goallm-surf-action-block");
      var allowB = document.getElementById("goallm-surf-action-allow");
      if (blockB) {{ blockB.style.background = "#dc2626"; }}
      if (allowB) {{ allowB.style.background = "#16a34a"; }}
    }}
    if (document.getElementById("goallm-surf-action-block")) document.getElementById("goallm-surf-action-block").onclick = function() {{
      quickAction = "block";
      clearScopeSelection();
      setStep2Visible(true);
      this.style.background = "#b91c1c";
      if (document.getElementById("goallm-surf-action-allow")) document.getElementById("goallm-surf-action-allow").style.background = "#16a34a";
    }};
    if (document.getElementById("goallm-surf-action-allow")) document.getElementById("goallm-surf-action-allow").onclick = function() {{
      quickAction = "allow";
      clearScopeSelection();
      setStep2Visible(true);
      this.style.background = "#15803d";
      if (document.getElementById("goallm-surf-action-block")) document.getElementById("goallm-surf-action-block").style.background = "#dc2626";
    }};
    function selectScope(scope, btnId) {{
      quickScope = scope;
      setApplyVisible(true);
      ["domain", "subdomains", "exact"].forEach(function(s) {{
        var id = "goallm-surf-scope-" + s;
        var b = document.getElementById(id);
        if (b) {{ b.style.background = (id === btnId ? "#e0e7ff" : "#f1f5f9"); b.style.borderColor = (id === btnId ? "#2F6CFF" : "#E4E7EC"); }}
      }});
    }}
    if (document.getElementById("goallm-surf-scope-domain")) document.getElementById("goallm-surf-scope-domain").onclick = function() {{ selectScope("domain_only", "goallm-surf-scope-domain"); }};
    if (document.getElementById("goallm-surf-scope-subdomains")) document.getElementById("goallm-surf-scope-subdomains").onclick = function() {{ selectScope("domain_and_subdomains", "goallm-surf-scope-subdomains"); }};
    if (document.getElementById("goallm-surf-scope-exact")) document.getElementById("goallm-surf-scope-exact").onclick = function() {{ selectScope("exact_url", "goallm-surf-scope-exact"); }};
    var toastEl = document.getElementById("goallm-surf-toast");
    var toastTimer = null;
    function showToast(html) {{
      if (!toastEl) return;
      if (toastTimer) clearTimeout(toastTimer);
      toastEl.innerHTML = html;
      toastEl.style.display = "block";
      toastTimer = setTimeout(function() {{ toastEl.style.display = "none"; toastTimer = null; }}, 5000);
    }}
    if (applyBtn) applyBtn.onclick = function() {{
      if (!quickAction || !quickScope) {{ showToast("בחר פעולה והיקף"); return; }}
      var u = config.surfRuleApplyBase + "&url=" + encodeURIComponent(config.currentUrl) + "&action=" + encodeURIComponent(quickAction) + "&scope=" + encodeURIComponent(quickScope);
      window.open(u, "_blank");
    }};
    if (config.crmFrontend) try {{ window.__goallm_crm_frontend = config.crmFrontend; }} catch (e) {{}}
    }}
    render();
  }} catch (e) {{
    var errMsg = (e && e.message) ? String(e.message).replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;") : "שגיאה";
    root.innerHTML = '<div style="position:fixed;left:0;top:50%;transform:translateY(-50%);z-index:2147483646;background:#0D1A3B;color:#fff;padding:12px 16px;border-radius:0 8px 8px 0;font-size:13px;font-family:system-ui;direction:rtl;">סרגל דיווח – שגיאה: ' + errMsg + '</div>';
  }}
}})();
</script>"""

    if inject_video:
        widget_html = widget_html + video_script

    # Prevent </script> in script body from closing the tag (escape so browser does not end script early)
    script_open = widget_html.find("<script>")
    script_close = widget_html.find("</script>")
    if script_open >= 0 and script_close > script_open:
        body = widget_html[script_open + 8 : script_close]
        if "</script>" in body:
            body = body.replace("</script>", "<\\/script>")
            widget_html = widget_html[: script_open + 8] + body + widget_html[script_close:]
            logger.warning("surf_widget: escaped </script> in injected script url=%s", (current_url or "")[:80])

    # Insert before </body>; if no </body>, append at end (use lambda so widget_html is not interpreted as re template)
    pattern = re.compile(r"</body\s*>", re.IGNORECASE)
    if pattern.search(text):
        text = pattern.sub(lambda m: widget_html + m.group(0), text, count=1)
    else:
        text = text + widget_html

    return text.encode(encoding, errors="replace")