"""Source identities and native report locations for individual schematic sheets."""
from pathlib import Path
import math
from .sexpr import parse
from .geometry import uid, point, signature


def sheet_sources(source, project_root):
    """Resolve hierarchy UUID paths; repeated instances keep their own sheet path."""
    result={}
    def walk(path, instance='/', ancestors=()):
        path=path.resolve()
        if not path.is_relative_to(project_root.resolve()) or path in ancestors or len(ancestors)>32:
            raise ValueError('Unsupported or cyclic schematic hierarchy')
        root=parse(path.read_text(encoding='utf-8-sig'))
        result[instance]=path
        for sheet in root.all('sheet'):
            filename=next((p.arg(2) for p in sheet.all('property') if p.arg()=='Sheetfile'),None)
            identifier=uid(sheet)
            if filename and identifier:walk(path.parent/filename,instance+identifier+'/',(*ancestors,path))
    walk(source)
    return result


def index_sheet(text, findings, preview):
    root=parse(text);objects={};persisted=set()
    def collect(node):
        identifier=uid(node)
        if identifier:persisted.add(identifier)
        for child in node.children:
            if child.children:collect(child)
    collect(root)
    for node in root.children:
        identifier=uid(node)
        if not identifier:continue
        pts=[];shape='point';kind=node.tag
        if node.tag in ('wire','bus'):
            points=node.get('pts')
            pts=[[float(p.arg()),float(p.arg(2))] for p in points.all('xy')] if points else []
            shape='polyline'
        elif node.tag in ('symbol','label','global_label','hierarchical_label','junction','no_connect','text'):
            p=point(node,'at') or point(node,'position')
            if p:pts=[p]
        if not pts:continue
        ref=next((p.arg(2) for p in node.all('property') if p.arg()=='Reference'),None)
        obj={'id':identifier,'kind':'symbol anchor' if kind=='symbol' else kind,'shape':shape,'points':pts,'reference':ref,'location_basis':'Source coordinates'}
        obj['signature']=signature(obj);objects[identifier]=obj
    matching=[f for f in findings if f['source']=='KiCad ERC' and (f.get('sheet_uuid')==preview['sheet_uuid'] or (not f.get('sheet_uuid') and f.get('sheet')==preview['sheet_path']))]
    for finding in matching:
        identifiers=[]
        for item in finding['objects']:
            identifier=item.get('uuid');p=item.get('pos')
            if identifier not in persisted:continue
            if identifier not in objects and p and all(isinstance(p.get(k),(int,float)) and math.isfinite(p[k]) for k in ('x','y')):
                obj={'id':identifier,'kind':'reported pin / object location','shape':'point','points':[[p['x'],p['y']]],'location_basis':'Native ERC coordinates; symbol outline is not inferred'}
                obj['signature']=signature(obj);objects[identifier]=obj
            if identifier in objects:identifiers.append(identifier)
        finding['schematic_object_ids']=identifiers
        finding['schematic_preview']=preview['artifact']
        finding['schematic_file']=preview['file']
        finding['schematic_highlight_message']='Native sheet and UUID-resolved source objects. Pins use engine-reported coordinates; symbol anchors are labelled.' if identifiers else 'Exact source geometry unavailable; inspect the native ERC evidence.'
    return {'version':'schematic-index-1.0','objects':list(objects.values()),'nets':[],
            'limitations':['Symbol highlights identify anchors and reported pins, not an inferred symbol-body outline.','Wire geometry comes from source UUIDs. Logical net tracing remains available in KiCad.']}
