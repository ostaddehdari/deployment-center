#!/usr/bin/env bash
set -Eeuo pipefail
BASE="https://github.com/ostaddehdari/deployment-center/releases/download/zohaonline-v0.6.4"
WORK="$(mktemp -d /tmp/zohaonline-v0.6.4.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT
curl -fL --retry 3 "$BASE/zohaonline-v0.6.4.zip" -o "$WORK/zohaonline-v0.6.4.zip"
echo "89b3083e57681be760a1c6b7e9c4a7bac193e60a7f06b749850100383bd8b511  $WORK/zohaonline-v0.6.4.zip" | sha256sum -c -
unzip -q "$WORK/zohaonline-v0.6.4.zip" -d "$WORK/package"
bash "$WORK/package/apply.sh" "${1:-/var/www/zoha}"
