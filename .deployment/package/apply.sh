#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
ROOT="${1:-/var/www/zoha}"
PKG="$(cd "$(dirname "$0")" && pwd)"
BASE_SHA='a6188cd58bdbf68865f37dab78f6f5b1dc4efb27'
BRANCH_EXPECTED='feature/zoha-public-site-v1'
cd "$ROOT"
echo '========== ZOHAONLINE v0.6.0 / BUILDER AUTHORITY AND THREE SUBLEVELS =========='
[ "$(git branch --show-current)" = "$BRANCH_EXPECTED" ] || { echo 'ERROR: unexpected branch'; exit 2; }
[ "$(git rev-parse HEAD)" = "$BASE_SHA" ] || { echo 'ERROR: this release requires the verified v0.5.0/v0.5.1 source commit'; exit 3; }
case "$(git remote get-url origin)" in *git.mtacloud.ir/vendors/zoha/zoha.git*) ;; *) echo 'ERROR: unexpected origin'; exit 4;; esac
[ "$(git ls-remote origin "refs/heads/$BRANCH_EXPECTED" | awk '{print $1}')" = "$BASE_SHA" ] || { echo 'ERROR: GitLab head changed'; exit 5; }
git diff --cached --quiet || { echo 'ERROR: existing staged changes; stopping'; exit 6; }
source "$PKG/owned-paths.sh"
[ -z "$(git status --porcelain -- "${FILES[@]}")" ] || { echo 'ERROR: release-owned files have local changes; no files were overwritten'; exit 7; }
echo 'eaa9ed4427ddc6ea06fe7699e13bd64e8b51f867a64ab9517252ead4dc7ea85b  zohaonline-v0.6.0.patch' | (cd "$PKG" && sha256sum -c -)
git apply --check "$PKG/zohaonline-v0.6.0.patch"
for service in zoha-api-v3 zoha-web; do systemctl is-active --quiet "$service"; done
[ -s apps/api/dist/main.js ] && [ -s apps/web/.output/server/index.mjs ] || { echo 'ERROR: current production builds missing'; exit 8; }
export PGPASSWORD="$(cat "${ZOHA_POSTGRES_PASSWORD_FILE:-/etc/zoha-online/postgres-password}")"
export PGCONNECT_TIMEOUT=10
PSQL=(psql --no-password -X -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 5433 -U zoha_app -d zoha_core)
[ "$("${PSQL[@]}" -Atc "SELECT count(*) FROM zoha.schema_migrations WHERE version IN ('180_hybrid_runtime_index_builder','190_gravity_toolbox');")" = 2 ] || { echo 'ERROR: v0.5.1 database migrations are required'; exit 9; }
[ "$("${PSQL[@]}" -Atc "SELECT count(*) FROM zoha.schema_migrations WHERE version='200_index_builder_authority';")" = 0 ] || { echo 'ERROR: migration 200 already recorded; stopping without repeating it'; exit 10; }
BACKUP="$(mktemp -d "/root/zoha-v060-backup-$(date +%Y%m%d-%H%M%S).XXXXXX")"
: > "$BACKUP/absent-files"
for p in "${FILES[@]}"; do
 if [ -e "$p" ]; then mkdir -p "$BACKUP/source/$(dirname "$p")"; cp -a "$p" "$BACKUP/source/$p"; else printf '%s\n' "$p" >> "$BACKUP/absent-files"; fi
done
cp -a apps/api/dist "$BACKUP/api-dist"
cp -a apps/web/.output "$BACKUP/web-output"
MIGRATED=0
STOPPED=0
COMMITTED=0
rollback(){
 rc=$?
 trap - EXIT
 if [ "$rc" -ne 0 ] && [ "$COMMITTED" = 0 ]; then
  set +e
  echo '========== RESTORE RELEASE-OWNED SOURCE / BUILDS =========='
  if [ "$MIGRATED" = 1 ]; then
   systemctl stop zoha-api-v3 zoha-web
   if ! "${PSQL[@]}" -f "$BACKUP/rollback.sql"; then
    echo "ERROR: database rollback needs inspection; services left stopped; backup=$BACKUP"
    exit "$rc"
   fi
   echo 'DB_POINTERS_AND_PROJECTION_ROLLBACK=PASS'
  fi
  for p in "${FILES[@]}"; do if [ -e "$BACKUP/source/$p" ]; then cp -a "$BACKUP/source/$p" "$p"; fi; done
  while IFS= read -r p; do [ -n "$p" ] && rm -f -- "$p"; done < "$BACKUP/absent-files"
  git reset -q -- "${FILES[@]}"
  rm -rf apps/api/dist apps/web/.output
  cp -a "$BACKUP/api-dist" apps/api/dist
  cp -a "$BACKUP/web-output" apps/web/.output
  if [ "$STOPPED" = 1 ] || [ "$MIGRATED" = 1 ]; then systemctl restart zoha-api-v3 zoha-web; fi
  echo "RELEASE_ROLLBACK=PASS backup=$BACKUP"
 fi
 exit "$rc"
}
trap rollback EXIT
echo "SOURCE_AND_BUILD_BACKUP=$BACKUP"
git apply "$PKG/zohaonline-v0.6.0.patch"
node --test tests/index-hierarchy.test.cjs tests/gravity-toolbox.test.cjs tests/admin-content-studio.test.cjs tests/real-index-builder.test.cjs tests/index-authoring-integration.test.cjs tests/admin-preview-auth.test.cjs tests/runtime-overview-sql.test.cjs
npm run test:contracts
npm run build
rm -rf apps/web/.nuxt
npm run build:web
git diff --check -- "${FILES[@]}"
echo 'TESTS_AND_BUILDS=PASS'

# Freeze application writes only for the consistent backup, migration and activation.
STOPPED=1
systemctl stop zoha-api-v3 zoha-web
SERVER_VERSION="$("${PSQL[@]}" -Atc 'SHOW server_version_num;')"
[[ "$SERVER_VERSION" =~ ^[0-9]+$ ]] || exit 11
python3 "$PKG/backup_index_forms.py" --server-major "$((SERVER_VERSION / 10000))" --output "$BACKUP/index-data.sql"
"${PSQL[@]}" -At > "$BACKUP/rollback.sql" <<'SQL'
SELECT 'BEGIN;';
SELECT format('UPDATE zoha.index_forms SET active_version=%s,draft_version=%s,settings=%L::jsonb WHERE id=%L::uuid;',active_version,draft_version,settings::text,id::text) FROM zoha.index_forms;
SELECT 'DELETE FROM zoha.index_runtime_post_type_fields;';
SELECT format('INSERT INTO zoha.index_runtime_post_type_fields(post_type_code,taxonomy_code,sort_order,is_required,settings) VALUES(%L,%L,%s,%L,%L::jsonb);',post_type_code,taxonomy_code,sort_order,is_required,settings::text) FROM zoha.index_runtime_post_type_fields;
SELECT format('UPDATE zoha.index_runtime_taxonomies SET title=%L,field_type=%L,is_multi=%L,allows_personal=%L,metadata=%L::jsonb,is_active=%L WHERE code=%L;',title,field_type,is_multi,allows_personal,metadata::text,is_active,code) FROM zoha.index_runtime_taxonomies;
SELECT format('UPDATE zoha.index_runtime_terms SET parent_id=%s WHERE id=%s;',COALESCE(parent_id::text,'NULL'),id) FROM zoha.index_runtime_terms;
SELECT 'DROP INDEX IF EXISTS zoha.index_builder_term_parent_unique;';
SELECT 'ALTER TABLE zoha.index_runtime_terms ADD CONSTRAINT index_runtime_terms_taxonomy_code_normalized_title_parent_h_key UNIQUE(taxonomy_code,normalized_title,parent_hint);';
SELECT 'DELETE FROM zoha.schema_migrations WHERE version=''200_index_builder_authority'';';
SELECT 'COMMIT;';
SQL
COUNTS_SQL="SELECT ct.code,fld.which,count(ff.id) FROM zoha.content_types ct JOIN zoha.content_type_index_forms m ON m.content_type_id=ct.id AND m.is_primary AND m.active AND NOT m.deleted JOIN zoha.index_forms f ON f.id=m.index_form_id CROSS JOIN LATERAL (VALUES('active',f.active_version),('draft',f.draft_version)) fld(which,version) JOIN zoha.index_form_versions v ON v.index_form_id=f.id AND v.version=fld.version LEFT JOIN zoha.index_form_fields ff ON ff.version_id=v.id AND ff.active AND NOT ff.deleted WHERE ct.code IN ('mold','full_sermon','supporting') GROUP BY ct.code,fld.which ORDER BY ct.code,fld.which;"
"${PSQL[@]}" -AtF '|' -c "$COUNTS_SQL" > "$BACKUP/form-counts-before.txt"
"${PSQL[@]}" -f database-v2/migrations/postgres/200_index_builder_authority.sql
MIGRATED=1
"${PSQL[@]}" -AtF '|' -c "$COUNTS_SQL" > "$BACKUP/form-counts-after.txt"
cmp "$BACKUP/form-counts-before.txt" "$BACKUP/form-counts-after.txt"
PARENTS="$("${PSQL[@]}" -Atc "SELECT count(*) FROM zoha.index_builder_published_fields WHERE taxonomy_code IN ('IDX-002','IDX-003') AND parent_taxonomy_code='IDX-001';")"
[ "$PARENTS" = 6 ] || { echo "ERROR: expected subject parent on both fields in all three forms; found=$PARENTS"; exit 12; }
echo 'FORM_COUNTS_PRESERVED=PASS'
echo 'SUBTOPIC_AND_PROCESSING_UNDER_TOPIC=PASS'
echo 'BUILDER_AUTHORITY_MIGRATION=PASS'
systemctl start zoha-api-v3 zoha-web
for service in zoha-api-v3 zoha-web; do
 for try in {1..15}; do if systemctl is-active --quiet "$service"; then break; fi; sleep 1; done
 systemctl is-active --quiet "$service"
 echo "$service=active"
done
CHECK_DIR="$(mktemp -d /tmp/zoha-v060-smoke.XXXXXX)"
curl -fkLsS --retry 6 --retry-all-errors --retry-delay 2 --max-time 20 'https://185.73.114.144/auth?mode=login' -o "$CHECK_DIR/login.html"
mapfile -t ASSETS < <(grep -oE '/_nuxt/[^" ]+\.(js|css)' "$CHECK_DIR/login.html" | sort -u)
[ "${#ASSETS[@]}" -gt 0 ] || { echo 'ERROR: Nuxt assets missing'; exit 13; }
for asset in "${ASSETS[@]}"; do curl -fkLsS --retry 3 --max-time 20 "https://185.73.114.144$asset" -o /dev/null; done
rm -rf "$CHECK_DIR"
echo 'WEB_AND_ASSETS=PASS'
git add -- "${FILES[@]}"
git -c user.name='ostaddehdari' -c user.email='ostaddehdari@users.noreply.git.mtacloud.ir' commit -m 'مرجعیت نمایه‌ساز و ساختار درختی نمایه‌ها با سه سطح زیرشاخه'
COMMITTED=1
LOCAL_SHA="$(git rev-parse HEAD)"
if ! git push origin "HEAD:$BRANCH_EXPECTED"; then
 echo "DEPLOYED_GITLAB_PUSH_PENDING=$LOCAL_SHA"
 echo "Retry: cd $ROOT && git push origin HEAD:$BRANCH_EXPECTED"
 exit 14
fi
REMOTE_SHA="$(git ls-remote origin "refs/heads/$BRANCH_EXPECTED" | awk '{print $1}')"
[ "$LOCAL_SHA" = "$REMOTE_SHA" ] || { echo 'ERROR: GitLab SHA verification failed'; exit 15; }
echo "GITLAB_PUSH_VERIFIED=$LOCAL_SHA"
echo "BACKUP=$BACKUP"
echo 'ZOHAONLINE_BUILDER_V060=PASS'
