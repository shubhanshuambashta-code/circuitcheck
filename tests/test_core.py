import io
import json
import stat
import time
import zipfile
from pathlib import Path
import pytest
from backend.sexpr import parse,tracks,change_width
from backend.uploads import unpack,inspect
from backend.engine import normalize,sanitize_svg,compare
from backend.storage import fingerprint

FIXTURES=Path(__file__).resolve().parents[1]/'fixtures'

def zip_bytes(entries):
    f=io.BytesIO()
    with zipfile.ZipFile(f,'w') as z:
        for name,blob in entries: z.writestr(name,blob)
    return f.getvalue()

@pytest.mark.parametrize('name',['../escape.kicad_pcb','/absolute.kicad_pcb','C:/bad.kicad_pcb','dir\\file.kicad_pcb','dir/../../bad','CON.txt','aux.kicad_pcb','a/'+('/'.join(['b']*13))+'.kicad_pcb'])
def test_unsafe_archive(name,tmp_path):
    with pytest.raises(ValueError): unpack([('project.zip',zip_bytes([(name,b'bad')]))],tmp_path)

def test_symlink_rejected(tmp_path):
    entry=zipfile.ZipInfo('link.kicad_pcb');entry.create_system=3;entry.external_attr=(stat.S_IFLNK|0o777)<<16
    with pytest.raises(ValueError,match='Links'): unpack([('a.zip',zip_bytes([(entry,b'/etc/passwd')]))],tmp_path)

def test_case_collision(tmp_path):
    with pytest.raises(ValueError,match='case-colliding'): unpack([('p.zip',zip_bytes([('a.txt',b'x'),('A.txt',b'y')]))],tmp_path)

def test_limits_and_nested_archives(tmp_path,monkeypatch):
    with pytest.raises(ValueError,match='Nested'): unpack([('p.zip',zip_bytes([('nested.zip',b'x')]))],tmp_path)
    import backend.uploads as u
    monkeypatch.setattr(u,'MAX_EXPANDED',1)
    with pytest.raises(ValueError,match='Expanded'): unpack([('p.zip',zip_bytes([('file.txt',b'ab')]))],tmp_path)

@pytest.mark.parametrize('name,blob,match',[('board.kicad_pcb',b'(kicad_sch)','Expected'),('board.kicad_pcb',b'(kicad_pcb','Unclosed'),('foo.step',b'ISO-10303','No KiCad'),('script.py',b'print(1)','unsupported'),('project.kicad_pro',b'[]','invalid')])
def test_unsupported_or_invalid_upload(name,blob,match,tmp_path):
    with pytest.raises(ValueError,match=match): unpack([(name,blob)],tmp_path)

def test_hierarchy_missing_and_ambiguity(tmp_path):
    manifest=unpack([('root.kicad_sch',(FIXTURES/'missing/root.kicad_sch').read_bytes())],tmp_path)
    assert any('Missing subsheet' in x['message'] for x in manifest['notices'])
    assert any('settings' in x['message'] for x in manifest['notices'])
    (tmp_path/'second.kicad_sch').write_bytes((FIXTURES/'valid_schematic/valid.kicad_sch').read_bytes())
    assert inspect(tmp_path)['requires_selection']

def test_structured_edit_preserves_unrelated_bytes():
    text=(FIXTURES/'drc/drc.kicad_pcb').read_text()
    track=tracks(text)[0]
    changed=change_width(text,track['id'],.15,.25)
    assert changed.replace('(width 0.25)','(width 0.15)')==text
    assert tracks(changed)[0]['width']==.25
    with pytest.raises(ValueError,match='changed since'): change_width(text,track['id'],.2,.3)
    with pytest.raises(ValueError,match='uniquely'): change_width(text,'unknown',.15,.25)
    with pytest.raises(ValueError,match='Unsupported'): change_width(text,track['id'],.15,.1)

def test_report_preserves_absent_values_and_exclusions():
    v={'type':'clearance','description':'Engine evidence without measurements','severity':'exclusion','items':[]}
    result=normalize({'violations':[v]},'DRC','a.kicad_pcb')[0]
    assert result['position'] is None and result['required'] is None and result['measured'] is None
    assert result['excluded'] and not result['repair']

def test_svg_is_sanitized(tmp_path):
    p=tmp_path/'evil.svg'
    p.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100" onload="alert(1)"><script>alert(1)</script><foreignObject/><image href="http://bad/"/><rect style="fill:url(http://bad)"/></svg>')
    info=sanitize_svg(p)
    text=p.read_text()
    assert not any(s in text for s in ('onload','script','foreignObject','http://bad'))
    assert info['mapping']['scale_x']==1

def test_api_boundary_and_project_isolation(client,upload_fixture):
    assert client.post('/api/sample',headers={'X-CircuitCheck':'0'}).status_code==403
    assert client.post('/api/sample',headers={'Origin':'https://attacker.test'}).status_code==403
    a=upload_fixture('valid');b=upload_fixture('drc')
    assert client.get(f"/api/projects/{a['project_id']}/revisions/{b['revision_id']}").status_code==404
    assert client.get(f"/api/projects/{a['project_id']}/download?revision_id={b['revision_id']}").status_code==404
    assert client.delete('/api/projects/'+a['project_id']).status_code==422

def test_worker_failure_is_not_clean(client,upload_fixture,monkeypatch):
    from backend import worker
    p=upload_fixture('valid')
    def fail(*args,**kwargs): raise RuntimeError('engine execution failed')
    monkeypatch.setattr(worker,'analyze',fail)
    worker.tick()
    r=client.get('/api/projects/'+p['project_id']).json()
    assert r['jobs'][0]['status']=='failed'
    assert r['revision']['result'] is None

def test_stale_queue_recovery_and_global_concurrency(client,upload_fixture):
    from backend import db
    a=upload_fixture('valid')
    assert db.claim()['id']==a['job_id']
    upload_fixture('drc')
    assert db.claim() is None
    with db.connect() as c:c.execute('UPDATE jobs SET updated=? WHERE id=?',(time.time()-1000,a['job_id']))
    db.recover()
    assert db.row('jobs',a['job_id'])['status']=='failed'

def test_external_library_never_reaches_engine(tmp_path):
    files=[('board.kicad_pcb',(FIXTURES/'valid/valid.kicad_pcb').read_bytes()),('fp-lib-table',b'(fp_lib_table (lib (name "Outside") (type "KiCad") (uri "C:/private/outside.pretty")))')]
    with pytest.raises(ValueError,match='external library'):unpack(files,tmp_path)

def test_custom_rule_stream_and_comments_accepted(tmp_path):
    files=[(p.name,p.read_bytes()) for p in (FIXTURES/'custom_rules').iterdir()]
    manifest=unpack(files,tmp_path)
    assert any(f['path']=='rules.kicad_dru' for f in manifest['files'])

def test_parser_handles_comment_and_string_limits():
    assert parse('(root # comment\n (value "a\\\"b"))').get('value').arg()=='a"b'
    with pytest.raises(ValueError,match='limits'):parse('('*130+'a'+')'*130)

def test_ai_validates_output_and_rejects_operations():
    from backend.ai import Answer
    from pydantic import ValidationError
    with pytest.raises(ValidationError):Answer.model_validate({'answer':'x','facts':[],'hypotheses':[],'missing_information':[],'object_ids':[],'operation':{'delete_component':'U1'}})

@pytest.mark.parametrize('text',['Replace U99','Width is 9.7 mm','Object 00000000-0000-0000-0000-000000000000 is affected'])
def test_ai_prose_cannot_introduce_unknown_references_or_measurements(text):
    from backend.ai import Answer,validate_evidence
    with pytest.raises(ValueError):validate_evidence(Answer(answer=text,facts=[],hypotheses=[],missing_information=[],object_ids=[]),{'evidence':'Track U1 measures 0.15 mm; minimum 0.25 mm','object_ids':[]})

def test_ai_unknown_objects_rejected(monkeypatch):
    import asyncio
    import backend.ai as ai
    monkeypatch.setenv('AI_API_KEY','test-placeholder')
    class Response:
        def raise_for_status(self):pass
        def json(self):return {'choices':[{'message':{'content':json.dumps({'answer':'bad','facts':[],'hypotheses':[],'missing_information':[],'object_ids':['invented']})}}]}
    class Client:
        def __init__(self,*a,**kw):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,*a,**kw):return Response()
    monkeypatch.setattr(ai.httpx,'AsyncClient',Client)
    finding={k:[] for k in ('objects','object_ids')};finding.update({'evidence':'data','rule':'rule','suggestion':'manual','repair':None})
    with pytest.raises(ValueError,match='unverified'):asyncio.run(ai.explain('why',finding))
