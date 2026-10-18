const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const read=p=>fs.readFileSync(p,'utf8');

const shell=read('apps/web/components/content/ContentAuthoringShell.vue');
const panel=read('apps/web/components/indexing/IndexRuntimePanel.vue');
const personal=read('apps/web/components/indexing/IndexPersonalSelect.vue');
const runtime=read('apps/web/composables/useIndexRuntime.ts');
const indexController=read('apps/api/src/index-runtime/index-runtime.controller.ts');
const indexService=read('apps/api/src/index-runtime/index-runtime.service.ts');
const appModule=read('apps/api/src/app.module.ts');
const contentService=read('apps/api/src/content-authoring/content-authoring.service.ts');
const dto=read('apps/api/src/content-authoring/content-authoring.dto.ts');
const indexingPage=read('apps/web/pages/app/content/[id]/indexing.vue');

test('authoring shell embeds runtime indexing as real third step',()=>{
 assert.match(shell,/step=ref<'content'\|'metadata'\|'indexing'>/);
 assert.match(shell,/IndexRuntimePanel v-model="indexPayload"/);
 assert.match(shell,/:content-id="editingId\|\|''" embedded/);
 assert.match(shell,/ثبت محتوا و نمایه‌ها/);
 assert.doesNotMatch(shell,/router\.push\(`\/app\/content\/\$\{created\.Id\}\/indexing`\)/);
});

test('create and update send index payload in the same authoring request',()=>{
 assert.match(shell,/IndexPayload:indexPayload\.value/);
 assert.match(dto,/IndexPayload\?: Record<string, unknown>/);
 assert.match(contentService,/saveIndexPayload\(principal,typeCode,contentId,body\.IndexPayload\)/);
 assert.match(contentService,/saveIndexPayload\(principal,row\.type_code,contentId,body\.IndexPayload\)/);
 assert.match(contentService,/content_index_payloads/);
});

test('runtime API uses authenticated request context and shared database service',()=>{
 assert.match(indexController,/@Req\(\) r:AppRequest/);
 assert.doesNotMatch(indexController,/@Headers\('userid'\)/);
 assert.match(indexService,/constructor\(private readonly db:DatabaseService\)/);
 assert.doesNotMatch(indexService,/new Pool/);
 assert.match(indexService,/cr\.owner_id=\$2 AND ct\.code=\$3/);
 assert.match(appModule,/IndexRuntimeController/);
 assert.match(appModule,/IndexRuntimeService/);
 assert.doesNotMatch(appModule,/imports:\[IndexRuntimeModule\]/);
});

test('frontend runtime uses the real Zoha auth headers and unwraps API envelope',()=>{
 assert.match(runtime,/useZohaAuth\(\)/);
 assert.match(runtime,/authenticatedHeaders\(\)/);
 assert.match(runtime,/const unwrap=/);
 assert.doesNotMatch(runtime,/useAuth\(\)/);
});

test('dependent taxonomies filter by parent and personal child creation keeps ownership parent',()=>{
 assert.match(indexService,/parent_taxonomy_code/);
 assert.doesNotMatch(indexService,/const parentMap/);
 assert.match(panel,/f\.parentTaxonomyCode/);
 assert.match(panel,/:parent="parentFor\(f\)"/);
 assert.match(panel,/:personal-parent-option="personalParentFor\(f\)"/);
 assert.match(personal,/parentSystemTermId/);
 assert.match(personal,/parentUserTermId/);
 assert.match(indexService,/parent_system_term_id/);
 assert.match(indexService,/parent_user_term_id/);
 assert.match(panel,/:parent="parentFor\(f,a\)"/);
 assert.match(panel,/:personal-parent-option="personalParentFor\(f,a\)"/);
 const dynamic=read('apps/web/components/indexing/IndexDynamicField.vue');
 assert.match(dynamic,/:parent="parent"/);
 assert.match(dynamic,/:personal-parent-option="personalParentOption"/);
 assert.match(personal,/parent\?\.scope==='system'\?parent\.id:undefined/);
 assert.match(personal,/parent\?\.scope==='personal'\?parent\.id:undefined/);
});

test('legacy carrier label is replaced by subtopic in authoring UI',()=>{
 assert.match(shell,/زیرموضوع<input v-model="meta\.carrier">/);
 assert.doesNotMatch(shell,/>محمول</);
});

test('standalone indexing route now renders the operational runtime panel',()=>{
 assert.match(indexingPage,/IndexRuntimePanel/);
 assert.match(indexingPage,/:content-type="content\.TypeCode"/);
 assert.doesNotMatch(indexingPage,/نمایه‌ای برای نمایش وجود ندارد/);
});
