"""Centre native tiedown decals on accessible deck plates, preserving atlas UVs."""
import bpy
import importlib
import json
import math
from pathlib import Path
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

s = bpy.data.scenes['ArcanePower_ReactorPrototype']
col = importlib.import_module('space-engineers-utilities.seut_collections').get_collections(s)['main'][0]


def surface(o):
    return BVHTree.FromPolygons([o.matrix_world @ v.co for v in o.data.vertices],
                               [list(p.vertices) for p in o.data.polygons])


plates = []
for o in col.objects:
    if o.name.startswith('Deck removable plate'):
        center = sum((o.matrix_world @ v.co for v in o.data.vertices), Vector()) / len(o.data.vertices)
        plates.append((math.atan2(center.y, center.x), o.name, surface(o)))
saddles = [surface(o) for o in col.objects if o.name.startswith('Integrated support / curved pillar saddle')]
results, removed = [], []
for o in list(col.objects):
    if not o.name.startswith('SEUT / Tiedown Handle'):
        continue
    points = [o.matrix_world @ v.co for v in o.data.vertices]
    center = sum(points, Vector()) / len(points)
    angle = math.atan2(center.y, center.x)
    desired = angle if o.get('deck_plate') else angle + math.pi / 24
    target, name, deck = min(plates, key=lambda p: abs(math.atan2(math.sin(desired-p[0]), math.cos(desired-p[0]))))
    rotation = Matrix.Rotation(target-angle, 4, 'Z')
    points = [rotation @ p for p in points]
    center = sum(points, Vector()) / len(points)
    # Remove inaccessible decals instead of projecting handles onto the saddles.
    samples = points + [center]
    if any(tree.ray_cast(Vector((p.x, p.y, 0)), Vector((0, 0, -1)), 1.2585)[0] is not None
           for tree in saddles for p in samples):
        removed.append(o.name)
        if bpy.context.view_layer.objects.active == o:
            bpy.context.view_layer.objects.active = None
        bpy.data.objects.remove(o, do_unlink=True)
        continue
    o.data = o.data.copy()
    inv = o.matrix_world.inverted()
    for v, p in zip(o.data.vertices, points):
        hit, normal, _, _ = deck.ray_cast(Vector((p.x, p.y, 0)), Vector((0, 0, -1)), 2)
        assert hit is not None and normal.z > .99, (o.name, name)
        v.co = inv @ (hit + Vector((0, 0, .0015)))
    o.data.update()
    o['deck_plate'] = name
    o['surface_clearance_m'] = .0015
    results.append({'handle': o.name, 'plate': name})
assert len(results) == 16, len(results)
s['tiedown_placement'] = '16 panel-centred deck handles; pillar saddle bays clear; 1.5mm surface offset'
(Path(__file__).resolve().parents[1] / 'validation/tiedown-handles.json').write_text(
    json.dumps({'handles': results, 'removed_under_saddles': removed, 'clearance_m': .0015}, indent=2))
bpy.context.view_layer.update()
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
print(s['tiedown_placement'])
