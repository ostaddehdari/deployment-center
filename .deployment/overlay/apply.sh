#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${1:-/var/www/zoha}"
PKG="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "========== ZOHAONLINE v0.1.3 / SEED RUNTIME DEFAULTS =========="

[ -f apps/api/src/app.module.ts ] || { echo 'ERROR: پروژه ضحی در مسیر مورد انتظار نیست'; exit 2; }
[ -f database-v2/migrations/postgres/160_admin_content_type_index_builder.sql ] || { echo 'ERROR: migration 160 موجود نیست'; exit 3; }
[ -f database-v2/migrations/postgres/170_index_defaults_personal_items.sql ] || { echo 'ERROR: migration 170 موجود نیست؛ ابتدا v0.1.2 را اجرا کنید'; exit 4; }

BRANCH="$(git branch --show-current)"
[ -n "$BRANCH" ] || { echo 'ERROR: detached HEAD مجاز نیست'; exit 5; }

ORIGIN_URL="$(git remote get-url origin 2>/dev/null || true)"
case "$ORIGIN_URL" in
  *git.mtacloud.ir/vendors/zoha/zoha.git*) ;;
  *) echo "ERROR: origin مورد انتظار GitLab ضحی نیست: $ORIGIN_URL"; exit 6;;
esac

echo "========== MATERIALIZE DEFAULT DATA =========="
python3 "$PKG/scripts/materialize-index-defaults.py" "$PKG"
[ -s "$PKG/data/index-defaults.json" ] || { echo 'ERROR: index-defaults.json آماده نشد'; exit 7; }
[ -f "$PKG/scripts/seed-index-runtime.py" ] || { echo 'ERROR: seed-index-runtime.py در بسته نیست'; exit 8; }

BACKUP="/root/zoha-index-v013-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP"

for p in   scripts/seed-index-runtime.py   data/index-defaults.json
do
  if [ -e "$p" ]; then
    mkdir -p "$BACKUP/$(dirname "$p")"
    cp -a "$p" "$BACKUP/$p"
  fi
done

mkdir -p scripts data
cp -a "$PKG/scripts/seed-index-runtime.py" scripts/
cp -a "$PKG/data/index-defaults.json" data/
chmod +x scripts/seed-index-runtime.py

echo "========== VALIDATE SEED GENERATOR =========="
SEED_SQL="/tmp/zoha-index-seed-v013.sql"
python3 scripts/seed-index-runtime.py data/index-defaults.json > "$SEED_SQL"
grep -q '^BEGIN;' "$SEED_SQL"
grep -q '^COMMIT;' "$SEED_SQL"
TAX_INS="$(grep -c '^INSERT INTO zoha.index_runtime_taxonomies' "$SEED_SQL")"
PT_INS="$(grep -c '^INSERT INTO zoha.index_runtime_post_type_fields' "$SEED_SQL")"
TERM_INS="$(grep -c '^INSERT INTO zoha.index_runtime_terms' "$SEED_SQL")"
echo "SEED_STATEMENTS taxonomies=$TAX_INS post_type_fields=$PT_INS terms=$TERM_INS"
[ "$TAX_INS" -eq 40 ] || { echo "ERROR: expected 40 taxonomy seed statements"; exit 9; }
[ "$PT_INS" -eq 98 ] || { echo "ERROR: expected 98 post-type field seed statements"; exit 10; }
[ "$TERM_INS" -ge 755 ] || { echo "ERROR: expected at least 755 term seed statements"; exit 11; }

echo "========== TESTS / BUILDS BEFORE DATABASE CHANGE =========="
node --test tests/index-runtime-defaults.test.cjs
npm run test:contracts
npm run build
npm run build:web

echo "========== COMMIT SEED GENERATOR TO GITLAB SOURCE =========="
git add scripts/seed-index-runtime.py data/index-defaults.json
if ! git diff --cached --quiet; then
  git -c user.name='ostaddehdari'       -c user.email='ostaddehdari@users.noreply.git.mtacloud.ir'       commit -m 'نمایه‌گذاری عملیاتی: افزودن seed پیش‌فرض‌های runtime'
else
  echo 'No new seed-source changes to commit.'
fi

LOCAL_SHA="$(git rev-parse HEAD)"
git push origin "HEAD:$BRANCH"
REMOTE_SHA="$(git ls-remote origin "refs/heads/$BRANCH" | awk '{print $1}')"
[ "$REMOTE_SHA" = "$LOCAL_SHA" ] || {
  echo "ERROR: GitLab SHA mismatch local=$LOCAL_SHA remote=$REMOTE_SHA"
  exit 12
}
echo "GITLAB_PUSH_VERIFIED=$REMOTE_SHA"

echo "========== APPLY SCHEMA MIGRATION =========="
PGPASSWORD="$(cat /etc/zoha-online/postgres-password)" psql -v ON_ERROR_STOP=1   -h 127.0.0.1 -p 5433   -U zoha_app -d zoha_core   -f database-v2/migrations/postgres/170_index_defaults_personal_items.sql

echo "========== APPLY VERSIONED DEFAULT SEED =========="
PGPASSWORD="$(cat /etc/zoha-online/postgres-password)" psql -v ON_ERROR_STOP=1   -h 127.0.0.1 -p 5433   -U zoha_app -d zoha_core   -f "$SEED_SQL"

DB() {
  PGPASSWORD="$(cat /etc/zoha-online/postgres-password)"   psql -At -h 127.0.0.1 -p 5433 -U zoha_app -d zoha_core -c "$1"
}

echo "========== STRICT DATABASE VERIFY =========="
TAX_COUNT="$(DB "SELECT count(*) FROM zoha.index_runtime_taxonomies WHERE is_active=true;")"
MOLD_COUNT="$(DB "SELECT count(*) FROM zoha.index_runtime_post_type_fields WHERE post_type_code='mold';")"
SERMON_COUNT="$(DB "SELECT count(*) FROM zoha.index_runtime_post_type_fields WHERE post_type_code='full_sermon';")"
SUPPORT_COUNT="$(DB "SELECT count(*) FROM zoha.index_runtime_post_type_fields WHERE post_type_code='supporting';")"
PROCESSING_COUNT="$(DB "SELECT count(*) FROM zoha.index_runtime_terms WHERE taxonomy_code='IDX-003' AND is_active=true;")"
TERM_COUNT="$(DB "SELECT count(*) FROM zoha.index_runtime_terms WHERE is_active=true;")"

echo "taxonomies=$TAX_COUNT"
echo "mold_fields=$MOLD_COUNT"
echo "full_sermon_fields=$SERMON_COUNT"
echo "supporting_fields=$SUPPORT_COUNT"
echo "processing_keys=$PROCESSING_COUNT"
echo "active_terms=$TERM_COUNT"

[ "$TAX_COUNT" -eq 40 ] || { echo "ERROR: taxonomies expected=40 actual=$TAX_COUNT"; exit 20; }
[ "$MOLD_COUNT" -eq 33 ] || { echo "ERROR: mold fields expected=33 actual=$MOLD_COUNT"; exit 21; }
[ "$SERMON_COUNT" -eq 34 ] || { echo "ERROR: full_sermon fields expected=34 actual=$SERMON_COUNT"; exit 22; }
[ "$SUPPORT_COUNT" -eq 31 ] || { echo "ERROR: supporting fields expected=31 actual=$SUPPORT_COUNT"; exit 23; }
[ "$PROCESSING_COUNT" -eq 16 ] || { echo "ERROR: processing keys expected=16 actual=$PROCESSING_COUNT"; exit 24; }
[ "$TERM_COUNT" -gt 0 ] || { echo "ERROR: runtime terms are empty"; exit 25; }

echo "========== RESTART =========="
systemctl restart zoha-api-v3 zoha-web
sleep 4
systemctl is-active --quiet zoha-api-v3
systemctl is-active --quiet zoha-web

echo "========== FINAL =========="
echo "BRANCH=$BRANCH"
echo "GITLAB_SHA=$REMOTE_SHA"
echo "BACKUP=$BACKUP"
echo "ZOHAONLINE_INDEX_V013=PASS"
