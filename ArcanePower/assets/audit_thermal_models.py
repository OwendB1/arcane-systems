"""Production main-model gates: grid, solids, support, UVs and real assemblies."""
import hashlib
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
R = runpy.run_path(str(ROOT/'assets/review_thermal_models.py'))
C, OUT = M['CONTRACT'], M['OUT']


def audit():
    previous = bpy.context.scene
    failures, models, trees = [], {}, {}

    def fail(model, check, obj):
        failures.append({'model': model, 'check': check, 'object': obj})

    def tree(obj):
        if obj.name not in trees:
            mesh = obj.data
            mesh.calc_loop_triangles()
            trees[obj.name] = BVHTree.FromPolygons([obj.matrix_world@v.co for v in mesh.vertices],
                [list(t.vertices) for t in mesh.loop_triangles], all_triangles=True)
        return trees[obj.name]

    for name, cells in C['SPECS'].items():
        ident = C['subtype'](name)
        if ident not in bpy.data.scenes:
            fail(name, 'missing base', ident)
            continue
        scene, col = M['scene_for'](name), M['main_for'](name)
        bpy.context.window.scene = scene
        bpy.context.view_layer.update()
        half = Vector(cells)*1.25
        stats = {'phase': scene['thermal_phase'], 'meshes': 0, 'triangles': 0,
                 'fasteners': 0, 'decals': 0, 'markings': 0}
        for obj in col.objects:
            if obj.type == 'MESH':
                stats['meshes'] += 1
                stats['triangles'] += sum(len(f.vertices)-2 for f in obj.data.polygons)
                points = [obj.matrix_world@v.co for v in obj.data.vertices]
                if any(not math.isfinite(v) for p in points for v in p):
                    fail(name, 'finite geometry', obj.name)
                inherited = obj.get('reactor_source_name')
                if not inherited and any(abs(p[i]) > half[i]+.001 for p in points for i in range(3)):
                    fail(name, '2.5 m envelope', obj.name)
                mesh = obj.data
                uv = mesh.uv_layers.active
                if not uv or any(not math.isfinite(v) for p in uv.data for v in p.uv):
                    fail(name, 'finite UV coverage', obj.name)
                original = bpy.data.objects.get(inherited) if inherited else None
                if inherited and (not original or original == obj or original.get('reactor_source_name')):
                    fail(name, 'original reactor provenance', obj.name)
                accepted_materials = original and list(mesh.materials) == list(original.data.materials)
                if not mesh.materials or (not accepted_materials and any(not mat or not mat.library for mat in mesh.materials)):
                    fail(name, 'native SEUT material', obj.name)
                if not obj.get('thermal_decal_support') and (not inherited or obj.get('thermal_pocket_cut')):
                    bm = bmesh.new()
                    bm.from_mesh(mesh)
                    if any(not e.is_manifold for e in bm.edges) or bm.calc_volume(signed=True) <= 1e-10:
                        fail(name, 'closed positive solid', obj.name)
                    bm.free()
                    mesh.calc_loop_triangles()
                    if uv and any(abs((uv.data[t.loops[1]].uv-uv.data[t.loops[0]].uv).cross(
                        uv.data[t.loops[2]].uv-uv.data[t.loops[0]].uv)) < 1e-11
                        # Boolean tessellation can leave numerically collinear
                        # slivers below 0.01 mm²; they have no usable UV area.
                        for t in mesh.loop_triangles if t.area > 1e-8):
                        fail(name, 'noncollapsed UV triangles', obj.name)
            key = next((k for k in ('thermal_support', 'thermal_decal_support', 'thermal_marking_support') if obj.get(k)), None)
            if not key:
                continue
            support = bpy.data.objects.get(obj[key])
            if not support:
                fail(name, 'missing backing', obj.name)
                continue
            if key == 'thermal_support':
                stats['fasteners'] += 1
                point, axis = Vector(obj['support_point']), Vector(obj['support_axis'])
                if obj.get('thermal_support_space'):
                    matrix = bpy.data.objects[obj['thermal_support_space']].matrix_world
                    point, axis = matrix@point, matrix.to_3x3()@axis
                points = [p-axis*(p-point).dot(axis) for p in (obj.matrix_world@v.co for v in obj.data.vertices)]
                tolerance = .012
            elif key == 'thermal_decal_support':
                stats['decals'] += 1
                points = [obj.matrix_world@v.co for v in obj.data.vertices]
                tolerance = .006
            else:
                stats['markings'] += 1
                ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
                mesh = ev.to_mesh()
                points = [obj.matrix_world@v.co for v in mesh.vertices]
                ev.to_mesh_clear()
                tolerance = .006
            if any(tree(support).find_nearest(p)[3] > tolerance for p in points):
                fail(name, 'full backed footprint', obj.name)
        ports = json.loads(col['ports'])
        for port in ports:
            pos, n, up = [Vector(port[k]) for k in ('position', 'normal', 'hot_axis')]
            axis = max(range(3), key=lambda i: abs(n[i]))
            if abs(abs(pos[axis])-half[axis]) > 1e-5 or n.dot(pos) <= 0 or abs(n.dot(up)) > 1e-5:
                fail(name, 'socket face/normal/roll', port['id'])
            for i in range(3):
                if i != axis:
                    offset = port.get('cell_offset', [0, 0, 0])
                    if offset != [0, 0, 0] and (name not in ('Reactor housing', 'PRIMARY / Reactor adapter') or offset != [0, 0, .17]):
                        fail(name, 'unapproved socket offset', port['id'])
                    index = (pos[i]-offset[i]+half[i]-1.25)/2.5
                    if abs(index-round(index)) > 1e-5:
                        fail(name, 'socket cell centre', port['id'])
            u = up.cross(n)
            for sign in (-1, 1):
                centre = pos+up*(sign*.46)
                samples = [centre]+[centre+.20*(u*math.cos(i*math.tau/8)+up*math.sin(i*math.tau/8)) for i in range(8)]
                if any(tree(o).ray_cast(p+n*.05, -n, .20)[0] is not None
                       for p in samples for o in col.objects if o.type == 'MESH' and not o.get('thermal_decal_support')):
                    fail(name, 'open 150 mm socket neck', port['id']+' '+str(sign))
        stats['ports'] = len(ports)
        models[name] = stats
    assemblies = {}
    for scene in (s for s in bpy.data.scenes if s.get('thermal_grid_routes') or s.get('bank_expected_ports_closed')):
        bpy.context.window.scene = scene
        bpy.context.view_layer.update()
        occupied, socket_map, instances = {}, {}, []
        for obj in scene.objects:
            name = obj.get('thermal_instance')
            if not name:
                continue
            instances.append(obj)
            matrix = obj.matrix_world.to_3x3()
            size = C['SPECS'][name]
            extent = tuple(round(sum(abs(matrix[i][j])*size[j] for j in range(3))) for i in range(3))
            for cell in C['occupied'](obj.matrix_world.translation, extent):
                if cell in occupied:
                    fail(scene.name, 'occupied cell overlap', obj.name+' / '+occupied[cell])
                occupied[cell] = obj.name
            for port in R['ports'](obj):
                key = tuple(round(x, 4) for x in port['position'])
                socket_map.setdefault(key, []).append((obj.name, port))
        for position, items in socket_map.items():
            if len(items) != 2:
                fail(scene.name, 'unmated/overused socket', str((position, [x[0] for x in items])))
                continue
            (an, a), (bn, b) = items
            if a['type'] != b['type'] or Vector(a['normal']).dot(Vector(b['normal'])) > -.9999 or Vector(a['hot_axis']).dot(Vector(b['hot_axis'])) < .9999:
                fail(scene.name, 'circuit or H/C reversal', an+' / '+bn)
        assemblies[scene.name] = {'instances': len(instances), 'occupied_cells': len(occupied), 'mated_sockets': len(socket_map)}
    protected = json.loads((OUT/'protected-sources.json').read_text())
    hashes = {n: hashlib.sha256((ROOT/'assets'/n).read_bytes()).hexdigest() for n in protected}
    if hashes != protected:
        fail('Protected sources', 'hash changed', str([n for n in protected if protected[n] != hashes[n]]))
    bpy.context.window.scene = previous
    report = {'status': 'passed' if not failures else 'failed', 'models': models, 'assemblies': assemblies,
              'protected_sources_unchanged': hashes == protected, 'failures': failures,
              'limits': 'Main geometry/grid/backing/UV/physical socket continuity. No thermal runtime or in-game validation.'}
    (OUT/'audit.json').write_text(json.dumps(report, indent=2)+'\n')
    return {'status': report['status'], 'models': len(models), 'assemblies': assemblies,
            'failure_count': len(failures), 'failures': failures[:30]}


if __name__ == '__main__':
    result = audit()
