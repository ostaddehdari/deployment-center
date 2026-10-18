#!/usr/bin/env bash
set -Eeuo pipefail
BASE="https://github.com/ostaddehdari/deployment-center/releases/download/zohaonline-v0.6.10"
WORK="$(mktemp -d /tmp/zohaonline-v0.6.10.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT
curl -fL --retry 3 "$BASE/zohaonline-v0.6.10.zip" -o "$WORK/zohaonline-v0.6.10.zip"
echo "8908d679dbdf7b356a4e4bb959718ea21e94a50d2cad5c53df13711512a9479e  $WORK/zohaonline-v0.6.10.zip" | sha256sum -c -
unzip -q "$WORK/zohaonline-v0.6.10.zip" -d "$WORK/package"
bash "$WORK/package/apply.sh" "${1:-/var/www/zoha}"
