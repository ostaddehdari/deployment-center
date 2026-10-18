#!/usr/bin/env bash
set -Eeuo pipefail
TAG="zohaonline-v0.6.0"
BASE="https://github.com/ostaddehdari/deployment-center/releases/download/${TAG}"
WORK="$(mktemp -d /tmp/zohaonline-v0.6.0.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT
curl -fL --retry 3 "$BASE/zohaonline-v0.6.0.zip" -o "$WORK/zohaonline-v0.6.0.zip"
echo "d6149fda3024ee6c580676845029826316d34f4aa70bdc3fce7b375482cb9055  $WORK/zohaonline-v0.6.0.zip" | sha256sum -c -
unzip -q "$WORK/zohaonline-v0.6.0.zip" -d "$WORK/package"
bash "$WORK/package/apply.sh" "${1:-/var/www/zoha}"
