"""
קבועים כלליים של התוכנית – ערכים שאפשר לשנות לפי צורך (כתובות, דגלים, שמות טבלאות).
מאוחד כאן כדי שיהיה קל לעבוד עם כל ההגדרות ממקום אחד.
"""

# --- שמות טבלאות (SQLite) ---
IMAGE_STATUS_TABLE_NAME = "image_status"
POLICIES_TABLE_NAME = "url_policies"
TAG_RULES_TABLE_NAME = "tag_rules"


# --- פרוקסי / CRM (ברירת מחדל; ניתן לדרוס עם משתני סביבה) ---
DEFAULT_CRM_PROXY_SECRET = "dev-secret"
DEFAULT_FILTER_BIND_BASE_URL = "http://localhost:5173"
# תוקף טוקן Surf (שניות) – אימות משתמש מפרוקסי ל-CRM
SURF_TOKEN_TTL_SEC = 300

# --- שרתים (ברירת מחדל להרצה) ---
DEFAULT_API_HOST = "127.0.0.1"
DEFAULT_API_PORT = 8000
DEFAULT_FLASK_HOST = "127.0.0.1"
DEFAULT_FLASK_PORT = 5000
