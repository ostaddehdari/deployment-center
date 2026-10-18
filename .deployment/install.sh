#!/usr/bin/env bash
set -Eeuo pipefail
BASE="https://github.com/ostaddehdari/deployment-center/releases/download/zohaonline-v0.6.6"
WORK="$(mktemp -d /tmp/zohaonline-v0.6.6.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT
curl -fL --retry 3 "$BASE/zohaonline-v0.6.6.zip" -o "$WORK/zohaonline-v0.6.6.zip"
echo "ea7bf0701071433148efc5489c39b9b05b74ded054217a63363700b56b135a45  $WORK/zohaonline-v0.6.6.zip" | sha256sum -c -
unzip -q "$WORK/zohaonline-v0.6.6.zip" -d "$WORK/package"
bash "$WORK/package/apply.sh" "${1:-/var/www/zoha}"
