#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
API_ENV="$ROOT_DIR/apps/api/.env"
WEB_ENV="$ROOT_DIR/apps/web/.env.local"
RESERVED_BUNNY_PORT=8000
DEFAULT_API_PORT=8010
DEFAULT_WEB_PORT=3000

read_env_value() {
  local file_path="$1"
  local key="$2"

  if [ ! -f "$file_path" ]; then
    return 1
  fi

  awk -F= -v key="$key" '$1 == key { print substr($0, index($0, "=") + 1); exit }' "$file_path"
}

API_PORT_VALUE="$(read_env_value "$API_ENV" "API_PORT" || true)"
API_PORT="${API_PORT_VALUE:-$DEFAULT_API_PORT}"
WEB_API_BASE="$(read_env_value "$WEB_ENV" "NEXT_PUBLIC_API_BASE_URL" || true)"
WEB_PORT_VALUE="$(read_env_value "$WEB_ENV" "WEB_PORT" || true)"
WEB_PORT="${WEB_PORT_VALUE:-${WEB_PORT:-$DEFAULT_WEB_PORT}}"
if [ -z "$WEB_API_BASE" ]; then
  WEB_API_BASE="$(read_env_value "$WEB_ENV" "NEXT_PUBLIC_API_BASE" || true)"
fi
EXPECTED_LOCALHOST_URL="http://localhost:$API_PORT"
EXPECTED_LOOPBACK_URL="http://127.0.0.1:$API_PORT"

echo "Preguntalo dev doctor"
echo "API port: $API_PORT"
echo "Expected web API base: $EXPECTED_LOCALHOST_URL or $EXPECTED_LOOPBACK_URL"
echo "Fixed web port: $WEB_PORT"

if [ "$API_PORT" = "$RESERVED_BUNNY_PORT" ]; then
  echo
  echo "Configuration error: API_PORT=$API_PORT conflicts with Bunny."
  echo "Bunny reserves port 8000 on this Mac."
  echo "Set Preguntalo API_PORT to 8010 or another non-reserved port."
  exit 1
fi

if [ -n "$WEB_API_BASE" ] && [ "$WEB_API_BASE" != "$EXPECTED_LOCALHOST_URL" ] && [ "$WEB_API_BASE" != "$EXPECTED_LOOPBACK_URL" ]; then
  echo
  echo "Configuration mismatch: NEXT_PUBLIC_API_BASE_URL or NEXT_PUBLIC_API_BASE is set to $WEB_API_BASE"
  echo "It should point to $EXPECTED_LOCALHOST_URL or $EXPECTED_LOOPBACK_URL"
  exit 1
fi

if lsof -nP -iTCP:"$API_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo
  echo "Port $API_PORT is already in use."
  lsof -nP -iTCP:"$API_PORT" -sTCP:LISTEN || true
  exit 1
fi

echo
echo "Config looks good."
echo "API can run on: http://127.0.0.1:$API_PORT"
if lsof -nP -iTCP:"$WEB_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Web port is currently in use: http://127.0.0.1:$WEB_PORT"
else
  echo "Web can run on: http://127.0.0.1:$WEB_PORT"
fi
if [ "$WEB_PORT" != "$DEFAULT_WEB_PORT" ]; then
  echo "Warning: WEB_PORT is not 3000. Current fixed setting is expected to stay on 3000."
  exit 1
fi
