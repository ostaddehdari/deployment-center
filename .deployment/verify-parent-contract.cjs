// Run against the collected source after applying both release patches.
// Node >=22.13 is required only for this standalone verification helper.
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {stripTypeScriptTypes}=require('node:module');
const root=path.resolve(process.argv[2]);
const read=p=>fs.readFileSync(path.join(root,p),'utf8');
const panel=read('apps/web/components/indexing/IndexRuntimePanel.vue');
const personal=read('apps/web/components/indexing/IndexPersonalSelect.vue');
const indexService=read('apps/api/src/index-runtime/index-runtime.service.ts');
const contract=read('tests/index-authoring-integration.test.cjs');
const helpers=panel.split('\n').filter(l=>/^const (selection|selectionTitle|fieldByTaxonomy|parentFor|personalParentFor)=/.test(l)).join('\n');
assert.equal(helpers.split('\n').length,5);
const source=stripTypeScriptTypes(helpers+'\n globalThis.helpers={selection,selectionTitle,parentFor,personalParentFor};');
const schema={value:{fields:[{code:'topic-key',taxonomyCode:'IDX-001'}]}};
const data={};
const ctx={schema,data};
vm.runInNewContext(source,ctx);
const h=ctx.helpers;
const child={code:'child-key',taxonomyCode:'IDX-002',parentTaxonomyCode:'IDX-001'};

test('v0.4.7 obsolete assertion reproduces the reported failure',()=>{
 assert.throws(()=>assert.match(panel,/personal-parent-option="a\.topic"/),{code:'ERR_ASSERTION'});
});
test('the complete corrected parent contract passes on real collected source',()=>{
 const marker="test('dependent taxonomies filter by parent and personal child creation keeps ownership parent',()=>{";
 const start=contract.indexOf(marker);
 assert.notEqual(start,-1);
 const body=contract.slice(start+marker.length,contract.indexOf('\n});',start));
 vm.runInNewContext(body,{assert,panel,personal,indexService,read});
});
for(const scope of ['system','personal']){
 const parent={id:scope==='system'?'system-17':'user-29',scope,title:'موضوع والد'};
 for(const multi of [false,true]){
  test(`${scope} parent identity survives ${multi?'array':'single'} selection`,()=>{
   const value=multi?[parent]:parent;
   assert.equal(h.selection(value),parent);
   data['topic-key']=value;
   assert.equal(h.parentFor(child),parent.title);
   assert.equal(h.personalParentFor(child),parent);
  });
 }
 test(`${scope} parent sends the correct ownership ID to addPersonal`,async()=>{
  let captured,chosen;
  const item={id:'new-item',scope:'personal',title:'آیتم جدید'};
  const addLine=personal.split('\n').find(l=>l.startsWith('const add='));
  assert.ok(addLine);
  const addCtx={props:{code:'IDX-002',personalParentOption:parent},q:{value:'  آیتم جدید  '},
   api:{addPersonal:async(...args)=>{captured=args;return {item}}},choose:x=>{chosen=x}};
  vm.runInNewContext(addLine+'; globalThis.add=add;',addCtx);
  await addCtx.add();
  assert.deepEqual(Array.from(captured),['IDX-002','آیتم جدید',scope==='system'?parent.id:undefined,scope==='personal'?parent.id:undefined]);
  assert.equal(chosen,item);
 });
}
for(const [label,value] of [['null',null],['undefined',undefined],['empty array',[]]]){
 test(`${label} parent yields empty filter and null selection`,()=>{
  data['topic-key']=value;
  assert.equal(h.selection(value),null);
  assert.equal(h.parentFor(child),'');
  assert.equal(h.personalParentFor(child),null);
 });
}
test('missing parent schema and root fields do not invent an ownership parent',()=>{
 assert.equal(h.parentFor({parentTaxonomyCode:'MISSING'}),'');
 assert.equal(h.personalParentFor({parentTaxonomyCode:'MISSING'}),null);
 assert.equal(h.parentFor({}),'');
 assert.equal(h.personalParentFor({}),null);
});
test('all four parent relationships remain in the runtime service',()=>{
 for(const [child,parent] of [['IDX-002','IDX-001'],['IDX-006','IDX-005'],['IDX-008','IDX-007'],['IDX-010','IDX-009']]){
  assert.ok(indexService.includes(`'${child}':'${parent}'`));
 }
});
