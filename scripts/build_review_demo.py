"""Generate the public replay from real native runs on original synthetic fixtures.

Requires an explicit isolated data folder. This never reads user projects.
The output is a recorded example; the Pages app cannot submit live engine jobs.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
parser=argparse.ArgumentParser()
parser.add_argument('--data-dir',type=Path,required=True)
args=parser.parse_args()
data_dir=args.data_dir.resolve()
if (data_dir/'circuitcheck.sqlite3').exists():raise SystemExit('Use a fresh isolated data directory; existing databases are never replaced.')
os.environ['CIRCUITCHECK_DATA']=str(data_dir)
from backend import worker
from backend.main import app
from backend.profiles import PRESETS
from backend.sexpr import tracks,change_width,parse
from backend.storage import LocalStorage
from fastapi.testclient import TestClient

with TestClient(app,headers={'X-CircuitCheck':'1'}) as client:
    created=client.post('/api/sample').json();pid=created['project_id'];aid=created['revision_id']
    worker.tick()
    a=client.get(f'/api/projects/{pid}').json()['revision']
    if a['result']['status']!='completed':raise RuntimeError('Synthetic revision A did not finish: '+json.dumps(a['result']['checks']))
    width=next(f for f in a['result']['findings'] if f.get('repair'))
    response=client.post(f'/api/projects/{pid}/review-notes',json={'finding_id':width['id'],'revision_id':aid,'kind':'comment','body':'Synthetic review example: increase this segment to the configured minimum, then check the revised board. Original evidence retained.'})
    response.raise_for_status()
    review=next((f for f in a['result']['findings'] if f['rule']=='text_height' and 'R2' not in f.get('references',[])),None)
    if review:
        client.post(f'/api/projects/{pid}/review-notes',json={'finding_id':review['id'],'revision_id':aid,'kind':'accepted_exception','body':'Synthetic review example only: the fixture text-height exception is accepted for this demonstration. This is not fabrication approval.'}).raise_for_status()
    dangling=next((f for f in a['result']['findings'] if f['rule']=='track_dangling' and width['repair']['object_id'] in f.get('board_object_ids',[])),None)
    if dangling:
        client.post(f'/api/projects/{pid}/review-notes',json={'finding_id':dangling['id'],'revision_id':aid,'kind':'accepted_exception','body':'Synthetic demo only: this isolated endpoint was accepted for this exact source evidence. Any change to the segment requires re-review.'}).raise_for_status()
    folder=ROOT/'fixtures/fieldnode'
    board=(folder/'fieldnode.kicad_pcb').read_text(encoding='utf-8-sig')
    board=change_width(board,width['repair']['object_id'],width['repair']['from'],width['repair']['to'])
    # Deliberate new width violation and physical net-assignment change.
    track=next(t for t in tracks(board) if t['width']==.3)
    atom=track['node'].get('width').children[1]
    board=board[:atom.start]+'.12'+board[atom.end:]
    track=next(t for t in tracks(board) if t['id']==track['id'])
    atom=track['node'].get('net').children[1]
    board=board[:atom.start]+'3'+board[atom.end:]
    # A moved component retains its UUID and demonstrates physical comparison.
    footprint=next(n for n in parse(board).all('footprint') if any(p.arg()=='Reference' and p.arg(2)=='R2' for p in n.all('property')))
    atom=footprint.get('at').children[1]
    board=board[:atom.start]+'81'+board[atom.end:]
    files=[('files',(p.name,board.encode() if p.name=='fieldnode.kicad_pcb' else p.read_bytes())) for p in folder.iterdir() if p.is_file()]
    response=client.post(f'/api/projects/{pid}/revisions',files=files);response.raise_for_status();bid=response.json()['revision_id']
    worker.tick()
    project=client.get(f'/api/projects/{pid}').json()
    a=client.get(f'/api/projects/{pid}/revisions/{aid}').json()
    b=client.get(f'/api/projects/{pid}/revisions/{bid}').json()
    if b['result']['status']!='completed':raise RuntimeError('Synthetic revision B did not finish: '+json.dumps(b['result']['checks']))
    ab=client.get(f'/api/projects/{pid}/compare?before={aid}&after={bid}').json()
    ba=client.get(f'/api/projects/{pid}/compare?before={bid}&after={aid}').json()
    if not all(ab[key] for key in ('resolved','remaining','new')):raise RuntimeError('Fixture did not demonstrate all finding transitions')
    demo=(ROOT/'public/demo').resolve()
    if demo.parent!=(ROOT/'public').resolve() or demo.name!='demo' or demo.is_symlink():raise RuntimeError('Unexpected demo output directory')
    if demo.exists():shutil.rmtree(demo)
    demo.mkdir()
    payload={'recording':{'kind':'native-engine-recording','synthetic':True,'description':'Original synthetic KiCad fixture with deliberately resolved, remaining and new findings. No functional circuit validation.'},'project':project,'revisions':{aid:a,bid:b},'comparisons':{aid+'..'+bid:ab,bid+'..'+aid:ba},'profiles':{'presets':PRESETS}}
    (demo/'data.json').write_text(json.dumps(payload,separators=(',',':')),encoding='utf-8')
    for rid,filename in [(aid,'revision-a.zip'),(bid,'revision-b.zip')]:
        store=LocalStorage().revision(pid,rid)
        with zipfile.ZipFile(demo/filename,'w',zipfile.ZIP_DEFLATED) as z:
            for p in (store/'source').rglob('*'):
                if p.is_file():z.write(p,p.relative_to(store/'source').as_posix())
        out=demo/'artifacts'/rid;out.mkdir(parents=True)
        for p in (store/'artifacts').glob('*'):
            if p.suffix=='.svg':shutil.copyfile(p,out/p.name)
            elif p.name in ('drc.json','erc.json','fabrication-drc.json'):
                report=json.loads(p.read_text(encoding='utf-8-sig'))
                if 'source' in report:report['source']='fieldnode.kicad_pcb';report['recording_note']='Only the host source-path metadata is redacted. Native findings and measurements are unchanged.'
                (out/p.name).write_text(json.dumps(report,indent=2),encoding='utf-8')
    report=client.get(f'/api/projects/{pid}/review-report');report.raise_for_status()
    (demo/'recorded-review.html').write_text(report.text,encoding='utf-8')
    evidence=client.get(f'/api/projects/{pid}/report');evidence.raise_for_status()
    (demo/'recorded-evidence.json').write_text(evidence.text,encoding='utf-8')
    print(json.dumps({'project_id':pid,'a':aid,'b':bid,'resolved':len(ab['resolved']),'remaining':len(ab['remaining']),'new':len(ab['new']),'changed_components':len(ab['geometry']['components']),'changed_routing_objects':len(ab['geometry']['connections']),'confirmed':sum(f['classification']=='confirmed_violation' for f in b['result']['findings']),'output':str(demo)}),flush=True)
