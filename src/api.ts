export const demoMode=import.meta.env.MODE==='pages';
export interface BoardObject {id:string;kind:string;shape:string;points:number[][];width?:number;radius?:number;layer?:string;net?:string;reference?:string;pad?:string;envelope?:boolean;signature:string}
export interface Geometry {version:string;objects:BoardObject[];nets:string[];limitations:string[]}
export interface Note {id:string;kind:string;body:string;revision_id:string;created:number;scope_valid:boolean}
export interface Coverage {id:string;name:string;status:string;count:number|null;excluded_count?:number;message:string;basis?:string}
export interface RuleProfile {code:string;name:string;version:string;manufacturer?:string;source?:string;scope?:string;order_reference?:string;constraints?:Record<string,number>;fingerprint?:string}
export interface ObjectEvidence {uuid?:string;description?:string;pos?:{x:number;y:number}}
export interface Finding {
 id:string;title:string;source:string;category:string;rule:string;severity:string;excluded:boolean;
 file:string;sheet?:string;objects:ObjectEvidence[];object_ids:string[];position?:{x:number;y:number};layer?:string;net?:string;
 measured?:{value:number;unit:string};required?:{value:number;unit:string};evidence:string;explanation:string;suggestion:string;
 repair?:{kind:string;object_id:string;from:number;to:number;file:string};verification:string;rule_source:string;
 classification?:string;classification_basis?:string;board_object_ids?:string[];highlight_status?:string;highlight_message?:string;references?:string[];nets?:string[];review_notes?:Note[];evidence_fingerprint?:string;schematic_object_ids?:string[];schematic_preview?:string;schematic_file?:string;schematic_highlight_message?:string;sheet_uuid?:string;
}
export interface Preview {artifact:string;view_box:number[];kind:string;file:string;bounds_mm?:number[];sheet_path?:string;sheet_number?:string;sheet_uuid?:string;mapping?:{scale_x:number;scale_y:number;offset_x:number;offset_y:number;convention:string}}
export interface Result {status:string;engine_version:string;checks:{name:string;status:string;message:string}[];findings:Finding[];previews:Preview[];project_hash:string;rules_fingerprint:string;notices:{kind:string;message:string}[];finished_at:number;cached:boolean;zone_policy:string;geometry?:Geometry;schematic_geometry?:Record<string,Geometry>;coverage?:Coverage[];provenance?:{adapter:string;normalizer:string;geometry:string;engineering_engine:string;explanation_engine:string;ai_role:string;project_hash:string;rules_fingerprint:string;rule_profile:RuleProfile}}
export interface Manifest {files:{path:string;size:number;kind:string}[];root:string;candidates:string[];requires_selection:boolean;notices:{kind:string;message:string}[];rule_profile?:RuleProfile}
export interface Revision {id:string;parent_id?:string;hash:string;created:number;manifest:Manifest;result?:Result}
export interface Job {id:string;revision_id:string;status:string;stage:string;error?:string;updated:number}
export interface Project {id:string;name:string;example:number;current_revision:string;revision:Revision;revisions:Revision[];jobs:Job[]}
export interface ProjectSummary {id:string;name:string;example:number;current_revision:string;created:number}
export interface ObjectChange {id:string;kind:string;reference?:string;status:string;before?:BoardObject;after?:BoardObject}
export interface Comparison {resolved:Finding[];remaining:Finding[];new:Finding[];complete:boolean;resolution_verified?:boolean;rules_changed?:boolean;profile_changed?:boolean;engine_changed?:boolean;coverage_changed?:boolean;unstable_identity?:boolean;geometry?:{available:boolean;objects:ObjectChange[];components:ObjectChange[];connections:ObjectChange[];note:string};changed_evidence?:{before:Finding;after:Finding}[]}
export interface Repair {repair_id:string;candidate_id:string;job_id:string;operation:NonNullable<Finding['repair']>}
export async function api<T=any>(path:string,body?:unknown,method?:string):Promise<T> {
 if(demoMode)return demoApi(path,body,method);
 const form=body instanceof FormData;
 const response=await fetch('/api'+path,{method:method||(body?'POST':'GET'),headers:{'X-CircuitCheck':'1',...(!form&&body?{'Content-Type':'application/json'}:{})},body:body?(form?body:JSON.stringify(body)):undefined}).catch(()=>{throw new Error('Cannot reach the local server. Start CircuitCheck, keep its server window open, and try again.')});
 if(!response.ok){let detail='Request failed. Please try again.';try{const error=await response.json();detail=typeof error.detail==='string'?error.detail:JSON.stringify(error.detail)}catch{}throw new Error(detail)}
 return response.json();
}
export const artifactUrl=(pid:string,rid:string,name:string)=>demoMode?`${import.meta.env.BASE_URL}demo/artifacts/${rid}/${name.split('/').map(encodeURIComponent).join('/')}`:`/api/projects/${pid}/revisions/${rid}/artifacts/${name.split('/').map(encodeURIComponent).join('/')}`;
export async function download(url:string){let filename='circuitcheck-export';if(demoMode){filename=url.includes('review-report')?'recorded-review.html':url.includes('/report')?'recorded-evidence.json':url.includes('original=true')?'revision-a.zip':'revision-b.zip';url=import.meta.env.BASE_URL+'demo/'+filename;}const r=await fetch(url);if(!r.ok)throw new Error('Export unavailable. Run analysis or inspect check coverage.');const blob=await r.blob();const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=r.headers.get('content-disposition')?.match(/filename="([^"]+)"/)?.[1]||filename;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}

let demoData:Promise<any>|undefined;
async function demoApi<T>(path:string,body?:unknown,method?:string):Promise<T>{
 demoData||=fetch(import.meta.env.BASE_URL+'demo/data.json').then(r=>{if(!r.ok)throw new Error('Recorded example could not be loaded.');return r.json()});
 const data=await demoData;const input=body as any;
 if(path==='/health')return {engine_available:false,ai_available:false,tested_engine:data.project.revision.result.engine_version,deployment:'recorded example'} as T;
 if(path==='/projects'&&!body)return [{id:data.project.id,name:data.project.name,example:1,current_revision:data.project.current_revision,created:data.project.created}] as T;
 if(path==='/sample')return {project_id:data.project.id,revision_id:data.project.current_revision} as T;
 if(path==='/rule-profiles')return data.profiles as T;
 if(path===`/projects/${data.project.id}`&&!body)return structuredClone(data.project) as T;
 const revision=path.match(/^\/projects\/[^/]+\/revisions\/([^/?]+)$/);
 if(revision&&!body&&data.revisions[revision[1]])return structuredClone(data.revisions[revision[1]]) as T;
 if(path.includes('/compare?')){const params=new URLSearchParams(path.split('?')[1]);const key=params.get('before')+'..'+params.get('after');if(data.comparisons[key])return structuredClone(data.comparisons[key]) as T;throw new Error('Choose two different recorded revisions.');}
 if(path.endsWith('/chat')){const result=data.revisions[input?.revision_id||data.project.current_revision]?.result;const f=result?.findings.find((f:Finding)=>f.id===input?.finding_id);if(!f)throw new Error('Select a recorded finding.');return {provider:'deterministic',explanation_engine:'deterministic-evidence-1.0',answer:f.evidence+' '+f.suggestion,hypotheses:[],missing_information:['Recorded engineering evidence. No AI request or live check was made.']} as T;}
 throw new Error(method==='DELETE'?'Project deletion is available in the local app.':'This is a recorded example. Run the local app for uploads, native checking, review notes and approved file edits.');
}
