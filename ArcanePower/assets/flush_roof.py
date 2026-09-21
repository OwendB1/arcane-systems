"""Seat the complete round roof against the 3-cell ceiling, retaining recessed seams."""
import bpy
import importlib
from mathutils import Vector

s = bpy.data.scenes['ArcanePower_ReactorPrototype']
assert s.get('three_cells_applied'), 'Fit the three-cell housing first'
bpy.context.window.scene = s
col = importlib.import_module('space-engineers-utilities.seut_collections').get_collections(s)['main'][0]


def top(obj):
    return max((obj.matrix_world @ v.co).z for v in obj.data.vertices)


def seat(obj, height):
    offset = height - top(obj)
    # Export scene mesh transforms are baked; refuse a silently incorrect adjustment.
    assert all(abs(obj.matrix_world[i][j] - (1 if i == j else 0)) < 1e-5
               for i in range(4) for j in range(4))
    for v in obj.data.vertices:
        v.co.z += offset


housing = next(o for o in col.objects if o.name.startswith('Circular upper armored housing'))
old_top = top(housing)
for v in housing.data.vertices:
    if v.co.z > 3.4:
        v.co.z = 3.4 + (v.co.z - 3.4) * (.346 / (old_top - 3.4))

for obj in col.objects:
    if obj.type != 'MESH':
        continue
    if obj.name.startswith(('Cap central service hatch', 'Cap removable sector')):
        seat(obj, 3.748)
    elif obj.name.startswith('Cap hatch rim') or (obj.name.startswith('Upper armored rim') and top(obj) > 3.5):
        seat(obj, 3.750)
    elif obj.name.startswith(('SEUT / Large Screw', 'SEUT / Wire Vent')) and top(obj) > 3.5:
        # Surface decals sit 1 mm above their panels, entirely under the ceiling.
        seat(obj, 3.749)

# Supporting roof now fills the old space beneath the plates and decals.
# Only deliberate 2–4 mm panel relief remains under the common +3.750 m ceiling.
max_z = max(top(o) for o in col.objects if o.type == 'MESH')
assert max_z <= 3.75001, max_z
s['roof_seating'] = 'Ceiling Z=3.750; continuous roof backing=3.746; plates=3.748; decals=3.749; rims=3.750 m'
bpy.context.view_layer.update()
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
print(s['roof_seating'])
