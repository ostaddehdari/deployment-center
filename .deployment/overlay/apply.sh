#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${1:-/var/www/zoha}"
PKG="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "========== ZOHAONLINE v0.2.1 / COMPONENT RESOLUTION HOTFIX =========="
[ -d .git ] || { echo 'ERROR: مسیر پروژه git نیست'; exit 2; }
BRANCH="$(git branch --show-current)"
[ "$BRANCH" = 'feature/zoha-public-site-v1' ] || { echo "ERROR: branch=$BRANCH"; exit 3; }
ORIGIN_URL="$(git remote get-url origin 2>/dev/null || true)"
case "$ORIGIN_URL" in
  *git.mtacloud.ir/vendors/zoha/zoha.git*) ;;
  *) echo "ERROR: origin مورد انتظار GitLab ضحی نیست: $ORIGIN_URL"; exit 4;;
esac

git merge-base --is-ancestor d7e9298e1a989124c79bf529ffee5a5184885f2f HEAD || {
  echo 'ERROR: commit پایه v0.2.0 در تاریخچه شاخه نیست'
  exit 5
}
if ! git diff --cached --quiet; then
  echo 'ERROR: staged changes قبلی وجود دارد؛ نصب متوقف شد.'
  git status --short
  exit 6
fi

FILES=(
'apps/web/components/content/ContentAuthoringShell.vue'
'apps/web/components/indexing/IndexRuntimePanel.vue'
'apps/web/pages/app/create/fiche.vue'
'apps/web/pages/app/create/sermon.vue'
'apps/web/pages/app/create/supporting.vue'
'apps/web/pages/app/content/[id]/edit.vue'
'apps/web/pages/app/content/[id]/indexing.vue'
'tests/component-resolution.test.cjs'
)
LEGACY='apps/web/pages/app/indexing/[contentType]/[contentId].vue'
[ -f "$LEGACY" ] && FILES+=("$LEGACY")

BACKUP="/root/zoha-v021-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP"
for p in "${FILES[@]}"; do
  if [ -e "$p" ]; then
    mkdir -p "$BACKUP/$(dirname "$p")"
    cp -a "$p" "$BACKUP/$p"
  fi
done

mkdir -p tests
cp -a "$PKG/tests/component-resolution.test.cjs" tests/
python3 "$PKG/scripts/patch-component-resolution.py" "$ROOT"

echo "========== COMPONENT RESOLUTION CONTRACT =========="
node --test tests/component-resolution.test.cjs
node --test tests/index-authoring-integration.test.cjs

echo "========== FULL CONTRACT SUITE =========="
npm run test:contracts

echo "========== BUILD API =========="
npm run build

echo "========== BUILD WEB =========="
npm run build:web

echo "========== DIFF CHECK =========="
git diff --check -- "${FILES[@]}"

echo "========== COMMIT RELEASE FILES ONLY =========="
git add -- "${FILES[@]}"
if ! git diff --cached --quiet; then
  git -c user.name='ostaddehdari'       -c user.email='ostaddehdari@users.noreply.git.mtacloud.ir'       commit -m 'فرم محتوا: رفع صفحه سفید با import صریح کامپوننت‌های نمایه‌گذاری'
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

echo "========== SOURCE VERIFY =========="
grep -q "import ContentAuthoringShell from '~/components/content/ContentAuthoringShell.vue'" apps/web/pages/app/create/fiche.vue
grep -q "import ContentAuthoringShell from '~/components/content/ContentAuthoringShell.vue'" 'apps/web/pages/app/content/[id]/edit.vue'
grep -q "import IndexRuntimePanel from '~/components/indexing/IndexRuntimePanel.vue'" 'apps/web/pages/app/content/[id]/indexing.vue'
grep -q "import IndexRuntimePanel from '~/components/indexing/IndexRuntimePanel.vue'" apps/web/components/content/ContentAuthoringShell.vue
grep -q "import IndexPersonalSelect from '~/components/indexing/IndexPersonalSelect.vue'" apps/web/components/indexing/IndexRuntimePanel.vue

echo "========== FINAL =========="
echo "BRANCH=$BRANCH"
echo "GITLAB_SHA=$REMOTE_SHA"
echo "BACKUP=$BACKUP"
echo "ZOHAONLINE_COMPONENT_RESOLUTION_V021=PASS"
