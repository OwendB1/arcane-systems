"""Production main-model gates: grid, solids, support, UVs and real assemblies."""
import hashlib
import itertools
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

    def bounds(obj):
        points = [obj.matrix_world@v.co for v in obj.data.vertices]
        return [Vector([fn(v[i] for v in points) for i in range(3)]) for fn in (min, max)]

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
        if scene['thermal_phase'] == 'textures':
            if scene.get('thermal_detail_revision', 0) < 1 or scene.get('thermal_detail_revision') != scene.get('thermal_texture_revision'):
                fail(name, 'completed detail/texture revisions', scene.name)
            if any(o.type == 'FONT' for o in col.objects):
                fail(name, 'mesh-based export markings', scene.name)
            if any('1200 C' in o.get('thermal_text', '') for o in col.objects):
                fail(name, 'current hot-end temperature markings', scene.name)
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
                if obj.get('thermal_chamfer_m') is not None:
                    axis = obj.get('thermal_bore_axis')
                    faces = [f for f in mesh.polygons if axis is None or abs(f.normal[axis]) > .01]
                    if obj['thermal_chamfer_m'] > .003001 or obj.get('thermal_chamfer_segments', 0) > 1 or any(f.use_smooth for f in faces):
                        fail(name, 'narrow flat hard-surface chamfer', obj.name)
                if obj.get('thermal_faceted_hardware') and any(f.use_smooth for f in mesh.polygons):
                    fail(name, 'flat faceted hardware normals', obj.name)
                uv = mesh.uv_layers.active
                if not uv or any(not math.isfinite(v) for p in uv.data for v in p.uv):
                    fail(name, 'finite UV coverage', obj.name)
                original = bpy.data.objects.get(inherited) if inherited else None
                if inherited and (not original or original == obj or original.get('reactor_source_name')):
                    fail(name, 'original reactor provenance', obj.name)
                accepted_materials = original and list(mesh.materials) == list(original.data.materials)
                if not mesh.materials or (not accepted_materials and any(not mat or
                    (not mat.library and not (mat.name in ('ArcanePower_ClearChamber','ArcanePower_CoolantGlass') and mat.seut.technique == 'GLASS')
                     and not (mat.name in ('ThermalStatus', 'ThermalHot', 'ThermalCold') and mat.get('thermal_native_emissive')))
                    for mat in mesh.materials)):
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
            if obj.get('thermal_text'):
                # A backed marking can still face into its support and read
                # backwards through its own back face in the viewport.
                axis = obj.matrix_world.to_3x3()@Vector((0, 0, 1))
                nearest = tree(support).find_nearest(obj.matrix_world.translation)
                if nearest[1] is None or nearest[1].dot(axis) < .99:
                    fail(name, 'outward text orientation', obj.name)
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
            if scene.get('thermal_detail_revision', 0) >= 2 and obj.get('source_asset') and key == 'thermal_decal_support' and any(f.use_smooth for f in support.data.polygons):
                # Vertex-only projection checks miss decal chords buried
                # between the backing's curved/faceted surface vertices.
                obj.data.calc_loop_triangles()
                buried = False
                for tri in obj.data.loop_triangles:
                    a, b, c = [obj.matrix_world@obj.data.vertices[i].co for i in tri.vertices]
                    for point in ((a+b+c)/3, (a+b)/2, (b+c)/2, (c+a)/2):
                        hit, normal, _, _ = tree(support).find_nearest(point)
                        if (point-hit).dot(normal) < -.00005:
                            buried = True
                            break
                    if buried:
                        break
                if buried:
                    fail(name, 'projected decal clears curved backing between vertices', obj.name)
        ports = json.loads(col['ports'])
        if scene.get('thermal_visibility_revision'):
            glazed = [o for o in col.objects if o.get('thermal_pressure_glass')]
            stats['transparent_pressure_tubes'] = len(glazed)
            for obj in glazed:
                if not any(obj.data.materials[f.material_index].name in ('ArcanePower_ClearChamber','ArcanePower_CoolantGlass')
                           for f in obj.data.polygons):
                    fail(name, 'transparent pressure-wall faces', obj.name)
                if obj.get('thermal_external_pipe_style') and any(
                        obj.data.materials[f.material_index].seut.technique == 'GLASS' and
                        obj.data.materials[f.material_index].name != 'ArcanePower_CoolantGlass'
                        for f in obj.data.polygons):
                    fail(name, 'shared smoked external sight glass', obj.name)
            for obj in col.objects:
                if not obj.get('thermal_external_pipe_clamp'):
                    continue
                owner = bpy.data.objects.get(obj.get('thermal_seated_on', ''))
                if not owner or owner.name not in col.objects or not owner.get('thermal_external_pipe_style'):
                    fail(name, 'pipe clamp has pressure-wall backing', obj.name)
                if owner and owner.get('thermal_motion_group'):
                    fail(name, 'unobstructed telescoping pressure sleeves', obj.name)
            if name.startswith('Brayton train'):
                rig = json.loads((ROOT/'assets/thermal-rotor-runtime.json').read_text())
                stats['rotor_blades'] = {}
                stats['rotor_clearance_mm'] = {}
                for spec in rig['rotors']:
                    root = next((o for o in col.objects if o.type == 'EMPTY' and o.get('native_subpart') == spec['subpart']), None)
                    if not root or (root.location-Vector(spec['pivot_blender'])).length > 1e-6:
                        fail(name, 'native shaft pivot', spec['subpart'])
                        continue
                    label = spec['id']
                    blades = [o for o in col.objects if o.name.startswith(name+' / '+label+' blade row')]
                    stators = [o for o in col.objects if o.name.startswith(name+' / '+label+' stator vane row')]
                    stats['rotor_blades'][label] = sum(o.get('thermal_blade_count', 0) for o in blades)
                    if (len(blades) != spec['rotor_rows'] or any(o.parent != root or
                            o.get('thermal_blade_count') != spec['blades_per_row'] for o in blades)):
                        fail(name, 'dense solid blade rows on independent rotor', spec['subpart'])
                    if (len(stators) != spec['stator_rows'] or any(o.parent or o.get('native_subpart') or
                            o.get('thermal_blade_count') != spec['vanes_per_row'] for o in stators)):
                        fail(name, 'fixed interleaved stator rows', spec['subpart'])
                    ordered = sorted(blades+stators, key=lambda o: o['thermal_row_x'])
                    gaps = [bounds(b)[0].x-bounds(a)[1].x for a, b in zip(ordered, ordered[1:])]
                    if not gaps or min(gaps) < .010 or any(a.get('thermal_rotating') == b.get('thermal_rotating')
                            for a, b in zip(ordered, ordered[1:])):
                        fail(name, 'alternating stages with 10 mm axial swept clearance', spec['subpart'])
                    stats.setdefault('stage_axial_clearance_mm', {})[label] = round(min(gaps, default=0)*1000, 2)
                    casing = next(o for o in col.objects if o.name.startswith(name+' / '+label+' casing'))
                    radius = 1.85 if label == 'turbine' else 1.35
                    tip = max((math.hypot((o.matrix_world@v.co).y, (o.matrix_world@v.co).z-.45)
                               for o in blades for v in o.data.vertices), default=0)
                    clearance = (radius-casing['thermal_pressure_wall_m'])*math.cos(math.pi/48)-tip
                    stats['rotor_clearance_mm'][label] = round(clearance*1000, 2)
                    if clearance < .025:
                        fail(name, '25 mm swept blade clearance', spec['subpart'])
                    if not casing.get('thermal_hollow_casing') or not any(
                        casing.data.materials[f.material_index].name == 'ArcanePower_ClearChamber'
                        for f in casing.data.polygons):
                        fail(name, 'hollow glazed inspection casing', casing.name)
                flow = [o for o in col.objects if o.get('thermal_flow_end')]
                stats['end_plenum_channels'] = len(flow)
                if len(flow) != 4:
                    fail(name, 'four seated inlet/exhaust channels', scene.name)
                for pipe in flow:
                    label = pipe['thermal_flow_machine']
                    stages = [o for o in col.objects if o.get('thermal_blade_count') and
                              o.name.startswith(name+' / '+label+' ')]
                    x = pipe['thermal_nozzle_centre'][0]
                    front = pipe['thermal_flow_end'] == 'front'
                    margin = (min(bounds(o)[0].x for o in stages)-x-.245 if front else
                              x-.245-max(bounds(o)[1].x for o in stages))
                    if margin < .02:
                        fail(name, 'inlet before first row and exhaust after last row', pipe.name)
                    c, n = Vector(pipe['thermal_nozzle_centre']), Vector(pipe['thermal_nozzle_normal'])
                    up = Vector((1, 0, 0))
                    across = n.cross(up)
                    walls = [o for o in col.objects if o.name.startswith(name+' / '+label+' casing') or
                             o.name.startswith(name+' / '+label+' split casing band')]
                    samples = [c]+[c+.19*(up*math.cos(i*math.tau/8)+across*math.sin(i*math.tau/8)) for i in range(8)]
                    if any(tree(w).ray_cast(point+n*.30, -n, .65)[0] is not None
                           for point in samples for w in walls):
                        fail(name, 'open nozzle through pressure wall and reinforcement bands', pipe.name)
                    if any(tree(pipe).overlap(tree(o)) for o in col.objects if 'fitted cradle' in o.name):
                        fail(name, 'flow channels clear load cradles', pipe.name)
                if any(tree(a).overlap(tree(b)) for a, b in itertools.combinations(flow, 2)):
                    fail(name, 'separate pressure channels without intersections', scene.name)
        if scene.get('thermal_detail_revision', 0) >= 2:
            reference = json.loads((OUT/'tight-fit-before-interfaces.json').read_text())[name]
            if ports != reference['ports'] or list(cells) != reference['cells']:
                fail(name, 'preserved pre-refinement cells and sockets', scene.name)
            stats['max_chamfer_mm'] = max((o.get('thermal_chamfer_m', 0)*1000 for o in col.objects), default=0)
            stats['flat_hardware'] = sum(bool(o.get('thermal_faceted_hardware')) for o in col.objects)
            flow = [o for o in col.objects if o.type == 'MESH' and
                    (o.get('pipe_path') or ' connected ' in o.name)]
            webs = [o for o in col.objects if o.name.startswith(name+' / manifold skid bracket') or
                    o.name.startswith(name+' / flange load web')]
            for web in webs:
                if any(tree(web).overlap(tree(pipe)) for pipe in flow):
                    fail(name, 'load supports clear flowing channels', web.name)
            for port in ports:
                flange = next(o for o in col.objects if o.name.startswith(name+' / '+port['id']+' flange') and o.get('interface_type'))
                n, c = Vector(port['normal']), Vector(port['position'])
                front = max((flange.matrix_world@v.co-c).dot(n) for v in flange.data.vertices)
                if abs(front+.014) > .0001:
                    fail(name, '14 mm flange face setback', port['id'])
            if name.startswith('Brayton train'):
                casings = [next(o for o in col.objects if o.name.startswith(name+' / '+label+' casing'))
                           for label in ('compressor', 'turbine', 'generator')]
                gaps = [bounds(b)[0].x-bounds(a)[1].x for a, b in zip(casings, casings[1:])]
                stats['casing_gaps_mm'] = [round(v*1000, 2) for v in gaps]
                if any(v < .10 or v > .13 for v in gaps):
                    fail(name, 'packed train casing clearances', str(gaps))
            elif name.startswith('Recuperator'):
                plates = [o for o in col.objects if o.name.startswith(name+' / counterflow plate')]
                stats['exchange_plates'] = len(plates)
                if len(plates) != 84:
                    fail(name, 'dense plate bank', str(len(plates)))
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
        if name == 'Reactor housing' and scene.get('thermal_flow_revision'):
            pumps=[o for o in col.objects if o.get('thermal_coolant_pump')]
            if len(pumps)!=4:
                fail(name,'four seated chamber pump heads',str(len(pumps)))
            for pump in pumps:
                index=int(pump.name.rsplit(' ',1)[1])
                expected=Vector((4.78*math.cos(index*math.pi/2),4.78*math.sin(index*math.pi/2),-.915))
                low,high=bounds(pump)
                if (pump.matrix_world.translation-expected).length>1e-5 or low.z>-.80 or high.z<-.60:
                    fail(name,'pump encloses distributor junctions',pump.name)
            for obj in col.objects:
                if obj.get('thermal_flow_fixture') and any(obj.name.startswith(name+' / '+port['id']+' ') for port in ports):
                    if not obj.parent or obj.get('thermal_motion_group')!=obj.parent.name:
                        fail(name,'socket indicators retract with carriage',obj.name)
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
