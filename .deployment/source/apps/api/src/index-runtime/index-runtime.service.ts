import { HttpStatus, Injectable } from '@nestjs/common';
import { DatabaseService } from '../common/database/database.service';
import { DomainException } from '../common/http/domain.exception';
import type { Principal } from '../common/types';
import { createHash, randomUUID } from 'node:crypto';
import { mkdir, writeFile, readFile, unlink } from 'node:fs/promises';
import { join } from 'node:path';

const normalize=(v:string)=>v.normalize('NFKC').replace(/[يى]/g,'ی').replace(/ك/g,'ک').replace(/[\u064b-\u065f\u0670]/g,'').replace(/\u200c/g,' ').replace(/\s+/g,' ').trim().toLocaleLowerCase('fa-IR');
const validTypes=new Set(['mold','full_sermon','supporting']);

@Injectable()
export class IndexRuntimeService{
 constructor(private readonly db:DatabaseService){}

 private fileRoot():string{return process.env.ZOHA_INDEX_FILE_ROOT||'/var/lib/zoha/index-files';}
 async uploadFieldFile(principal:Principal,contentType:string,fieldKey:string,file?:{originalname:string;mimetype:string;size:number;buffer:Buffer}){
  this.assertContentType(contentType);
  const schema=await this.schema(contentType);
  const field=(schema.fields as {key?:string;code:string;type:string;config?:Record<string,unknown>}[]).find(f=>f.key===fieldKey||f.code===fieldKey);
  if(!field||field.type!=='file'||!file?.buffer?.length)throw new DomainException('Index.File.Invalid',HttpStatus.BAD_REQUEST);
  const max=Math.min(10485760,Math.max(1024,Number(field.config?.maxFileMB??1)*1048576));
  if(file.size>max)throw new DomainException('Index.File.TooLarge',HttpStatus.PAYLOAD_TOO_LARGE);
  const name=file.originalname.replace(/[\x00-\x1f/\\]/g,'_').slice(0,240)||'file';
  const allowed=String(field.config?.accept??'').split(',').map(x=>x.trim().toLowerCase()).filter(Boolean);
  if(allowed.length&&!allowed.some(x=>x.startsWith('.')?name.toLowerCase().endsWith(x):x.endsWith('/*')?file.mimetype.startsWith(x.slice(0,-1)):file.mimetype===x))throw new DomainException('Index.File.TypeInvalid',HttpStatus.BAD_REQUEST);
  const id=randomUUID(),root=this.fileRoot(),location=join(root,id);
  await mkdir(root,{recursive:true,mode:0o700});
  await writeFile(location,file.buffer,{mode:0o600,flag:'wx'});
  try{await this.db.query(`INSERT INTO zoha.index_field_files(id,owner_id,content_type,field_key,file_name,mime_type,size_bytes,sha256) VALUES($1,$2,$3,$4,$5,$6,$7,$8)`,[id,principal.id,contentType,fieldKey,name,file.mimetype.slice(0,120)||'application/octet-stream',file.size,createHash('sha256').update(file.buffer).digest('hex')]);}
  catch(e){await unlink(location).catch(()=>undefined);throw e;}
  return {id,name,size:file.size,type:file.mimetype};
 }
 async downloadFieldFile(principal:Principal,id:string){
  if(!/^[0-9a-f-]{36}$/i.test(id))throw new DomainException('Index.File.NotFound',HttpStatus.NOT_FOUND);
  const r=await this.db.query<{file_name:string;mime_type:string}>(`SELECT file_name,mime_type FROM zoha.index_field_files WHERE id=$1 AND owner_id=$2`,[id,principal.id]);
  if(!r.rows[0])throw new DomainException('Index.File.NotFound',HttpStatus.NOT_FOUND);
  const buffer=await readFile(join(this.fileRoot(),id)).catch(()=>{throw new DomainException('Index.File.NotFound',HttpStatus.NOT_FOUND)});
  return {buffer,name:r.rows[0].file_name};
 }

 private assertContentType(contentType:string):void{
  if(!validTypes.has(contentType))throw new DomainException('Index.ContentType.Invalid',HttpStatus.BAD_REQUEST);
 }
 private payloadObject(payload:unknown):Record<string,unknown>{
  if(!payload||typeof payload!=='object'||Array.isArray(payload))throw new DomainException('Index.Payload.Invalid',HttpStatus.BAD_REQUEST);
  const encoded=JSON.stringify(payload);
  if(Buffer.byteLength(encoded,'utf8')>262144)throw new DomainException('Index.Payload.TooLarge',HttpStatus.PAYLOAD_TOO_LARGE);
  return payload as Record<string,unknown>;
 }
 private async assertOwnedContent(principal:Principal,contentType:string,contentId:string):Promise<void>{
  this.assertContentType(contentType);
  const found=await this.db.query<{id:string}>(
   `SELECT cr.id FROM zoha.content_records cr
    JOIN zoha.content_types ct ON ct.id=cr.content_type_id
    WHERE cr.id=$1 AND cr.owner_id=$2 AND ct.code=$3 AND cr.deleted=false AND cr.active=true LIMIT 1`,
   [contentId,principal.id,contentType],
  );
  if(!found.rows[0])throw new DomainException('Content.NotFound',HttpStatus.NOT_FOUND);
 }

 async schema(contentType:string){return publishedIndexSchema(this.db,contentType)}

 async options(principal:Principal,code:string,q='',parent='',parentId='',parentScope='',contentType=''){
  const tx=(await this.db.query<{code:string;title:string;allows_personal:boolean;parent_taxonomy_code:string|null}>(`SELECT DISTINCT taxonomy_code AS code,label AS title,COALESCE((config->'runtime'->>'allowsPersonal')::boolean,false) AS allows_personal,parent_taxonomy_code FROM zoha.index_builder_published_fields WHERE taxonomy_code=$1 AND ($2='' OR content_type=$2) LIMIT 1`,[code,contentType])).rows[0];
  if(!tx)throw new DomainException('Index.Taxonomy.NotFound',HttpStatus.NOT_FOUND);
  const n=normalize(q),p=normalize(parent);
  if(tx.parent_taxonomy_code&&!parent)return {taxonomy:tx,items:[]};
  if(parentId&&!/^[0-9]+$/.test(parentId))throw new DomainException('Index.Parent.Invalid',HttpStatus.BAD_REQUEST);
  const sys=await this.db.query(`SELECT id,title,'system'::text AS scope,parent_hint AS parent FROM zoha.index_runtime_terms WHERE taxonomy_code=$1 AND is_active AND ($2='' OR normalized_title LIKE '%'||$2||'%') AND ($3='' OR parent_hint=$3 OR (parent_id IS NULL AND parent_hint IS NULL)) AND ($4='' OR ($5='system' AND (parent_id::text=$4 OR (parent_id IS NULL AND (parent_hint=$3 OR parent_hint IS NULL))))) ORDER BY sort_order,title LIMIT 80`,[code,n,p,parentId,parentScope]);
  const own=await this.db.query(`SELECT id,title,'personal'::text AS scope,NULL::text AS parent FROM zoha.user_index_terms WHERE user_id=$1 AND taxonomy_code=$2 AND is_active AND ($3='' OR normalized_title LIKE '%'||$3||'%') AND ($4='' OR ($5='system' AND parent_system_term_id::text=$4) OR ($5='personal' AND parent_user_term_id::text=$4)) ORDER BY updated_at DESC LIMIT 40`,[principal.apiUserId,code,n,parentId,parentScope]);
  return {taxonomy:tx,items:[...sys.rows,...own.rows]};
 }
 async createPersonal(principal:Principal,code:string,body:{title?:string,contentType?:string,parentSystemTermId?:number|string,parentUserTermId?:number|string}){
  const title=(body.title??'').trim();
  if(title.length<2||title.length>180)throw new DomainException('Index.Personal.Title.Invalid',HttpStatus.BAD_REQUEST);
  const tx=(await this.db.query<{allows_personal:boolean;parent_taxonomy_code:string|null}>(`SELECT COALESCE((config->'runtime'->>'allowsPersonal')::boolean,false) AS allows_personal,parent_taxonomy_code FROM zoha.index_builder_published_fields WHERE taxonomy_code=$1 AND ($2='' OR content_type=$2) LIMIT 1`,[code,body.contentType??''])).rows[0];
  if(!tx)throw new DomainException('Index.Taxonomy.NotFound',HttpStatus.NOT_FOUND);
  if(!tx.allows_personal)throw new DomainException('Index.Personal.Disabled',HttpStatus.BAD_REQUEST);
  if(body.parentUserTermId&&body.parentSystemTermId)throw new DomainException('Index.Parent.Invalid',HttpStatus.BAD_REQUEST);
  if(tx.parent_taxonomy_code){
   if(!body.parentUserTermId&&!body.parentSystemTermId)throw new DomainException('ابتدا آیتم والد را انتخاب کنید.',HttpStatus.BAD_REQUEST);
   const parent=body.parentUserTermId?await this.db.query(`SELECT id FROM zoha.user_index_terms WHERE id=$1 AND user_id=$2 AND taxonomy_code=$3 AND is_active`,[body.parentUserTermId,principal.apiUserId,tx.parent_taxonomy_code]):await this.db.query(`SELECT id FROM zoha.index_runtime_terms WHERE id=$1 AND taxonomy_code=$2 AND is_active`,[body.parentSystemTermId,tx.parent_taxonomy_code]);
   if(!parent.rows[0])throw new DomainException('Index.Personal.Parent.Forbidden',HttpStatus.FORBIDDEN);
  }else if(body.parentUserTermId||body.parentSystemTermId)throw new DomainException('Index.Parent.Invalid',HttpStatus.BAD_REQUEST);
  const n=normalize(title);
  const global=await this.db.query(`SELECT id,title FROM zoha.index_runtime_terms WHERE taxonomy_code=$1 AND normalized_title=$2 AND is_active AND ($3::bigint IS NULL OR parent_id=$3) AND $4::bigint IS NULL LIMIT 1`,[code,n,body.parentSystemTermId??null,body.parentUserTermId??null]);
  if(global.rows[0])return {created:false,useExisting:true,item:{...global.rows[0],scope:'system'}};
  try{
   const r=await this.db.query(`INSERT INTO zoha.user_index_terms(user_id,taxonomy_code,title,normalized_title,parent_system_term_id,parent_user_term_id) VALUES($1,$2,$3,$4,$5,$6) RETURNING id,title`,[principal.apiUserId,code,title,n,body.parentSystemTermId??null,body.parentUserTermId??null]);
   return {created:true,item:{...r.rows[0],scope:'personal'}};
  }catch(error:unknown){
   const r=await this.db.query(`SELECT id,title FROM zoha.user_index_terms WHERE user_id=$1 AND taxonomy_code=$2 AND normalized_title=$3 AND is_active AND parent_system_term_id IS NOT DISTINCT FROM $4::bigint AND parent_user_term_id IS NOT DISTINCT FROM $5::bigint LIMIT 1`,[principal.apiUserId,code,n,body.parentSystemTermId??null,body.parentUserTermId??null]);
   if(r.rows[0])return {created:false,useExisting:true,item:{...r.rows[0],scope:'personal'}};
   throw error;
  }
 }
 async updatePersonal(principal:Principal,id:number,title:string){
  const t=title.trim();if(t.length<2||t.length>180)throw new DomainException('Index.Personal.Title.Invalid',HttpStatus.BAD_REQUEST);
  const r=await this.db.query(`UPDATE zoha.user_index_terms SET title=$3,normalized_title=$4,updated_at=now() WHERE id=$1 AND user_id=$2 AND is_active RETURNING id,title`,[id,principal.apiUserId,t,normalize(t)]);
  if(!r.rows[0])throw new DomainException('Index.Personal.NotFound',HttpStatus.NOT_FOUND);return r.rows[0];
 }
 async deletePersonal(principal:Principal,id:number){const r=await this.db.query(`UPDATE zoha.user_index_terms SET is_active=false,updated_at=now() WHERE id=$1 AND user_id=$2 AND is_active RETURNING id`,[id,principal.apiUserId]);return {ok:Boolean(r.rows[0])};}
 async listPersonal(principal:Principal,code?:string){const r=await this.db.query(`SELECT id,taxonomy_code AS "taxonomyCode",title,is_active AS active,created_at AS "createdAt" FROM zoha.user_index_terms WHERE user_id=$1 AND ($2::text IS NULL OR taxonomy_code=$2) ORDER BY updated_at DESC`,[principal.apiUserId,code??null]);return r.rows;}
 async loadPayload(principal:Principal,contentType:string,contentId:string){
  await this.assertOwnedContent(principal,contentType,contentId);
  const r=await this.db.query(`SELECT payload,schema_version AS "schemaVersion",updated_at AS "updatedAt" FROM zoha.content_index_payloads WHERE content_type=$1 AND content_id=$2 AND user_id=$3`,[contentType,contentId,principal.apiUserId]);
  return r.rows[0]??{payload:{topicAnalyses:[]},schemaVersion:3};
 }
 async savePayload(principal:Principal,contentType:string,contentId:string,payload:unknown){
  await this.assertOwnedContent(principal,contentType,contentId);
  const clean=this.payloadObject(payload);
  const r=await this.db.query(`INSERT INTO zoha.content_index_payloads(content_type,content_id,user_id,payload,schema_version) VALUES($1,$2,$3,$4::jsonb,3) ON CONFLICT(content_type,content_id,user_id) DO UPDATE SET payload=EXCLUDED.payload,schema_version=3,updated_at=now() RETURNING updated_at AS "updatedAt"`,[contentType,contentId,principal.apiUserId,JSON.stringify(clean)]);
  return {ok:true,...r.rows[0]};
 }
}

export async function publishedIndexSchema(db:DatabaseService,contentType:string){
  if(!validTypes.has(contentType))throw new DomainException('Index.ContentType.Invalid',HttpStatus.BAD_REQUEST);
  const relationsPromise=db.query(`SELECT code,source_title AS source,target_title AS target,cardinality,rule_text AS rule,note FROM zoha.index_runtime_relations ORDER BY code`);
  const formFields=await db.query<{
   id:string;field_key:string;label:string;help_text:string|null;placeholder:string|null;input_kind:string;value_kind:string;
   required:boolean;search_enabled:boolean;index_enabled:boolean;display_order:number;width:number;config:Record<string,unknown>;validation:Record<string,unknown>;
   parent_key:string|null;parent_taxonomy_code:string|null;taxonomy_code:string|null;legacy_title:string|null;is_multi:boolean|null;allows_personal:boolean|null;
  }>(`SELECT ff.id,ff.field_key,ff.label,ff.help_text,ff.placeholder,ff.input_kind,ff.value_kind,ff.required,ff.search_enabled,ff.index_enabled,
      ff.display_order,ff.width,ff.config,ff.validation,ff.config->'runtime'->>'taxonomyCode' AS taxonomy_code,NULL::text AS legacy_title,false AS is_multi,COALESCE((ff.config->'runtime'->>'allowsPersonal')::boolean,false) AS allows_personal,parent.field_key AS parent_key,parent.config->'runtime'->>'taxonomyCode' AS parent_taxonomy_code
    FROM zoha.content_types ct
    JOIN zoha.content_type_index_forms map ON map.content_type_id=ct.id AND map.is_primary=true AND map.active=true AND map.deleted=false
    JOIN zoha.index_forms f ON f.id=map.index_form_id AND f.active=true AND f.deleted=false AND f.is_active=true
    JOIN zoha.index_form_versions v ON v.index_form_id=f.id AND v.version=f.active_version AND v.active=true AND v.deleted=false
    JOIN zoha.index_form_fields ff ON ff.version_id=v.id AND ff.active=true AND ff.deleted=false
    LEFT JOIN zoha.index_form_fields parent ON parent.version_id=v.id AND parent.field_key=ff.config->'hierarchy'->>'parentKey' AND parent.active AND NOT parent.deleted
    WHERE ct.code=$1 AND ct.active=true AND ct.deleted=false
    ORDER BY ff.display_order,ff.id`,[contentType]);
  const relations=await relationsPromise;
  if(formFields.rows.length){
   const ids=formFields.rows.map(row=>row.id);
   const optionRows=ids.length?await db.query<{field_id:string;value_key:string;label:string;sort_order:number}>(
    `SELECT field_id,value_key,label,sort_order FROM zoha.index_form_options WHERE field_id=ANY($1::uuid[]) AND active=true AND deleted=false AND is_active=true ORDER BY field_id,sort_order,id`,[ids],
   ):({rows:[]} as {rows:{field_id:string;value_key:string;label:string;sort_order:number}[]});
   const options=new Map<string,{value:string;label:string;sortOrder:number}[]>();
   for(const row of optionRows.rows){const list=options.get(row.field_id)??[];list.push({value:row.value_key,label:row.label,sortOrder:row.sort_order});options.set(row.field_id,list);}
    const fields=formFields.rows.map(row=>{
    const runtime=(row.config?.runtime&&typeof row.config.runtime==='object'&&!Array.isArray(row.config.runtime)?row.config.runtime:{}) as Record<string,unknown>;
    const taxonomyCode=row.taxonomy_code??(typeof runtime.taxonomyCode==='string'?runtime.taxonomyCode:null);
    const manualOptions=options.get(row.id)??[];
    const sourceMode=typeof runtime.sourceMode==='string'?runtime.sourceMode:(taxonomyCode?'runtime_taxonomy':manualOptions.length?'manual':'none');
    return {
     code:taxonomyCode??row.field_key,key:row.field_key,title:row.label,legacyTitle:row.legacy_title,type:row.input_kind,valueKind:row.value_kind,
     multi:['multiselect','checkbox','tags'].includes(row.input_kind)||Boolean(row.is_multi),allowsPersonal:Boolean(row.allows_personal),sortOrder:row.display_order,
     required:row.required,searchEnabled:row.search_enabled,indexEnabled:row.index_enabled,taxonomyCode,sourceMode,
     parentKey:row.parent_key,parentTaxonomyCode:row.parent_taxonomy_code,
     settings:{helpText:row.help_text??'',placeholder:row.placeholder??'',width:row.width},config:row.config??{},validation:row.validation??{},options:manualOptions,
    };
   });
   return {contentType,version:6,builder:'index-builder-v6',fields,relations:relations.rows,topicAnalysis:{fields:['IDX-001','IDX-003','IDX-002','IDX-004'],label:'نمایه‌ها و زیرشاخه‌های تعریف‌شده در نمایه‌ساز'}};
  }
  return {contentType,version:6,builder:'index-builder-v6',fields:[],relations:relations.rows,topicAnalysis:{fields:[],label:''}};
 }
