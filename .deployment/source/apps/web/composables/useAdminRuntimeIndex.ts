import type { ApiEnvelope } from '~/types/site'
import type { AdminRuntimeOverview,AdminRuntimeTermsResponse,RuntimeContentTypeCode } from '~/types/admin-runtime-index'

export const useAdminRuntimeIndex=()=>{
 const auth=useZohaAuth()
 const headers=():Record<string,string>=>auth.authenticatedHeaders()
 const unwrap=<T>(response:ApiEnvelope<T>|T):T=>typeof response==='object'&&response!==null&&'data' in response&&'status' in response?(response as ApiEnvelope<T>).data:response as T
 const overview=async(contentType?:RuntimeContentTypeCode):Promise<AdminRuntimeOverview>=>unwrap(await $fetch('/api/admin/runtime-index/v1/overview',{headers:headers(),query:{contentType}}))
 const assignField=async(contentType:RuntimeContentTypeCode,code:string):Promise<AdminRuntimeOverview>=>unwrap(await $fetch(`/api/admin/runtime-index/v1/post-types/${contentType}/fields/${code}`,{method:'POST',headers:headers()}))
 const updateField=async(contentType:RuntimeContentTypeCode,code:string,body:{IsRequired?:boolean;Settings?:Record<string,unknown>}):Promise<AdminRuntimeOverview>=>unwrap(await $fetch(`/api/admin/runtime-index/v1/post-types/${contentType}/fields/${code}`,{method:'PATCH',headers:headers(),body}))
 const removeField=async(contentType:RuntimeContentTypeCode,code:string):Promise<AdminRuntimeOverview>=>unwrap(await $fetch(`/api/admin/runtime-index/v1/post-types/${contentType}/fields/${code}`,{method:'DELETE',headers:headers()}))
 const reorder=async(contentType:RuntimeContentTypeCode,codes:string[]):Promise<AdminRuntimeOverview>=>unwrap(await $fetch(`/api/admin/runtime-index/v1/post-types/${contentType}/reorder`,{method:'POST',headers:headers(),body:{TaxonomyCodes:codes}}))
 const updateTaxonomy=async(code:string,body:{Title?:string;FieldType?:string;IsMulti?:boolean;AllowsPersonal?:boolean;IsActive?:boolean;Metadata?:Record<string,unknown>}):Promise<{ok:boolean}>=>unwrap(await $fetch(`/api/admin/runtime-index/v1/taxonomies/${code}`,{method:'PATCH',headers:headers(),body}))
 const terms=async(code:string,q='',page=1,pageSize=50,includeInactive=false):Promise<AdminRuntimeTermsResponse>=>unwrap(await $fetch(`/api/admin/runtime-index/v1/taxonomies/${code}/terms`,{headers:headers(),query:{q,page,pageSize,includeInactive}}))
 const createTerm=async(code:string,body:{Title:string;ParentHint?:string;ParentId?:string;SortOrder?:number;Metadata?:Record<string,unknown>}):Promise<Record<string,unknown>>=>unwrap(await $fetch(`/api/admin/runtime-index/v1/taxonomies/${code}/terms`,{method:'POST',headers:headers(),body}))
 const updateTerm=async(code:string,id:string,body:{Title?:string;ParentHint?:string;ParentId?:string;SortOrder?:number;IsActive?:boolean;Metadata?:Record<string,unknown>}):Promise<Record<string,unknown>>=>unwrap(await $fetch(`/api/admin/runtime-index/v1/taxonomies/${code}/terms/${id}`,{method:'PATCH',headers:headers(),body}))
 const deleteTerm=async(code:string,id:string):Promise<{ok:boolean}>=>unwrap(await $fetch(`/api/admin/runtime-index/v1/taxonomies/${code}/terms/${id}`,{method:'DELETE',headers:headers()}))
 return{overview,assignField,updateField,removeField,reorder,updateTaxonomy,terms,createTerm,updateTerm,deleteTerm}
}
