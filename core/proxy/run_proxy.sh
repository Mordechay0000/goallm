#!/usr/bin/env bash
# הפעלת הפרוקסי.
# אימות: ה-addon עצמו מאמת כל חיבור.
#   - פרטי התחברות אישיים לכל משתמש (נוצרים ב-CRM, עמוד "חיבורים") – מומלץ; מזהה לפי משתמש ולא לפי IP.
#   - PROXY_AUTH=user:pass – (אופציונלי, legacy) סיסמה משותפת; מי שמתחבר איתה מזוהה לפי שיוך IP.
#   - PROXY_REQUIRE_AUTH=0 – בלי סיסמה בכלל (זיהוי לפי IP בלבד; לפיתוח / רשת סגורה בלבד).
# אין יותר סיסמת ברירת מחדל קבועה.
#
# שימוש: ./run_proxy.sh [mitmproxy|mitmweb|mitmdump] [ארגומנטים נוספים ל-mitmproxy]
# בייצור: הגדירו TRUSTED_PROXY_IPS, CRM_PROXY_SECRET (אם ה-CRM על מכונה אחרת), IMAGE_ANALYZER=openai ו-VLM_API_BASE.

set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

TOOL="${1:-mitmproxy}"
shift || true

# טעינת venv אם קיים
if [ -f "venv/bin/activate" ]; then
  source venv/bin/activate
fi

exec "$TOOL" -s core/proxy/mitmproxy_addon.py "$@"
