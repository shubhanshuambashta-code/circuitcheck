"""Run separately: python -m backend.worker. A single process bounds concurrency to one job."""
import argparse
import json
import logging
import time
import traceback
from . import db
from .storage import LocalStorage
from .engine import analyze

def tick():
    db.recover()
    job=db.claim()
    if not job: return False
    store=LocalStorage()
    try:
        rev=db.row('revisions',job['revision_id'])
        folder=store.revision(job['project_id'],job['revision_id'])
        result=analyze(folder/'source',folder/'artifacts',db.decode(rev['manifest']),
                       lambda stage: db.update_job(job['id'],'running',stage))
        with db.connect() as c:
            c.execute('UPDATE revisions SET result=? WHERE id=?',(json.dumps(result),rev['id']))
        db.update_job(job['id'],result['status'],'Checks completed' if result['status']=='completed' else 'Review check coverage')
    except Exception as e:
        folder=store.revision(job['project_id'],job['revision_id'])/'artifacts'
        folder.mkdir(parents=True,exist_ok=True)
        (folder/'failure.log').write_text(traceback.format_exc(),encoding='utf-8')
        db.update_job(job['id'],'failed','Analysis failed',str(e))
        logging.exception('Analysis failed for job %s',job['id'])
    return True

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--once',action='store_true'); args=parser.parse_args()
    db.init()
    if args.once: tick(); return
    while True:
        if not tick(): time.sleep(1)

if __name__=='__main__': main()

