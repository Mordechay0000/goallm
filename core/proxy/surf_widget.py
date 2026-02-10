"""
Surf widget: inject a collapsible sidebar into every allowed HTML page.
- Small tab on the left edge opens a panel with:
  - "דיווח" = link to request block (CRM request-change with action=block)
  - For admin (from token): show allowing rule and "חסום את האתר" to create block rule.
Token is created by the proxy (shared secret with CRM) so CRM can verify the bound user.
"""
import base64
import hashlib
import hmac
import html
import json
import os
import re
import time
from urllib.parse import quote, urlparse
from typing import Optional, Any

from core.flow.site_policy_pages import CRM_API_URL, CRM_FRONTEND_URL
from data.constants import CRM_PROXY_SECRET, SURF_TOKEN_TTL_SEC


def _url_to_domain_path(url: str) -> tuple[str, str]:
    """Extract exact domain and path from URL (no subdomains in pattern)."""
    u = (url or "").strip()
    if not u or "://" not in u:
        return "", "/"
    try:
        p = urlparse(u)
        domain = (p.hostname or "").lower().rstrip(".")
        path = (p.path or "").strip() or "/"
        path = "/" + path.lstrip("/") if path != "/" else "/"
        return domain, path
    except Exception:
        return "", "/"

def create_surf_token(user_id: int) -> str:
    """Create a signed token for the bound user (proxy → CRM verification)."""
    expiry = int(time.time()) + SURF_TOKEN_TTL_SEC
    payload = f"{user_id}:{expiry}"
    payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    sig = hmac.new(
        CRM_PROXY_SECRET.encode(),
        payload_b64.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()
    return f"{payload_b64}.{sig}"


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
) -> bytes:
    """
    Inject the surf widget (tab + panel) and config script before </body>.
    Only injects when user_id is set (bound connection). Preserves encoding.
    """
    if user_id is None:
        return html_body

    try:
        text = html_body.decode(encoding, errors="replace")
    except Exception:
        return html_body

    token = create_surf_token(user_id)
    crm_api = json.dumps(CRM_API_URL)
    crm_frontend = json.dumps(CRM_FRONTEND_URL)
    current_url_esc = json.dumps(current_url)
    token_esc = json.dumps(token)
    rule_json = json.dumps(rule, ensure_ascii=False) if rule else "null"
    rule_domain_js = json.dumps((rule.get("domain") or rule.get("domain_pattern") or "").strip()) if rule else '""'
    rule_path_js = json.dumps((rule.get("path") or rule.get("path_pattern") or "/").strip() or "/") if rule else '"/"'
    request_change_url = _request_change_link(current_url, "block")
    request_change_url_attr = request_change_url.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")
    rule_display = _rule_display(rule)
    current_domain, current_path = _url_to_domain_path(current_url)
    current_domain_js = json.dumps(current_domain)
    current_path_js = json.dumps(current_path)

    # Inline widget: token-based (IP binding). No iframe.
    widget_html = f"""<div id="goallm-surf-root"></div>
<script>
(function(){{
  var root = document.getElementById("goallm-surf-root");
  if (!root) return;
  var config = {{
    crmApi: {crm_api},
    currentUrl: {current_url_esc},
    token: {token_esc},
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
        '<div id="goallm-surf-admin" style="display:none;margin-top:12px;padding-top:12px;border-top:1px solid #E4E7EC;">' +
          '<div style="font-weight:600;color:#0D1A3B;margin-bottom:6px;">הכלל שמאפשר את האתר</div>' +
          '<div id="goallm-surf-rule-text" style="font-size:13px;color:#1A1A1A;margin-bottom:10px;word-break:break-all;"></div>' +
          '<button type="button" id="goallm-surf-block-btn" style="width:100%;padding:10px 14px;background:#dc2626;color:#fff;border:none;border-radius:8px;font-weight:500;cursor:pointer;margin-bottom:8px;">חסום את האתר עכשיו</button>' +
          '<button type="button" id="goallm-surf-update-rule-btn" style="display:none;width:100%;padding:10px 14px;background:#b91c1c;color:#fff;border:none;border-radius:8px;font-weight:500;cursor:pointer;">שנה את הכלל הקיים לחסום</button>' +
        '</div>' +
      '</div>' +
    '</div>';
    var wrap = document.getElementById("goallm-surf-wrap");
    var tab = document.getElementById("goallm-surf-tab");
    var panel = document.getElementById("goallm-surf-panel");
    if (tab) tab.onclick = function() {{ open = !open; if (wrap) wrap.style.width = open ? "312px" : "32px"; if (panel) panel.style.display = open ? "block" : "none"; tab.innerHTML = open ? "&#xAB;" : "&#xBB;"; }};
    var ruleEl = document.getElementById("goallm-surf-rule-text");
    if (ruleEl) ruleEl.textContent = config.ruleDisplay;
    var adminEl = document.getElementById("goallm-surf-admin");
    var blockBtn = document.getElementById("goallm-surf-block-btn");
    var updateRuleBtn = document.getElementById("goallm-surf-update-rule-btn");
    var ruleDomain = (config.ruleDomain || "").toString().trim();
    var rulePath = (config.rulePath || "/").toString().trim() || "/";
    var currentDomain = (config.currentDomain || "").toString().trim();
    var currentPath = (config.currentPath || "/").toString().trim() || "/";
    var ruleIsExactMatch = ruleDomain && currentDomain && ruleDomain === currentDomain && rulePath === currentPath;
    if (blockBtn) blockBtn.onclick = function() {{
      blockBtn.disabled = true;
      fetch(config.crmApi + "/api/surf-widget/block", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ token: config.token, url: config.currentUrl }})
      }}).then(function(r) {{ return r.json(); }}).then(function(data) {{
        if (data.success) {{ alert("האתר נחסם בהצלחה."); window.location.reload(); }}
        else {{ alert(data.error || "שגיאה בחסימת האתר"); }}
      }}).catch(function(e) {{ alert('שגיאה: ' + (e.message || 'לא ניתן לחסום')); }}).finally(function() {{ blockBtn.disabled = false; }});
    }};
    if (updateRuleBtn && config.rule && ruleDomain && !ruleIsExactMatch) {{
      updateRuleBtn.style.display = "block";
      updateRuleBtn.onclick = function() {{
        updateRuleBtn.disabled = true;
        fetch(config.crmApi + "/api/surf-widget/update-rule-to-block", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ token: config.token, rule_domain: ruleDomain, rule_path: rulePath }})
        }}).then(function(r) {{ return r.json(); }}).then(function(data) {{
          if (data.success) {{ alert("הכלל עודכן לחסום בהצלחה."); window.location.reload(); }}
          else {{ alert(data.error || "שגיאה בעדכון הכלל"); }}
        }}).catch(function(e) {{ alert('שגיאה: ' + (e.message || 'לא ניתן לעדכן')); }}).finally(function() {{ updateRuleBtn.disabled = false; }});
      }};
    }}
    fetch(config.crmApi + "/api/surf-widget/context?token=" + encodeURIComponent(config.token))
      .then(function(r) {{ if (!r.ok) return null; return r.json(); }})
      .then(function(data) {{
        if (data && data.hasOwnProperty("is_admin") && data.is_admin === true && adminEl) {{
          adminEl.style.display = "block";
        }}
      }})
      .catch(function() {{}});
  }}
  render();
}})();
</script>"""

    # Insert before </body>; if no </body>, append at end (use lambda so widget_html is not interpreted as re template)
    pattern = re.compile(r"</body\s*>", re.IGNORECASE)
    if pattern.search(text):
        text = pattern.sub(lambda m: widget_html + m.group(0), text, count=1)
    else:
        text = text + widget_html

    return text.encode(encoding, errors="replace")