#!/usr/bin/env bash
set -Eeuo pipefail
BASE="https://github.com/ostaddehdari/deployment-center/releases/download/zohaonline-v0.6.9"
WORK="$(mktemp -d /tmp/zohaonline-v0.6.9.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT
curl -fL --retry 3 "$BASE/zohaonline-v0.6.9.zip" -o "$WORK/zohaonline-v0.6.9.zip"
echo "eba203182d005aedbdc35a5afa767c206d524753f4510041c1df3d38be6a7a4b  $WORK/zohaonline-v0.6.9.zip" | sha256sum -c -
unzip -q "$WORK/zohaonline-v0.6.9.zip" -d "$WORK/package"
bash "$WORK/package/apply.sh" "${1:-/var/www/zoha}"
