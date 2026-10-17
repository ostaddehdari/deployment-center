const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');

const shell=fs.readFileSync('apps/web/components/content/ContentAuthoringShell.vue','utf8');

test('authoring folder list iterates the Vue ref value',()=>{
  assert.match(shell,/for\(const tree of trees\.value\)walk\(tree\.Projects,0\)/);
  assert.doesNotMatch(shell,/for\(const tree of trees\)walk\(tree\.Projects,0\)/);
});

test('authoring shell explicitly imports rich HTML editor',()=>{
  assert.match(shell,/import HtmlRichEditor from ['"]~\/components\/content\/HtmlRichEditor\.vue['"]/);
  assert.match(shell,/<HtmlRichEditor\b/);
});
