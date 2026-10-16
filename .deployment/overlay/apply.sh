#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${1:-/var/www/zoha}"
PKG="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "========== ZOHAONLINE v0.3.2 / RUNTIME BUILDER CONTRACT ALIGNMENT =========="
[ -d .git ] || { echo 'ERROR: project is not git'; exit 2; }
BRANCH="$(git branch --show-current)"
[ "$BRANCH" = 'feature/zoha-public-site-v1' ] || { echo "ERROR: branch=$BRANCH"; exit 3; }
ORIGIN_URL="$(git remote get-url origin 2>/dev/null || true)"
case "$ORIGIN_URL" in
  *git.mtacloud.ir/vendors/zoha/zoha.git*) ;;
  *) echo "ERROR: unexpected origin: $ORIGIN_URL"; exit 4;;
esac

git merge-base --is-ancestor aca88c7660acb3a9da255039acea00e3f5b0a0b8 HEAD || {
  echo 'ERROR: v0.2.2 base commit is not in branch history'
  exit 5
}
if ! git diff --cached --quiet; then
  echo 'ERROR: pre-existing staged changes; stopping.'
  git status --short
  exit 6
fi

FILES=(
'apps/api/src/app.module.ts'
'apps/api/src/admin-content-studio/admin-runtime-index.controller.ts'
'apps/api/src/admin-content-studio/admin-runtime-index.dto.ts'
'apps/api/src/admin-content-studio/admin-runtime-index.service.ts'
'apps/api/src/index-runtime/index-runtime.service.ts'
'apps/web/composables/useAdminRuntimeIndex.ts'
'apps/web/composables/useIndexRuntime.ts'
'apps/web/types/admin-runtime-index.ts'
'apps/web/pages/admin/index-builder.vue'
'apps/web/pages/admin/content-types.vue'
'apps/web/components/admin/AdminSidebar.vue'
'apps/web/components/indexing/IndexRuntimePanel.vue'
'apps/web/components/indexing/IndexPersonalSelect.vue'
'tests/real-index-builder.test.cjs'
'tests/admin-content-studio.test.cjs'
)

BACKUP="/root/zoha-v032-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP"
for p in "${FILES[@]}"; do
  if [ -e "$p" ]; then
    mkdir -p "$BACKUP/$(dirname "$p")"
    cp -a "$p" "$BACKUP/$p"
  fi
done

echo "========== REPAIR AND VERIFY v0.3.0 SOURCE PAYLOAD =========="
python3 - "$PKG/patch-v030.part-01" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
s=p.read_text(encoding='ascii')
if len(s) != 15000:
    raise SystemExit(f'ERROR: unexpected part length {len(s)}')
if s[13909] == 'h':
    s=s[:13909]+'H'+s[13910:]
    p.write_text(s,encoding='ascii')
    print('PAYLOAD_CHAR_REPAIRED=YES position=13909 h->H')
elif s[13909] == 'H':
    print('PAYLOAD_CHAR_ALREADY_CORRECT=YES')
else:
    raise SystemExit(f'ERROR: unexpected character at 13909: {s[13909]!r}')
PY

PATCH_TGZ="$(mktemp /tmp/zoha-v030-patch.XXXXXX.tgz)"
LIST_FILE="$(mktemp /tmp/zoha-v032-tar-list.XXXXXX)"
trap 'rm -f "$PATCH_TGZ" "$LIST_FILE"' EXIT
cat "$PKG"/patch-v030.part-* | base64 -d > "$PATCH_TGZ"
echo "1bb67e515bb0f514bb6c50d88144b2e68a920e0fdb37d248cabd5605ec38d2dd  $PATCH_TGZ" | sha256sum -c -
tar -tzf "$PATCH_TGZ" > "$LIST_FILE"
if grep -Eq '^/|(^|/)\.\.(/|$)' "$LIST_FILE"; then
  echo 'ERROR: unsafe path in source patch'
  exit 7
fi

echo "========== REAPPLY VERIFIED REAL BUILDER SOURCE =========="
tar -xzf "$PATCH_TGZ" -C "$ROOT"
cp -a "$PKG/tests/admin-content-studio.test.cjs" "$ROOT/tests/admin-content-studio.test.cjs"

echo "========== UPDATED CONTENT STUDIO CONTRACT =========="
node --test tests/admin-content-studio.test.cjs

echo "========== REAL INDEX BUILDER CONTRACT =========="
node --test tests/real-index-builder.test.cjs

echo "========== EXISTING INDEX CONTRACTS =========="
node --test tests/index-runtime-defaults.test.cjs
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
  git -c user.name='ostaddehdari'       -c user.email='ostaddehdari@users.noreply.git.mtacloud.ir'       commit -m 'نمایه‌ساز واقعی: هم‌راستاسازی تست‌ها با Runtime Builder'
else
  echo 'No source changes to commit; continuing verification.'
fi

LOCAL_SHA="$(git rev-parse HEAD)"
echo "========== PUSH TO GITLAB SOURCE OF TRUTH =========="
git push origin "HEAD:$BRANCH"
REMOTE_SHA="$(git ls-remote origin "refs/heads/$BRANCH" | awk '{print $1}')"
[ "$REMOTE_SHA" = "$LOCAL_SHA" ] || {
  echo "ERROR: GitLab SHA mismatch local=$LOCAL_SHA remote=$REMOTE_SHA"
  exit 8
}
echo "GITLAB_PUSH_VERIFIED=$REMOTE_SHA"

echo "========== RUNTIME DATABASE PRECHECK =========="
PGPASSWORD="$(cat /etc/zoha-online/postgres-password)"
export PGPASSWORD
COUNTS="$(psql -h 127.0.0.1 -p 5433 -U zoha_app -d zoha_core -Atc "SELECT (SELECT count(*) FROM zoha.index_runtime_taxonomies WHERE is_active)||'|'||(SELECT count(*) FROM zoha.index_runtime_post_type_fields)||'|'||(SELECT count(*) FROM zoha.index_runtime_terms WHERE is_active);")"
IFS='|' read -r TAXONOMIES POST_TYPE_FIELDS ACTIVE_TERMS <<< "$COUNTS"
echo "taxonomies=$TAXONOMIES post_type_fields=$POST_TYPE_FIELDS active_terms=$ACTIVE_TERMS"
[ "$TAXONOMIES" -eq 40 ] || { echo 'ERROR: runtime taxonomy count'; exit 9; }
[ "$POST_TYPE_FIELDS" -eq 98 ] || { echo 'ERROR: runtime post type field count'; exit 10; }
[ "$ACTIVE_TERMS" -gt 0 ] || { echo 'ERROR: runtime terms empty'; exit 11; }

echo "========== RESTART =========="
systemctl restart zoha-api-v3 zoha-web
sleep 5
systemctl is-active --quiet zoha-api-v3
systemctl is-active --quiet zoha-web
echo 'zoha-api-v3=active'
echo 'zoha-web=active'

echo "========== SOURCE VERIFY =========="
grep -q 'useAdminRuntimeIndex' apps/web/pages/admin/index-builder.vue
grep -q 'IndexRuntimePanel' apps/web/pages/admin/index-builder.vue
grep -q 'مدیریت آیتم‌های فهرست' apps/web/pages/admin/index-builder.vue
grep -q 'نمایه‌ساز این نوع' apps/web/pages/admin/content-types.vue
grep -q 'نمایه‌های واقعی' apps/web/pages/admin/content-types.vue
! grep -q "label:'نمایه‌ها'" apps/web/components/admin/AdminSidebar.vue
grep -q 'AdminRuntimeIndexController' apps/api/src/app.module.ts
grep -q 'runtime-backed with collapsible tabs real preview and term management' tests/admin-content-studio.test.cjs

echo "========== FINAL =========="
echo "BRANCH=$BRANCH"
echo "GITLAB_SHA=$REMOTE_SHA"
echo "BACKUP=$BACKUP"
echo "ZOHAONLINE_REAL_INDEX_BUILDER_V032=PASS"
