const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');

const runtime=fs.readFileSync('apps/web/composables/useIndexRuntime.ts','utf8');
const panel=fs.readFileSync('apps/web/components/indexing/IndexRuntimePanel.vue','utf8');
const select=fs.readFileSync('apps/web/components/indexing/IndexPersonalSelect.vue','utf8');
const controller=fs.readFileSync('apps/api/src/admin-content-studio/admin-runtime-index.controller.ts','utf8');
const service=fs.readFileSync('apps/api/src/admin-content-studio/admin-runtime-index.service.ts','utf8');
const builder=fs.readFileSync('apps/web/pages/admin/index-builder.vue','utf8');

test('admin preview uses admin authenticated schema and options routes',()=>{
 assert.match(runtime,/mode:'user'\|'admin-preview'/);
 assert.match(runtime,/\/api\/admin\/runtime-index\/v1\/preview\/schema/);
 assert.match(runtime,/\/api\/admin\/runtime-index\/v1\/preview\/taxonomies/);
 assert.match(controller,/preview\/schema\/:contentType/);
 assert.match(controller,/preview\/taxonomies\/:code\/options/);
 assert.match(service,/async previewSchema/);
 assert.match(service,/async previewOptions/);
});

test('same runtime renderer is reused in admin preview without personal writes',()=>{
 assert.match(panel,/adminPreview\?:boolean/);
 assert.match(panel,/useIndexRuntime\(props\.adminPreview\?'admin-preview':'user'\)/);
 assert.match(select,/adminPreview\?:boolean/);
 assert.match(select,/!props\.adminPreview&&props\.allowsPersonal/);
 assert.match(builder,/:admin-preview="true"/);
});
