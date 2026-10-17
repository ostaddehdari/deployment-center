#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${1:-/var/www/zoha}"
PKG="$(cd "$(dirname "$0")" && pwd)"
BASE_SHA="eb140a90aa78b4b92f4443a94591af415fd36392"
PAYLOAD_SHA="5f2c485c7d04fe8dac4c1f6c956e0ecdd1eadda80887bc21a22217769cb44bf4"

cd "$ROOT"

echo "========== ZOHAONLINE v0.4.0 / HYBRID GRAVITY RUNTIME INDEX BUILDER =========="

[ -d .git ] || { echo "ERROR: $ROOT is not a git repository"; exit 2; }
BRANCH="$(git branch --show-current)"
[ "$BRANCH" = "feature/zoha-public-site-v1" ] || { echo "ERROR: unexpected branch=$BRANCH"; exit 3; }

ORIGIN_URL="$(git remote get-url origin 2>/dev/null || true)"
case "$ORIGIN_URL" in
  *git.mtacloud.ir/vendors/zoha/zoha.git*) ;;
  *) echo "ERROR: unexpected origin=$ORIGIN_URL"; exit 4 ;;
esac

HEAD_SHA="$(git rev-parse HEAD)"
[ "$HEAD_SHA" = "$BASE_SHA" ] || {
  echo "ERROR: expected v0.3.7 base HEAD=$BASE_SHA but found $HEAD_SHA"
  exit 5
}

if ! git diff --cached --quiet; then
  echo "ERROR: pre-existing staged changes detected; refusing to mix release files."
  git status --short
  exit 6
fi

echo "========== RECONSTRUCT / VERIFY RELEASE PAYLOAD =========="
PAYLOAD_TGZ="$(mktemp /tmp/zoha-v040-payload.XXXXXX.tgz)"
PAYLOAD_DIR="$(mktemp -d /tmp/zoha-v040-payload.XXXXXX)"
trap 'rm -f "$PAYLOAD_TGZ"; rm -rf "$PAYLOAD_DIR"' EXIT

cat "$PKG"/payload-v040.part-* | base64 -d > "$PAYLOAD_TGZ"
echo "$PAYLOAD_SHA  $PAYLOAD_TGZ" | sha256sum -c -
echo "========== RECOVER / VERIFY TAR PAYLOAD =========="
PAYLOAD_TAR="$PAYLOAD_DIR/payload.tar"
set +e
gzip -dc "$PAYLOAD_TGZ" > "$PAYLOAD_TAR"
GZIP_RC=$?
set -e
if [ "$GZIP_RC" -eq 0 ]; then
  echo "GZIP_STREAM=PASS"
else
  echo "GZIP_TRAILER_WARNING=YES rc=$GZIP_RC"
  echo "INFO: continuing only if the decompressed tar is structurally valid and all source contracts pass."
fi

[ -s "$PAYLOAD_TAR" ] || { echo "ERROR: recovered tar is empty"; exit 7; }
tar -tf "$PAYLOAD_TAR" > "$PAYLOAD_DIR/list.txt"
echo "TAR_LISTING=PASS entries=$(wc -l < "$PAYLOAD_DIR/list.txt")"

if grep -Eq '^/|(^|/)\.\.(/|$)' "$PAYLOAD_DIR/list.txt"; then
  echo "ERROR: unsafe path in payload"
  exit 7
fi

for expected in   patch-hybrid-support.py   replacements/apps/web/pages/admin/index-builder.vue   replacements/apps/web/components/indexing/IndexDynamicField.vue   replacements/apps/web/components/indexing/IndexRuntimePanel.vue   replacements/apps/api/src/index-runtime/index-runtime.service.ts   replacements/database-v2/migrations/postgres/180_hybrid_runtime_index_builder.sql   tests/real-index-builder.test.cjs
do
  grep -Fxq "$expected" "$PAYLOAD_DIR/list.txt" || {
    echo "ERROR: recovered tar missing $expected"
    exit 7
  }
done

tar -xf "$PAYLOAD_TAR" -C "$PAYLOAD_DIR"
echo "RECOVERED_PAYLOAD=PASS"

FILES=(
  'apps/api/src/admin-content-studio/admin-content-studio.service.ts'
  'apps/api/src/admin-content-studio/admin-content-studio.dto.ts'
  'apps/api/src/index-runtime/index-runtime.service.ts'
  'apps/web/composables/useIndexRuntime.ts'
  'apps/web/components/indexing/IndexPersonalSelect.vue'
  'apps/web/components/indexing/IndexRuntimePanel.vue'
  'apps/web/components/indexing/IndexDynamicField.vue'
  'apps/web/pages/admin/index-builder.vue'
  'database-v2/migrations/postgres/180_hybrid_runtime_index_builder.sql'
  'tests/admin-content-studio.test.cjs'
  'tests/real-index-builder.test.cjs'
)

BACKUP="/root/zoha-v040-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP"
for p in "${FILES[@]}"; do
  if [ -e "$p" ]; then
    mkdir -p "$BACKUP/$(dirname "$p")"
    cp -a "$p" "$BACKUP/$p"
  fi
done
echo "SOURCE_BACKUP=$BACKUP"

echo "========== PATCH EXISTING CONTENT STUDIO SUPPORT =========="
python3 "$PAYLOAD_DIR/patch-hybrid-support.py" "$ROOT"

echo "========== INSTALL v0.4.0 SOURCE OVERLAY =========="
while IFS= read -r src; do
  rel="${src#"$PAYLOAD_DIR/replacements/"}"
  mkdir -p "$ROOT/$(dirname "$rel")"
  cp -a "$src" "$ROOT/$rel"
done < <(find "$PAYLOAD_DIR/replacements" -type f | sort)
cp -a "$PAYLOAD_DIR/tests/real-index-builder.test.cjs" "$ROOT/tests/real-index-builder.test.cjs"

echo "========== DEDICATED HYBRID BUILDER CONTRACT =========="
node --test tests/real-index-builder.test.cjs

echo "========== CONTENT STUDIO CONTRACT =========="
node --test tests/admin-content-studio.test.cjs

echo "========== INDEX AUTHORING REGRESSION =========="
node --test tests/index-authoring-integration.test.cjs

echo "========== RUNTIME SQL REGRESSION =========="
node --test tests/runtime-overview-sql.test.cjs

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
check_fixed(){
  local label="$1" needle="$2" file="$3"
  if grep -Fq -- "$needle" "$file"; then
    echo "PASS: $label"
  else
    echo "FAIL: $label"
    echo "  file=$file"
    echo "  expected=$needle"
    exit 8
  fi
}

check_fixed 'Gravity toolbox palette restored' 'field-palette' apps/web/pages/admin/index-builder.vue
check_fixed 'Versioned form studio connected' 'useAdminContentStudio' apps/web/pages/admin/index-builder.vue
check_fixed 'Runtime vocabulary connected' 'useAdminRuntimeIndex' apps/web/pages/admin/index-builder.vue
check_fixed 'Runtime source mode exposed' 'SourceMode' apps/web/pages/admin/index-builder.vue
check_fixed 'Runtime taxonomy binding exposed' 'TaxonomyCode' apps/web/pages/admin/index-builder.vue
check_fixed 'Real term manager preserved' 'مدیریت آیتم‌های فهرست' apps/web/pages/admin/index-builder.vue
check_fixed 'Draft preview schema override enabled' ':schema-override="previewSchema"' apps/web/pages/admin/index-builder.vue
check_fixed 'Generic dynamic renderer installed' 'IndexDynamicField' apps/web/components/indexing/IndexRuntimePanel.vue
check_fixed 'Published runtime reads versioned form fields' 'index_form_fields' apps/api/src/index-runtime/index-runtime.service.ts
check_fixed 'Published runtime resolves content form mapping' 'content_type_index_forms' apps/api/src/index-runtime/index-runtime.service.ts
check_fixed 'Migration bridge marker exists' 'runtime-hybrid-v4' database-v2/migrations/postgres/180_hybrid_runtime_index_builder.sql
check_fixed 'Searchable select catalog exists' "Kind:'searchable_select'" apps/api/src/admin-content-studio/admin-content-studio.service.ts
echo "SOURCE_VERIFY=PASS"

echo "========== COMMIT RELEASE FILES ONLY =========="
git add -- "${FILES[@]}"
if git diff --cached --quiet; then
  echo "ERROR: no v0.4.0 source changes staged"
  exit 9
fi

git -c user.name='ostaddehdari' \
    -c user.email='ostaddehdari@users.noreply.git.mtacloud.ir' \
    commit -m 'نمایه‌ساز حرفه‌ای: ترکیب Toolbox فرم با Runtime واقعی'

LOCAL_SHA="$(git rev-parse HEAD)"

echo "========== PUSH TO GITLAB SOURCE OF TRUTH =========="
git push origin "HEAD:$BRANCH"
REMOTE_SHA="$(git ls-remote origin "refs/heads/$BRANCH" | awk '{print $1}')"
[ "$REMOTE_SHA" = "$LOCAL_SHA" ] || {
  echo "ERROR: GitLab SHA mismatch local=$LOCAL_SHA remote=$REMOTE_SHA"
  exit 10
}
echo "GITLAB_PUSH_VERIFIED=$REMOTE_SHA"

echo "========== BACKUP VERSIONED INDEX-FORM DATABASE ROWS =========="
export PGPASSWORD="$(cat /etc/zoha-online/postgres-password)"
DB_BACKUP="/root/zoha-v040-index-form-data-$(date +%Y%m%d-%H%M%S).sql"
pg_dump -h 127.0.0.1 -p 5433 -U zoha_app -d zoha_core \
  --data-only --inserts \
  --table=zoha.index_forms \
  --table=zoha.index_form_versions \
  --table=zoha.index_form_fields \
  --table=zoha.index_form_options \
  --table=zoha.index_form_rules \
  --table=zoha.content_type_index_forms \
  > "$DB_BACKUP"
echo "DB_BACKUP=$DB_BACKUP"

echo "========== APPLY DATABASE SCHEMA / MIGRATION 180 =========="
bash database-v2/deploy/apply-schema.sh --apply

echo "========== VERIFY HYBRID BUILDER DATABASE =========="
psql -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 5433 -U zoha_app -d zoha_core -Atc "
SELECT CASE WHEN EXISTS(
  SELECT 1 FROM zoha.schema_migrations WHERE version='180_hybrid_runtime_index_builder'
) THEN 'MIGRATION_180=PASS' ELSE 'MIGRATION_180=FAIL' END;
"

COUNTS="$(psql -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 5433 -U zoha_app -d zoha_core -AtF '|' -c "
WITH wanted(code,expected) AS (
  VALUES ('mold',33),('full_sermon',34),('supporting',31)
), actual AS (
  SELECT ct.code,count(ff.id)::int AS n
  FROM zoha.content_types ct
  JOIN zoha.content_type_index_forms m
    ON m.content_type_id=ct.id AND m.is_primary AND m.active AND NOT m.deleted
  JOIN zoha.index_forms f
    ON f.id=m.index_form_id AND f.active AND NOT f.deleted
  JOIN zoha.index_form_versions v
    ON v.index_form_id=f.id AND v.version=f.active_version AND v.active AND NOT v.deleted
  LEFT JOIN zoha.index_form_fields ff
    ON ff.version_id=v.id AND ff.active AND NOT ff.deleted
  WHERE ct.code IN ('mold','full_sermon','supporting')
  GROUP BY ct.code
)
SELECT w.code,w.expected,COALESCE(a.n,0)
FROM wanted w LEFT JOIN actual a USING(code)
ORDER BY w.code;
")"
echo "$COUNTS"
while IFS='|' read -r code expected actual; do
  [ "$expected" = "$actual" ] || {
    echo "ERROR: active hybrid field count $code expected=$expected actual=$actual"
    exit 11
  }
done <<< "$COUNTS"

DRAFT_COUNTS="$(psql -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 5433 -U zoha_app -d zoha_core -AtF '|' -c "
WITH wanted(form_code,expected) AS (
 VALUES ('mold_default_index',33),('full_sermon_default_index',34),('supporting_default_index',31)
)
SELECT w.form_code,w.expected,count(ff.id)::int
FROM wanted w
JOIN zoha.index_forms f ON f.code=w.form_code
JOIN zoha.index_form_versions v ON v.index_form_id=f.id AND v.version=f.draft_version
LEFT JOIN zoha.index_form_fields ff ON ff.version_id=v.id AND ff.active AND NOT ff.deleted
GROUP BY w.form_code,w.expected
ORDER BY w.form_code;
")"
echo "$DRAFT_COUNTS"
while IFS='|' read -r code expected actual; do
  [ "$expected" = "$actual" ] || {
    echo "ERROR: draft hybrid field count $code expected=$expected actual=$actual"
    exit 12
  }
done <<< "$DRAFT_COUNTS"

BOUND_COUNT="$(psql -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 5433 -U zoha_app -d zoha_core -Atc "
SELECT count(*)
FROM zoha.index_form_fields ff
JOIN zoha.index_form_versions v ON v.id=ff.version_id
JOIN zoha.index_forms f ON f.id=v.index_form_id
WHERE f.code IN ('mold_default_index','full_sermon_default_index','supporting_default_index')
  AND v.version=f.active_version
  AND ff.active AND NOT ff.deleted
  AND COALESCE(ff.config->'runtime'->>'taxonomyCode','')<>'';
")"
[ "$BOUND_COUNT" -eq 98 ] || {
  echo "ERROR: active runtime taxonomy bindings expected=98 actual=$BOUND_COUNT"
  exit 13
}
echo "RUNTIME_BINDINGS=PASS count=$BOUND_COUNT"

echo "========== RESTART =========="
systemctl restart zoha-api-v3 zoha-web
sleep 5
systemctl is-active --quiet zoha-api-v3
systemctl is-active --quiet zoha-web
echo "zoha-api-v3=active"
echo "zoha-web=active"

echo "========== WEB ASSET SMOKE =========="
LOGIN_HTML="$(mktemp /tmp/zoha-v040-login.XXXXXX.html)"
curl -ks 'https://185.73.114.144/auth?mode=login' -H 'Cache-Control: no-cache' -o "$LOGIN_HTML"
ASSET_FAIL=0
while read -r asset; do
  [ -n "$asset" ] || continue
  code="$(curl -ks -o /dev/null -w '%{http_code}' "https://185.73.114.144$asset" -H 'Cache-Control: no-cache')"
  echo "$code $asset"
  [ "$code" = 200 ] || ASSET_FAIL=1
done < <(grep -oE '/_nuxt/[^" ]+\.(js|css)' "$LOGIN_HTML" | sort -u)
rm -f "$LOGIN_HTML"
[ "$ASSET_FAIL" -eq 0 ] || { echo "ERROR: Nuxt asset smoke failed"; exit 14; }
echo "NUXT_ASSETS=PASS"

echo "========== FINAL =========="
echo "BRANCH=$BRANCH"
echo "GITLAB_SHA=$REMOTE_SHA"
echo "SOURCE_BACKUP=$BACKUP"
echo "DB_BACKUP=$DB_BACKUP"
echo "ZOHAONLINE_HYBRID_INDEX_BUILDER_V040=PASS"
