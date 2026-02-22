"""
קבועים לעיצוב דפי נחיתה: חסימה, נשלח לבדיקה, תוכן מסונן.
ניתן לשנות כאן סגנונות, רקעים (SVG), גופנים וטקסטים.
"""

# CSS משותף לכל דפי הנחיתה – גופנים, ריווח, כפתורים, תגיות. מוזרק כ־<style> ב־head.
COMMON_STYLES = """
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

# קישור לטעינת גופן Heebo מ־Google Fonts. מוזרק ב־<head> של דפי הנחיתה.
FONT_LINK = '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Heebo:wght@400;500;700&display=swap" rel="stylesheet">'

# רקע CSS מעל רקע המצב – גרדיאנט לבן במרכז כדי שהטקסט יישאר קריא על הרקע הצבעוני.
BG_OVERLAY = "radial-gradient(ellipse 85% 75% at 50% 50%, rgba(255,255,255,0.94), transparent 65%), "

# רקע SVG אדום/קורל – מוצג כשהאתר חסום במדיניות (אין גישה).
BG_DANGER = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 600"><defs><linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" style="stop-color:#fef2f2"/><stop offset="50%" style="stop-color:#fee2e2"/><stop offset="100%" style="stop-color:#fecaca"/></linearGradient><pattern id="stripes" patternUnits="userSpaceOnUse" width="32" height="16"><path d="M0 0L16 16M16 0L32 16" stroke="#dc2626" stroke-width="1.5" opacity="0.15"/></pattern></defs><rect width="600" height="600" fill="url(#g)"/><rect width="600" height="600" fill="url(#stripes)"/></svg>"""
# רקע SVG כחול רך – מוצג כשהאתר חסום בהגדרות המשתמש ("ההגדרות שלי").
BG_USER = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 600"><defs><linearGradient id="u" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" style="stop-color:#eff6ff"/><stop offset="50%" style="stop-color:#dbeafe"/><stop offset="100%" style="stop-color:#bfdbfe"/></linearGradient><pattern id="dots" patternUnits="userSpaceOnUse" width="40" height="40"><circle cx="20" cy="20" r="2" fill="#2F6CFF" opacity="0.2"/></pattern></defs><rect width="600" height="600" fill="url(#u)"/><rect width="600" height="600" fill="url(#dots)"/></svg>"""
# רקע SVG כתום/ענבר – מוצג כשהדף נחסם בגלל סינון תוכן (מלל/תמונה).
BG_FILTER = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 600"><defs><linearGradient id="f" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" style="stop-color:#fff7ed"/><stop offset="50%" style="stop-color:#ffedd5"/><stop offset="100%" style="stop-color:#fed7aa"/></linearGradient><pattern id="lines" patternUnits="userSpaceOnUse" width="6" height="20"><line x1="0" y1="4" x2="6" y2="4" stroke="#ea580c" stroke-width="1.2" opacity="0.25"/><line x1="0" y1="12" x2="5" y2="12" stroke="#c2410c" stroke-width="0.8" opacity="0.2"/></pattern></defs><rect width="600" height="600" fill="url(#f)"/><rect width="600" height="600" fill="url(#lines)"/></svg>"""
# רקע SVG צהוב/ענבר – מוצג בדף "נשלח לבדיקה" (האתר עדיין לא נבדק).
BG_PENDING = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 600"><defs><linearGradient id="p" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" style="stop-color:#fffbeb"/><stop offset="50%" style="stop-color:#fef3c7"/><stop offset="100%" style="stop-color:#fde68a"/></linearGradient><pattern id="waves" patternUnits="userSpaceOnUse" width="60" height="30"><path d="M0 15 Q15 8 30 15 T60 15" stroke="#d97706" stroke-width="1" fill="none" opacity="0.25"/><path d="M0 22 Q15 15 30 22 T60 22" stroke="#b45309" stroke-width="0.8" fill="none" opacity="0.15"/></pattern></defs><rect width="600" height="600" fill="url(#p)"/><rect width="600" height="600" fill="url(#waves)"/></svg>"""

# דף HTML שמוצג כשכתובת ה-IP של הגולש לא משויכת לאף משתמש – הפרוקסי מחזיר 403 עם התוכן הזה.
UNBOUND_IP_HTML = """<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>חיבור לא מאושר</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 2rem; text-align: center; }
    h1 { color: #c00; }
    p { max-width: 32em; margin: 1rem auto; line-height: 1.5; }
  </style>
</head>
<body>
  <h1>חיבור לא מאושר</h1>
  <p>החיבור שלך לא מסונן על ידי המערכת. שירות הסינון וההקלטה זמין רק למשתמשים רשומים שמשויכים לחשבון.</p>
  <p>כדי להשתמש בשירות, יש לשייך את המכשיר (כתובת ה-IP) לחשבון במערכת.</p>
</body>
</html>"""

# תבנית דף אבחון סינון – מוצג ב־/diagnostic.
# מקבל: {server_time}, {connection_filtered}, {filter_check_url}, {cert_base_url}, {back_to_tools_html}.
DIAGNOSTIC_HTML_TEMPLATE = """<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="server-time" content="{server_time}">
  <meta name="connection-filtered" content="{connection_filtered}">
  <meta name="filter-check-url" content="{filter_check_url}">
  <meta name="cert-base-url" content="{cert_base_url}">
  <title>בדיקת סינון</title>
  """ + FONT_LINK + """
  <style>
    """ + COMMON_STYLES + """
    body { background: """ + BG_OVERLAY + """ #f0f9ff; }
    .back-to-tools { margin-bottom: 1.25rem; }
    .back-to-tools a {
      display: inline-flex; align-items: center; gap: 0.4rem; font-size: 0.95rem; font-weight: 500;
      color: #0D1A3B; text-decoration: none; border: 1px solid #E4E7EC; padding: 0.5rem 1rem;
      border-radius: 8px; background: #fff; box-shadow: 0 4px 18px rgba(0, 0, 0, 0.05);
      transition: background-color 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
    }
    .back-to-tools a:hover { background: #F7F8FA; border-color: #d1d5db; box-shadow: 0 4px 18px rgba(0, 0, 0, 0.08); }
    .progress-area { margin: 2rem 0; min-height: 140px; display: flex; flex-direction: column; align-items: center; justify-content: center; }
    .spinner { width: 56px; height: 56px; border: 3px solid #E4E7EC; border-top-color: #2F6CFF; border-radius: 50%; animation: spin 0.9s cubic-bezier(0.5, 0, 0.5, 1) infinite; }
    .spinner-dots { display: flex; gap: 8px; margin-top: 1rem; }
    .spinner-dots span { width: 8px; height: 8px; background: #2F6CFF; border-radius: 50%; animation: pulse 1.4s ease-in-out infinite both; }
    .spinner-dots span:nth-child(1) { animation-delay: 0s; }
    .spinner-dots span:nth-child(2) { animation-delay: 0.2s; }
    .spinner-dots span:nth-child(3) { animation-delay: 0.4s; }
    @keyframes spin { to { transform: rotate(360deg); } }
    @keyframes pulse { 0%, 80%, 100% { transform: scale(0.6); opacity: 0.5; } 40% { transform: scale(1); opacity: 1; } }
    .progress-text { margin-top: 0.75rem; font-size: 0.95rem; color: #6b7280; }
    #summary { margin-top: 2rem; padding: 1.25rem 1.5rem; border-radius: 16px; font-weight: 600; font-size: 1.1rem; text-align: center; }
    #summary.all-ok { background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%); color: #065f46; }
    #summary.has-issues { background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%); color: #991b1b; }
    #summary.has-issues { text-align: right; }
    #summary.has-issues a { color: #1d4ed8; text-decoration: underline; }
    a.cert-download-link { color: #1d4ed8; text-decoration: underline; }
    a.cert-download-link:hover { text-decoration: underline; }
    .not-filtered-msg { margin-top: 1rem; padding: 1rem 1.25rem; border-radius: 16px; font-size: 0.95rem; }
    .not-filtered-msg.has-issues { background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); color: #92400e; }
  </style>
</head>
<body>
  <div class="page-wrap">
    {back_to_tools_html}
    <div class="status-badge">בדיקת סינון</div>
    <h1 class="page-head">בדיקת חיבור לסינון</h1>

    <div id="progress-area" class="progress-area">
      <div class="spinner"></div>
      <div class="spinner-dots"><span></span><span></span><span></span></div>
      <div class="progress-text" id="progress-text">בודק אם הגלישה דרך הסינון...</div>
    </div>

    <div id="summary" style="display:none;"></div>
    <div id="not-filtered-msg" style="display:none;" class="not-filtered-msg"></div>
  </div>
  <script>
    (function() {
      var MAX_CLOCK_SKEW_SEC = 60;
      var CERT_TIMEOUT_MS = 8000;
      var progressArea = document.getElementById('progress-area');
      var progressText = document.getElementById('progress-text');
      var summaryEl = document.getElementById('summary');
      var notFilteredEl = document.getElementById('not-filtered-msg');
      var finished = false;

      var filterCheckUrlEl = document.querySelector('meta[name="filter-check-url"]');
      var certBaseUrlEl = document.querySelector('meta[name="cert-base-url"]');
      var filterCheckUrl = filterCheckUrlEl ? (filterCheckUrlEl.getAttribute('content') || '').trim() : '';
      var certBaseUrlRaw = certBaseUrlEl ? (certBaseUrlEl.getAttribute('content') || '').trim().replace(/\/?$/, '') : '';
      var certBaseUrl = (certBaseUrlRaw && certBaseUrlRaw.indexOf('{') === -1) ? certBaseUrlRaw : (location.origin + '/diagnostic/cert');

      var connectionFilteredEl = document.querySelector('meta[name="connection-filtered"]');
      var connectionFiltered = connectionFilteredEl ? (connectionFilteredEl.getAttribute('content') || '').toLowerCase() === 'true' : true;

      var osNames = { windows: 'Windows', mac: 'Mac', ios: 'iPhone/iPad', android: 'Android', linux: 'Linux' };
      function getCertProblemHtml() {
        var ua = navigator.userAgent || '';
        var isWin = /Win|Windows/i.test(ua);
        var isIOS = /iPhone|iPad|iPod/i.test(ua);
        var isAndroid = /Android/i.test(ua);
        var isMac = /Mac/i.test(ua) && !/iPhone|iPad/i.test(ua);
        var os = isWin ? 'windows' : (isIOS ? 'ios' : (isAndroid ? 'android' : (isMac ? 'mac' : 'linux')));
        var osName = osNames[os] || 'המכשיר שלך';
        var certUrl = (certBaseUrl || (location.origin + '/diagnostic/cert')) + '?os=' + os;
        var link = '<a href="' + certUrl + '" download target="_blank" rel="noopener" class="cert-download-link">לחץ כאן להורדת תעודת אבטחה ל־' + osName + '</a>';
        var hint = '';
        if (isIOS) hint = 'הורד את הקובץ, התקן את הפרופיל בהגדרות, ואז הפעל אמון בהגדרות > כללי > אודות > תעודות אבטחה.';
        else if (isAndroid) hint = 'הורד את הקובץ והתקן אותו כתעודת אבטחה בהגדרות המכשיר.';
        else if (isWin) hint = 'הורד את הקובץ והתקן אותו (למשל בלחיצה כפולה או דרך תחנת השירות).';
        else if (isMac) hint = 'הורד את הקובץ ופתח אותו – הוא יירשם ב־Keychain.';
        else hint = 'הורד את הקובץ והתקן אותו כתעודת אבטחה במערכת.';
        return 'תעודת האבטחה לא מותקנת במכשיר. ' + link + '. ' + hint;
      }

      function showNotFilteredIfNeeded() {
        if (!connectionFiltered && notFilteredEl) {
          notFilteredEl.style.display = 'block';
          notFilteredEl.className = 'not-filtered-msg has-issues';
          notFilteredEl.innerHTML = 'החיבור שלך לא מסונן כרגע. שירות הסינון זמין רק כשהמכשיר משויך לחשבון.';
        }
      }

      function showResult(isOk, problemText, isCertProblem) {
        if (finished) return;
        finished = true;
        progressArea.style.display = 'none';
        summaryEl.style.display = 'block';
        if (isOk) {
          summaryEl.className = 'all-ok';
          summaryEl.textContent = 'לא נמצאו בעיות';
        } else {
          summaryEl.className = 'has-issues';
          summaryEl.innerHTML = (isCertProblem ? getCertProblemHtml() : problemText);
        }
        showNotFilteredIfNeeded();
      }

      function setProgressText(txt) { if (progressText) progressText.textContent = txt; }

      function isSameOrigin(checkUrl) {
        try {
          var u = new URL(checkUrl);
          return u.origin === location.origin;
        } catch (e) { return false; }
      }

      if (!filterCheckUrl) {
        setProgressText('בודק שעון ותעודת אבטחה...');
        runClockAndCertChecks();
        return;
      }

      if (!isSameOrigin(filterCheckUrl)) {
        setProgressText('בודק שעון ותעודת אבטחה...');
        runClockAndCertChecks();
        return;
      }

      fetch(filterCheckUrl, { cache: 'no-store' }).then(function(res) {
        if (!res.ok) {
          showResult(false, 'נראה שהגלישה לא עוברת דרך שרת הסינון. נסה לפתוח את הדף מכתובת הסינון (filter.check) או לוודא שהמכשיר מוגדר לגלישה דרך הפרוקסי.', false);
          return;
        }
        return res.json().then(function(data) {
          if (!data || data.filtered !== true) {
            showResult(false, 'נראה שהגלישה לא עוברת דרך שרת הסינון. נסה לפתוח את הדף מכתובת הסינון (filter.check) או לוודא שהמכשיר מוגדר לגלישה דרך הפרוקסי.', false);
            return;
          }
          setProgressText('בודק שעון ותעודת אבטחה...');
          runClockAndCertChecks();
        }).catch(function() {
          showResult(false, 'נראה שהגלישה לא עוברת דרך שרת הסינון. נסה לפתוח את הדף מכתובת הסינון (filter.check) או לוודא שהמכשיר מוגדר לגלישה דרך הפרוקסי.', false);
        });
      }).catch(function() {
        showResult(false, 'נראה שהגלישה לא עוברת דרך שרת הסינון. נסה לפתוח את הדף מכתובת הסינון (filter.check) או לוודא שהמכשיר מוגדר לגלישה דרך הפרוקסי.', false);
      });

      function runClockAndCertChecks() {
        var serverTimeEl = document.querySelector('meta[name="server-time"]');
        var serverTime = serverTimeEl ? parseInt(serverTimeEl.getAttribute('content'), 10) : 0;
        var clientTime = Math.floor(Date.now() / 1000);
        var skew = serverTime ? Math.abs(clientTime - serverTime) : 0;

        if (!serverTime) {
          showResult(false, 'לא ניתן להשלים את הבדיקה. נסה לרענן את הדף.', false);
          return;
        }
        if (skew > MAX_CLOCK_SKEW_SEC) {
          showResult(false, 'השעון במכשיר לא מסונכרן. כוון את השעון בהגדרות המכשיר ונסה שוב.', false);
          return;
        }

        setProgressText('בודק תעודת אבטחה (HTTPS)...');
        var certTimeout = setTimeout(function() {
          if (!finished) showResult(false, null, true);
        }, CERT_TIMEOUT_MS);

        fetch('https://example.com', { cache: 'no-store', mode: 'no-cors' }).then(function(res) {
          clearTimeout(certTimeout);
          showResult(true);
        }).catch(function() {
          clearTimeout(certTimeout);
          showResult(false, null, true);
        });
      }
    })();
  </script>
</body>
</html>"""
