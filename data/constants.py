"""
קבועים כלליים של התוכנית – ערכים שאפשר לשנות לפי צורך.
מאוחד כאן כדי שיהיה קל לעבוד עם כל ההגדרות ממקום אחד.
כל הערכים מהסביבה מוחלים כאן.

משתני סביבה:
  CRM_PROXY_SECRET         – סוד משותף בין הפרוקסי ל-CRM (touch-ip, Surf token).
  FILTER_BIND_BASE_URL     – כתובת דף הקישור (unbound IP). "off"/"0" = כבוי.
  CRM_API_URL              – כתובת API של ה-CRM.
  CRM_FRONTEND_URL         – כתובת פרונט ה-CRM.
  GOALLM_STORAGE_DIR       – תיקיית אחסון (מאגר, DB). ברירת מחדל: .storage בשורש.
  USE_LLM_IMAGE_ANALYZER   – "1"/"true"/"yes" = שימוש ב-LLM לניתוח תמונות.
  SECRET_KEY               – מפתח ל-JWT (חובה בייצור).
"""
import os

# ========== שמות טבלאות (SQLite) ==========
# שם הטבלה שמאחסנת סטטוס תמונות (allowed/blocked/pending) ב־SQLite של הסינון.
IMAGE_STATUS_TABLE_NAME = "image_status"
# שם הטבלה של חוקי ה-URL (דומיין, path, state) במאגר המדיניות.
POLICIES_TABLE_NAME = "url_policies"
# שם הטבלה של חוקי תגיות (tag → state) במאגר המדיניות.
TAG_RULES_TABLE_NAME = "tag_rules"

# ========== פרוקסי / CRM ==========
# ברירת מחדל לסוד המשותף – דרוס עם CRM_PROXY_SECRET בסביבה.
DEFAULT_CRM_PROXY_SECRET = "dev-secret"
# ברירת מחדל לכתובת דף הקישור – IP לא משויך מנותב לכאן; "off"/"0" = כבוי.
DEFAULT_FILTER_BIND_BASE_URL = "https://filter.forum-dev.com"

# ערך אפקטיבי: מסביבה או ברירת מחדל. משמש אימות touch-ip ו־Surf token.
CRM_PROXY_SECRET = (os.environ.get("CRM_PROXY_SECRET") or DEFAULT_CRM_PROXY_SECRET).strip()

# ערך אפקטיבי: אם "off"/"0"/"false" – None (לא מפנים ל־bind, מציגים 403).
_raw_bind = (os.environ.get("FILTER_BIND_BASE_URL") or DEFAULT_FILTER_BIND_BASE_URL).strip().rstrip("/")
FILTER_BIND_BASE_URL = None if _raw_bind.lower() in ("off", "0", "false", "") else _raw_bind

# תוקף טוקן Surf בשניות – אחרי הזמן הזה הטוקן לא תקף לאימות משתמש מפרוקסי ל-CRM.
SURF_TOKEN_TTL_SEC = 300
   
# ========== כתובות CRM (API ופרונט) ==========
# ברירת מחדל לכתובת ה-API של ה-CRM (FastAPI).
DEFAULT_CRM_API_URL = "http://127.0.0.1:8000"
# ברירת מחדל לכתובת הפרונט (למשל Vite ב־dev על 5173).
DEFAULT_CRM_FRONTEND_URL = "http://localhost:5173"

# ערכים אפקטיביים – מסביבה או ברירת מחדל. קישורים בדפי נחיתה ובדפדפן.
CRM_API_URL = (os.environ.get("CRM_API_URL") or DEFAULT_CRM_API_URL).rstrip("/")
CRM_FRONTEND_URL = (os.environ.get("CRM_FRONTEND_URL") or DEFAULT_CRM_FRONTEND_URL).rstrip("/")

# ========== אחסון ==========
# אם מוגדר – נתיב תיקיית האחסון (מאגר, DB). אם None – כל מודול משתמש ב־.storage יחסית לשורש.
GOALLM_STORAGE_DIR = os.environ.get("GOALLM_STORAGE_DIR")

# ========== שרתים (ברירת מחדל להרצה) ==========
# כתובת להאזנה כשמריצים את ה-API (למשל 0.0.0.0 לגישה מהרשת).
DEFAULT_API_HOST = "0.0.0.0"
# פורט להאזנה של ה-API (FastAPI).
DEFAULT_API_PORT = 8000

# ========== אבטחה (JWT, סיסמאות) ==========
# מספר סיבובי bcrypt להצפנת סיסמאות – גבוה יותר = מאובן יותר אבל איטי יותר.
BCRYPT_ROUNDS = 12
# מפתח ברירת מחדל ל-JWT – בייצור חובה להגדיר SECRET_KEY בסביבה.
DEFAULT_SECRET_KEY = "change-this-in-production-use-secrets-token-urlsafe-32"
SECRET_KEY = os.environ.get("SECRET_KEY", DEFAULT_SECRET_KEY)
# אלגוריתם חתימת JWT.
ALGORITHM = "HS256"
# תוקף טוקן הגישה בדקות – אחרי הזמן הזה המשתמש צריך להתחבר מחדש.
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 ימים

# ========== אימות (OTP) ==========
# אורך קוד האימות (ספרות) שנשלח בטלפון/אימייל.
CODE_LENGTH = 6
# תוקף קוד האימות בדקות – אחרי הזמן הזה הקוד לא תקף.
CODE_EXPIRE_MINUTES = 10
# מרווח מינימלי בדקות בין שליחת קוד לאותו יעד (מגבלת קצב).
RATE_LIMIT_MINUTES = 2

# ========== תמונות – ניתוח ותור ==========
# True אם מוגדר USE_LLM_IMAGE_ANALYZER=1/true/yes – משתמשים ב-LLM לניתוח תמונות; אחרת מנתח סימולציה.
USE_LLM_IMAGE_ANALYZER = (os.environ.get("USE_LLM_IMAGE_ANALYZER") or "").strip().lower() in ("1", "true", "yes")

# timeout בשניות להמתנה לתוצאת ניתוח תמונה לפני שמסמנים שגיאה.
DEFAULT_ANALYSIS_TIMEOUT_SECONDS = 120
# מרווח בשניות בין בדיקות Watchdog על משימות תקועות בתור.
WATCHDOG_INTERVAL_SECONDS = 30
# מספר workers במקביל בתור ניתוח התמונות – מגדיל throughput.
DEFAULT_MAX_WORKERS = 1000

# צלע מקסימלית (פיקסלים) לתמונה לפני חישוב hash – חוסך זיכרון ו-CPU.
MAX_SIDE_FOR_HASH = 1024
# איכות JPEG בקנוניזציה לפני hash – קבועה כדי hash דטרמיניסטי.
JPEG_QUALITY = 90
# מקסימום תמונות מוטמעות (data: URL) לעיבוד בדף אחד – מונע עומס.
MAX_EMBEDDED_IMAGES_PER_PAGE = 100

# ========== סינון מלל – ספים ורמות ==========
# רמות חומרה למילים: 1=קל, 2=בינוני, 3=חמור. משמש את רשימות המילים והספים.
SEVERITY_LIGHT = 1
SEVERITY_MEDIUM = 2
SEVERITY_SEVERE = 3

# מינימום מופעים של חומרה 1 (קל) במשפט/פסקה/דף כדי לחסום את היחידה.
THRESHOLD_SENTENCE_LIGHT = 2
THRESHOLD_PARAGRAPH_LIGHT = 5
THRESHOLD_PAGE_LIGHT = 10

# True = מופע אחד של חומרה 3 (חמור) בדף מספיק לחסימת הדף (בטקסט גולמי).
ANY_SEVERITY_3_BLOCKS_PAGE = True
# מינימום מופעים של חומרה 2 (בינוני) בדף כדי לאפשר חסימת דף לפי מגמה.
THRESHOLD_PAGE_MEDIUM_BLOCK = 3
# אחוז מינימלי מרכיבי הדף (למשל פסקאות) עם זיהוי כדי לחסום את כל הדף.
MIN_PERCENTAGE_COMPONENTS_FOR_PAGE_BLOCK = 0.25
# מינימום מספר רכיבים עם זיהוי כדי לחסום דף (גם אם האחוז נמוך).
MIN_COMPONENTS_WITH_DETECTION_FOR_PAGE_BLOCK = 3

# קודי שפה נתמכות – תואמות לתיקיות ב־word_lists (he, en).
SUPPORTED_LANGS = ("he", "en")
