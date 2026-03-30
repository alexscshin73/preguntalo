#!/usr/bin/env bash

set -euo pipefail

LABEL="com.carroamix.preguntalo.public"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TARGET_PATH="$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl bootout "gui/$UID/$LABEL" >/dev/null 2>&1 || true
rm -f "$TARGET_PATH"

bash "$ROOT_DIR/scripts/preguntalo_public_stop.sh" >/dev/null 2>&1 || true

echo "Removed launch agent: $TARGET_PATH"
