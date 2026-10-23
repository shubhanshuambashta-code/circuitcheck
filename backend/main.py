from contextlib import asynccontextmanager
import io
import json
import shutil
import time
import zipfile
from pathlib import Path
from uuid import uuid4
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field
from . import db, repairs
from .config import ROOT,MAX_UPLOAD
from .storage import LocalStorage,fingerprint
from .uploads import unpack,inspect,safe_path
from .engine import executable,compare
from .ai import explain

@asynccontextmanager
async def lifespan(app):
    db.init()
    yield

app=FastAPI(title='CircuitCheck',version='0.1.0',lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware,allowed_hosts=['127.0.0.1','localhost','testserver','[::1]'])

@app.middleware('http')
async def local_boundary(request:Request,call_next):
    if request.method not in ('GET','HEAD','OPTIONS'):
        origin=request.headers.get('origin')
        from urllib.parse import urlparse
        if (origin and urlparse(origin).hostname not in ('localhost','127.0.0.1','::1')) or request.headers.get('x-circuitcheck')!='1':
            return JSONResponse({'detail':'Local API request rejected. Open CircuitCheck on localhost.'},status_code=403)
        length=request.headers.get('content-length')
        if length and int(length)>MAX_UPLOAD+1024*1024: return JSONResponse({'detail':'Upload exceeds 25 MB'},status_code=413)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='no-referrer'
    if request.url.path.endswith('.svg'): response.headers['Content-Security-Policy']="default-src 'none'; style-src 'unsafe-inline'; sandbox"
    return response

@app.exception_handler(ValueError)
async def invalid(request,error): return JSONResponse({'detail':str(error)},status_code=422)

def require(table,id):
    r=db.row(table,id)
    if not r: raise HTTPException(404,'Not found')
    return r

def queue(project_id,revision_id):
    now=time.time(); id=str(uuid4())
    with db.connect() as c:
        if c.execute("SELECT count(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0]>=20:
            raise ValueError('Analysis queue is full. Wait for current jobs to finish.')
        active=c.execute("SELECT id FROM jobs WHERE revision_id=? AND status IN ('queued','running')",(revision_id,)).fetchone()
        if active: return active['id']
        c.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?)',(id,project_id,revision_id,'queued','Waiting for analysis worker',None,now,now))
    return id

def create_project(files,example=False):
    id=str(uuid4()); rid=str(uuid4()); store=LocalStorage()
    original=store.project(id)/'original'
    source=store.revision(id,rid)/'source'
    original.mkdir(parents=True)
    try:
        manifest=unpack(files,original)
        shutil.copytree(original,source)
        name=Path(manifest['root']).name if manifest['root'] else 'Choose project root'
        now=time.time()
        with db.connect() as c:
            c.execute('INSERT INTO projects VALUES(?,?,?,?,?)',(id,name,now,rid,int(example)))
            c.execute('INSERT INTO revisions VALUES(?,?,?,?,?,?,?)',(rid,id,None,fingerprint(source),json.dumps(manifest),None,now))
        job=queue(id,rid) if not manifest['requires_selection'] else None
        return {'project_id':id,'revision_id':rid,'job_id':job,'manifest':manifest}
    except Exception:
        store.delete(id)
        raise

@app.get('/api/health')
def health():
    import os
    return {'status':'ok','engine_available':bool(executable()),'ai_available':bool(os.getenv('AI_API_KEY')),'tested_engine':'10.0.7','deployment':'local single-user'}

@app.get('/api/capabilities')
def capabilities():
    return {'formats':[
        {'format':'KiCad PCB','extensions':['.kicad_pcb'],'read':True,'preview':True,'electrical':'Connectivity DRC; no functional simulation','manufacturing':'Project DRC','edit':'Selected straight track width only','native_export':True,'conversion':False},
        {'format':'KiCad schematic','extensions':['.kicad_sch'],'read':True,'preview':True,'electrical':'ERC and netlist','manufacturing':False,'edit':False,'native_export':'Unmodified originals','conversion':False},
        {'format':'KiCad project / ZIP','extensions':['.kicad_pro','.zip'],'read':True,'preview':'Contained native designs','electrical':'Contained designs','manufacturing':'Contained boards','edit':'Supported PCB operation only','native_export':True,'conversion':False},
        *[{'format':f,'read':False,'preview':False,'electrical':False,'manufacturing':False,'edit':False,'native_export':False,'conversion':False} for f in ['EasyEDA','EAGLE','Altium','Gerber / Excellon','STEP / IGES','DXF','STL']]],
        'notes':['Photographs and PDFs are reference files, not electrical connectivity.','STEP/WRL files may accompany native projects but are not analyzed.','No format conversion is implemented.']}

@app.get('/api/projects')
def projects():
    with db.connect() as c:
        return [dict(r) for r in c.execute('SELECT * FROM projects ORDER BY created DESC')]

@app.post('/api/projects',status_code=202)
async def upload(files:list[UploadFile]=File(...)):
    incoming=[]; size=0
    for f in files:
        blob=await f.read(MAX_UPLOAD+1); size+=len(blob)
        if size>MAX_UPLOAD: raise HTTPException(413,'Upload exceeds 25 MB')
        incoming.append((f.filename or 'unknown',blob))
    return create_project(incoming)

@app.post('/api/sample',status_code=202)
def sample():
    folder=ROOT/'fixtures'/'fieldnode'
    return create_project([(p.relative_to(folder).as_posix(),p.read_bytes()) for p in folder.rglob('*') if p.is_file()],True)

@app.get('/api/projects/{id}')
def project(id):
    p=require('projects',id)
    with db.connect() as c:
        revisions=[dict(x) for x in c.execute('SELECT id,parent_id,hash,created FROM revisions WHERE project_id=? ORDER BY created',(id,))]
        jobs=[dict(x) for x in c.execute('SELECT * FROM jobs WHERE project_id=? ORDER BY created DESC LIMIT 20',(id,))]
    rev=require('revisions',p['current_revision'])
    return {**p,'revision':{**rev,'manifest':db.decode(rev['manifest']),'result':db.decode(rev['result'])},'revisions':revisions,'jobs':jobs}

class RootSelection(BaseModel): root:str=Field(max_length=500)
@app.post('/api/projects/{id}/root')
def select_root(id,body:RootSelection):
    p=require('projects',id); rev=require('revisions',p['current_revision'])
    if db.decode(rev['result']): raise ValueError('Root selection is only available before the first analysis')
    manifest=inspect(LocalStorage().revision(id,rev['id'])/'source',body.root)
    with db.connect() as c:
        c.execute('UPDATE revisions SET manifest=? WHERE id=?',(json.dumps(manifest),rev['id']))
        c.execute('UPDATE projects SET name=? WHERE id=?',(Path(body.root).name,id))
    return {'job_id':queue(id,rev['id'])}

@app.post('/api/projects/{id}/analyze',status_code=202)
def analyze(id):
    p=require('projects',id)
    return {'job_id':queue(id,p['current_revision'])}

@app.get('/api/jobs/{id}')
def job(id): return require('jobs',id)

@app.get('/api/projects/{id}/revisions/{rid}')
def revision(id,rid):
    r=require('revisions',rid)
    if r['project_id']!=id: raise HTTPException(404,'Not found')
    return {**r,'manifest':db.decode(r['manifest']),'result':db.decode(r['result'])}

@app.get('/api/projects/{id}/revisions/{rid}/artifacts/{name:path}')
def artifact(id,rid,name):
    r=require('revisions',rid)
    if r['project_id']!=id: raise HTTPException(404,'Not found')
    root=LocalStorage().revision(id,rid)/'artifacts'
    path=root.joinpath(*safe_path(name).parts).resolve()
    if root.resolve() not in path.parents or not path.is_file() or path.suffix not in ('.svg','.json','.log','.xml'): raise HTTPException(404,'Artifact not found')
    return FileResponse(path)

class PreviewRequest(BaseModel): finding_id:str=Field(max_length=64)
@app.post('/api/projects/{id}/repairs')
def preview(id,body:PreviewRequest): return repairs.preview(id,body.finding_id)

@app.post('/api/projects/{id}/repairs/{repair_id}/apply')
def apply(id,repair_id): return repairs.apply(id,repair_id)

@app.post('/api/projects/{id}/undo')
def undo(id):
    p=require('projects',id); rev=require('revisions',p['current_revision'])
    if not rev['parent_id']: raise ValueError('Original revision is already selected')
    with db.connect() as c:
        changed=c.execute('UPDATE projects SET current_revision=? WHERE id=? AND current_revision=?',(rev['parent_id'],id,rev['id'])).rowcount
        if not changed: raise ValueError('Revision changed; reload the project')
    return {'revision_id':rev['parent_id'],'job_id':queue(id,rev['parent_id'])}

@app.get('/api/projects/{id}/compare')
def comparison(id,before:str,after:str):
    a=require('revisions',before); b=require('revisions',after)
    if a['project_id']!=id or b['project_id']!=id: raise HTTPException(404,'Not found')
    if not a['result'] or not b['result']: raise ValueError('Both revisions must complete analysis before comparison')
    return compare(db.decode(a['result']),db.decode(b['result']))

class Question(BaseModel):
    question:str=Field(min_length=1,max_length=2000)
    finding_id:str | None=None

@app.post('/api/projects/{id}/chat')
async def chat(id,body:Question):
    p=require('projects',id); result=db.decode(require('revisions',p['current_revision'])['result'])
    if not result: raise ValueError('Run checks before asking about results')
    finding=next((f for f in result['findings'] if f['id']==body.finding_id),None)
    if not finding:
        checks='; '.join(f"{c['name']}: {c['status']}" for c in result['checks'])
        return {'provider':'deterministic','answer':f"Checks on this revision: {checks}. {len(result['findings'])} findings were reported. Select a finding to ask about its evidence or correction.",'facts':[],'hypotheses':[],'missing_information':[],'object_ids':[]}
    try: return await explain(body.question,finding)
    except Exception:
        return {'provider':'deterministic','answer':finding['explanation']+' '+finding['suggestion'],'facts':[finding['evidence']],
                'hypotheses':[],'missing_information':['The AI provider is unavailable or its response failed validation. Showing original tool evidence.'],'object_ids':finding['object_ids']}

@app.get('/api/projects/{id}/download')
def download(id,revision_id:str | None=None,original:bool=False):
    p=require('projects',id); store=LocalStorage()
    rid=revision_id or p['current_revision']
    rev=require('revisions',rid)
    if rev['project_id']!=id: raise HTTPException(404,'Not found')
    directory=store.project(id)/'original' if original else store.revision(id,rid)/'source'
    content=io.BytesIO()
    with zipfile.ZipFile(content,'w',zipfile.ZIP_DEFLATED) as z:
        for f in directory.rglob('*'):
            if f.is_file(): z.write(f,f.relative_to(directory).as_posix())
    content.seek(0)
    return StreamingResponse(content,media_type='application/zip',headers={'Content-Disposition':f'attachment; filename="circuitcheck-{id[:8]}-{"original" if original else rid[:8]}.zip"'})

@app.get('/api/projects/{id}/report')
def report(id):
    p=require('projects',id); rev=require('revisions',p['current_revision'])
    if not rev['result']: raise ValueError('No completed report is available')
    return JSONResponse({'project':p,'revision':rev['id'],'manifest':db.decode(rev['manifest']),'result':db.decode(rev['result'])},
                        headers={'Content-Disposition':'attachment; filename="circuitcheck-report.json"'})

@app.delete('/api/projects/{id}')
def delete(id):
    require('projects',id)
    with db.connect() as c:
        if c.execute("SELECT id FROM jobs WHERE project_id=? AND status IN ('queued','running')",(id,)).fetchone(): raise ValueError('Wait for the active job to finish before deleting the project')
        c.execute('DELETE FROM projects WHERE id=?',(id,))
    LocalStorage().delete(id)
    return {'deleted':True}

if (ROOT/'dist').exists(): app.mount('/',StaticFiles(directory=ROOT/'dist',html=True),name='frontend')

