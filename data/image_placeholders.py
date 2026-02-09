"""
תמונות placeholder להצגה כשתמונה חסומה / נשלחת לבדיקה / שגיאה.
ניתן לשנות כאן את ה-SVG כדי להתאים לעיצוב.
"""

# Blocked image placeholder: 3x3 grid with black gradient (black -> dark gray -> gray)
BLOCK_IMAGE = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet">
  <rect x="0" y="0" width="33.33" height="33.33" fill="#000000"/>
  <rect x="33.33" y="0" width="33.34" height="33.33" fill="#1a1a1a"/>
  <rect x="66.67" y="0" width="33.33" height="33.33" fill="#333333"/>
  <rect x="0" y="33.33" width="33.33" height="33.34" fill="#0d0d0d"/>
  <rect x="33.33" y="33.33" width="33.34" height="33.34" fill="#262626"/>
  <rect x="66.67" y="33.33" width="33.33" height="33.34" fill="#404040"/>
  <rect x="0" y="66.67" width="33.33" height="33.33" fill="#1a1a1a"/>
  <rect x="33.33" y="66.67" width="33.34" height="33.33" fill="#333333"/>
  <rect x="66.67" y="66.67" width="33.33" height="33.33" fill="#4d4d4d"/>
  <g stroke="#ffffff" stroke-width="6" stroke-linecap="round">
    <line x1="30" y1="30" x2="70" y2="70"/>
    <line x1="70" y1="30" x2="30" y2="70"/>
  </g>
</svg>
"""

# Checking image placeholder: 3x3 grid with yellow gradient (bright yellow -> yellow -> dark yellow)
CHECKING_IMAGE = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet">
  <rect x="0" y="0" width="33.33" height="33.33" fill="#ffeb3b"/>
  <rect x="33.33" y="0" width="33.34" height="33.33" fill="#ffd54f"/>
  <rect x="66.67" y="0" width="33.33" height="33.33" fill="#ffc107"/>
  <rect x="0" y="33.33" width="33.33" height="33.34" fill="#fff176"/>
  <rect x="33.33" y="33.33" width="33.34" height="33.34" fill="#ffec40"/>
  <rect x="66.67" y="33.33" width="33.33" height="33.34" fill="#ffdb4d"/>
  <rect x="0" y="66.67" width="33.33" height="33.33" fill="#fff59d"/>
  <rect x="33.33" y="66.67" width="33.34" height="33.33" fill="#fff176"/>
  <rect x="66.67" y="66.67" width="33.33" height="33.33" fill="#ffec40"/>
  <g stroke="#000000" stroke-width="5" fill="none" stroke-linecap="round">
    <circle cx="50" cy="40" r="12"/>
    <line x1="58" y1="48" x2="65" y2="55" stroke-width="6"/>
  </g>
</svg>
"""

# Error image placeholder: 3x3 grid with red gradient (bright red -> red -> dark red)
ERROR_IMAGE = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet">
  <rect x="0" y="0" width="33.33" height="33.33" fill="#f44336"/>
  <rect x="33.33" y="0" width="33.34" height="33.33" fill="#e53935"/>
  <rect x="66.67" y="0" width="33.33" height="33.33" fill="#d32f2f"/>
  <rect x="0" y="33.33" width="33.33" height="33.34" fill="#ef5350"/>
  <rect x="33.33" y="33.33" width="33.34" height="33.34" fill="#e53935"/>
  <rect x="66.67" y="33.33" width="33.33" height="33.34" fill="#c62828"/>
  <rect x="0" y="66.67" width="33.33" height="33.33" fill="#ffcdd2"/>
  <rect x="33.33" y="66.67" width="33.34" height="33.33" fill="#ef5350"/>
  <rect x="66.67" y="66.67" width="33.33" height="33.33" fill="#e53935"/>
  <g fill="#ffffff">
    <path d="M 50 25 L 50 55 M 50 60 L 50 65" stroke="#ffffff" stroke-width="7" stroke-linecap="round"/>
    <circle cx="50" cy="68" r="4" fill="#ffffff"/>
  </g>
</svg>
"""
