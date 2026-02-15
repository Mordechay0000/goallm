#!/usr/bin/env bash
# הפעלת הפרוקסי עם אימות (שם משתמש וסיסמה).
# להגדרת פרוקסי: הפעילו סקריפט זה. בדפדפן/מערכת הגדירו proxy ל־127.0.0.1:8080.
# בפעם הראשונה הדפדפן יבקש שם משתמש (filter) וסיסמה (f123456Ab).
#
# שימוש: ./run_proxy.sh [mitmproxy|mitmweb|mitmdump]
# דריסת פרטי אימות: PROXY_AUTH=user:pass ./run_proxy.sh
# ביטול אימות: PROXY_AUTH= ./run_proxy.sh

set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

TOOL="${1:-mitmproxy}"
shift || true

# טעינת venv אם קיים
if [ -f "venv/bin/activate" ]; then
  source venv/bin/activate
fi

PROXY_AUTH="${PROXY_AUTH:-filter:f123456Ab}"

if [ -n "$PROXY_AUTH" ]; then
  exec "$TOOL" -s core/proxy/mitmproxy_addon.py --set "proxyauth=$PROXY_AUTH" "$@"
else
  exec "$TOOL" -s core/proxy/mitmproxy_addon.py "$@"
fi
