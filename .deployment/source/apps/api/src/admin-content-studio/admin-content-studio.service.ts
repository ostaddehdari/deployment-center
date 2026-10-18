import { randomUUID } from 'node:crypto';
import { hierarchyOrder } from './index-hierarchy';
import { HttpStatus, Injectable } from '@nestjs/common';
import type { PoolClient } from 'pg';
import { DatabaseService } from '../common/database/database.service';
import { DomainException } from '../common/http/domain.exception';
import type { Principal } from '../common/types';
import type { AssignIndexFormDTO, CreateContentTypeDTO, CreateIndexFormDTO, ReorderIndexFieldsDTO, SaveIndexFieldDTO, UpdateContentTypeDTO, UpdateIndexFormDTO } from './admin-content-studio.dto';

interface ContentTypeRow {
  id:string;code:string;title:string;description:string|null;kind:string;system_defined:boolean;is_active:boolean;active_version:number;
  settings:Record<string,unknown>;content_count:string;index_form_id:string|null;index_form_title:string|null;
}
interface IndexFormRow {id:string;code:string;title:string;description:string|null;active_version:number;draft_version:number;is_system:boolean;is_active:boolean;field_count:string;assigned_count:string;updated_at:Date;}
interface IndexVersionRow {id:string;version:number;immutable:boolean;published_at:Date|null;}
interface IndexFieldRow {id:string;field_key:string;label:string;help_text:string|null;placeholder:string|null;input_kind:string;value_kind:string;required:boolean;search_enabled:boolean;index_enabled:boolean;display_order:number;width:number;config:Record<string,unknown>;validation:Record<string,unknown>;}
interface OptionRow {id:string;field_id:string;value_key:string;label:string;sort_order:number;}

const FIELD_CATALOG=[
 {Group:'پایه',Kind:'text',Title:'متن تک‌خطی',ValueKind:'string'},{Group:'پایه',Kind:'textarea',Title:'متن چندخطی',ValueKind:'string'},
 {Group:'پایه',Kind:'richtext',Title:'متن غنی',ValueKind:'string'},{Group:'پایه',Kind:'number',Title:'عدد',ValueKind:'number'},
 {Group:'پایه',Kind:'boolean',Title:'بله / خیر',ValueKind:'boolean'},{Group:'پایه',Kind:'email',Title:'ایمیل',ValueKind:'string'},
 {Group:'پایه',Kind:'phone',Title:'تلفن',ValueKind:'string'},{Group:'پایه',Kind:'url',Title:'نشانی وب',ValueKind:'string'},
 {Group:'پایه',Kind:'date',Title:'تاریخ',ValueKind:'date'},{Group:'پایه',Kind:'time',Title:'زمان',ValueKind:'string'},
 {Group:'پایه',Kind:'datetime',Title:'تاریخ و زمان',ValueKind:'date'},{Group:'پایه',Kind:'password',Title:'رمز',ValueKind:'string'},
 {Group:'انتخابی',Kind:'select',Title:'فهرست کشویی',ValueKind:'string'},{Group:'انتخابی',Kind:'searchable_select',Title:'فهرست جستجوپذیر',ValueKind:'string'},{Group:'انتخابی',Kind:'multiselect',Title:'انتخاب چندگانه',ValueKind:'array'},
 {Group:'انتخابی',Kind:'radio',Title:'گزینه رادیویی',ValueKind:'string'},{Group:'انتخابی',Kind:'checkbox',Title:'چک‌باکس‌ها',ValueKind:'array'},
 {Group:'انتخابی',Kind:'tags',Title:'برچسب‌ها',ValueKind:'array'},{Group:'انتخابی',Kind:'consent',Title:'تأیید / رضایت',ValueKind:'boolean'},
 {Group:'پیشرفته',Kind:'file',Title:'بارگذاری فایل',ValueKind:'reference'},{Group:'پیشرفته',Kind:'reference',Title:'ارجاع',ValueKind:'reference'},
 {Group:'پیشرفته',Kind:'relation',Title:'رابطه با محتوا',ValueKind:'reference'},{Group:'پیشرفته',Kind:'repeater',Title:'تکرارشونده',ValueKind:'array'},
 {Group:'پیشرفته',Kind:'group',Title:'گروه فیلد',ValueKind:'object'},{Group:'پیشرفته',Kind:'duration',Title:'مدت زمان',ValueKind:'number'},
 {Group:'پیشرفته',Kind:'color',Title:'رنگ',ValueKind:'string'},{Group:'پیشرفته',Kind:'range',Title:'بازه / اسلایدر',ValueKind:'number'},
 {Group:'پیشرفته',Kind:'name',Title:'نام شخص',ValueKind:'object'},{Group:'پیشرفته',Kind:'address',Title:'نشانی',ValueKind:'object'},
 {Group:'چیدمان',Kind:'section',Title:'بخش',ValueKind:'object'},{Group:'چیدمان',Kind:'html',Title:'HTML توضیحی',ValueKind:'string'},
 {Group:'چیدمان',Kind:'page',Title:'شکست صفحه',ValueKind:'object'},{Group:'چیدمان',Kind:'hidden',Title:'فیلد مخفی',ValueKind:'string'},
 {Group:'انتخابی',Kind:'image_choice',Title:'انتخاب تصویری',ValueKind:'string'},
 {Group:'پیشرفته',Kind:'list',Title:'جدول تکرارشونده',ValueKind:'array'},{Group:'پیشرفته',Kind:'rating',Title:'امتیازدهی',ValueKind:'number'},
 {Group:'پیشرفته',Kind:'signature',Title:'امضای ترسیمی',ValueKind:'string'},{Group:'پیشرفته',Kind:'calculation',Title:'محاسبه فرمول',ValueKind:'number'},
 {Group:'قیمت‌گذاری',Kind:'product',Title:'محصول / خدمت',ValueKind:'number'},{Group:'قیمت‌گذاری',Kind:'quantity',Title:'تعداد',ValueKind:'number'},
 {Group:'قیمت‌گذاری',Kind:'price_option',Title:'گزینه قیمت',ValueKind:'string'},{Group:'قیمت‌گذاری',Kind:'shipping',Title:'هزینه ارسال',ValueKind:'boolean'},
 {Group:'قیمت‌گذاری',Kind:'total',Title:'مبلغ کل',ValueKind:'number'},
] as const;

@Injectable()
export class AdminContentStudioService {
  constructor(private readonly db:DatabaseService){}

  private admin(principal:Principal|null):Principal{
    if(!principal)throw new DomainException('Common.Unauthorized',HttpStatus.UNAUTHORIZED);
    if(!principal.roles.includes('system_admin'))throw new DomainException('Common.Forbidden',HttpStatus.FORBIDDEN);
    return principal;
  }

  async overview(principalInput:Principal|null):Promise<Record<string,unknown>>{
    this.admin(principalInput);
    const [ContentTypes,IndexForms]=await Promise.all([this.contentTypes(principalInput),this.indexForms(principalInput)]);
    return {ContentTypes,IndexForms,FieldCatalog:FIELD_CATALOG};
  }

  async contentTypes(principalInput:Principal|null):Promise<Record<string,unknown>[]>{
    this.admin(principalInput);
    const result=await this.db.query<ContentTypeRow>(`
      SELECT ct.id,ct.code,ct.title,ct.description,ct.kind,ct.system_defined,ct.is_active,ct.active_version,ct.settings,
             count(DISTINCT cr.id)::text AS content_count,
             cif.index_form_id,ifm.title AS index_form_title
      FROM zoha.content_types ct
      LEFT JOIN zoha.content_records cr ON cr.content_type_id=ct.id AND cr.deleted=false AND cr.deleted_at IS NULL
      LEFT JOIN zoha.content_type_index_forms cif ON cif.content_type_id=ct.id AND cif.is_primary=true AND cif.deleted=false AND cif.active=true
      LEFT JOIN zoha.index_forms ifm ON ifm.id=cif.index_form_id AND ifm.deleted=false AND ifm.active=true
      WHERE ct.deleted=false AND ct.active=true
      GROUP BY ct.id,cif.index_form_id,ifm.title
      ORDER BY ct.system_defined DESC,ct.created_at,ct.title`);
    return result.rows.map(row=>({
      Id:row.id,Code:row.code,Title:row.title,Description:row.description,Kind:row.kind,SystemDefined:row.system_defined,
      IsActive:row.is_active,ActiveVersion:row.active_version,Settings:row.settings,ContentCount:Number(row.content_count),
      IndexFormId:row.index_form_id,IndexFormTitle:row.index_form_title,
    }));
  }

  async createContentType(principalInput:Principal|null,body:CreateContentTypeDTO):Promise<Record<string,unknown>>{
    const principal=this.admin(principalInput);
    const code=body.Code.trim().toLowerCase();
    const exists=await this.db.query<{id:string}>(`SELECT id FROM zoha.content_types WHERE code=$1 AND deleted=false LIMIT 1`,[code]);
    if(exists.rows[0])throw new DomainException('Content.Type.CodeExists',HttpStatus.CONFLICT);
    const row=await this.db.transaction(async(client)=>{
      const inserted=await client.query<{id:string}>(`
        INSERT INTO zoha.content_types(code,title,description,kind,system_defined,active_version,is_active,settings,created_by,updated_by,active,deleted)
        VALUES($1,$2,$3,'user_defined',false,1,true,$4::jsonb,$5,$5,true,false) RETURNING id`,
        [code,body.Title.trim(),body.Description?.trim()||null,JSON.stringify({icon:body.Icon??'content',color:body.Color??'#129986',defaultVisibility:body.DefaultVisibility??'private'}),principal.id]);
      const id=inserted.rows[0]?.id;
      if(!id)throw new DomainException('Content.Type.CreateFailed',HttpStatus.INTERNAL_SERVER_ERROR);
      await client.query(`INSERT INTO zoha.content_type_versions(content_type_id,version,form_schema,validation_rules,publication_rules,published_at,immutable,created_by,updated_by,active,deleted)
                          VALUES($1,1,'{"layout":"grid","source":"admin-content-studio"}'::jsonb,'{}','{}',now(),false,$2,$2,true,false)`,[id,principal.id]);
      if(body.IndexFormId)await this.assignIndexFormTx(client,principal.id,id,body.IndexFormId);
      return id;
    });
    return this.getContentType(principal,row);
  }

  async updateContentType(principalInput:Principal|null,id:string,body:UpdateContentTypeDTO):Promise<Record<string,unknown>>{
    const principal=this.admin(principalInput);
    const current=await this.db.query<{settings:Record<string,unknown>;system_defined:boolean}>(`SELECT settings,system_defined FROM zoha.content_types WHERE id=$1 AND deleted=false LIMIT 1`,[id]);
    const row=current.rows[0];
    if(!row)throw new DomainException('Content.Type.NotFound',HttpStatus.NOT_FOUND);
    const settings={...row.settings};
    if(body.Icon!==undefined)settings.icon=body.Icon;
    if(body.Color!==undefined)settings.color=body.Color;
    if(body.DefaultVisibility!==undefined)settings.defaultVisibility=body.DefaultVisibility;
    await this.db.transaction(async client=>{
      await client.query(`UPDATE zoha.content_types SET title=COALESCE($1,title),description=COALESCE($2,description),is_active=COALESCE($3,is_active),settings=$4::jsonb,updated_by=$5,updated_at=now(),update_at=now() WHERE id=$6`,
        [body.Title?.trim()||null,body.Description===undefined?null:body.Description.trim(),body.IsActive??null,JSON.stringify(settings),principal.id,id]);
      if(body.IndexFormId)await this.assignIndexFormTx(client,principal.id,id,body.IndexFormId);
    });
    return this.getContentType(principal,id);
  }

  private async getContentType(principalInput:Principal|null,id:string):Promise<Record<string,unknown>>{
    const rows=await this.contentTypes(principalInput);
    const found=rows.find(row=>row.Id===id);
    if(!found)throw new DomainException('Content.Type.NotFound',HttpStatus.NOT_FOUND);
    return found;
  }

  async indexForms(principalInput:Principal|null):Promise<Record<string,unknown>[]>{
    this.admin(principalInput);
    const result=await this.db.query<IndexFormRow>(`
      SELECT f.id,f.code,f.title,f.description,f.active_version,f.draft_version,f.is_system,f.is_active,f.updated_at,
             count(DISTINCT fld.id)::text AS field_count,count(DISTINCT map.content_type_id)::text AS assigned_count
      FROM zoha.index_forms f
      LEFT JOIN zoha.index_form_versions v ON v.index_form_id=f.id AND v.version=f.draft_version AND v.deleted=false AND v.active=true
      LEFT JOIN zoha.index_form_fields fld ON fld.version_id=v.id AND fld.deleted=false AND fld.active=true
      LEFT JOIN zoha.content_type_index_forms map ON map.index_form_id=f.id AND map.deleted=false AND map.active=true
      WHERE f.deleted=false AND f.active=true
      GROUP BY f.id ORDER BY f.is_system DESC,f.updated_at DESC,f.title`);
    return result.rows.map(row=>({Id:row.id,Code:row.code,Title:row.title,Description:row.description,ActiveVersion:row.active_version,DraftVersion:row.draft_version,SystemDefined:row.is_system,IsActive:row.is_active,FieldCount:Number(row.field_count),AssignedCount:Number(row.assigned_count),UpdatedAt:row.updated_at.toISOString()}));
  }

  async getIndexForm(principalInput:Principal|null,id:string):Promise<Record<string,unknown>>{
    this.admin(principalInput);
    const form=await this.db.query<IndexFormRow>(`SELECT f.*,0::text AS field_count,0::text AS assigned_count FROM zoha.index_forms f WHERE f.id=$1 AND f.deleted=false AND f.active=true LIMIT 1`,[id]);
    const f=form.rows[0];
    if(!f)throw new DomainException('IndexForm.NotFound',HttpStatus.NOT_FOUND);
    const version=await this.db.query<IndexVersionRow>(`SELECT id,version,immutable,published_at FROM zoha.index_form_versions WHERE index_form_id=$1 AND version=$2 AND deleted=false AND active=true LIMIT 1`,[id,f.draft_version]);
    const v=version.rows[0];
    if(!v)throw new DomainException('IndexForm.Draft.NotFound',HttpStatus.NOT_FOUND);
    const fields=await this.db.query<IndexFieldRow>(`SELECT id,field_key,label,help_text,placeholder,input_kind,value_kind,required,search_enabled,index_enabled,display_order,width,config,validation FROM zoha.index_form_fields WHERE version_id=$1 AND deleted=false AND active=true ORDER BY display_order,id`,[v.id]);
    const fieldIds=fields.rows.map(row=>row.id);
    const options=fieldIds.length?await this.db.query<OptionRow>(`SELECT id,field_id,value_key,label,sort_order FROM zoha.index_form_options WHERE field_id=ANY($1::uuid[]) AND deleted=false AND active=true AND is_active=true ORDER BY field_id,sort_order,id`,[fieldIds]):{rows:[] as OptionRow[]};
    const optionsByField=new Map<string,OptionRow[]>();
    for(const option of options.rows){const current=optionsByField.get(option.field_id)??[];current.push(option);optionsByField.set(option.field_id,current);}
    const assigned=await this.db.query<{id:string;code:string;title:string}>(`SELECT ct.id,ct.code,ct.title FROM zoha.content_type_index_forms map JOIN zoha.content_types ct ON ct.id=map.content_type_id WHERE map.index_form_id=$1 AND map.deleted=false AND map.active=true AND ct.deleted=false ORDER BY ct.title`,[id]);
    return {
      Id:f.id,Code:f.code,Title:f.title,Description:f.description,ActiveVersion:f.active_version,DraftVersion:f.draft_version,SystemDefined:f.is_system,IsActive:f.is_active,
      AssignedContentTypes:assigned.rows.map(row=>({Id:row.id,Code:row.code,Title:row.title})),
      Fields:fields.rows.map(row=>({Id:row.id,Key:row.field_key,Label:row.label,HelpText:row.help_text,Placeholder:row.placeholder,InputKind:row.input_kind,ValueKind:row.value_kind,Required:row.required,SearchEnabled:row.search_enabled,IndexEnabled:row.index_enabled,DisplayOrder:row.display_order,Width:row.width,Config:row.config,Validation:row.validation,Options:(optionsByField.get(row.id)??[]).map(option=>({Id:option.id,Label:option.label,Value:option.value_key,SortOrder:option.sort_order}))})),
    };
  }

  async createIndexForm(principalInput:Principal|null,body:CreateIndexFormDTO):Promise<Record<string,unknown>>{
    const principal=this.admin(principalInput);
    const normalizedCode=body.Code.trim().toLowerCase();
    const existing=await this.db.query<{id:string}>(`SELECT id FROM zoha.index_forms WHERE code=$1 AND deleted=false LIMIT 1`,[normalizedCode]);
    if(existing.rows[0])throw new DomainException('IndexForm.CodeExists',HttpStatus.CONFLICT);
    const inserted=await this.db.transaction(async client=>{
      const form=await client.query<{id:string}>(`INSERT INTO zoha.index_forms(code,title,description,active_version,draft_version,is_system,is_active,created_by,updated_by,active,deleted) VALUES($1,$2,$3,0,1,false,true,$4,$4,true,false) RETURNING id`,[normalizedCode,body.Title.trim(),body.Description?.trim()||null,principal.id]);
      const id=form.rows[0]?.id;if(!id)throw new DomainException('IndexForm.CreateFailed',HttpStatus.INTERNAL_SERVER_ERROR);
      await client.query(`INSERT INTO zoha.index_form_versions(index_form_id,version,schema_snapshot,immutable,created_by,updated_by,active,deleted) VALUES($1,1,'{"layout":"grid"}'::jsonb,false,$2,$2,true,false)`,[id,principal.id]);
      return id;
    });
    return this.getIndexForm(principal,inserted);
  }

  async updateIndexForm(principalInput:Principal|null,id:string,body:UpdateIndexFormDTO):Promise<Record<string,unknown>>{
    const principal=this.admin(principalInput);
    const result=await this.db.query(`UPDATE zoha.index_forms SET title=COALESCE($1,title),description=COALESCE($2,description),is_active=COALESCE($3,is_active),updated_by=$4,updated_at=now(),update_at=now() WHERE id=$5 AND deleted=false`,[body.Title?.trim()||null,body.Description===undefined?null:body.Description.trim(),body.IsActive??null,principal.id,id]);
    if(result.rowCount===0)throw new DomainException('IndexForm.NotFound',HttpStatus.NOT_FOUND);
    return this.getIndexForm(principal,id);
  }

  private async draft(client:PoolClient,id:string):Promise<IndexVersionRow>{
    const result=await client.query<IndexVersionRow>(`SELECT v.id,v.version,v.immutable,v.published_at FROM zoha.index_forms f JOIN zoha.index_form_versions v ON v.index_form_id=f.id AND v.version=f.draft_version WHERE f.id=$1 AND f.deleted=false AND f.active=true AND v.deleted=false AND v.active=true LIMIT 1 FOR UPDATE OF f,v`,[id]);
    const row=result.rows[0];
    if(!row)throw new DomainException('IndexForm.Draft.NotFound',HttpStatus.NOT_FOUND);
    if(row.immutable)throw new DomainException('IndexForm.Draft.Immutable',HttpStatus.CONFLICT);
    return row;
  }

  private async normalizeTree(client:PoolClient,versionId:string):Promise<void>{
    const rows=await client.query<{id:string;field_key:string;config:Record<string,unknown>}>(`SELECT id,field_key,config FROM zoha.index_form_fields WHERE version_id=$1 AND active AND NOT deleted ORDER BY display_order,id`,[versionId]);
    try{
      const nodes=rows.rows.map(f=>({...f,key:f.field_key,parentKey:String((f.config?.hierarchy as Record<string,unknown>|undefined)?.parentKey??'')||null}));
      const ordered=hierarchyOrder(nodes);
      for(let i=0;i<ordered.length;i++)await client.query(`UPDATE zoha.index_form_fields SET display_order=$2 WHERE id=$1`,[ordered[i]!.id,(i+1)*10]);
    }catch(e){throw new DomainException(e instanceof Error?e.message:'IndexField.Hierarchy.Invalid',HttpStatus.BAD_REQUEST)}
  }
  private async fieldConfig(client:PoolClient,versionId:string,body:SaveIndexFieldDTO,current?:{field_key:string;config:Record<string,unknown>}):Promise<Record<string,unknown>>{
    const config={...(body.Config??{})};
    const previous=(current?.config.runtime??{}) as Record<string,unknown>;
    const runtime={...((config.runtime??{}) as Record<string,unknown>)};
    // Vocabulary identity is created by the builder, never selected from an external catalogue.
    const choices=['select','searchable_select','multiselect','radio','checkbox','tags','image_choice','price_option'].includes(body.InputKind);
    const vocabulary=choices&&!['image_choice','price_option'].includes(body.InputKind)&&runtime.sourceMode==='runtime_taxonomy';
    runtime.taxonomyCode=previous.taxonomyCode??(vocabulary?'IDX-B'+randomUUID().replace(/-/g,'').slice(0,16):null);
    runtime.sourceMode=vocabulary?'runtime_taxonomy':choices?'manual':'none';
    const parentKey=String((config.hierarchy as Record<string,unknown>|undefined)?.parentKey??'')||null;
    const parent=parentKey?(await client.query<{config:Record<string,unknown>}>(`SELECT config FROM zoha.index_form_fields WHERE version_id=$1 AND field_key=$2 AND active AND NOT deleted`,[versionId,parentKey])).rows[0]:null;
    if(parentKey&&!parent)throw new DomainException('نمایه والد در همین فرم وجود ندارد.',HttpStatus.BAD_REQUEST);
    const parentRuntime=(parent?.config.runtime??{}) as Record<string,unknown>;
    runtime.parentTaxonomyCode=parentRuntime.taxonomyCode??null;
    config.runtime=runtime;config.hierarchy={parentKey};config.authority='index-builder';
    if(runtime.taxonomyCode){
      await client.query(`INSERT INTO zoha.index_runtime_taxonomies(code,title,field_type,is_multi,allows_personal,metadata) VALUES($1,$2,$3,$4,$5,'{"authority":"index-builder"}'::jsonb) ON CONFLICT(code) DO NOTHING`,[runtime.taxonomyCode,body.Label.trim(),choices?'taxonomy':body.InputKind,['multiselect','checkbox','tags'].includes(body.InputKind),Boolean(runtime.allowsPersonal)]);
    }
    return config;
  }

  async addField(principalInput:Principal|null,formId:string,body:SaveIndexFieldDTO):Promise<Record<string,unknown>>{
    const principal=this.admin(principalInput);
    await this.db.transaction(async client=>{
      const draft=await this.draft(client,formId);
      const duplicate=await client.query<{id:string}>(`SELECT id FROM zoha.index_form_fields WHERE version_id=$1 AND field_key=$2 AND deleted=false LIMIT 1`,[draft.id,body.Key.trim()]);
      if(duplicate.rows[0])throw new DomainException('IndexField.KeyExists',HttpStatus.CONFLICT);
      const config=await this.fieldConfig(client,draft.id,body);
      const order=await client.query<{value:string}>(`SELECT (COALESCE(max(display_order),0)+10)::text AS value FROM zoha.index_form_fields WHERE version_id=$1 AND deleted=false`,[draft.id]);
      const inserted=await client.query<{id:string}>(`INSERT INTO zoha.index_form_fields(version_id,field_key,label,help_text,placeholder,input_kind,value_kind,required,search_enabled,index_enabled,display_order,width,config,validation,created_by,updated_by,active,deleted) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13::jsonb,$14::jsonb,$15,$15,true,false) RETURNING id`,[draft.id,body.Key.trim(),body.Label.trim(),body.HelpText?.trim()||null,body.Placeholder?.trim()||null,body.InputKind,body.ValueKind??'string',body.Required??false,body.SearchEnabled??true,body.IndexEnabled??true,Number(order.rows[0]?.value??10),body.Width??100,JSON.stringify(config),JSON.stringify(body.Validation??{}),principal.id]);
      await this.replaceOptions(client,principal.id,inserted.rows[0]!.id,body.Options??[]);
      await this.normalizeTree(client,draft.id);
      await client.query(`UPDATE zoha.index_forms SET updated_at=now(),update_at=now(),updated_by=$1 WHERE id=$2`,[principal.id,formId]);
    });
    return this.getIndexForm(principal,formId);
  }

  async updateField(principalInput:Principal|null,formId:string,fieldId:string,body:SaveIndexFieldDTO):Promise<Record<string,unknown>>{
    const principal=this.admin(principalInput);
    await this.db.transaction(async client=>{
      const draft=await this.draft(client,formId);
      const duplicate=await client.query<{id:string}>(`SELECT id FROM zoha.index_form_fields WHERE version_id=$1 AND field_key=$2 AND id<>$3 AND deleted=false LIMIT 1`,[draft.id,body.Key.trim(),fieldId]);
      if(duplicate.rows[0])throw new DomainException('IndexField.KeyExists',HttpStatus.CONFLICT);
      const current=(await client.query<{field_key:string;config:Record<string,unknown>}>(`SELECT field_key,config FROM zoha.index_form_fields WHERE id=$1 AND version_id=$2 AND NOT deleted`,[fieldId,draft.id])).rows[0];
      if(!current)throw new DomainException('IndexField.NotFound',HttpStatus.NOT_FOUND);
      const config=await this.fieldConfig(client,draft.id,body,current);
      const result=await client.query(`UPDATE zoha.index_form_fields SET field_key=$1,label=$2,help_text=$3,placeholder=$4,input_kind=$5,value_kind=$6,required=$7,search_enabled=$8,index_enabled=$9,width=$10,config=$11::jsonb,validation=$12::jsonb,updated_by=$13,updated_at=now(),update_at=now() WHERE id=$14 AND version_id=$15 AND deleted=false`,[body.Key.trim(),body.Label.trim(),body.HelpText?.trim()||null,body.Placeholder?.trim()||null,body.InputKind,body.ValueKind??'string',body.Required??false,body.SearchEnabled??true,body.IndexEnabled??true,body.Width??100,JSON.stringify(config),JSON.stringify(body.Validation??{}),principal.id,fieldId,draft.id]);
      if(result.rowCount===0)throw new DomainException('IndexField.NotFound',HttpStatus.NOT_FOUND);
      await this.replaceOptions(client,principal.id,fieldId,body.Options??[]);
      if(current.field_key!==body.Key.trim())await client.query(`UPDATE zoha.index_form_fields SET config=jsonb_set(config,'{hierarchy,parentKey}',to_jsonb($3::text)) WHERE version_id=$1 AND config->'hierarchy'->>'parentKey'=$2 AND NOT deleted`,[draft.id,current.field_key,body.Key.trim()]);
      await this.normalizeTree(client,draft.id);
      await client.query(`UPDATE zoha.index_forms SET updated_at=now(),update_at=now(),updated_by=$1 WHERE id=$2`,[principal.id,formId]);
    });
    return this.getIndexForm(principal,formId);
  }

  private async replaceOptions(client:PoolClient,userId:string,fieldId:string,options:{Label:string;Value:string}[]):Promise<void>{
    await client.query(`DELETE FROM zoha.index_form_options WHERE field_id=$1`,[fieldId]);
    for(let i=0;i<options.length;i+=1){const option=options[i]!;await client.query(`INSERT INTO zoha.index_form_options(field_id,value_key,label,sort_order,created_by,updated_by,active,deleted) VALUES($1,$2,$3,$4,$5,$5,true,false)`,[fieldId,option.Value.trim()||`option_${i+1}`,option.Label.trim()||`گزینه ${i+1}`,i*10,userId]);}
  }

  async removeField(principalInput:Principal|null,formId:string,fieldId:string):Promise<Record<string,unknown>>{
    const principal=this.admin(principalInput);
    await this.db.transaction(async client=>{const draft=await this.draft(client,formId);const child=await client.query(`SELECT id FROM zoha.index_form_fields WHERE version_id=$1 AND config->'hierarchy'->>'parentKey'=(SELECT field_key FROM zoha.index_form_fields WHERE id=$2) AND active AND NOT deleted LIMIT 1`,[draft.id,fieldId]);if(child.rows[0])throw new DomainException('ابتدا زیرشاخه‌ها را جابه‌جا یا حذف کنید.',HttpStatus.CONFLICT);const result=await client.query(`DELETE FROM zoha.index_form_fields WHERE id=$1 AND version_id=$2`,[fieldId,draft.id]);if(result.rowCount===0)throw new DomainException('IndexField.NotFound',HttpStatus.NOT_FOUND);});
    return this.getIndexForm(principal,formId);
  }

  async reorder(principalInput:Principal|null,formId:string,body:ReorderIndexFieldsDTO):Promise<Record<string,unknown>>{
    const principal=this.admin(principalInput);
    await this.db.transaction(async client=>{const draft=await this.draft(client,formId);for(let i=0;i<body.FieldIds.length;i+=1){await client.query(`UPDATE zoha.index_form_fields SET display_order=$1,updated_by=$2,updated_at=now(),update_at=now() WHERE id=$3 AND version_id=$4`,[(i+1)*10,principal.id,body.FieldIds[i],draft.id]);}await this.normalizeTree(client,draft.id);});
    return this.getIndexForm(principal,formId);
  }

  async publish(principalInput:Principal|null,formId:string):Promise<Record<string,unknown>>{
    const principal=this.admin(principalInput);
    await this.db.transaction(async client=>{
      const draft=await this.draft(client,formId);
      await this.normalizeTree(client,draft.id);
      const count=await client.query<{value:string}>(`SELECT count(*)::text AS value FROM zoha.index_form_fields WHERE version_id=$1 AND deleted=false AND active=true`,[draft.id]);
      if(Number(count.rows[0]?.value??0)<1)throw new DomainException('IndexForm.Publish.Empty',HttpStatus.CONFLICT);
      await client.query(`UPDATE zoha.index_form_versions SET immutable=true,published_at=now(),updated_by=$1,updated_at=now(),update_at=now() WHERE id=$2`,[principal.id,draft.id]);
      const next=draft.version+1;
      const nextVersion=await client.query<{id:string}>(`INSERT INTO zoha.index_form_versions(index_form_id,version,schema_snapshot,validation_rules,immutable,created_by,updated_by,active,deleted) SELECT index_form_id,$1,schema_snapshot,validation_rules,false,$2,$2,true,false FROM zoha.index_form_versions WHERE id=$3 RETURNING id`,[next,principal.id,draft.id]);
      const nextId=nextVersion.rows[0]!.id;
      await client.query(`INSERT INTO zoha.index_form_fields(version_id,field_key,label,help_text,placeholder,input_kind,value_kind,required,search_enabled,index_enabled,display_order,width,config,validation,created_by,updated_by,active,deleted) SELECT $1,field_key,label,help_text,placeholder,input_kind,value_kind,required,search_enabled,index_enabled,display_order,width,config,validation,$2,$2,true,false FROM zoha.index_form_fields WHERE version_id=$3 AND deleted=false AND active=true`,[nextId,principal.id,draft.id]);
      await client.query(`INSERT INTO zoha.index_form_options(field_id,value_key,label,sort_order,is_active,created_by,updated_by,active,deleted) SELECT nf.id,o.value_key,o.label,o.sort_order,o.is_active,$1,$1,true,false FROM zoha.index_form_fields oldf JOIN zoha.index_form_options o ON o.field_id=oldf.id AND o.deleted=false JOIN zoha.index_form_fields nf ON nf.version_id=$2 AND nf.field_key=oldf.field_key WHERE oldf.version_id=$3`,[principal.id,nextId,draft.id]);
      await client.query(`UPDATE zoha.index_forms SET active_version=$1,draft_version=$2,updated_by=$3,updated_at=now(),update_at=now() WHERE id=$4`,[draft.version,next,principal.id,formId]);
      await client.query(`SELECT zoha.sync_index_builder_projection($1::uuid)`,[formId]);
    });
    return this.getIndexForm(principal,formId);
  }

  async assign(principalInput:Principal|null,formId:string,body:AssignIndexFormDTO):Promise<Record<string,unknown>>{
    const principal=this.admin(principalInput);
    await this.db.transaction(async client=>this.assignIndexFormTx(client,principal.id,body.ContentTypeId,formId));
    return this.getIndexForm(principal,formId);
  }

  private async assignIndexFormTx(client:PoolClient,userId:string,contentTypeId:string,indexFormId:string):Promise<void>{
    const form=await client.query<{id:string}>(`SELECT id FROM zoha.index_forms WHERE id=$1 AND deleted=false AND active=true LIMIT 1`,[indexFormId]);
    if(!form.rows[0])throw new DomainException('IndexForm.NotFound',HttpStatus.NOT_FOUND);
    await client.query(`UPDATE zoha.content_type_index_forms SET is_primary=false,updated_by=$1,updated_at=now(),update_at=now() WHERE content_type_id=$2 AND deleted=false AND active=true`,[userId,contentTypeId]);
    await client.query(`INSERT INTO zoha.content_type_index_forms(content_type_id,index_form_id,is_primary,created_by,updated_by,active,deleted) VALUES($1,$2,true,$3,$3,true,false) ON CONFLICT(content_type_id,index_form_id) DO UPDATE SET is_primary=true,active=true,deleted=false,updated_by=EXCLUDED.updated_by,updated_at=now(),update_at=now()`,[contentTypeId,indexFormId,userId]);
    await client.query(`SELECT zoha.sync_index_builder_projection($1::uuid)`,[indexFormId]);
  }
}
