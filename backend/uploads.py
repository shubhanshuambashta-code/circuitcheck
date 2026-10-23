import io
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath
from .config import MAX_UPLOAD, MAX_EXPANDED, MAX_FILES
from .sexpr import parse

NATIVE={'.kicad_pcb':'kicad_pcb','.kicad_sch':'kicad_sch','.kicad_sym':'kicad_symbol_lib','.kicad_mod':'footprint','.kicad_dru':'version','.kicad_wks':'kicad_wks'}
ASSOCIATED={'.kicad_pro','.step','.stp','.wrl','.txt','.md','.pdf','.png','.jpg','.jpeg','.json','.kicad_prl'}
TABLES={'sym-lib-table','fp-lib-table'}

def safe_path(name):
    if '\\' in name or '\x00' in name or ':' in name:
        raise ValueError('Archive contains an unsafe path')
    p=PurePosixPath(name)
    if p.is_absolute() or not p.parts or any(x in ('.','..') for x in p.parts) or len(p.parts)>12:
        raise ValueError('Archive contains path traversal or excessive nesting')
    if any(x.endswith(('.', ' ')) or x.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))} for x in p.parts):
        raise ValueError('Unsafe platform filename')
    return p

def unpack(files: list[tuple[str,bytes]], directory: Path):
    if sum(len(b) for _,b in files)>MAX_UPLOAD: raise ValueError('Upload exceeds 25 MB')
    expanded=[]
    for name,blob in files:
        if name.lower().endswith('.zip'):
            try:
                with zipfile.ZipFile(io.BytesIO(blob)) as z:
                    entries=z.infolist()
                    if len(entries)>MAX_FILES: raise ValueError('Archive exceeds 500 entries')
                    if sum(x.file_size for x in entries)>MAX_EXPANDED: raise ValueError('Expanded project exceeds 100 MB')
                    for x in entries:
                        p=safe_path(x.filename.rstrip('/'))
                        mode=x.external_attr>>16
                        if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0,stat.S_IFREG,stat.S_IFDIR)) or x.flag_bits&1:
                            raise ValueError('Links, special files and encrypted entries are unsupported')
                        if x.is_dir(): continue
                        if p.suffix.lower()=='.zip': raise ValueError('Nested archives are unsupported')
                        expanded.append((p,z.read(x)))
            except zipfile.BadZipFile as exc: raise ValueError('Unreadable ZIP archive') from exc
        else: expanded.append((safe_path(name),blob))
    if len(expanded)>MAX_FILES or sum(len(x[1]) for x in expanded)>MAX_EXPANDED: raise ValueError('Project exceeds extraction limits')
    seen=set()
    for p,blob in expanded:
        key=str(p).casefold()
        if key in seen: raise ValueError('Duplicate or case-colliding project paths')
        seen.add(key)
        ext=p.suffix.lower()
        if ext not in NATIVE and ext not in ASSOCIATED and p.name not in TABLES:
            raise ValueError(f'{p.name}: unsupported file type. Upload native KiCad PCB, schematic and project files, or a project ZIP. Scripts are never executed.')
        if ext in NATIVE or p.name in TABLES:
            try:
                text=blob.decode('utf-8-sig')
                if ext=='.kicad_dru':
                    root=parse('('+text+'\n)')
                    if not root.children or root.children[0].tag!='version' or any(n.tag not in ('version','rule') for n in root.children):
                        raise ValueError('Expected a KiCad custom rule stream')
                else:
                    root=parse(text)
                    expected=NATIVE.get(ext,p.name.replace('-','_'))
                    if root.tag!=expected: raise ValueError(f'Expected {expected} contents')
            except (UnicodeError,ValueError) as e: raise ValueError(f'{p.name}: invalid KiCad file: {e}') from e
        elif ext=='.kicad_pro':
            try:
                if not isinstance(json.loads(blob),dict): raise ValueError('Expected project object')
            except (ValueError,UnicodeError) as e: raise ValueError(f'{p.name}: invalid project JSON') from e
        target=directory.joinpath(*p.parts)
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(blob)
    return inspect(directory)

def inspect(directory: Path, selected: str | None = None):
    paths=sorted(p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file())
    designs=[p for p in paths if Path(p).suffix in ('.kicad_pcb','.kicad_sch')]
    if not designs: raise ValueError('No KiCad board or schematic found. A project settings file alone cannot be checked.')
    notices=[]
    referenced=set()
    for f in [x for x in designs if x.endswith('.kicad_sch')]:
        root=parse((directory/f).read_text(encoding='utf-8-sig'))
        for sheet in root.all('sheet'):
            for prop in sheet.all('property'):
                if prop.arg().lower() in ('sheetfile','sheet file'):
                    ref=prop.arg(2)
                    try:
                        if '\\' in ref or ':' in ref or '${' in ref: raise ValueError('External reference')
                        candidate=(directory/Path(f).parent/ref).resolve()
                        rel=candidate.relative_to(directory.resolve()).as_posix()
                    except ValueError:
                        notices.append({'kind':'missing','message':f'{f}: external or unsafe subsheet reference {ref} is blocked.'})
                        continue
                    referenced.add(rel)
                    if rel not in paths: notices.append({'kind':'missing','message':f'Missing subsheet: {rel}. Upload the complete hierarchy.'})
    stems=sorted({str(Path(x).with_suffix('')) for x in designs if x not in referenced})
    # A same-stem schematic and board are a single candidate project.
    root=selected or (stems[0] if len(stems)==1 else None)
    if selected and selected not in stems: raise ValueError('Unknown root project')
    if root and root+'.kicad_pro' not in paths:
        notices.append({'kind':'missing','message':'Project settings are missing. Checks use engine defaults; the original design rules cannot be established.'})
    if root and root+'.kicad_pro' in paths:
        settings=json.loads((directory/(root+'.kicad_pro')).read_text(encoding='utf-8-sig'))
        severities=settings.get('board',{}).get('design_settings',{}).get('rule_severities',{})
        if root+'.kicad_dru' not in paths and severities.get('missing_courtyard') is None:
            # Absence alone cannot establish that a custom rule file was intended.
            # Keep this uncertainty explicit without calling it a defect.
            notices.append({'kind':'info','message':'No custom rule file supplied. Additional rules referenced only outside this upload cannot be established.'})
    for f in paths:
        if Path(f).name in TABLES:
            table=parse((directory/f).read_text(encoding='utf-8-sig'))
            for lib in table.all('lib'):
                uri=lib.get('uri')
                if not uri: continue
                value=uri.arg().replace('${KIPRJMOD}',str((directory/f).parent))
                candidate=Path(value)
                if not candidate.is_absolute(): candidate=(directory/f).parent/candidate
                try: candidate.resolve().relative_to(directory.resolve())
                except ValueError:
                    raise ValueError(f'{Path(f).name}: external library URI {uri.arg()} is blocked. Bundle the library inside the ZIP and reference it with ${{KIPRJMOD}}.')
                if not candidate.exists(): notices.append({'kind':'missing','message':f'Missing library: {uri.arg()}.'})
    return {'files':[{'path':f,'size':(directory/f).stat().st_size,'kind':Path(f).suffix.lstrip('.') or 'library table'} for f in paths],
            'candidates':stems,'root':root,'notices':notices,'requires_selection':root is None}

