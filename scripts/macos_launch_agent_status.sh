#!/usr/bin/env bash

set -euo pipefail

LABEL="com.carroamix.preguntalo.public"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TARGET_PATH="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ -f "$TARGET_PATH" ]; then
  echo "Launch agent file: present ($TARGET_PATH)"
else
  echo "Launch agent file: missing ($TARGET_PATH)"
fi

if launchctl print "gui/$UID/$LABEL" >/dev/null 2>&1; then
  echo "Launch agent status: loaded"
else
  echo "Launch agent status: not loaded"
fi

bash "$ROOT_DIR/scripts/preguntalo_public_status.sh"
