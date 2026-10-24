"""UUID-resolved board geometry in millimetres, independent of exported SVG IDs.

Tracks/arcs use their native centreline; pads/components use explicit envelopes.
Unsupported objects stay unresolved rather than being assigned guessed geometry.
"""
import hashlib
import json
import math
import re
from .sexpr import parse, number

VERSION = 'board-index-1.0'

def uid(node):
    value = node.get('uuid') or node.get('tstamp')
    return value.arg() if value else None

def point(node, tag):
    return [number(node, tag), number(node, tag, 2)] if node.get(tag) else None

def tree(node):
    return [tree(n) for n in node.children] if node.children else node.value

def signature(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def transform(p, at, angle):
    a = math.radians(angle)
    return [at[0]+p[0]*math.cos(a)+p[1]*math.sin(a), at[1]-p[0]*math.sin(a)+p[1]*math.cos(a)]

def arc_points(a, b, c):
    d = 2*(a[0]*(b[1]-c[1])+b[0]*(c[1]-a[1])+c[0]*(a[1]-b[1]))
    if abs(d) < 1e-12: return [a,b,c]
    sq = lambda p: p[0]*p[0]+p[1]*p[1]
    x=(sq(a)*(b[1]-c[1])+sq(b)*(c[1]-a[1])+sq(c)*(a[1]-b[1]))/d
    y=(sq(a)*(c[0]-b[0])+sq(b)*(a[0]-c[0])+sq(c)*(b[0]-a[0]))/d
    angles=[math.atan2(p[1]-y,p[0]-x) for p in (a,b,c)]
    end=(angles[2]-angles[0])%(2*math.pi); mid=(angles[1]-angles[0])%(2*math.pi)
    sweep=end if mid<=end else end-2*math.pi
    radius=math.hypot(a[0]-x,a[1]-y)
    return [[x+radius*math.cos(angles[0]+sweep*i/64), y+radius*math.sin(angles[0]+sweep*i/64)] for i in range(65)]

def board_index(text):
    root=parse(text)
    if root.tag!='kicad_pcb': raise ValueError('Expected a KiCad board')
    nets={n.arg():n.arg(2,'') for n in root.all('net')}
    objects=[]
    persisted=[]
    def identities(node):
        identifier=uid(node)
        if identifier:persisted.append(identifier)
        for child in node.children:
            if child.children:identities(child)
    identities(root)
    def net_name(n):
        value=n.get('net')
        return value.arg(2,nets.get(value.arg(),value.arg())) if value else None
    def add(n, kind, points, **extra):
        identifier=uid(n)
        if not identifier or not points or any(v is None or not math.isfinite(v) for p in points for v in p): return
        item={'id':identifier,'kind':kind,'points':points,'layer':n.get('layer').arg() if n.get('layer') else None,
              'net':net_name(n),'width':number(n,'width') or 0, **extra}
        # Semantic signatures omit file formatting and UUID representation.
        item['signature']=signature({k:v for k,v in item.items() if k!='id'})
        objects.append(item)
    for n in root.children:
        if n.tag in ('segment','arc'):
            pts=[point(n,'start'),point(n,'end')]
            if n.tag=='arc': pts=arc_points(pts[0],point(n,'mid'),pts[1])
            add(n,'track',pts,shape='polyline')
        elif n.tag=='via':
            p=point(n,'at'); size=number(n,'size') or 0
            add(n,'via',[p],shape='circle',radius=size/2,drill=number(n,'drill'))
        elif n.tag=='zone':
            poly=n.get('polygon'); pts=poly.get('pts') if poly else None
            if pts: add(n,'zone',[point(p,'xy') if p.get('xy') else [float(p.arg()),float(p.arg(2))] for p in pts.all('xy')],shape='polygon',envelope=True)
        elif n.tag=='footprint':
            at=point(n,'at') or [0,0]; angle=float(n.get('at').arg(3,0)) if n.get('at') else 0
            properties={x.arg():x.arg(2) for x in n.all('property')}
            ref=properties.get('Reference') or next((x.arg(2) for x in n.all('fp_text') if x.arg()=='reference'),None)
            extent=[]
            for pad in n.all('pad'):
                p=point(pad,'at') or [0,0]; centre=transform(p,at,angle)
                size=point(pad,'size') or [0,0]
                # Pad orientation is stored in board coordinates in PCB files.
                pad_angle=float(pad.get('at').arg(3,0)) if pad.get('at') else 0
                corners=[transform([x*size[0]/2,y*size[1]/2],centre,pad_angle) for x,y in [(-1,-1),(1,-1),(1,1),(-1,1)]]
                extent.extend(corners)
                add(pad,'pad',corners,shape='polygon',reference=ref,pad=pad.arg(),parent_id=uid(n),envelope=True,net=net_name(pad))
            for graphic in n.children:
                if graphic.tag in ('fp_line','fp_rect'):
                    for tag in ('start','end'):
                        p=point(graphic,tag)
                        if p: extent.append(transform(p,at,angle))
            if extent:
                x0=min(p[0] for p in extent);y0=min(p[1] for p in extent);x1=max(p[0] for p in extent);y1=max(p[1] for p in extent)
                add(n,'component',[[x0,y0],[x1,y0],[x1,y1],[x0,y1]],shape='polygon',reference=ref,value=properties.get('Value'),angle=angle,envelope=True,
                    properties_signature=signature(tree(n)))
        elif n.tag in ('gr_line','gr_rect','gr_arc','gr_circle'):
            a=point(n,'start') or point(n,'center');z=point(n,'end')
            if a and z:
                pts=[a,z]
                if n.tag=='gr_rect':pts=[a,[z[0],a[1]],z,[a[0],z[1]]]
                if n.tag=='gr_arc':pts=arc_points(a,point(n,'mid'),z)
                add(n,'graphic',pts,shape='polygon' if n.tag=='gr_rect' else 'polyline')
        elif n.tag=='gr_text':
            p=point(n,'at')
            if p:add(n,'text',[p],shape='point',text=n.arg(),envelope=True)
    return {'version':VERSION,'objects':objects,'persisted_ids':persisted,'nets':sorted({x['net'] for x in objects if x.get('net')}),
            'limitations':['Pads and components highlight their UUID-resolved envelopes, not an inferred collision point.','Zone outlines are source contours; poured geometry is rendered by KiCad.','Unsupported object geometry is explicitly unavailable.']}

def link_findings(findings, geometry, schematic_sources=()):
    objects={o['id']:o for o in geometry.get('objects',[])}
    reference_candidates={}
    for o in objects.values():
        if o['kind']=='component' and o.get('reference'):reference_candidates.setdefault(o['reference'],[]).append(o['id'])
    refs={ref:ids[0] for ref,ids in reference_candidates.items() if len(ids)==1}
    symbols={};persisted=set(geometry.get('persisted_ids',objects))
    for path in schematic_sources:
        try:
            root=parse(path.read_text(encoding='utf-8-sig'))
            def identities(node):
                identifier=uid(node)
                if identifier:persisted.add(identifier)
                for child in node.children:
                    if child.children:identities(child)
            identities(root)
            for symbol in root.all('symbol'):
                ref=next((p.arg(2) for p in symbol.all('property') if p.arg()=='Reference'),None)
                if ref and ref in refs:
                    symbols[uid(symbol)]=refs[ref]
                    for pin in symbol.all('pin'):
                        pads=[o['id'] for o in objects.values() if o['kind']=='pad' and o.get('reference')==ref and o.get('pad')==pin.arg()]
                        symbols[uid(pin)]=pads[0] if len(pads)==1 else refs[ref]
        except (ValueError,OSError):continue
    for f in findings:
        f['identity_status']='stable_native_ids' if f.get('object_ids') and all(identifier in persisted for identifier in f['object_ids']) else 'unresolved_native_ids'
        ids=[]
        for identifier in f.get('object_ids',[]):
            target=identifier if identifier in objects else symbols.get(identifier)
            if target and target not in ids:ids.append(target)
        f['board_object_ids']=ids
        f['highlight_status']='exact_objects' if ids else ('reported_location' if f.get('position') and f['source']=='KiCad DRC' else 'unavailable')
        f['highlight_message']='UUID-resolved board objects; pad/component envelopes are labelled.' if ids else ('Engine-reported position only; exact object geometry unavailable.' if f['highlight_status']=='reported_location' else 'No board object mapping was established. Inspect the exact source objects in KiCad; no guessed highlight is shown.')
        linked=[objects[i] for i in ids]
        f['references']=sorted({o['reference'] for o in linked if o.get('reference')})
        f['nets']=sorted({o['net'] for o in linked if o.get('net')})
        if len(f['nets'])==1:f['net']=f['nets'][0]
        f['object_signature']=signature([objects[i]['signature'] for i in sorted(ids)]) if ids else None

def geometry_diff(before, after):
    a={x['id']:x for x in (before or {}).get('objects',[])};b={x['id']:x for x in (after or {}).get('objects',[])}
    changes=[]
    for identifier in sorted(a.keys()|b.keys()):
        old=a.get(identifier);new=b.get(identifier)
        if old and new and old['signature']==new['signature']:continue
        changes.append({'id':identifier,'kind':(new or old)['kind'],'reference':(new or old).get('reference'),
                        'status':'added' if not old else 'removed' if not new else 'modified','before':old,'after':new})
    return {'available':bool(before and after),'objects':changes,
            'components':[c for c in changes if c['kind']=='component'],
            'connections':[c for c in changes if c['kind'] in ('track','pad','via')],
            'note':'Physical routing and pad net assignments are compared by UUID. This does not infer logical intent or prove connectivity equivalence; rewritten UUIDs appear as added/removed.'}
