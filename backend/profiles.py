"""Versioned fabrication constraints, enforced by a second native DRC pass.

Preset codes are CircuitCheck identifiers, never manufacturer order lookups.
Numeric imports are data only. Existing project rules are retained unchanged.
"""
import json
import re
import shutil
from .geometry import signature

PRESETS=[{
 'code':'PCBWAY-STANDARD-BASELINE','name':'PCBWay standard published baseline','version':'2026-10-24',
 'manufacturer':'PCBWay','source':'https://www.pcbway.com/capabilities.html','retrieved':'2026-10-24',
 'constraints':{'track_width':0.1,'clearance':0.1,'hole_size':0.15},
 'scope':'Published minimum trace/spacing and CNC drill baseline. Confirm copper weight, stackup, process and order-specific limits with the manufacturer. This subset is not fabrication approval.'
}]
ALLOWED={'track_width','clearance','hole_size','annular_width','edge_clearance'}

def validate_profile(raw):
    if not isinstance(raw,dict):raise ValueError('Rule profile must be a JSON object')
    if set(raw)-{'code','name','version','manufacturer','source','retrieved','constraints','scope','order_reference'}:raise ValueError('Unknown rule-profile fields')
    profile={}
    for field in ('code','name','version','manufacturer','source','retrieved','scope','order_reference'):
        value=raw.get(field,'')
        if not isinstance(value,str) or len(value)>1200:raise ValueError('Invalid rule-profile '+field)
        profile[field]=value
    profile['code']=profile['code'] or 'CUSTOM'
    profile['name']=profile['name'] or 'Custom fabrication rules'
    limits=raw.get('constraints',{})
    if not isinstance(limits,dict) or set(limits)-ALLOWED:raise ValueError('Unsupported constraint. Use track_width, clearance, hole_size, annular_width or edge_clearance in mm.')
    for key,value in limits.items():
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not (0<value<=20):raise ValueError('Constraint values must be finite numbers greater than 0 and at most 20 mm')
    profile['constraints']=limits
    profile['fingerprint']=signature(profile)
    return profile

def prepare_profile(source, destination, root, profile):
    shutil.copytree(source,destination)
    target=destination/(root+'.kicad_dru'); target.parent.mkdir(parents=True,exist_ok=True)
    # This is an independent fabrication pass. Retaining stricter project rules
    # here can mask a weaker vendor violation in KiCad's single chosen rule.
    # Original project rules are checked separately and are never rewritten.
    existing='(version 1)\n'
    settings_path=destination/(root+'.kicad_pro')
    settings=json.loads(settings_path.read_text(encoding='utf-8-sig')) if settings_path.exists() else {}
    design=settings.setdefault('board',{}).setdefault('design_settings',{})
    globals=design.setdefault('rules',{});severities=design.setdefault('rule_severities',{})
    mapping={'track_width':('min_track_width','track_width'),'clearance':('min_clearance','clearance'),
             'hole_size':('min_through_hole_diameter','drill_out_of_range'),'annular_width':('min_via_annular_width','annular_width'),
             'edge_clearance':('min_copper_edge_clearance','copper_edge_clearance')}
    for constraint in profile['constraints']:
        floor,rule=mapping[constraint];globals[floor]=0;severities[rule]='error'
    if 'hole_size' in profile['constraints']:
        for key in ('min_microvia_drill','min_via_drill'):
            if key in globals:globals[key]=0
    if 'drc_exclusions' in design:design['drc_exclusions']=[]
    settings_path.write_text(json.dumps(settings,indent=2),encoding='utf-8')
    # Only fixed constraint names and validated numeric literals enter the grammar.
    rules='\n'.join(f'(rule "CircuitCheck fabrication {key}" (severity error) (constraint {key} (min {value:.8g}mm)))' for key,value in sorted(profile['constraints'].items()))
    target.write_text(existing+'\n'+rules+'\n',encoding='utf-8')
    return destination/(root+'.kicad_pcb')
