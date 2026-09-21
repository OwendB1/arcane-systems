"""Replace the top conveyor skin with a four-leaf, conveyor-connected vent hatch."""
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
COLS=importlib.import_module('space-engineers-utilities.seut_collections')
col=COLS.get_collections(s)['main'][0]
root=next(o for o in col.objects if o.parent is None)
native={m.name:m for m in bpy.data.materials if m.library}
source=ast.parse((ROOT/'assets/build_deployable_chamber.py').read_text())
exec(compile(ast.Module(body=[n for n in source.body if isinstance(n,ast.FunctionDef)
    and n.name in ('mesh_object','prism','annulus')],type_ignores=[]),'chamber helpers','exec'))
backup=ROOT/'assets/arcane-power-before-ejection-hatch.blend'
if not backup.exists():bpy.ops.wm.save_as_mainfile(filepath=str(backup),copy=True)
bpy.context.window.scene=s

if not s.get('ap_ejection_bore'):
    for o in list(col.objects):
        if o.name.startswith('Axial conveyor / top /') or o.name in (
                'AP vent / intake plenum','AP vent / intake inner lip',
                'AP vent / central service cap','AP vent / intake outer lip','AP vent / intake fuel trace',
                'AP vent / cassette inner wall'):
            bpy.data.objects.remove(o,do_unlink=True)
    def cut(obj,cutter):
        mod=obj.modifiers.new('Ejection clearance','BOOLEAN')
        mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter
        bpy.context.view_layer.objects.active=obj
        bpy.ops.object.modifier_apply(modifier=mod.name)
    outline=[(1.86*math.cos(i*math.tau/128),1.86*math.sin(i*math.tau/128)) for i in range(128)]
    bore=prism('Ejection bore cutter',outline,2.28,3.80,native['Metal_Dull'])
    for o in list(col.objects):
        if o.type!='MESH' or o==bore:continue
        points=[o.matrix_world@Vector(v) for v in o.bound_box]
        if (max(v.z for v in points)>2.28 and min(v.z for v in points)<3.8
                and min(v.x for v in points)<1.86 and max(v.x for v in points)>-1.86
                and min(v.y for v in points)<1.86 and max(v.y for v in points)>-1.86):
            cut(o,bore)
            if not o.data.polygons:bpy.data.objects.remove(o,do_unlink=True)
    bpy.data.objects.remove(bore,do_unlink=True)
    # The leaves first lower, then slide beneath the roof skin. This pocket
    # overlaps the shield cassette only after the shield has deployed below it.
    pocket=annulus('Hatch pocket cutter',1.84,4.35,3.20,3.52,native['Metal_Dull'])
    for o in list(col.objects):
        if o.type=='MESH' and o.name.startswith(('Circular upper armored housing','Cap central service hatch','Cap removable sector','Cap hatch rim','AP vent / cassette outer wall')):
            cut(o,pocket)
    bpy.data.objects.remove(pocket,do_unlink=True)
    annulus('AP vent / ejection throat',1.86,1.91,2.46,3.18,native['PaintedMetal_VeryDark'])
    annulus('AP vent / throat fuel trace',1.865,1.905,2.455,2.475,native['Emissive'])
    annulus('AP vent / hatch seat',1.86,2.04,3.53,3.745,native['Metal_Dull'])
    s['ap_ejection_bore']=True

name='ArcanePower_VentHatch'
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
outline=[(.006,.006)]+[(1.845*math.cos(a),1.845*math.sin(a))
    for a in [.004+(math.pi/2-.008)*i/32 for i in range(33)]]
prism('Vent hatch / armored leaf',outline,0,.16,native['PaintedMetal_Darker'],target,parent)
annulus('Vent hatch / machined edge',1.79,1.843,.16,.165,native['Metal_Dull'],target,parent,start=.025,end=math.pi/2-.025,segments=32)
annulus('Vent hatch / neon arc',1.69,1.735,.16,.164,native['Emissive'],target,parent,start=.10,end=math.pi/2-.10,segments=32)
annulus('Vent hatch / conveyor marking',1.60,1.63,.16,.163,native['PaintedMetal_Yellow'],target,parent,start=.16,end=math.pi/2-.16,segments=32)
inspection=bpy.data.collections.get('AP hatch inspection (not exported)')
if not inspection:
    inspection=bpy.data.collections.new('AP hatch inspection (not exported)');s.collection.children.link(inspection)
for o in list(inspection.objects):bpy.data.objects.remove(o,do_unlink=True)
slides=[];dummies=[]
for i in range(4):
    dummy_name='subpart_VentHatch'+str(i+1)
    old=s.objects.get(dummy_name)
    if old:bpy.data.objects.remove(old,do_unlink=True)
    rest=Matrix.Rotation(i*math.pi/2,4,'Z');rest.translation=(0,0,3.58)
    dummy=bpy.data.objects.new(dummy_name,None);col.objects.link(dummy)
    dummy.parent=root;dummy.matrix_basis=rest;dummy['file']=name;dummies.append(dummy)
    direction=Matrix.Rotation(i*math.pi/2,3,'Z')@Vector((1.95,1.95,0));slides.append(list(direction))
    for mesh in target.objects:
        if mesh.type=='MESH':
            o=bpy.data.objects.new('Hatch inspection / %d / '%i+mesh.name,mesh.data)
            inspection.objects.link(o);o.matrix_world=rest
detector=s.objects['detector_conveyor_top']
detector['highlight']=';'.join(d.name for d in dummies)
detector['purpose']='Grid-centred conveyor connection through the custom vent hatch'
detector.seut.highlight_objects.clear()
for d in dummies:detector.seut.highlight_objects.add().obj=d
data=json.loads((ROOT/'assets/vent.json').read_text())
data['intake']['radial_slide_m']=.60
data['hatch']={'count':4,'model':name,'bore_radius_m':1.86,'park_z':3.58,'drop_m':.30,'slides':slides}
data['status']='Direct top ejection hatch; centred conveyor connection retained'
(ROOT/'assets/vent.json').write_text(json.dumps(data,indent=2)+'\n')
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
print('Four retracting vent leaves; 3.72m clear bore; top conveyor dummy retained')
