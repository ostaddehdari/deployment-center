const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');

const migration=fs.readFileSync('database-v2/migrations/postgres/160_admin_content_type_index_builder.sql','utf8');
const service=fs.readFileSync('apps/api/src/admin-content-studio/admin-content-studio.service.ts','utf8');
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
 assert.match(controller,/createContentType/);
 assert.match(controller,/updateContentType/);
 assert.match(controller,/addField/);
 assert.match(controller,/updateField/);
 assert.match(controller,/removeField/);
 assert.match(controller,/reorder/);
 assert.match(controller,/publish/);
 assert.match(controller,/assign/);
 assert.match(service,/roles\.includes\('system_admin'\)/);
 assert.match(moduleSource,/AdminContentStudioController/);
});

test('field catalog includes Gravity-Forms-style basic choice advanced and layout fields',()=>{
 for(const kind of ['text','textarea','richtext','number','email','phone','date','time','select','multiselect','radio','checkbox','file','reference','relation','repeater','group','consent','section','html','page','hidden'])assert.ok(service.includes(`Kind:'${kind}'`),kind);
});

test('admin has dedicated content type page with three core content families and runtime builder links',()=>{
 assert.match(typesPage,/محتوای مولد/);
 assert.match(typesPage,/full_sermon/);
 assert.match(typesPage,/محتوای پشتیبان/);
 assert.match(typesPage,/نوع محتوای جدید/);
 assert.match(typesPage,/نمایه‌های واقعی/);
 assert.match(typesPage,/نمایه‌ساز این نوع/);
 assert.match(typesPage,/builderUrl/);
});

test('index builder is runtime-backed with collapsible tabs real preview and term management',()=>{
 for(const phrase of ['useAdminRuntimeIndex','sideCollapsed','sideTab','المنت‌ها','تنظیمات','مدیریت آیتم‌های فهرست','نمایش واقعی کاربر','IndexRuntimePanel'])assert.match(builderPage,new RegExp(phrase));
 assert.match(builderPage,/draggable="true"/);
 assert.match(builderPage,/runtime\.reorder/);
 assert.match(builderPage,/runtime\.assignField/);
 assert.match(builderPage,/runtime\.removeField/);
 assert.match(builderPage,/runtime\.updateTaxonomy/);
 assert.match(builderPage,/runtime\.terms/);
 assert.match(builderPage,/runtime\.createTerm/);
 assert.match(builderPage,/runtime\.updateTerm/);
 assert.match(builderPage,/runtime\.deleteTerm/);
 assert.doesNotMatch(builderPage,/field-palette/);
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
