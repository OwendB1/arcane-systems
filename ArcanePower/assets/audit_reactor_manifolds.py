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
    edges = [o for o in moving if o.get('thermal_cover_edge')]
    bodies = [o for o in moving if o.get('thermal_rounded_manifold')]
    connectors = [o for o in moving if o.get('thermal_moving_connector')]
    tails = [o for o in moving if o.get('thermal_extending_connector')]
    static = [o for o in col.objects if o.type == 'MESH' and not o.get('thermal_motion_group')]
    static_data = {o.name: geometry(o) for o in static}
    backings = [o for o in static if o.get('thermal_controller_backing')]
    backing_samples = 0
    if len(backings) != 2:
        fail('both controller recesses restored', len(backings))
    for backing in backings:
        side = backing['thermal_controller_backing']
        tree = static_data[backing.name][0]
        for iy in range(-6, 7):
            y = iy*.11
            for z in (-3.18, -3.10, -3., -2.9, -2.75, -2.6, -2.45, -2.33,
                      -2.2, -2.05, -1.9, -1.82):
                if abs(y) < .31 and abs(z+2.33) < .31:
                    continue
                radius = 6.124 if z < -3.07 else 6.158
                expected_x = side*math.sqrt(radius*radius-y*y)
                hit = tree.ray_cast(Vector((side*8, y, z)), Vector((-side, 0, 0)), 3)[0]
                backing_samples += 1
                if hit is None or abs(hit.x-expected_x) > .002:
                    fail('continuous curved controller backing and lower notch', [side, y, z])
        native = next(o for o in static if o.get('reactor_source_name') ==
                      'Base upgrade / native socket '+str(1 if side > 0 else 3))
        source = bpy.data.objects[native['reactor_source_name']]
        if native.data != source.data or any(abs(a-b) > 1e-6 for ra, rb in
                zip(native.matrix_world, source.matrix_world) for a, b in zip(ra, rb)):
            fail('unmodified native controller connector', native.name)
    if len(covers) != 8 or len(motion) != 4:
        fail('four bays / eight curved leaves', [len(motion), len(covers)])
    if len(edges) != 8:
        fail('eight backed outer door seams', len(edges))
    if len(bodies) != 4 or len(connectors) != 4 or len(tails) != 4:
        fail('four rounded manifolds / four complete connectors', [len(bodies), len(connectors), len(tails)])
    for obj in bodies+connectors+tails:
        ident = obj.get('thermal_rounded_manifold') or obj.get('thermal_moving_connector') or obj['thermal_extending_connector']
        carriage = next(row['carriage'] for row in motion if row['id'] == ident)
        if not obj.parent or obj.parent.name != carriage or obj.get('thermal_motion_group') != carriage:
            fail('casting and connector follow pipe carriage', obj.name)
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        if any(not e.is_manifold for e in bm.edges) or bm.calc_volume(signed=True) <= 0:
            fail('closed positive manifold solid', obj.name)
        bm.free()
    for cover in covers+edges:
        if cover in covers and (not cover.get('uncut_original_checkpoint') or not cover.get('native_uv_preserved')):
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
        relevant = [geometry(o)[0] for o in covers+edges
                    if row['id']+' /' in o.name or o.get('thermal_cover_edge') == row['id']]
        # The old nose-only test missed the 68 mm slots at the door edges.
        # Check those seams directly, including oblique views into the bay.
        for edge in (-1, 1):
            a = row['panel_angle']+edge*.117
            for height in (-3.04, -2.75, -2.33, -1.91, -1.62):
                target = Vector((6.01*math.cos(a), 6.01*math.sin(a), height))
                for offset in (-.32, 0, .32):
                    eye_angle = row['panel_angle']+offset
                    direction = Vector((-math.cos(eye_angle), -math.sin(eye_angle), 0))
                    origin = target-direction*2
                    if not any(t.ray_cast(origin, direction, 2.2)[0] is not None for t in relevant):
                        fail('closed outer seam hides plumbing', [row['id'], edge, height, offset])
        for sign in (-1, 1):
            for i in range(33):
                a = i*math.tau/32
                radius = 0 if i == 32 else .273
                point = Vector((side*8, y+radius*math.cos(a), z+sign*.46+radius*math.sin(a)))
                if not any(t.ray_cast(point, Vector((-side, 0, 0)), 4)[0] is not None for t in relevant):
                    fail('pipes fully hidden by closed original armor', [row['id'], sign, i])
        # The shared casting is wider than a pipe nose. Test its full projected
        # silhouette as well as the two original circular heads.
        for obj in bodies+connectors+tails:
            ident = obj.get('thermal_rounded_manifold') or obj.get('thermal_moving_connector') or obj.get('thermal_extending_connector')
            if ident != row['id']:
                continue
            for vertex in obj.data.vertices:
                point = obj.matrix_world@vertex.co
                point.x = side*8
                if not any(t.ray_cast(point, Vector((-side, 0, 0)), 4)[0] is not None for t in relevant):
                    fail('rounded assembly hidden behind closed armor', obj.name)
        body = next(o for o in bodies if o['thermal_rounded_manifold'] == row['id'])
        casting = geometry(body)[0]
        for sign in (-1, 1):
            for i in range(17):
                a = i*math.tau/16
                radius = 0 if i == 16 else .22
                start = Vector((side*8, y+radius*math.cos(a), z+sign*.46+radius*math.sin(a)))
                if casting.ray_cast(start, Vector((-side, 0, 0)), 5)[0] is not None:
                    fail('isolated open manifold bores', [row['id'], sign, i])
    # Include stage boundaries and mid-travel positions. No pose may rely on
    # clipping the cover through a neighbouring panel or the controller bay.
    values = sorted(set([i/40 for i in range(41)]+[.149, .151, .399, .401, .449, .451]))
    for value in values:
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
            if value == 1:
                connector = next(o for o in connectors if o['thermal_moving_connector'] == row['id'])
                tail = next(o for o in tails if o['thermal_extending_connector'] == row['id'])
                tail_points = [tail.matrix_world@v.co for v in tail.data.vertices]
                points = [connector.matrix_world@v.co for v in connector.data.vertices]+tail_points
                if min(math.hypot(p.x, p.y) for p in points) >= 6.10:
                    fail('deployed connector reaches inside curved housing', row['id'])
                if min(abs(p.x) for p in tail_points) >= 4.29:
                    fail('deployed connector remains engaged through bulkhead guide', row['id'])
        pose_rows.append({'deployment': value, 'broadphase_pairs_checked': tested})
    T['pose'](old_pose)
    report = {'status': 'passed' if not failures else 'failed', 'bays': 4, 'curved_leaves': len(covers),
              'controller_backings': len(backings), 'controller_backing_samples': backing_samples,
              'rounded_manifolds': len(bodies), 'moving_connectors': len(connectors), 'extending_tails': len(tails),
              'closed_nose_occlusion_samples': 264, 'poses': pose_rows, 'failures': failures,
              'limits': 'Authored geometry and mechanical preview; native subparts/runtime are not installed.'}
    (M['OUT']/'curved-manifold-audit.json').write_text(json.dumps(report, indent=2)+'\n')
    return {'status': report['status'], 'failure_count': len(failures), 'failures': failures[:30], 'poses': len(pose_rows)}


if __name__ == '__main__':
    result = audit()
