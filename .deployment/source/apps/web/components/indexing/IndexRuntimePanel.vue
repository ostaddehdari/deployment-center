<script setup lang="ts">
import { hierarchyOrder, hierarchyDepth, descendants } from '~/utils/indexHierarchy'
import IndexDynamicField from '~/components/indexing/IndexDynamicField.vue'
import IndexPersonalSelect from '~/components/indexing/IndexPersonalSelect.vue'
import { defaultFor, validateField, visibleField } from '~/utils/indexFieldRuntime'
import type { ContentTypeCode,IndexPayload } from '~/types/content'
import type { IndexFieldDefinition,IndexOption,IndexSchema } from '~/composables/useIndexRuntime'

const props=withDefaults(defineProps<{contentType:ContentTypeCode;contentId?:string;modelValue?:IndexPayload;embedded?:boolean;adminPreview?:boolean;schemaOverride?:IndexSchema|null}>(),{contentId:'',embedded:false,adminPreview:false,schemaOverride:null})
const emit=defineEmits<{(e:'update:modelValue',value:IndexPayload):void;(e:'saved'):void}>()
const api=useIndexRuntime(props.adminPreview?'admin-preview':'user')
const schema=ref<IndexSchema|null>(null)
const data=reactive<IndexPayload>({topicAnalyses:[]})
const busy=ref(false),loading=ref(true),errorMessage=ref(''),saved=ref('')

const topicCodes=['IDX-001','IDX-003','IDX-002','IDX-004']
const clone=<T>(value:T):T=>JSON.parse(JSON.stringify(value)) as T
const field=(code:string):IndexFieldDefinition|undefined=>schema.value?.fields?.find(x=>x.code===code||x.taxonomyCode===code)
const hasTopicAnalysis=computed(()=>topicCodes.every(code=>Boolean(field(code))))
const schemaNodes=computed(()=>(schema.value?.fields??[]).map(f=>({key:f.key||f.code,parentKey:f.parentKey||null,field:f})))
const orderedFields=computed(()=>{try{return hierarchyOrder(schemaNodes.value).map(n=>n.field)}catch{return schema.value?.fields??[]}})
const analysisFields=computed(()=>{if(!hasTopicAnalysis.value)return [];const topic=field('IDX-001');const keys=new Set(topic?descendants(schemaNodes.value,topic.key||topic.code):[]);return orderedFields.value.filter(f=>topicCodes.includes(f.code)||keys.has(f.key||f.code))})
const normalFields=computed(()=>orderedFields.value.filter(f=>!analysisFields.value.includes(f)))
const depthFor=(f:IndexFieldDefinition)=>{try{return hierarchyDepth(schemaNodes.value,f.key||f.code)}catch{return 0}}
const pageIndex=ref(0),attempted=ref(false)
const formPages=computed(()=>{const pages:{title:string;fields:IndexFieldDefinition[]}[]=[{title:'شروع',fields:[]}];for(const f of normalFields.value){if(f.type==='page')pages.push({title:f.title,fields:[]});else pages[pages.length-1]!.fields.push(f)}return pages})
const currentFields=computed(()=>formPages.value[pageIndex.value]?.fields??[])
const fieldErrors=computed(()=>{const out:Record<string,string>={};for(const f of schema.value?.fields??[]){if(!isVisible(f)||parentPending(f)||analysisFields.value.includes(f))continue;out[f.code]=validateField({...f,required:attempted.value&&f.required},data[f.code])}return out})
const validate=(all=true):boolean=>{attempted.value=true;if(hasTopicAnalysis.value&&(all||pageIndex.value===0)){for(const row of data.topicAnalyses){for(const f of analysisFields.value){if(!parentPending(f,row)&&validateField(f,valueFor(f,row))){pageIndex.value=0;errorMessage.value=`فیلد «${f.title}» در تحلیل موضوعی را تکمیل کنید.`;return false}}}}const fields=all?normalFields.value:currentFields.value;const invalid=fields.find(f=>isVisible(f)&&!parentPending(f)&&validateField(f,data[f.code]));if(invalid){const i=formPages.value.findIndex(p=>p.fields.some(f=>f.code===invalid.code));if(i>=0)pageIndex.value=i;errorMessage.value='فیلدهای مشخص‌شده را بررسی کنید.';return false}errorMessage.value='';return true}
const nextPage=()=>{if(validate(false))pageIndex.value=Math.min(pageIndex.value+1,formPages.value.length-1)}
defineExpose({validate})
const ensureAnalyses=()=>{if(!Array.isArray(data.topicAnalyses))data.topicAnalyses=[];if(hasTopicAnalysis.value&&!data.topicAnalyses.length)addAnalysis()}
const applyPayload=(payload:IndexPayload|undefined)=>{for(const key of Object.keys(data))delete data[key];Object.assign(data,clone(payload??{topicAnalyses:[]}));for(const f of schema.value?.fields??[]){const value=defaultFor(f);if(data[f.code]===undefined&&value!==undefined)data[f.code]=value}pageIndex.value=0;attempted.value=false;ensureAnalyses()}
const addAnalysis=()=>data.topicAnalyses.push({topic:null,processingKey:null,subtopic:null,interpretation:''})
const removeAnalysis=(i:number)=>data.topicAnalyses.splice(i,1)
const analysisKey=(f:IndexFieldDefinition):string=>({'IDX-001':'topic','IDX-003':'processingKey','IDX-002':'subtopic','IDX-004':'interpretation'} as Record<string,string>)[f.code]??f.code
const valueFor=(f:IndexFieldDefinition,row?:unknown):unknown=>row?(row as Record<string,unknown>)[analysisKey(f)]:data[f.code]
const setFieldValue=(f:IndexFieldDefinition,value:unknown,row?:unknown)=>{const values=(row??data) as Record<string,unknown>;const key=row?analysisKey(f):f.code;if(JSON.stringify(values[key])!==JSON.stringify(value)){for(const childKey of descendants(schemaNodes.value,f.key||f.code)){const child=orderedFields.value.find(x=>(x.key||x.code)===childKey);if(child)values[row?analysisKey(child):child.code]=null}}values[key]=value}
const selection=(value:unknown):IndexOption|null=>{const selected=Array.isArray(value)?value[0]:value;return selected&&typeof selected==='object'?selected as IndexOption:null}
const selectionTitle=(value:unknown):string=>selection(value)?.title??(typeof value==='string'||typeof value==='number'?String(value):'')
const fieldByTaxonomy=(code:string):IndexFieldDefinition|undefined=>schema.value?.fields?.find(x=>x.taxonomyCode===code||x.code===code)
const parentField=(f:IndexFieldDefinition):IndexFieldDefinition|undefined=>f.parentKey?orderedFields.value.find(p=>(p.key||p.code)===f.parentKey):f.parentTaxonomyCode?fieldByTaxonomy(f.parentTaxonomyCode):undefined
const parentFor=(f:IndexFieldDefinition,row?:unknown):string=>{const parent=parentField(f);return parent?selectionTitle(valueFor(parent,analysisFields.value.includes(parent)?row:undefined)):''}
const personalParentFor=(f:IndexFieldDefinition,row?:unknown):IndexOption|null=>{const parent=parentField(f);return parent?selection(valueFor(parent,analysisFields.value.includes(parent)?row:undefined)):null}
const parentPending=(f:IndexFieldDefinition,row?:unknown):boolean=>{const parent=parentField(f);return Boolean(parent&&['select','searchable_select','multiselect','radio','checkbox','tags'].includes(parent.type)&&!parentFor(f,row))}

const widthFor=(f:IndexFieldDefinition):number=>{const n=Number((f.settings??{}).width??100);return n>=25&&n<=100?n:100}
const comparable=(value:unknown):string=>{if(value===null||value===undefined)return'';if(Array.isArray(value))return value.map(comparable).join('|');if(typeof value==='object'){const v=value as Record<string,unknown>;return String(v.title??v.label??v.value??v.id??'')}return String(value)}
const isVisible=(f:IndexFieldDefinition):boolean=>!f.config?.condition||visibleField(f,schema.value?.fields??[],data)

const load=async()=>{
 loading.value=true;errorMessage.value=''
 try{
  schema.value=props.schemaOverride?clone(props.schemaOverride):await api.schema(props.contentType)
  if(props.contentId&&!props.schemaOverride){const r=await api.load(props.contentType,props.contentId);applyPayload(r.payload)}
  else applyPayload(props.modelValue)
 }catch(e:unknown){errorMessage.value=e instanceof Error?e.message:'نمایه‌ساز بارگذاری نشد.'}
 finally{loading.value=false}
}
const save=async()=>{
 if(!props.contentId)return
 if(!validate())return
 busy.value=true;saved.value='';errorMessage.value=''
 try{await api.save(props.contentType,props.contentId,clone(data));saved.value='نمایه‌ها ذخیره شدند.';emit('saved')}
 catch(e:unknown){errorMessage.value=e instanceof Error?e.message:'ذخیره نمایه‌ها انجام نشد.'}
 finally{busy.value=false}
}
watch(data,()=>emit('update:modelValue',clone(data)),{deep:true})
watch(()=>props.contentType,()=>void load())
watch(()=>props.schemaOverride,()=>void load(),{deep:true})
onMounted(()=>void load())
</script>

<template>
<section class="index-panel" dir="rtl">
 <header class="index-head">
  <div><h2>نمایه‌گذاری {{contentType==='mold'?'محتوای مولد':contentType==='full_sermon'?'محتوای کامل / منبر':'محتوای پشتیبان'}}</h2><p>فرم را تکمیل کنید؛ برای هر موضوع می‌توانید زیرموضوع و برداشت جداگانه ثبت کنید.</p></div>
  <button v-if="!embedded&&contentId" class="save" :disabled="busy||loading" @click="save">{{busy?'در حال ذخیره…':'ذخیره نمایه‌ها'}}</button>
 </header>
 <div v-if="errorMessage" class="error">{{errorMessage}}</div>
 <div v-if="loading" class="loading">در حال بارگذاری نمایه‌ساز…</div>
 <template v-else-if="schema">
  <nav v-if="formPages.length>1" class="page-steps" aria-label="مراحل فرم"><span v-for="(p,i) in formPages" :key="i" :class="{active:i===pageIndex}">{{i+1}}. {{p.title}}</span></nav>
  <div v-if="hasTopicAnalysis&&pageIndex===0" class="analysis">
   <div class="section-title"><div><h3>تحلیل موضوعی</h3><p>{{schema.topicAnalysis.label||'موضوع، کلید پردازش، زیرموضوع و برداشت'}}</p></div><button type="button" @click="addAnalysis">+ موضوع دیگر</button></div>
   <article v-for="(a,i) in data.topicAnalyses" :key="i" class="analysis-card">
    <div class="grid">
     <fieldset v-for="f in analysisFields" :key="f.code" class="tree-runtime-field" :disabled="parentPending(f,a)" :style="{marginInlineStart:`${depthFor(f)*22}px`}" :data-depth="depthFor(f)">
      <small v-if="parentField(f)" class="parent-label">ذیل {{parentField(f)?.title}}</small>
      <IndexDynamicField :admin-preview="props.adminPreview" :field="f" :model-value="valueFor(f,a)" :parent="parentFor(f,a)" :personal-parent-option="personalParentFor(f,a)" :content-type="contentType" :fields="schema.fields" :form-values="data" @update:model-value="setFieldValue(f,$event,a)"/>
      <small v-if="parentPending(f,a)">ابتدا {{parentField(f)?.title}} را انتخاب کنید.</small>
     </fieldset>
    </div>
    <button v-if="data.topicAnalyses.length>1" class="remove" type="button" @click="removeAnalysis(i)">حذف این تحلیل</button>
   </article>
  </div>

  <div v-if="normalFields.length" class="fields">
   <template v-for="f in currentFields" :key="f.code">
    <fieldset v-if="isVisible(f)" class="runtime-field tree-runtime-field" :disabled="parentPending(f)" :style="{gridColumn:depthFor(f)?'1 / -1':`span ${Math.round(widthFor(f)/100*12)}`,marginInlineStart:`${depthFor(f)*22}px`}" :data-depth="depthFor(f)"><small v-if="parentField(f)" class="parent-label">ذیل {{parentField(f)?.title}}</small>
     <IndexPersonalSelect v-if="f.type==='taxonomy'||f.type==='choice'" :admin-preview="props.adminPreview" :code="f.code" :label="f.title" :content-type="contentType" :multi="f.multi" :allows-personal="f.allowsPersonal" :parent="parentFor(f)" :personal-parent-option="personalParentFor(f)" :model-value="data[f.code]" @update:model-value="setFieldValue(f,$event)"/>
     <IndexDynamicField v-else :admin-preview="props.adminPreview" :field="f" :model-value="data[f.code]" :parent="parentFor(f)" :personal-parent-option="personalParentFor(f)" :content-type="contentType" :fields="schema.fields" :form-values="data" :error="fieldErrors[f.code]" @update:model-value="setFieldValue(f,$event)"/>
    <small v-if="parentPending(f)">ابتدا {{parentField(f)?.title}} را انتخاب کنید.</small></fieldset>
   </template>
  </div>
  <div v-else-if="!hasTopicAnalysis" class="empty">برای این فرم هنوز المنتی منتشر نشده است.</div>
  <div v-if="formPages.length>1" class="page-controls"><button type="button" :disabled="pageIndex===0" @click="pageIndex--">مرحله قبل</button><span>{{pageIndex+1}} از {{formPages.length}}</span><button v-if="pageIndex<formPages.length-1" type="button" @click="nextPage">مرحله بعد</button><button v-else type="button" @click="validate()">بررسی فرم</button></div>
  <p v-if="saved" class="saved">{{saved}}</p>
 </template>
</section>
</template>

<style scoped>
.index-panel{display:grid;gap:18px}.index-head{display:flex;align-items:center;justify-content:space-between;gap:14px;background:#fff;border:1px solid #e5e8ed;border-radius:18px;padding:18px}.index-panel h2,.index-panel h3{margin:0}.index-panel p{margin:5px 0 0;color:#6c7480}.save,.section-title button{border:0;border-radius:12px;padding:10px 16px;background:#102b4e;color:white;font-weight:800;cursor:pointer}.analysis{display:grid;gap:12px}.section-title{display:flex;justify-content:space-between;align-items:end;gap:12px}.analysis-card{background:#fff;border:1px solid #e4e8ee;border-radius:18px;padding:16px}.grid,.fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.fields{background:#fff;border:1px solid #e4e8ee;border-radius:18px;padding:16px}.runtime-field{min-width:0}.remove{margin-top:12px;border:0;background:#fff1f1;color:#a62828;padding:7px 10px;border-radius:9px;cursor:pointer}.saved{color:#087b56;font-weight:800}.loading,.empty{padding:24px;text-align:center;color:#7d8898}.error{padding:12px 14px;border-radius:12px;background:#fff1f1;color:#9e2525;font-weight:700}@media(max-width:760px){.grid,.fields{grid-template-columns:1fr}.index-head,.section-title{align-items:stretch;flex-direction:column}}

.fields{grid-template-columns:repeat(12,minmax(0,1fr))}.page-steps{display:flex;gap:8px;flex-wrap:wrap}.page-steps span{border-radius:8px;background:#f0f3f7;color:#687b92;padding:8px 12px}.page-steps .active{background:#102b4e;color:#fff}.page-controls{display:flex;justify-content:space-between;align-items:center;border-top:1px solid #e5ebf1;padding-top:12px}.page-controls button{border:0;border-radius:8px;background:#102b4e;color:#fff;padding:9px 16px}.page-controls button:disabled{opacity:.4}@media(max-width:760px){.fields{grid-template-columns:1fr}.runtime-field{grid-column:1/-1!important}}.index-panel :deep(.hidden-field){opacity:.7}
.tree-runtime-field{border:0;padding:0;margin:0;min-width:0;display:grid;gap:7px}.tree-runtime-field[data-depth]:not([data-depth="0"]){border-inline-start:2px solid #b7cee4;padding-inline-start:12px;grid-column:1/-1}.tree-runtime-field:disabled{opacity:.55}.parent-label{color:#39658c;font-weight:700}.grid{grid-template-columns:repeat(2,minmax(0,1fr))}
</style>
