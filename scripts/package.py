"""Create the source deliverable, excluding private projects, secrets and installed runtimes."""
from pathlib import Path
import argparse
import zipfile
ROOT=Path(__file__).resolve().parents[1]
excluded={'node_modules','data','.venv','.git','.pytest_cache','__pycache__','test-results','playwright-report'}
parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT.parent/'CircuitCheck-source.zip');args=parser.parse_args()
target=args.output.resolve();target.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
    for p in sorted(ROOT.rglob('*')):
        rel=p.relative_to(ROOT)
        if not p.is_file() or any(x in excluded for x in rel.parts) or (p.name.startswith('.env') and p.name!='.env.example') or p.suffix in ('.pyc','.tsbuildinfo','.pem','.key'):continue
        archive.write(p,Path('CircuitCheck')/rel)
print(f'Created {target.name}: {target.stat().st_size:,} bytes')
