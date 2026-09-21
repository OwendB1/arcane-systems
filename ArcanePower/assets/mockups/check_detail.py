"""Check native interface sizes and every frame of the rounded ring-bay study."""
import bpy
import json
import math
from pathlib import Path

s = bpy.data.scenes['08 Rounded reactor detail']
bpy.context.window.scene = s
ports = [o for o in s.objects if o.get('source_asset') in ['Conveyor LG', 'Conveyor Access LG']]
upgrades = [o for o in s.objects if o.get('source_asset') == 'Upgrade Port LG']
assert len(ports) == 4 and len(upgrades) == 2
for o in ports+upgrades:
    assert all(abs(v-1) < 1e-6 for v in o.scale)
    width = max(v.co.x for v in o.data.vertices)-min(v.co.x for v in o.data.vertices)
    assert abs(width-(.68 if o in upgrades else 1.36)) < .002
    assert all(abs(v-1) < 1e-6 for v in o.parent.scale)
for o in ports:
    # Native model origin sits one half-cell inside the nominal attachment face.
    p = o.parent.matrix_world @ o.location
    assert abs(max(abs(p.x), abs(p.y))-5) < .001
    assert abs(p.z-1.25) < .001
tiles = [o for o in s.objects if 'arrival_frame' in o]
axes = [o for o in s.objects if 'ring_index' in o]
assert len(tiles) == 80 and len(axes) == 2
for batch in range(1, 21):
    group = [o for o in tiles if o['batch'] == batch]
    assert sorted(o['dispenser'] for o in group) == [1, 2, 3, 4]
    s.frame_set(207+(batch-1)*8)
    assert sum(not o.hide_render for o in tiles) == batch*4
radial_max, zmin, zmax = 0, 100, -100
for frame in range(1, 481):
    s.frame_set(frame)
    s.view_layers[0].update()
    for axis in axes:
        for o in axis.children_recursive:
            if o.type != 'MESH':
                continue
            for vert in o.data.vertices:
                v = o.matrix_world @ vert.co
                radial_max = max(radial_max, math.hypot(v.x, v.y))
                zmin, zmax = min(zmin, v.z), max(zmax, v.z)
assert radial_max < 3.07, 'Ring leaves clear bore of deployment lip'
assert zmin > .44 and zmax < 8.83, 'Ring crosses floor or upper coil bounds'
s.frame_set(440)
result = {'status': 'passed', 'native_conveyor_meshes': 4, 'native_upgrade_meshes': 2,
          'tiles': 80, 'batches_of_four': 20, 'ring_frames_checked': 480,
          'ring_radial_max_m': radial_max, 'ring_z_range_m': [zmin, zmax],
          'limits': 'Base mesh vertices only; not evaluated bevel geometry or exhaustive inter-object collision. Blender prototype; no SE export/in-game validation.'}
Path(__file__).with_name('detail-validation.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, indent=2))
