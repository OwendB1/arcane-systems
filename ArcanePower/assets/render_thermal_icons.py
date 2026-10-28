"""Render inventory icons from the finished thermal mains.

Temporary linked copies preserve the production scenes, geometry and materials.
CLI: blender -b assets/arcane-thermal-models.blend --python this_file [-- subtypes].
Use the separate render process after live inspection; no authoring blend is saved.
"""
import importlib
import json
import runpy
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
COLS = importlib.import_module('space-engineers-utilities.seut_collections')
MODELS = json.loads((ROOT/'validation/thermal-models/models.json').read_text())
CONTRACT = runpy.run_path(str(ROOT/'assets/thermal_model_contract.py'))
PLAYABLE = CONTRACT['PLAYABLE']
MODELS = CONTRACT['runtime_models'](MODELS)
FOLDER = ROOT/'assets/icons/thermal'
SCENE = 'Thermal inventory icon studio'
badge = runpy.run_path(str(ROOT/'assets/icon_badges.py'))['badge']


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


def render(subtype):
    assert Path(bpy.data.filepath).name == 'arcane-thermal-models.blend'
    name = next(name for name, spec in MODELS.items() if spec['subtype'] == subtype)
    source = bpy.data.scenes[MODELS[CONTRACT['COOLER_UPGRADES'].get(name,name)]['subtype']]
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
        if 'mirrored' in name:
            direction = Vector((1.2, 1.7, 1.0))
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
            if name not in CONTRACT['BARE_PIPES']:
                shape=name.split(' / ')[1]
                badge(scene, {'Straight':'I','Elbow':'L','Riser':'UP','Tee':'T','Cross':'+',
                              'Roll adapter':'90','End cap':'CAP','Reactor adapter':'R'}[shape], (.8,.9,1), .24)
            elif 'Roll adapter' in name:
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
    for name, spec in MODELS.items():
        if name not in PLAYABLE:continue
        if not selected or spec['subtype'] in selected:
            print(json.dumps(render(spec['subtype'])), flush=True)
