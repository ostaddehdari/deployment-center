#!/usr/bin/env bash
set -Eeuo pipefail
BASE="https://github.com/ostaddehdari/deployment-center/releases/download/zohaonline-v0.6.8"
WORK="$(mktemp -d /tmp/zohaonline-v0.6.8.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT
curl -fL --retry 3 "$BASE/zohaonline-v0.6.8.zip" -o "$WORK/zohaonline-v0.6.8.zip"
echo "961140c46a9b5e37158993f9dfb91674a0503d34c4dc7fa1c9855a5f77708ae3  $WORK/zohaonline-v0.6.8.zip" | sha256sum -c -
unzip -q "$WORK/zohaonline-v0.6.8.zip" -d "$WORK/package"
bash "$WORK/package/apply.sh" "${1:-/var/www/zoha}"
