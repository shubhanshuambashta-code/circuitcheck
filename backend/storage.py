"""Storage boundary. Only validated project/revision UUIDs reach this implementation."""
from pathlib import Path
from typing import Protocol
from uuid import UUID
import hashlib
import shutil
from .config import DATA

class Storage(Protocol):
    def project(self, project_id: str) -> Path: ...
    def revision(self, project_id: str, revision_id: str) -> Path: ...
    def delete(self, project_id: str) -> None: ...

class LocalStorage:
    def __init__(self, root: Path = DATA):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def project(self, project_id):
        UUID(project_id)
        return self.root / 'projects' / project_id

    def revision(self, project_id, revision_id):
        UUID(revision_id)
        return self.project(project_id) / 'revisions' / revision_id

    def delete(self, project_id):
        path = self.project(project_id).resolve()
        if self.root not in path.parents:
            raise ValueError('Invalid project path')
        shutil.rmtree(path, ignore_errors=True)

def fingerprint(directory: Path):
    h = hashlib.sha256()
    for p in sorted(directory.rglob('*')):
        if p.is_file():
            h.update(p.relative_to(directory).as_posix().encode())
            h.update(b'\0')
            h.update(p.read_bytes())
    return h.hexdigest()

