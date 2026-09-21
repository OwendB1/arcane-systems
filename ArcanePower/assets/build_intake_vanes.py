"""Replace static intake grille bars with 32 radial shutter subparts."""
import ast
import bpy
import bmesh
import importlib
import json
import math
from pathlib import Path
from mathutils import Matrix, Vector

ROOT=Path(__file__).resolve().parents[1]
COLS=importlib.import_module('space-engineers-utilities.seut_collections')
s=bpy.data.scenes['ArcanePower_ReactorPrototype']
col=COLS.get_collections(s)['main'][0]
root=next(o for o in col.objects if o.parent is None)
native={m.name:m for m in bpy.data.materials if m.library}
source=ast.parse((ROOT/'assets/build_deployable_chamber.py').read_text())
exec(compile(ast.Module(body=[n for n in source.body if isinstance(n,ast.FunctionDef)
     and n.name in ('mesh_object','annulus')],type_ignores=[]),'chamber helpers','exec'))
for o in list(col.objects):
    if o.name.startswith(('AP vent / intake louver','subpart_VentVane')):
        bpy.data.objects.remove(o,do_unlink=True)
# Leave headroom for the opening blades under the plenum's back wall.
plenum=s.objects['AP vent / intake plenum']
for v in plenum.data.vertices:
    if v.co.z<2.70:v.co.z=2.70
plenum.data.update()
name='ArcanePower_VentVane'
scene=bpy.data.scenes.get(name) or bpy.data.scenes.new(name)
scene.view_layers[0].name='SEUT'
scene.seut.sceneType='subpart';scene.seut.subtypeId=name
scene.seut.mod_path=str(ROOT/'src');scene.seut.export_sbc_type='none'
cols=COLS.get_collections(scene)
if not cols['seut']:
    wrapper=bpy.data.collections.new('SEUT ('+name+')');scene.collection.children.link(wrapper)
    wrapper.seut.scene=scene;wrapper.seut.col_type='seut';wrapper.seut.version=3
else:wrapper=cols['seut'][0]
if not cols['main']:
    target=bpy.data.collections.new('Main ('+name+')');wrapper.children.link(target)
    target.seut.scene=scene;target.seut.col_type='main';target.seut.version=3
else:target=cols['main'][0]
for o in list(target.objects):bpy.data.objects.remove(o,do_unlink=True)
parent=bpy.data.objects.new(name+' root',None);target.objects.link(parent)
annulus('Intake shutter / blade',1.29,1.735,-.014,.014,native['PaintedMetal_Darker'],target,parent,
        start=-math.pi/32+.005,end=math.pi/32-.005,segments=6)
annulus('Intake shutter / fuel edge',1.70,1.73,-.019,-.014,native['Emissive'],target,parent,
        start=-math.pi/32+.017,end=math.pi/32-.017,segments=6)
for o in target.objects:
    if o.type=='MESH':o.data.transform(Matrix.Translation((-1.5125,0,0)))
inspection=bpy.data.collections.get('AP intake inspection (not exported)')
if not inspection:
    inspection=bpy.data.collections.new('AP intake inspection (not exported)');s.collection.children.link(inspection)
for o in list(inspection.objects):bpy.data.objects.remove(o,do_unlink=True)
for i in range(32):
    a=i*math.tau/32
    rest=Matrix.Rotation(a,4,'Z');rest.translation=(1.5125*math.cos(a),1.5125*math.sin(a),2.49)
    dummy=bpy.data.objects.new('subpart_VentVane%02d'%i,None);col.objects.link(dummy)
    dummy.parent=root;dummy.matrix_basis=rest;dummy['file']=name
    for mesh in target.objects:
        if mesh.type!='MESH':continue
        o=bpy.data.objects.new('Intake inspection / %02d / '%i+mesh.name,mesh.data)
        inspection.objects.link(o);o.matrix_world=rest
manifest=ROOT/'assets/vent.json'
data=json.loads(manifest.read_text())
data['intake']={'count':32,'model':name,'pivot_radius':1.5125,'pivot_z':2.49,'angle_degrees':80,'axis':'subpart local X'}
data['status']='Direct mod-script motion; no exterior exhaust route'
manifest.write_text(json.dumps(data,indent=2))
bpy.context.window.scene=s
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
print('32 intake shutters; one shared MWM, radial hinges, native emissive edges')
