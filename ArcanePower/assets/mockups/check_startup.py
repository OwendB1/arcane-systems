"""Check v02 assembly batches, deployment clearance, and ignition gating in Blender."""
import bpy
import json
from pathlib import Path
from mathutils import Vector

s = bpy.data.scenes['06 Tile assembly startup']
bpy.context.window.scene = s
tiles = [o for o in s.objects if 'arrival_frame' in o]
axes = [o for o in s.objects if 'ring_index' in o]
assert len(tiles) == 80 and len(axes) == 2
for batch in range(1, 21):
    group = [o for o in tiles if o['batch'] == batch]
    assert len(group) == 4 and sorted(o['dispenser'] for o in group) == [1, 2, 3, 4]
    s.frame_set(207+(batch-1)*8)
    s.view_layers[0].update()
    assert sum(not o.hide_render for o in tiles) == batch*4
    for tile in group:
        assert abs(tile.scale.x-1) < .0001
        assert abs((tile.location-Vector((0, 0, 5.9))).length-1.35) < .10
core = next(o for o in s.objects if o.name.startswith('Ignition / inner plasma'))
for frame in [1, 30, 90, 120, 200, 279, 359, 380, 405, 414, 415, 450]:
    s.frame_set(frame)
    s.view_layers[0].update()
    assert core.hide_render == (frame < 415)
    if frame == 1:
        assert all(o.location.z < 2.5 for o in axes)
        assert all(o.hide_render for o in tiles)
    if frame >= 120:
        assert all(abs(o.location.z-5.9) < .0001 for o in axes)
    for axis in axes:
        for o in axis.children_recursive:
            if o.type != 'MESH':
                continue
            verts = [o.matrix_world @ v.co for v in o.data.vertices]
            assert min(v.z for v in verts) > .5, 'Ring intersects base floor'
            assert max(v.z for v in verts) < 8.7, 'Ring intersects upper cap'
            assert max(abs(v.x) for v in verts) < 3.75
            assert max(abs(v.y) for v in verts) < 3.75
s.frame_set(279)
result = {'status': 'passed', 'tiles': 80, 'batch_size': 4, 'batches': 20,
          'checks': ['One tile per dispenser in each batch', 'Visible tile count at every batch completion',
                     'Final tile scale and shell position', 'No plasma ignition before assembly/tilt',
                     'Ring parked/raised positions and bay/cap bounds at 12 poses'],
          'limitations': 'Two-ring Blender study only. No exhaustive collision, SE export, inventory consumption, or multiplayer test.'}
Path(__file__).with_name('startup-validation.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, indent=2))
