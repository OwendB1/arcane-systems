"""Render matched views of the authored build stages (run inside Blender)."""
import importlib
from pathlib import Path
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
COLS = importlib.import_module('space-engineers-utilities.seut_collections')
folder = ROOT/'validation/construction'
folder.mkdir(parents=True, exist_ok=True)
original = bpy.context.window.scene
scene = bpy.data.scenes.new('Construction review')
scene.render.engine = 'CYCLES'
scene.cycles.samples = 24
scene.cycles.use_denoising = True
scene.render.resolution_x = 480
scene.render.resolution_y = 360
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.world = bpy.data.worlds.new('Construction studio')
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.16,.19,.24,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value = .8
camera = bpy.data.objects.new('Review camera',bpy.data.cameras.new('Review camera'))
scene.collection.objects.link(camera)
scene.camera = camera
camera.data.type = 'ORTHO'
for position in ((-8,-10,9),(8,-5,8),(0,8,6)):
    light = bpy.data.lights.new('Review light','AREA')
    light.energy = 2300
    light.size = 10
    obj = bpy.data.objects.new('Review light',light)
    scene.collection.objects.link(obj)
    obj.location = position
    obj.rotation_euler = (-obj.location).to_track_quat('-Z','Y').to_euler()
for name in ('ArcanePower_ReactorPrototype','ArcanePower_ContainmentController',
             'ArcanePower_AdvancedContainmentController','ArcanePower_VentDuct','ArcanePower_VentOutlet'):
    source = bpy.data.scenes[name]
    bpy.context.window.scene = source
    bpy.context.view_layer.update()
    stages = sorted(COLS.get_collections(source)['bs'],key=lambda c:c.seut.type_index)
    points = [o.matrix_world @ v.co for c in stages for o in c.objects if o.type=='MESH' for v in o.data.vertices]
    center = Vector([(min(p[i] for p in points)+max(p[i] for p in points))/2 for i in range(3)])
    camera.location = (5,12,6) if 'Controller' in name else (10,-16,10)
    camera.rotation_euler = (-camera.location).to_track_quat('-Z','Y').to_euler()
    projected = [camera.rotation_euler.to_matrix().transposed() @ (p-center) for p in points]
    camera.data.ortho_scale = 1.2*max(max(p.x for p in projected)-min(p.x for p in projected),
                                    (max(p.y for p in projected)-min(p.y for p in projected))*4/3)
    for collection in stages:
        objects=[]
        for mesh in collection.objects:
            if mesh.type!='MESH':continue
            obj=bpy.data.objects.new('Review mesh',mesh.data)
            scene.collection.objects.link(obj)
            obj.matrix_world=mesh.matrix_world.copy()
            obj.location-=center
            objects.append(obj)
        bpy.context.window.scene=scene
        scene.render.filepath=str(folder/(name+'_BS'+str(collection.seut.type_index)+'.png'))
        bpy.ops.render.render(write_still=True)
        for obj in objects:bpy.data.objects.remove(obj,do_unlink=True)
bpy.context.window.scene=original
for obj in list(scene.objects):bpy.data.objects.remove(obj,do_unlink=True)
bpy.data.scenes.remove(scene)
print('Rendered 15 construction panels')
