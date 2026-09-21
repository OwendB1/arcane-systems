"""Inner four-leaf vent closure and lined door pockets joining the roof hatch."""
import ast
import bpy
import bmesh
import importlib
import json
import math
from pathlib import Path
from mathutils import Matrix, Vector
ROOT=Path(__file__).resolve().parents[1]
s=bpy.data.scenes['ArcanePower_ReactorPrototype']
bpy.context.window.scene=s
cols=importlib.import_module('space-engineers-utilities.seut_collections')
col=cols.get_collections(s)['main'][0]
root=next(o for o in col.objects if o.parent is None)
native={m.name:m for m in bpy.data.materials if m.library}
source=ast.parse((ROOT/'assets/build_deployable_chamber.py').read_text())
exec(compile(ast.Module(body=[n for n in source.body if isinstance(n,ast.FunctionDef)
    and n.name in ('mesh_object','prism','annulus')],type_ignores=[]),'chamber helpers','exec'))
backup=ROOT/'assets/arcane-power-before-ceiling-hatch.blend'
if not backup.exists():bpy.ops.wm.save_as_mainfile(filepath=str(backup),copy=True)
if not s.get('ap_ceiling_pocket'):
    cutter=annulus('Ceiling door pocket cutter',1.84,4.05,2.675,2.865,native['Metal_Dull'])
    for o in list(col.objects):
        if o.type=='MESH' and o.name.startswith(('AP vent / cassette outer wall','AP vent / ejection throat')):
            mod=o.modifiers.new('Inner leaf clearance','BOOLEAN')
            mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter
            bpy.context.view_layer.objects.active=o
            bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter,do_unlink=True)
    s['ap_ceiling_pocket']=True
for o in list(col.objects):
    if o.name.startswith('subpart_VentVane') or o.name in ('AP vent / ejection throat','AP vent / throat fuel trace'):
        bpy.data.objects.remove(o,do_unlink=True)
for c in [bpy.data.collections.get('AP intake inspection (not exported)')]:
    if c:
        for o in list(c.objects):bpy.data.objects.remove(o,do_unlink=True)
        bpy.data.collections.remove(c)
for o in list(col.objects):
    if o.name.startswith('AP vent / connected duct /') or o.name.startswith('subpart_CeilingHatch'):
        bpy.data.objects.remove(o,do_unlink=True)
# The central barrel and the enclosed radial door pockets form a continuous
# vent lining. The shield sleeve cassette occupies the annulus inside 2.58m;
# leave that space free so the telescoping sleeves can pass the pocket floor.
for label,ri,ro,z0,z1,material in [
    ('inner seat',1.86,1.915,2.335,2.675,'Metal_Dull'),
    ('inner seat light',1.866,1.906,2.331,2.335,'Emissive'),
    ('inner pocket floor',2.58,4.035,2.655,2.675,'PaintedMetal_VeryDark'),
    ('inner pocket ceiling',2.58,4.035,2.865,2.885,'PaintedMetal_VeryDark'),
    ('inner pocket wall',4.015,4.035,2.675,2.865,'Metal_Dull'),
    ('upper pocket floor',2.58,4.38,3.18,3.20,'PaintedMetal_VeryDark'),
    ('upper pocket ceiling',2.58,4.38,3.52,3.54,'PaintedMetal_VeryDark'),
    ('upper pocket wall',4.36,4.38,3.20,3.52,'Metal_Dull'),
    ('central barrel',1.86,1.91,2.865,3.18,'PaintedMetal_VeryDark'),
    ('barrel band',1.862,1.916,2.96,3.00,'Metal_Dull'),
    ('barrel light',1.858,1.864,3.035,3.075,'Emissive')]:
    annulus('AP vent / connected duct / '+label,ri,ro,z0,z1,native[material])
# Reuse the roof's four-leaf geometry, with a matching underside trim/light so
# it reads correctly from inside the chamber without mirroring the MWM axes.
scene=bpy.data.scenes['ArcanePower_VentHatch']
target=cols.get_collections(scene)['main'][0]
parent=next(o for o in target.objects if o.parent is None)
for o in list(target.objects):
    if o.name.startswith('Vent hatch / underside'):bpy.data.objects.remove(o,do_unlink=True)
for label,ri,ro,material in [('edge',1.79,1.843,'Metal_Dull'),('neon arc',1.69,1.735,'Emissive'),('marking',1.60,1.63,'PaintedMetal_Yellow')]:
    annulus('Vent hatch / underside '+label,ri,ro,-.004,0,native[material],target,parent,start=.10,end=math.pi/2-.10,segments=32)
inspection=bpy.data.collections.get('AP ceiling hatch inspection (not exported)')
if not inspection:
    inspection=bpy.data.collections.new('AP ceiling hatch inspection (not exported)');s.collection.children.link(inspection)
for o in list(inspection.objects):bpy.data.objects.remove(o,do_unlink=True)
slides=[]
for i in range(4):
    angle=math.pi/4+i*math.pi/2
    rest=Matrix.Rotation(angle,4,'Z');rest.translation=(0,0,2.365)
    dummy=bpy.data.objects.new('subpart_CeilingHatch'+str(i+1),None);col.objects.link(dummy)
    dummy.parent=root;dummy.matrix_basis=rest;dummy['file']=scene.name
    slides.append(list(Matrix.Rotation(angle,3,'Z')@Vector((1.40,1.40,0))))
    for mesh in target.objects:
        if mesh.type=='MESH':
            o=bpy.data.objects.new('Ceiling hatch inspection / %d / '%i+mesh.name,mesh.data)
            inspection.objects.link(o);o.matrix_world=rest
# Include newly added underside detailing in the outer hatch inspection too.
outer=bpy.data.collections['AP hatch inspection (not exported)']
for o in list(outer.objects):bpy.data.objects.remove(o,do_unlink=True)
for i in range(4):
    rest=s.objects['subpart_VentHatch'+str(i+1)].matrix_world
    for mesh in target.objects:
        if mesh.type=='MESH':
            o=bpy.data.objects.new('Hatch inspection / %d / '%i+mesh.name,mesh.data)
            outer.objects.link(o);o.matrix_world=rest
p=ROOT/'assets/vent.json';data=json.loads(p.read_text())
data['intake']['count']=0
data['intake']['status']='Superseded by the four CeilingHatch leaves; shared Intake clock retained'
data['ceiling_hatch']={'count':4,'model':scene.name,'park_z':2.365,'lift_m':.32,'slides':slides,'bore_radius_m':1.86}
data['status']='Paired inner/outer four-leaf vent doors with lined connecting barrel and retraction pockets'
p.write_text(json.dumps(data,indent=2)+'\n')
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
print('Inner door: lifts 0.32m then retracts 1.98m between the dispensers; shared roof/ceiling leaf model.')
