"""Original CC0 KiCad fixtures. Deterministic UUIDs; no third-party design content."""
import json
from pathlib import Path
from uuid import uuid5,NAMESPACE_URL

ROOT=Path(__file__).resolve().parents[1]/'fixtures'
def uid(s): return str(uuid5(NAMESPACE_URL,'circuitcheck-fixture/'+s))
def save(folder,name,content):
    p=ROOT/folder/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(content,encoding='utf-8')

header='''(kicad_pcb (version 20241229) (generator "circuitcheck-fixture")
 (general (thickness 1.6)) (paper "A4")
 (layers (0 "F.Cu" signal) (31 "B.Cu" signal) (36 "B.SilkS" user "b.silkscreen") (37 "F.SilkS" user "f.silkscreen") (38 "B.Mask" user) (39 "F.Mask" user) (44 "Edge.Cuts" user))
 (setup (pad_to_mask_clearance 0))
 (net 0 "") (net 1 "GND") (net 2 "+3V3") (net 3 "SDA") (net 4 "SCL")
'''
outline=f'(gr_rect (start 50 50) (end 110 90) (stroke (width 0.1) (type default)) (fill none) (layer "Edge.Cuts") (uuid "{uid("outline")} "))'.replace(' ")','")')

def text(value,x,y,size=1):
    return f'(gr_text "{value}" (at {x} {y}) (layer "F.SilkS") (uuid "{uid(value)}") (effects (font (size {size} {size}) (thickness 0.15))))'

def footprint(ref,x,y,pads,body=(-1.5,-1.5,1.5,1.5)):
    s=f'(footprint "{ref}" (layer "F.Cu") (uuid "{uid(ref)}") (at {x} {y})\n'
    s+=f'(property "Reference" "{ref}" (at 0 -2.4 0) (layer "F.SilkS") (effects (font (size 0.9 0.9) (thickness 0.13))))\n'
    s+=f'(property "Value" "Review fixture" (at 0 2.4 0) (layer "F.Fab") hide (effects (font (size 1 1) (thickness 0.15))))\n'
    s+=f'(fp_rect (start {body[0]} {body[1]}) (end {body[2]} {body[3]}) (stroke (width 0.15) (type default)) (fill none) (layer "F.SilkS"))\n'
    for i,(px,py,net) in enumerate(pads,1):
        s+=f'(pad "{i}" smd roundrect (at {px} {py}) (size 1.5 0.8) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.2) (net {net} "{["","GND","+3V3","SDA","SCL"][net]}") (uuid "{uid(ref+str(i))}"))\n'
    return s+')\n'

def segment(name,a,b,width=.3,net=1,layer='F.Cu'):
    return f'(segment (start {a[0]} {a[1]}) (end {b[0]} {b[1]}) (width {width}) (layer "{layer}") (net {net}) (uuid "{uid(name)}"))\n'

project={'board':{'design_settings':{'rules':{'min_track_width':0.25,'min_clearance':0.2,'min_copper_edge_clearance':0.2},
          'rule_severities':{'track_width':'error','clearance':'error','unconnected_items':'warning'}}},
         'meta':{'filename':'fieldnode.kicad_pro','version':1},'net_settings':{'classes':[{'name':'Default','clearance':0.2,'track_width':0.3,'via_diameter':0.6,'via_drill':0.3}]}}
s=header+outline+'\n'+text('FIELDNODE',65,55,1.4)+text('SENSOR INTERFACE / REV A',77,86,0.8)+text('REVIEW FIXTURE',95,55,0.8)
for j,(x,y) in enumerate([(54,54),(106,54),(54,86),(106,86)]):
    s+=f'(footprint "Mount" (layer "F.Cu") (uuid "{uid("mount"+str(j))}") (at {x} {y}) (pad "" np_thru_hole circle (at 0 0) (size 2.5 2.5) (drill 2.5) (layers "*.Cu" "*.Mask")))\n'
for side,x in [('J1',58),('J2',102)]:
    pads=[(0,i*2.54,(i%4)+1) for i in range(6)]
    s+=footprint(side,x,62,pads,(-1.6,-1.3,1.6,14.0))
pads=[(-4,i*1.27,(i%4)+1) for i in range(8)]+[(4,i*1.27,(i%4)+1) for i in range(8)]
s+=footprint('U1',80,65,pads,(-3,-1.5,3,10.4))
for i in range(6):
    x=67+(i%3)*12; y=60+(i//3)*20
    s+=footprint('R'+str(i+1),x,y,[(-1.5,0,(i%4)+1),(1.5,0,(i%4)+1)],(-.7,-.8,.7,.8))
    s+=segment('resistor'+str(i),(x-1.5,y),(x+1.5,y))
for i in range(6):
    y=62+i*2.54
    for side in ('left','right'):
        start=(58,y) if side=='left' else (102,y)
        mid=(63+i*.7,y) if side=='left' else (97-i*.7,y)
        end=(76,65+i*1.27) if side=='left' else (84,65+i*1.27)
        elbow=(mid[0]+(3 if side=='left' else -3),end[1])
        net=(i%4)+1
        s+=segment(f'{side}-{i}-a',start,mid,net=net)
        s+=segment(f'{side}-{i}-b',mid,elbow,net=net)
        s+=segment(f'{side}-{i}-c',elbow,end,net=net)
# Deliberate, spatially isolated width violation suitable for the controlled repair.
s+=segment('repair-target',(72,82),(87,82),width=.15,net=1)
s+=text('GND',70,82,.7)+text('3V3',61,59,.7)+text('SDA / SCL',100,79,.7)
save('fieldnode','fieldnode.kicad_pcb',s+')\n')
save('fieldnode','fieldnode.kicad_pro',json.dumps(project,indent=2))
save('valid','valid.kicad_pcb',header+outline+')\n')
save('valid','valid.kicad_pro',json.dumps(project,indent=2))
save('drc','drc.kicad_pcb',header+outline+segment('repair-target',(65,65),(85,65),.15)+')\n')
save('drc','drc.kicad_pro',json.dumps(project,indent=2))
save('corrected','drc.kicad_pcb',header+outline+segment('repair-target',(65,65),(85,65),.25)+')\n')
save('corrected','drc.kicad_pro',json.dumps(project,indent=2))
# Embedded test symbol avoids relying on an external symbol library for connectivity.
sch=f'''(kicad_sch (version 20250114) (generator "circuitcheck-fixture") (uuid "{uid('schematic')}") (paper "A4")
 (lib_symbols (symbol "Test:Output" (pin_names (offset 0)) (in_bom yes) (on_board yes)
   (property "Reference" "U" (at 0 2.54 0) (effects (font (size 1.27 1.27))))
   (property "Value" "Output" (at 0 -2.54 0) (effects (font (size 1.27 1.27))))
   (symbol "Output_1_1" (rectangle (start -2 2) (end 2 -2) (stroke (width 0) (type default)) (fill (type background)))
     (pin output line (at 5.08 0 180) (length 3.08) (name "OUT" (effects (font (size 1 1)))) (number "1" (effects (font (size 1 1))))))))
 (symbol (lib_id "Test:Output") (at 70 70 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid "{uid('U1sch')}")
   (property "Reference" "U1" (at 70 66 0) (effects (font (size 1.27 1.27))))
   (property "Value" "Output" (at 70 73 0) (effects (font (size 1.27 1.27))))
   (pin "1" (uuid "{uid('U1pin')}"))
   (instances (project "erc" (path "/{uid('schematic')}" (reference "U1") (unit 1)))))
 (sheet_instances (path "/" (page "1")))
)'''
save('erc','erc.kicad_sch',sch)
save('erc','erc.kicad_pro','{}')
validsch=f'(kicad_sch (version 20250114) (generator "circuitcheck-fixture") (uuid "{uid("validsch")}") (paper "A4") (lib_symbols) (sheet_instances (path "/" (page "1"))))'
save('valid_schematic','valid.kicad_sch',validsch)
save('valid_schematic','valid.kicad_pro','{}')
missing=validsch[:-1]+f'(sheet (at 100 100) (size 30 20) (stroke (width 0) (type default)) (fill (color 0 0 0 0)) (uuid "{uid("missing")}") (property "Sheetname" "Sensor" (at 100 99 0) (effects (font (size 1 1)))) (property "Sheetfile" "missing.kicad_sch" (at 100 121 0) (effects (font (size 1 1))))))'
save('missing','root.kicad_sch',missing)
save('hierarchy','root.kicad_sch',missing.replace('missing.kicad_sch','sheets/child.kicad_sch'))
save('hierarchy','root.kicad_pro','{}')
save('hierarchy','sheets/child.kicad_sch',validsch)
save('custom_rules','rules.kicad_pcb',header+outline+segment('repair-target',(65,65),(85,65),.15)+')\n')
save('custom_rules','rules.kicad_pro',json.dumps(project,indent=2))
save('custom_rules','rules.kicad_dru',"# Original fixture custom rule\n(version 1)\n(rule \"Review width\" (condition \"A.Type == 'Track'\") (constraint track_width (min 0.35mm)))\n")
save('missing_library','board.kicad_pcb',header+outline+')\n')
save('missing_library','board.kicad_pro',json.dumps(project,indent=2))
save('missing_library','fp-lib-table','(fp_lib_table (lib (name "Test") (type "KiCad") (uri "${KIPRJMOD}/not-supplied.pretty") (options "") (descr "")))')
save('malformed','bad.kicad_pcb','(kicad_pcb (broken')
save('','LICENSE.txt','All fixture design files in this directory are original CircuitCheck test content dedicated to the public domain under CC0 1.0. https://creativecommons.org/publicdomain/zero/1.0/\nThey are synthetic test designs, not a validated functional circuit.\n')
print('Generated original KiCad fixtures')
