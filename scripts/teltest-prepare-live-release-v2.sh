#!/usr/bin/env bash
# Prepare a public-release candidate from the ACTUAL installed TelTest code.
# Does NOT change running services, queue, credentials, or application files.
set -Eeuo pipefail
umask 077
TAG="$1"
[[ "$(hostname)" == VMID-20571 && "$(id -u)" -eq 0 ]] || { echo ERROR_WRONG_HOST_OR_USER;exit 2; }
[[ "$TAG" =~ ^teltest-v0[.]12[.]2-live[.][0-9]{8}[.][0-9]+$ ]] || { echo ERROR_BAD_PINNED_TAG;exit 2; }
BASE=/root/deployment-center-teltest
OUT="/root/teltest-release-prepared/$TAG"
[[ ! -e "$OUT" ]] || { echo ERROR_RELEASE_DIRECTORY_ALREADY_EXISTS;exit 3; }
for f in "$BASE/pack_live.py" "$BASE/install-release.sh" /opt/teltest/repo/eitaa_live_gateway.py;do
  [[ -f "$f" && ! -L "$f" ]] || { echo "ERROR_REQUIRED_FILE=$f";exit 3; }
done
echo '10e0590b2be54b18a1936253a62d91f38089903d4bd1e599ff5e56b1da48a1d0  /root/deployment-center-teltest/pack_live.py' | sha256sum -c -
echo '0685b6b1ca6f4debedb721fa9e8ed9ace9da1fb174ae9d09516bb528ab6ad96a  /root/deployment-center-teltest/install-release.sh' | sha256sum -c -
for s in teltest.service teltest-eitaa-gateway.service;do systemctl is-active --quiet "$s" || { echo "ERROR_SERVICE=$s";exit 3;};done
for s in teltest-delivery.timer teltest-scheduler.timer teltest-delivery.service;do
  ! systemctl is-active --quiet "$s" || { echo "ERROR_UNSAFE_WORKER=$s";exit 3; }
done
curl -fsS --max-time 10 http://127.0.0.1:18870/teltest/health | python3 -c 'import json,sys;d=json.load(sys.stdin);assert d["ok"] and d["app"]=="teltest"'
python3 - <<'PY'
import sqlite3,pathlib
s=pathlib.Path('/opt/teltest/repo/eitaa_live_gateway.py').read_text(encoding='utf8')
assert '# TELTEST_EITAA_NATIVE_PHOTO_V1' in s and '_native_eitaa_media_type' in s, 'NATIVE_PHOTO_MISSING'
with sqlite3.connect('file:/var/lib/teltest/data/teltest.sqlite3?mode=ro',uri=True) as c:
    assert c.execute('SELECT state,pause_requested FROM delivery_queue WHERE job_id=11').fetchone()==('paused',1), 'JOB11_NOT_PAUSED'
    assert not c.execute("SELECT 1 FROM delivery_queue WHERE state='running' LIMIT 1").fetchone(), 'DELIVERY_ACTIVE'
print('NATIVE_PHOTO_AND_JOB11_GUARDS_OK')
PY
mkdir -p "$OUT"
python3 "$BASE/pack_live.py" --tag "$TAG" --output "$OUT"
cp "$BASE/install-release.sh" "$OUT/install-release.sh"
cat > "$OUT/release-notes.md" <<EOF
# $TAG — TelTest verified live source snapshot

From production /opt/teltest/repo on VMID-20571.

Includes confirmed production Eitaa native-photo JPEG/PNG routing, accounts UI, extraction and transfer runtime.
Does not include database, credentials, OTP, sessions, tokens, media, backups, or separate EitaaBun gateway.

Safety: job 11 and delivery timers must remain stopped. Perform only a checksummed --check before considering any --apply.

PUBLIC RELEASE WARNING: inspect source and packaged files for embedded secrets before publishing.
EOF
(cd "$OUT" && sha256sum "$TAG.zip" install-release.sh release-manifest.json > SHA256SUMS && sha256sum -c SHA256SUMS)
unzip -p "$OUT/$TAG.zip" app/eitaa_live_gateway.py | grep -Fq '# TELTEST_EITAA_NATIVE_PHOTO_V1' || { echo ERROR_NATIVE_PHOTO_NOT_IN_ZIP;exit 4; }
python3 - "$OUT/release-manifest.json" "$TAG" <<'PY'
import json,sys
p,t=sys.argv[1:]
d=json.load(open(p))
assert d['tag']==t and len(d['source_files'])>=50 and 'eitaa_live_gateway.py' in d['source_files']
print('MANIFEST_SOURCE_FILES=',len(d['source_files']))
PY
echo "RELEASE_PREPARED=$OUT"
echo 'PREPARE_ONLY__NOT_UPLOADED__PRODUCTION_UNCHANGED'
echo 'PUBLIC_RELEASE_REQUIRES_SECRETS_REVIEW=YES'
