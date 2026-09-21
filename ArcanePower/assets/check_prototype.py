"""Blender geometry evidence, not a substitute for an in-game interaction check."""
import bpy
import importlib
import json
import math
from pathlib import Path
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

s = bpy.data.scenes['ArcanePower_ReactorPrototype']
cols = importlib.import_module('space-engineers-utilities.seut_collections').get_collections(s)
meshes, bounds = [], {}
deck_tops = 0
for key in ['main', 'hkt']:
    points = []
    for obj in cols[key][0].objects:
        if obj.type != 'MESH':
            continue
        vertices = [obj.matrix_world @ v.co for v in obj.data.vertices]
        points.extend(vertices)
        if key == 'main':
            meshes.append((obj.name, BVHTree.FromPolygons(vertices, [list(p.vertices) for p in obj.data.polygons])))
            if obj.name.startswith('Deck removable plate'):
                top = max(v.z for v in vertices)
                faces = [p for p in obj.data.polygons if all(abs(vertices[i].z-top) < 1e-5 for i in p.vertices)]
                assert faces and all(p.normal.z > .99 for p in faces), obj.name
                deck_tops += 1
    bounds[key] = {'min': [min(p[i] for p in points) for i in range(3)],
                   'max': [max(p[i] for p in points) for i in range(3)]}
    for p in points:
        assert abs(p.x) <= 6.2501 and abs(p.y) <= 6.2501 and abs(p.z) <= 3.7501, (key, p[:])

results, corner_backing = [], []
for side in range(6):
    native = ('Inventory access /', 'SEUT / Conveyor Frame LG') if side in (0, 2) else ('Base upgrade / native socket' if side in (1, 3) else 'Axial conveyor /')
    width = .2 if side in (1, 3) else .45
    samples = []
    points = [(0, 0), (-width, 0), (width, 0), (0, width), (0, -width)]
    if side not in (1, 3):
        points += [(-.85, 0), (.85, 0), (0, .85), (0, -.85)]
    for u, v in points:
        if side < 4:
            rotation = Matrix.Rotation(side*math.pi/2, 4, 'Z')
            origin = rotation @ Vector((u, -6.6, -2.5+v))
            direction = rotation @ Vector((0, 1, 0))
        else:
            sign = 1 if side == 4 else -1
            origin = Vector((u, v, sign*4.1))
            direction = Vector((0, 0, -sign))
        hits = []
        for name, mesh in meshes:
            hit, normal, index, distance = mesh.ray_cast(origin, direction, 1)
            if hit is not None:
                hits.append((distance, name))
        first = min(hits) if hits else None
        samples.append(first)
        assert first and first[1].startswith(native), (side, u, v, first)
    results.append({'side': side, 'samples': samples})
    if side not in (1, 3):
        # Outside the clipped native corners, housing must remain rather than a
        # hole left by a rectangular cutter. These complement the frame-edge rays.
        for u, v in [(-.97, -.97), (-.97, .97), (.97, -.97), (.97, .97)]:
            if side < 4:
                origin = rotation @ Vector((u, -6.6, -2.5+v))
            else:
                origin = Vector((u, v, sign*4.1))
            hits = []
            for name, mesh in meshes:
                hit, normal, index, distance = mesh.ray_cast(origin, direction, 1)
                if hit is not None:
                    hits.append((distance, name))
            first = min(hits) if hits else None
            assert first and not first[1].startswith(native), (side, u, v, first)
            corner_backing.append({'side': side, 'point': [u, v], 'housing': first})

dummies = {o.name: list(o.location) for o in cols['main'][0].objects if o.name.startswith('detector_')}
assert deck_tops == 24, deck_tops
assert len([n for n in dummies if n.startswith('detector_conveyor_')]) == 4
assert len([n for n in dummies if n.startswith('detector_upgrade_')]) == 2
assert len(cols['hkt'][0].objects) == 10
report = {'scope': 'Blender only; no game calls', 'bounds_blender_xyz': bounds,
          'native_face_visibility': results, 'detectors_blender_xyz': dummies,
          'collision_bodies': 10, 'game_size_xyz': [5, 3, 5], 'outward_deck_plates': deck_tops,
          'chamfer_corner_backing': corner_backing}
path = Path(__file__).resolve().parents[1]/'validation/blender-prototype.json'
path.write_text(json.dumps(report, indent=2))
print('PASS: main/collision bounds, 24 outward deck plates,', sum(len(r['samples']) for r in results), 'native hatch/frame rays, 4 conveyor + 2 upgrade detectors; evidence:', path)
