import copy
import json
from pathlib import Path
import pytest
from backend.geometry import board_index,geometry_diff,link_findings
from backend.review import build_coverage,evidence_class,annotation_scope
from backend.profiles import validate_profile
from backend.engine import compare,normalize

FIXTURES=Path(__file__).resolve().parents[1]/'fixtures'

def test_exact_track_pad_and_component_mapping():
    index=board_index((FIXTURES/'fieldnode/fieldnode.kicad_pcb').read_text())
    track=next(o for o in index['objects'] if o['kind']=='track' and o['width']==.15)
    finding={'source':'KiCad DRC','object_ids':[track['id']],'position':None}
    link_findings([finding],index)
    assert finding['board_object_ids']==[track['id']]
    assert finding['highlight_status']=='exact_objects' and finding['nets']==['GND']
    assert any(o['kind']=='component' and o['reference']=='U1' for o in index['objects'])
    pad=next(o for o in index['objects'] if o['kind']=='pad' and o['reference']=='J1' and o['pad']=='1')
    assert sum(p[0] for p in pad['points'])/4==58
    unknown={'source':'KiCad DRC','object_ids':['missing-uuid'],'position':None}
    link_findings([unknown],index)
    assert unknown['highlight_status']=='unavailable' and unknown['board_object_ids']==[]

def test_geometry_diff_reports_physical_and_net_changes():
    text=(FIXTURES/'fieldnode/fieldnode.kicad_pcb').read_text()
    a=board_index(text);b=board_index(text.replace('(at 79 60)','(at 81 60)').replace('(width 0.15)','(width 0.25)'))
    changes=geometry_diff(a,b)
    assert any(c['reference']=='R2' for c in changes['components'])
    assert any(c['kind']=='track' for c in changes['connections'])

def test_coverage_distinguishes_checked_zero_disabled_failed_and_absent():
    checks=[{'name':'DRC','status':'completed','message':'Native report'}]
    rows=build_coverage(checks,[],{'notices':[]},{})
    assert next(r for r in rows if r['id']=='copper_clearance')['count']==0
    assert next(r for r in rows if r['id']=='ERC')['status']=='not_checked'
    assert next(r for r in rows if r['id']=='ratings')['count'] is None
    disabled=build_coverage(checks,[],{'notices':[]},{'board':{'design_settings':{'rule_severities':{'clearance':'ignore'}}}})
    assert next(r for r in disabled if r['id']=='copper_clearance')['status']=='partial'
    failed=build_coverage([{'name':'DRC','status':'failed','message':'Timeout'}],[],{'notices':[]},{})
    assert next(r for r in failed if r['id']=='track_width')['count'] is None

def test_rule_changes_prevent_claiming_a_verified_fix():
    old={'status':'completed','engine_version':'10.0.7','rules_fingerprint':'a','provenance':{'normalizer':'2'},'findings':[{'id':'width','identity_status':'stable_native_ids'}]}
    new={'status':'completed','engine_version':'10.0.7','rules_fingerprint':'b','provenance':{'normalizer':'2'},'findings':[]}
    result=compare(old,new)
    assert len(result['resolved'])==1 and result['rules_changed'] and not result['resolution_verified']
    new['rules_fingerprint']='a'
    assert compare(old,new)['resolution_verified']
    old['findings'][0]['identity_status']='unresolved_native_ids'
    assert not compare(old,new)['resolution_verified']

@pytest.mark.parametrize('value',[0,-1,float('nan'),float('inf'),True,'0.1'])
def test_profiles_reject_unbounded_or_executable_values(value):
    with pytest.raises(ValueError):validate_profile({'constraints':{'track_width':value}})

def test_review_exception_scope_changes_with_evidence_or_rules():
    f={'evidence_fingerprint':'first'};r={'rules_fingerprint':'rules','engine_version':'10.0.7'}
    scope=annotation_scope(f,r)
    assert scope!=annotation_scope({**f,'evidence_fingerprint':'second'},r)
    assert scope!=annotation_scope(f,{**r,'rules_fingerprint':'new-rules'})

def test_linked_upload_preserves_project_original_and_notes(client,upload_fixture):
    from backend import db
    from backend.storage import LocalStorage
    a=upload_fixture('drc')
    with db.connect() as c:c.execute("UPDATE jobs SET status='completed' WHERE id=?",(a['job_id'],))
    finding=normalize({'violations':[{'type':'track_width','description':'min 0.25 mm; actual 0.15 mm','severity':'error','items':[{'uuid':'known-track'}]}]},'DRC','drc.kicad_pcb')[0]
    finding['evidence_fingerprint']='known'
    result={'status':'completed','engine_version':'10.0.7','rules_fingerprint':'same','findings':[finding],'checks':[]}
    with db.connect() as c:c.execute('UPDATE revisions SET result=? WHERE id=?',(json.dumps(result),a['revision_id']))
    note=client.post(f"/api/projects/{a['project_id']}/review-notes",json={'finding_id':finding['id'],'revision_id':a['revision_id'],'kind':'accepted_exception','body':'Requires independent review before manufacturing.'})
    assert note.status_code==201
    original=(LocalStorage().project(a['project_id'])/'original/drc.kicad_pcb').read_bytes()
    files=[('files',(p.name,p.read_bytes())) for p in (FIXTURES/'drc').iterdir() if p.is_file()]
    response=client.post(f"/api/projects/{a['project_id']}/revisions",files=files)
    assert response.status_code==202,response.text
    b=response.json()
    assert db.row('revisions',b['revision_id'])['parent_id']==a['revision_id']
    assert (LocalStorage().project(a['project_id'])/'original/drc.kicad_pcb').read_bytes()==original
    with db.connect() as c:c.execute('UPDATE revisions SET result=? WHERE id=?',(json.dumps(result),b['revision_id']))
    revised=client.get('/api/projects/'+a['project_id']).json()['revision']['result']['findings'][0]
    assert revised['review_notes'][0]['scope_valid']
    other=upload_fixture('valid')
    assert client.post(f"/api/projects/{other['project_id']}/review-notes",json={'finding_id':finding['id'],'revision_id':a['revision_id'],'kind':'comment','body':'wrong project'}).status_code==404

def test_unknown_manufacturer_order_code_does_not_invent_constraints(client,upload_fixture):
    from backend import db
    a=upload_fixture('drc')
    with db.connect() as c:c.execute("UPDATE jobs SET status='completed' WHERE id=?",(a['job_id'],))
    response=client.post(f"/api/projects/{a['project_id']}/rule-profile",json={'code':'unknown-order-123','order_reference':'order-123'})
    assert response.status_code==202,response.text
    profile=client.get('/api/projects/'+a['project_id']).json()['revision']['manifest']['rule_profile']
    assert profile['constraints']=={} and 'Unverified' in profile['name']

@pytest.mark.parametrize('limit',[.2,.4])
def test_native_profile_pass_and_geometry(engine,client,upload_fixture,limit):
    from backend import db,worker
    a=upload_fixture('drc');worker.tick()
    current=client.get('/api/projects/'+a['project_id']).json()
    assert current['revision']['result']['geometry']['objects']
    response=client.post(f"/api/projects/{a['project_id']}/rule-profile",json={'profile':{'name':'Test vendor','version':'1','constraints':{'track_width':limit,'clearance':.2}}})
    assert response.status_code==202,response.text
    worker.tick()
    result=client.get('/api/projects/'+a['project_id']).json()['revision']['result']
    assert next(c for c in result['coverage'] if c['id']=='fab_track_width')['status']=='checked'
    assert any(f['source']=='Fabrication DRC' and f['measured']['value']==.15 and f['required']['value']==limit for f in result['findings'])
    assert result['provenance']['rule_profile']['name']=='Test vendor'
