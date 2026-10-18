#!/usr/bin/env bash
set -Eeuo pipefail
BASE="https://github.com/ostaddehdari/deployment-center/releases/download/zohaonline-v0.6.3"
WORK="$(mktemp -d /tmp/zohaonline-v0.6.3.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT
curl -fL --retry 3 "$BASE/zohaonline-v0.6.3.zip" -o "$WORK/zohaonline-v0.6.3.zip"
echo "26b71cc3a38aa1774149b936a0e31a63134a418bb633268426652548df5e65b1  $WORK/zohaonline-v0.6.3.zip" | sha256sum -c -
unzip -q "$WORK/zohaonline-v0.6.3.zip" -d "$WORK/package"
bash "$WORK/package/apply.sh" "${1:-/var/www/zoha}"
