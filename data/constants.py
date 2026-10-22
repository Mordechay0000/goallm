"""
קבועים כלליים של התוכנית – ערכים שאפשר לשנות לפי צורך.
מאוחד כאן כדי שיהיה קל לעבוד עם כל ההגדרות ממקום אחד.
כל הערכים מהסביבה מוחלים כאן.

משתני סביבה (עיקריים):
  SECRET_KEY               – מפתח ל-JWT. אם לא מוגדר – נוצר אקראית ונשמר ב-.storage/secret_key (לא ברירת מחדל קבועה).
  CRM_PROXY_SECRET         – סוד משותף בין הפרוקסי ל-CRM. אם לא מוגדר – נוצר אקראית ונשמר ב-.storage/crm_proxy_secret.
                             כשהפרוקסי וה-CRM רצים על מכונות שונות – חובה להגדיר אותו ידנית בשתיהן.
  TRUSTED_PROXY_IPS        – רשימת IP/CIDR (מופרדת בפסיקים) של פרוקסים מהימנים. רק מהם מכבדים X-Forwarded-For.
                             ברירת מחדל: 127.0.0.1,::1. בייצור – להוסיף את כתובת שרת הפרוקסי ואת ה-reverse proxy של ה-CRM.
                             "none" = לא לסמוך על אף אחד (כך run_cluster.sh מריץ את תהליכי הפרוקסי מאחורי load balancer).
  PROXY_REQUIRE_AUTH       – "1" (ברירת מחדל) = חובה להזדהות מול הפרוקסי. "0" = מותר בלי סיסמה (זיהוי לפי IP בלבד, לפיתוח/רשת סגורה).
  PROXY_AUTH               – (אופציונלי, legacy) שם משתמש:סיסמה משותפים. מי שמתחבר איתם מזוהה לפי שיוך IP.
                             אין יותר ברירת מחדל קבועה. הדרך המומלצת: פרטי התחברות אישיים לכל משתמש (נוצרים ב-CRM).
  FILTER_BIND_BASE_URL     – כתובת דף הקישור (unbound IP). "off"/"0" = כבוי.
  CRM_API_URL              – כתובת API של ה-CRM.
  CRM_FRONTEND_URL         – כתובת פרונט ה-CRM.
  CORS_ALLOW_ORIGINS       – מקורות מותרים ל-CORS (מופרד בפסיקים). ברירת מחדל: כתובת ה-CRM + שרת הפיתוח.
  GOALLM_STORAGE_DIR       – תיקיית אחסון (מאגר, DB). ברירת מחדל: .storage בשורש.
  IMAGE_ANALYZER           – simulated | llama_cpp | openai (שרת תואם OpenAI כמו vLLM / llama-server).
  USE_LLM_IMAGE_ANALYZER   – (legacy) "1" = llama_cpp.
"""
import os
import secrets as _secrets
from pathlib import Path as _Path

# ========== שמות טבלאות (SQLite) ==========
# שם הטבלה שמאחסנת סטטוס תמונות (allowed/blocked/pending) ב־SQLite של הסינון.
IMAGE_STATUS_TABLE_NAME = "image_status"
# שם הטבלה של חוקי ה-URL (דומיין, path, state) במאגר המדיניות.
POLICIES_TABLE_NAME = "url_policies"
# שם הטבלה של חוקי תגיות (tag → state) במאגר המדיניות.
TAG_RULES_TABLE_NAME = "tag_rules"

# ========== פרוקסי / CRM – כתובת בסיס אחת ==========
# אתר ניהול הסינון (CRM) – כתובת בסיס אחת שכוללת:
# - פרונט (ממשק ניהול)
# - API (תחת /api)
# - דף שיוך IP (bind) – אותו דומיין
#
# אפשר להגדיר פעם אחת ב-CRM_BASE_URL, וכל השאר נגזר ממנו.
DEFAULT_CRM_BASE_URL = "https://filter.forum-dev.com"
CRM_BASE_URL = (os.environ.get("CRM_BASE_URL") or DEFAULT_CRM_BASE_URL).strip().rstrip("/")

# ========== אחסון ==========
# אם מוגדר – נתיב תיקיית האחסון (מאגר, DB). אם None – .storage בשורש הפרויקט.
GOALLM_STORAGE_DIR = os.environ.get("GOALLM_STORAGE_DIR")
PROJECT_ROOT = _Path(__file__).resolve().parent.parent
STORAGE_DIR = _Path(GOALLM_STORAGE_DIR) if GOALLM_STORAGE_DIR else PROJECT_ROOT / ".storage"


def _load_or_create_secret(env_name: str, filename: str) -> str:
    """
    סוד מהסביבה, ואם אין – מקובץ ב-STORAGE_DIR, ואם אין – יוצרים אקראי ושומרים (הרשאות 600).
    כך אין אף פעם ערך ברירת מחדל קבוע שידוע לכל מי שקרא את הקוד.
    הפרוקסי וה-CRM על אותה מכונה קוראים את אותו קובץ ולכן מסונכרנים.
    """
    value = (os.environ.get(env_name) or "").strip()
    if value:
        return value
    path = STORAGE_DIR / filename
    try:
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    except FileNotFoundError:
        pass
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    value = _secrets.token_urlsafe(48)
    try:
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(value)
        return value
    except FileExistsError:
        # תהליך אחר (פרוקסי / CRM) יצר את הקובץ במקביל
        return path.read_text(encoding="utf-8").strip()


# סוד משותף בין הפרוקסי ל-CRM (נקודות קצה פנימיות כמו touch-ip).
CRM_PROXY_SECRET = _load_or_create_secret("CRM_PROXY_SECRET", "crm_proxy_secret")

# פרוקסים מהימנים – רק מהם מכבדים X-Forwarded-For / X-Real-IP (IP/CIDR מופרדים בפסיקים).
TRUSTED_PROXY_IPS = (os.environ.get("TRUSTED_PROXY_IPS") or "127.0.0.1,::1").strip()

# אימות מול הפרוקסי. ברירת מחדל: חובה. הזדהות אישית לכל משתמש נוצרת ב-CRM (עמוד "חיבורים").
PROXY_REQUIRE_AUTH = (os.environ.get("PROXY_REQUIRE_AUTH") or "1").strip().lower() not in ("0", "false", "no", "off")
# (legacy) שם משתמש:סיסמה משותפים – מי שמתחבר איתם מזוהה לפי שיוך IP. ריק = כבוי. אין ברירת מחדל קבועה.
PROXY_AUTH = (os.environ.get("PROXY_AUTH") or "").strip()
# מרווח מינימלי (שניות) בין עדכוני last_used_at לאותו IP – מונע בקשת HTTP על כל בקשה.
TOUCH_IP_MIN_INTERVAL_SEC = 300
# כתובת ופורט הפרוקסי כפי שמוצגים למשתמש בעמוד "חיבורים" (להגדרת המכשיר).
PROXY_PUBLIC_HOST = (os.environ.get("PROXY_PUBLIC_HOST") or "").strip()
PROXY_PUBLIC_PORT = int(os.environ.get("PROXY_PUBLIC_PORT", "8080"))

# אתרים רגישים (בנקים, קופות חולים, ממשלה) שעוברים בלי פתיחת ההצפנה (TLS passthrough) – אם הם מותרים ברשימה.
# גם פרטיות (אין סיבה שהשרת יראה סיסמאות בנק) וגם אפליקציות עם certificate pinning שלא עובדות דרך MITM.
# דריסה: SENSITIVE_PASSTHROUGH_DOMAINS="a.co.il,b.co.il" (ריק = כבוי).
_DEFAULT_PASSTHROUGH = (
    "bankhapoalim.co.il,bankleumi.co.il,leumi.co.il,discountbank.co.il,mizrahi-tefahot.co.il,fibi.co.il,"
    "bank-yahav.co.il,mercantile.co.il,bankjerusalem.co.il,onezerobank.com,"
    "clalit.co.il,maccabi4u.co.il,meuhedet.co.il,leumit.co.il,gov.il"
)
SENSITIVE_PASSTHROUGH_DOMAINS = tuple(
    d.strip().lower().lstrip(".")
    for d in (os.environ.get("SENSITIVE_PASSTHROUGH_DOMAINS", _DEFAULT_PASSTHROUGH)).split(",")
    if d.strip()
)

# כתובת דף הקישור (bind) – כברירת מחדל אותה כתובת בסיס של ה-CRM.
# אם FILTER_BIND_BASE_URL מוגדר בסביבה – הוא יגבר; אם "off"/"0"/"false" – אין דף bind.
_raw_bind = (os.environ.get("FILTER_BIND_BASE_URL") or CRM_BASE_URL).strip().rstrip("/")
FILTER_BIND_BASE_URL = None if _raw_bind.lower() in ("off", "0", "false", "") else _raw_bind

# כתובת ה־host של דף אבחון הסינון – גישה דרך הפרוקסי מפנה ל־CRM/diagnostic.
FILTER_DIAGNOSTIC_HOST = "1.2.3.4"
FILTER_DIAGNOSTIC_HOST_ALIAS = "filter.check"

# תיקיית תעודות mitmproxy (להגשת הורדת תעודה מדף האבחון ב־CRM). ברירת מחדל: ~/.mitmproxy
FILTER_CERT_DIR = os.environ.get("FILTER_CERT_DIR") or os.path.expanduser("~/.mitmproxy")

# קוד HTTP לתגובות חסימה / שלח לבדיקה – מחזירים דף HTML עם קוד זה (418 = I'm a teapot, לא בשימוש סטנדרטי).
FILTER_BLOCKED_OR_REVIEW_HTTP_STATUS = 418

# ========== כתובות CRM (API ופרונט) ==========
# ערכים אפקטיביים – מסביבה או נגזרים מ-CRM_BASE_URL.
# ניתן עדיין לדרוס כל אחד מהם בנפרד במקרה הצורך.
CRM_API_URL = (os.environ.get("CRM_API_URL") or f"{CRM_BASE_URL}/api").rstrip("/")
CRM_FRONTEND_URL = (os.environ.get("CRM_FRONTEND_URL") or CRM_BASE_URL).rstrip("/")

# מקורות מותרים ל-CORS. האימות הוא Bearer token (לא cookie), אבל אין סיבה לאפשר לכל אתר לקרוא ל-API.
CORS_ALLOW_ORIGINS = tuple(
    o.strip().rstrip("/")
    for o in (os.environ.get("CORS_ALLOW_ORIGINS") or f"{CRM_FRONTEND_URL},http://localhost:5173,http://127.0.0.1:5173").split(",")
    if o.strip()
)

# ========== שרתים (ברירת מחדל להרצה) ==========
# כתובת להאזנה כשמריצים את ה-API (למשל 0.0.0.0 לגישה מהרשת).
DEFAULT_API_HOST = "0.0.0.0"
# פורט להאזנה של ה-API (FastAPI).
DEFAULT_API_PORT = 8000

# ========== אבטחה (JWT, סיסמאות) ==========
# מספר סיבובי bcrypt להצפנת סיסמאות – גבוה יותר = מאובן יותר אבל איטי יותר.
BCRYPT_ROUNDS = 12
# מפתח JWT – מהסביבה או אקראי שנשמר ב-.storage/secret_key (אין ברירת מחדל קבועה שאפשר לזייף איתה טוקן).
SECRET_KEY = _load_or_create_secret("SECRET_KEY", "secret_key")
# אלגוריתם חתימת JWT.
ALGORITHM = "HS256"
# תוקף טוקן הגישה בדקות – אחרי הזמן הזה המשתמש צריך להתחבר מחדש.
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 ימים

# ========== פרטיות ==========
# כמה ימים לשמור יומני הקלטת תעבורה (כתובות מלאות). 0 = לא למחוק אוטומטית.
TRAFFIC_LOG_RETENTION_DAYS = int(os.environ.get("TRAFFIC_LOG_RETENTION_DAYS", "30"))

# המשתמש הראשון שנרשם הופך למנהל. בייצור מומלץ 0 ולמנות מנהל עם: python -m crm.manage set-admin <phone>
FIRST_USER_ADMIN = (os.environ.get("GOALLM_FIRST_USER_ADMIN") or "1").strip().lower() not in ("0", "false", "no", "off")

# ========== אימות (OTP) ==========
# אורך קוד האימות (ספרות) שנשלח בטלפון/אימייל.
CODE_LENGTH = 6
# תוקף קוד האימות בדקות – אחרי הזמן הזה הקוד לא תקף.
CODE_EXPIRE_MINUTES = 10
# מרווח מינימלי בדקות בין שליחת קוד לאותו יעד (מגבלת קצב).
RATE_LIMIT_MINUTES = 2
# מקסימום ניסיונות שגויים לקוד אחד – אחרי זה הקוד נמחק (מונע ניחוש של 10^6 אפשרויות).
CODE_MAX_ATTEMPTS = 5
# שליחת הקוד. אימייל: SMTP. SMS: twilio | webhook (ספק ישראלי דרך מתאם HTTP קטן) | none.
# בלי ספק מוגדר – כניסה עם קוד לא זמינה (הקוד כבר לא נכתב ללוג). לפיתוח בלבד: OTP_DEV_LOG_CODES=1.
SMTP_HOST = (os.environ.get("SMTP_HOST") or "").strip()
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = (os.environ.get("SMTP_USER") or "").strip()
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD") or ""
SMTP_FROM = (os.environ.get("SMTP_FROM") or SMTP_USER).strip()
SMTP_SECURITY = (os.environ.get("SMTP_SECURITY") or "starttls").strip().lower()  # starttls | ssl | none
SMS_PROVIDER = (os.environ.get("SMS_PROVIDER") or "none").strip().lower()
TWILIO_ACCOUNT_SID = (os.environ.get("TWILIO_ACCOUNT_SID") or "").strip()
TWILIO_AUTH_TOKEN = (os.environ.get("TWILIO_AUTH_TOKEN") or "").strip()
TWILIO_FROM = (os.environ.get("TWILIO_FROM") or "").strip()
SMS_WEBHOOK_URL = (os.environ.get("SMS_WEBHOOK_URL") or "").strip()
SMS_WEBHOOK_TOKEN = (os.environ.get("SMS_WEBHOOK_TOKEN") or "").strip()
OTP_DEV_LOG_CODES = (os.environ.get("OTP_DEV_LOG_CODES") or "0").strip().lower() in ("1", "true", "yes", "on")

# ========== תמונות – ניתוח ותור ==========
# (legacy) USE_LLM_IMAGE_ANALYZER=1 שווה ל-IMAGE_ANALYZER=llama_cpp.
USE_LLM_IMAGE_ANALYZER = (os.environ.get("USE_LLM_IMAGE_ANALYZER") or "").strip().lower() in ("1", "true", "yes")
# איזה מנתח תמונות להפעיל:
#   simulated – לפיתוח בלבד (תוצאה פסאודו-אקראית!)
#   llama_cpp – מודל GGUF מקומי (בקשה אחת בכל רגע; מתאים לבדיקות, לא לעומס)
#   openai    – שרת תואם OpenAI: vLLM / SGLang / llama-server / ספק ענן. זו הדרך לייצור (batching, מקביליות).
IMAGE_ANALYZER = (os.environ.get("IMAGE_ANALYZER") or ("llama_cpp" if USE_LLM_IMAGE_ANALYZER else "simulated")).strip().lower()
# שרת VLM תואם OpenAI (למשל vLLM: http://127.0.0.1:8001/v1)
VLM_API_BASE = (os.environ.get("VLM_API_BASE") or "http://127.0.0.1:8001/v1").strip().rstrip("/")
# ברירת מחדל: Qwen3.5-9B (Apache-2.0). ב-V* (פרטים קטנים בתמונה ברזולוציה גבוהה) 90.1 מול 83.2 של Qwen3-VL-30B
# ו-69.6 של Gemini-2.5-Flash-Lite – בדיוק המקרה הקשה של דמות קטנה ברקע.
VLM_MODEL = (os.environ.get("VLM_MODEL") or "Qwen/Qwen3.5-9B").strip()
# מודלים "חושבים" (Qwen3.5) מוסיפים טקסט חשיבה לפני התשובה – כבוי כברירת מחדל (מהירות ועלות). vLLM/SGLang מכבדים זאת.
VLM_DISABLE_THINKING = (os.environ.get("VLM_DISABLE_THINKING") or "1").strip().lower() not in ("0", "false", "no", "off")
VLM_API_KEY = (os.environ.get("VLM_API_KEY") or "").strip()
VLM_TIMEOUT_SECONDS = float(os.environ.get("VLM_TIMEOUT_SECONDS", "60"))
# סף א-סימטרי: אם ההסתברות של "Yes" בשאלה כלשהי ≥ הסף – נחשב Yes (חוסם). החמצה חמורה מחסימת-שווא.
# עובד רק כשהשרת מחזיר logprobs (vLLM כן). 0.5 = התנהגות רגילה; נמוך יותר = שמרני יותר.
VLM_YES_THRESHOLD = float(os.environ.get("VLM_YES_THRESHOLD", "0.2"))
# רזולוציה: צלע ארוכה מקסימלית שנשלחת למודל (אנשים קטנים ברקע צריכים רזולוציה – זה המחיר בטוקנים).
VLM_MAX_SIDE = int(os.environ.get("VLM_MAX_SIDE", "1280"))
# תמונות קטנות מוגדלות לפחות לגודל הזה בצלע הקצרה – אחרת המודל לא "רואה" אותן.
VLM_MIN_SIDE = int(os.environ.get("VLM_MIN_SIDE", "256"))
# כמה פריימים לדגום מתמונה מונפשת (GIF/WebP/APNG). כל פריים = קריאה נפרדת למודל.
VLM_MAX_ANIMATION_FRAMES = int(os.environ.get("VLM_MAX_ANIMATION_FRAMES", "4"))
# אזור "לא בטוח": אם P(Yes) הגבוה בין הסף הזה לבין VLM_YES_THRESHOLD – התמונה לא נפתחת אלא עוברת לתור בדיקה אנושית.
# 0 = כבוי (המודל מכריע לבד). עובד רק כשהשרת מחזיר logprobs.
VLM_REVIEW_LOW = float(os.environ.get("VLM_REVIEW_LOW", "0.05"))

# ========== וידאו – בדיקת סרטון בודד ==========
# כמה פריימים לשנייה לדגום (1–2 מספיק לפי הדרישה).
VIDEO_FPS = float(os.environ.get("VIDEO_FPS", "1"))
# זיהוי שינוי: הפריים מוקטן לרוחב הזה, מחולק לאריחים בגודל VIDEO_CHANGE_TILE_PX, ומושווה לפריים האחרון שנבדק.
VIDEO_CHANGE_WIDTH = int(os.environ.get("VIDEO_CHANGE_WIDTH", "320"))
VIDEO_CHANGE_TILE_PX = int(os.environ.get("VIDEO_CHANGE_TILE_PX", "16"))
# פיקסל "השתנה" אם ההפרש שלו (0–255, אחרי טשטוש קל שמסנן רעש דחיסה) ≥ הערך הזה.
VIDEO_CHANGE_PIXEL_DELTA = int(os.environ.get("VIDEO_CHANGE_PIXEL_DELTA", "28"))
# אריח "השתנה" אם לפחות החלק הזה מהפיקסלים שלו השתנה, או שההפרש הממוצע בו ≥ VIDEO_CHANGE_TILE_MEAN.
# אריח אחד שהשתנה מספיק כדי לשלוח את הפריים לבדיקה.
VIDEO_CHANGE_TILE_FRACTION = float(os.environ.get("VIDEO_CHANGE_TILE_FRACTION", "0.03"))
VIDEO_CHANGE_TILE_MEAN = float(os.environ.get("VIDEO_CHANGE_TILE_MEAN", "10"))
# רשת ביטחון: בודקים פריים לפחות פעם בכך וכך שניות גם אם לא זוהה שינוי.
VIDEO_FORCE_ANALYZE_SEC = float(os.environ.get("VIDEO_FORCE_ANALYZE_SEC", "15"))
# סרטון ארוך מזה לא נבדק אוטומטית (עלות). שידור חי לא ניתן לבדיקה מראש.
VIDEO_MAX_DURATION_SEC = int(os.environ.get("VIDEO_MAX_DURATION_SEC", "7200"))
# רזולוציית הפריים שנשלח למודל (צלע ארוכה).
VIDEO_FRAME_MAX_SIDE = int(os.environ.get("VIDEO_FRAME_MAX_SIDE", "1280"))
# ========== אפליקציות עם certificate pinning (אנדרואיד / iOS) ==========
# אפליקציה שלא סומכת על תעודת הפרוקסי נכשלת. 1 = אחרי AUTO_PASSTHROUGH_MIN_FAILURES כישלונות לאותו דומיין,
# אם האתר מותר במפורש ברשימה של המשתמש – החיבור עובר בלי פתיחת ההצפנה (התוכן בתוכו לא מסונן!).
# 0 (ברירת מחדל) = האפליקציה פשוט לא עובדת. החלטה שלכם: עדיף שבור או לא מסונן באתרים שאישרתם.
AUTO_PASSTHROUGH_PINNED_APPS = (os.environ.get("AUTO_PASSTHROUGH_PINNED_APPS") or "0").strip().lower() in ("1", "true", "yes", "on")
AUTO_PASSTHROUGH_MIN_FAILURES = int(os.environ.get("AUTO_PASSTHROUGH_MIN_FAILURES", "2"))

# ========== סינון מלל – ניקוד (בלי מודל שפה) ==========
# משקל ברירת מחדל של מילה קשה (blocked.txt) – לפחות פי 2 מכל מילה חשודה (scored.txt, המשקל כתוב ליד כל מילה).
TEXT_HARD_WEIGHT = float(os.environ.get("TEXT_HARD_WEIGHT", "8"))
# כלל אחד בכל רמה – משפט, רכיב (כותרת / תוצאת חיפוש / כתבה / תגובה / פסקה / רשימה), קטע (רצף מילים) ודף:
# יחידה "חמה" כשהניקוד שלה ל-TEXT_DENSITY_WORDS מילים ≥ TEXT_DENSITY_SCORE. יחידה קצרה נספרת כאילו היא באורך
# TEXT_DENSITY_WORDS (מילה חשודה אחת בכותרת קצרה אינה "צפיפות"). משפט / רכיב / קטע חם הופך ל-X.
TEXT_DENSITY_WORDS = int(os.environ.get("TEXT_DENSITY_WORDS", "250"))
TEXT_DENSITY_SCORE = float(os.environ.get("TEXT_DENSITY_SCORE", "12"))
# הדף נחסם לפי יחס: כשחלק כזה ממנו הפך ל-X, או כשמה שנשאר בטקסט שלו אחרי ה-X (בלי קישורים – אותם שופטים
# בדף שהם מובילים אליו) עדיין בצפיפות כזו ל-TEXT_DENSITY_WORDS מילים ומצטבר לפחות ל-TEXT_DENSITY_SCORE:
# כתבה שכל-כולה בנושא, לא כמה תוצאות / כתבות / תגובות בעייתיות בדף.
TEXT_PAGE_HIDDEN_SHARE = float(os.environ.get("TEXT_PAGE_HIDDEN_SHARE", "0.25"))
TEXT_PAGE_DENSITY_SCORE = float(os.environ.get("TEXT_PAGE_DENSITY_SCORE", "3"))
# 3 מילים שונות ויותר יחד → הניקוד מוכפל.
TEXT_DIVERSITY_BONUS = float(os.environ.get("TEXT_DIVERSITY_BONUS", "1.3"))
# הקשר תורני (context.txt): לפחות כך וכך סמנים, ובצפיפות של לפחות כך וכך ל-1000 מילים → מילים חשודות (לא קשות)
# שוקלות רק TEXT_CONTEXT_FACTOR.
TEXT_CONTEXT_FACTOR = float(os.environ.get("TEXT_CONTEXT_FACTOR", "0.3"))
TEXT_CONTEXT_MIN_MARKERS = int(os.environ.get("TEXT_CONTEXT_MIN_MARKERS", "3"))
TEXT_CONTEXT_MIN_DENSITY = float(os.environ.get("TEXT_CONTEXT_MIN_DENSITY", "4"))
# הקשר רפואי (medical.txt) – אותו כלל, הפחתה חלשה יותר (מאמר על סרטן השד, לא "חינוך מיני" בתחפושת רפואית).
TEXT_MEDICAL_FACTOR = float(os.environ.get("TEXT_MEDICAL_FACTOR", "0.6"))
TEXT_TITLE_FACTOR = float(os.environ.get("TEXT_TITLE_FACTOR", "1.5"))

# ========== בדיקת תיאור הסרטון (לפני הפריימים) ==========
# מודל השפה (VLM_API_BASE) קורא כותרת, תיאור, ערוץ ותגיות לפני שמורידים פריים אחד. יכול רק לחסום, לא לאשר.
# auto (ברירת מחדל) = פעיל כש-IMAGE_ANALYZER=openai (יש שרת מודל). 1 = תמיד, 0 = כבוי.
_desc = (os.environ.get("VIDEO_DESCRIPTION_CHECK") or "auto").strip().lower()
VIDEO_DESCRIPTION_CHECK = (IMAGE_ANALYZER == "openai") if _desc == "auto" else _desc in ("1", "true", "yes", "on")
# חוסם כש-P(כן) ≥ הסף (א-סימטרי, כמו בתמונות).
DESCRIPTION_YES_THRESHOLD = float(os.environ.get("DESCRIPTION_YES_THRESHOLD", str(VLM_YES_THRESHOLD)))
DESCRIPTION_MAX_CHARS = int(os.environ.get("DESCRIPTION_MAX_CHARS", "4000"))

# יוטיוב: הבודק מוריד דרך yt-dlp. משרתי ענן יוטיוב מבקש לפעמים "אישור שאינך בוט" –
# אז צריך קובץ עוגיות (Netscape cookies.txt של חשבון ייעודי) ו/או פרוקסי ביתי.
YTDLP_COOKIES_FILE = (os.environ.get("YTDLP_COOKIES_FILE") or "").strip() or None
YTDLP_PROXY = (os.environ.get("YTDLP_PROXY") or "").strip() or None
# רזולוציה מקסימלית להורדה לבדיקה (גובה). 720 מספיק לדמות קטנה ברקע; יותר = יותר תעבורה.
VIDEO_YTDLP_MAX_HEIGHT = int(os.environ.get("VIDEO_YTDLP_MAX_HEIGHT", "720"))

# מקסימום משימות שמחכות בתור (מעבר לזה – לא נכנסות, והבקשה הבאה לאותה תמונה תנסה שוב).
IMAGE_QUEUE_MAX = int(os.environ.get("IMAGE_QUEUE_MAX", "5000"))
# תמונה שנשארה pending יותר מזה (למשל אחרי הפעלה מחדש – התור יושב בזיכרון) נשלחת שוב לבדיקה.
PENDING_STALE_SECONDS = int(os.environ.get("PENDING_STALE_SECONDS", "300"))
# תמונה בסטטוס error נשלחת שוב אחרי הזמן הזה, עד MAX_ANALYSIS_ATTEMPTS ניסיונות (אחר כך נשארת חסומה).
ERROR_RETRY_SECONDS = int(os.environ.get("ERROR_RETRY_SECONDS", "600"))
MAX_ANALYSIS_ATTEMPTS = int(os.environ.get("MAX_ANALYSIS_ATTEMPTS", "3"))

# timeout בשניות להמתנה לתוצאת ניתוח תמונה לפני שמסמנים שגיאה.
DEFAULT_ANALYSIS_TIMEOUT_SECONDS = 120
# מרווח בשניות בין בדיקות Watchdog על משימות תקועות בתור.
WATCHDOG_INTERVAL_SECONDS = 30
# מספר workers במקביל בתור ניתוח התמונות. 1000 גרם להפעלה איטית של mitmproxy (pending).
# ניתן לדרוס עם משתנה סביבה IMAGE_MAX_WORKERS.
DEFAULT_MAX_WORKERS = int(os.environ.get("IMAGE_MAX_WORKERS", "16"))

# צלע מקסימלית (פיקסלים) לתמונה לפני חישוב hash – חוסך זיכרון ו-CPU.
MAX_SIDE_FOR_HASH = 1024
# איכות JPEG בקנוניזציה לפני hash – קבועה כדי hash דטרמיניסטי.
JPEG_QUALITY = 90
# מקסימום תמונות מוטמעות (data: URL) לעיבוד בדף אחד – מונע עומס.
# מעבר לכך – placeholder אפור בלי בדיקה (אף פעם לא המקור). דפי חיפוש תמונות מכילים מאות תמונות ממוזערות.
MAX_EMBEDDED_IMAGES_PER_PAGE = int(os.environ.get("MAX_EMBEDDED_IMAGES_PER_PAGE", "300"))

# ========== סינון מלל – רמה אחת, חסימה לפי יחס ==========
# רמה אחת: מילה ברשימה = תוכן לא צנוע. חסימת דף תמיד לפי יחס על כל הדף/מסמך.

# יחס מילים (טקסט גולמי / PDF מלא): מילים_שנמצאו / סה"כ_מילים
MIN_RATIO_WORDS_FOR_PAGE_BLOCK = 0.02  # 2%
# מינימום מילים שנמצאו (לטקסט גולמי) – מונע חסימה על מסמך עם מילה אחת
MIN_MATCHES_FOR_PAGE_BLOCK = 2
# מסמך קצר (עד N מילים): חסימה לפי count בלבד. מסמך ארוך: לפי ratio.
MIN_WORDS_FOR_RATIO_BLOCK = 80

# אחוז מינימלי רכיבים/בלוקים עם זיהוי (HTML, PDF) – יחס על כל הדף
MIN_PERCENTAGE_COMPONENTS_FOR_PAGE_BLOCK = 0.25  # 25%
# מינימום מספר רכיבים עם זיהוי – מונע חסימה על דף עם רכיב אחד בלבד
MIN_COMPONENTS_WITH_DETECTION_FOR_PAGE_BLOCK = 3

# קודי שפה נתמכות – תואמות לתיקיות ב־word_lists (he, en)
SUPPORTED_LANGS = ("he", "en")

# דומיינים של אתרי שיתוף קבצים ציבוריים – קישור ציבורי חסום עד בדיקה ("שלח לבדיקה").
# רשימת דומיינים (ללא www) – גוגל דרייב, דרופבוקס, OneDrive וכו'.
# Hosts are matched after lowercasing and stripping www.
PUBLIC_FILE_SHARE_DOMAINS = (
    "drive.google.com",
    "docs.google.com",
    "dropbox.com",
    "onedrive.live.com",
    "1drv.ms",
    "sharepoint.com",
    "we.tl",
    "wetransfer.com",
    "send.any.run",
    "file.io",
    "transfer.sh",
    "tmpfiles.org",
)
