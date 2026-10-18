#!/usr/bin/env bash
set -Eeuo pipefail
BASE="https://github.com/ostaddehdari/deployment-center/releases/download/zohaonline-v0.6.2"
WORK="$(mktemp -d /tmp/zohaonline-v0.6.2.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT
curl -fL --retry 3 "$BASE/zohaonline-v0.6.2.zip" -o "$WORK/zohaonline-v0.6.2.zip"
echo "f784e23165fe461a2f67b1bf5f01e97921b47585599fc28206e65e2dc5805363  $WORK/zohaonline-v0.6.2.zip" | sha256sum -c -
unzip -q "$WORK/zohaonline-v0.6.2.zip" -d "$WORK/package"
bash "$WORK/package/apply.sh" "${1:-/var/www/zoha}"
