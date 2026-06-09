#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="$ROOT_DIR/assets/xterm-lib"
MANIFEST_PATH="$TARGET_DIR/VENDORED.yml"

XTERM_VERSION="${1:-}"
UNICODE11_VERSION="${2:-}"

resolve_latest_version() {
  local package="$1"
  local encoded_package
  local latest_json
  local version

  encoded_package="${package//\//%2F}"
  latest_json="$(curl -fsL "https://registry.npmjs.org/${encoded_package}/latest")"
  version="$(printf '%s' "$latest_json" | grep -m1 -oE '"version"\s*:\s*"[^"]+"' | sed -E 's/"version"\s*:\s*"([^"]+)"/\1/')"

  if [[ -z "$version" ]]; then
    echo "Failed to resolve latest version for ${package}" >&2
    exit 1
  fi

  printf '%s' "$version"
}

if [[ -z "$XTERM_VERSION" ]]; then
  XTERM_VERSION="$(resolve_latest_version "@xterm/xterm")"
fi

if [[ -z "$UNICODE11_VERSION" ]]; then
  UNICODE11_VERSION="$(resolve_latest_version "@xterm/addon-unicode11")"
fi

XTERM_JS_URL="https://cdn.jsdelivr.net/npm/@xterm/xterm@${XTERM_VERSION}/lib/xterm.js"
XTERM_CSS_URL="https://cdn.jsdelivr.net/npm/@xterm/xterm@${XTERM_VERSION}/css/xterm.css"
UNICODE11_JS_URL="https://cdn.jsdelivr.net/npm/@xterm/addon-unicode11@${UNICODE11_VERSION}/lib/addon-unicode11.js"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

echo "Downloading xterm ${XTERM_VERSION} and xterm-addon-unicode11 ${UNICODE11_VERSION}..."
curl -fL "$XTERM_JS_URL" -o "$TMP_DIR/xterm.js"
curl -fL "$XTERM_CSS_URL" -o "$TMP_DIR/xterm.css"
curl -fL "$UNICODE11_JS_URL" -o "$TMP_DIR/addon-unicode11.js"

install -m 0644 "$TMP_DIR/xterm.js" "$TARGET_DIR/xterm.js"
install -m 0644 "$TMP_DIR/xterm.css" "$TARGET_DIR/xterm.css"
install -m 0644 "$TMP_DIR/addon-unicode11.js" "$TARGET_DIR/addon-unicode11.js"

XTERM_JS_SHA="$(sha256sum "$TARGET_DIR/xterm.js" | awk '{print $1}')"
XTERM_CSS_SHA="$(sha256sum "$TARGET_DIR/xterm.css" | awk '{print $1}')"
UNICODE11_JS_SHA="$(sha256sum "$TARGET_DIR/addon-unicode11.js" | awk '{print $1}')"
UPDATED_UTC="$(date -u +%F)"

cat > "$MANIFEST_PATH" <<EOF
name: xterm-lib
description: Vendored browser assets for LLMPentestBench terminal UI.
upstream:
  xterm:
    package: @xterm/xterm
    version: ${XTERM_VERSION}
    file: xterm.js
    url: ${XTERM_JS_URL}
    sha256: ${XTERM_JS_SHA}
  xterm_css:
    package: @xterm/xterm
    version: ${XTERM_VERSION}
    file: xterm.css
    url: ${XTERM_CSS_URL}
    sha256: ${XTERM_CSS_SHA}
  addon_unicode11:
    package: @xterm/addon-unicode11
    version: ${UNICODE11_VERSION}
    file: addon-unicode11.js
    url: ${UNICODE11_JS_URL}
    sha256: ${UNICODE11_JS_SHA}
license: MIT
updated_utc: ${UPDATED_UTC}
update_script: CTFd/plugins/LLMPentestBench/scripts/update-xterm-lib.sh
EOF

echo "Updated vendored xterm assets in: $TARGET_DIR"
echo "Updated manifest: $MANIFEST_PATH"
