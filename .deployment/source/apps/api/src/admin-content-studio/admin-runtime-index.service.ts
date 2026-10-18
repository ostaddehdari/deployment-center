import { publishedIndexSchema } from '../index-runtime/index-runtime.service';
import { HttpStatus, Injectable } from '@nestjs/common';
import { DatabaseService } from '../common/database/database.service';
import { DomainException } from '../common/http/domain.exception';
import type { Principal } from '../common/types';
import type { CreateRuntimeTermDTO, ReorderRuntimeFieldsDTO, UpdateRuntimePostTypeFieldDTO, UpdateRuntimeTaxonomyDTO, UpdateRuntimeTermDTO } from './admin-runtime-index.dto';

const runtimeTypes=['mold','full_sermon','supporting'] as const;
const runtimeTypeSet=new Set<string>(runtimeTypes);
const fixedFieldTypes:Record<string,string>={'IDX-001':'taxonomy','IDX-002':'taxonomy','IDX-003':'taxonomy','IDX-004':'textarea'};
const normalize=(v:string)=>v.normalize('NFKC').replace(/[يى]/g,'ی').replace(/ك/g,'ک').replace(/[\u064b-\u065f\u0670]/g,'').replace(/\u200c/g,' ').replace(/\s+/g,' ').trim().toLocaleLowerCase('fa-IR');

interface RuntimeTaxonomyRow {
  code:string;title:string;legacy_title:string|null;field_type:string;is_multi:boolean;allows_personal:boolean;metadata:Record<string,unknown>;is_active:boolean;
  active_term_count:string;total_term_count:string;sort_order:number|null;is_required:boolean|null;settings:Record<string,unknown>|null;
}
interface RuntimeTermRow {id:string;title:string;normalized_title:string;parent_id:string|null;parent_hint:string|null;metadata:Record<string,unknown>;sort_order:number;is_active:boolean;created_at:Date;}
interface RuntimeTypeRow {code:string;title:string;description:string|null;settings:Record<string,unknown>;field_count:string;}

@Injectable()
export class AdminRuntimeIndexService {
  constructor(private readonly db:DatabaseService){}

  private admin(principal:Principal|null):Principal{
    if(!principal)throw new DomainException('Common.Unauthorized',HttpStatus.UNAUTHORIZED);
    if(!principal.roles.includes('system_admin'))throw new DomainException('Common.Forbidden',HttpStatus.FORBIDDEN);
    return principal;
  }
  private contentType(code:string):string{
    if(!runtimeTypeSet.has(code))throw new DomainException('Index.ContentType.Invalid',HttpStatus.BAD_REQUEST);
    return code;
  }
  private async taxonomy(code:string):Promise<void>{
    const r=await this.db.query<{code:string}>(`SELECT code FROM zoha.index_runtime_taxonomies WHERE code=$1 LIMIT 1`,[code]);
    if(!r.rows[0])throw new DomainException('Index.Taxonomy.NotFound',HttpStatus.NOT_FOUND);
  }

  private async parentCode(code:string,contentType=''):Promise<string|null>{
    const parent=(await this.db.query<{code:string}>(`SELECT parent.config->'runtime'->>'taxonomyCode' AS code FROM zoha.index_form_fields child JOIN zoha.index_form_versions v ON v.id=child.version_id JOIN zoha.index_forms f ON f.id=v.index_form_id AND f.draft_version=v.version LEFT JOIN zoha.index_form_fields parent ON parent.version_id=child.version_id AND parent.field_key=child.config->'hierarchy'->>'parentKey' AND parent.active AND NOT parent.deleted WHERE child.config->'runtime'->>'taxonomyCode'=$1 AND ($2='' OR f.id IN(SELECT m.index_form_id FROM zoha.content_type_index_forms m JOIN zoha.content_types ct ON ct.id=m.content_type_id WHERE ct.code=$2 AND m.is_primary AND m.active AND NOT m.deleted)) AND child.active AND NOT child.deleted AND f.active AND NOT f.deleted ORDER BY child.updated_at DESC LIMIT 1`,[code,contentType])).rows[0];
    return parent?.code??null;
  }
  private async termParent(code:string,id?:string,hint?:string):Promise<{id:string|null;hint:string|null}>{
    const parentCode=await this.parentCode(code);
    if(!parentCode){if(id)throw new DomainException('این نمایه والد ندارد.',HttpStatus.BAD_REQUEST);return {id:null,hint:null}}
    if(!id||!/^[0-9]+$/.test(id))throw new DomainException('آیتم والد را از فهرست انتخاب کنید.',HttpStatus.BAD_REQUEST);
    const parent=(await this.db.query<{id:string;normalized_title:string}>(`SELECT id::text,normalized_title FROM zoha.index_runtime_terms WHERE id=$1 AND taxonomy_code=$2 AND is_active`,[id,parentCode])).rows[0];
    if(!parent)throw new DomainException('آیتم والد معتبر نیست.',HttpStatus.BAD_REQUEST);
    return {id:parent.id,hint:parent.normalized_title};
  }
  async overview(principalInput:Principal|null,contentTypeInput?:string):Promise<Record<string,unknown>>{
    this.admin(principalInput);
    const contentType=this.contentType(contentTypeInput&&runtimeTypeSet.has(contentTypeInput)?contentTypeInput:'mold');
    const [types,taxonomies,relations]=await Promise.all([
      this.db.query<RuntimeTypeRow>(`
        SELECT ct.code,ct.title,ct.description,ct.settings,count(p.taxonomy_code)::text AS field_count
        FROM zoha.content_types ct
        LEFT JOIN zoha.index_runtime_post_type_fields p ON p.post_type_code=ct.code
        WHERE ct.code=ANY($1::text[]) AND ct.deleted=false
        GROUP BY ct.id
        ORDER BY array_position($1::text[],ct.code)`,[runtimeTypes]),
      this.db.query<RuntimeTaxonomyRow>(`
        SELECT t.code,t.title,t.legacy_title,t.field_type,t.is_multi,t.allows_personal,t.metadata,t.is_active,
               count(term.id) FILTER (WHERE term.is_active)::text AS active_term_count,
               count(term.id)::text AS total_term_count,
               p.sort_order,p.is_required,p.settings
        FROM zoha.index_runtime_taxonomies t
        LEFT JOIN zoha.index_runtime_terms term ON term.taxonomy_code=t.code
        LEFT JOIN zoha.index_runtime_post_type_fields p ON p.taxonomy_code=t.code AND p.post_type_code=$1
        GROUP BY t.code,p.sort_order,p.is_required,p.settings
        ORDER BY CASE WHEN p.sort_order IS NULL THEN 1 ELSE 0 END,COALESCE(p.sort_order,999999),t.code`,[contentType]),
      this.db.query(`SELECT code,source_title AS source,target_title AS target,cardinality,rule_text AS rule,note FROM zoha.index_runtime_relations ORDER BY code`),
    ]);
    const Taxonomies=taxonomies.rows.map(row=>({
      Code:row.code,Title:row.title,LegacyTitle:row.legacy_title,FieldType:row.field_type,IsMulti:row.is_multi,AllowsPersonal:row.allows_personal,
      Metadata:row.metadata,IsActive:row.is_active,ActiveTermCount:Number(row.active_term_count),TotalTermCount:Number(row.total_term_count),
      Assigned:row.sort_order!==null,SortOrder:row.sort_order,IsRequired:Boolean(row.is_required),Settings:row.settings??{},ParentTaxonomyCode:String(row.metadata?.parentTaxonomyCode??'')||null,
    }));
    const ContentTypes=types.rows.map(row=>({Code:row.code,Title:row.title,Description:row.description,Settings:row.settings,FieldCount:Number(row.field_count),RuntimeEnabled:true}));
    return {SelectedContentType:contentType,ContentTypes,Taxonomies,Fields:Taxonomies.filter(v=>v.Assigned),Relations:relations.rows};
  }

  async previewSchema(principalInput:Principal|null,contentTypeInput:string):Promise<Record<string,unknown>>{
    this.admin(principalInput);
    const contentType=this.contentType(contentTypeInput);
    return publishedIndexSchema(this.db,contentType);
  }

  async previewOptions(principalInput:Principal|null,code:string,q='',parent='',parentId='',parentScope='',contentType=''):Promise<Record<string,unknown>>{
    this.admin(principalInput);
    const tx=(await this.db.query<{code:string;title:string;allows_personal:boolean}>(`SELECT code,title,allows_personal FROM zoha.index_runtime_taxonomies WHERE code=$1 AND is_active`,[code])).rows[0];
    if(!tx)throw new DomainException('Index.Taxonomy.NotFound',HttpStatus.NOT_FOUND);
    const n=normalize(q),p=normalize(parent);
    if(await this.parentCode(code,contentType)&&!parent)return {taxonomy:tx,items:[]};
    if(parentId&&!/^[0-9]+$/.test(parentId))throw new DomainException('Index.Parent.Invalid',HttpStatus.BAD_REQUEST);
    const items=await this.db.query(`SELECT id,title,'system'::text AS scope,parent_hint AS parent FROM zoha.index_runtime_terms
      WHERE taxonomy_code=$1 AND is_active AND ($2='' OR normalized_title LIKE '%'||$2||'%') AND ($3='' OR parent_hint=$3 OR (parent_id IS NULL AND parent_hint IS NULL)) AND ($4='' OR ($5='system' AND (parent_id::text=$4 OR (parent_id IS NULL AND (parent_hint=$3 OR parent_hint IS NULL)))))
      ORDER BY sort_order,title LIMIT 80`,[code,n,p,parentId,parentScope]);
    return {taxonomy:tx,items:items.rows};
  }

  async assignField(principalInput:Principal|null,contentTypeInput:string,taxonomyCode:string):Promise<Record<string,unknown>>{
    this.admin(principalInput);
    throw new DomainException('تعریف نمایه فقط از نمایه‌ساز و با انتشار نسخه انجام می‌شود.',HttpStatus.CONFLICT);
  }

  async updateField(principalInput:Principal|null,contentTypeInput:string,taxonomyCode:string,body:UpdateRuntimePostTypeFieldDTO):Promise<Record<string,unknown>>{
    this.admin(principalInput);
    throw new DomainException('تعریف نمایه فقط از نمایه‌ساز و با انتشار نسخه انجام می‌شود.',HttpStatus.CONFLICT);
  }

  async removeField(principalInput:Principal|null,contentTypeInput:string,taxonomyCode:string):Promise<Record<string,unknown>>{
    this.admin(principalInput);
    throw new DomainException('تعریف نمایه فقط از نمایه‌ساز و با انتشار نسخه انجام می‌شود.',HttpStatus.CONFLICT);
  }

  async reorder(principalInput:Principal|null,contentTypeInput:string,body:ReorderRuntimeFieldsDTO):Promise<Record<string,unknown>>{
    this.admin(principalInput);
    throw new DomainException('تعریف نمایه فقط از نمایه‌ساز و با انتشار نسخه انجام می‌شود.',HttpStatus.CONFLICT);
  }

  async updateTaxonomy(principalInput:Principal|null,code:string,body:UpdateRuntimeTaxonomyDTO):Promise<Record<string,unknown>>{
    this.admin(principalInput);
    throw new DomainException('تعریف نمایه فقط از نمایه‌ساز و با انتشار نسخه انجام می‌شود.',HttpStatus.CONFLICT);
  }

  async terms(principalInput:Principal|null,code:string,query='',pageInput='1',pageSizeInput='50',includeInactiveInput='false'):Promise<Record<string,unknown>>{
    this.admin(principalInput);await this.taxonomy(code);
    const page=Math.max(1,Number(pageInput)||1),pageSize=Math.min(100,Math.max(10,Number(pageSizeInput)||50)),includeInactive=includeInactiveInput==='true';
    const q=normalize(query);const offset=(page-1)*pageSize;
    const [items,total]=await Promise.all([
      this.db.query<RuntimeTermRow>(`SELECT id::text,title,normalized_title,parent_id::text,parent_hint,metadata,sort_order,is_active,created_at FROM zoha.index_runtime_terms
        WHERE taxonomy_code=$1 AND ($2='' OR normalized_title LIKE '%'||$2||'%') AND ($3::boolean OR is_active)
        ORDER BY is_active DESC,sort_order,title LIMIT $4 OFFSET $5`,[code,q,includeInactive,pageSize,offset]),
      this.db.query<{value:string}>(`SELECT count(*)::text AS value FROM zoha.index_runtime_terms WHERE taxonomy_code=$1 AND ($2='' OR normalized_title LIKE '%'||$2||'%') AND ($3::boolean OR is_active)`,[code,q,includeInactive]),
    ]);
    return {TaxonomyCode:code,ParentTaxonomyCode:await this.parentCode(code),Items:items.rows.map(row=>({Id:row.id,Title:row.title,ParentId:row.parent_id,ParentHint:row.parent_hint,Metadata:row.metadata,SortOrder:row.sort_order,IsActive:row.is_active,CreatedAt:row.created_at})),Total:Number(total.rows[0]?.value??0),Page:page,PageSize:pageSize};
  }

  async createTerm(principalInput:Principal|null,code:string,body:CreateRuntimeTermDTO):Promise<Record<string,unknown>>{
    this.admin(principalInput);await this.taxonomy(code);
    const title=body.Title.trim();if(title.length<1)throw new DomainException('Index.Term.Title.Invalid',HttpStatus.BAD_REQUEST);
    const normalized=normalize(title),parent=await this.termParent(code,body.ParentId,body.ParentHint),parentHint=parent.hint;
    const existing=await this.db.query<{id:string;is_active:boolean}>(`SELECT id::text,is_active FROM zoha.index_runtime_terms WHERE taxonomy_code=$1 AND normalized_title=$2 AND parent_id IS NOT DISTINCT FROM $3::bigint ORDER BY is_active DESC LIMIT 1`,[code,normalized,parent.id]);
    if(existing.rows[0]){
      if(existing.rows[0].is_active)throw new DomainException('Index.Term.Exists',HttpStatus.CONFLICT);
      const revived=await this.db.query(`UPDATE zoha.index_runtime_terms SET title=$2,normalized_title=$3,parent_hint=$4,sort_order=$5,metadata=$6::jsonb,parent_id=$7,is_active=true WHERE id=$1 RETURNING id::text AS "Id",title AS "Title",parent_hint AS "ParentHint",parent_id::text AS "ParentId",sort_order AS "SortOrder",is_active AS "IsActive"`,[existing.rows[0].id,title,normalized,parentHint,body.SortOrder??0,JSON.stringify(body.Metadata??{}),parent.id]);
      return revived.rows[0]??{ok:true};
    }
    const r=await this.db.query(`INSERT INTO zoha.index_runtime_terms(taxonomy_code,title,normalized_title,parent_hint,metadata,sort_order,parent_id,is_active) VALUES($1,$2,$3,$4,$5::jsonb,$6,$7,true) RETURNING id::text AS "Id",title AS "Title",parent_hint AS "ParentHint",parent_id::text AS "ParentId",sort_order AS "SortOrder",is_active AS "IsActive"`,[code,title,normalized,parentHint,JSON.stringify(body.Metadata??{}),body.SortOrder??0,parent.id]);
    return r.rows[0]??{ok:true};
  }

  async updateTerm(principalInput:Principal|null,code:string,id:string,body:UpdateRuntimeTermDTO):Promise<Record<string,unknown>>{
    this.admin(principalInput);await this.taxonomy(code);
    const current=await this.db.query<RuntimeTermRow>(`SELECT id::text,title,normalized_title,parent_id::text,parent_hint,metadata,sort_order,is_active,created_at FROM zoha.index_runtime_terms WHERE id=$1 AND taxonomy_code=$2`,[id,code]);
    const row=current.rows[0];if(!row)throw new DomainException('Index.Term.NotFound',HttpStatus.NOT_FOUND);
    const title=body.Title===undefined?row.title:body.Title.trim();if(!title)throw new DomainException('Index.Term.Title.Invalid',HttpStatus.BAD_REQUEST);
    const normalized=normalize(title);const parent=await this.termParent(code,body.ParentId??row.parent_id??undefined,body.ParentHint??row.parent_hint??undefined),parentHint=parent.hint;
    const duplicate=await this.db.query<{id:string}>(`SELECT id::text FROM zoha.index_runtime_terms WHERE taxonomy_code=$1 AND normalized_title=$2 AND parent_id IS NOT DISTINCT FROM $3::bigint AND id<>$4 AND is_active LIMIT 1`,[code,normalized,parent.id,id]);
    if(duplicate.rows[0])throw new DomainException('Index.Term.Exists',HttpStatus.CONFLICT);
    const r=await this.db.query(`UPDATE zoha.index_runtime_terms SET title=$3,normalized_title=$4,parent_hint=$5,sort_order=$6,metadata=$7::jsonb,is_active=$8,parent_id=$9 WHERE id=$1 AND taxonomy_code=$2 RETURNING id::text AS "Id",title AS "Title",parent_hint AS "ParentHint",parent_id::text AS "ParentId",sort_order AS "SortOrder",is_active AS "IsActive"`,[id,code,title,normalized,parentHint,body.SortOrder??row.sort_order,JSON.stringify(body.Metadata??row.metadata),body.IsActive??row.is_active,parent.id]);
    return r.rows[0]??{ok:true};
  }

  async deleteTerm(principalInput:Principal|null,code:string,id:string):Promise<Record<string,unknown>>{
    this.admin(principalInput);await this.taxonomy(code);
    const r=await this.db.query(`UPDATE zoha.index_runtime_terms SET is_active=false WHERE id=$1 AND taxonomy_code=$2 AND is_active RETURNING id`,[id,code]);
    return {ok:Boolean(r.rows[0])};
  }
}
