<script setup lang="ts">
import type { ContentTypeCode } from '~/types/content'
import type { IndexOption } from '~/composables/useIndexRuntime'

const props=defineProps<{code:string;label:string;contentType?:ContentTypeCode;modelValue:unknown;multi?:boolean;allowsPersonal?:boolean;parent?:string;personalParentOption?:IndexOption|null;adminPreview?:boolean;placeholder?:string;helpText?:string;required?:boolean}>()
const emit=defineEmits<{(e:'update:modelValue',value:IndexOption|IndexOption[]|null):void}>()
const api=useIndexRuntime(props.adminPreview?'admin-preview':'user')
const q=ref(''),items=ref<IndexOption[]>([]),busy=ref(false),open=ref(false),selected=ref<IndexOption[]>([])

let requestSequence=0
const refresh=async()=>{const request=++requestSequence;busy.value=true;items.value=[];try{const r=await api.options(props.code,q.value,props.parent||'',props.personalParentOption,props.contentType);if(request===requestSequence)items.value=r.items||[]}finally{if(request===requestSequence)busy.value=false}}
watch(()=>props.modelValue,v=>{selected.value=Array.isArray(v)?(v as IndexOption[]):(v?[v as IndexOption]:[])},{immediate:true,deep:true})
watch(q,()=>{open.value=true;void refresh()})
watch(()=>[props.parent,props.personalParentOption?.id,props.personalParentOption?.scope],()=>{items.value=[];requestSequence++;if(open.value)void refresh()})
const choose=(x:IndexOption)=>{if(props.multi){if(!selected.value.some(y=>y.id===x.id&&y.scope===x.scope))selected.value=[...selected.value,x]}else selected.value=[x];emit('update:modelValue',props.multi?selected.value:(selected.value[0]||null));q.value='';open.value=false}
const remove=(x:IndexOption)=>{selected.value=selected.value.filter(y=>!(y.id===x.id&&y.scope===x.scope));emit('update:modelValue',props.multi?selected.value:(selected.value[0]||null))}
const canAdd=computed(()=>!props.adminPreview&&props.allowsPersonal&&q.value.trim().length>1&&!items.value.some(x=>x.title===q.value.trim()))
const add=async()=>{const parent=props.personalParentOption??null;const parentSystemTermId=parent?.scope==='system'?parent.id:undefined;const parentUserTermId=parent?.scope==='personal'?parent.id:undefined;const r=await api.addPersonal(props.code,q.value.trim(),parentSystemTermId,parentUserTermId,props.contentType);choose(r.item)}
onMounted(()=>void refresh())
</script>
<template><div class="ips"><label>{{label}} <em v-if="required">*</em></label><small v-if="helpText" class="help">{{helpText}}</small><div class="chips"><span v-for="x in selected" :key="x.scope+'-'+x.id" :class="['chip',x.scope]">{{x.title}}<small v-if="x.scope==='personal'">شخصی</small><button type="button" @click="remove(x)">×</button></span></div><div class="search"><input v-model="q" type="search" :placeholder="placeholder||`جست‌وجوی ${label}…`" @focus="open=true;refresh()"><div v-if="open" class="drop"><button v-for="x in items" :key="x.scope+'-'+x.id" type="button" @click="choose(x)"><span>{{x.title}}</span><small>{{x.scope==='personal'?'شخصی من':'عمومی'}}</small></button><button v-if="canAdd" class="add" type="button" @click="add">+ افزودن «{{q.trim()}}» به موارد شخصی من</button><p v-if="busy">در حال جست‌وجو…</p><p v-else-if="!items.length&&!canAdd">موردی پیدا نشد.</p></div></div></div></template>
<style scoped>.ips{display:grid;gap:8px}.ips>label{font-weight:800}.ips>label em{color:#b42318;font-style:normal}.help{color:#697386;line-height:1.7}.search{position:relative}.search input{width:100%;padding:12px;border:1px solid #d7dce3;border-radius:12px}.drop{position:absolute;z-index:20;top:calc(100% + 5px);right:0;left:0;max-height:280px;overflow:auto;background:white;border:1px solid #d7dce3;border-radius:14px;box-shadow:0 14px 34px #0002;padding:6px}.drop button{width:100%;display:flex;justify-content:space-between;padding:10px;border:0;background:transparent;border-radius:9px;text-align:right}.drop button:hover{background:#f4f7fa}.drop .add{color:#0a6c55;font-weight:800;background:#effaf6}.drop p{padding:8px;margin:0;color:#6c7480}.chips{display:flex;flex-wrap:wrap;gap:6px}.chip{display:inline-flex;align-items:center;gap:6px;background:#eef2f6;padding:5px 9px;border-radius:999px}.chip.personal{background:#fff4d8}.chip small{font-size:10px}.chip button{border:0;background:none;font-size:16px}</style>
