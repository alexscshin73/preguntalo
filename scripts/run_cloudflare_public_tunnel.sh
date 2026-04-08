#!/usr/bin/env bash

set -euo pipefail

KEYCHAIN_SERVICE="${PREGUNTALO_CLOUDFLARE_KEYCHAIN_SERVICE:-preguntalo-cloudflare-tunnel}"
KEYCHAIN_ACCOUNT="${PREGUNTALO_CLOUDFLARE_KEYCHAIN_ACCOUNT:-preguntalo.carroamix.com}"
CLOUDFLARED_BIN="${PREGUNTALO_CLOUDFLARE_TUNNEL_BIN:-$(command -v cloudflared || true)}"
TOKEN_FILE="${PREGUNTALO_CLOUDFLARE_TUNNEL_TOKEN_FILE:-}"

load_token_from_keychain() {
  if command -v security >/dev/null 2>&1; then
    security find-generic-password -w -s "$KEYCHAIN_SERVICE" -a "$KEYCHAIN_ACCOUNT" 2>/dev/null || true
  fi
}

load_token_from_file() {
  if [ -n "$TOKEN_FILE" ] && [ -f "$TOKEN_FILE" ]; then
    tr -d '\n' < "$TOKEN_FILE"
  fi
}

TOKEN="${PREGUNTALO_CLOUDFLARE_TUNNEL_TOKEN:-$(load_token_from_file)}"

if [ -z "$TOKEN" ]; then
  TOKEN="$(load_token_from_keychain)"
fi

if [ -z "$CLOUDFLARED_BIN" ] || [ ! -x "$CLOUDFLARED_BIN" ]; then
  echo "cloudflared was not found."
  echo "Install it or set PREGUNTALO_CLOUDFLARE_TUNNEL_BIN first."
  exit 1
fi

if [ -z "$TOKEN" ]; then
  echo "No Cloudflare tunnel token was found."
  echo
  echo "Provide the token with a file or environment variable:"
  echo "  export PREGUNTALO_CLOUDFLARE_TUNNEL_TOKEN_FILE=/path/to/cloudflare.token"
  echo "  bash scripts/store_cloudflare_tunnel_token.sh '...'"
  echo "  export PREGUNTALO_CLOUDFLARE_TUNNEL_TOKEN='...'"
  echo
  echo "See docs/PREGUNTALO_CARROAMIX_SETUP.md for the full setup flow."
  exit 1
fi

echo "Starting Cloudflare named tunnel for PreguntaLo"
exec "$CLOUDFLARED_BIN" tunnel run --token "$TOKEN"
