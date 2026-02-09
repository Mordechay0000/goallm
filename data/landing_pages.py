"""
קבועים לעיצוב דפי נחיתה: חסימה, נשלח לבדיקה, תוכן מסונן.
ניתן לשנות כאן סגנונות, רקעים (SVG), גופנים וטקסטים.
"""

# Design language: ניקיון עסקי, טאצ' מודרני עדין (תואם ל-CRM)
# Primary #0D1A3B, Accent #2F6CFF, Border #E4E7EC, Text #1A1A1A, Shadow עדין
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

# Heebo font – תואם לשפה העיצובית של ה-CRM
FONT_LINK = '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Heebo:wght@400;500;700&display=swap" rel="stylesheet">'

# Overlay: מרכז בהיר לקריאות, שוליים נותנים לצבע המצב לבלוט
BG_OVERLAY = "radial-gradient(ellipse 85% 75% at 50% 50%, rgba(255,255,255,0.94), transparent 65%), "

# מיפוי צבע לפי מצב (מזוהה במבט): אדום=חסום | כחול=הגדרות שלי | כתום=תוכן מסונן | צהוב/ענבר=ממתין לבדיקה
# חסום מדיניות (אין גישה): אדום/קורל רך
BG_DANGER = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 600"><defs><linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" style="stop-color:#fef2f2"/><stop offset="50%" style="stop-color:#fee2e2"/><stop offset="100%" style="stop-color:#fecaca"/></linearGradient><pattern id="stripes" patternUnits="userSpaceOnUse" width="32" height="16"><path d="M0 0L16 16M16 0L32 16" stroke="#dc2626" stroke-width="1.5" opacity="0.15"/></pattern></defs><rect width="600" height="600" fill="url(#g)"/><rect width="600" height="600" fill="url(#stripes)"/></svg>"""
# חסום בהגדרות המשתמש: כחול רך – "ההגדרות שלי"
BG_USER = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 600"><defs><linearGradient id="u" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" style="stop-color:#eff6ff"/><stop offset="50%" style="stop-color:#dbeafe"/><stop offset="100%" style="stop-color:#bfdbfe"/></linearGradient><pattern id="dots" patternUnits="userSpaceOnUse" width="40" height="40"><circle cx="20" cy="20" r="2" fill="#2F6CFF" opacity="0.2"/></pattern></defs><rect width="600" height="600" fill="url(#u)"/><rect width="600" height="600" fill="url(#dots)"/></svg>"""
# סינון תוכן (הדף נחסם): כתום/ענבר רך – "תוכן מסונן"
BG_FILTER = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 600"><defs><linearGradient id="f" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" style="stop-color:#fff7ed"/><stop offset="50%" style="stop-color:#ffedd5"/><stop offset="100%" style="stop-color:#fed7aa"/></linearGradient><pattern id="lines" patternUnits="userSpaceOnUse" width="6" height="20"><line x1="0" y1="4" x2="6" y2="4" stroke="#ea580c" stroke-width="1.2" opacity="0.25"/><line x1="0" y1="12" x2="5" y2="12" stroke="#c2410c" stroke-width="0.8" opacity="0.2"/></pattern></defs><rect width="600" height="600" fill="url(#f)"/><rect width="600" height="600" fill="url(#lines)"/></svg>"""
# ממתין לבדיקה: צהוב/ענבר רך – "בהמתנה"
BG_PENDING = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 600"><defs><linearGradient id="p" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" style="stop-color:#fffbeb"/><stop offset="50%" style="stop-color:#fef3c7"/><stop offset="100%" style="stop-color:#fde68a"/></linearGradient><pattern id="waves" patternUnits="userSpaceOnUse" width="60" height="30"><path d="M0 15 Q15 8 30 15 T60 15" stroke="#d97706" stroke-width="1" fill="none" opacity="0.25"/><path d="M0 22 Q15 15 30 22 T60 22" stroke="#b45309" stroke-width="0.8" fill="none" opacity="0.15"/></pattern></defs><rect width="600" height="600" fill="url(#p)"/><rect width="600" height="600" fill="url(#waves)"/></svg>"""
