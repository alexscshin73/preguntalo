#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${PREGUNTALO_PLAYTICA_ENV_FILE:-$ROOT_DIR/.env.playtica}"
CRON_LINE="@reboot cd $ROOT_DIR && PREGUNTALO_PLAYTICA_ENV_FILE=$ENV_FILE bash $ROOT_DIR/scripts/preguntalo_playtica_public_supervisor.sh >> $ROOT_DIR/run/supervisor.log 2>&1"

mkdir -p "$ROOT_DIR/run"

existing="$(crontab -l 2>/dev/null || true)"

if printf '%s\n' "$existing" | grep -F "$ROOT_DIR/scripts/preguntalo_playtica_public_supervisor.sh" >/dev/null 2>&1; then
  echo "Playtica crontab entry already exists."
  exit 0
fi

{
  printf '%s\n' "$existing"
  printf '%s\n' "$CRON_LINE"
} | crontab -

echo "Installed Playtica crontab entry."
