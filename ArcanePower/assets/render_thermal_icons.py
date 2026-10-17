"""Render inventory icons from the finished thermal mains.

Temporary linked copies preserve the production scenes, geometry and materials.
CLI: blender -b assets/arcane-thermal-models.blend --python this_file [-- subtypes].
Use the separate render process after live inspection; no authoring blend is saved.
"""
import importlib
import json
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
COLS = importlib.import_module('space-engineers-utilities.seut_collections')
MODELS = json.loads((ROOT/'validation/thermal-models/models.json').read_text())
FOLDER = ROOT/'assets/icons/thermal'
SCENE = 'Thermal inventory icon studio'


def studio():
    scene = bpy.data.scenes.get(SCENE)
    if scene is not None:
        return scene
    scene = bpy.data.scenes.new(SCENE)
    scene['review_only'] = True
    scene.render.engine = 'BLENDER_EEVEE'
    scene.view_layers[0].name = 'SEUT'
    scene.view_layers[0]['Paint Color'] = (.55, .55, .55)
    scene.view_layers[0]['UV Grid Overlay'] = 0.0
    scene.render.resolution_x = scene.render.resolution_y = 512
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.exposure = -.65
    scene.world = bpy.data.worlds.new(SCENE)
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes['Background']
    background.inputs['Color'].default_value = (.22, .25, .30, 1)
    background.inputs['Strength'].default_value = .8
    camera = bpy.data.objects.new(SCENE, bpy.data.cameras.new(SCENE))
    scene.collection.objects.link(camera)
    camera.data.type = 'ORTHO'
    scene.camera = camera
    return scene


def emission(name, color):
    material = bpy.data.materials.get(name)
    if material is None:
        material = bpy.data.materials.new(name)
        material.use_nodes = True
        nodes = material.node_tree.nodes
        nodes.clear()
        shader = nodes.new('ShaderNodeEmission')
        shader.inputs['Color'].default_value = (*color, 1)
        material.node_tree.links.new(shader.outputs[0], nodes.new('ShaderNodeOutputMaterial').inputs['Surface'])
    return material


def badge(scene, text, color, x):
    scale = scene.camera.data.ortho_scale
    mesh = bpy.data.meshes.new('Icon badge')
    mesh.from_pydata([(x, -.46, 0), (x+.22, -.46, 0), (x+.22, -.33, 0), (x, -.33, 0)], [], [(0, 1, 2, 3)])
    obj = bpy.data.objects.new('Icon badge', mesh)
    scene.collection.objects.link(obj)
    obj.parent = scene.camera
    obj.location.z = -2
    obj.scale = (scale, scale, scale)
    obj.data.materials.append(emission('Icon badge dark', (.012, .020, .030)))
    font = bpy.data.curves.new('Icon legend', 'FONT')
    font.body = text
    font.align_x = 'CENTER'
    font.align_y = 'CENTER'
    font.size = .09*scale
    font.space_character = 1.1
    label = bpy.data.objects.new('Icon legend', font)
    scene.collection.objects.link(label)
    label.parent = scene.camera
    label.location = ((x+.11)*scale, -.395*scale, -1.99)
    font.materials.append(emission('Icon legend '+text, color))
    for item in (obj, label):
        item.visible_shadow = False
        item.visible_diffuse = False
        item.visible_glossy = False
        item.visible_transmission = False


def render(subtype):
    assert Path(bpy.data.filepath).name == 'arcane-thermal-models.blend'
    name = next(name for name, spec in MODELS.items() if spec['subtype'] == subtype)
    source = bpy.data.scenes[subtype]
    scene = studio()
    previous = bpy.context.window.scene
    meshes = []
    try:
        bpy.context.window.scene = source
        bpy.context.view_layer.update()
        for mesh in COLS.get_collections(source)['main'][0].objects:
            if mesh.type != 'MESH' or mesh.hide_render:
                continue
            obj = mesh.copy()
            obj.parent = None
            obj.animation_data_clear()
            scene.collection.objects.link(obj)
            obj.matrix_world = mesh.matrix_world.copy()
            obj.hide_render = False
            meshes.append(obj)
        assert meshes, subtype
        bpy.context.window.scene = scene
        bpy.context.view_layer.update()
        corners = [obj.matrix_world@Vector(point) for obj in meshes for point in obj.bound_box]
        centre = Vector([(min(p[i] for p in corners)+max(p[i] for p in corners))/2 for i in range(3)])
        span = max(max(p[i] for p in corners)-min(p[i] for p in corners) for i in range(3))
        for obj in meshes:
            obj.location -= centre
        direction = Vector((-1.2, -1.7, 1.1) if ' / ' in name else (1.2, -1.7, 1.0))
        if name == 'Reactor housing':
            direction = Vector((.6, -2, .65))
        scene.camera.location = direction.normalized()*span*3
        scene.camera.rotation_euler = (-scene.camera.location).to_track_quat('-Z', 'Y').to_euler()
        projected = [scene.camera.rotation_euler.to_matrix().transposed()@(p-centre) for p in corners]
        scene.camera.data.ortho_scale = 1.20*max(max(p[i] for p in projected)-min(p[i] for p in projected) for i in (0, 1))
        for position, power in [((-1, -1.3, 1.4), 40), ((1, -.8, .5), 25), ((.4, 1, 1), 45)]:
            light = bpy.data.lights.new('Icon softbox', 'AREA')
            light.energy = power*span*span
            light.size = span
            obj = bpy.data.objects.new('Icon softbox', light)
            scene.collection.objects.link(obj)
            obj.location = Vector(position)*span
            obj.rotation_euler = (-obj.location).to_track_quat('-Z', 'Y').to_euler()
        if ' / ' in name:
            circuit = name.split(' / ')[0]
            label, color = {'PRIMARY': ('P', (.08, .8, .6)), 'CO2_HP': ('HP', (1, .5, .08)), 'CO2_LP': ('LP', (.1, .65, 1))}[circuit]
            badge(scene, label, color, -.46)
            if 'Roll adapter' in name:
                badge(scene, '90', (.8, .9, 1), .24)
            elif 'reactor adapter' in name.lower():
                badge(scene, 'R', (.8, .9, 1), .24)
        if name.endswith('upgraded'):
            badge(scene, 'II', (1, .7, .14), .24)
        FOLDER.mkdir(parents=True, exist_ok=True)
        scene.render.filepath = str(FOLDER/(subtype+'.png'))
        bpy.ops.render.render(write_still=True)
        return {'subtype': subtype, 'icon': scene.render.filepath, 'meshes': len(meshes)}
    finally:
        bpy.context.window.scene = previous
        for obj in list(scene.objects):
            if obj == scene.camera:
                continue
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.context.view_layer.update()


if __name__ == '__main__':
    import sys
    selected = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    for spec in MODELS.values():
        if not selected or spec['subtype'] in selected:
            print(json.dumps(render(spec['subtype'])), flush=True)
