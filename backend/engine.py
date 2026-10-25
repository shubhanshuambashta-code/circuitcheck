"""Native KiCad adapter: commands are probed, reports retained, failures stay failures."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from defusedxml import ElementTree as ET
from .config import ENGINE_TIMEOUT, PINNED_ENGINE
from .sexpr import tracks, parse, number
from .storage import fingerprint
from .limits import unix_limits,windows_job
from .geometry import board_index, geometry_diff, signature
from .review import enrich,ADAPTER_VERSION,NORMALIZER_VERSION

class EngineError(RuntimeError): pass

def executable():
    configured=os.getenv('KICAD_CLI')
    if configured and Path(configured).is_file(): return configured
    found=shutil.which('kicad-cli')
    if found: return found
    for p in (Path('C:/Program Files/KiCad/10.0/bin/kicad-cli.exe'),Path('C:/Program Files/KiCad/9.0/bin/kicad-cli.exe')):
        if p.exists(): return str(p)
    return None

def run(args, cwd: Path, output: Path, timeout=ENGINE_TIMEOUT):
    output.parent.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy()
    # AI credentials have no reason to be in the checker's environment.
    for key in list(env):
        if any(x in key.upper() for x in ('API_KEY','TOKEN','SECRET','PASSWORD')): env.pop(key)
    config=output.parent/'engine-config'
    config.mkdir(exist_ok=True)
    env['KICAD_CONFIG_HOME']=str(config)
    env['KICAD_DOCUMENTS_HOME']=str(config/'documents')
    env['KIPRJMOD']=str(cwd)
    env['OMP_NUM_THREADS']='2'
    env['QT_QPA_PLATFORM']='offscreen'
    with output.open('w',encoding='utf-8') as log:
        try:
            proc=subprocess.Popen([str(x) for x in args],cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,shell=False,
                                  creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0,
                                  preexec_fn=unix_limits if os.name!='nt' else None)
            close_job=None
            try:
                close_job=windows_job(proc)
                code=proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill(); proc.wait()
                raise EngineError(f'KiCad exceeded the {timeout} second execution limit. See the retained log.')
            except OSError:
                proc.kill();proc.wait();raise
            finally:
                if close_job:close_job()
        except OSError as e: raise EngineError(f'Could not start KiCad: {e}') from e
    return code,output.read_text(encoding='utf-8',errors='replace')[-32000:]

class KiCad:
    def __init__(self, probe_dir: Path):
        self.exe=executable()
        if not self.exe: raise EngineError('KiCad CLI is unavailable. Install KiCad 10.0.7 on the server and set KICAD_CLI. No electrical or design-rule checks ran.')
        self.probe_dir=probe_dir
        code,out=run([self.exe,'version'],probe_dir,probe_dir/'version.log',15)
        self.version=out.strip().splitlines()[-1] if code==0 and out.strip() else 'unknown'
        if not self.version.startswith('10.0.'):
            raise EngineError(f'KiCad {self.version} is not verified. This adapter requires KiCad 10.0.x; tested pin {PINNED_ENGINE}.')
        self.helps={}

    def help(self,command):
        key='-'.join(command)
        if key not in self.helps:
            code,out=run([self.exe,*command,'--help'],self.probe_dir,self.probe_dir/(key+'-help.log'),15)
            if code: raise EngineError(f'Installed CLI does not provide {" ".join(command)}')
            self.helps[key]=out
        return self.helps[key]

    def report(self,source: Path,kind: str,out: Path,parity=False):
        cmd=['pcb','drc'] if kind=='DRC' else ['sch','erc']
        help=self.help(cmd)
        required=['--format','--severity-all','--exit-code-violations']
        if any(x not in help for x in required): raise EngineError(f'{kind} JSON reporting is unavailable in this KiCad build')
        args=[self.exe,*cmd,'--format','json','--severity-all','--exit-code-violations','--units','mm','--output',out]
        if kind=='DRC':
            if '--refill-zones' not in help: raise EngineError('Zone-refill support is required for this adapter')
            args+=['--refill-zones']
            if parity and '--schematic-parity' in help: args+=['--schematic-parity']
        code,log=run([*args,source],source.parent,out.with_suffix('.log'))
        if code not in (0,5) or not out.exists(): raise EngineError(f'{kind} could not complete (exit {code}). {log[-1500:]}')
        try: report=json.loads(out.read_text(encoding='utf-8-sig'))
        except ValueError as e: raise EngineError(f'{kind} returned an unreadable report') from e
        if not isinstance(report,dict) or (kind=='DRC' and 'violations' not in report) or (kind=='ERC' and 'sheets' not in report):
            raise EngineError(f'{kind} report schema is unsupported')
        if code==5 and not any(report.get(k) for k in ('violations','sheets','unconnected_items','schematic_parity')):
            raise EngineError('Violation exit code without usable finding evidence')
        return report

    def pcb_preview(self,source: Path,out: Path):
        help=self.help(['pcb','export','svg'])
        if '--page-size-mode' not in help: raise EngineError('Verified full-page SVG export is unavailable')
        args=[self.exe,'pcb','export','svg','--layers','F.Cu,B.Cu,F.SilkS,Edge.Cuts','--mode-single',
              '--page-size-mode','1','--exclude-drawing-sheet','--output',out]
        if '--check-zones' in help: args+=['--check-zones']
        code,log=run([*args,source],source.parent,out.with_suffix('.log'))
        if code or not out.exists(): raise EngineError(f'Board preview failed (exit {code}): {log[-700:]}')
        info=sanitize_svg(out,board=True)
        info['layers']=[]
        for layer in ('B.Cu','F.Cu','F.SilkS','Edge.Cuts'):
            name='layer-'+layer.replace('.','-')+'.svg'
            target=out.parent/name
            layer_args=[self.exe,'pcb','export','svg','--layers',layer,'--mode-single','--page-size-mode','1','--exclude-drawing-sheet','--output',target]
            if '--check-zones' in help: layer_args+=['--check-zones']
            code,log=run([*layer_args,source],source.parent,target.with_suffix('.log'))
            if code or not target.exists(): raise EngineError(f'Layer export {layer} failed: {log[-500:]}')
            layer_info=sanitize_svg(target,board=True)
            if layer_info['view_box']!=info['view_box'] or layer_info['mapping']!=info['mapping']:
                raise EngineError('Layer coordinate transforms do not match; overlay rejected')
            info['layers'].append({'name':layer,'artifact':name})
        return info

    def schematic_exports(self,source:Path,out:Path,project_root=None):
        from .schematic import sheet_sources
        help=self.help(['sch','export','svg'])
        folder=out/'schematic'; folder.mkdir(exist_ok=True)
        self.help(['sch','export','netlist'])
        code,log=run([self.exe,'sch','export','netlist','--format','kicadxml','--output',out/'netlist.xml',source],source.parent,out/'netlist.log')
        if code: raise EngineError(f'Netlist export failed: {log[-700:]}')
        project_root=project_root or source.parent
        sources=sheet_sources(source,project_root)
        pages=ET.parse(out/'netlist.xml').getroot().findall('design/sheet')
        if '--pages' not in help:raise EngineError('Native per-sheet SVG export is unavailable; sheet mapping was not guessed.')
        root_uuid=parse(source.read_text(encoding='utf-8-sig')).get('uuid').arg()
        previews=[]
        for page in pages:
            number=page.get('number','')
            if not re.fullmatch(r'[A-Za-z0-9._-]{1,32}',number):raise EngineError('Unsupported schematic page identifier')
            path=sources.get(page.get('tstamps','/'))
            if not path:raise EngineError('Native sheet could not be linked to its source')
            target=folder/('page-'+number)
            if target.exists():shutil.rmtree(target)
            target.mkdir()
            code,log=run([self.exe,'sch','export','svg','--exclude-drawing-sheet','--pages',number,'--output',target,source],source.parent,out/('schematic-page-'+number+'.log'))
            exported=list(target.glob('*.svg'))
            if code or len(exported)!=1:raise EngineError(f'Schematic page {number} export failed: {log[-700:]}')
            p=exported[0];info=sanitize_svg(p,board=False)
            info.update({'artifact':p.relative_to(out).as_posix(),'file':path.relative_to(project_root).as_posix(),'sheet_path':page.get('name','/'),'sheet_number':number,'sheet_uuid':'/'+root_uuid+page.get('tstamps','/').rstrip('/')})
            previews.append(info)
        return previews

def sanitize_svg(path:Path,board=False):
    root=ET.parse(path).getroot()
    allowed={'svg','g','path','circle','ellipse','line','polyline','polygon','rect','text','tspan','defs','clipPath','title','desc'}
    for parent in list(root.iter()):
        for child in list(parent):
            if child.tag.split('}')[-1] not in allowed: parent.remove(child)
        for k,v in list(parent.attrib.items()):
            local=k.split('}')[-1]
            if local.lower().startswith('on') or local in ('href','src') or any(x in v.lower() for x in ('url(', 'javascript:', '@import', 'expression(')):
                del parent.attrib[k]
    vb=[float(x) for x in root.attrib.get('viewBox','0 0 0 0').split()]
    width=root.attrib.get('width','')
    height=root.attrib.get('height','')
    # Full-page, unmirrored, scale=1 exports preserve KiCad's top-left mm origin.
    # We do not infer an origin for fitted/cropped exports or arbitrary imported SVG.
    mapping=None
    if len(vb)==4 and width.endswith('mm') and height.endswith('mm'):
        sx=vb[2]/float(width[:-2]); sy=vb[3]/float(height[:-2])
        if sx>0 and abs(sx-sy)<0.01: mapping={'scale_x':sx,'scale_y':sy,'offset_x':vb[0],'offset_y':vb[1],'convention':'KiCad top-left, X right, Y down; mm; full-page scale 1'}
    import xml.etree.ElementTree as Writer
    Writer.register_namespace('', 'http://www.w3.org/2000/svg')
    Writer.ElementTree(root).write(path,encoding='utf-8',xml_declaration=True)
    return {'artifact':path.name,'view_box':vb,'mapping':mapping,'kind':'pcb' if board else 'schematic'}

def normalize(report,kind,source,board_text=None):
    entries=[]
    if kind=='DRC':
        for key in ('violations','unconnected_items','schematic_parity'):
            entries.extend(report.get(key,[]))
    else:
        for sheet in report.get('sheets',[]):
            for v in sheet.get('violations',[]):
                entries.append({**v,'sheet':sheet.get('path',''),'sheet_uuid':sheet.get('uuid_path','').rstrip('/')})
    track_map={t['id']:t for t in tracks(board_text)} if board_text else {}
    result=[]
    seen=set()
    for v in entries:
        rule=v.get('type','unknown')
        items=v.get('items',[])
        ids=[x.get('uuid') for x in items if x.get('uuid')]
        stable=hashlib.sha256(json.dumps([kind,source,rule,sorted(ids),v.get('sheet')],sort_keys=True).encode()).hexdigest()[:20]
        if stable in seen: continue
        seen.add(stable)
        description=v.get('description','No description supplied by engine.')
        pos=next((x.get('pos') for x in items if isinstance(x.get('pos'),dict)),None)
        measured=required=None
        # Only literal report measurements are used. No design limits are guessed.
        actual=re.search(r'(?:actual|measured)\s+([\d.]+)\s*(mm|mils|in)\b',description,re.I)
        minimum=re.search(r'(?:min(?:imum)?(?: width| clearance| height)?|required)\s+([\d.]+)\s*(mm|mils|in)\b',description,re.I)
        if actual: measured={'value':float(actual[1]),'unit':actual[2]}
        if minimum: required={'value':float(minimum[1]),'unit':minimum[2]}
        repair=None
        track=next((track_map[x] for x in ids if x in track_map),None)
        if rule=='track_width' and track and measured and required and required['unit']=='mm' and measured['unit']=='mm' and 0<track['width']<required['value']<=10:
            repair={'kind':'track_width','object_id':track['id'],'from':track['width'],'to':required['value'],'file':source}
        excluded=v.get('excluded',False) or v.get('severity')=='exclusion'
        suggestions={
            'track_width':'Set the identified track segment to at least the reported minimum width, then rerun DRC.',
            'clearance':'Move the identified copper features apart to satisfy the reported clearance rule, then rerun DRC.',
            'unconnected_items':'Review the listed endpoints and complete the intended connection in KiCad, then rerun DRC.',
            'pin_not_connected':'Connect the named pin as intended, or explicitly mark an intentionally unused pin in KiCad, then rerun ERC.',
            'lib_footprint_mismatch':'Review the embedded footprint against the specified project library before updating it.',
            'lib_footprint_issues':'Provide the referenced footprint library and rerun the check.'}
        titles={'track_width':'Track width below configured minimum','track_dangling':'Track has an unconnected end','silk_over_copper':'Silkscreen overlaps a solder-mask opening','text_height':'Silkscreen text height outside rule','clearance':'Copper clearance below configured minimum','unconnected_items':'Connection is incomplete','pin_not_connected':'Pin is not connected'}
        result.append({'id':stable,'source':f'KiCad {kind}','category':'Rule violation','rule':rule,
                       'title':titles.get(rule,rule.replace('_',' ').capitalize()),'severity':v.get('severity','warning'),'excluded':excluded,
                       'file':source,'sheet':v.get('sheet'),'sheet_uuid':v.get('sheet_uuid'),'objects':items,'object_ids':ids,'position':pos,
                       'layer':track['layer'] if track else None,'net':track['net'] if track else None,
                       'measured':measured,'required':required,'evidence':description,'explanation':description,
                       'suggestion':suggestions.get(rule,'Inspect the named objects and the reported rule in KiCad. Apply a design change appropriate to the evidence, then rerun this check.'),
                       'repair':repair,'verification':'Detected by engine','rule_source':'Project settings / custom rules; exact rule in original engine evidence'})
    return result

def board_bounds(text):
    root=parse(text); points=[]
    for n in root.children:
        layer=n.get('layer') if n.children else None
        if layer and layer.arg()=='Edge.Cuts':
            for tag in ('start','end','mid','center'):
                if n.get(tag): points.append([number(n,tag),number(n,tag,2)])
    if not points:
        for t in tracks(text): points.extend([t['start'],t['end']])
    if not points: return None
    return [min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points)]

def compare(old,new):
    a={x['id']:x for x in old.get('findings',[])}; b={x['id']:x for x in new.get('findings',[])}
    rules_changed=old.get('rules_fingerprint')!=new.get('rules_fingerprint')
    profile_changed=old.get('provenance',{}).get('rule_profile')!=new.get('provenance',{}).get('rule_profile')
    engine_changed=old.get('engine_version')!=new.get('engine_version') or old.get('provenance',{}).get('normalizer')!=new.get('provenance',{}).get('normalizer')
    coverage_changed=signature(old.get('coverage',[]))!=signature(new.get('coverage',[])) if not (old.get('coverage') and new.get('coverage')) else [(c['id'],c['status']) for c in old['coverage']]!=[(c['id'],c['status']) for c in new['coverage']]
    unstable_identity=any(f.get('identity_status')!='stable_native_ids' for f in [*[a[k] for k in a.keys()-b.keys()],*[b[k] for k in b.keys()-a.keys()]])
    comparable=not(rules_changed or profile_changed or engine_changed or coverage_changed or unstable_identity) and bool(old.get('provenance') and new.get('provenance'))
    return {'resolved':[a[k] for k in a.keys()-b.keys()], 'remaining':[b[k] for k in a.keys()&b.keys()], 'new':[b[k] for k in b.keys()-a.keys()],
            'complete':old.get('status')=='completed' and new.get('status')=='completed',
            'resolution_verified':comparable and old.get('status')=='completed' and new.get('status')=='completed',
            'rules_changed':rules_changed,'profile_changed':profile_changed,'engine_changed':engine_changed,'coverage_changed':coverage_changed,
            'unstable_identity':unstable_identity,
            'before_provenance':old.get('provenance',{}),'after_provenance':new.get('provenance',{}),
            'changed_evidence':[{'before':a[k],'after':b[k]} for k in a.keys()&b.keys() if a[k].get('evidence_fingerprint')!=b[k].get('evidence_fingerprint')],
            'geometry':geometry_diff(old.get('geometry'),new.get('geometry'))}

def analyze(source:Path,artifacts:Path,manifest,progress=lambda _:None):
    artifacts.mkdir(parents=True,exist_ok=True)
    engine=KiCad(artifacts)
    before=fingerprint(source)
    rules=hashlib.sha256(b''.join(p.read_bytes() for p in sorted(source.rglob('*')) if p.suffix in ('.kicad_pro','.kicad_dru'))).hexdigest()
    key=hashlib.sha256(json.dumps([before,rules,engine.version,manifest['root'],manifest.get('rule_profile'),ADAPTER_VERSION,NORMALIZER_VERSION,'geometry-v1;schematic-sheets-v1;refill-zones;all-severities;full-page-svg-v2'],sort_keys=True).encode()).hexdigest()
    cache=artifacts/'result.json'
    if cache.exists():
        cached=json.loads(cache.read_text())
        if cached.get('cache_key')==key and cached['status']=='completed': return {**cached,'cached':True}
    # KiCad can create .kicad_prl session preferences even without --save-board.
    # Every engine operation therefore runs in a disposable copy, never a revision.
    original_source=source
    work=artifacts/'working'
    if work.exists(): shutil.rmtree(work)
    shutil.copytree(source,work)
    source=work
    checks=[]; findings=[]; previews=[]; geometry={'version':'board-index-1.0','objects':[],'nets':[],'limitations':[]}
    root=manifest['root']
    if root is None: raise EngineError('Choose a root project before analysis')
    pcb=source/(root+'.kicad_pcb'); sch=source/(root+'.kicad_sch')
    dependencies_missing=any(x['kind']=='missing' for x in manifest['notices'])
    for kind,path in (('DRC',pcb),('ERC',sch)):
        if not path.exists():
            checks.append({'name':kind,'status':'skipped','message':f'No {"board" if kind=="DRC" else "schematic"} was supplied.'})
            continue
        if kind=='ERC' and any('subsheet' in x['message'] for x in manifest['notices']):
            checks.append({'name':kind,'status':'skipped','message':'Missing hierarchy. Upload the missing subsheets.'})
            continue
        progress(f'Running {kind}')
        try:
            report=engine.report(path,kind,artifacts/(kind.lower()+'.json'),parity=kind=='DRC' and sch.exists() and not dependencies_missing)
            findings+=normalize(report,kind,path.relative_to(source).as_posix(),path.read_text(encoding='utf-8-sig') if kind=='DRC' else None)
            checks.append({'name':kind,'status':'completed','message':'Original report retained; project severities and exclusions included.',
                           'ignored_checks':[x.get('key','unknown') for x in report.get('ignored_checks',[]) if isinstance(x,dict)]})
        except EngineError as e: checks.append({'name':kind,'status':'failed','message':str(e)})
        progress('Exporting board preview' if kind=='DRC' else 'Exporting sheets and netlist')
        try:
            if kind=='DRC':
                preview=engine.pcb_preview(path,artifacts/'board.svg')
                preview.update({'file':path.relative_to(source).as_posix(),'bounds_mm':board_bounds(path.read_text(encoding='utf-8-sig'))})
                previews.append(preview)
                checks.append({'name':'PCB preview','status':'completed','message':'Unmirrored full-page SVG; millimetre origin preserved.'})
            else:
                for preview in engine.schematic_exports(path,artifacts,source):
                    previews.append(preview)
                checks.append({'name':'Schematic preview & netlist','status':'completed','message':'SVG sheets and native connectivity exported.'})
        except EngineError as e: checks.append({'name':f'{kind} exports','status':'failed','message':str(e)})
    if not pcb.exists() or not sch.exists() or dependencies_missing:
        checks.append({'name':'Schematic / PCB parity','status':'skipped','message':'Requires a matching complete schematic and board with project dependencies.'})
    else: checks.append({'name':'Schematic / PCB parity','status':'completed' if next((c['status']=='completed' for c in checks if c['name']=='DRC'),False) else 'failed','message':'Included in PCB DRC.'})
    if pcb.exists():
        try:geometry=board_index(pcb.read_text(encoding='utf-8-sig'))
        except (ValueError,TypeError,ArithmeticError) as e:checks.append({'name':'Object geometry','status':'failed','message':'Exact object mapping unavailable: '+str(e)})
        native_python=Path(engine.exe).parent/('python.exe' if os.name=='nt' else 'python3')
        if native_python.is_file():
            try:
                code,log=run([native_python,Path(__file__).with_name('native_geometry.py'),pcb,artifacts/'native-geometry.json'],source,artifacts/'native-geometry.log')
                if code:raise EngineError(log[-500:])
                native=json.loads((artifacts/'native-geometry.json').read_text(encoding='utf-8'))
                index={o['id']:o for o in geometry['objects']}
                persisted=set(geometry.get('persisted_ids',[]));untracked=0
                for item in native['objects']:
                    if item['id'] not in persisted:
                        untracked+=1;continue
                    prior=index.get(item['id'],{})
                    merged={**prior,**item}
                    merged['signature']=signature({k:v for k,v in merged.items() if k not in ('id','signature')})
                    index[item['id']]=merged
                geometry['objects']=list(index.values())
                geometry['native_engine']=native['engine']
                geometry['untracked_objects']=untracked
                if untracked:geometry['limitations'].append(f'{untracked} native objects have no persistent source UUID and are omitted from exact revision matching.')
            except (EngineError,ValueError,OSError) as e:
                geometry['limitations'].append('Native envelopes unavailable; source-resolved supported objects only: '+str(e))
    profile=manifest.get('rule_profile')
    profile_coverage=[]
    if profile and profile.get('constraints') and pcb.exists():
        from .profiles import prepare_profile
        progress('Checking fabrication profile')
        fab_folder=artifacts/'fabrication-working'
        if fab_folder.exists():shutil.rmtree(fab_folder)
        try:
            fab_pcb=prepare_profile(source,fab_folder,root,profile)
            report=engine.report(fab_pcb,'DRC',artifacts/'fabrication-drc.json')
            fab_findings=normalize(report,'DRC',pcb.relative_to(source).as_posix(),pcb.read_text(encoding='utf-8-sig'))
            # Include only evidence that explicitly names one of our generated rules.
            for f in fab_findings:
                if 'CircuitCheck fabrication' not in f['evidence']:continue
                f['id']=signature(['fabrication',profile['fingerprint'],f['id']])[:20]
                f['source']='Fabrication DRC';f['repair']=None;f['rule_source']=profile['name']+' '+profile['version']
                findings.append(f)
            for key in profile['constraints']:
                profile_coverage.append({'id':'fab_'+key,'name':'Fabrication · '+key.replace('_',' '),'status':'checked','count':sum(f['source']=='Fabrication DRC' and ('CircuitCheck fabrication '+key) in f['evidence'] and not f['excluded'] for f in findings),'message':'Native DRC against selected profile; project rules remain independently checked.','basis':profile['name']+' · '+profile['version']})
            checks.append({'name':'Fabrication profile','status':'completed','message':'Native report retained as fabrication-drc.json.'})
        except (EngineError,ValueError) as e:
            checks.append({'name':'Fabrication profile','status':'failed','message':str(e)})
            profile_coverage=[{'id':'fab_'+key,'name':'Fabrication · '+key.replace('_',' '),'status':'failed','count':None,'message':str(e)} for key in profile['constraints']]
        finally:
            if fab_folder.exists():shutil.rmtree(fab_folder)
    else:
        profile_coverage=[{'id':'fabrication','name':'Manufacturer constraints','status':'not_checked','count':None,'message':'Select or import a numeric rule profile and supply a board. An order reference alone does not establish constraints.'}]
    failed=any(x['status']=='failed' for x in checks)
    completed=any(x['name'] in ('DRC','ERC') and x['status']=='completed' for x in checks)
    status='failed' if not completed else ('partial' if failed or dependencies_missing else 'completed')
    result={'status':status,'engine_version':engine.version,'checks':checks,'findings':findings,'previews':previews,
            'project_hash':before,'rules_fingerprint':rules,'cache_key':key,'cached':False,'zone_policy':'Refilled in memory on working copies for DRC; originals and saved zone fills are never rewritten.',
            'notices':manifest['notices'],'finished_at':time.time()}
    enrich(result,manifest,source,geometry)
    from .schematic import index_sheet
    result['schematic_geometry']={}
    for preview in previews:
        if preview['kind']!='schematic':continue
        # Preserve source paths relative to the complete upload, including nested roots.
        file=preview['file']
        result['schematic_geometry'][preview['artifact']]=index_sheet((source/file).read_text(encoding='utf-8-sig'),findings,preview)
    result['provenance']['schematic_geometry']='schematic-index-1.0'
    result['coverage']+=profile_coverage
    if fingerprint(original_source)!=before: raise EngineError('Revision changed during analysis; result rejected')
    for p in original_source.rglob('*'):
        if p.is_file() and p.suffix!='.kicad_prl' and p.read_bytes()!=(source/p.relative_to(original_source)).read_bytes():
            raise EngineError('Engine unexpectedly rewrote a design file in the disposable copy; result rejected')
    cache.write_text(json.dumps(result,indent=2),encoding='utf-8')
    shutil.rmtree(work)
    return result

