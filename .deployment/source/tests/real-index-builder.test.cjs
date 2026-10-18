const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const read=p=>fs.readFileSync(p,'utf8');

const page=read('apps/web/pages/admin/index-builder.vue');
const types=read('apps/web/pages/admin/content-types.vue');
const sidebar=read('apps/web/components/admin/AdminSidebar.vue');
const controller=read('apps/api/src/admin-content-studio/admin-runtime-index.controller.ts');
const runtimeAdmin=read('apps/api/src/admin-content-studio/admin-runtime-index.service.ts');
const runtime=read('apps/api/src/index-runtime/index-runtime.service.ts');
const panel=read('apps/web/components/indexing/IndexRuntimePanel.vue');
const dynamic=read('apps/web/components/indexing/IndexDynamicField.vue');
const migration=read('database-v2/migrations/postgres/180_hybrid_runtime_index_builder.sql');

test('builder is a real hybrid: Gravity toolbox controls plus runtime vocabulary binding',()=>{
 assert.match(page,/useAdminContentStudio\(\)/);
 assert.match(page,/useAdminRuntimeIndex\(\)/);
 assert.match(page,/field-palette/);
 assert.match(page,/Toolbox فرم/);
 assert.match(page,/SourceMode/);
 assert.match(page,/TaxonomyCode/);
 assert.match(runtimeAdmin,/index_runtime_taxonomies/);
 assert.match(runtimeAdmin,/index_runtime_post_type_fields/);
});

test('builder puts elements and settings in one collapsible left tab rail',()=>{
 assert.match(page,/sideCollapsed/);
 assert.match(page,/المنت‌ها/);
 assert.match(page,/تنظیمات/);
 assert.match(page,/builder-shell/);
 assert.match(page,/grid-template-columns:370px minmax\(0,1fr\)/);
});

test('manual options runtime binding and conditional logic are editable',()=>{
 assert.match(page,/گزینه‌های دستی/);
 assert.match(page,/runtime_taxonomy/);
 assert.match(page,/منطق شرطی/);
 assert.match(page,/ConditionOperator/);
 assert.match(page,/ConditionAction/);
 assert.match(panel,/isVisible/);
 assert.match(panel,/condition/);
});

test('taxonomy items retain real search create edit and safe deactivate APIs',()=>{
 assert.match(controller,/taxonomies\/:code\/terms/);
 assert.match(controller,/createTerm/);
 assert.match(controller,/updateTerm/);
 assert.match(controller,/deleteTerm/);
 assert.match(page,/جستجو بین آیتم‌ها/);
 assert.match(page,/افزودن آیتم/);
 assert.match(page,/غیرفعال/);
});

test('builder draft preview uses operational renderer with schema override',()=>{
 assert.match(page,/IndexRuntimePanel/);
 assert.match(page,/نمایش واقعی کاربر/);
 assert.match(page,/:schema-override="previewSchema"/);
 assert.match(panel,/schemaOverride/);
 assert.match(panel,/IndexDynamicField/);
});

test('published schema only reads the builder active version and never resurrects removed legacy fields',()=>{
 assert.match(runtime,/content_type_index_forms/);
 assert.match(runtime,/index_forms/);
 assert.match(runtime,/index_form_versions/);
 assert.match(runtime,/index_form_fields/);
 assert.match(runtime,/f\.active_version/);
 assert.match(runtime,/index-builder-v6/);
 assert.doesNotMatch(runtime,/runtime-fallback/);
 assert.doesNotMatch(runtime,/FROM zoha.index_runtime_post_type_fields/);
 assert.match(runtime,/parent_key/);
});

test('dynamic renderer covers the advertised toolbox families',()=>{
 for(const kind of ['section','html','page','hidden','searchable_select','select','multiselect','radio','checkbox','textarea','richtext','boolean','consent','range','tags','file','reference','relation','repeater','name','address','group'])assert.ok(dynamic.includes(`f.type==='${kind}'`),kind);
 assert.match(dynamic,/IndexPersonalSelect/);
 assert.match(dynamic,/runtime_taxonomy/);
});

test('topic analysis keeps semantic runtime codes and same payload shape',()=>{
 assert.match(panel,/IDX-001/);
 assert.match(panel,/IDX-003/);
 assert.match(panel,/IDX-002/);
 assert.match(panel,/IDX-004/);
 assert.match(panel,/topicAnalyses/);
 assert.match(migration,/taxonomyCode/);
 assert.match(migration,/IDX-002.*IDX-001/);
});

test('content types link directly to their own builder and old labels menu stays removed',()=>{
 assert.match(types,/builderUrl\(item\.Code\)/);
 assert.match(types,/نمایه‌ساز این نوع/);
 assert.doesNotMatch(sidebar,/label:'نمایه‌ها'/);
 assert.doesNotMatch(sidebar,/to:'\/admin\/labels'/);
});
