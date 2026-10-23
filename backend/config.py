import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Minimal .env reader: no interpolation, no command evaluation, environment wins.
if (ROOT/'.env').is_file():
    for line in (ROOT/'.env').read_text(encoding='utf-8-sig').splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            key,value=line.split('=',1)
            if key.strip() in {'KICAD_CLI','CIRCUITCHECK_DATA','ENGINE_TIMEOUT','AI_API_KEY','AI_BASE_URL','AI_MODEL'}:
                os.environ.setdefault(key.strip(),value.strip().strip('"').strip("'"))
DATA = Path(os.environ.get('CIRCUITCHECK_DATA', ROOT / 'data')).resolve()
ENGINE_TIMEOUT = int(os.environ.get('ENGINE_TIMEOUT', '120'))
MAX_UPLOAD = 25 * 1024 * 1024
MAX_EXPANDED = 100 * 1024 * 1024
MAX_FILES = 500
PINNED_ENGINE = '10.0.7'

