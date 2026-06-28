#!/usr/bin/env bash
# Stop LU web backend (:8000) and frontend (:3000).
#
# Strategy: kill the supervisor named in the PID file (prevents respawn) and its
# whole process group; then, as a fallback, free the expected ports.
#
# Usage:  scripts/stop-web.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

API_PORT="${LU_API_PORT:-8000}"
WEB_PORT="${LU_WEB_PORT:-3000}"
API_PID="$ROOT/.api.pid"; WEB_PID="$ROOT/.web.pid"; CF_PID="$ROOT/.cf.pid"

port_pid() { ss -ltnp 2>/dev/null | awk -v p=":$1" '$4 ~ p"$"' | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2; }

stop_one() {  # name pidfile port
  local name="$1" pidf="$2" port="$3" sp lp
  if [ -f "$pidf" ]; then
    sp="$(cat "$pidf" 2>/dev/null)"
    if [ -n "$sp" ] && kill -0 "$sp" 2>/dev/null; then
      kill -TERM "$sp" 2>/dev/null            # supervisor (stops respawn)
      kill -TERM "-$sp" 2>/dev/null || true   # its process group (the worker)
    fi
    rm -f "$pidf"
  fi
  lp="$(port_pid "$port")"; [ -n "$lp" ] && kill -TERM "$lp" 2>/dev/null || true
  sleep 1
  lp="$(port_pid "$port")"; [ -n "$lp" ] && kill -KILL "$lp" 2>/dev/null || true
  printf '\033[2m  %s stopped\033[0m\n' "$name"
}

stop_tunnel() {  # cloudflared has no local port; stop by pidfile + pattern
  local sp
  if [ -f "$CF_PID" ]; then
    sp="$(cat "$CF_PID" 2>/dev/null)"
    if [ -n "$sp" ] && kill -0 "$sp" 2>/dev/null; then
      kill -TERM "$sp" 2>/dev/null
      kill -TERM "-$sp" 2>/dev/null || true
    fi
    rm -f "$CF_PID"
  fi
  pkill -x cloudflared 2>/dev/null || true   # -x: exact exe name, never matches a shell
  printf '\033[2m  TUNNEL stopped\033[0m\n'
}

stop_one API "$API_PID" "$API_PORT"
stop_one WEB "$WEB_PID" "$WEB_PORT"
stop_tunnel
