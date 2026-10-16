#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${1:-/var/www/zoha}"
PKG="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
echo "========== ZOHAONLINE v0.1.1 / INDEX DEFAULTS V2 HOTFIX =========="
[ -f apps/api/src/app.module.ts ] || { echo 'ERROR: پروژه ضحی در مسیر مورد انتظار نیست'; exit 2; }
[ -f database-v2/migrations/postgres/160_admin_content_type_index_builder.sql ] || { echo 'ERROR: ابتدا migration 160 نمایه‌ساز حرفه‌ای لازم است.'; exit 3; }
BRANCH="$(git branch --show-current)"
[ -n "$BRANCH" ] || { echo 'ERROR: detached HEAD مجاز نیست'; exit 4; }
ORIGIN_URL="$(git remote get-url origin 2>/dev/null || true)"
case "$ORIGIN_URL" in
  *git.mtacloud.ir/vendors/zoha/zoha.git*) ;;
  *) echo "ERROR: origin مورد انتظار GitLab ضحی نیست: $ORIGIN_URL"; exit 5;;
esac
BACKUP="/root/zoha-index-v011-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP"
for p in   apps/api/src/app.module.ts   apps/api/src/index-runtime   apps/web/components/indexing   apps/web/composables/useIndexRuntime.ts   'apps/web/pages/app/indexing/[contentType]/[contentId].vue'   data/index-defaults.json   tests/index-runtime-defaults.test.cjs   database-v2/migrations/postgres/170_index_defaults_personal_items.sql
 do
   if [ -e "$p" ]; then mkdir -p "$BACKUP/$(dirname "$p")"; cp -a "$p" "$BACKUP/$p"; fi
 done
mkdir -p apps/api/src/index-runtime apps/web/components/indexing apps/web/composables 'apps/web/pages/app/indexing/[contentType]/[contentId]' data tests
cp -a "$PKG/apps/api/src/index-runtime/." apps/api/src/index-runtime/
cp -a "$PKG/apps/web/components/indexing/." apps/web/components/indexing/
cp -a "$PKG/apps/web/composables/useIndexRuntime.ts" apps/web/composables/
cp -a "$PKG/apps/web/pages/app/indexing/[contentType]/[contentId].vue" 'apps/web/pages/app/indexing/[contentType]/[contentId].vue'
cp -a "$PKG/data/index-defaults.json" data/
cp -a "$PKG/tests/index-runtime-defaults.test.cjs" tests/
cp -a "$PKG/database-v2/migrations/postgres/170_index_defaults_personal_items.sql" database-v2/migrations/postgres/
python3 "$PKG/scripts/patch-index-runtime.py" "$ROOT"

echo "========== TESTS BEFORE DATABASE CHANGE =========="
node --test tests/index-runtime-defaults.test.cjs
npm run test:contracts

echo "========== BUILDS BEFORE DATABASE CHANGE =========="
npm run build
npm run build:web

echo "========== COMMIT SELECTED RELEASE FILES =========="
git add   apps/api/src/index-runtime   apps/api/src/app.module.ts   apps/web/components/indexing   apps/web/composables/useIndexRuntime.ts   'apps/web/pages/app/indexing/[contentType]/[contentId].vue'   database-v2/migrations/postgres/170_index_defaults_personal_items.sql   data/index-defaults.json   tests/index-runtime-defaults.test.cjs
if ! git diff --cached --quiet; then
  git -c user.name='ostaddehdari' -c user.email='ostaddehdari@users.noreply.git.mtacloud.ir'     commit -m 'نمایه‌گذاری عملیاتی: پیش‌فرض سه نوع محتوا و آیتم‌های شخصی'
else
  echo 'No new release-file changes to commit.'
fi
LOCAL_SHA="$(git rev-parse HEAD)"
echo "LOCAL_SHA=$LOCAL_SHA"

echo "========== PUSH TO GITLAB SOURCE OF TRUTH =========="
git push origin "HEAD:$BRANCH"
REMOTE_SHA="$(git ls-remote origin "refs/heads/$BRANCH" | awk '{print $1}')"
[ "$REMOTE_SHA" = "$LOCAL_SHA" ] || { echo "ERROR: GitLab SHA mismatch local=$LOCAL_SHA remote=$REMOTE_SHA"; exit 6; }
echo "GITLAB_PUSH_VERIFIED=$REMOTE_SHA"

echo "========== MIGRATION =========="
PGPASSWORD="$(cat /etc/zoha-online/postgres-password)" psql -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 5433 -U zoha_app -d zoha_core -f database-v2/migrations/postgres/170_index_defaults_personal_items.sql

echo "========== RESTART =========="
systemctl restart zoha-api-v3 zoha-web
sleep 4
systemctl is-active --quiet zoha-api-v3
systemctl is-active --quiet zoha-web

echo "========== DATABASE VERIFY =========="
PGPASSWORD="$(cat /etc/zoha-online/postgres-password)" psql -h 127.0.0.1 -p 5433 -U zoha_app -d zoha_core -c "SELECT post_type_code,count(*) AS active_fields FROM zoha.index_runtime_post_type_fields GROUP BY post_type_code ORDER BY post_type_code; SELECT taxonomy_code,count(*) AS defaults FROM zoha.index_runtime_terms GROUP BY taxonomy_code ORDER BY taxonomy_code LIMIT 12;"

echo "========== FINAL =========="
echo "BRANCH=$BRANCH"
echo "GITLAB_SHA=$REMOTE_SHA"
echo "BACKUP=$BACKUP"
echo "ZOHAONLINE_INDEX_V011=PASS"
