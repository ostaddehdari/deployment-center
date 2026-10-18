'use strict';
const fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process');
const api=path.resolve(__dirname,'../apps/api'),dist=path.join(api,'dist'),entry=path.join(dist,'main.js');
function walk(dir){const out=[];if(!fs.existsSync(dir))return out;for(const e of fs.readdirSync(dir,{withFileTypes:true})){if(e.name==='node_modules')continue;const p=path.join(dir,e.name);if(e.isDirectory())out.push(...walk(p));else if(e.name==='main.js'&&fs.existsSync(path.join(dir,'app.module.js')))out.push(p)}return out}
if(!fs.existsSync(entry)){
 const candidates=walk(dist);
 if(candidates.length!==1)throw new Error('API build must contain exactly one main.js with its app.module.js; found '+candidates.length);
 const relative='./'+path.relative(dist,candidates[0]).split(path.sep).join('/');
 fs.writeFileSync(entry,"'use strict';\nrequire("+JSON.stringify(relative)+");\n",{flag:'wx'});
 console.log('API_ENTRY_WRAPPER='+relative);
}
if(fs.statSync(entry).size===0)throw new Error('API entry is empty');
cp.execFileSync(process.execPath,['--check',entry],{stdio:'inherit'});
console.log('API_EXECUTABLE_VERIFIED='+entry);
