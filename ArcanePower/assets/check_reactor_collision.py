"""Focused Blender contact probes for the reactor housing, not a game test."""
import importlib
import json
import math
from pathlib import Path

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
scene = bpy.data.scenes['ArcanePower_ReactorPrototype']
bpy.context.window.scene = scene
collections = importlib.import_module('space-engineers-utilities.seut_collections').get_collections(scene)
collision = collections['hkt'][0]
collision.hide_viewport = False
bpy.context.view_layer.update()
assert len(collision.objects) == 10
trees, bodies = [], []
for obj in collision.objects:
    assert obj.rigid_body.collision_shape == 'CONVEX_HULL'
    assert obj.matrix_world == Matrix.Identity(4), (obj.name, 'unbaked placement')
    assert not obj.modifiers and obj.data.uv_layers and obj.data.materials
    vertices = [obj.matrix_world @ v.co for v in obj.data.vertices]
    assert all(abs(p.x) <= 6.2501 and abs(p.y) <= 6.2501 and abs(p.z) <= 3.7501 for p in vertices)
    # Validate the actual convex solid, not a curved mesh that Havok will fill in.
    for face in obj.data.polygons:
        anchor = vertices[face.vertices[0]]
        assert all(face.normal.dot(p - anchor) < .0001 for p in vertices), obj.name
    trees.append((obj.name, BVHTree.FromPolygons(vertices, [list(p.vertices) for p in obj.data.polygons])))
    bodies.append({'name': obj.name, 'vertices': len(vertices),
                   'min': [min(p[i] for p in vertices) for i in range(3)],
                   'max': [max(p[i] for p in vertices) for i in range(3)]})


def cast(origin, direction, length):
    hits = []
    for name, tree in trees:
        point, normal, index, distance = tree.ray_cast(Vector(origin), Vector(direction), length)
        if point is not None:
            hits.append((distance, name, point))
    return min(hits, key=lambda h: h[0]) if hits else None


deck_hits, roof_hits, glass_hits, clear_ledge = [], [], [], []
for index in range(128):
    angle = (index + .5) * math.tau / 128
    axis = Vector((math.cos(angle), math.sin(angle), 0))
    for radius in (0, 2, 3.9, 5.3, 5.7, 6.1):
        p = axis * radius
        deck = cast((p.x, p.y, -1), (0, 0, -1), 3)
        roof = cast((p.x, p.y, 4.5), (0, 0, -1), 2)
        assert deck and deck[1] == 'AP collision / base and platform', (index, radius, deck)
        assert abs(deck[2].z + 1.26) < .001
        assert roof and roof[1] == 'AP collision / roof platform', (index, radius, roof)
        assert abs(roof[2].z - 3.75) < .001
        deck_hits.append(deck[2].z)
        roof_hits.append(roof[2].z)
    hit = cast(axis * 7, -axis, 4)
    assert hit and 'glass' in hit[1], (index, hit)
    error = abs(hit[2].xy.length - 4.944)
    assert error < .003, (index, error)
    glass_hits.append(error)
    # Walkway outside the glass stays clear from just above the deck to head
    # height. At R5.35 a 0.4m character radius has clearance to the glass.
    for z in (-1.24, -.3, .7):
        start = axis * 6.3
        start.z = z
        assert cast(start, -axis, .95) is None, (index, z, 'blocked ledge')
        clear_ledge.append([index, z])

report = {'scope': 'Blender convex contact geometry; not native character or Havok runtime validation',
          'revision': scene['reactor_collision_revision'], 'bodies': bodies,
          'deck_contacts': len(deck_hits), 'roof_contacts': len(roof_hits),
          'glass_contacts': len(glass_hits), 'maximum_glass_surface_error_m': max(glass_hits),
          'clear_ledge_probes': len(clear_ledge), 'identity_transforms': True,
          'moving_hatch_collision': False}
(ROOT / 'validation/reactor-collision.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS:', len(deck_hits), 'deck contacts,', len(roof_hits), 'roof contacts,',
      len(glass_hits), 'glass contacts,', len(clear_ledge), 'clear ledge probes; glass error', max(glass_hits))
