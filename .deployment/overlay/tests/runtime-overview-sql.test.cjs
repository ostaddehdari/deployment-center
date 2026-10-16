const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');

const service=fs.readFileSync('apps/api/src/admin-content-studio/admin-runtime-index.service.ts','utf8');

test('runtime overview grouped taxonomy query orders by grouped assignment column',()=>{
  assert.match(service,/ORDER BY CASE WHEN p\.sort_order IS NULL THEN 1 ELSE 0 END,COALESCE\(p\.sort_order,999999\),t\.code/);
  assert.doesNotMatch(service,/ORDER BY CASE WHEN p\.taxonomy_code IS NULL THEN 1 ELSE 0 END/);
  assert.match(service,/GROUP BY t\.code,p\.sort_order,p\.is_required,p\.settings/);
});
