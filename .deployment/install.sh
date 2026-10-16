#!/usr/bin/env bash
set -Eeuo pipefail
REPO="ostaddehdari/deployment-center"
TAG="zohaonline-v0.1.0"
ASSET="zohaonline-v0.1.0.zip"
EXPECTED_SHA256="d1c0c4f375d0048aee24c9b5a27368dc42128fd0d74c39e73c53f57bd9c483c8"
TARGET="${1:-/var/www/zoha}"
TMP="$(mktemp -d /tmp/zohaonline-v0.1.0.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT
URL="https://github.com/${REPO}/releases/download/${TAG}/${ASSET}"
curl --fail --location --retry 3 --connect-timeout 15 "$URL" -o "$TMP/$ASSET"
echo "${EXPECTED_SHA256}  $TMP/$ASSET" | sha256sum -c -
unzip -q "$TMP/$ASSET" -d "$TMP/package"
chmod +x "$TMP/package/apply.sh"
bash "$TMP/package/apply.sh" "$TARGET"
