import type { ApiEnvelope } from '~/types/site'
import type { ContentTypeCode,IndexPayload } from '~/types/content'

export type IndexScope='system'|'personal'
export type IndexSourceMode='none'|'manual'|'runtime_taxonomy'
export interface IndexOption {id:number|string;title:string;scope:IndexScope;parent?:string|null}
export interface IndexManualOption {value:string;label:string;sortOrder?:number}
export interface IndexFieldDefinition {
 code:string
 key?:string
 title:string
 legacyTitle?:string|null
 type:string
 valueKind?:string
 multi:boolean
 allowsPersonal:boolean
 sortOrder:number
 required?:boolean
 searchEnabled?:boolean
 indexEnabled?:boolean
 taxonomyCode?:string|null
 sourceMode?:IndexSourceMode|string
 parentKey?:string|null
 parentTaxonomyCode?:string|null
 settings?:Record<string,unknown>
 config?:Record<string,unknown>
 validation?:Record<string,unknown>
 options?:IndexManualOption[]
}
export interface IndexSchema {
 contentType:ContentTypeCode
 version:number
 builder?:string
 fields:IndexFieldDefinition[]
 relations:Record<string,unknown>[]
 topicAnalysis:{fields:string[];label:string}
}
export interface IndexOptionsResponse {taxonomy:{code:string;title:string;allows_personal:boolean};items:IndexOption[]}
export interface IndexPayloadResponse {payload:IndexPayload;schemaVersion:number;updatedAt?:string}

export const useIndexRuntime=(mode:'user'|'admin-preview'='user')=>{
 const auth=useZohaAuth()
 const headers=():Record<string,string>=>auth.authenticatedHeaders()
 const unwrap=<T>(response:ApiEnvelope<T>|T):T=>{
  if(typeof response==='object'&&response!==null&&'data' in response&&'status' in response)return(response as ApiEnvelope<T>).data
  return response as T
 }
 const schema=async(t:ContentTypeCode):Promise<IndexSchema>=>unwrap(await $fetch<ApiEnvelope<IndexSchema>|IndexSchema>(mode==='admin-preview'?`/api/admin/runtime-index/v1/preview/schema/${t}`:`/api/v1/index-runtime/schema/${t}`,{headers:headers()}))
 const options=async(code:string,q='',parent='',parentOption?:IndexOption|null,contentType?:ContentTypeCode):Promise<IndexOptionsResponse>=>unwrap(await $fetch<ApiEnvelope<IndexOptionsResponse>|IndexOptionsResponse>(mode==='admin-preview'?`/api/admin/runtime-index/v1/preview/taxonomies/${code}/options`:`/api/v1/index-runtime/taxonomies/${code}/options`,{headers:headers(),query:{q,parent,parentId:parentOption?.id,parentScope:parentOption?.scope,contentType}}))
 const addPersonal=async(code:string,title:string,parentSystemTermId?:number|string,parentUserTermId?:number|string,contentType?:ContentTypeCode):Promise<{created:boolean;useExisting?:boolean;item:IndexOption}>=>{if(mode==='admin-preview')throw new Error('افزودن مورد شخصی در پیش‌نمایش مدیریت غیرفعال است.');return unwrap(await $fetch(`/api/v1/index-runtime/taxonomies/${code}/personal`,{method:'POST',headers:headers(),body:{title,parentSystemTermId,parentUserTermId,contentType}})) as {created:boolean;useExisting?:boolean;item:IndexOption}}
 const load=async(t:ContentTypeCode,id:string):Promise<IndexPayloadResponse>=>unwrap(await $fetch<ApiEnvelope<IndexPayloadResponse>|IndexPayloadResponse>(`/api/v1/index-runtime/${t}/${id}`,{headers:headers()}))
 const save=async(t:ContentTypeCode,id:string,payload:IndexPayload):Promise<{ok:boolean;updatedAt?:string}>=>unwrap(await $fetch(`/api/v1/index-runtime/${t}/${id}`,{method:'POST',headers:headers(),body:{payload}})) as {ok:boolean;updatedAt?:string}
 const uploadFile=async(t:ContentTypeCode,key:string,file:File):Promise<{id:string;name:string;size:number;type:string}>=>{if(mode==='admin-preview')throw new Error('بارگذاری فایل در پیش‌نمایش انجام نمی‌شود.');const body=new FormData();body.append('contentType',t);body.append('fieldKey',key);body.append('file',file);const h=headers();delete h['Content-Type'];delete h['content-type'];return unwrap(await $fetch('/api/v1/index-runtime/files/upload',{method:'POST',headers:h,body}))}
 const downloadFile=async(id:string,name:string)=>{const blob=await $fetch<Blob>(`/api/v1/index-runtime/files/${id}`,{headers:headers(),responseType:'blob'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
 return{schema,options,addPersonal,load,save,uploadFile,downloadFile}
}
