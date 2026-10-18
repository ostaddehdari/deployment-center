<script setup lang="ts">
import IndexPersonalSelect from '~/components/indexing/IndexPersonalSelect.vue'
import IndexRichText from '~/components/indexing/IndexRichText.vue'
import IndexSignature from '~/components/indexing/IndexSignature.vue'
import { derivedValue, numberValue, safeMarkup } from '~/utils/indexFieldRuntime'
import type { ContentTypeCode } from '~/types/content'
import type { IndexFieldDefinition,IndexManualOption,IndexOption } from '~/composables/useIndexRuntime'

const props=withDefaults(defineProps<{field:IndexFieldDefinition;modelValue:unknown;adminPreview?:boolean;parent?:string;personalParentOption?:IndexOption|null;contentType?:ContentTypeCode;formValues?:Record<string,unknown>;fields?:IndexFieldDefinition[];error?:string}>(),{adminPreview:false,parent:'',personalParentOption:null,contentType:'mold',formValues:()=>({}),fields:()=>[],error:''})
const emit=defineEmits<{(e:'update:modelValue',value:unknown):void}>()
const api=useIndexRuntime(props.adminPreview?'admin-preview':'user')
const runtimeItems=ref<IndexOption[]>([]),runtimeBusy=ref(false)
const f=computed(()=>props.field)
const sourceMode=computed(()=>String(f.value.sourceMode??((f.value.config?.runtime as Record<string,unknown>|undefined)?.sourceMode??'none')))
const taxonomyCode=computed(()=>String(f.value.taxonomyCode??((f.value.config?.runtime as Record<string,unknown>|undefined)?.taxonomyCode??'')))
const manualOptions=computed<IndexManualOption[]>(()=>Array.isArray(f.value.options)?f.value.options:[])
const placeholder=computed(()=>String(f.value.settings?.placeholder??''))
const helpText=computed(()=>String(f.value.settings?.helpText??''))
const config=computed<Record<string,unknown>>(()=>f.value.config??{})
const inputType=computed(()=>f.value.type==='datetime'?'datetime-local':f.value.type==='phone'?'tel':f.value.type==='duration'?'number':['email','url','password','date','time','number','color'].includes(f.value.type)?f.value.type:'text')
const objectValue=computed<Record<string,unknown>>(()=>props.modelValue&&typeof props.modelValue==='object'&&!Array.isArray(props.modelValue)?props.modelValue as Record<string,unknown>: {})
const arrayValue=computed<unknown[]>(()=>Array.isArray(props.modelValue)?props.modelValue:[])
const runtimeSelectedKey=computed(()=>{const v=props.modelValue as IndexOption|null|undefined;return v?`${v.scope}:${v.id}`:''})
const runtimeMultiKeys=computed(()=>new Set(arrayValue.value.map(v=>{const x=v as IndexOption;return `${x.scope}:${x.id}`})))
const manualMultiValues=computed(()=>new Set(arrayValue.value.map(v=>String(v))))
const rangeMin=computed(()=>Number((f.value.validation??{}).min??(config.value.min??0)))
const rangeMax=computed(()=>Number((f.value.validation??{}).max??(config.value.max??100)))
const localError=ref(''),fileBusy=ref(false),searchTerm=ref(''),searchOpen=ref(false)
const filteredOptions=computed(()=>manualOptions.value.filter(o=>(o.label+' '+o.value).toLocaleLowerCase('fa').includes(searchTerm.value.toLocaleLowerCase('fa'))))
const columns=computed<{key:string;label:string}[]>(()=>Array.isArray(config.value.columns)&&config.value.columns.length?config.value.columns as {key:string;label:string}[]:[{key:'value',label:'مقدار'}])
const amount=computed(()=>derivedValue(f.value,props.fields,props.formValues))
const money=(n:unknown)=>new Intl.NumberFormat('fa-IR',{maximumFractionDigits:2}).format(numberValue(n))+' '+String(config.value.currency??'تومان')
const safeImage=(v:unknown)=>{const s=String(v??'');return /^(https?:\/\/|\/(?!\/))/.test(s)?s:''}
const multiFile=computed(()=>Boolean(config.value.multiple??f.value.multi))
const fileItems=computed(()=>(Array.isArray(props.modelValue)?props.modelValue:props.modelValue?[props.modelValue]:[]) as {id?:string;name:string;size:number;preview?:boolean}[])
watch(amount,v=>{if(v!==null&&!Object.is(v,props.modelValue))emit('update:modelValue',v)},{immediate:true})

let runtimeRequest=0
const loadRuntime=async()=>{const request=++runtimeRequest;runtimeItems.value=[];
 if(sourceMode.value!=='runtime_taxonomy'||!taxonomyCode.value||['searchable_select','multiselect','tags'].includes(f.value.type))return
 runtimeBusy.value=true
 try{const r=await api.options(taxonomyCode.value,'',props.parent||'',props.personalParentOption,props.contentType);if(request===runtimeRequest)runtimeItems.value=r.items??[]}
 catch(e:unknown){localError.value=e instanceof Error?e.message:'دریافت گزینه‌ها انجام نشد.'}
 finally{if(request===runtimeRequest)runtimeBusy.value=false}
}
watch([taxonomyCode,sourceMode,()=>props.parent,()=>props.personalParentOption?.id,()=>props.personalParentOption?.scope],()=>void loadRuntime())
onMounted(()=>void loadRuntime())

const runtimeSingle=(key:string)=>emit('update:modelValue',runtimeItems.value.find(x=>`${x.scope}:${x.id}`===key)??null)
const toggleRuntime=(item:IndexOption,checked:boolean)=>{const list=[...arrayValue.value] as IndexOption[];const key=`${item.scope}:${item.id}`;emit('update:modelValue',checked?[...list.filter(x=>`${x.scope}:${x.id}`!==key),item]:list.filter(x=>`${x.scope}:${x.id}`!==key))}
const toggleManual=(value:string,checked:boolean)=>{const list=[...manualMultiValues.value];emit('update:modelValue',checked?[...list.filter(x=>x!==value),value]:list.filter(x=>x!==value))}
const updateObject=(key:string,value:unknown)=>emit('update:modelValue',{...objectValue.value,[key]:value})
const addRepeater=()=>{if(arrayValue.value.length<Number(config.value.maxRows??100))emit('update:modelValue',[...arrayValue.value,f.value.type==='list'?{}:''])}
const updateRepeater=(index:number,value:unknown)=>{const list=[...arrayValue.value];list[index]=value;emit('update:modelValue',list)}
const updateCell=(index:number,key:string,value:string)=>updateRepeater(index,{...(arrayValue.value[index] as Record<string,unknown>??{}),[key]:value})
const removeRepeater=(index:number)=>emit('update:modelValue',arrayValue.value.filter((_,i)=>i!==index))
const updateTags=(value:string)=>emit('update:modelValue',value.split(/[،,\n]/).map(x=>x.trim()).filter(Boolean))
const filePicked=async(event:Event)=>{
 const input=event.target as HTMLInputElement,files=Array.from(input.files??[]);if(!files.length)return
 fileBusy.value=true;localError.value=''
 try{if(files.some(x=>x.size>Number(config.value.maxFileMB??1)*1048576))throw Error('اندازه فایل بیشتر از حد مجاز است.');if(files.length+(multiFile.value?fileItems.value.length:0)>Number(config.value.maxFiles??5))throw Error('تعداد فایل‌ها بیشتر از حد مجاز است.');const uploaded=[];for(const file of files)uploaded.push(props.adminPreview?{name:file.name,size:file.size,preview:true}:await api.uploadFile(props.contentType,f.value.key??f.value.code,file));emit('update:modelValue',multiFile.value?[...fileItems.value,...uploaded]:uploaded[0]??null)}
 catch(e:unknown){localError.value=e instanceof Error?e.message:'بارگذاری انجام نشد.'}finally{fileBusy.value=false;input.value=''}
}
const removeFile=(index:number)=>emit('update:modelValue',multiFile.value?fileItems.value.filter((_,i)=>i!==index):null)
const download=async(item:{id?:string;name:string})=>{if(!item.id)return;try{await api.downloadFile(item.id,item.name)}catch{localError.value='دریافت فایل انجام نشد.'}}
const inputValue=()=>typeof props.modelValue==='string'||typeof props.modelValue==='number'?props.modelValue:''
const updateGroup=(event:Event)=>{try{emit('update:modelValue',JSON.parse((event.target as HTMLTextAreaElement).value))}catch{}}
const textValue=(event:Event)=>String((event.target as HTMLInputElement|HTMLTextAreaElement|HTMLSelectElement).value??'')
const checkedValue=(event:Event)=>Boolean((event.target as HTMLInputElement).checked)
const selectedValues=(event:Event)=>Array.from((event.target as HTMLSelectElement).selectedOptions).map(o=>o.value)
const chooseManual=(o:IndexManualOption)=>{emit('update:modelValue',o.value);searchTerm.value='';searchOpen.value=false}
const numberInput=(event:Event)=>{const s=textValue(event);emit('update:modelValue',s===''?null:numberValue(s))}
</script>

<template>
<div v-if="f.type!=='hidden'||adminPreview" class="dynamic-field" :data-field="f.code" :class="[`kind-${f.type}`,{layout:['section','html','page'].includes(f.type),'has-error':error||localError}]">
 <template v-if="f.type==='section'">
  <div class="section-block"><h3>{{f.title}}</h3><p v-if="helpText">{{helpText}}</p></div>
 </template>
 <template v-else-if="f.type==='html'">
  <div class="html-block"><strong>{{f.title}}</strong><div v-html="safeMarkup(config.html||helpText)"/></div>
 </template>
 <template v-else-if="f.type==='page'">
  <div class="page-break"><span>شکست صفحه</span><b>{{f.title}}</b></div>
 </template>
 <template v-else-if="f.type==='hidden'">
  <div class="hidden-field"><span>فیلد مخفی</span><b>{{f.title}}</b><input type="hidden" :value="String(modelValue??'')"></div>
 </template>

 <template v-else>
  <label v-if="!(sourceMode==='runtime_taxonomy'&&taxonomyCode&&['searchable_select','multiselect','tags'].includes(f.type))" class="field-label">{{f.title}} <em v-if="f.required">*</em></label>
  <small v-if="helpText" class="help">{{helpText}}</small>

  <IndexPersonalSelect
   v-if="sourceMode==='runtime_taxonomy'&&taxonomyCode&&['searchable_select','multiselect','tags'].includes(f.type)"
   :admin-preview="adminPreview" :code="taxonomyCode" :label="f.title" :required="f.required" :placeholder="placeholder"
   :help-text="helpText" :multi="f.type!=='searchable_select'||f.multi" :allows-personal="f.allowsPersonal"
   :content-type="contentType" :parent="parent" :personal-parent-option="personalParentOption" :model-value="modelValue"
   @update:model-value="emit('update:modelValue',$event)"
  />

  <template v-else-if="sourceMode==='runtime_taxonomy'&&taxonomyCode&&f.type==='select'">
   <select :value="runtimeSelectedKey" @change="runtimeSingle(textValue($event))">
    <option value="">{{placeholder||'انتخاب کنید'}}</option>
    <option v-for="x in runtimeItems" :key="x.scope+'-'+x.id" :value="x.scope+':'+x.id">{{x.title}}{{x.scope==='personal'?' — شخصی':''}}</option>
   </select><small v-if="runtimeBusy">در حال دریافت گزینه‌ها…</small>
  </template>

  <div v-else-if="sourceMode==='runtime_taxonomy'&&taxonomyCode&&f.type==='radio'" class="choices">
   <label v-for="x in runtimeItems" :key="x.scope+'-'+x.id"><input type="radio" :name="f.code" :checked="runtimeSelectedKey===x.scope+':'+x.id" @change="runtimeSingle(x.scope+':'+x.id)">{{x.title}}</label>
  </div>
  <div v-else-if="sourceMode==='runtime_taxonomy'&&taxonomyCode&&f.type==='checkbox'" class="choices">
   <label v-for="x in runtimeItems" :key="x.scope+'-'+x.id"><input type="checkbox" :checked="runtimeMultiKeys.has(x.scope+':'+x.id)" @change="toggleRuntime(x,checkedValue($event))">{{x.title}}</label>
  </div>

  <select v-else-if="f.type==='select'" :value="String(modelValue??'')" @change="emit('update:modelValue',textValue($event))">
   <option value="">{{placeholder||'انتخاب کنید'}}</option><option v-for="o in manualOptions" :key="o.value" :value="o.value">{{o.label}}</option>
  </select>
  <select v-else-if="f.type==='multiselect'" multiple :value="arrayValue.map(String)" @change="emit('update:modelValue',selectedValues($event))">
   <option v-for="o in manualOptions" :key="o.value" :value="o.value">{{o.label}}</option>
  </select>
  <div v-else-if="f.type==='radio'" class="choices"><label v-for="o in manualOptions" :key="o.value"><input type="radio" :name="f.code" :checked="String(modelValue??'')===o.value" @change="emit('update:modelValue',o.value)">{{o.label}}</label></div>
  <div v-else-if="f.type==='checkbox'" class="choices"><label v-for="o in manualOptions" :key="o.value"><input type="checkbox" :checked="manualMultiValues.has(o.value)" @change="toggleManual(o.value,checkedValue($event))">{{o.label}}</label></div>
  <div v-else-if="f.type==='searchable_select'" class="manual-search"><div v-if="modelValue" class="selected-choice">{{manualOptions.find(o=>o.value===modelValue)?.label??modelValue}}<button type="button" @click="emit('update:modelValue',null)">×</button></div><input v-model="searchTerm" type="search" :aria-label="f.title" :placeholder="placeholder||'جستجو و انتخاب گزینه'" @focus="searchOpen=true" @input="searchOpen=true" @keydown.escape="searchOpen=false" @keydown.enter.prevent="filteredOptions[0]&&chooseManual(filteredOptions[0])"><div v-if="searchOpen" class="search-options"><button v-for="o in filteredOptions" :key="o.value" type="button" @click="chooseManual(o)">{{o.label}}</button><small v-if="!filteredOptions.length">موردی پیدا نشد.</small><button type="button" @click="searchOpen=false">بستن</button></div></div>
  <textarea v-else-if="f.type==='textarea'" :aria-label="f.title" :rows="Number(config.rows??4)" :maxlength="Number(f.validation?.maxLength)||undefined" :value="String(modelValue??'')" :placeholder="placeholder" @input="emit('update:modelValue',textValue($event))"/>
  <IndexRichText v-else-if="f.type==='richtext'" :model-value="modelValue" :placeholder="placeholder" @update:model-value="emit('update:modelValue',$event)"/>
  <label v-else-if="f.type==='boolean'||f.type==='consent'" class="boolean"><input type="checkbox" :checked="Boolean(modelValue)" @change="emit('update:modelValue',checkedValue($event))"><span>{{placeholder||f.title}}</span></label>
  <div v-else-if="f.type==='range'" class="range-control"><input type="range" :aria-label="f.title" :min="rangeMin" :max="rangeMax" :step="Number(config.step??1)" :value="Number(modelValue??rangeMin)" @input="numberInput"><output>{{modelValue??rangeMin}}</output></div>
  <input v-else-if="f.type==='tags'" :value="arrayValue.join('، ')" :placeholder="placeholder||'برچسب‌ها را با ویرگول جدا کنید'" @input="updateTags(textValue($event))">
  <div v-else-if="f.type==='file'" class="file-field"><input type="file" :aria-label="f.title" :disabled="fileBusy" :accept="String(config.accept??'')" :multiple="multiFile" @change="filePicked"><small v-if="fileBusy">در حال بارگذاری…</small><small v-if="adminPreview">فایل انتخابی در پیش‌نمایش روی سرور ذخیره نمی‌شود.</small><div v-for="(item,i) in fileItems" :key="item.id??i" class="uploaded"><button type="button" :disabled="!item.id" @click="download(item)">{{item.name}}</button><small>{{Math.ceil(item.size/1024)}} KB</small><button type="button" @click="removeFile(i)">حذف از فیلد</button></div></div>
  <input v-else-if="f.type==='reference'||f.type==='relation'" :value="String(modelValue??'')" :placeholder="placeholder||'شناسه یا مرجع محتوا'" @input="emit('update:modelValue',textValue($event))">

  <div v-else-if="f.type==='repeater'" class="repeater"><div v-for="(row,i) in arrayValue" :key="i"><input :value="String(row??'')" @input="updateRepeater(i,textValue($event))"><button type="button" @click="removeRepeater(i)">×</button></div><button type="button" :disabled="arrayValue.length>=Number(config.maxRows??100)" @click="addRepeater">+ افزودن ردیف</button></div>
  <div v-else-if="f.type==='name'" class="object-grid"><input :value="String(objectValue.first??'')" placeholder="نام" @input="updateObject('first',textValue($event))"><input :value="String(objectValue.last??'')" placeholder="نام خانوادگی" @input="updateObject('last',textValue($event))"></div>
  <div v-else-if="f.type==='address'" class="object-grid"><label v-for="c in [{key:'country',label:'کشور'},{key:'province',label:'استان'},{key:'city',label:'شهر'},{key:'postalCode',label:'کد پستی'},{key:'address',label:'نشانی'}]" :key="c.key">{{c.label}}<input :value="String(objectValue[c.key]??'')" @input="updateObject(c.key,textValue($event))"></label></div>
  <div v-else-if="f.type==='group'" class="object-grid"><label v-for="c in columns" :key="c.key">{{c.label}}<input :value="String(objectValue[c.key]??'')" @input="updateObject(c.key,textValue($event))"></label></div>
  <div v-else-if="f.type==='list'" class="list-field"><table><thead><tr><th v-for="c in columns" :key="c.key">{{c.label}}</th><th>حذف</th></tr></thead><tbody><tr v-for="(row,i) in arrayValue" :key="i"><td v-for="c in columns" :key="c.key"><input :aria-label="c.label" :value="String((row as Record<string,unknown>)?.[c.key]??'')" @input="updateCell(i,c.key,textValue($event))"></td><td><button type="button" @click="removeRepeater(i)">×</button></td></tr></tbody></table><button type="button" :disabled="arrayValue.length>=Number(config.maxRows??100)" @click="addRepeater">+ افزودن ردیف</button></div>
  <div v-else-if="f.type==='image_choice'" class="image-choices"><button v-for="o in manualOptions" :key="o.value" type="button" :class="{picked:String(modelValue??'')===o.value}" :aria-pressed="String(modelValue??'')===o.value" @click="emit('update:modelValue',o.value)"><img v-if="safeImage((config.optionImages as Record<string,unknown>)?.[o.value])" :src="safeImage((config.optionImages as Record<string,unknown>)?.[o.value])" alt=""><b>{{o.label}}</b></button></div>
  <div v-else-if="f.type==='rating'" class="rating" role="radiogroup" :aria-label="f.title"><button v-for="n in Math.min(10,Math.max(2,Number(config.stars??5)))" :key="n" type="button" role="radio" :aria-label="`${n} ستاره`" :aria-checked="Number(modelValue)===n" :class="{filled:Number(modelValue)>=n}" @click="emit('update:modelValue',n)">★</button></div>
  <IndexSignature v-else-if="f.type==='signature'" :model-value="modelValue" @update:model-value="emit('update:modelValue',$event)"/>
  <div v-else-if="f.type==='product'" class="product"><span>قیمت واحد: {{money(config.price)}}</span><label v-if="!config.quantityField">تعداد<input type="number" min="0" step="1" :value="Number(modelValue??1)" @input="numberInput"></label></div>
  <label v-else-if="f.type==='shipping'" class="boolean"><input type="checkbox" :checked="Boolean(modelValue)" @change="emit('update:modelValue',checkedValue($event))">{{money(config.price)}}</label>
  <select v-else-if="f.type==='price_option'" :value="String(modelValue??'')" @change="emit('update:modelValue',textValue($event))"><option value="">انتخاب کنید</option><option v-for="o in manualOptions" :key="o.value" :value="o.value">{{o.label}} · {{money((config.optionPrices as Record<string,unknown>)?.[o.value])}}</option></select>
  <output v-else-if="f.type==='calculation'||f.type==='total'" class="calculated">{{amount===null?'فرمول نامعتبر':f.type==='total'?money(amount):new Intl.NumberFormat('fa-IR').format(amount)}}</output>
  <input v-else-if="f.type==='quantity'" type="number" :aria-label="f.title" min="0" step="1" :value="inputValue()" @input="numberInput">
  <input v-else :type="inputType" :aria-label="f.title" :min="f.validation?.min as string" :max="f.validation?.max as string" :step="String(config.step??'any')" :maxlength="Number(f.validation?.maxLength)||undefined" :value="inputValue()" :placeholder="placeholder" @input="f.type==='number'||f.type==='duration'?numberInput($event):emit('update:modelValue',textValue($event))">
 </template>
 <small v-if="error||localError" class="field-error" role="alert">{{error||localError}}</small>
</div>
</template>

<style scoped>
.dynamic-field{display:grid;gap:7px;min-width:0}.field-label{font-weight:800;color:#24364d}.field-label em{color:#b42318;font-style:normal}.help{color:#6f7c8e;line-height:1.7}.dynamic-field input,.dynamic-field textarea,.dynamic-field select{font:inherit;border:1px solid #d7dce3;border-radius:11px;padding:10px;background:#fff;min-width:0}.dynamic-field textarea{min-height:92px;resize:vertical}.dynamic-field select[multiple]{min-height:120px}.choices{display:flex;flex-wrap:wrap;gap:9px}.choices label,.boolean{display:flex;align-items:center;gap:7px;border:1px solid #e2e7ed;border-radius:10px;padding:8px 10px}.choices input,.boolean input{width:auto}.repeater{display:grid;gap:7px}.repeater>div{display:flex;gap:6px}.repeater input{flex:1}.repeater button{border:1px solid #dce2e9;background:#fff;border-radius:8px;padding:7px 10px}.object-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}.section-block{padding:12px 14px;border-right:4px solid #102b4e;background:#f5f8fb;border-radius:10px}.section-block h3{margin:0}.section-block p{margin:5px 0 0;color:#718096}.html-block{padding:12px;border:1px dashed #bac5d2;border-radius:10px;background:#fbfcfd}.page-break{display:flex;align-items:center;gap:12px;color:#6d7888}.page-break:after{content:'';height:1px;background:#ccd4de;flex:1}.page-break span{font-size:11px;background:#eef2f6;border-radius:999px;padding:4px 8px}.hidden-field{display:flex;gap:8px;align-items:center;color:#7b8796;background:#f6f7f9;padding:9px;border-radius:9px}.hidden-field span{font-size:10px;background:#e8ebef;padding:3px 6px;border-radius:999px}@media(max-width:640px){.object-grid{grid-template-columns:1fr}}

.dynamic-field input,.dynamic-field textarea,.dynamic-field select{box-sizing:border-box;max-width:100%}.field-error{color:#ac2b2b}.has-error{outline:1px solid #e6b1b1;border-radius:9px;padding:7px}.object-grid label{display:grid;gap:5px}.manual-search{position:relative}.search-options{position:absolute;top:100%;inset-inline:0;z-index:10;max-height:220px;overflow:auto;display:grid;padding:6px;border:1px solid #dce2e9;border-radius:10px;background:#fff;box-shadow:0 10px 30px #0002}.search-options button{border:0;background:#fff;padding:9px;text-align:right}.search-options button:hover{background:#edf5ff}.selected-choice{display:flex;justify-content:space-between;padding:7px;background:#edf5ff;border-radius:8px}.selected-choice button{border:0;background:none}.image-choices{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:8px}.image-choices button{border:2px solid #e3e8ee;border-radius:11px;background:#fff;padding:8px;display:grid;gap:8px}.image-choices img{width:100%;height:110px;object-fit:cover;border-radius:7px}.image-choices button.picked{border-color:#1a66b1;background:#eef6ff}.rating{display:flex;direction:ltr;justify-content:flex-end}.rating button{border:0;background:none;color:#cbd1d9;font-size:32px}.rating button.filled{color:#d7931f}.file-field{display:grid;gap:8px}.uploaded{display:flex;gap:7px;align-items:center;background:#f5f8fc;padding:7px;border-radius:8px}.uploaded button{overflow-wrap:anywhere;border:1px solid #dce2e9;background:#fff;border-radius:7px;padding:6px}.list-field{overflow-x:auto}.list-field table{width:100%;border-collapse:collapse}.list-field th,.list-field td{padding:5px;border:1px solid #e4e9ef}.list-field input{width:100%}.list-field button{border:1px solid #dce2e9;background:#fff;border-radius:7px;padding:7px}.product{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px;border-radius:10px;background:#f5f9fd}.product input{max-width:100px}.calculated{font-size:22px;font-weight:900;background:#edf8f3;color:#12654c;padding:15px;border-radius:10px}
</style>
