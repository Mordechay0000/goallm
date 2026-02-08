"""
תצורת סינון מלל – ספים ורמות חומרה.

ניתן לשנות ספים כאן או לטעון מקובץ/משתני סביבה בהמשך.
"""
from pathlib import Path

# נתיב תיקיית רשימות המילים (יחסית למיקום המודול)
_BASE = Path(__file__).resolve().parent
WORD_LISTS_DIR = _BASE / "word_lists"

# רמות חומרה: 1=קל (קללות), 2=בינוני (מילים בהקשר), 3=חמור (תוכן מיני/כפירה וכו')
SEVERITY_LIGHT = 1
SEVERITY_MEDIUM = 2
SEVERITY_SEVERE = 3

# ספים – כמה מופעים של חומרה 1 (קל) → לחסום/להחליף יחידה
THRESHOLD_SENTENCE_LIGHT = 2   # 2+ מילים קלות במשפט → חסימת כל המשפט (איקסים)
THRESHOLD_PARAGRAPH_LIGHT = 5  # 5+ מילים קלות בפסקה → חסימת כל הפסקה
THRESHOLD_PAGE_LIGHT = 10      # 10+ מילים קלות בדף → חסימת כל הדף

# חומרה 3 (חמור) – מופע אחד בדף = החלפת המילה; חסימת דף רק אם מפוזר (מגמה)
ANY_SEVERITY_3_BLOCKS_PAGE = True  # משמש לטקסט גולמי (ללא HTML)

# חומרה 2 – אם מעל X מופעים בדף → חסימת דף רק אם מפוזר ב־X+ רכיבים
THRESHOLD_PAGE_MEDIUM_BLOCK = 3  # 3+ מילים בינוניות

# מגמה (spread): חסימת דף רק לפי אחוז הרכיבים עם זיהוי – לא לפי מספר הזיהויים בתוך רכיב.
MIN_PERCENTAGE_COMPONENTS_FOR_PAGE_BLOCK = 0.25   # 25% מרכיבי הדף עם זיהוי → חסימת דף
MIN_COMPONENTS_WITH_DETECTION_FOR_PAGE_BLOCK = 3  # מינימום X רכיבים עם זיהוי (גם אם אחוז נמוך)

# שפות נתמכות (תיקיות ב־word_lists)
SUPPORTED_LANGS = ("he", "en")
