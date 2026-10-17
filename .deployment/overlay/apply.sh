#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${1:-/var/www/zoha}"
PKG="$(cd "$(dirname "$0")" && pwd)"
BASE_SHA="eb140a90aa78b4b92f4443a94591af415fd36392"
BRANCH_EXPECTED="feature/zoha-public-site-v1"

cd "$ROOT"

echo "========== ZOHAONLINE v0.4.4 / DIRECT HYBRID BUILDER =========="
[ -d .git ] || { echo "ERROR: $ROOT is not a git repository"; exit 2; }
BRANCH="$(git branch --show-current)"
[ "$BRANCH" = "$BRANCH_EXPECTED" ] || { echo "ERROR: unexpected branch=$BRANCH"; exit 3; }
ORIGIN_URL="$(git remote get-url origin 2>/dev/null || true)"
case "$ORIGIN_URL" in *git.mtacloud.ir/vendors/zoha/zoha.git*) ;; *) echo "ERROR: unexpected origin=$ORIGIN_URL"; exit 4;; esac
HEAD_SHA="$(git rev-parse HEAD)"
[ "$HEAD_SHA" = "$BASE_SHA" ] || { echo "ERROR: expected base HEAD=$BASE_SHA found=$HEAD_SHA"; exit 5; }
if ! git diff --cached --quiet; then echo "ERROR: pre-existing staged changes detected"; git status --short; exit 6; fi

echo "========== VERIFY DIRECT PATCH =========="
PATCH="$PKG/zohaonline-v0.4.4.patch"
PATCH_SHA="b80bbbdac908c434bf2db1588640db3c6fb2258bd7c668fdac8b84e379ccd58f"
[ -f "$PATCH" ] || { echo "ERROR: missing release patch $PATCH"; exit 7; }
echo "$PATCH_SHA  $PATCH" | sha256sum -c -
git apply --check "$PATCH"
echo "DIRECT_PATCH_VERIFY=PASS"

FILES=(
 'apps/api/src/admin-content-studio/admin-content-studio.dto.ts'
 'apps/api/src/admin-content-studio/admin-content-studio.service.ts'
 'apps/api/src/index-runtime/index-runtime.service.ts'
 'apps/web/composables/useIndexRuntime.ts'
 'apps/web/components/indexing/IndexRuntimePanel.vue'
 'apps/web/components/indexing/IndexDynamicField.vue'
 'apps/web/pages/admin/index-builder.vue'
 'database-v2/migrations/postgres/180_hybrid_runtime_index_builder.sql'
 'tests/admin-content-studio.test.cjs'
 'tests/real-index-builder.test.cjs'
)

OWNED_DIRTY="$(git status --porcelain -- "${FILES[@]}")"
if [ -n "$OWNED_DIRTY" ]; then
  echo "ERROR: pre-existing changes detected in v0.4.4-owned paths; refusing to overwrite."
  printf '%s\n' "$OWNED_DIRTY"
  exit 7
fi

BACKUP="/root/zoha-v044-source-backup-$(date +%Y%m%d-%H%M%S)"
ABSENT_LIST="$BACKUP/.absent"
mkdir -p "$BACKUP"
: > "$ABSENT_LIST"
for p in "${FILES[@]}"; do
  if [ -e "$p" ]; then
    mkdir -p "$BACKUP/$(dirname "$p")"
    cp -a "$p" "$BACKUP/$p"
  else
    printf '%s\n' "$p" >> "$ABSENT_LIST"
  fi
done
echo "SOURCE_BACKUP=$BACKUP"

COMMITTED=0
rollback_source(){
  rc=$?
  if [ "$rc" -ne 0 ] && [ "$COMMITTED" -eq 0 ]; then
    echo "========== AUTO ROLLBACK RELEASE-OWNED SOURCE =========="
    for p in "${FILES[@]}"; do
      if [ -e "$BACKUP/$p" ]; then
        mkdir -p "$(dirname "$p")"
        cp -a "$BACKUP/$p" "$p"
      fi
    done
    if [ -s "$ABSENT_LIST" ]; then
      while IFS= read -r p; do [ -n "$p" ] && rm -f -- "$p"; done < "$ABSENT_LIST"
    fi
    git reset -q -- "${FILES[@]}" 2>/dev/null || true
    echo "SOURCE_ROLLBACK=PASS"
  fi
  exit "$rc"
}
trap rollback_source ERR

echo "========== APPLY DIRECT PATCH =========="
git apply "$PATCH"
echo "DIRECT_PATCH_APPLY=PASS"

echo "========== HYBRID BUILDER CONTRACTS =========="
node --test tests/admin-content-studio.test.cjs tests/real-index-builder.test.cjs tests/index-authoring-integration.test.cjs tests/runtime-overview-sql.test.cjs

echo "========== FULL CONTRACT SUITE =========="
npm run test:contracts

echo "========== BUILD API =========="
npm run build

echo "========== CLEAN / BUILD WEB =========="
rm -rf apps/web/.nuxt apps/web/.output
npm run build:web

echo "========== DIFF CHECK =========="
git diff --check -- "${FILES[@]}"

echo "========== SOURCE VERIFY =========="
check_fixed(){ local label="$1" needle="$2" file="$3"; if grep -Fq -- "$needle" "$file"; then echo "PASS: $label"; else echo "FAIL: $label"; echo " file=$file"; echo " expected=$needle"; exit 8; fi; }
check_fixed 'Gravity toolbox restored' 'field-palette' apps/web/pages/admin/index-builder.vue
check_fixed 'Versioned studio connected' 'useAdminContentStudio' apps/web/pages/admin/index-builder.vue
check_fixed 'Runtime vocabulary connected' 'useAdminRuntimeIndex' apps/web/pages/admin/index-builder.vue
check_fixed 'Manual option source exists' 'گزینه‌های دستی' apps/web/pages/admin/index-builder.vue
check_fixed 'Conditional logic exists' 'منطق شرطی' apps/web/pages/admin/index-builder.vue
check_fixed 'Draft schema override exists' ':schema-override="previewSchema"' apps/web/pages/admin/index-builder.vue
check_fixed 'Dynamic renderer exists' 'IndexDynamicField' apps/web/components/indexing/IndexRuntimePanel.vue
check_fixed 'Published form drives runtime' 'content_type_index_forms' apps/api/src/index-runtime/index-runtime.service.ts
check_fixed 'Runtime fallback preserved' 'runtime-fallback' apps/api/src/index-runtime/index-runtime.service.ts
check_fixed 'Searchable select accepted by DTO' "'searchable_select'" apps/api/src/admin-content-studio/admin-content-studio.dto.ts
check_fixed 'Migration bridge marker exists' 'runtime-hybrid-v4-direct-source' database-v2/migrations/postgres/180_hybrid_runtime_index_builder.sql
echo "SOURCE_VERIFY=PASS"

echo "========== COMMIT RELEASE FILES ONLY =========="
git add -- "${FILES[@]}"
if git diff --cached --quiet; then echo "ERROR: no v0.4.4 source changes staged"; exit 9; fi
git -c user.name='ostaddehdari' -c user.email='ostaddehdari@users.noreply.git.mtacloud.ir' commit -m 'نمایه‌ساز حرفه‌ای: Toolbox فرم و اتصال Runtime نسخه‌دار'
LOCAL_SHA="$(git rev-parse HEAD)"
COMMITTED=1

echo "========== PUSH TO GITLAB SOURCE OF TRUTH =========="
git push origin "HEAD:$BRANCH"
REMOTE_SHA="$(git ls-remote origin "refs/heads/$BRANCH" | awk '{print $1}')"
[ "$REMOTE_SHA" = "$LOCAL_SHA" ] || { echo "ERROR: GitLab SHA mismatch local=$LOCAL_SHA remote=$REMOTE_SHA"; exit 10; }
echo "GITLAB_PUSH_VERIFIED=$REMOTE_SHA"

echo "========== BACKUP INDEX FORM DATABASE =========="
export PGPASSWORD="$(cat /etc/zoha-online/postgres-password)"
DB_BACKUP="/root/zoha-v044-index-form-data-$(date +%Y%m%d-%H%M%S).sql"
pg_dump -h 127.0.0.1 -p 5433 -U zoha_app -d zoha_core --data-only --inserts \
 --table=zoha.index_forms \
 --table=zoha.index_form_versions \
 --table=zoha.index_form_fields \
 --table=zoha.index_form_options \
 --table=zoha.index_form_rules \
 --table=zoha.content_type_index_forms > "$DB_BACKUP"
echo "DB_BACKUP=$DB_BACKUP"

echo "========== APPLY MIGRATION 180 =========="
bash database-v2/deploy/apply-schema.sh --apply

echo "========== VERIFY MIGRATION / FIELD COUNTS =========="
MIGRATION_COUNT="$(psql -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 5433 -U zoha_app -d zoha_core -Atc "SELECT count(*) FROM zoha.schema_migrations WHERE version='180_hybrid_runtime_index_builder';")"
[ "$MIGRATION_COUNT" = "1" ] || { echo "ERROR: migration 180 not recorded"; exit 11; }
echo "MIGRATION_180=PASS"

COUNTS="$(psql -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 5433 -U zoha_app -d zoha_core -AtF '|' -c "
WITH wanted(code,expected) AS (VALUES ('mold',33),('full_sermon',34),('supporting',31)), actual AS (
 SELECT ct.code,count(ff.id)::int AS n
 FROM zoha.content_types ct
 JOIN zoha.content_type_index_forms m ON m.content_type_id=ct.id AND m.is_primary AND m.active AND NOT m.deleted
 JOIN zoha.index_forms f ON f.id=m.index_form_id AND f.active AND NOT f.deleted
 JOIN zoha.index_form_versions v ON v.index_form_id=f.id AND v.version=f.active_version AND v.active AND NOT v.deleted
 LEFT JOIN zoha.index_form_fields ff ON ff.version_id=v.id AND ff.active AND NOT ff.deleted
 WHERE ct.code IN ('mold','full_sermon','supporting') GROUP BY ct.code
)
SELECT w.code,w.expected,COALESCE(a.n,0) FROM wanted w LEFT JOIN actual a USING(code) ORDER BY w.code;")"
echo "$COUNTS"
while IFS='|' read -r code expected actual; do [ "$expected" = "$actual" ] || { echo "ERROR: active fields $code expected=$expected actual=$actual"; exit 12; }; done <<< "$COUNTS"

DRAFT_COUNTS="$(psql -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 5433 -U zoha_app -d zoha_core -AtF '|' -c "
WITH wanted(code,expected) AS (VALUES ('mold',33),('full_sermon',34),('supporting',31)), actual AS (
 SELECT ct.code,count(ff.id)::int AS n
 FROM zoha.content_types ct
 JOIN zoha.content_type_index_forms m ON m.content_type_id=ct.id AND m.is_primary AND m.active AND NOT m.deleted
 JOIN zoha.index_forms f ON f.id=m.index_form_id AND f.active AND NOT f.deleted
 JOIN zoha.index_form_versions v ON v.index_form_id=f.id AND v.version=f.draft_version AND v.active AND NOT v.deleted
 LEFT JOIN zoha.index_form_fields ff ON ff.version_id=v.id AND ff.active AND NOT ff.deleted
 WHERE ct.code IN ('mold','full_sermon','supporting') GROUP BY ct.code
)
SELECT w.code,w.expected,COALESCE(a.n,0) FROM wanted w LEFT JOIN actual a USING(code) ORDER BY w.code;")"
echo "$DRAFT_COUNTS"
while IFS='|' read -r code expected actual; do [ "$expected" = "$actual" ] || { echo "ERROR: draft fields $code expected=$expected actual=$actual"; exit 13; }; done <<< "$DRAFT_COUNTS"

BOUND_COUNT="$(psql -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 5433 -U zoha_app -d zoha_core -Atc "
SELECT count(*) FROM zoha.content_types ct
JOIN zoha.content_type_index_forms m ON m.content_type_id=ct.id AND m.is_primary AND m.active AND NOT m.deleted
JOIN zoha.index_forms f ON f.id=m.index_form_id
JOIN zoha.index_form_versions v ON v.index_form_id=f.id AND v.version=f.active_version
JOIN zoha.index_form_fields ff ON ff.version_id=v.id AND ff.active AND NOT ff.deleted
WHERE ct.code IN ('mold','full_sermon','supporting') AND COALESCE(ff.config->'runtime'->>'taxonomyCode','')<>'';")"
[ "$BOUND_COUNT" = "98" ] || { echo "ERROR: runtime bindings expected=98 actual=$BOUND_COUNT"; exit 14; }
echo "RUNTIME_BINDINGS=PASS count=$BOUND_COUNT"

echo "========== RESTART =========="
systemctl restart zoha-api-v3 zoha-web
sleep 5
systemctl is-active --quiet zoha-api-v3
systemctl is-active --quiet zoha-web
echo "zoha-api-v3=active"
echo "zoha-web=active"

echo "========== WEB ASSET SMOKE =========="
LOGIN_HTML="$(mktemp /tmp/zoha-v044-login.XXXXXX.html)"
curl -ks 'https://185.73.114.144/auth?mode=login' -H 'Cache-Control: no-cache' -o "$LOGIN_HTML"
ASSET_FAIL=0
while read -r asset; do [ -n "$asset" ] || continue; code="$(curl -ks -o /dev/null -w '%{http_code}' "https://185.73.114.144$asset" -H 'Cache-Control: no-cache')"; echo "$code $asset"; [ "$code" = 200 ] || ASSET_FAIL=1; done < <(grep -oE '/_nuxt/[^" ]+\.(js|css)' "$LOGIN_HTML" | sort -u)
rm -f "$LOGIN_HTML"
[ "$ASSET_FAIL" -eq 0 ] || { echo "ERROR: Nuxt asset smoke failed"; exit 15; }
echo "NUXT_ASSETS=PASS"

echo "========== FINAL =========="
echo "BRANCH=$BRANCH"
echo "GITLAB_SHA=$REMOTE_SHA"
echo "SOURCE_BACKUP=$BACKUP"
echo "DB_BACKUP=$DB_BACKUP"
echo "ZOHAONLINE_HYBRID_INDEX_BUILDER_V044=PASS"