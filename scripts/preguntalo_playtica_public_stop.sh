#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUN_DIR="$ROOT_DIR/run"

stop_pid_file() {
  local path="$1"

  if [ ! -f "$path" ]; then
    return
  fi

  local pid
  pid="$(tr -d '\n' < "$path")"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
  fi
  rm -f "$path"
}

stop_pid_file "$RUN_DIR/tunnel.pid"
stop_pid_file "$RUN_DIR/web.pid"
stop_pid_file "$RUN_DIR/api.pid"

echo "Stopped PreguntaLo Playtica public processes."
