#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
API_DIR="$ROOT_DIR/apps/api"
API_ENV="$API_DIR/.env"
WEB_ENV="$ROOT_DIR/apps/web/.env.local"
DEFAULT_API_PORT=8010
DEFAULT_API_PREFIX="/api/v1"
RESERVED_BUNNY_PORT=8000
api_pid=""
api_started_here=0

read_env_value() {
  local file_path="$1"
  local key="$2"

  if [ ! -f "$file_path" ]; then
    return 1
  fi

  awk -F= -v key="$key" '$1 == key { print substr($0, index($0, "=") + 1); exit }' "$file_path"
}

cleanup() {
  if [ "$api_started_here" -eq 1 ] && [ -n "$api_pid" ] && kill -0 "$api_pid" >/dev/null 2>&1; then
    kill "$api_pid" >/dev/null 2>&1 || true
    wait "$api_pid" >/dev/null 2>&1 || true
  fi
}

wait_for_api() {
  local api_port="$1"
  local api_prefix="$2"
  local health_url="http://127.0.0.1:$api_port$api_prefix/health"

  for _ in $(seq 1 30); do
    if curl -sSf --max-time 2 "$health_url" >/dev/null; then
      echo "API is ready at $health_url"
      return 0
    fi

    if [ "$api_started_here" -eq 1 ] && [ -n "$api_pid" ] && ! kill -0 "$api_pid" >/dev/null 2>&1; then
      echo "API exited before becoming ready."
      return 1
    fi

    sleep 1
  done

  echo "Timed out waiting for API at $health_url"
  return 1
}

trap cleanup EXIT INT TERM

API_PORT="$(read_env_value "$API_ENV" "API_PORT" || true)"
API_PREFIX="$(read_env_value "$API_ENV" "API_PREFIX" || true)"
WEB_API_BASE="$(read_env_value "$WEB_ENV" "NEXT_PUBLIC_API_BASE_URL" || true)"

if [ -z "$WEB_API_BASE" ]; then
  WEB_API_BASE="$(read_env_value "$WEB_ENV" "NEXT_PUBLIC_API_BASE" || true)"
fi

API_PORT="${API_PORT:-$DEFAULT_API_PORT}"
API_PREFIX="${API_PREFIX:-$DEFAULT_API_PREFIX}"

EXPECTED_LOCALHOST_URL="http://localhost:$API_PORT"
EXPECTED_LOOPBACK_URL="http://127.0.0.1:$API_PORT"

if [ "$API_PORT" = "$RESERVED_BUNNY_PORT" ]; then
  echo "Configuration error: API_PORT=$API_PORT conflicts with Bunny."
  echo "Use API_PORT=8010 or another non-reserved port in apps/api/.env."
  exit 1
fi

if [ -n "$WEB_API_BASE" ] && [ "$WEB_API_BASE" != "$EXPECTED_LOCALHOST_URL" ] && [ "$WEB_API_BASE" != "$EXPECTED_LOOPBACK_URL" ]; then
  echo "Configuration mismatch: NEXT_PUBLIC_API_BASE_URL or NEXT_PUBLIC_API_BASE is set to $WEB_API_BASE"
  echo "It should point to $EXPECTED_LOCALHOST_URL or $EXPECTED_LOOPBACK_URL"
  exit 1
fi

if lsof -nP -iTCP:"$API_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Reusing existing API on port $API_PORT."
else
  echo "Starting API on port $API_PORT..."
  (
    cd "$ROOT_DIR"
    exec bash scripts/api_dev.sh
  ) &
  api_pid="$!"
  api_started_here=1
fi

wait_for_api "$API_PORT" "$API_PREFIX"

cd "$ROOT_DIR"
exec bash scripts/web_dev.sh
