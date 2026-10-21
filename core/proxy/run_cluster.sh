#!/usr/bin/env bash
# כמה תהליכי mitmdump על אותה מכונה, מאחורי load balancer של TCP (nginx stream / HAProxy).
# mitmproxy מעבד כל זרימה ב-event loop אחד ומחזיק GIL אחד – תהליך אחד מנצל בערך ליבה אחת.
#
# שימוש:
#   bash core/proxy/run_cluster.sh start   [N] [BASE_PORT]   # ברירת מחדל: N = מספר הליבות, BASE_PORT = 8081
#   bash core/proxy/run_cluster.sh stop
#   bash core/proxy/run_cluster.sh status
#   bash core/proxy/run_cluster.sh restart [N] [BASE_PORT]
#
# התהליכים מאזינים על 127.0.0.1:BASE_PORT … BASE_PORT+N-1; ה-load balancer מאזין לגולשים (למשל 8080).
# דוגמאות הגדרה: docs/deploy/SCALE.he.md
#
# חשוב:
# - מאחורי load balancer של TCP הפרוקסי רואה את כתובת ה-balancer, לא של הגולש, ולחיבור HTTPS אין כותרת
#   X-Forwarded-For. לכן זיהוי לפי IP לא עובד כאן – רק פרטי התחברות אישיים (עמוד "חיבורים" ב-CRM).
#   הסקריפט מסרב לעלות עם PROXY_REQUIRE_AUTH=0 או עם סיסמה משותפת (PROXY_AUTH).
# - כל התהליכים חייבים אותה תעודת CA (confdir משותף). אם עוד אין CA – התהליך הראשון יוצר אותה, והשאר
#   עולים רק אחריו (אחרת כמה תהליכים במקביל היו יוצרים כמה תעודות שונות).
# - כל תהליך מריץ תור ניתוח תמונות משלו (IMAGE_MAX_WORKERS בקשות במקביל לשרת ה-VLM). סה"כ = N × IMAGE_MAX_WORKERS.

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

CMD="${1:-status}"
N="${2:-${PROXY_WORKERS:-$(nproc 2>/dev/null || echo 2)}}"
BASE_PORT="${3:-${PROXY_BASE_PORT:-8081}}"
LISTEN_HOST="${PROXY_LISTEN_HOST:-127.0.0.1}"
CONFDIR="${MITM_CONFDIR:-$HOME/.mitmproxy}"
RUN_DIR="${GOALLM_STORAGE_DIR:-$ROOT/.storage}/run"
mkdir -p "$RUN_DIR"

if [ -f "venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi

pid_alive() { [ -n "${1:-}" ] && kill -0 "$1" 2>/dev/null; }

start_one() {
  local i="$1" port=$((BASE_PORT + $1))
  local pidfile="$RUN_DIR/mitm-$i.pid" logfile="$RUN_DIR/mitm-$i.log"
  if [ -f "$pidfile" ] && pid_alive "$(cat "$pidfile")"; then
    echo "worker $i already running (pid $(cat "$pidfile"), port $port)"
    return
  fi
  nohup mitmdump -q -s core/proxy/mitmproxy_addon.py \
    --listen-host "$LISTEN_HOST" --listen-port "$port" --set confdir="$CONFDIR" \
    >>"$logfile" 2>&1 &
  echo $! >"$pidfile"
  echo "worker $i started (pid $!, $LISTEN_HOST:$port, log $logfile)"
}

start() {
  if [ "${PROXY_REQUIRE_AUTH:-1}" = "0" ] || [ -n "${PROXY_AUTH:-}" ]; then
    echo "Refusing to start: behind a TCP load balancer every client has the balancer's IP." >&2
    echo "Use personal proxy credentials only (unset PROXY_AUTH, keep PROXY_REQUIRE_AUTH=1)." >&2
    exit 1
  fi
  command -v mitmdump >/dev/null || { echo "mitmdump not found (bash setup.sh)" >&2; exit 1; }
  # The balancer (127.0.0.1) never adds X-Forwarded-For to a TCP stream. Trusting it would let a client put
  # its own forged X-Forwarded-For on a plain-HTTP request and have it believed. Trust nobody here.
  export TRUSTED_PROXY_IPS="${CLUSTER_TRUSTED_PROXY_IPS:-none}"
  local first=0
  if [ ! -f "$CONFDIR/mitmproxy-ca.pem" ]; then
    echo "No CA in $CONFDIR yet – starting worker 0 first so it creates one"
    start_one 0
    for _ in $(seq 1 30); do
      [ -f "$CONFDIR/mitmproxy-ca.pem" ] && break
      sleep 1
    done
    [ -f "$CONFDIR/mitmproxy-ca.pem" ] || { echo "CA was not created – see $RUN_DIR/mitm-0.log" >&2; exit 1; }
    first=1
  fi
  for i in $(seq "$first" $((N - 1))); do
    start_one "$i"
  done
}

stop() {
  local any=0
  for pidfile in "$RUN_DIR"/mitm-*.pid; do
    [ -f "$pidfile" ] || continue
    any=1
    local pid
    pid="$(cat "$pidfile")"
    if pid_alive "$pid"; then
      kill "$pid" && echo "stopped pid $pid ($(basename "$pidfile" .pid))"
    fi
    rm -f "$pidfile"
  done
  [ "$any" = 1 ] || echo "no workers running"
}

status() {
  local any=0
  for pidfile in "$RUN_DIR"/mitm-*.pid; do
    [ -f "$pidfile" ] || continue
    any=1
    local pid
    pid="$(cat "$pidfile")"
    if pid_alive "$pid"; then
      echo "$(basename "$pidfile" .pid): running (pid $pid)"
    else
      echo "$(basename "$pidfile" .pid): DEAD (stale pid $pid)"
    fi
  done
  [ "$any" = 1 ] || echo "no workers running"
}

case "$CMD" in
  start) start ;;
  stop) stop ;;
  status) status ;;
  restart) stop; sleep 1; start ;;
  *) echo "usage: $0 start|stop|status|restart [N] [BASE_PORT]" >&2; exit 2 ;;
esac
