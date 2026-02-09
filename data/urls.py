"""
כתובות ברירת מחדל ל-CRM ולפרונט – משמשות כשמשתני סביבה לא מוגדרים.
ניתן לשנות כאן או להגדיר CRM_API_URL / CRM_FRONTEND_URL בסביבה.
"""

# ברירת מחדל ל-API של ה-CRM (FastAPI)
DEFAULT_CRM_API_URL = "http://127.0.0.1:8000"

# ברירת מחדל לפרונט של ה-CRM (Vite ב-dev בדרך כלל 5173)
DEFAULT_CRM_FRONTEND_URL = "http://localhost:5173"
