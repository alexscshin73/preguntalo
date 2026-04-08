#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
INTERVAL_SECONDS="${PREGUNTALO_SUPERVISOR_INTERVAL_SECONDS:-60}"

shutdown() {
  echo "Stopping PreguntaLo Playtica public supervisor..."
  bash "$ROOT_DIR/scripts/preguntalo_playtica_public_stop.sh" >/dev/null 2>&1 || true
  exit 0
}

trap shutdown INT TERM HUP

echo "Starting PreguntaLo Playtica public supervisor."
echo "Health check interval: ${INTERVAL_SECONDS}s"

while true; do
  bash "$ROOT_DIR/scripts/preguntalo_playtica_public_start.sh"
  sleep "$INTERVAL_SECONDS" &
  wait "$!"
done
