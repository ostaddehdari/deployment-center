const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');

const migration=fs.readFileSync('database-v2/migrations/postgres/160_admin_content_type_index_builder.sql','utf8');
const migration180=fs.readFileSync('database-v2/migrations/postgres/180_hybrid_runtime_index_builder.sql','utf8');
const service=fs.readFileSync('apps/api/src/admin-content-studio/admin-content-studio.service.ts','utf8');
const dto=fs.readFileSync('apps/api/src/admin-content-studio/admin-content-studio.dto.ts','utf8');
const controller=fs.readFileSync('apps/api/src/admin-content-studio/admin-content-studio.controller.ts','utf8');
const moduleSource=fs.readFileSync('apps/api/src/app.module.ts','utf8');
const typesPage=fs.readFileSync('apps/web/pages/admin/content-types.vue','utf8');
const builderPage=fs.readFileSync('apps/web/pages/admin/index-builder.vue','utf8');
const sidebar=fs.readFileSync('apps/web/components/admin/AdminSidebar.vue','utf8');
const indexing=fs.readFileSync('apps/api/src/content-authoring/content-authoring.service.ts','utf8');

test('content studio migration creates versioned index-form schema and seeds three existing types',()=>{
 for(const table of ['index_forms','index_form_versions','index_form_fields','index_form_options','index_form_rules','content_type_index_forms'])assert.match(migration,new RegExp(`CREATE TABLE IF NOT EXISTS ${table}`));
 assert.match(migration,/mold_default_index/);
 assert.match(migration,/full_sermon_default_index/);
 assert.match(migration,/supporting_default_index/);
 assert.match(migration,/JOIN form_fields ff/);
});

test('admin content studio API supports content-type management and full index builder lifecycle',()=>{
 assert.match(controller,/api\/admin\/content-studio\/v1/);
 for(const name of ['createContentType','updateContentType','addField','updateField','removeField','reorder','publish','assign'])assert.match(controller,new RegExp(name));
 assert.match(service,/roles\.includes\('system_admin'\)/);
 assert.match(moduleSource,/AdminContentStudioController/);
});

test('field catalog contains the complete Gravity-style toolbox including searchable select',()=>{
 const kinds=['text','textarea','richtext','number','boolean','email','phone','url','date','time','datetime','password','select','searchable_select','multiselect','radio','checkbox','tags','consent','file','reference','relation','repeater','group','duration','color','range','name','address','section','html','page','hidden'];
 for(const kind of kinds){assert.ok(service.includes(`Kind:'${kind}'`),kind);assert.ok(dto.includes(`'${kind}'`),`dto:${kind}`)}
 assert.equal(kinds.length,33);
});

test('admin has dedicated content type page with three core content families and builder links',()=>{
 assert.match(typesPage,/محتوای مولد/);
 assert.match(typesPage,/full_sermon/);
 assert.match(typesPage,/محتوای پشتیبان/);
 assert.match(typesPage,/نوع محتوای جدید/);
 assert.match(typesPage,/نمایه‌ساز این نوع/);
 assert.match(typesPage,/builderUrl/);
});

test('hybrid index builder uses versioned form studio plus real runtime vocabulary',()=>{
 for(const phrase of ['useAdminContentStudio','useAdminRuntimeIndex','field-palette','sideCollapsed','المنت‌ها','تنظیمات','SourceMode','TaxonomyCode','گزینه‌های دستی','منطق شرطی','مدیریت آیتم‌های این نمایه','نمایش واقعی کاربر','schema-override'])assert.match(builderPage,new RegExp(phrase));
 assert.match(builderPage,/draggable="true"/);
 assert.match(builderPage,/studio\.reorder/);
 assert.match(builderPage,/studio\.addField/);
 assert.match(builderPage,/studio\.updateField/);
 assert.match(builderPage,/studio\.removeField/);
 assert.match(builderPage,/studio\.publish/);
 assert.match(builderPage,/runtime\.terms/);
 assert.match(builderPage,/runtime\.createTerm/);
 assert.match(builderPage,/runtime\.updateTerm/);
 assert.match(builderPage,/runtime\.deleteTerm/);
});

test('v4 migration bridges all three core forms from runtime assignments without deleting old versions',()=>{
 assert.match(migration180,/runtime-hybrid-v4/);
 assert.match(migration180,/index_runtime_post_type_fields/);
 assert.match(migration180,/index_runtime_taxonomies/);
 assert.match(migration180,/searchable_select/);
 assert.match(migration180,/max\(version\)/);
 assert.match(migration180,/active_version=v_active,draft_version=v_draft/);
 assert.doesNotMatch(migration180,/DELETE FROM index_form_versions/);
});

test('sidebar links to content types and index builder',()=>{
 assert.match(sidebar,/\/admin\/content-types/);
 assert.match(sidebar,/\/admin\/index-builder/);
});

test('published index forms are returned to user content indexing endpoint',()=>{
 assert.match(indexing,/content_type_index_forms/);
 assert.match(indexing,/index_form_fields/);
 assert.match(indexing,/Definitions:fields\.rows\.map/);
});
