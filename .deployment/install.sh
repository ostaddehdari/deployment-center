#!/usr/bin/env bash
set -Eeuo pipefail
BASE="https://github.com/ostaddehdari/deployment-center/releases/download/zohaonline-v0.6.7"
WORK="$(mktemp -d /tmp/zohaonline-v0.6.7.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT
curl -fL --retry 3 "$BASE/zohaonline-v0.6.7.zip" -o "$WORK/zohaonline-v0.6.7.zip"
echo "9211184186ec44188abbb51c0f78ddf7324eaae93a98ba0d45b27af9eb2d7c0b  $WORK/zohaonline-v0.6.7.zip" | sha256sum -c -
unzip -q "$WORK/zohaonline-v0.6.7.zip" -d "$WORK/package"
bash "$WORK/package/apply.sh" "${1:-/var/www/zoha}"
