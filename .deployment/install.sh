#!/usr/bin/env bash
set -Eeuo pipefail
BASE="https://github.com/ostaddehdari/deployment-center/releases/download/zohaonline-v0.6.5"
WORK="$(mktemp -d /tmp/zohaonline-v0.6.5.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT
curl -fL --retry 3 "$BASE/zohaonline-v0.6.5.zip" -o "$WORK/zohaonline-v0.6.5.zip"
echo "7d99fa5cfbf34363fa798dcce860b7a113df55ebf3c604e27a186573f14950c8  $WORK/zohaonline-v0.6.5.zip" | sha256sum -c -
unzip -q "$WORK/zohaonline-v0.6.5.zip" -d "$WORK/package"
bash "$WORK/package/apply.sh" "${1:-/var/www/zoha}"
