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

LOCAL_API_HEALTH_URL="${PREGUNTALO_API_HEALTH_URL:-http://127.0.0.1:8010/api/v1/health}"
LOCAL_WEB_URL="${PREGUNTALO_WEB_URL:-http://127.0.0.1:3000}"
PUBLIC_URL="${PREGUNTALO_PUBLIC_URL:-https://preguntalo.carroamix.com}"
PUBLIC_HEALTH_URL="${PREGUNTALO_PUBLIC_HEALTH_URL:-$PUBLIC_URL/api/proxy/api/v1/health}"
WEB_START_SCRIPT="${PREGUNTALO_WEB_START_SCRIPT:-$ROOT_DIR/scripts/web_public.sh}"

mkdir -p "$RUN_DIR"

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

  if curl -s --max-time 5 "$LOCAL_API_HEALTH_URL" >/dev/null 2>&1; then
    echo "API already reachable on $LOCAL_API_HEALTH_URL"
    return
  fi

  echo "Starting PreguntaLo API..."
  nohup bash "$ROOT_DIR/scripts/api_dev.sh" >"$API_LOG" 2>&1 &
  echo "$!" >"$API_PID_FILE"

  if wait_for_url "$LOCAL_API_HEALTH_URL" 40; then
    echo "API is ready."
    return
  fi

  echo "API did not become ready in time."
  tail -n 40 "$API_LOG" || true
  exit 1
}

start_web() {
  cleanup_stale_pid_file "$WEB_PID_FILE"

  if curl -s --max-time 5 "$LOCAL_WEB_URL" >/dev/null 2>&1; then
    echo "Web already reachable on $LOCAL_WEB_URL"
    return
  fi

  echo "Starting PreguntaLo web..."
  nohup bash "$WEB_START_SCRIPT" >"$WEB_LOG" 2>&1 &
  echo "$!" >"$WEB_PID_FILE"

  if wait_for_url "$LOCAL_WEB_URL" 40; then
    echo "Web is ready."
    return
  fi

  echo "Web did not become ready in time."
  tail -n 40 "$WEB_LOG" || true
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

  echo "Starting Cloudflare tunnel..."
  nohup bash "$ROOT_DIR/scripts/run_cloudflare_public_tunnel.sh" >"$TUNNEL_LOG" 2>&1 &
  echo "$!" >"$TUNNEL_PID_FILE"
  sleep 3

  local tunnel_pid
  tunnel_pid="$(read_pid_file "$TUNNEL_PID_FILE")"
  if [ -z "$tunnel_pid" ] || ! is_pid_running "$tunnel_pid"; then
    echo "Cloudflare tunnel failed to start."
    tail -n 40 "$TUNNEL_LOG" || true
    exit 1
  fi

  echo "Cloudflare tunnel is running."
}

start_api
start_web
start_tunnel

if wait_for_url "$PUBLIC_HEALTH_URL" 20; then
  public_status="ok"
else
  public_status="unreachable"
fi

echo
echo "PreguntaLo public service is ready."
echo "Public URL: $PUBLIC_URL"
echo "Public health: $public_status ($PUBLIC_HEALTH_URL)"
echo "API log: $API_LOG"
echo "Web log: $WEB_LOG"
echo "Tunnel log: $TUNNEL_LOG"
