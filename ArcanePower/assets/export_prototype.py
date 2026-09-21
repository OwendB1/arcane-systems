"""Convert the reviewed v03 geometry into SEUT reactor/subpart export scenes.

Run through Blender MCP with v03 open. Prototype-only collision and tiled housing UVs.
"""
import bpy
import importlib
import math
from pathlib import Path
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT/'src'
MOD.mkdir(parents=True, exist_ok=True)
COLLECTIONS = importlib.import_module('space-engineers-utilities.seut_collections')
SOURCE = bpy.data.scenes['08 Rounded reactor detail']
SOURCE.frame_set(1)
bpy.context.window.scene = SOURCE
bpy.context.view_layer.update()
source_root = next(o for o in SOURCE.objects if o.name.startswith('V03 / rounded reactor'))
axes = sorted((o for o in SOURCE.objects if 'ring_index' in o), key=lambda o:o['ring_index'])
ring_objects = set(o for a in axes for o in a.children_recursive)
native = {m.name:m for m in bpy.data.materials if m.library and m.library.filepath.endswith('Materials.blend')}
mapping = {'Hull':'PaintedMetal_Colorable', 'Panel':'PaintedMetal_Darker', 'Dark':'PaintedMetal_VeryDark',
           'Edge':'Metal_Dull', 'Copper':'Metal_Shiny', 'Yellow':'PaintedMetal_Yellow',
           'Cyan':'Emissive', 'Amber':'Emissive', 'FieldTile':'Emissive', 'White':'PaintedMetal_Clean'}


def new_scene(name, subpart=False):
    assert name not in bpy.data.scenes, 'Save edits before rebuilding export scenes'
    s = bpy.data.scenes.new(name)
    bpy.context.window.scene = s
    s.unit_settings.system = 'METRIC'
    bpy.ops.scene.recreate_collections()
    s.seut.subtypeId = name
    s.seut.mod_path = str(MOD)
    s.seut.export_sbc_type = 'none'
    s.seut.export_deleteLooseFiles = False
    s.seut.bBox_X = s.seut.bBox_Y = s.seut.bBox_Z = 5
    if subpart:
        s.seut.sceneType = 'subpart'
    cols = COLLECTIONS.get_collections(s)
    r = bpy.data.objects.new(name+' root', None)
    cols['main'][0].objects.link(r)
    return s, cols, r


def copy_mesh(o, col, parent, offset):
    evaluated = o.evaluated_get(SOURCE.view_layers[0].depsgraph)
    mesh = bpy.data.meshes.new_from_object(evaluated, depsgraph=SOURCE.view_layers[0].depsgraph)
    mesh.transform(Matrix.Translation(-Vector(offset)) @ o.matrix_world)
    for i, m in enumerate(mesh.materials):
        if m and m.name.startswith('AP / '):
            key = m.name[5:].split('.')[0]
            mesh.materials[i] = native[mapping.get(key, 'PaintedMetal_Colorable')]
        elif m:
            mesh.materials[i] = native.get(m.name.split('.')[0], m)
    if not mesh.uv_layers:
        uv = mesh.uv_layers.new(name='UVMap')
        for poly in mesh.polygons:
            axis = max(range(3), key=lambda i: abs(poly.normal[i]))
            u, v = [i for i in range(3) if i != axis]
            for loop in poly.loop_indices:
                p = mesh.vertices[mesh.loops[loop].vertex_index].co
                uv.data[loop].uv = (p[u]/2.5, p[v]/2.5)
    c = bpy.data.objects.new(o.name, mesh)
    col.objects.link(c)
    c.parent = parent
    return c


def collider(cols, pos, size, angle=0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(pos[0], pos[1], pos[2]-6.25))
    o = bpy.context.object
    o.name = 'Collision / housing'
    o.scale = size
    o.rotation_euler.z = angle
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    for c in list(o.users_collection):
        c.objects.unlink(o)
    cols['hkt'][0].objects.link(o)


main, cols, root = new_scene('ArcanePower_ReactorPrototype')
for o in source_root.children_recursive:
    if o.type != 'MESH' or o in ring_objects or 'batch' in o or o.name.startswith('V03 / Ignition'):
        continue
    if any(p.name.startswith('Scale reference') for p in [o.parent, o.parent.parent if o.parent else None] if p):
        continue
    copy_mesh(o, cols['main'][0], root, (0,0,6.25))
# Segmented compound collision preserves the open chamber; no solid cube around it.
collider(cols, (0,0,.22), (7.5,7.5,.44))
for i in range(24):
    a = i*math.tau/24
    collider(cols, (4.25*math.cos(a),4.25*math.sin(a),1.40), (2.0,1.15,2.10), a)
for i in range(4):
    a = math.pi/4+i*math.pi/2
    collider(cols, (4.2*math.cos(a),4.2*math.sin(a),6.0), (.90,.90,6.4), a)
for i in range(12):
    a = i*math.tau/12
    collider(cols, (2.4*math.cos(a),2.4*math.sin(a),9.85), (3.8,1.25,.85), a)
for x,y in [(0,-5.15),(0,5.15),(-5.15,0),(5.15,0)]:
    collider(cols, (x,y,1.25), (2.48,2.48,2.48))
for i,(x,y) in enumerate([(0,-6.15),(0,6.15),(-6.15,0),(6.15,0)]):
    d = bpy.data.objects.new('detector_conveyor_'+str(i),None)
    cols['main'][0].objects.link(d)
    d.parent=root
    d.location=(x,y,-5.0)
    d.scale=(.6,.6,.6)
inventory = bpy.data.objects.new('detector_terminal',None)
cols['main'][0].objects.link(inventory)
inventory.parent=root
inventory.location=(0,-6.2,-5.0)
inventory.scale=(.7,.1,.7)
scenes = []
for i,a in enumerate(axes):
    s, sc, sr = new_scene('ArcanePower_Ring'+str(i+1), True)
    for o in a.children_recursive:
        if o.type=='MESH':
            copy_mesh(o, sc['main'][0], sr, a.location)
    bpy.context.window.scene=main
    d=bpy.data.objects.new('subpart_Ring'+str(i+1),None)
    cols['main'][0].objects.link(d)
    d.parent=root
    d.location=a.location-Vector((0,0,6.25))
    d['file']=s.seut.subtypeId
    scenes.append(s)
bpy.context.window.scene=main
path=ROOT/'assets'/'arcane-power-prototype.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(path))
bpy.app.driver_namespace['ap_export_scenes'] = scenes+[main]
print('Ready to export:',[s.name for s in scenes+[main]])
