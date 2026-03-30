#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
WEB_DIR="$ROOT_DIR/apps/web"
WEB_ENV="$WEB_DIR/.env.local"
DEFAULT_WEB_PORT=3000
WEB_BUILD_ON_START="${PREGUNTALO_WEB_BUILD_ON_START:-1}"

read_env_value() {
  local file_path="$1"
  local key="$2"

  if [ ! -f "$file_path" ]; then
    return 1
  fi

  awk -F= -v key="$key" '$1 == key { print substr($0, index($0, "=") + 1); exit }' "$file_path"
}

PREFERRED_WEB_PORT="${WEB_PORT:-}"

if [ -z "$PREFERRED_WEB_PORT" ]; then
  PREFERRED_WEB_PORT="$(read_env_value "$WEB_ENV" "WEB_PORT" || true)"
fi

PREFERRED_WEB_PORT="${PREFERRED_WEB_PORT:-$DEFAULT_WEB_PORT}"

if lsof -nP -iTCP:"$PREFERRED_WEB_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $PREFERRED_WEB_PORT is already in use."
  echo "Stop the existing process on that port and try again."
  exit 1
fi

cd "$WEB_DIR"

if [ "$WEB_BUILD_ON_START" = "1" ]; then
  echo "Building PreguntaLo web for production..."
  npm run build
elif [ ! -f "$WEB_DIR/.next/BUILD_ID" ]; then
  echo "Missing production build output at apps/web/.next."
  echo "Run npm run web:build or keep PREGUNTALO_WEB_BUILD_ON_START=1."
  exit 1
fi

echo "Starting PreguntaLo web on $PREFERRED_WEB_PORT."
exec npx next start --hostname 0.0.0.0 --port "$PREFERRED_WEB_PORT"
