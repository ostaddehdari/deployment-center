#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${1:-/var/www/zoha}"
PKG="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "========== ZOHAONLINE v0.3.4 / ADMIN PREVIEW AUTH BRIDGE =========="
[ -d .git ] || { echo 'ERROR: project is not git'; exit 2; }
BRANCH="$(git branch --show-current)"
[ "$BRANCH" = 'feature/zoha-public-site-v1' ] || { echo "ERROR: branch=$BRANCH"; exit 3; }
git merge-base --is-ancestor 02b76e32ea91776ae459c9e773f24c2a58d380ea HEAD || { echo 'ERROR: v0.3.3 base missing'; exit 4; }
if ! git diff --cached --quiet; then echo 'ERROR: staged changes exist'; git status --short; exit 5; fi

FILES=(
'apps/api/src/admin-content-studio/admin-runtime-index.service.ts'
'apps/api/src/admin-content-studio/admin-runtime-index.controller.ts'
'apps/web/composables/useIndexRuntime.ts'
'apps/web/components/indexing/IndexPersonalSelect.vue'
'apps/web/components/indexing/IndexRuntimePanel.vue'
'apps/web/pages/admin/index-builder.vue'
'tests/admin-preview-auth.test.cjs'
)
BACKUP="/root/zoha-v034-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP"
for p in "${FILES[@]}"; do
 if [ -e "$p" ]; then mkdir -p "$BACKUP/$(dirname "$p")"; cp -a "$p" "$BACKUP/$p"; fi
done

python3 "$PKG/scripts/patch-admin-preview-auth.py" "$ROOT"
cp -a "$PKG/tests/admin-preview-auth.test.cjs" tests/admin-preview-auth.test.cjs

echo "========== PREVIEW AUTH CONTRACT =========="
node --test tests/admin-preview-auth.test.cjs

echo "========== FULL CONTRACT SUITE =========="
npm run test:contracts

echo "========== BUILD API =========="
npm run build

echo "========== BUILD WEB =========="
npm run build:web

echo "========== DIFF CHECK =========="
git diff --check -- "${FILES[@]}"

git add -- "${FILES[@]}"
if ! git diff --cached --quiet; then
 git -c user.name='ostaddehdari' -c user.email='ostaddehdari@users.noreply.git.mtacloud.ir' commit -m 'نمایه‌ساز: رفع احراز هویت پیش‌نمایش مدیریت'
fi

LOCAL_SHA="$(git rev-parse HEAD)"
git push origin "HEAD:$BRANCH"
REMOTE_SHA="$(git ls-remote origin "refs/heads/$BRANCH" | awk '{print $1}')"
[ "$REMOTE_SHA" = "$LOCAL_SHA" ] || { echo "ERROR: GitLab SHA mismatch"; exit 6; }
echo "GITLAB_PUSH_VERIFIED=$REMOTE_SHA"

systemctl restart zoha-api-v3 zoha-web
sleep 5
systemctl is-active --quiet zoha-api-v3
systemctl is-active --quiet zoha-web
echo 'zoha-api-v3=active'
echo 'zoha-web=active'

grep -q "preview/schema/:contentType" apps/api/src/admin-content-studio/admin-runtime-index.controller.ts
grep -q "admin-preview" apps/web/composables/useIndexRuntime.ts
grep -q ':admin-preview="true"' apps/web/pages/admin/index-builder.vue

echo "BRANCH=$BRANCH"
echo "GITLAB_SHA=$REMOTE_SHA"
echo "BACKUP=$BACKUP"
echo "ZOHAONLINE_ADMIN_PREVIEW_AUTH_V034=PASS"
