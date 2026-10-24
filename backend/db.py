"""SQLite repository. Short-lived connections and atomic queue claims; no ORM state in workers."""
import json
import sqlite3
import time
from contextlib import contextmanager
from .config import DATA

@contextmanager
def connect():
    DATA.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATA / 'circuitcheck.sqlite3', timeout=30)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA journal_mode=WAL')
    try:
        yield db
        db.commit()
    finally:
        db.close()

def init():
    with connect() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,name TEXT,created REAL,current_revision TEXT,example INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS revisions(id TEXT PRIMARY KEY,project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,parent_id TEXT,hash TEXT,manifest TEXT,result TEXT,created REAL);
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,revision_id TEXT,status TEXT,stage TEXT,error TEXT,created REAL,updated REAL);
        CREATE TABLE IF NOT EXISTS repairs(id TEXT PRIMARY KEY,project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,base_id TEXT,candidate_id TEXT,finding_id TEXT,operation TEXT,state TEXT,created REAL);
        CREATE INDEX IF NOT EXISTS jobs_status ON jobs(status,created);
        CREATE TABLE IF NOT EXISTS review_notes(id TEXT PRIMARY KEY,project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,finding_id TEXT,revision_id TEXT,kind TEXT,body TEXT,scope TEXT,created REAL);
        CREATE INDEX IF NOT EXISTS review_notes_finding ON review_notes(project_id,finding_id);
        CREATE TABLE IF NOT EXISTS explanations(id TEXT PRIMARY KEY,project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,revision_id TEXT,finding_id TEXT,question TEXT,response TEXT,created REAL);
        ''')

def row(table, id):
    if table not in ('projects', 'revisions', 'jobs', 'repairs'):
        raise ValueError('Unknown repository')
    with connect() as c:
        r = c.execute(f'SELECT * FROM {table} WHERE id=?', (id,)).fetchone()
        return dict(r) if r else None

def update_job(id, status, stage, error=None):
    with connect() as c:
        c.execute('UPDATE jobs SET status=?,stage=?,error=?,updated=? WHERE id=?', (status, stage, error, time.time(), id))

def claim():
    with connect() as c:
        c.execute('BEGIN IMMEDIATE')
        if c.execute("SELECT 1 FROM jobs WHERE status='running' LIMIT 1").fetchone():
            return None
        r = c.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
        if r:
            c.execute("UPDATE jobs SET status='running',stage='Reading project',updated=? WHERE id=?", (time.time(), r['id']))
            return dict(r)

def recover():
    # A job is never silently declared clean after a worker interruption.
    with connect() as c:
        c.execute("UPDATE jobs SET status='failed',stage='Worker interrupted',error='Worker heartbeat expired. Rerun checks.',updated=? WHERE status='running' AND updated<?", (time.time(), time.time()-600))

def decode(r):
    return json.loads(r) if r else None

