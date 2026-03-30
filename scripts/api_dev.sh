#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
API_DIR="$ROOT_DIR/apps/api"
API_ENV="$API_DIR/.env"
DEFAULT_API_HOST="127.0.0.1"
DEFAULT_API_PORT=8010
RESERVED_BUNNY_PORT=8000
API_RELOAD="${API_RELOAD:-0}"

read_env_value() {
  local file_path="$1"
  local key="$2"

  if [ ! -f "$file_path" ]; then
    return 1
  fi

  awk -F= -v key="$key" '$1 == key { print substr($0, index($0, "=") + 1); exit }' "$file_path"
}

API_HOST="$(read_env_value "$API_ENV" "API_HOST" || true)"
API_PORT="$(read_env_value "$API_ENV" "API_PORT" || true)"

API_HOST="${API_HOST:-$DEFAULT_API_HOST}"
API_PORT="${API_PORT:-$DEFAULT_API_PORT}"

if [ "$API_PORT" = "$RESERVED_BUNNY_PORT" ]; then
  echo "Configuration error: API_PORT=$API_PORT conflicts with Bunny."
  echo "Use API_PORT=8010 or another non-reserved port in apps/api/.env."
  exit 1
fi

if [ ! -x "$API_DIR/.venv/bin/python" ]; then
  echo "Missing API virtualenv at apps/api/.venv."
  echo "Run:"
  echo "  cd apps/api"
  echo "  python3 -m venv .venv"
  echo "  source .venv/bin/activate"
  echo "  pip install -e ."
  exit 1
fi

if [ ! -x "$API_DIR/.venv/bin/uvicorn" ]; then
  echo "uvicorn is not installed in apps/api/.venv."
  echo "Run:"
  echo "  cd apps/api"
  echo "  source .venv/bin/activate"
  echo "  pip install -e ."
  exit 1
fi

cd "$API_DIR"
if [ "$API_RELOAD" = "1" ]; then
  exec "$API_DIR/.venv/bin/uvicorn" app.main:app --reload --host "$API_HOST" --port "$API_PORT"
fi

exec "$API_DIR/.venv/bin/uvicorn" app.main:app --host "$API_HOST" --port "$API_PORT"
