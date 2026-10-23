import io
import json
import re
import zipfile
from pathlib import Path
from backend import db
from backend.worker import tick
from backend.storage import LocalStorage,fingerprint

def finished(client,p):
    assert tick()
    r=client.get('/api/projects/'+p['project_id']).json()
    assert r['jobs'][0]['status']!='failed',r['jobs'][0]
    return r

def test_real_clean_board(engine,client,upload_fixture):
    p=upload_fixture('valid');r=finished(client,p)
    result=r['revision']['result']
    assert result['status']=='completed'
    assert result['findings']==[]
    assert result['engine_version']=='10.0.7'
    assert any(c['name']=='ERC' and c['status']=='skipped' for c in result['checks'])
    assert len(result['previews'][0]['layers'])==4

def test_real_erc_and_netlist(engine,client,upload_fixture):
    p=upload_fixture('erc');r=finished(client,p)
    result=r['revision']['result']
    assert any(f['rule']=='pin_not_connected' and f['object_ids'] for f in result['findings']),result
    base=f"/api/projects/{p['project_id']}/revisions/{p['revision_id']}/artifacts/"
    xml=client.get(base+'netlist.xml')
    assert xml.status_code==200 and '<export' in xml.text
    assert any(p['kind']=='schematic' for p in result['previews'])

def test_valid_schematic(engine,client,upload_fixture):
    p=upload_fixture('valid_schematic');r=finished(client,p)
    assert not r['revision']['result']['findings']

def test_real_schematic_board_parity(engine,client):
    folder=Path(__file__).resolve().parents[1]/'fixtures'
    inputs=[('files',('valid.kicad_pcb',(folder/'valid/valid.kicad_pcb').read_bytes())),
            ('files',('valid.kicad_pro',(folder/'valid/valid.kicad_pro').read_bytes())),
            ('files',('valid.kicad_sch',(folder/'valid_schematic/valid.kicad_sch').read_bytes()))]
    response=client.post('/api/projects',files=inputs)
    assert response.status_code==202,response.text
    r=finished(client,response.json())
    assert r['revision']['result']['status']=='completed'
    assert any(c['name']=='Schematic / PCB parity' and c['status']=='completed' for c in r['revision']['result']['checks'])

def test_real_hierarchical_schematic(engine,client):
    folder=Path(__file__).resolve().parents[1]/'fixtures/hierarchy'
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as z:
        for p in folder.rglob('*'):
            if p.is_file():z.write(p,p.relative_to(folder).as_posix())
    response=client.post('/api/projects',files=[('files',('hierarchy.zip',stream.getvalue()))])
    assert response.status_code==202,response.text
    p=response.json();r=finished(client,p)
    assert r['revision']['result']['status']=='completed',r
    assert len(r['revision']['result']['previews'])==2
    assert not any('Missing subsheet' in n['message'] for n in r['revision']['manifest']['notices'])

def test_real_custom_rules_and_missing_library(engine,client,upload_fixture):
    p=upload_fixture('custom_rules');r=finished(client,p)
    f=next(f for f in r['revision']['result']['findings'] if f['rule']=='track_width')
    assert 'Review width' in f['evidence']
    assert f['required']['value']==.35
    p=upload_fixture('missing_library');r=finished(client,p)
    assert r['revision']['result']['status']=='partial'
    assert any('Missing library' in n['message'] for n in r['revision']['manifest']['notices'])

def test_missing_hierarchy_never_clean(engine,client,upload_fixture):
    p=upload_fixture('missing');assert tick()
    r=client.get('/api/projects/'+p['project_id']).json()
    assert r['jobs'][0]['status']=='failed'
    assert r['revision']['result']['status']=='failed'
    assert any(c['name']=='ERC' and c['status']=='skipped' for c in r['revision']['result']['checks'])

def test_native_repair_full_cycle_and_download(engine,client,upload_fixture):
    p=upload_fixture('drc');r=finished(client,p);pid=p['project_id'];rid=p['revision_id']
    f=next(f for f in r['revision']['result']['findings'] if f['rule']=='track_width')
    assert f['measured']=={'value':.15,'unit':'mm'}
    assert f['required']=={'value':.25,'unit':'mm'}
    assert f['repair'] and f['position']=={'x':65.0,'y':65.0}
    original=LocalStorage().revision(pid,rid)/'source'
    old_hash=fingerprint(original)
    before=client.get(f'/api/projects/{pid}/download?original=true').content
    result=client.post(f'/api/projects/{pid}/repairs',json={'finding_id':f['id']})
    assert result.status_code==200,result.text
    repair=result.json();cid=repair['candidate_id']
    assert client.post(f"/api/projects/{pid}/repairs/{repair['repair_id']}/apply",json={}).status_code==422
    assert tick()
    proposed=client.get(f'/api/projects/{pid}/revisions/{cid}').json()
    assert proposed['result']['status']=='completed'
    assert not any(x['id']==f['id'] for x in proposed['result']['findings'])
    comparison=client.get(f'/api/projects/{pid}/compare?before={rid}&after={cid}').json()
    assert f['id'] in [x['id'] for x in comparison['resolved']]
    assert not comparison['new']
    change=client.post(f"/api/projects/{pid}/repairs/{repair['repair_id']}/apply",json={})
    assert change.status_code==200,change.text
    assert tick()
    assert client.get('/api/projects/'+pid).json()['current_revision']==cid
    assert fingerprint(original)==old_hash
    old=zipfile.ZipFile(io.BytesIO(before));new=zipfile.ZipFile(io.BytesIO(client.get(f'/api/projects/{pid}/download').content))
    assert new.read('drc.kicad_pro')==old.read('drc.kicad_pro')
    assert new.read('drc.kicad_pcb').replace(b'(width 0.25)',b'(width 0.15)')==old.read('drc.kicad_pcb')
    assert client.get(f'/api/projects/{pid}/report').status_code==200
    undo=client.post(f'/api/projects/{pid}/undo',json={})
    assert undo.status_code==200 and undo.json()['revision_id']==rid
    assert tick()
    assert client.delete('/api/projects/'+pid).status_code==200
    assert not LocalStorage().project(pid).exists()

def test_svg_coordinate_mapping_matches_known_track(engine,client,upload_fixture):
    p=upload_fixture('drc');r=finished(client,p)
    info=r['revision']['result']['previews'][0]
    assert info['mapping']['scale_x']==1 and info['mapping']['scale_y']==1
    svg=client.get(f"/api/projects/{p['project_id']}/revisions/{p['revision_id']}/artifacts/board.svg").text
    # Independent check: native fixture endpoints (65,65) and (85,65) are literal exported geometry.
    assert re.search(r'M\s*65\.0000[, ]+65\.0000.*?L\s*85\.0000[, ]+65\.0000',svg,re.S)

def test_cache_and_ai_free_explanation(engine,client,upload_fixture):
    p=upload_fixture('drc');r=finished(client,p)
    f=r['revision']['result']['findings'][0]
    answer=client.post(f"/api/projects/{p['project_id']}/chat",json={'question':'Which rule triggered this?','finding_id':f['id']})
    assert answer.status_code==200 and answer.json()['provider']=='deterministic'
    assert f['evidence'] in answer.json()['answer']
    client.post(f"/api/projects/{p['project_id']}/analyze",json={});assert tick()
    assert client.get('/api/projects/'+p['project_id']).json()['revision']['result']['cached']
