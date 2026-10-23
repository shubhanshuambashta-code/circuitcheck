"""Allowlisted operations, immutable candidates, compare-and-swap apply, independent recheck."""
import json
import shutil
import time
from uuid import uuid4
from . import db
from .storage import LocalStorage,fingerprint
from .sexpr import change_width
from .uploads import inspect

def preview(project_id,finding_id):
    project=db.row('projects',project_id)
    if not project: raise ValueError('Project not found')
    base=db.row('revisions',project['current_revision'])
    result=db.decode(base['result'])
    if not result or result['status']!='completed': raise ValueError('Complete the checks with project dependencies before previewing a repair')
    finding=next((f for f in result['findings'] if f['id']==finding_id),None)
    if not finding or not finding.get('repair') or finding['excluded']: raise ValueError('Automatic repair is unavailable for this finding')
    op=finding['repair']
    if op['kind']!='track_width': raise ValueError('Operation is not allowed')
    store=LocalStorage(); source=store.revision(project_id,base['id'])/'source'
    if fingerprint(source)!=base['hash']: raise ValueError('Source changed since analysis; upload or recheck the current revision')
    candidate=str(uuid4()); repair_id=str(uuid4()); job_id=str(uuid4())
    target=store.revision(project_id,candidate)/'source'
    shutil.copytree(source,target)
    try:
        file=target/op['file']
        original=file.read_bytes().decode('utf-8-sig')
        changed=change_width(original,op['object_id'],op['from'],op['to'])
        # Preserve source encoding, line endings and unrelated content byte-for-byte.
        prefix=b'\xef\xbb\xbf' if file.read_bytes().startswith(b'\xef\xbb\xbf') else b''
        file.write_bytes(prefix+changed.encode('utf-8'))
        manifest=inspect(target,db.decode(base['manifest'])['root'])
        now=time.time()
        with db.connect() as c:
            c.execute('INSERT INTO revisions VALUES(?,?,?,?,?,?,?)',(candidate,project_id,base['id'],fingerprint(target),json.dumps(manifest),None,now))
            c.execute('INSERT INTO repairs VALUES(?,?,?,?,?,?,?,?)',(repair_id,project_id,base['id'],candidate,finding_id,json.dumps(op),'preview',now))
            c.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?)',(job_id,project_id,candidate,'queued','Validating proposed copy',None,now,now))
        return {'repair_id':repair_id,'candidate_id':candidate,'job_id':job_id,'operation':op,'message':'Proposed copy only. Review the recheck before applying.'}
    except Exception:
        shutil.rmtree(target.parent,ignore_errors=True)
        raise

def apply(project_id,repair_id):
    repair=db.row('repairs',repair_id)
    if not repair or repair['project_id']!=project_id or repair['state']!='preview': raise ValueError('Repair preview not found')
    candidate=db.row('revisions',repair['candidate_id']); result=db.decode(candidate['result'])
    if not result or result['status']!='completed': raise ValueError('The proposed file must reopen and complete checks before applying')
    base=db.row('revisions',repair['base_id'])
    store=LocalStorage()
    if fingerprint(store.revision(project_id,base['id'])/'source')!=base['hash'] or fingerprint(store.revision(project_id,candidate['id'])/'source')!=candidate['hash']:
        raise ValueError('Design contents changed after preview. Create a new preview and rerun checks.')
    if any(f['id']==repair['finding_id'] and not f['excluded'] for f in result['findings']): raise ValueError('Targeted finding remains. Automatic apply is unavailable.')
    now=time.time(); job=str(uuid4())
    # Invalidate before publishing the new current revision / queued job, avoiding
    # a worker race with the candidate validation cache.
    cache=store.revision(project_id,candidate['id'])/'artifacts'/'result.json'
    cache.unlink(missing_ok=True)
    with db.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        changed=c.execute('UPDATE projects SET current_revision=? WHERE id=? AND current_revision=?',(candidate['id'],project_id,repair['base_id'])).rowcount
        if not changed: raise ValueError('Project changed after preview. Create a new preview from the current revision.')
        c.execute("UPDATE repairs SET state='applied' WHERE id=?",(repair_id,))
        c.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?)',(job,project_id,candidate['id'],'queued','Rechecking applied revision',None,now,now))
    # Force a fresh check after apply instead of treating candidate validation as a new run.
    return {'revision_id':candidate['id'],'job_id':job}

