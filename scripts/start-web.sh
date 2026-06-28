#!/usr/bin/env bash
# Start LU web backend (FastAPI :8000) and frontend (Next.js :3000) under a
# supervisor. Each service is auto-restarted on crash; logs land in .api.log /
# .web.log; PID files at the project root point at the supervisor.
#
# Usage:
#   scripts/start-web.sh            # PROD: build the web app, then serve (changes take effect)
#   scripts/start-web.sh --dev      # DEV: hot-reload (uvicorn --reload + next dev), no build
#   scripts/start-web.sh --force    # kill whatever holds :8000/:3000 first (default: also done)
#
# Open http://localhost:3000 afterwards. If the page looks stale, hard-refresh
# (Ctrl/Cmd+Shift+R) — production serves a build snapshot and the browser caches.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WEB_DIR="$ROOT/apps/web"

API_PORT="${LU_API_PORT:-8000}"
WEB_PORT="${LU_WEB_PORT:-3000}"
API_PID="$ROOT/.api.pid"; WEB_PID="$ROOT/.web.pid"
API_LOG="$ROOT/.api.log"; WEB_LOG="$ROOT/.web.log"

export PATH="$HOME/.local/bin:$PATH"   # uv lives here, not on default PATH

g() { printf '\033[32m%s\033[0m\n' "$*"; }
r() { printf '\033[31m%s\033[0m\n' "$*"; }
d() { printf '\033[2m%s\033[0m\n' "$*"; }

port_pid() { ss -ltnp 2>/dev/null | awk -v p=":$1" '$4 ~ p"$"' | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2; }

# ── Internal crash-restart supervisor (re-exec of this script) ──
if [ "${1:-}" = "__supervise" ]; then
  LABEL="$2"; LOG="$3"; shift 3; [ "${1:-}" = "--" ] && shift
  SHUTTING=0
  trap 'SHUTTING=1; [ -n "${CHILD:-}" ] && kill -TERM "-$CHILD" 2>/dev/null' TERM INT HUP
  printf '\n[%s] supervisor up (pid=%s) %s\n' "$LABEL" "$$" "$(date "+%F %T")" >>"$LOG"
  fails=0
  while [ "$SHUTTING" -eq 0 ]; do
    setsid "$@" >>"$LOG" 2>&1 &
    CHILD=$!; wait "$CHILD"; code=$?
    [ "$SHUTTING" -eq 1 ] && break
    printf '\n[%s] exited (code=%s), restarting…\n' "$LABEL" "$code" >>"$LOG"
    fails=$((fails+1)); [ "$fails" -ge 5 ] && { sleep 15; fails=0; } || sleep 2
  done
  exit 0
fi

DEV=0
for a in "$@"; do [ "$a" = "--dev" ] && DEV=1; done  # --force is implied; we always free our own ports

# Free our ports (stop anything already listening — almost always our own stale run).
"$SCRIPT_DIR/stop-web.sh" >/dev/null 2>&1 || true

start_one() {  # name pidfile logfile -- cmd...
  local name="$1" pidf="$2" logf="$3"; shift 3; [ "${1:-}" = "--" ] && shift
  setsid bash "$SCRIPT_DIR/start-web.sh" __supervise "$name" "$logf" -- "$@" >/dev/null 2>&1 &
  echo $! >"$pidf"
  g "  $name started (supervisor pid $(cat "$pidf"))"
}

if [ "$DEV" -eq 1 ]; then
  d "starting in DEV mode (hot-reload, no build)…"
  start_one API "$API_PID" "$API_LOG" -- uv run uvicorn luapi.main:app --app-dir apps/api --reload --port "$API_PORT"
  start_one WEB "$WEB_PID" "$WEB_LOG" -- bash -c "cd '$WEB_DIR' && exec npx --no-install next dev -p $WEB_PORT"
else
  d "building web (prod)…"
  ( cd "$WEB_DIR" && npm run build ) || { r "web build failed — not starting"; exit 1; }
  g "web build ok"
  d "starting in PROD mode…"
  start_one API "$API_PID" "$API_LOG" -- uv run uvicorn luapi.main:app --app-dir apps/api --port "$API_PORT"
  start_one WEB "$WEB_PID" "$WEB_LOG" -- bash -c "cd '$WEB_DIR' && exec npx --no-install next start -p $WEB_PORT"
fi

d "waiting for services…"
ok=0
for _ in $(seq 1 40); do
  sleep 1
  if curl -fs -o /dev/null "http://localhost:$API_PORT/health" 2>/dev/null \
     && curl -fs -o /dev/null "http://localhost:$WEB_PORT/watchlist" 2>/dev/null; then ok=1; break; fi
done
echo
echo "API  :$API_PORT  $( [ -n "$(port_pid "$API_PORT")" ] && g 'UP' || r 'DOWN' )"
echo "WEB  :$WEB_PORT  $( [ -n "$(port_pid "$WEB_PORT")" ] && g 'UP' || r 'DOWN' )"
if [ "$ok" -eq 1 ]; then g "LU is up → http://localhost:$WEB_PORT  (硬刷新 Ctrl/Cmd+Shift+R)"
else r "services slow to respond — check .api.log / .web.log"; fi
