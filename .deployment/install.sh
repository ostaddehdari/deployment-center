#!/usr/bin/env bash
set -Eeuo pipefail
REPO="ostaddehdari/deployment-center"
TAG="zohaonline-v0.3.4"
ASSET="zohaonline-v0.3.4.zip"
TARGET="${1:-/var/www/zoha}"
TMP="$(mktemp -d /tmp/zohaonline-v0.3.4.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT
BASE="https://github.com/${REPO}/releases/download/${TAG}"
curl --fail --location --retry 3 "$BASE/SHA256SUMS" -o "$TMP/SHA256SUMS"
curl --fail --location --retry 3 "$BASE/$ASSET" -o "$TMP/$ASSET"
(
 cd "$TMP"
 grep "  $ASSET$" SHA256SUMS | sha256sum -c -
)
unzip -q "$TMP/$ASSET" -d "$TMP/package"
chmod +x "$TMP/package/apply.sh"
bash "$TMP/package/apply.sh" "$TARGET"
