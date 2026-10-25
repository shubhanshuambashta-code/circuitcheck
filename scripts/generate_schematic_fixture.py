"""Original CC0 schematic corresponding to the synthetic Fieldnode board."""
from pathlib import Path
from uuid import uuid5,NAMESPACE_URL

def uid(value):return str(uuid5(NAMESPACE_URL,'circuitcheck-fixture/'+value))

def generate(folder):
    def symbol_type(name,count,prefix='U'):
        rows=(count+1)//2
        text=f'(symbol "{name}" (pin_names (offset 0.5)) (in_bom yes) (on_board yes) (property "Reference" "{prefix}" (at 0 3.81 0) (effects (font (size 1.27 1.27)))) (property "Value" "{name.split(":")[-1]}" (at 0 -3.81 0) (effects (font (size 1.27 1.27))))'
        simple=name.split(':')[-1]
        text+=f'(symbol "{simple}_1_1" (rectangle (start -7.62 2.54) (end 7.62 {-rows*2.54}) (stroke (width 0.254) (type default)) (fill (type background)))'
        for i in range(count):
            x=-10.16 if i%2==0 else 10.16;y=-(i//2)*2.54
            text+=f'(pin passive line (at {x} {y} {0 if x<0 else 180}) (length 2.54) (name "{i+1}" (effects (font (size 1 1)))) (number "{i+1}" (effects (font (size 1 1)))))'
        return text+'))'
    types=[('Header6',6,'J'),('Interface16',16,'U'),('Passive2',2,'R')]
    embedded=''.join(symbol_type('CircuitCheck:'+name,count,prefix) for name,count,prefix in types)
    library=''.join(symbol_type(name,count,prefix) for name,count,prefix in types)
    root=uid('fieldnode-sch')
    text=f'(kicad_sch (version 20250114) (generator "circuitcheck-fixture") (uuid "{root}") (paper "A4") (lib_symbols {embedded})'
    text+=f'(text "FIELDNODE / SCHEMATIC REVIEW" (at 111.76 25.4 0) (effects (font (size 2 2))) (uuid "{uid("sch-title")}"))'
    text+=f'(text "Synthetic fixture: R1 pin 1 is intentionally unconnected in revision A." (at 111.76 175.26 0) (effects (font (size 1.27 1.27))) (uuid "{uid("sch-note")}"))'
    parts=[('J1','Header6',48.26,60.96,6),('U1','Interface16',111.76,60.96,16),('J2','Header6',175.26,60.96,6)]
    parts += [('R'+str(i+1),'Passive2',60.96+(i%3)*50.8,116.84+(i//3)*30.48,2) for i in range(6)]
    nets=['GND','+3V3','SDA','SCL']
    for ref,kind,x,y,count in parts:
        text+=f'(symbol (lib_id "CircuitCheck:{kind}") (at {x} {y} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid "{uid("sch-"+ref)}")'
        for name,value,dy,hidden in [('Reference',ref,-7.62,''),('Value','Review fixture',-5.08,''),('Footprint',ref,0,'hide')]:
            text+=f'(property "{name}" "{value}" (at {x} {y+dy} 0) (effects (font (size 1.27 1.27)) {hidden}))'
        for i in range(count):text+=f'(pin "{i+1}" (uuid "{uid("sch-"+ref+"-pin-"+str(i+1))}"))'
        text+=f'(instances (project "fieldnode" (path "/{root}" (reference "{ref}") (unit 1)))))'
        for i in range(count):
            px=x+(-10.16 if i%2==0 else 10.16);py=y+(i//2)*2.54
            if ref=='R1' and i==0:continue
            # Board pads alternate by row for U1; other footprints follow pad order.
            net=nets[(i%8)%4] if ref=='U1' else nets[(int(ref[1:])-1)%4] if ref.startswith('R') else nets[i%4]
            text+=label(ref,i+1,net,px,py)
    text+='(sheet_instances (path "/" (page "1"))))'
    folder.mkdir(parents=True,exist_ok=True)
    (folder/'fieldnode.kicad_sch').write_text(text,encoding='utf-8')
    (folder/'CircuitCheck.kicad_sym').write_text('(kicad_symbol_lib (version 20241209) (generator "circuitcheck-fixture") '+library+')',encoding='utf-8')
    (folder/'sym-lib-table').write_text('(sym_lib_table (lib (name "CircuitCheck") (type "KiCad") (uri "${KIPRJMOD}/CircuitCheck.kicad_sym") (options "") (descr "Original CC0 review fixture")))',encoding='utf-8')

def label(ref,pin,net,x,y):
    return f'(global_label "{net}" (shape input) (at {x:.4f} {y:.4f} {180 if pin%2 else 0}) (effects (font (size 1 1)) (justify {"right" if pin%2 else "left"})) (uuid "{uid("sch-label-"+ref+"-"+str(pin))}"))'

def revision_b(text):
    return text[:-1]+label('R1',1,'GND',50.8,116.84)+')'

if __name__=='__main__':generate(Path(__file__).resolve().parents[1]/'fixtures/fieldnode')
