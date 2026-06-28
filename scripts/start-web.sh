#!/usr/bin/env bash
# Start LU web backend (FastAPI :8000) and frontend (Next.js :3000) under a
# supervisor. Each service is auto-restarted on crash; logs land in .api.log /
# .web.log; PID files at the project root point at the supervisor.
#
# Usage:
#   scripts/start-web.sh            # PROD: build the web app, then serve (changes take effect)
#   scripts/start-web.sh --dev      # DEV: hot-reload (uvicorn --reload + next dev), no build
#   scripts/start-web.sh --tunnel   # also open a public cloudflared tunnel to :3000, print its URL
#   (flags combine, e.g. `--dev --tunnel`)
#
# Open http://localhost:3000 afterwards. If the page looks stale, hard-refresh
# (Ctrl/Cmd+Shift+R) — production serves a build snapshot and the browser caches.
#
# --tunnel needs cloudflared on PATH (~/.local/bin). It uses Cloudflare's free
# "quick tunnel": a RANDOM https://<words>.trycloudflare.com URL, no account, no
# DNS setup — but the URL changes every start and the page has NO auth (anyone with
# the link can use it + burn your AI quota). stop-web.sh tears the tunnel down too.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WEB_DIR="$ROOT/apps/web"

API_PORT="${LU_API_PORT:-8000}"
WEB_PORT="${LU_WEB_PORT:-3000}"
API_PID="$ROOT/.api.pid"; WEB_PID="$ROOT/.web.pid"; CF_PID="$ROOT/.cf.pid"
API_LOG="$ROOT/.api.log"; WEB_LOG="$ROOT/.web.log"; CF_LOG="$ROOT/.cf.log"

export PATH="$HOME/.local/bin:$PATH"   # uv lives here, not on default PATH

g() { printf '\033[32m%s\033[0m\n' "$*"; }
r() { printf '\033[31m%s\033[0m\n' "$*"; }
d() { printf '\033[2m%s\033[0m\n' "$*"; }

port_pid() { ss -ltnp 2>/dev/null | awk -v p=":$1" '$4 ~ p"$"' | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2; }
lan_ip()  { hostname -I 2>/dev/null | tr ' ' '\n' | grep -vE '^(172\.1[6-9]|172\.2[0-9]|172\.3[0-1]|127\.|169\.254\.)' | grep -E '^[0-9]+\.' | head -1; }
# does the port listen on all interfaces (*: / 0.0.0.0 / ::) rather than only loopback?
port_public() { ss -ltn 2>/dev/null | awk -v p=":$1" '$4 ~ p"$"{print $4}' | grep -qE '^(\*|0\.0\.0\.0|\[::\]|::):' && echo 1 || echo 0; }

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

DEV=0; TUNNEL=0
for a in "$@"; do
  [ "$a" = "--dev" ] && DEV=1
  [ "$a" = "--tunnel" ] && TUNNEL=1
done  # we always free our own ports first (implicit --force)

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
LANIP="$(lan_ip)"
echo
echo "──────────────── 端口 / 可访问地址 ────────────────"
echo "API  :$API_PORT  $( [ -n "$(port_pid "$API_PORT")" ] && g 'UP' || r 'DOWN' )  (仅本机 127.0.0.1,供 web 内部转发)"
echo "WEB  :$WEB_PORT  $( [ -n "$(port_pid "$WEB_PORT")" ] && g 'UP' || r 'DOWN' )"
echo
echo "  本机          → http://localhost:$WEB_PORT"
if [ -n "$LANIP" ]; then
  if [ "$(port_public "$WEB_PORT")" = "1" ]; then
    echo "  局域网/同网段  → http://$LANIP:$WEB_PORT   $(d '(需防火墙放行该端口)')"
  else
    r   "  局域网         → 未监听对外网卡(仅 localhost),外部无法访问"
  fi
fi
echo "  公网          → 加 --tunnel 启动,会在下方打印 trycloudflare 网址"
echo "───────────────────────────────────────────────────"
if [ "$ok" -eq 1 ]; then g "LU is up  (页面没更新就硬刷新 Ctrl/Cmd+Shift+R)"
else r "services slow to respond — check .api.log / .web.log"; fi

# ── Optional public tunnel ──
if [ "$TUNNEL" -eq 1 ]; then
  if command -v cloudflared >/dev/null 2>&1; then
    : > "$CF_LOG"   # truncate so we grep THIS run's URL
    start_one TUNNEL "$CF_PID" "$CF_LOG" -- cloudflared tunnel --url "http://localhost:$WEB_PORT" --no-autoupdate
    d "waiting for tunnel URL…"
    URL=""
    for _ in $(seq 1 20); do
      sleep 2
      URL="$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$CF_LOG" | tail -1)"
      [ -n "$URL" ] && break
    done
    if [ -n "$URL" ]; then g "TUNNEL (公网) → $URL"; d "  ⚠ 无鉴权,谁有链接谁能用;停止见 stop-web.sh"
    else r "tunnel URL not ready — check $CF_LOG"; fi
  else
    r "cloudflared 未安装,跳过 --tunnel。安装:"
    d "  curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o ~/.local/bin/cloudflared && chmod +x ~/.local/bin/cloudflared"
  fi
fi
