"""Repair already-built solids affected by the original annulus winding bug.

Leaves deliberately two-sided glass and other open meshes unchanged. Regenerated
geometry uses the corrected annulus helper and does not need this migration.
"""
import bpy
import bmesh
import importlib

get_cols = importlib.import_module('space-engineers-utilities.seut_collections').get_collections
fixed = []
for name in ['ArcanePower_ReactorPrototype', 'ArcanePower_Ring1', 'ArcanePower_Ring2']:
    for obj in get_cols(bpy.data.scenes[name])['main'][0].objects:
        if obj.type != 'MESH':
            continue
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        if bm.faces and all(edge.is_manifold for edge in bm.edges) and bm.calc_volume(signed=True) < -1e-6:
            bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
            bm.normal_update()
            assert bm.calc_volume(signed=True) > 0, obj.name
            bm.to_mesh(obj.data)
            obj.data.update()
            fixed.append(obj.name)
        bm.free()
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
print('Corrected outward normals on', len(fixed), 'closed solids:', fixed)
