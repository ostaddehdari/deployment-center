from pathlib import Path
import sys

root=Path(sys.argv[1]).resolve()

def read(rel):
    p=root/rel
    if not p.exists():
        raise SystemExit(f"ERROR missing {rel}")
    return p,p.read_text(encoding='utf-8')

def write(p,s):
    p.write_text(s,encoding='utf-8')

rel='apps/api/src/admin-content-studio/admin-runtime-index.service.ts'
p,s=read(rel)
if 'async previewSchema(' not in s:
    marker='  async assignField('
    idx=s.find(marker)
    if idx<0: raise SystemExit('ERROR service marker not found')
    block="""  async previewSchema(principalInput:Principal|null,contentTypeInput:string):Promise<Record<string,unknown>>{
    this.admin(principalInput);
    const contentType=this.contentType(contentTypeInput);
    const [fields,relations]=await Promise.all([
      this.db.query(`SELECT t.code,t.title,t.legacy_title AS \"legacyTitle\",t.field_type AS type,t.is_multi AS multi,t.allows_personal AS \"allowsPersonal\",p.sort_order AS \"sortOrder\",p.settings
        FROM zoha.index_runtime_post_type_fields p
        JOIN zoha.index_runtime_taxonomies t ON t.code=p.taxonomy_code
        WHERE p.post_type_code=$1 AND t.is_active
        ORDER BY p.sort_order`,[contentType]),
      this.db.query(`SELECT code,source_title AS source,target_title AS target,cardinality,rule_text AS rule,note FROM zoha.index_runtime_relations ORDER BY code`),
    ]);
    return {contentType,version:3,fields:fields.rows,relations:relations.rows,topicAnalysis:{fields:['IDX-001','IDX-003','IDX-002','IDX-004'],label:'موضوع ← کلید پردازش ← زیرموضوع ← برداشت'}};
  }

  async previewOptions(principalInput:Principal|null,code:string,q='',parent=''):Promise<Record<string,unknown>>{
    this.admin(principalInput);
    const tx=(await this.db.query<{code:string;title:string;allows_personal:boolean}>(`SELECT code,title,allows_personal FROM zoha.index_runtime_taxonomies WHERE code=$1 AND is_active`,[code])).rows[0];
    if(!tx)throw new DomainException('Index.Taxonomy.NotFound',HttpStatus.NOT_FOUND);
    const n=normalize(q),p=normalize(parent);
    const items=await this.db.query(`SELECT id,title,'system'::text AS scope,parent_hint AS parent FROM zoha.index_runtime_terms
      WHERE taxonomy_code=$1 AND is_active AND ($2='' OR normalized_title LIKE '%'||$2||'%') AND ($3='' OR parent_hint=$3)
      ORDER BY sort_order,title LIMIT 80`,[code,n,p]);
    return {taxonomy:tx,items:items.rows};
  }

"""
    s=s[:idx]+block+s[idx:]
    write(p,s)

rel='apps/api/src/admin-content-studio/admin-runtime-index.controller.ts'
p,s=read(rel)
if "@Get('preview/schema/:contentType')" not in s:
    marker="  @Post('post-types/:contentType/fields/:taxonomyCode')"
    idx=s.find(marker)
    if idx<0: raise SystemExit('ERROR controller marker not found')
    block="""  @Get('preview/schema/:contentType')
  previewSchema(@Req() request:AppRequest,@Param('contentType') contentType:string){return this.runtime.previewSchema(this.actor(request),contentType);}
  @Get('preview/taxonomies/:code/options')
  previewOptions(@Req() request:AppRequest,@Param('code') code:string,@Query('q') q='',@Query('parent') parent=''){return this.runtime.previewOptions(this.actor(request),code,q,parent);}

"""
    s=s[:idx]+block+s[idx:]
    write(p,s)

rel='apps/web/composables/useIndexRuntime.ts'
p,s=read(rel)
s=s.replace("export const useIndexRuntime=()=>{","export const useIndexRuntime=(mode:'user'|'admin-preview'='user')=>{")
old=" const schema=async(t:ContentTypeCode):Promise<IndexSchema>=>unwrap(await $fetch<ApiEnvelope<IndexSchema>|IndexSchema>(`/api/v1/index-runtime/schema/${t}`,{headers:headers()}))"
new=" const schema=async(t:ContentTypeCode):Promise<IndexSchema>=>unwrap(await $fetch<ApiEnvelope<IndexSchema>|IndexSchema>(mode==='admin-preview'?`/api/admin/runtime-index/v1/preview/schema/${t}`:`/api/v1/index-runtime/schema/${t}`,{headers:headers()}))"
s=s.replace(old,new)
old=" const options=async(code:string,q='',parent=''):Promise<IndexOptionsResponse>=>unwrap(await $fetch<ApiEnvelope<IndexOptionsResponse>|IndexOptionsResponse>(`/api/v1/index-runtime/taxonomies/${code}/options`,{headers:headers(),query:{q,parent}}))"
new=" const options=async(code:string,q='',parent=''):Promise<IndexOptionsResponse>=>unwrap(await $fetch<ApiEnvelope<IndexOptionsResponse>|IndexOptionsResponse>(mode==='admin-preview'?`/api/admin/runtime-index/v1/preview/taxonomies/${code}/options`:`/api/v1/index-runtime/taxonomies/${code}/options`,{headers:headers(),query:{q,parent}}))"
s=s.replace(old,new)
old=" const addPersonal=async(code:string,title:string,parentSystemTermId?:number|string,parentUserTermId?:number|string):Promise<{created:boolean;useExisting?:boolean;item:IndexOption}>=>unwrap(await $fetch(`/api/v1/index-runtime/taxonomies/${code}/personal`,{method:'POST',headers:headers(),body:{title,parentSystemTermId,parentUserTermId}})) as {created:boolean;useExisting?:boolean;item:IndexOption}"
new=" const addPersonal=async(code:string,title:string,parentSystemTermId?:number|string,parentUserTermId?:number|string):Promise<{created:boolean;useExisting?:boolean;item:IndexOption}>=>{if(mode==='admin-preview')throw new Error('افزودن مورد شخصی در پیش‌نمایش مدیریت غیرفعال است.');return unwrap(await $fetch(`/api/v1/index-runtime/taxonomies/${code}/personal`,{method:'POST',headers:headers(),body:{title,parentSystemTermId,parentUserTermId}})) as {created:boolean;useExisting?:boolean;item:IndexOption}}"
s=s.replace(old,new)
write(p,s)

rel='apps/web/components/indexing/IndexPersonalSelect.vue'
p,s=read(rel)
s=s.replace("personalParentOption?:IndexOption|null}>()","personalParentOption?:IndexOption|null;adminPreview?:boolean}>()")
s=s.replace("const api=useIndexRuntime()","const api=useIndexRuntime(props.adminPreview?'admin-preview':'user')")
s=s.replace("const canAdd=computed(()=>props.allowsPersonal&&q.value.trim().length>1","const canAdd=computed(()=>!props.adminPreview&&props.allowsPersonal&&q.value.trim().length>1")
write(p,s)

rel='apps/web/components/indexing/IndexRuntimePanel.vue'
p,s=read(rel)
s=s.replace("modelValue?:IndexPayload;embedded?:boolean}>(),{contentId:'',embedded:false})","modelValue?:IndexPayload;embedded?:boolean;adminPreview?:boolean}>(),{contentId:'',embedded:false,adminPreview:false})")
s=s.replace("const api=useIndexRuntime()","const api=useIndexRuntime(props.adminPreview?'admin-preview':'user')")
s=s.replace('<IndexPersonalSelect code="IDX-001"','<IndexPersonalSelect :admin-preview="props.adminPreview" code="IDX-001"')
s=s.replace('<IndexPersonalSelect code="IDX-003"','<IndexPersonalSelect :admin-preview="props.adminPreview" code="IDX-003"')
s=s.replace('<IndexPersonalSelect code="IDX-002"','<IndexPersonalSelect :admin-preview="props.adminPreview" code="IDX-002"')
s=s.replace("<IndexPersonalSelect v-if=\"f.type==='taxonomy'||f.type==='choice'\"","<IndexPersonalSelect :admin-preview=\"props.adminPreview\" v-if=\"f.type==='taxonomy'||f.type==='choice'\"")
write(p,s)

rel='apps/web/pages/admin/index-builder.vue'
p,s=read(rel)
if ':admin-preview="true"' not in s:
    s=s.replace('<IndexRuntimePanel ', '<IndexRuntimePanel :admin-preview="true" ', 1)
write(p,s)

print('ADMIN_PREVIEW_AUTH_BRIDGE_PATCH=PASS')
