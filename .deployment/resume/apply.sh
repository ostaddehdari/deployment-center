#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
ROOT="${1:-/var/www/zoha}"
PKG="$(cd "$(dirname "$0")" && pwd)"
EXPECTED_SHA='a6188cd58bdbf68865f37dab78f6f5b1dc4efb27'
cd "$ROOT"
echo '========== ZOHAONLINE v0.5.1 / RESUME VERIFIED TOOLBOX INSTALL =========='
[ "$(git branch --show-current)" = 'feature/zoha-public-site-v1' ] || { echo 'ERROR: unexpected branch'; exit 2; }
[ "$(git rev-parse HEAD)" = "$EXPECTED_SHA" ] || { echo 'ERROR: this resume requires the verified v0.5.0 source commit'; exit 3; }
case "$(git remote get-url origin)" in *git.mtacloud.ir/vendors/zoha/zoha.git*) ;; *) echo 'ERROR: unexpected GitLab origin'; exit 4;; esac
source "$PKG/owned-paths.sh"
[ -z "$(git status --porcelain -- "${FILES[@]}")" ] || { echo 'ERROR: toolbox source has uncommitted changes; stopping without overwriting'; exit 5; }
REMOTE_SHA="$(git ls-remote origin refs/heads/feature/zoha-public-site-v1 | awk '{print $1}')"
[ "$REMOTE_SHA" = "$EXPECTED_SHA" ] || { echo 'ERROR: GitLab head changed; stopping'; exit 6; }
[ -s apps/api/dist/main.js ] && [ -s apps/web/.output/server/index.mjs ] || { echo 'ERROR: verified build outputs are missing'; exit 7; }
echo "GITLAB_PUSH_VERIFIED=$REMOTE_SHA"
echo 'VERIFIED_V050_SOURCE=PASS'
echo 'BUILDS_REUSED=PASS'

PGPASSWORD="$(cat "${ZOHA_POSTGRES_PASSWORD_FILE:-/etc/zoha-online/postgres-password}")"
export PGPASSWORD
export PGCONNECT_TIMEOUT=10
PSQL=(psql --no-password -X -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 5433 -U zoha_app -d zoha_core)
SERVER_VERSION_NUM="$("${PSQL[@]}" -Atc 'SHOW server_version_num;')"
[[ "$SERVER_VERSION_NUM" =~ ^[0-9]+$ ]] || { echo 'ERROR: invalid PostgreSQL server version'; exit 8; }
SERVER_MAJOR="$((SERVER_VERSION_NUM / 10000))"
echo "POSTGRES_SERVER_MAJOR=$SERVER_MAJOR"

BACKUP_DIR="$(mktemp -d "${ZOHA_RESUME_STATE_DIR:-/root}/zoha-v051-db-backup-$(date +%Y%m%d-%H%M%S).XXXXXX")"
DB_BACKUP="$BACKUP_DIR/index-form-data.sql"
echo '========== COMPATIBLE DATABASE BACKUP =========='
python3 "$PKG/backup_index_forms.py" --server-major "$SERVER_MAJOR" --output "$DB_BACKUP"

echo '========== APPLY ONLY TOOLBOX MIGRATIONS =========='
for version in 180_hybrid_runtime_index_builder 190_gravity_toolbox; do
  count="$("${PSQL[@]}" -Atc "SELECT count(*) FROM zoha.schema_migrations WHERE version='$version';")"
  if [ "$count" = 0 ]; then
    "${PSQL[@]}" -f "database-v2/migrations/postgres/$version.sql"
  elif [ "$count" != 1 ]; then
    echo "ERROR: invalid migration state for $version"; exit 9
  fi
  count="$("${PSQL[@]}" -Atc "SELECT count(*) FROM zoha.schema_migrations WHERE version='$version';")"
  [ "$count" = 1 ] || { echo "ERROR: migration not recorded: $version"; exit 10; }
  echo "MIGRATION_$version=PASS"
done

echo '========== VERIFY FORM COUNTS =========='
for which in active_version draft_version; do
  COUNTS="$("${PSQL[@]}" -AtF '|' -c "
WITH wanted(code,expected) AS (VALUES ('mold',33),('full_sermon',34),('supporting',31)), actual AS (
 SELECT ct.code,count(ff.id)::int AS n
 FROM zoha.content_types ct
 JOIN zoha.content_type_index_forms m ON m.content_type_id=ct.id AND m.is_primary AND m.active AND NOT m.deleted
 JOIN zoha.index_forms f ON f.id=m.index_form_id AND f.active AND NOT f.deleted
 JOIN zoha.index_form_versions v ON v.index_form_id=f.id AND v.version=f.$which AND v.active AND NOT v.deleted
 LEFT JOIN zoha.index_form_fields ff ON ff.version_id=v.id AND ff.active AND NOT ff.deleted
 WHERE ct.code IN ('mold','full_sermon','supporting') GROUP BY ct.code
)
SELECT w.code,w.expected,COALESCE(a.n,0) FROM wanted w LEFT JOIN actual a USING(code) ORDER BY w.code;")"
  [ "$(printf '%s\n' "$COUNTS" | wc -l)" -eq 3 ] || { echo 'ERROR: missing form count rows'; exit 11; }
  while IFS='|' read -r code expected actual; do
    [ "$expected" = "$actual" ] || { echo "ERROR: $which $code expected=$expected actual=$actual"; exit 12; }
  done <<< "$COUNTS"
  echo "$which=$COUNTS"
done
BOUND_COUNT="$("${PSQL[@]}" -Atc "
SELECT count(*) FROM zoha.content_types ct
JOIN zoha.content_type_index_forms m ON m.content_type_id=ct.id AND m.is_primary AND m.active AND NOT m.deleted
JOIN zoha.index_forms f ON f.id=m.index_form_id
JOIN zoha.index_form_versions v ON v.index_form_id=f.id AND v.version=f.active_version
JOIN zoha.index_form_fields ff ON ff.version_id=v.id AND ff.active AND NOT ff.deleted
WHERE ct.code IN ('mold','full_sermon','supporting') AND COALESCE(ff.config->'runtime'->>'taxonomyCode','')<>'';")"
[ "$BOUND_COUNT" = 98 ] || { echo "ERROR: runtime bindings expected=98 actual=$BOUND_COUNT"; exit 13; }
echo 'RUNTIME_BINDINGS=PASS count=98'
API_USER="$(systemctl show zoha-api-v3 -p User --value)"
install -d -m 0700 -o "${API_USER:-root}" /var/lib/zoha/index-files

echo '========== RESTART SERVICES =========='
systemctl restart zoha-api-v3 zoha-web
for service in zoha-api-v3 zoha-web; do
  for try in {1..15}; do
    if systemctl is-active --quiet "$service"; then break; fi
    sleep 1
  done
  systemctl is-active --quiet "$service"
  echo "$service=active"
done

echo '========== VERIFY WEB AND ASSETS =========='
CHECK_DIR="$(mktemp -d /tmp/zoha-v051-smoke.XXXXXX)"
trap 'rm -rf "$CHECK_DIR"' EXIT
curl -fkLsS --retry 3 --max-time 20 'https://185.73.114.144/auth?mode=login' -H 'Cache-Control: no-cache' -o "$CHECK_DIR/login.html"
mapfile -t ASSETS < <(grep -oE '/_nuxt/[^" ]+\.(js|css)' "$CHECK_DIR/login.html" | sort -u)
[ "${#ASSETS[@]}" -gt 0 ] || { echo 'ERROR: login HTML contained no Nuxt assets'; exit 14; }
for asset in "${ASSETS[@]}"; do
  curl -fkLsS --retry 2 --max-time 20 "https://185.73.114.144$asset" -H 'Cache-Control: no-cache' -o /dev/null
done
echo 'NUXT_ASSETS=PASS'
echo "DB_BACKUP=$DB_BACKUP"
echo "GITLAB_SHA=$REMOTE_SHA"
echo 'ZOHAONLINE_TOOLBOX_V051=PASS'
