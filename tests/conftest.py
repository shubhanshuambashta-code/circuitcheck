import os
from pathlib import Path
import pytest

@pytest.fixture(autouse=True)
def database(tmp_path,monkeypatch):
    import backend.db as db
    import backend.storage as storage
    monkeypatch.setattr(db,'DATA',tmp_path/'data')
    original_init=storage.LocalStorage.__init__
    monkeypatch.setattr(storage.LocalStorage,'__init__',lambda self,root=None:original_init(self,tmp_path/'data'))
    monkeypatch.delenv('AI_API_KEY',raising=False)
    db.init()

@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from backend.main import app
    with TestClient(app,headers={'X-CircuitCheck':'1'}) as c: yield c

@pytest.fixture
def engine():
    from backend.engine import executable
    if not executable(): pytest.skip('Real KiCad 10.0.7 is required for native integration tests')

@pytest.fixture
def upload_fixture(client):
    def upload(name):
        folder=Path(__file__).resolve().parents[1]/'fixtures'/name
        result=client.post('/api/projects',files=[('files',(p.name,p.read_bytes())) for p in folder.iterdir() if p.is_file()])
        assert result.status_code==202,result.text
        return result.json()
    return upload
