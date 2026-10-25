"""Evidence categories, explicit coverage, and reproducible review scope."""
import hashlib
import json
import os
from .geometry import link_findings, signature

ADAPTER_VERSION='circuitcheck-0.2.1'
NORMALIZER_VERSION='evidence-2.1'
ADVISORY_RULES={'lib_footprint_mismatch','lib_footprint_issues','lib_symbol_mismatch','lib_symbol_issues','footprint_type_mismatch','footprint_link_issues'}
GROUPS=[
 ('copper_clearance','Copper clearance',{'clearance','shorting_items','tracks_crossing'}),
 ('track_width','Track width',{'track_width'}),
 ('unconnected','Unconnected nets / track ends',{'unconnected_items','track_dangling','via_dangling','isolated_copper'}),
 ('drill','Hole size and annular rings',{'drill_out_of_range','annular_width','hole_near_hole','hole_clearance'}),
 ('board_edge','Copper to board edge',{'copper_edge_clearance','edge_clearance'}),
 ('silkscreen','Silkscreen and text',{'silk_over_copper','silk_overlap','text_height','text_thickness'}),
]

def evidence_class(f):
    if f.get('rule') in ADVISORY_RULES:return 'review_suggestion'
    if f.get('rule') in ('unknown','') or not f.get('rule'):return 'potential_concern'
    return 'confirmed_violation'

def build_coverage(checks, findings, manifest, settings):
    drc=next((c for c in checks if c['name']=='DRC'),{})
    severities=settings.get('board',{}).get('design_settings',{}).get('rule_severities',{})
    rows=[]
    for key,label,rules in GROUPS:
        disabled=[r for r in rules if severities.get(r)=='ignore']
        group=[f for f in findings if f['source']=='KiCad DRC' and f['rule'] in rules]
        status='checked' if drc.get('status')=='completed' else 'failed' if drc.get('status')=='failed' else 'not_checked'
        if disabled and status=='checked':status='partial'
        count=sum(not f.get('excluded') for f in group)
        rows.append({'id':key,'name':label,'status':status,'count':count if status in ('checked','partial') else None,
                     'excluded_count':sum(bool(f.get('excluded')) for f in group),
                     'message':('Ignored rule(s): '+', '.join(disabled)+'. Zero reports does not establish coverage of ignored rules.') if disabled else drc.get('message','No board DRC report.'),
                     'basis':'Native KiCad DRC using supplied project settings and enabled checks; no per-object pass count is inferred.'})
    for name,label in [('ERC','Schematic electrical rules'),('Schematic / PCB parity','Schematic / PCB parity')]:
        check=next((c for c in checks if c['name']==name),{})
        status={'completed':'checked','failed':'failed'}.get(check.get('status'),'not_checked')
        ignored=check.get('ignored_checks',[]) if name=='ERC' else []
        if ignored and status=='checked':status='partial'
        rows.append({'id':name,'name':label,'status':status,'count':sum(f['source']=='KiCad ERC' and not f.get('excluded') for f in findings) if name=='ERC' and status in ('checked','partial') else None,'message':check.get('message','Not evaluated.')+(' Disabled native checks: '+', '.join(ignored)+'.' if ignored else '')})
    for key,label,reason in [
        ('ratings','Component voltage / power ratings','Component ratings and operating conditions were not evaluated.'),
        ('current','Current capacity / thermal performance','No electrothermal calculation or physical validation was performed.'),
        ('simulation','Circuit function / signal integrity','No functional, timing or signal-integrity simulation was performed.'),
        ('assembly','Physical assembly / solder quality','Design files do not establish physical assembly quality.')]:
        rows.append({'id':key,'name':label,'status':'not_checked','count':None,'message':reason})
    if any(n['kind']=='missing' for n in manifest.get('notices',[])):
        for row in rows:
            if row['status']=='checked':row['status']='partial';row['message']+=' Project dependencies are missing.'
    return rows

def enrich(result, manifest, source, geometry):
    root=manifest['root']; settings={}
    p=source/(root+'.kicad_pro')
    if p.is_file():settings=json.loads(p.read_text(encoding='utf-8-sig'))
    link_findings(result['findings'],geometry,source.rglob('*.kicad_sch'))
    for f in result['findings']:
        f['classification']=evidence_class(f)
        f['classification_basis']='Native rule report; numerical values are shown only when present in the original evidence.' if f['classification']=='confirmed_violation' else 'Native library / consistency evidence requires engineering review.' if f['classification']=='review_suggestion' else 'The source did not establish a recognized rule violation.'
        f['evidence_fingerprint']=signature([f['rule'],f.get('measured'),f.get('required'),f.get('evidence'),f.get('object_signature'),f.get('objects')])
    result['geometry']=geometry
    result['coverage']=build_coverage(result['checks'],result['findings'],manifest,settings)
    unresolved=sum(f.get('identity_status')!='stable_native_ids' for f in result['findings'])
    result['coverage'].append({'id':'identity','name':'Revision object identity','status':'partial' if unresolved else 'checked','count':None,'message':f'{unresolved} finding(s) lack persistent native object IDs; these cannot establish verified fixes across revisions.' if unresolved else 'Finding objects have persistent source IDs. Unsupported geometry is labelled separately.'})
    result['provenance']={'adapter':ADAPTER_VERSION,'normalizer':NORMALIZER_VERSION,'geometry':geometry['version'],
                          'engineering_engine':'KiCad '+result['engine_version'],
                          'explanation_engine':('configured model: '+os.getenv('AI_MODEL','gpt-4.1-mini')+' · not used for checking') if os.getenv('AI_API_KEY') else 'deterministic-evidence-1.0',
                          'ai_role':'Evidence explanation only; does not create or confirm engineering findings.',
                          'project_hash':result['project_hash'],'rules_fingerprint':result['rules_fingerprint'],
                          'rule_profile':manifest.get('rule_profile') or {'code':'project','name':'Supplied KiCad project rules','version':result['rules_fingerprint'][:12]}}
    return result

def annotation_scope(finding,result):
    return signature([finding.get('evidence_fingerprint'),result.get('rules_fingerprint'),result.get('provenance',{}).get('rule_profile'),result.get('engine_version')])

def attach_reviews(project_id,result):
    from . import db
    with db.connect() as c:rows=[dict(r) for r in c.execute('SELECT * FROM review_notes WHERE project_id=? ORDER BY created',(project_id,))]
    for f in result.get('findings',[]):
        f['review_notes']=[{**r,'scope_valid':r['scope']==annotation_scope(f,result)} for r in rows if r['finding_id']==f['id']]
    return result
