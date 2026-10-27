"""Render current authored meshes as cyan blueprint studies; never save source blends.

Run with blender -b --factory-startup --python this_file.py, then optional labels after --.
The functions can also prepare a temporary review in the live Blender window.
"""
import bmesh
import bpy
import json
import math
from pathlib import Path
import runpy
import sys
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.cache/workshop-blueprints'
CONTRACT = runpy.run_path(str(ROOT / 'assets/thermal_model_contract.py'))
RINGS = json.loads((ROOT / 'assets/deployment.json').read_text())['rings']

# Labels are shared with the plate compositor. Variants with identical geometry
# use one drawing plus their two ratings instead of duplicating the same mesh.
JOBS = [
    ('reactor', 'ArcanePower_Thermal_ReactorHousing', (9, -18, 5)),
    ('controller', 'ArcanePower_ContainmentController', (5, 12, 6)),
    ('advanced-controller', 'ArcanePower_AdvancedContainmentController', (5, 12, 6)),
    ('duct', 'ArcanePower_VentDuct', (8, -12, 10)),
    ('outlet', 'ArcanePower_VentOutlet', (8, -12, 10)),
    ('energy-core', 'ArcanePower_EnergyCore', (-10, -16, 9)),
    ('energy-bank', 'ArcanePower_EnergyCore', (-10, -16, 10)),
    ('energy-full', 'ArcanePower_EnergyCore', (-10, -16, 9)),
]
for label, subtype in [('capacity', 'Capacity'), ('transfer', 'Transfer'), ('stabilizer', 'Stabilizer')]:
    JOBS += [(label, 'ArcanePower_Energy'+subtype+'Advanced', (-4, 7, 4)),
             (label+'-standard', 'ArcanePower_Energy'+subtype, (-4, 7, 4))]
for label, name in [('turbine', 'Brayton train'), ('turbine-upgraded', 'Brayton train upgraded'),
                    ('turbine-mirrored', 'Brayton train mirrored'),
                    ('turbine-mirrored-upgraded', 'Brayton train mirrored upgraded'),
                    ('air-cooler', 'Atmospheric cooler'), ('air-cooler-rear', 'Atmospheric cooler'),
                    ('space-radiator', 'Space radiator'), ('radiator-stack', 'Space radiator'),
                    ('radiator-panel', 'Radiator panel')]:
    direction = (10, -17, 8) if name.startswith('Brayton') else (10, -14, 9)
    if label == 'air-cooler-rear': direction = (-10, 14, 7)
    JOBS.append((label, CONTRACT['subtype'](name), direction))
for shape in [*CONTRACT['PIPE_PORTS'], 'Reactor adapter']:
    for bare in (False, True):
        name = 'PRIMARY / '+shape+(' bare' if bare else '')
        label = 'pipe-'+shape.lower().replace(' ', '-')+('-bare' if bare else '')
        JOBS.append((label, CONTRACT['subtype'](name), (-8, -12, 8)))


def setup(labels=None):
    """Load the maintained scenes, leaving source data and saved files untouched."""
    global sources, scene, body, edge, cam
    OUT.mkdir(parents=True, exist_ok=True)
    sources = {s.name: s for s in bpy.data.scenes}
    active = [job for job in JOBS if not labels or job[0] in labels]
    thermal_names = {job[1] for job in active if job[1].startswith('ArcanePower_Thermal_')}
    if any(job[0] == 'radiator-stack' for job in active):
        thermal_names.add(CONTRACT['subtype']('Radiator panel'))
    hardware_names = {job[1] for job in active if job in JOBS[1:5]}
    energy = any(job[1].startswith('ArcanePower_Energy') for job in active)
    common = set()
    if any(job[0] == 'reactor' for job in active):
        common.update({'ArcanePower_Ring1', 'ArcanePower_Ring2', 'ArcanePower_Ring3',
                       'ArcanePower_Ring4', 'ArcanePower_FloorLeaf', 'ArcanePower_VentHatch'})
    groups = [('arcane-energy-core.blend', lambda n: energy and (n.startswith('ArcanePower_Energy') or n in {'ArcanePower_Ring3', 'ArcanePower_Ring4'})),
              ('arcane-thermal-models.blend', lambda n: n in thermal_names | common),
              ('arcane-power-prototype.blend', lambda n: n in hardware_names)]
    for filename, wanted in groups:
        if filename == Path(bpy.data.filepath).name: continue
        print('BLUEPRINT_LOAD', filename, flush=True)
        with bpy.data.libraries.load(str(ROOT/'assets'/filename), link=False) as (available, loaded):
            names = [name for name in available.scenes if wanted(name)]
            loaded.scenes = list(names)
        sources.update(zip(names, loaded.scenes))
        print('BLUEPRINT_LOADED', filename, len(names), flush=True)
    assert all(name in sources for _, name, _ in active), 'Missing authored model scene'
    scene = bpy.data.scenes.new('Workshop blueprint render')
    scene['workshop_review_only'] = True
    bpy.context.window.scene = scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 3
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'OPTIX'
    prefs.get_devices()
    if any(d.type == 'OPTIX' for d in prefs.devices):
        for device in prefs.devices: device.use = device.type == 'OPTIX'
        scene.cycles.device = 'GPU'
    scene.render.resolution_x = scene.render.resolution_y = 1200
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
    body.use_nodes = True
    body.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (.018, .075, .115, 1)
    body.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = .85
    edge = bpy.data.materials.new('Blueprint ink')
    edge.use_nodes = True
    edge.node_tree.nodes.clear()
    emission = edge.node_tree.nodes.new('ShaderNodeEmission')
    emission.inputs[0].default_value = (.26, .76, 1, 1)
    emission.inputs[1].default_value = 1.5
    output = edge.node_tree.nodes.new('ShaderNodeOutputMaterial')
    edge.node_tree.links.new(emission.outputs[0], output.inputs['Surface'])
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


def main_collection(source):
    # Read the saved SEUT collection hierarchy without loading editor callbacks.
    # Factory-startup background renders need geometry, not the export add-on.
    pending = [source.collection]
    while pending:
        collection = pending.pop()
        if collection.name.startswith('Main ('):
            return collection
        pending.extend(collection.children)
    raise ValueError('Missing authored Main collection: '+source.name)


def geometry(source, transform=Matrix.Identity(4), reactor=False, cutaway=False):
    bpy.context.window.scene = source
    bpy.context.view_layer.update()
    entries = [(obj, obj.matrix_world.copy()) for obj in main_collection(source).objects]
    for obj, local in entries:
        pose = transform @ local
        if obj.type == 'MESH':
            source_name = obj.get('reactor_source_name', obj.name).lower()
            glass = ('glazing' in source_name or 'glass' in source_name
                     or (' / pane' in source_name and 'panel' not in source_name)
                     or any(m and ('glass' in m.name.lower() or 'clearchamber' in m.name.lower()) for m in obj.data.materials))
            if cutaway and glass: continue
            yield obj, pose, glass
        elif obj.type == 'EMPTY' and obj.get('reactor_source_name', obj.name).startswith('subpart_') and obj.get('file') in bpy.data.scenes:
            native = obj.get('reactor_source_name', obj.name)
            if reactor and any(name in native for name in ('Tile', 'Plasma', 'BlastShield')): continue
            child = sources.get(obj['file'], bpy.data.scenes[obj['file']])
            if native.startswith('subpart_EnergyRing'):
                spec = RINGS[int(native[-1])+1]
                pose = pose @ Matrix.Rotation(math.radians(spec['tilt_degrees']), 4, Vector(spec['axis']))
            if reactor and native.startswith('subpart_Ring'):
                ring = list(geometry(child, cutaway=cutaway))
                points = [p @ v.co for mesh, p, _ in ring for v in mesh.data.vertices]
                center = Vector([(min(p[i] for p in points)+max(p[i] for p in points))/2 for i in range(3)])
                deployed = Matrix.Translation((0, 0, .25)) @ Matrix.Rotation(math.radians(25*int(native[-1])), 4, 'X') @ Matrix.Translation(-center)
                for mesh, local, glass in ring: yield mesh, deployed @ local, glass
            else:
                yield from geometry(child, pose, cutaway=cutaway)


def prepare(label):
    """Build one temporary scene and frame its authored geometry."""
    for obj in list(scene.objects):
        if obj.type not in ('MESH', 'CURVE'): continue
        data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if data.users == 0:
            if isinstance(data, bpy.types.Mesh): bpy.data.meshes.remove(data)
            elif isinstance(data, bpy.types.Curve): bpy.data.curves.remove(data)
    _, name, direction = next(job for job in JOBS if job[0] == label)
    cutaway = label in ('reactor', 'energy-core', 'energy-bank')
    parts = list(geometry(sources[name], reactor=label == 'reactor', cutaway=cutaway))
    if label in ('energy-bank', 'energy-full'):
        for subtype, position, angle in [('CapacityAdvanced', (5, 0, 0), -math.pi/2),
                                         ('CapacityAdvanced', (-5, 0, 0), math.pi/2),
                                         ('TransferAdvanced', (0, 5, 0), 0),
                                         ('StabilizerAdvanced', (0, -5, 0), math.pi)]:
            pose = Matrix.Translation(position) @ Matrix.Rotation(angle, 4, 'Z')
            parts.extend(geometry(sources['ArcanePower_Energy'+subtype], pose, cutaway=cutaway))
    if label == 'radiator-stack':
        for height in (6.25, 11.25):
            parts.extend(geometry(sources[CONTRACT['subtype']('Radiator panel')], Matrix.Translation((0, 0, height))))
    bpy.context.window.scene = scene
    points = [pose @ v.co for mesh, pose, _ in parts for v in mesh.data.vertices]
    assert points, label
    center = Vector([(min(p[i] for p in points)+max(p[i] for p in points))/2 for i in range(3)])
    span = max(max(p[i] for p in points)-min(p[i] for p in points) for i in range(3))
    print('BLUEPRINT_PARTS', label, len(parts), flush=True)
    outline_vertices, outline_edges = [], []
    for original, pose, glass in parts:
        mesh = original.data.copy()
        if not glass:
            mesh.materials.clear()
            mesh.materials.append(body)
            for polygon in mesh.polygons: polygon.material_index = 0
            copy = bpy.data.objects.new(original.name+' schematic', mesh)
            scene.collection.objects.link(copy)
            copy.matrix_world = pose
            copy.location -= center
        bm = bmesh.new()
        bm.from_mesh(mesh)
        for line in bm.edges:
            if not line.is_boundary and line.calc_face_angle(0) < math.radians(35): continue
            index = len(outline_vertices)
            outline_vertices.extend(tuple(pose @ vertex.co-center) for vertex in line.verts)
            outline_edges.append((index, index+1))
        bm.free()
        if glass: bpy.data.meshes.remove(mesh)
    # Batch the same authored crease edges in one mesh. Creating hundreds of
    # thousands of individual Curve splines makes dense assemblies needlessly slow.
    lines = bpy.data.meshes.new('Crease outlines')
    lines.from_pydata(outline_vertices, outline_edges, [])
    wire = bpy.data.objects.new('Technical outlines', lines)
    scene.collection.objects.link(wire)
    group = bpy.data.node_groups.new('Blueprint edge tubes', 'GeometryNodeTree')
    group.interface.new_socket(name='Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    group.interface.new_socket(name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    modifier = wire.modifiers.new('Blueprint edge tubes', 'NODES')
    modifier.node_group = group
    incoming = group.nodes.new('NodeGroupInput')
    curves = group.nodes.new('GeometryNodeMeshToCurve')
    profile = group.nodes.new('GeometryNodeCurvePrimitiveCircle')
    profile.inputs['Resolution'].default_value = 4
    profile.inputs['Radius'].default_value = span*.00055
    tubes = group.nodes.new('GeometryNodeCurveToMesh')
    material = group.nodes.new('GeometryNodeSetMaterial')
    material.inputs['Material'].default_value = edge
    outgoing = group.nodes.new('NodeGroupOutput')
    for start, end in [(incoming.outputs['Geometry'], curves.inputs['Mesh']),
                       (curves.outputs['Curve'], tubes.inputs['Curve']),
                       (profile.outputs['Curve'], tubes.inputs['Profile Curve']),
                       (tubes.outputs['Mesh'], material.inputs['Geometry']),
                       (material.outputs['Geometry'], outgoing.inputs['Geometry'])]:
        group.links.new(start, end)
    print('BLUEPRINT_EDGES', label, len(outline_edges), flush=True)
    cam.location = Vector(direction).normalized()*span*3
    cam.rotation_euler = (-cam.location).to_track_quat('-Z', 'Y').to_euler()
    view = cam.rotation_euler.to_matrix().transposed()
    projected = [view @ (p-center) for p in points]
    cam.data.ortho_scale = 1.12*max(max(p[i] for p in projected)-min(p[i] for p in projected) for i in (0, 1))
    scene.render.filepath = str(OUT/(label+'.png'))
    return {'label': label, 'source_parts': len(parts), 'span': round(span, 3), 'file': scene.render.filepath}


def render(label):
    print('BLUEPRINT_PREPARE', prepare(label), flush=True)
    assert scene.camera is not None
    bpy.ops.render.render(write_still=True)
    print('BLUEPRINT_RENDER', label, flush=True)


def main():
    selected = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    setup(selected)
    for label, _, _ in JOBS:
        if not selected or label in selected: render(label)


if __name__ == '__main__': main()
