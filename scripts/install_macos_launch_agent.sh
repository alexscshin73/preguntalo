#!/usr/bin/env bash

set -euo pipefail

LABEL="com.carroamix.preguntalo.public"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TEMPLATE_PATH="$ROOT_DIR/ops/launchd/$LABEL.plist.template"
TARGET_DIR="$HOME/Library/LaunchAgents"
TARGET_PATH="$TARGET_DIR/$LABEL.plist"
RUN_DIR="$ROOT_DIR/run"
PATH_VALUE="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared is required but was not found in PATH."
  exit 1
fi

mkdir -p "$TARGET_DIR" "$RUN_DIR"

sed \
  -e "s#__ROOT_DIR__#$ROOT_DIR#g" \
  -e "s#__RUN_DIR__#$RUN_DIR#g" \
  -e "s#__HOME__#$HOME#g" \
  -e "s#__PATH__#$PATH_VALUE#g" \
  "$TEMPLATE_PATH" >"$TARGET_PATH"

launchctl bootout "gui/$UID/$LABEL" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$UID" "$TARGET_PATH"
launchctl enable "gui/$UID/$LABEL"
launchctl kickstart -k "gui/$UID/$LABEL"

echo "Installed launch agent: $TARGET_PATH"
echo "Label: $LABEL"
echo "Boot/login behavior: launchd will re-run public:start every 60 seconds."
echo "Status: npm run public:autostart:status"
