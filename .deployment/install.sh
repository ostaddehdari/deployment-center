#!/usr/bin/env bash
set -Eeuo pipefail
BASE="https://github.com/ostaddehdari/deployment-center/releases/download/zohaonline-v0.6.1"
WORK="$(mktemp -d /tmp/zohaonline-v0.6.1.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT
curl -fL --retry 3 "$BASE/zohaonline-v0.6.1.zip" -o "$WORK/zohaonline-v0.6.1.zip"
echo "6354a9ba71321d4b42c3313cef1c35d9d2c6e5d0fde483f7d24130551bfae87a  $WORK/zohaonline-v0.6.1.zip" | sha256sum -c -
unzip -q "$WORK/zohaonline-v0.6.1.zip" -d "$WORK/package"
bash "$WORK/package/apply.sh" "${1:-/var/www/zoha}"
