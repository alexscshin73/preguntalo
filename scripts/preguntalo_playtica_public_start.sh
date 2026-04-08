#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUN_DIR="$ROOT_DIR/run"
API_PID_FILE="$RUN_DIR/api.pid"
WEB_PID_FILE="$RUN_DIR/web.pid"
TUNNEL_PID_FILE="$RUN_DIR/tunnel.pid"
API_LOG="$RUN_DIR/api.log"
WEB_LOG="$RUN_DIR/web.log"
TUNNEL_LOG="$RUN_DIR/tunnel.log"
ENV_FILE="${PREGUNTALO_PLAYTICA_ENV_FILE:-$ROOT_DIR/.env.playtica}"

mkdir -p "$RUN_DIR"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing Playtica env file: $ENV_FILE"
  exit 1
fi

api_health_url() {
  local port="${API_PORT:-8010}"
  echo "${PREGUNTALO_API_HEALTH_URL:-http://127.0.0.1:${port}/api/v1/health}"
}

web_url() {
  local port="${WEB_PORT:-3000}"
  echo "${PREGUNTALO_WEB_URL:-http://127.0.0.1:${port}}"
}

public_url() {
  echo "${PREGUNTALO_PUBLIC_URL:-https://preguntalo.carroamix.com}"
}

public_health_url() {
  echo "${PREGUNTALO_PUBLIC_HEALTH_URL:-$(public_url)/api/proxy/api/v1/health}"
}

is_pid_running() {
  local pid="$1"
  kill -0 "$pid" 2>/dev/null
}

read_pid_file() {
  local path="$1"
  if [ -f "$path" ]; then
    tr -d '\n' < "$path"
  fi
}

cleanup_stale_pid_file() {
  local path="$1"
  local pid
  pid="$(read_pid_file "$path")"
  if [ -n "$pid" ] && ! is_pid_running "$pid"; then
    rm -f "$path"
  fi
}

wait_for_url() {
  local url="$1"
  local attempts="$2"

  for _ in $(seq 1 "$attempts"); do
    if curl -fsS --max-time 5 "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done

  return 1
}

start_api() {
  cleanup_stale_pid_file "$API_PID_FILE"

  if curl -fsS --max-time 5 "$(api_health_url)" >/dev/null 2>&1; then
    echo "API already reachable on $(api_health_url)"
    return
  fi

  echo "Starting PreguntaLo API on Playtica..."
  nohup bash -lc "
    set -a
    . \"$ENV_FILE\"
    set +a
    export PATH=\"\$HOME/.local/bin:\$PATH\"
    cd \"$ROOT_DIR/apps/api\"
    exec uvicorn app.main:app --host \"\${API_HOST:-127.0.0.1}\" --port \"\${API_PORT:-8010}\"
  " >"$API_LOG" 2>&1 &
  echo "$!" >"$API_PID_FILE"

  if wait_for_url "$(api_health_url)" 60; then
    echo "API is ready."
    return
  fi

  echo "API did not become ready in time."
  tail -n 80 "$API_LOG" || true
  exit 1
}

start_web() {
  cleanup_stale_pid_file "$WEB_PID_FILE"

  if curl -fsS --max-time 5 "$(web_url)" >/dev/null 2>&1; then
    echo "Web already reachable on $(web_url)"
    return
  fi

  echo "Starting PreguntaLo web on Playtica..."
  nohup bash -lc "
    set -a
    . \"$ENV_FILE\"
    set +a
    export PATH=\"\$HOME/.local/bin:\$PATH\"
    cd \"$ROOT_DIR/apps/web\"
    if [ \"\${PREGUNTALO_WEB_BUILD_ON_START:-1}\" = \"1\" ]; then
      npm run build
    elif [ ! -f .next/BUILD_ID ]; then
      echo 'Missing production build output at apps/web/.next.'
      exit 1
    fi
    exec npx next start --hostname 0.0.0.0 --port \"\${WEB_PORT:-3000}\"
  " >"$WEB_LOG" 2>&1 &
  echo "$!" >"$WEB_PID_FILE"

  if wait_for_url "$(web_url)" 80; then
    echo "Web is ready."
    return
  fi

  echo "Web did not become ready in time."
  tail -n 80 "$WEB_LOG" || true
  exit 1
}

start_tunnel() {
  cleanup_stale_pid_file "$TUNNEL_PID_FILE"

  local existing_pid
  existing_pid="$(read_pid_file "$TUNNEL_PID_FILE")"
  if [ -n "$existing_pid" ] && is_pid_running "$existing_pid"; then
    echo "Cloudflare tunnel already running (pid $existing_pid)."
    return
  fi

  echo "Starting Cloudflare tunnel on Playtica..."
  nohup bash -lc "
    set -a
    . \"$ENV_FILE\"
    set +a
    export PATH=\"\$HOME/.local/bin:\$PATH\"
    cd \"$ROOT_DIR\"
    exec bash \"$ROOT_DIR/scripts/run_cloudflare_public_tunnel.sh\"
  " >"$TUNNEL_LOG" 2>&1 &
  echo "$!" >"$TUNNEL_PID_FILE"
  sleep 3

  local tunnel_pid
  tunnel_pid="$(read_pid_file "$TUNNEL_PID_FILE")"
  if [ -z "$tunnel_pid" ] || ! is_pid_running "$tunnel_pid"; then
    echo "Cloudflare tunnel failed to start."
    tail -n 80 "$TUNNEL_LOG" || true
    exit 1
  fi

  echo "Cloudflare tunnel is running."
}

start_api
start_web
start_tunnel

if wait_for_url "$(public_health_url)" 20; then
  public_status="ok"
else
  public_status="unreachable"
fi

echo
echo "PreguntaLo Playtica public service is ready."
echo "Public URL: $(public_url)"
echo "Public health: $public_status ($(public_health_url))"
echo "API log: $API_LOG"
echo "Web log: $WEB_LOG"
echo "Tunnel log: $TUNNEL_LOG"
