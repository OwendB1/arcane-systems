"""Ceiling vent intake and six nested, separately exportable blast-shield sleeves.

Run on the current engineering model. No timeline animation or regression runs.
"""
import ast
import bpy
import bmesh
import importlib
import json
import math
from pathlib import Path
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
COLS = importlib.import_module('space-engineers-utilities.seut_collections')
s = bpy.data.scenes['ArcanePower_ReactorPrototype']
col = COLS.get_collections(s)['main'][0]
root = next(o for o in col.objects if o.parent is None)
native = {m.name: m for m in bpy.data.materials if m.library}
# Reuse only geometry helpers; do not rerun the existing chamber conversion.
source = ast.parse((ROOT/'assets/build_deployable_chamber.py').read_text())
helpers = ast.Module(body=[n for n in source.body if isinstance(n, ast.FunctionDef)
                          and n.name in ('mesh_object', 'prism', 'box', 'annulus')], type_ignores=[])
exec(compile(helpers, 'build_deployable_chamber.py:helpers', 'exec'))

checkpoint = ROOT/'assets/arcane-power-before-vent.blend'
if not checkpoint.exists():
    bpy.ops.wm.save_as_mainfile(filepath=str(checkpoint), copy=True)
inspection = bpy.data.collections.get('AP vent inspection (not exported)')
if inspection:
    for o in list(inspection.objects): bpy.data.objects.remove(o, do_unlink=True)
else:
    inspection = bpy.data.collections.new('AP vent inspection (not exported)')
    s.collection.children.link(inspection)
for o in list(col.objects):
    if o.name.startswith(('Upper containment bell', 'Upper copper coil', 'AP vent /', 'subpart_BlastShield')):
        bpy.data.objects.remove(o, do_unlink=True)

# Cut a real storage pocket inside the roof, clear of its central conveyor.
# The exterior roof and conveyor aperture keep their existing surfaces.
housing = next(o for o in col.objects if o.name.startswith('Circular upper armored housing'))
if not housing.get('blast_shield_storage_pocket'):
    cutter = annulus('AP vent / temporary storage cutter',1.91,2.65,2.30,3.50,native['Metal_Dull'])
    bpy.context.view_layer.objects.active = housing
    mod = housing.modifiers.new('Telescopic blast shield storage pocket','BOOLEAN')
    mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter,do_unlink=True)
    housing['blast_shield_storage_pocket']=True

# Radial service recesses echo the lower deck plates, now on the bell underside.
annulus('AP vent / bell backing',2.65,4.04,2.56,2.84,native['PaintedMetal_VeryDark'])
annulus('AP vent / outer machined rim',3.98,4.06,2.43,2.62,native['Metal_Dull'])
annulus('AP vent / cassette outer wall',2.615,2.70,2.46,3.47,native['PaintedMetal_Colorable'])
annulus('AP vent / cassette inner wall',1.855,1.905,2.47,3.47,native['Metal_Dull'])
for i in range(24):
    a=i*math.tau/24
    annulus('AP vent / recessed bell plate %02d'%i,2.73,3.96,2.465,2.565,
            native['PaintedMetal_Darker'],start=a+.017,end=a+math.tau/24-.017,segments=5)
    annulus('AP vent / ceiling fuel strip %02d'%i,3.84,3.885,2.451,2.464,
            native['Emissive'],start=a+.038,end=a+math.tau/24-.038,segments=5)
    # Dark recessed slot with three solid vanes, not a flat vent decal.
    annulus('AP vent / bell recess %02d'%i,2.87,3.65,2.455,2.465,
            native['PaintedMetal_VeryDark'],start=a+.085,end=a+.176,segments=3)
    for r in (3.03,3.25,3.47):
        annulus('AP vent / recess vane %02d'%i,r,r+.035,2.442,2.46,
                native['Metal_Dull'],start=a+.089,end=a+.172,segments=3)

# Annular intake lies INSIDE the deployed shield. The central cap protects the
# existing top conveyor; exhaust routing beyond this intake is separate work.
annulus('AP vent / intake plenum',1.22,1.85,2.57,2.81,native['PaintedMetal_VeryDark'])
annulus('AP vent / intake outer lip',1.79,1.855,2.465,2.65,native['Metal_Dull'])
annulus('AP vent / intake inner lip',1.22,1.285,2.465,2.65,native['Metal_Dull'])
annulus('AP vent / intake fuel trace',1.75,1.79,2.455,2.475,native['Emissive'])
disk=[(1.22*math.cos(i*math.tau/96),1.22*math.sin(i*math.tau/96)) for i in range(96)]
prism('AP vent / central service cap',disk,2.49,2.72,native['PaintedMetal_Darker'])
for i in range(32):
    a=i*math.tau/32
    annulus('AP vent / intake louver %02d'%i,1.29,1.735,2.49,2.57,native['Metal_Dull'],
            start=a+.035,end=a+.065,segments=2)

stages=[]
for i in range(6):
    name='BlastShield%d'%(i+1)
    scene_name='ArcanePower_'+name
    scene=bpy.data.scenes.get(scene_name) or bpy.data.scenes.new(scene_name)
    scene.view_layers[0].name='SEUT'
    scene.seut.sceneType='subpart';scene.seut.subtypeId=scene_name
    scene.seut.mod_path=str(ROOT/'src');scene.seut.export_sbc_type='none'
    scene.seut.export_deleteLooseFiles=False
    # Create SEUT collections without switching the foreground Blender scene.
    collections=COLS.get_collections(scene)
    if not collections['seut']:
        wrapper=bpy.data.collections.new('SEUT ('+scene_name+')')
        wrapper.seut.scene=scene;wrapper.seut.col_type='seut';wrapper.seut.version=3
        scene.collection.children.link(wrapper)
    else: wrapper=collections['seut'][0]
    if not collections['main']:
        target=bpy.data.collections.new('Main ('+scene_name+')')
        target.seut.scene=scene;target.seut.col_type='main';target.seut.version=3
        wrapper.children.link(target)
    else: target=collections['main'][0]
    for o in list(target.objects):bpy.data.objects.remove(o,do_unlink=True)
    parent=bpy.data.objects.new(scene_name+' root',None);target.objects.link(parent)
    inner=1.924+.115*(5-i);outer=inner+.055
    park=2.48+.025*i;height=.82;travel=(i+1)*(3.845/6)
    annulus(name+' / armored sleeve',inner,outer,0,height,native['PaintedMetal_Darker'],target,parent)
    annulus(name+' / upper guide flange',outer,inner+.110,height-.035,height,native['Metal_Dull'],target,parent)
    annulus(name+' / lower seal',inner,outer+.018,-.01,.045,native['Metal_Dull'],target,parent)
    for sector in range(16):
        a=sector*math.tau/16
        annulus(name+' / raised panel %02d'%sector,outer,outer+.009,.105,.72,
                native['PaintedMetal_Colorable'],target,parent,start=a+.017,end=a+math.tau/16-.017,segments=6)
        annulus(name+' / fuel seam %02d'%sector,outer+.010,outer+.016,.065,.092,
                native['Emissive'],target,parent,start=a+.035,end=a+math.tau/16-.035,segments=6)
    dummy=bpy.data.objects.new('subpart_'+name,None);col.objects.link(dummy)
    dummy.parent=root;dummy.location=(0,0,park);dummy['file']=scene_name
    for mesh in target.objects:
        if mesh.type!='MESH':continue
        obj=bpy.data.objects.new('Vent inspection / '+mesh.name,mesh.data)
        inspection.objects.link(obj);obj.location=(0,0,park)
        obj['blast_stage']=i;obj['park_z']=park;obj['travel_m']=travel
    stages.append({'name':name,'scene':scene_name,'inner_radius':inner,'outer_radius':outer,
                   'park_z':park,'height':height,'travel_m':travel,'deployed_bottom':park-travel})

def set_vent_pose(deployed=False):
    """Static inspection only; no timeline/keyframes or runtime trigger."""
    for obj in inspection.objects:
        obj.location.z=obj['park_z']-(obj['travel_m'] if deployed else 0)
    s['vent_inspection_pose']='deployed' if deployed else 'stowed'
    bpy.context.view_layer.update()

set_vent_pose(False)
bpy.app.driver_namespace['ap_set_vent_pose']=set_vent_pose
s['blast_shield_design']='6 telescopic sleeves; innermost bore R1.924 outside R1.920 floor fuel trace; native fuel emissives'
manifest={'stages':stages,'floor_trace_outer_radius':1.92,'ceiling_pocket':[1.91,2.65,2.30,3.50],
          'emissive_material':'Emissive','status':'Blender geometry and SEUT subparts; vent trigger and exhaust routing not yet wired'}
(ROOT/'assets/vent.json').write_text(json.dumps(manifest,indent=2))
bpy.context.window.scene=s
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
print(s['blast_shield_design'])
