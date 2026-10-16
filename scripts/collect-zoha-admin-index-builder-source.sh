#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${1:-/var/www/zoha}"
OUT="${2:-/root/zoha-admin-index-builder-source-$(date +%Y%m%d-%H%M%S).tgz}"
WORK="$(mktemp -d /tmp/zoha-admin-index-builder.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT

cd "$ROOT"
[ -d .git ] || { echo "ERROR: $ROOT is not a git working tree"; exit 2; }

mkdir -p "$WORK/source" "$WORK/meta"

git branch --show-current > "$WORK/meta/branch.txt"
git rev-parse HEAD > "$WORK/meta/head.txt"
git status --short > "$WORK/meta/status.txt"
git log -12 --oneline --decorate > "$WORK/meta/recent-commits.txt"

copy_path(){
  local p="$1"
  if [ -e "$p" ]; then
    mkdir -p "$WORK/source/$(dirname "$p")"
    cp -a "$p" "$WORK/source/$p"
  fi
}

for p in   apps/api/src/app.module.ts   apps/api/src/admin-content-studio   apps/api/src/index-runtime   apps/api/src/common/database/database.service.ts   apps/api/src/common/types.ts   apps/web/pages/admin/index-builder.vue   apps/web/pages/admin/content-types.vue   apps/web/pages/admin/content.vue   apps/web/pages/admin/forms.vue   apps/web/composables/useAdminContentStudio.ts   apps/web/composables/useIndexRuntime.ts   apps/web/composables/useZohaAuth.ts   apps/web/components/admin   apps/web/components/indexing   apps/web/layouts   apps/web/middleware   apps/web/types/admin-content-studio.ts   apps/web/types/content.ts   apps/web/types/site.ts   database-v2/migrations/postgres/160_admin_content_type_index_builder.sql   database-v2/migrations/postgres/170_index_defaults_personal_items.sql   tests/admin-content-studio.test.cjs   tests/index-runtime-defaults.test.cjs   tests/index-authoring-integration.test.cjs   package.json
do
  copy_path "$p"
done

while IFS= read -r p; do
  copy_path "$p"
done < <(
  grep -RIlE     '/admin/index-builder|/admin/forms|نمایه.?ساز|IndexForms|FieldCatalog|admin-content-studio|index_runtime_taxonomies'     apps/web apps/api/src tests 2>/dev/null | sort -u
)

find "$WORK/source" -type f \(   -name '.env' -o -name '.env.*' -o -name '*password*' -o -name '*secret*'   -o -name '*.pem' -o -name '*.key' -o -name 'id_rsa*' -o -name 'id_ed25519*' \) -delete 2>/dev/null || true

find "$WORK/source" -type d \(   -name node_modules -o -name .nuxt -o -name .output -o -name dist -o -name uploads \) -prune -exec rm -rf {} + 2>/dev/null || true

cat > "$WORK/meta/README.txt" <<'EOF'
ZohaOnline admin/index-builder exact source snapshot.
Read-only collection for rebuilding the admin index builder on the real runtime taxonomy model.
No environments, secrets, credentials, uploads, databases, node_modules or build output are included.
EOF

tar -C "$WORK" -czf "$OUT" source meta
sha256sum "$OUT" | tee "${OUT}.sha256"

echo
echo "ADMIN_INDEX_SOURCE_SNAPSHOT=PASS"
echo "FILE=$OUT"
echo "SHA256_FILE=${OUT}.sha256"
echo "SIZE=$(du -h "$OUT" | awk '{print $1}')"
