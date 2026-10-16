"""Repair already-built solids affected by the original annulus winding bug.

Leaves deliberately two-sided glass and other open meshes unchanged. Regenerated
geometry uses the corrected annulus helper and does not need this migration.
"""
import bpy
import bmesh
import importlib
import sys
from pathlib import Path

get_cols = importlib.import_module('space-engineers-utilities.seut_collections').get_collections


def repair_scene(scene):
    fixed = []
    for obj in get_cols(scene)['main'][0].objects:
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
    return fixed


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from build_construction_stages import NAMES, ENERGY, build_stages

    original_scene = bpy.context.window.scene
    targets = ('ArcanePower_ReactorPrototype', 'ArcanePower_Ring1', 'ArcanePower_Ring2') + ENERGY
    fixed = {}
    try:
        for name in targets:
            scene = bpy.data.scenes.get(name)
            if scene is None:
                continue
            changed = repair_scene(scene)
            if changed:
                fixed[name] = changed
                if name in NAMES + ENERGY:
                    build_stages(scene)
    finally:
        bpy.context.window.scene = original_scene
    bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
    print('Corrected outward normals on', sum(map(len, fixed.values())), 'closed solids:', fixed)
    return fixed


if __name__ == '__main__':
    main()
