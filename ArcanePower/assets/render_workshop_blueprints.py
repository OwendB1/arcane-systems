"""Render authored SEUT models as schematic plates (never saves either .blend).

blender -b ArcanePower/assets/arcane-energy-core.blend --python ArcanePower/assets/render_workshop_blueprints.py
Then: python3 ArcanePower/tools/compose_workshop_blueprints.py
"""
import bpy, bmesh, importlib, math, sys
from pathlib import Path
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.cache/workshop-blueprints'
OUT.mkdir(parents=True, exist_ok=True)
COLS = importlib.import_module('space-engineers-utilities.seut_collections')
with bpy.data.libraries.load(str(ROOT / 'assets/arcane-power-prototype.blend'), link=False) as (source, target):
    target.scenes = [name for name in source.scenes if name.startswith('ArcanePower_') and name not in bpy.data.scenes]
scene = bpy.data.scenes.new('Workshop blueprint render')
bpy.context.window.scene = scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 24
scene.cycles.use_denoising = True
scene.render.resolution_x = scene.render.resolution_y = 1000
scene.render.resolution_percentage = 100
scene.render.film_transparent = True
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.view_settings.view_transform = 'Standard'
scene.world = bpy.data.worlds.new('Blueprint world')
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.08, .18, .25, 1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value = .6

body = bpy.data.materials.new('Blueprint surface')
body.diffuse_color = (.018, .075, .115, 1)
body.use_nodes = True
body.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (.018, .075, .115, 1)
body.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = .85
edge = bpy.data.materials.new('Blueprint ink')
edge.use_nodes = True
nodes = edge.node_tree.nodes
nodes.clear()
e = nodes.new('ShaderNodeEmission')
e.inputs[0].default_value = (.26, .76, 1, 1)
e.inputs[1].default_value = 1.5
output = nodes.new('ShaderNodeOutputMaterial')
edge.node_tree.links.new(e.outputs[0], output.inputs['Surface'])
cam = bpy.data.objects.new('Blueprint camera', bpy.data.cameras.new('Blueprint camera'))
scene.collection.objects.link(cam)
cam.data.type = 'ORTHO'
scene.camera = cam
for position in ((-10, -14, 18), (10, 5, 12)):
    light = bpy.data.lights.new('Blueprint softbox', 'AREA')
    light.energy, light.size = 2500, 10
    obj = bpy.data.objects.new(light.name, light)
    scene.collection.objects.link(obj)
    obj.location = position
    obj.rotation_euler = (-obj.location).to_track_quat('-Z', 'Y').to_euler()


def geometry(source, transform=Matrix.Identity(4), reactor=False):
    bpy.context.window.scene = source
    bpy.context.view_layer.update()
    for obj in COLS.get_collections(source)['main'][0].objects:
        pose = transform @ obj.matrix_world
        if obj.type == 'MESH':
            # The cutaway removes glazing, exposing the authored interior.
            if obj.name.startswith('Curved chamber / pane') or any(m and ('glass' in m.name.lower()) for m in obj.data.materials):
                continue
            yield obj, pose
        elif obj.name.startswith('subpart_') and obj.get('file') in bpy.data.scenes:
            if reactor and any(name in obj.name for name in ('Tile', 'Plasma', 'BlastShield')):
                continue
            if reactor and obj.name.startswith('subpart_Ring'):
                index = int(obj.name[-1])
                ring = list(geometry(bpy.data.scenes[obj['file']]))
                points = [p @ v.co for mesh, p in ring for v in mesh.data.vertices]
                center = Vector([(min(p[i] for p in points)+max(p[i] for p in points))/2 for i in range(3)])
                deployed = Matrix.Translation((0, 0, .25)) @ Matrix.Rotation(math.radians(25 * index), 4, 'X') @ Matrix.Translation(-center)
                for mesh, local in ring: yield mesh, deployed @ local
                continue
            yield from geometry(bpy.data.scenes[obj['file']], pose)


jobs = [
    ('reactor', 'ArcanePower_ReactorPrototype', (9, -18, 5)),
    ('controller', 'ArcanePower_ContainmentController', (5, 12, 6)),
    ('advanced-controller', 'ArcanePower_AdvancedContainmentController', (5, 12, 6)),
    ('duct', 'ArcanePower_VentDuct', (8, -12, 10)),
    ('outlet', 'ArcanePower_VentOutlet', (8, -12, 10)),
    ('energy-core', 'ArcanePower_EnergyCore', (10, 16, 9)),
    ('capacity', 'ArcanePower_EnergyCapacityAdvanced', (4, -7, 4)),
    ('transfer', 'ArcanePower_EnergyTransferAdvanced', (4, -7, 4)),
    ('stabilizer', 'ArcanePower_EnergyStabilizerAdvanced', (4, -7, 4)),
]
for label, name, direction in jobs:
    if '--' in sys.argv and label not in sys.argv[sys.argv.index('--')+1:]: continue
    objects = []
    parts = list(geometry(bpy.data.scenes[name], reactor=label == 'reactor'))
    bpy.context.window.scene = scene
    points = [pose @ v.co for original, pose in parts for v in original.data.vertices]
    center = Vector([(min(p[i] for p in points) + max(p[i] for p in points)) / 2 for i in range(3)])
    span = max(max(p[i] for p in points) - min(p[i] for p in points) for i in range(3))
    lines = bpy.data.curves.new('Crease outlines', 'CURVE')
    lines.dimensions = '3D'
    lines.resolution_u = 1
    lines.bevel_depth = span * .00055
    lines.bevel_resolution = 0
    lines.materials.append(edge)
    for original, pose in parts:
        mesh = original.data.copy()
        mesh.materials.clear()
        mesh.materials.append(body)
        for polygon in mesh.polygons: polygon.material_index = 0
        copy = bpy.data.objects.new(original.name + ' schematic', mesh)
        scene.collection.objects.link(copy)
        copy.matrix_world = pose
        copy.location -= center
        objects.append(copy)
        bm = bmesh.new()
        bm.from_mesh(mesh)
        for line in bm.edges:
            if not line.is_boundary and line.calc_face_angle(0) < math.radians(35): continue
            spline = lines.splines.new('POLY')
            spline.points.add(1)
            for point, vertex in zip(spline.points, line.verts):
                point.co = (*(pose @ vertex.co - center), 1)
        bm.free()
    wire = bpy.data.objects.new('Technical outlines', lines)
    scene.collection.objects.link(wire)
    objects.append(wire)
    cam.location = Vector(direction).normalized() * span * 3
    cam.rotation_euler = (-cam.location).to_track_quat('-Z', 'Y').to_euler()
    view = cam.rotation_euler.to_matrix().transposed()
    projected = [view @ (p - center) for p in points]
    cam.data.ortho_scale = 1.12 * max(max(p[i] for p in projected) - min(p[i] for p in projected) for i in (0, 1))
    scene.render.filepath = str(OUT / (label + '.png'))
    bpy.ops.render.render(write_still=True)
    print('BLUEPRINT_RENDER', label, flush=True)
    for obj in objects:
        data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if data.users == 0:
            if isinstance(data, bpy.types.Mesh): bpy.data.meshes.remove(data)
            elif isinstance(data, bpy.types.Curve): bpy.data.curves.remove(data)
