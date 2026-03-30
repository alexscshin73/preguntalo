#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUN_DIR="$ROOT_DIR/run"
API_PID_FILE="$RUN_DIR/api.pid"
WEB_PID_FILE="$RUN_DIR/web.pid"
TUNNEL_PID_FILE="$RUN_DIR/tunnel.pid"

LOCAL_API_HEALTH_URL="${PREGUNTALO_API_HEALTH_URL:-http://127.0.0.1:8010/api/v1/health}"
LOCAL_WEB_URL="${PREGUNTALO_WEB_URL:-http://127.0.0.1:3000}"
PUBLIC_URL="${PREGUNTALO_PUBLIC_URL:-https://preguntalo.carroamix.com}"
PUBLIC_HEALTH_URL="${PREGUNTALO_PUBLIC_HEALTH_URL:-$PUBLIC_URL/api/proxy/api/v1/health}"

report_pid_file() {
  local label="$1"
  local path="$2"

  if [ ! -f "$path" ]; then
    echo "$label: not running"
    return
  fi

  local pid
  pid="$(tr -d '\n' < "$path")"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    echo "$label: running (pid $pid)"
  else
    echo "$label: stale pid file"
  fi
}

report_pid_file "API" "$API_PID_FILE"
report_pid_file "Web" "$WEB_PID_FILE"
report_pid_file "Tunnel" "$TUNNEL_PID_FILE"

if curl -fsS --max-time 5 "$LOCAL_API_HEALTH_URL" >/dev/null 2>&1; then
  echo "Local API health: ok"
else
  echo "Local API health: unreachable"
fi

if curl -fsS --max-time 5 "$LOCAL_WEB_URL" >/dev/null 2>&1; then
  echo "Local web health: ok"
else
  echo "Local web health: unreachable"
fi

if curl -fsS --max-time 10 "$PUBLIC_HEALTH_URL" >/dev/null 2>&1; then
  echo "Public health: ok"
else
  echo "Public health: unreachable"
fi

echo "Public URL: $PUBLIC_URL"
