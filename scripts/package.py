"""Create the source deliverable, excluding private projects, secrets and installed runtimes."""
from pathlib import Path
import zipfile
ROOT=Path(__file__).resolve().parents[1]
excluded={'node_modules','data','.venv','.git','.pytest_cache','__pycache__','test-results','playwright-report'}
target=ROOT.parent/'CircuitCheck-source.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
    for p in sorted(ROOT.rglob('*')):
        rel=p.relative_to(ROOT)
        if not p.is_file() or any(x in excluded for x in rel.parts) or p.name=='.env' or p.suffix in ('.pyc','.tsbuildinfo'):continue
        archive.write(p,Path('CircuitCheck')/rel)
print(f'Created {target.name}: {target.stat().st_size:,} bytes')
