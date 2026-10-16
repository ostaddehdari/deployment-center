const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');

const read=p=>fs.readFileSync(p,'utf8');

test('create routes explicitly import ContentAuthoringShell',()=>{
  for(const p of [
    'apps/web/pages/app/create/fiche.vue',
    'apps/web/pages/app/create/sermon.vue',
    'apps/web/pages/app/create/supporting.vue',
  ]){
    const s=read(p);
    assert.match(s,/import ContentAuthoringShell from ['"]~\/components\/content\/ContentAuthoringShell\.vue['"]/);
    assert.match(s,/<ContentAuthoringShell\b/);
  }
});

test('edit route explicitly imports ContentAuthoringShell',()=>{
  const s=read('apps/web/pages/app/content/[id]/edit.vue');
  assert.match(s,/import ContentAuthoringShell from ['"]~\/components\/content\/ContentAuthoringShell\.vue['"]/);
  assert.match(s,/<ContentAuthoringShell\b/);
});

test('authoring shell explicitly imports IndexRuntimePanel',()=>{
  const s=read('apps/web/components/content/ContentAuthoringShell.vue');
  assert.match(s,/import IndexRuntimePanel from ['"]~\/components\/indexing\/IndexRuntimePanel\.vue['"]/);
  assert.match(s,/<IndexRuntimePanel\b/);
});

test('index runtime panel explicitly imports personal selector',()=>{
  const s=read('apps/web/components/indexing/IndexRuntimePanel.vue');
  assert.match(s,/import IndexPersonalSelect from ['"]~\/components\/indexing\/IndexPersonalSelect\.vue['"]/);
  assert.match(s,/<IndexPersonalSelect\b/);
});

test('content indexing route explicitly imports runtime panel',()=>{
  const s=read('apps/web/pages/app/content/[id]/indexing.vue');
  assert.match(s,/import IndexRuntimePanel from ['"]~\/components\/indexing\/IndexRuntimePanel\.vue['"]/);
  assert.match(s,/<IndexRuntimePanel\b/);
});

test('direct runtime indexing route is explicit when present',()=>{
  const p='apps/web/pages/app/indexing/[contentType]/[contentId].vue';
  if(!fs.existsSync(p))return;
  const s=read(p);
  assert.match(s,/import IndexRuntimePanel from ['"]~\/components\/indexing\/IndexRuntimePanel\.vue['"]/);
});
