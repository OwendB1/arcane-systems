"""Focused gates for the curved split-cover repair, run in live Blender."""
import json
import math
from pathlib import Path
import runpy

import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(str(ROOT/'assets/build_thermal_models.py'))
T = runpy.run_path(str(ROOT/'assets/build_reactor_thermal_manifolds.py'))


def audit():
    scene = M['scene_for']('Reactor housing')
    old_pose = scene['thermal_manifolds_deployment']
    T['pose'](0)
    col = M['main_for']('Reactor housing')
    motion = json.loads(col['manifold_motion'])
    failures, pose_rows = [], []

    def fail(check, detail):
        failures.append({'check': check, 'detail': detail})

    def geometry(obj):
        obj.data.calc_loop_triangles()
        verts = [obj.matrix_world@v.co for v in obj.data.vertices]
        bounds = ([min(v[i] for v in verts) for i in range(3)], [max(v[i] for v in verts) for i in range(3)])
        tree = BVHTree.FromPolygons(verts, [list(t.vertices) for t in obj.data.loop_triangles], all_triangles=True, epsilon=0.)
        return tree, bounds

    def overlaps(a, b):
        return all(a[0][i] < b[1][i]-.00001 and b[0][i] < a[1][i]-.00001 for i in range(3))

    moving = [o for o in col.objects if o.type == 'MESH' and o.get('thermal_motion_group')]
    covers = [o for o in moving if o.get('thermal_cover')]
    static = [o for o in col.objects if o.type == 'MESH' and not o.get('thermal_motion_group')]
    static_data = {o.name: geometry(o) for o in static}
    if len(covers) != 8 or len(motion) != 4:
        fail('four bays / eight curved leaves', [len(motion), len(covers)])
    for cover in covers:
        if not cover.get('uncut_original_checkpoint') or not cover.get('native_uv_preserved'):
            fail('original curved geometry and UV source', cover.name)
        bm = bmesh.new()
        bm.from_mesh(cover.data)
        if any(not e.is_manifold for e in bm.edges) or bm.calc_volume(signed=True) <= 0:
            fail('closed split armor', cover.name)
        bm.free()
    for row in motion:
        # Test the entire projected nose disc, including the lowest edge of the
        # original 1.48 m armor panel. Fixed cover seams may remain narrow.
        side = 1 if row['deployed_face'][0] > 0 else -1
        y, z = row['stowed_face'][1:]
        relevant = [geometry(o)[0] for o in covers if row['id']+' /' in o.name]
        for sign in (-1, 1):
            for i in range(33):
                a = i*math.tau/32
                radius = 0 if i == 32 else .273
                point = Vector((side*8, y+radius*math.cos(a), z+sign*.46+radius*math.sin(a)))
                if not any(t.ray_cast(point, Vector((-side, 0, 0)), 4)[0] is not None for t in relevant):
                    fail('pipes fully hidden by closed original armor', [row['id'], sign, i])
    # Include stage boundaries and mid-travel positions. No pose may rely on
    # clipping the cover through a neighbouring panel or the controller bay.
    for value in (0, .05, .10, .15, .20, .25, .30, .35, .40, .45, .50, .65, .80, 1):
        T['pose'](value)
        data = {o.name: geometry(o) for o in moving}
        tested = 0
        for i, obj in enumerate(moving):
            tree, box = data[obj.name]
            for other in static:
                other_tree, other_box = static_data[other.name]
                if overlaps(box, other_box):
                    tested += 1
                    if tree.overlap(other_tree):
                        fail('moving part / fixed geometry clearance', [value, obj.name, other.name])
            for other in moving[i+1:]:
                if obj['thermal_motion_group'] == other['thermal_motion_group']:
                    continue
                other_tree, other_box = data[other.name]
                if overlaps(box, other_box):
                    tested += 1
                    if tree.overlap(other_tree):
                        fail('independent moving groups clearance', [value, obj.name, other.name])
        for row in motion:
            carriage = bpy.data.objects[row['carriage']]
            expected = Vector(row['stowed_face']).lerp(Vector(row['deployed_face']), max(0, min(1, (value-.45)/.55)))
            if (carriage.matrix_world.translation-expected).length > 1e-5:
                fail('carriage position', [value, row['id']])
            if value < .45 and abs(carriage.matrix_world.translation.x-row['stowed_face'][0]) > 1e-5:
                fail('covers clear before pipe deployment', [value, row['id']])
        pose_rows.append({'deployment': value, 'broadphase_pairs_checked': tested})
    T['pose'](old_pose)
    report = {'status': 'passed' if not failures else 'failed', 'bays': 4, 'curved_leaves': len(covers),
              'closed_nose_occlusion_samples': 264, 'poses': pose_rows, 'failures': failures,
              'limits': 'Authored geometry and mechanical preview; native subparts/runtime are not installed.'}
    (M['OUT']/'curved-manifold-audit.json').write_text(json.dumps(report, indent=2)+'\n')
    return {'status': report['status'], 'failure_count': len(failures), 'failures': failures[:30], 'poses': len(pose_rows)}


if __name__ == '__main__':
    result = audit()
