#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUN_DIR="$ROOT_DIR/run"
API_PID_FILE="$RUN_DIR/api.pid"
WEB_PID_FILE="$RUN_DIR/web.pid"
TUNNEL_PID_FILE="$RUN_DIR/tunnel.pid"

stop_from_pid_file() {
  local label="$1"
  local path="$2"

  if [ ! -f "$path" ]; then
    echo "$label is not running."
    return
  fi

  local pid
  pid="$(tr -d '\n' < "$path")"
  if [ -z "$pid" ]; then
    rm -f "$path"
    echo "$label pid file was empty and has been cleared."
    return
  fi

  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid"
    echo "Stopped $label (pid $pid)."
  else
    echo "$label was not running, removed stale pid file."
  fi

  rm -f "$path"
}

stop_from_pid_file "Cloudflare tunnel" "$TUNNEL_PID_FILE"
stop_from_pid_file "PreguntaLo web" "$WEB_PID_FILE"
stop_from_pid_file "PreguntaLo API" "$API_PID_FILE"
