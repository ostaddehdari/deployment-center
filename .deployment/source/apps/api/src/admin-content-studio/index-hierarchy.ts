export interface HierarchyNode {key:string;parentKey:string|null}
export const MAX_INDEX_DEPTH=3
export function hierarchyDepth(nodes:HierarchyNode[],key:string):number {
 const map=new Map(nodes.map(n=>[n.key,n]));const seen=new Set<string>();let depth=0;let node=map.get(key)
 while(node?.parentKey){if(seen.has(node.key))throw new Error('رابطه دوری در نمایه‌ها مجاز نیست.');seen.add(node.key);node=map.get(node.parentKey);if(!node)throw new Error('نمایه والد در همین فرم وجود ندارد.');depth++;if(depth>MAX_INDEX_DEPTH)throw new Error('حداکثر سه سطح زیرشاخه زیر نمایه اصلی مجاز است.')}
 return depth
}
export function validateHierarchy(nodes:HierarchyNode[]):void {
 if(new Set(nodes.map(n=>n.key)).size!==nodes.length)throw new Error('کلید نمایه‌ها باید یکتا باشد.')
 for(const n of nodes)hierarchyDepth(nodes,n.key)
}
export function hierarchyOrder<T extends HierarchyNode>(nodes:T[]):T[]{
 validateHierarchy(nodes);const out:T[]=[];const visit=(parent:string|null)=>{for(const n of nodes)if((n.parentKey||null)===parent){out.push(n);visit(n.key)}};visit(null);return out
}
export function descendants(nodes:HierarchyNode[],key:string):string[]{
 const found:string[]=[];const visit=(k:string)=>{for(const n of nodes)if(n.parentKey===k&&!found.includes(n.key)){found.push(n.key);visit(n.key)}};visit(key);return found
}
