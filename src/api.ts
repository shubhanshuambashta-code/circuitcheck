export interface ObjectEvidence {uuid?:string;description?:string;pos?:{x:number;y:number}}
export interface Finding {
 id:string;title:string;source:string;category:string;rule:string;severity:string;excluded:boolean;
 file:string;sheet?:string;objects:ObjectEvidence[];object_ids:string[];position?:{x:number;y:number};layer?:string;net?:string;
 measured?:{value:number;unit:string};required?:{value:number;unit:string};evidence:string;explanation:string;suggestion:string;
 repair?:{kind:string;object_id:string;from:number;to:number;file:string};verification:string;rule_source:string;
}
export interface Preview {artifact:string;view_box:number[];kind:string;file:string;bounds_mm?:number[];mapping?:{scale_x:number;scale_y:number;offset_x:number;offset_y:number;convention:string}}
export interface Result {status:string;engine_version:string;checks:{name:string;status:string;message:string}[];findings:Finding[];previews:Preview[];project_hash:string;rules_fingerprint:string;notices:{kind:string;message:string}[];finished_at:number;cached:boolean;zone_policy:string}
export interface Manifest {files:{path:string;size:number;kind:string}[];root:string;candidates:string[];requires_selection:boolean;notices:{kind:string;message:string}[]}
export interface Revision {id:string;parent_id?:string;hash:string;created:number;manifest:Manifest;result?:Result}
export interface Job {id:string;revision_id:string;status:string;stage:string;error?:string;updated:number}
export interface Project {id:string;name:string;example:number;current_revision:string;revision:Revision;revisions:Revision[];jobs:Job[]}
export interface ProjectSummary {id:string;name:string;example:number;current_revision:string;created:number}
export interface Comparison {resolved:Finding[];remaining:Finding[];new:Finding[];complete:boolean}
export interface Repair {repair_id:string;candidate_id:string;job_id:string;operation:NonNullable<Finding['repair']>}
export async function api<T=any>(path:string,body?:unknown,method?:string):Promise<T> {
 const form=body instanceof FormData;
 const response=await fetch('/api'+path,{method:method||(body?'POST':'GET'),headers:{'X-CircuitCheck':'1',...(!form&&body?{'Content-Type':'application/json'}:{})},body:body?(form?body:JSON.stringify(body)):undefined}).catch(()=>{throw new Error('Cannot reach the local server. Start CircuitCheck, keep its server window open, and try again.')});
 if(!response.ok){let detail='Request failed. Please try again.';try{const error=await response.json();detail=typeof error.detail==='string'?error.detail:JSON.stringify(error.detail)}catch{}throw new Error(detail)}
 return response.json();
}
export const artifactUrl=(pid:string,rid:string,name:string)=>`/api/projects/${pid}/revisions/${rid}/artifacts/${name.split('/').map(encodeURIComponent).join('/')}`;
export async function download(url:string){const r=await fetch(url);if(!r.ok){const e=await r.json();throw new Error(e.detail||'Export failed')}const blob=await r.blob();const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=r.headers.get('content-disposition')?.match(/filename="([^"]+)"/)?.[1]||'circuitcheck-export';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}
