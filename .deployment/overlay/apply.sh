#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${1:-/var/www/zoha}"
PKG="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "========== ZOHAONLINE v0.3.6 / PREVIEW CONTRACT ALIGNMENT =========="
[ -d .git ] || { echo 'ERROR: project is not git'; exit 2; }
BRANCH="$(git branch --show-current)"
[ "$BRANCH" = 'feature/zoha-public-site-v1' ] || { echo "ERROR: branch=$BRANCH"; exit 3; }
ORIGIN_URL="$(git remote get-url origin 2>/dev/null || true)"
case "$ORIGIN_URL" in
  *git.mtacloud.ir/vendors/zoha/zoha.git*) ;;
  *) echo "ERROR: unexpected origin: $ORIGIN_URL"; exit 4;;
esac

git merge-base --is-ancestor 02b76e32ea91776ae459c9e773f24c2a58d380ea HEAD || {
  echo 'ERROR: v0.3.3 base commit is not in branch history'
  exit 5
}
if ! git diff --cached --quiet; then
  echo 'ERROR: pre-existing staged changes; stopping.'
  git status --short
  exit 6
fi

FILES=(
'apps/api/src/admin-content-studio/admin-runtime-index.service.ts'
'apps/api/src/admin-content-studio/admin-runtime-index.controller.ts'
'apps/web/composables/useIndexRuntime.ts'
'apps/web/components/indexing/IndexPersonalSelect.vue'
'apps/web/components/indexing/IndexRuntimePanel.vue'
'apps/web/pages/admin/index-builder.vue'
'tests/admin-preview-auth.test.cjs'
'tests/real-index-builder.test.cjs'
)

BACKUP="/root/zoha-v036-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP"
for p in "${FILES[@]}"; do
  if [ -e "$p" ]; then
    mkdir -p "$BACKUP/$(dirname "$p")"
    cp -a "$p" "$BACKUP/$p"
  fi
done

echo "========== RESUME PREVIEW AUTH BRIDGE =========="
python3 "$PKG/scripts/patch-admin-preview-auth.py" "$ROOT"
mkdir -p tests
cp -a "$PKG/tests/admin-preview-auth.test.cjs" tests/admin-preview-auth.test.cjs

echo "========== ALIGN STALE BUILDER CONTRACT =========="
python3 "$PKG/scripts/patch-real-builder-preview-contract.py" "$ROOT"

echo "========== PREVIEW AUTH CONTRACT =========="
node --test tests/admin-preview-auth.test.cjs

echo "========== REAL INDEX BUILDER CONTRACT =========="
node --test tests/real-index-builder.test.cjs

echo "========== EXISTING RUNTIME CONTRACTS =========="
node --test tests/runtime-overview-sql.test.cjs
node --test tests/index-authoring-integration.test.cjs

echo "========== FULL CONTRACT SUITE =========="
npm run test:contracts

echo "========== BUILD API =========="
npm run build

echo "========== BUILD WEB =========="
npm run build:web

echo "========== DIFF CHECK =========="
git diff --check -- "${FILES[@]}"

echo "========== SOURCE VERIFY =========="
grep -q 'adminPreview?:boolean' apps/web/components/indexing/IndexPersonalSelect.vue
grep -q "useIndexRuntime(props.adminPreview?'admin-preview':'user')" apps/web/components/indexing/IndexRuntimePanel.vue
grep -q 'IndexPersonalSelect[^>]*code="IDX-001"' tests/real-index-builder.test.cjs
grep -q ':admin-preview="true"' apps/web/pages/admin/index-builder.vue

echo "========== COMMIT RELEASE FILES ONLY =========="
git add -- "${FILES[@]}"
if ! git diff --cached --quiet; then
  git -c user.name='ostaddehdari'       -c user.email='ostaddehdari@users.noreply.git.mtacloud.ir'       commit -m 'نمایه‌ساز: تکمیل پیش‌نمایش ادمین و هم‌راستاسازی تست'
else
  echo 'No source changes to commit; continuing verification.'
fi

LOCAL_SHA="$(git rev-parse HEAD)"

echo "========== PUSH TO GITLAB SOURCE OF TRUTH =========="
git push origin "HEAD:$BRANCH"
REMOTE_SHA="$(git ls-remote origin "refs/heads/$BRANCH" | awk '{print $1}')"
[ "$REMOTE_SHA" = "$LOCAL_SHA" ] || {
  echo "ERROR: GitLab SHA mismatch local=$LOCAL_SHA remote=$REMOTE_SHA"
  exit 7
}
echo "GITLAB_PUSH_VERIFIED=$REMOTE_SHA"

echo "========== RESTART =========="
systemctl restart zoha-api-v3 zoha-web
sleep 5
systemctl is-active --quiet zoha-api-v3
systemctl is-active --quiet zoha-web
echo 'zoha-api-v3=active'
echo 'zoha-web=active'

echo "========== FINAL =========="
echo "BRANCH=$BRANCH"
echo "GITLAB_SHA=$REMOTE_SHA"
echo "BACKUP=$BACKUP"
echo "ZOHAONLINE_ADMIN_PREVIEW_AUTH_V036=PASS"
