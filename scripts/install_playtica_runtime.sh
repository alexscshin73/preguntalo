#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOCAL_BIN_DIR="${HOME}/.local/bin"
LOCAL_OPT_DIR="${HOME}/.local/opt"
PIP_BOOTSTRAP_URL="${PREGUNTALO_PIP_BOOTSTRAP_URL:-https://bootstrap.pypa.io/get-pip.py}"
CLOUDFLARED_URL="${PREGUNTALO_CLOUDFLARED_URL:-https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64}"
NODE_CHANNEL="${PREGUNTALO_NODE_CHANNEL:-latest-v22.x}"
NODE_DIST_BASE="${PREGUNTALO_NODE_DIST_BASE:-https://nodejs.org/dist}"

mkdir -p "$LOCAL_BIN_DIR" "$LOCAL_OPT_DIR"

install_pip_user() {
  if python3 -m pip --version >/dev/null 2>&1; then
    return 0
  fi

  local bootstrap_script
  bootstrap_script="$(mktemp)"
  curl -fsSL "$PIP_BOOTSTRAP_URL" -o "$bootstrap_script"
  python3 "$bootstrap_script" --user --break-system-packages
  rm -f "$bootstrap_script"
}

install_api_deps() {
  python3 -m pip install --user --break-system-packages -e "$ROOT_DIR/apps/api"
}

install_cloudflared_user() {
  if [ -x "$LOCAL_BIN_DIR/cloudflared" ]; then
    return 0
  fi

  curl -fsSL "$CLOUDFLARED_URL" -o "$LOCAL_BIN_DIR/cloudflared"
  chmod +x "$LOCAL_BIN_DIR/cloudflared"
}

install_node_user() {
  if [ -x "$LOCAL_BIN_DIR/node" ] && [ -x "$LOCAL_BIN_DIR/npm" ] && [ -x "$LOCAL_BIN_DIR/npx" ]; then
    return 0
  fi

  local shasums_url archive_name archive_path extract_dir node_dir
  shasums_url="$NODE_DIST_BASE/$NODE_CHANNEL/SHASUMS256.txt"
  archive_name="$(curl -fsSL "$shasums_url" | awk '/linux-x64\.tar\.xz$/ {print $2; exit}')"
  if [ -z "$archive_name" ]; then
    echo "Unable to resolve a Node.js linux-x64 archive from $shasums_url"
    exit 1
  fi

  archive_path="$(mktemp)"
  curl -fsSL "$NODE_DIST_BASE/$NODE_CHANNEL/$archive_name" -o "$archive_path"

  extract_dir="$LOCAL_OPT_DIR/node"
  rm -rf "$extract_dir"
  mkdir -p "$extract_dir"
  tar -xJf "$archive_path" -C "$extract_dir"
  rm -f "$archive_path"

  node_dir="$(find "$extract_dir" -maxdepth 1 -mindepth 1 -type d | head -n 1)"
  if [ -z "$node_dir" ]; then
    echo "Node.js archive extracted but no directory was found."
    exit 1
  fi

  ln -sf "$node_dir/bin/node" "$LOCAL_BIN_DIR/node"
  ln -sf "$node_dir/bin/npm" "$LOCAL_BIN_DIR/npm"
  ln -sf "$node_dir/bin/npx" "$LOCAL_BIN_DIR/npx"
}

install_web_deps() {
  export PATH="$LOCAL_BIN_DIR:$PATH"
  cd "$ROOT_DIR"
  npm ci
}

cd "$ROOT_DIR"
install_pip_user
install_api_deps
install_cloudflared_user
install_node_user
install_web_deps

echo "Playtica runtime install complete."
echo "pip: $(python3 -m pip --version)"
echo "node: $(node --version)"
echo "npm: $(npm --version)"
echo "cloudflared: $LOCAL_BIN_DIR/cloudflared"
