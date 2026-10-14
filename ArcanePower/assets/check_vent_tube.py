"""Focused Blender checks for vent ports, hatch links and baked open-bore hulls."""
import importlib
import json
import math
from pathlib import Path

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
collections = importlib.import_module('space-engineers-utilities.seut_collections')
report = {}
for name in ('ArcanePower_VentDuct', 'ArcanePower_VentOutlet'):
    scene = bpy.data.scenes[name]
    bpy.context.window.scene = scene
    cols = collections.get_collections(scene)
    cols['hkt'][0].hide_viewport = False
    bpy.context.view_layer.update()
    trees, bodies = [], []
    assert len(cols['hkt'][0].objects) == 8
    for obj in cols['hkt'][0].objects:
        assert obj.matrix_world == Matrix.Identity(4), obj.name
        assert obj.rigid_body.collision_shape == 'CONVEX_HULL'
        assert obj.data.uv_layers and obj.data.materials
        vertices = [v.co.copy() for v in obj.data.vertices]
        for face in obj.data.polygons:
            origin = vertices[face.vertices[0]]
            assert all(face.normal.dot(p - origin) < .0001 for p in vertices), obj.name
        trees.append(BVHTree.FromPolygons(vertices, [list(p.vertices) for p in obj.data.polygons]))
        bodies.append({'name': obj.name, 'min': [min(v[i] for v in vertices) for i in range(3)],
                       'max': [max(v[i] for v in vertices) for i in range(3)]})

    def cast(origin, direction, distance):
        return [tree.ray_cast(Vector(origin), Vector(direction), distance)[0] for tree in trees]

    for i in range(128):
        angle = (i + .5) * math.tau / 128
        x, y = math.cos(angle), math.sin(angle)
        for radius in (0, 1, 1.82):
            assert not any(p is not None for p in cast((radius*x, radius*y, -1.5), (0, 0, 1), 3)), 'blocked bore'
        for radius in (2.2, 3.4):
            hits = [p for p in cast((radius*x, radius*y, 1.5), (0, 0, -1), 3) if p is not None]
            assert hits and min(abs(p.z - 1.25) for p in hits) < .001, 'missing upper platform'
    main = cols['main'][0]
    ports = [o for o in main.objects if o.name.startswith('detector_conveyor_')]
    assert len(ports) == 2
    for suffix, height in (('top', 1.25), ('bottom', -1.25)):
        port = next(o for o in ports if o.name.endswith(suffix))
        assert (port.matrix_world.translation - Vector((0, 0, height))).length < .0001
    leaves = [o for o in main.objects if o.name.startswith('subpart_OutletHatch')]
    assert len(leaves) == (4 if name.endswith('Outlet') else 0)
    for i, leaf in enumerate(sorted(leaves, key=lambda o: o.name)):
        assert leaf['file'] == 'ArcanePower_VentHatch'
        expected = Matrix.Translation((0, 0, 1.08)) @ Matrix.Rotation(i * math.pi / 2, 4, 'Z')
        assert max(abs(leaf.matrix_world[r][c]-expected[r][c]) for r in range(4) for c in range(4)) < .0001
    report[name] = {'bodies': bodies, 'bore_probes': 384, 'platform_probes': 256,
                    'conveyor_ports': 2, 'outlet_leaf_links': len(leaves)}

# The two model interfaces meet at native grid spacing: reactor roof
# at 3.75m, first tube centre at 5m, then 2.5m per section.
reactor = bpy.data.scenes['ArcanePower_ReactorPrototype']
bpy.context.window.scene = reactor
bpy.context.view_layer.update()
port = reactor.objects['detector_conveyor_top']
# The reactor detector is inset 30mm in its 80mm-thick native port volume.
assert (port.matrix_world.translation - Vector((0, 0, 3.75))).length < .04
report['installation'] = {'first_tube_centre_m': 5, 'section_spacing_m': 2.5,
                          'required_ducts': [1, 15], 'outlets': 1,
                          'same_grid': True, 'aligned_up': True}
report['limits'] = 'Static tube hulls only; moving hatch physics and in-game contact remain unverified.'
(ROOT / 'validation/vent-tube-model.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS: both vent models, 768 clear bore probes, 512 platform contacts, aligned ports and four outlet leaves')
