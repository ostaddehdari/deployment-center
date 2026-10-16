#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${1:-/var/www/zoha}"
OUT="${2:-/root/zoha-index-integration-source-$(date +%Y%m%d-%H%M%S).tgz}"
WORK="$(mktemp -d /tmp/zoha-index-source.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT

cd "$ROOT"
[ -d .git ] || { echo "ERROR: $ROOT is not a git working tree"; exit 2; }

mkdir -p "$WORK/source" "$WORK/meta"

echo "Collecting exact ZohaOnline authoring/indexing integration source..."

git branch --show-current > "$WORK/meta/branch.txt"
git rev-parse HEAD > "$WORK/meta/head.txt"
git remote -v > "$WORK/meta/remotes.txt"
git status --short > "$WORK/meta/status.txt"
git log -15 --oneline --decorate > "$WORK/meta/recent-commits.txt"

copy_path() {
  local p="$1"
  if [ -e "$p" ]; then
    mkdir -p "$WORK/source/$(dirname "$p")"
    cp -a "$p" "$WORK/source/$p"
  fi
}

# Backend: exact current content write flow, auth, DB and runtime indexing.
for p in   apps/api/src/app.module.ts   apps/api/src/content-authoring   apps/api/src/index-runtime   apps/api/src/admin-content-studio   apps/api/src/common   apps/api/src/db.ts   apps/api/src/database   apps/api/src/entities/entity-operation.service.ts   apps/api/package.json
do
  copy_path "$p"
done

# Frontend: current authoring shell/pages/composables + runtime indexing + auth.
for p in   apps/web/components/content   apps/web/components/content-authoring   apps/web/components/indexing   apps/web/composables/useContentAuthoring.ts   apps/web/composables/useIndexRuntime.ts   apps/web/composables/useZohaAuth.ts   apps/web/composables/useAuth.ts   apps/web/pages/app/fiche.vue   apps/web/pages/app/sermon.vue   apps/web/pages/app/supporting.vue   apps/web/pages/app/content   apps/web/pages/app/indexing   apps/web/types   apps/web/package.json   apps/web/nuxt.config.ts
do
  copy_path "$p"
done

# Discover any current source file that actually references authoring/indexing.
while IFS= read -r p; do
  copy_path "$p"
done < <(
  grep -RIlE     'ContentAuthoringShell|useContentAuthoring|IndexRuntimePanel|useIndexRuntime|content-authoring|index-runtime'     apps/web apps/api/src tests 2>/dev/null | sort -u
)

# Migrations and tests needed to preserve current contracts.
for p in   database-v2/migrations/postgres/160_admin_content_type_index_builder.sql   database-v2/migrations/postgres/170_index_defaults_personal_items.sql   tests/content-authoring.test.cjs   tests/admin-content-studio.test.cjs   tests/index-runtime-defaults.test.cjs   package.json
do
  copy_path "$p"
done

# Guardrail: never package likely secrets/runtime artifacts.
find "$WORK/source" -type f \(   -name '.env' -o -name '.env.*' -o   -name '*password*' -o -name '*secret*' -o   -name '*.pem' -o -name '*.key' -o   -name 'id_rsa*' -o -name 'id_ed25519*' \) -delete 2>/dev/null || true

find "$WORK/source" -type d \(   -name node_modules -o -name .nuxt -o -name .output -o -name dist -o -name uploads \) -prune -exec rm -rf {} + 2>/dev/null || true

cat > "$WORK/meta/README.txt" <<'EOF'
ZohaOnline exact-source integration snapshot.
Purpose: integrate runtime indexing directly into the existing create/edit flows.
Contains source/config/tests only. No .env, credentials, databases, uploads or build artifacts.
This collector is read-only with respect to the Zoha project.
EOF

tar -C "$WORK" -czf "$OUT" source meta
sha256sum "$OUT" | tee "${OUT}.sha256"

echo
echo "SOURCE_SNAPSHOT=PASS"
echo "FILE=$OUT"
echo "SHA256_FILE=${OUT}.sha256"
echo "SIZE=$(du -h "$OUT" | awk '{print $1}')"
