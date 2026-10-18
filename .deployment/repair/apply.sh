#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
ROOT="${1:-/var/www/zoha}"
PKG="$(cd "$(dirname "$0")" && pwd)"
BASE='9b317ca2967bb2929d5eeaf042f3cca3522cebf0'
BRANCH='feature/zoha-public-site-v1'
cd "$ROOT"
echo '========== ZOHAONLINE v0.6.1 / RESTORE API EXECUTABLE AND OTP HEALTH =========='
[ "$(git rev-parse HEAD)" = "$BASE" ] || { echo 'ERROR: expected installed v0.6.0 source commit'; exit 2; }
[ "$(git branch --show-current)" = "$BRANCH" ] || exit 3
case "$(git remote get-url origin)" in *git.mtacloud.ir/vendors/zoha/zoha.git*) ;; *) exit 4;; esac
FILES=(apps/api/package.json apps/api/tsconfig.build.json scripts/verify-zoha-api-build.cjs)
[ -z "$(git status --porcelain -- "${FILES[@]}")" ] || { echo 'ERROR: build configuration has local changes; stopping'; exit 5; }
git diff --cached --quiet || { echo 'ERROR: existing staged changes'; exit 6; }
[ "$(git ls-remote origin "refs/heads/$BRANCH" | awk '{print $1}')" = "$BASE" ] || { echo 'ERROR: remote source changed'; exit 7; }
[ -f apps/api/tsconfig.build.json ] || { echo 'ERROR: build tsconfig missing'; exit 8; }
BACKUP="$(mktemp -d /root/zoha-v061-api-backup-XXXXXXXX)"
: > "$BACKUP/absent"
for file in "${FILES[@]}"; do
 if [ -e "$file" ]; then mkdir -p "$BACKUP/source/$(dirname "$file")"; cp -a "$file" "$BACKUP/source/$file"; else printf '%s\n' "$file" >> "$BACKUP/absent"; fi
done
if [ -d apps/api/dist ]; then cp -a apps/api/dist "$BACKUP/dist"; fi
COMMITTED=0
rollback(){
 rc=$?;trap - EXIT
 if [ "$rc" != 0 ] && [ "$COMMITTED" = 0 ]; then
  set +e
  systemctl stop zoha-api-v3
  for file in "${FILES[@]}"; do if [ -e "$BACKUP/source/$file" ]; then cp -a "$BACKUP/source/$file" "$file"; fi; done
  while IFS= read -r file; do [ -n "$file" ] && rm -f -- "$file"; done < "$BACKUP/absent"
  git reset -q -- "${FILES[@]}"
  if [ -d "$BACKUP/dist" ]; then rm -rf apps/api/dist; cp -a "$BACKUP/dist" apps/api/dist; fi
  if [ -s apps/api/dist/main.js ]; then systemctl start zoha-api-v3; fi
  echo "REPAIR_FAILED_BACKUP=$BACKUP"
  journalctl -u zoha-api-v3 -n 35 --no-pager -o cat
 fi
 exit "$rc"
}
trap rollback EXIT
echo "API_BUILD_BACKUP=$BACKUP"
systemctl stop zoha-api-v3
node "$PKG/patch-build.cjs" "$ROOT"
install -D -m 0644 "$PKG/verify-zoha-api-build.cjs" scripts/verify-zoha-api-build.cjs
npm run build
[ -s apps/api/dist/main.js ] || { echo 'ERROR: main.js was not emitted'; exit 9; }
node --check apps/api/dist/main.js
node --test tests/index-hierarchy.test.cjs tests/gravity-toolbox.test.cjs
npm run test:contracts
git diff --check -- "${FILES[@]}"
systemctl reset-failed zoha-api-v3
systemctl start zoha-api-v3
# An empty OTP body cannot identify a recipient; a JSON validation response proves the actual API is alive.
healthy=0
for attempt in {1..25}; do
 status="$(curl -ksS --max-time 4 -o "$BACKUP/otp-validation.json" -w '%{http_code}' \
  -X POST 'https://185.73.114.144/public/auth/user/v1/requestOtp' \
  -H 'Content-Type: application/json' -H 'AppId: 1' -H 'ServiceId: 1' \
  -H 'UserId: 1' -H 'Language: fa' -H "CorrelationId: $(cat /proc/sys/kernel/random/uuid)" --data '{}' || true)"
 if [[ "$status" =~ ^(400|401|403|422)$ ]] && node -e 'JSON.parse(require("node:fs").readFileSync(process.argv[1],"utf8"))' "$BACKUP/otp-validation.json" >/dev/null 2>&1; then healthy=1;break;fi
 sleep 1
done
[ "$healthy" = 1 ] || { echo "ERROR: OTP validation route did not become healthy HTTP=$status"; exit 10; }
PID="$(systemctl show zoha-api-v3 -p MainPID --value)"
[ "$PID" != 0 ] || exit 11
for attempt in {1..5}; do sleep 1;systemctl is-active --quiet zoha-api-v3;[ "$(systemctl show zoha-api-v3 -p MainPID --value)" = "$PID" ]; done
echo "OTP_API_VALIDATION_HTTP=$status"
echo 'API_PROCESS_STABLE=PASS'
git add -- "${FILES[@]}"
git -c user.name='ostaddehdari' -c user.email='ostaddehdari@users.noreply.git.mtacloud.ir' commit -m 'رفع خروجی ناقص build و تضمین فایل اجرایی API و بررسی سلامت ورود'
COMMITTED=1
SHA="$(git rev-parse HEAD)"
if ! git push origin "HEAD:$BRANCH"; then echo "API_REPAIRED_PUSH_PENDING=$SHA";exit 12;fi
[ "$(git ls-remote origin "refs/heads/$BRANCH" | awk '{print $1}')" = "$SHA" ] || exit 13
echo "GITLAB_PUSH_VERIFIED=$SHA"
echo "BACKUP=$BACKUP"
echo 'ZOHAONLINE_API_V061=PASS'
