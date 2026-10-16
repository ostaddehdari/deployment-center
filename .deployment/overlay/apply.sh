#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${1:-/var/www/zoha}"
PKG="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "========== ZOHAONLINE v0.3.3 / RUNTIME OVERVIEW SQL HOTFIX =========="
[ -d .git ] || { echo 'ERROR: project is not git'; exit 2; }
BRANCH="$(git branch --show-current)"
[ "$BRANCH" = 'feature/zoha-public-site-v1' ] || { echo "ERROR: branch=$BRANCH"; exit 3; }
ORIGIN_URL="$(git remote get-url origin 2>/dev/null || true)"
case "$ORIGIN_URL" in
  *git.mtacloud.ir/vendors/zoha/zoha.git*) ;;
  *) echo "ERROR: unexpected origin: $ORIGIN_URL"; exit 4;;
esac

git merge-base --is-ancestor 2cb7b5f68dfe16c885a01b64ec4f7a49fa688249 HEAD || {
  echo 'ERROR: v0.3.2 base commit is not in branch history'
  exit 5
}
if ! git diff --cached --quiet; then
  echo 'ERROR: pre-existing staged changes; stopping.'
  git status --short
  exit 6
fi

FILES=(
'apps/api/src/admin-content-studio/admin-runtime-index.service.ts'
'tests/runtime-overview-sql.test.cjs'
)

BACKUP="/root/zoha-v033-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP"
for p in "${FILES[@]}"; do
  if [ -e "$p" ]; then
    mkdir -p "$BACKUP/$(dirname "$p")"
    cp -a "$p" "$BACKUP/$p"
  fi
done

echo "========== PATCH OVERVIEW QUERY =========="
python3 - "$ROOT/apps/api/src/admin-content-studio/admin-runtime-index.service.ts" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
s=p.read_text(encoding='utf-8')
old="ORDER BY CASE WHEN p.taxonomy_code IS NULL THEN 1 ELSE 0 END,COALESCE(p.sort_order,999999),t.code"
new="ORDER BY CASE WHEN p.sort_order IS NULL THEN 1 ELSE 0 END,COALESCE(p.sort_order,999999),t.code"
if new in s:
    print("OVERVIEW_SQL_ALREADY_FIXED=YES")
elif old in s:
    s=s.replace(old,new,1)
    p.write_text(s,encoding='utf-8')
    print("OVERVIEW_SQL_PATCHED=YES")
else:
    raise SystemExit("ERROR: expected overview ORDER BY pattern not found")
PY

mkdir -p tests
cp -a "$PKG/tests/runtime-overview-sql.test.cjs" tests/runtime-overview-sql.test.cjs

echo "========== SOURCE REGRESSION TEST =========="
node --test tests/runtime-overview-sql.test.cjs

echo "========== LIVE POSTGRES OVERVIEW SQL SMOKE =========="
export PGPASSWORD="$(cat /etc/zoha-online/postgres-password)"
psql -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 5433 -U zoha_app -d zoha_core -Atc "
SELECT count(*) FROM (
  SELECT t.code,t.title,t.legacy_title,t.field_type,t.is_multi,t.allows_personal,t.metadata,t.is_active,
         count(term.id) FILTER (WHERE term.is_active)::text AS active_term_count,
         count(term.id)::text AS total_term_count,
         p.sort_order,p.is_required,p.settings
  FROM zoha.index_runtime_taxonomies t
  LEFT JOIN zoha.index_runtime_terms term ON term.taxonomy_code=t.code
  LEFT JOIN zoha.index_runtime_post_type_fields p ON p.taxonomy_code=t.code AND p.post_type_code='mold'
  GROUP BY t.code,p.sort_order,p.is_required,p.settings
  ORDER BY CASE WHEN p.sort_order IS NULL THEN 1 ELSE 0 END,COALESCE(p.sort_order,999999),t.code
) q;
" | grep -qx '40'
echo "LIVE_OVERVIEW_SQL_SMOKE=PASS rows=40"

echo "========== FULL CONTRACT SUITE =========="
npm run test:contracts

echo "========== BUILD API =========="
npm run build

echo "========== DIFF CHECK =========="
git diff --check -- "${FILES[@]}"

echo "========== COMMIT RELEASE FILES ONLY =========="
git add -- "${FILES[@]}"
if ! git diff --cached --quiet; then
  git -c user.name='ostaddehdari' \
      -c user.email='ostaddehdari@users.noreply.git.mtacloud.ir' \
      commit -m 'نمایه‌ساز واقعی: رفع خطای GROUP BY در overview'
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

echo "========== RESTART API =========="
systemctl restart zoha-api-v3
sleep 5
systemctl is-active --quiet zoha-api-v3
echo 'zoha-api-v3=active'

echo "========== POST-RESTART ERROR CHECK =========="
journalctl -u zoha-api-v3 --since "2 minutes ago" --no-pager -o cat | tail -n 120

echo "========== FINAL =========="
echo "BRANCH=$BRANCH"
echo "GITLAB_SHA=$REMOTE_SHA"
echo "BACKUP=$BACKUP"
echo "ZOHAONLINE_RUNTIME_OVERVIEW_SQL_V033=PASS"
