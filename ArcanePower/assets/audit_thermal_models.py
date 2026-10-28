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


def audit_blast_shields():
    """Check the unified seal without changing the accepted sleeve envelope."""
    stages = json.loads((ROOT/'assets/vent.json').read_text())['stages']
    for stage in stages:
        name = stage['name']
        obj = bpy.data.objects[name+' / armored sleeve']
        assert bpy.data.objects.get(name+' / lower seal') is None, ('Duplicate inner seal', name)
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        try:
            assert all(e.is_manifold for e in bm.edges), ('Open shield', name)
            remaining = set(bm.verts)
            pending = [remaining.pop()]
            while pending:
                vertex = pending.pop()
                for edge in vertex.link_edges:
                    other = edge.other_vert(vertex)
                    if other in remaining:
                        remaining.remove(other)
                        pending.append(other)
            assert not remaining, ('Disconnected seal', name)
            inner, outer = stage['inner_radius'], stage['outer_radius']
            # Both authored rings have 128 sides; preserve their exact union.
            area = 64*math.sin(math.tau/128)
            volume = area*((outer**2-inner**2)*(.82-.045)+((outer+.018)**2-inner**2)*.055)
            assert abs(bm.calc_volume()-volume) < 1e-5, ('Changed sleeve envelope', name)
            assert min(v.co.xy.length for v in bm.verts) >= inner-1e-6, ('Narrowed shield bore', name)
        finally:
            bm.free()
    return {'status':'passed', 'continuous_seals':len(stages)}


def audit_internal_plumbing(col):
    """Prove retained pillar plumbing is untouched and chamber plumbing is removed."""
    import re
    checkpoint = ROOT/'assets/arcane-thermal-before-chamber-pipe-glass.blend'
    names = list(json.loads((OUT/'internal-pipes-baseline.json').read_text()))
    objects_before = set(bpy.data.objects)
    with bpy.data.libraries.load(str(checkpoint),link=False) as (_, loaded):
        loaded.objects = list(names)
    originals = dict(zip(names,loaded.objects))

    def geometry(obj):
        mesh = obj.data
        poses = []
        while obj is not None:
            poses.append((tuple(v for row in obj.matrix_basis for v in row),
                          tuple(v for row in obj.matrix_parent_inverse for v in row)))
            obj = obj.parent
        return (poses,[tuple(v.co) for v in mesh.vertices],
                [tuple(f.vertices) for f in mesh.polygons],
                [[tuple(v.uv) for v in layer.data] for layer in mesh.uv_layers])

    def material(obj, face):
        return re.sub(r'\.\d{3}$','',obj.data.materials[face.material_index].name)

    pillars, retained, removed = [], [], []
    try:
        for name, original in originals.items():
            assert original is not None, name
            chamber = all((original.matrix_world@v.co).xy.length < 5.5 for v in original.data.vertices)
            current = col.objects.get(name)
            if chamber:
                assert current is None, ('Retired chamber plumbing remains',name)
                removed.append(name)
                continue
            assert current is not None and geometry(current) == geometry(original), ('Pillar geometry/UV/pose changed',name)
            retained.append(name)
            if current.get('thermal_internal_coolant'): pillars.append(name)
            assert [material(current,f) for f in current.data.polygons] == [material(original,f) for f in original.data.polygons], ('Pillar material changed',name)
        assert len(removed) == 64 and len(pillars) == 8 and len(retained) == 48
        report = {'status':'passed','checkpoint':checkpoint.name,
                  'checkpoint_sha256':hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                  'pillar_geometry_transforms_uvs_and_materials_match':True,
                  'pillar_pipes':len(pillars),'pillar_objects':len(retained),
                  'chamber_pipe_bodies_removed':16,'chamber_pipe_clamps_removed':48,
                  'floor_vents':sum(o.get('native_subpart','').endswith('ChamberVent') for o in col.objects)}
        (OUT/'internal-pipes-preserved.json').write_text(json.dumps(report,indent=2)+'\n')
        return report
    finally:
        for obj in set(bpy.data.objects)-objects_before:
            bpy.data.objects.remove(obj,do_unlink=True)


def audit_chamber_vents(col):
    """Closed covers occlude the well; moving covers never intersect its fittings."""
    rig = runpy.run_path(str(ROOT/'assets/build_reactor_thermal_manifolds.py'))
    scene = M['scene_for']('Reactor housing')
    previous = bpy.context.scene
    deployment = scene['thermal_manifolds_deployment']

    def tree(objects):
        vertices, faces = [], []
        for obj in objects:
            offset = len(vertices)
            vertices.extend(obj.matrix_world@v.co for v in obj.data.vertices)
            faces.extend([offset+i for i in f.vertices] for f in obj.data.polygons)
        return BVHTree.FromPolygons(vertices, faces)

    samples = 0
    try:
        rig['pose'](0)
        bays = []
        for i, bay in enumerate(('LA','LB','RA','RB')):
            hinge = next(o for o in col.objects if o.get('native_subpart') == 'Thermal_'+bay+'_ChamberVent')
            lid = next(o for o in hinge.children if o.type == 'MESH')
            fixed = [o for o in col.objects if o.type == 'MESH' and o.get('thermal_floor_vent')
                     and 'floor vent '+bay+' ' in o.name and o != lid]
            closed = tree([lid]+fixed)
            angle = i*math.pi/2
            n = Vector((math.cos(angle),math.sin(angle),0));t = Vector((-n.y,n.x,0))
            # Include the old 10/30 mm side gaps, corners and new lip edges.
            xs = (-.445,-.435,-.430,-.425,-.420,0,.420,.425,.430,.435,.445)
            ys = (-.275,-.265,-.255,-.250,-.245,-.240,0,.240,.245,.250,.255,.265,.275)
            for x in xs:
                for y in ys:
                    origin = n*(4.45-y)+t*x+Vector((0,0,-1.16))
                    hit,_,_,_ = closed.ray_cast(origin,Vector((0,0,-1)),.12)
                    assert hit is not None, ('Unsealed chamber vent',bay,x,y)
                    samples += 1
            bays.append((bay,lid,tree(fixed)))
        for i in range(101):
            rig['pose'](i/100)
            for bay,lid,fixed in bays:
                assert not tree([lid]).overlap(fixed), ('Vent clips fixed fitting',bay,i/100)
        return {'closed_surface_samples':samples,'travel_samples':101*len(bays)}
    finally:
        rig['pose'](deployment)
        bpy.context.window.scene = previous
        bpy.context.view_layer.update()


def audit_pillar_side_covers(col):
    source = lambda o: o.get('reactor_source_name',o.name)
    assert not any(source(o).startswith('SEUT / Tech Panel') for o in col.objects), 'Buried legacy pillar decals remain'
    numbers = [o for o in col.objects if o.get('pillar_number')]
    assert len(numbers) == 8 and all(o.get('lod_keep') for o in numbers), 'Retain four pillar numbers and their backing plates in LODs'
    bodies = [o for o in col.objects if source(o).startswith('Reactor exterior / chamfered pillar jacket')]
    receivers = [o for o in col.objects if source(o).startswith('Reactor exterior / pillar inspection receiver')
                 and max(v.co.x for v in o.data.vertices)-min(v.co.x for v in o.data.vertices) < .5]
    assert len(receivers) == 8
    covers = [o for o in col.objects if source(o).startswith('Reactor exterior / pillar side cover')]
    assert len(covers) == 16
    def tree(obj):
        return BVHTree.FromPolygons([obj.matrix_world@v.co for v in obj.data.vertices],
                                   [list(f.vertices) for f in obj.data.polygons])
    for cover in covers:
        receiver = min(receivers,key=lambda o:(o.matrix_world.translation-cover.matrix_world.translation).length_squared)
        transform = receiver.matrix_world.inverted()@cover.matrix_world
        back = min((transform@v.co).z for v in cover.data.vertices)
        ledge = max(v.co.z for v in receiver.data.vertices if v.co.z < -.001)
        assert back-ledge >= .009, ('Receiver cuts through cover sidewall',cover.name,back-ledge)
        assert not tree(cover).overlap(tree(receiver)), ('Cover/receiver surface intersection',cover.name)
    for receiver in receivers:
        body = min(bodies,key=lambda o:(o.matrix_world.translation-receiver.matrix_world.translation).length_squared)
        to_body = body.matrix_world.inverted()@receiver.matrix_world
        to_receiver = to_body.inverted()
        for x,y in ((0,-1.48),(0,1.48),(-.21,-1.48),(.21,-1.48),(-.21,1.48),(.21,1.48),(-.21,0),(.21,0)):
            hit,point,_,_ = body.ray_cast(to_body@Vector((x,y,.02)),to_body.to_3x3()@Vector((0,0,-1)),distance=.3)
            assert hit and (to_receiver@point).z < -.09, ('Jacket overlaps side receiver',receiver.name,x,y)
    seats = [o for o in col.objects if source(o).startswith('Reactor exterior / side cover cross seat')]
    assert len(seats) == 8
    for seat in seats:
        assert max(abs(v.co.x) for v in seat.data.vertices) <= .15901, ('Coincident cross seat/receiver faces',seat.name)
        for cover in covers:
            assert not tree(cover).overlap(tree(seat)), ('Cover/cross-seat surface intersection',cover.name,seat.name)
    return {'recesses':len(receivers),'cross_seats':len(seats),'clear_cover_perimeters':len(covers)}


def audit_pillar_pipe_sockets(col):
    assert not any('pillar end yoke' in o.name for o in col.objects), 'Obsolete yokes remain'
    sockets = [o for o in col.objects if o.get('pillar_pipe_socket')]
    pipes = [o for o in col.objects if o.get('thermal_internal_coolant')]
    assert len(sockets) == 16 and len(pipes) == 8
    for pipe in pipes:
        pair = [o for o in sockets if o['pillar_pipe_socket'] == pipe.name]
        assert {o['pillar_pipe_end'] for o in pair} == {'lower','upper'}
        ends = json.loads(pipe['pipe_path'])
        for socket in pair:
            endpoint = Vector(ends[0 if socket['pillar_pipe_end'] == 'lower' else -1])
            assert (socket.matrix_world.translation-endpoint).length < .00001, ('Unseated socket',socket.name)
            assert min(v.co.xy.length for v in socket.data.vertices) >= .0999, ('Blocked socket bore',socket.name)
            assert socket.get('thermal_reactor_coupling'), ('Socket fit lost in LOD',socket.name)
            # The end flange must sit inside the existing foot/roof support.
            support_name = 'fitted curved pillar foot' if socket['pillar_pipe_end'] == 'lower' else 'fitted pillar roof seat'
            supports = [o for o in col.objects if support_name in o.name]
            axis = socket.matrix_world.to_3x3()@Vector((0,0,-1))
            origin = socket.matrix_world@Vector((.16,0,max(v.co.z for v in socket.data.vertices)+.01))
            assert any(o.ray_cast(o.matrix_world.inverted()@origin,o.matrix_world.to_3x3().inverted()@axis,distance=.4)[0]
                       for o in supports), ('Unsupported pipe socket',socket.name)
    return {'sockets':len(sockets),'unchanged_risers':len(pipes)}


def audit(names=None):
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
        if names is not None and name not in names:
            continue
        ident = C['subtype'](name)
        if ident not in bpy.data.scenes:
            fail(name, 'missing base', ident)
            continue
        scene, col = M['scene_for'](name), M['main_for'](name)
        bare = name in C['BARE_PIPES']
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
                exhaust = name == 'Atmospheric cooler' and obj.get('cooler_exhaust_part')
                coupling = name in ('PRIMARY / Reactor adapter', 'PRIMARY / Reactor adapter bare') and obj.get('thermal_reactor_coupling') == 2
                spindle = name == 'Pipe rotor head' and obj.get('pipe_rotor_spindle')
                # Only the receiving sleeve crosses the reactor socket plane;
                # cell size and the accepted placement collision stay unchanged.
                if not inherited and any(p[i] > half[i]+.001 or p[i] < (-3.06 if exhaust and i == 1 else C['PIPE_ROTOR_CUFF_BOTTOM']-.001 if spindle and i == 2 else -half[i]-.001-(.065 if coupling and i == 0 else 0))
                                         for p in points for i in range(3)):
                    fail(name, '2.5 m envelope', obj.name)
                mesh = obj.data
                if obj.get('thermal_pipe_end_revision') and {mesh.materials[f.material_index].name for f in mesh.polygons} != {'Metal_Dull','ArcanePower_CoolantGlass'}:
                    fail(name, 'short metal ends retain a glass sight length', obj.name)
                if obj.get('thermal_pipe_end_revision'):
                    bm = bmesh.new();bm.from_mesh(mesh)
                    # Every material must close independently: a watertight
                    # combined tube can still expose the metal wall via glass.
                    if any(len(e.link_faces)!=2 or e.link_faces[0].material_index!=e.link_faces[1].material_index for e in bm.edges):
                        fail(name, 'metal ferrules and glass have closed annular end faces', obj.name)
                    bm.free()
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
                    (not mat.library and not (mat.name in ('ArcanePower_ClearChamber','ArcanePower_CoolantGlass','ArcanePower_InternalCoolantGlass') and mat.seut.technique == 'GLASS')
                     and not (mat.name in ('ArcanePower_ArmatureCopper','ArcanePower_ArmatureCyan') and mat.get('thermal_armature_copper') and mat.seut.technique == 'MESH'
                              and all(mat.node_tree.nodes.get(n) and mat.node_tree.nodes[n].image for n in ('CM','NG','ADD')))
                     and not (mat.name == 'ArcanePower_ArmatureSteel' and mat.get('thermal_laminated_steel') and mat.seut.technique == 'MESH'
                              and all(mat.node_tree.nodes.get(n) and mat.node_tree.nodes[n].image for n in ('CM','NG')))
                     and not (mat.name in ('ThermalStatus', 'ThermalHot', 'ThermalCold', 'ThermalRadiatorHeatRoot', 'ThermalRadiatorHeatMid', 'ThermalRadiatorHeatTip') and mat.get('thermal_native_emissive')))
                    for mat in mesh.materials)):
                    fail(name, 'native SEUT material', obj.name)
                if obj.get('thermal_turbine_light'):
                    backing = bpy.data.objects.get(obj.get('thermal_seated_on',''))
                    if not backing or any(tree(backing).find_nearest(obj.matrix_world@v.co)[3] > .003
                                          for v in mesh.vertices[:4]):
                        fail(name, 'recessed turbine light seated on its rail or hatch', obj.name)
                native_terminal = obj.get('control_access') and obj.get('source_asset', '').startswith('SEUT Common.blend / Terminal')
                # Native terminals include open decal/screen surfaces. Their
                # authored mounting backings remain subject to the solid gate.
                if not obj.get('thermal_decal_support') and not native_terminal and (not inherited or obj.get('thermal_pocket_cut')):
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
        if name == 'Reactor housing':
            audit_internal_plumbing(col)
            terminals = [o for o in col.objects if o.type == 'EMPTY' and o.get('control_access')]
            if len(terminals) != 2:
                fail(name, 'two opposite control access panels', scene.name)
            for terminal in terminals:
                body = bpy.data.objects.get(terminal.get('highlight', ''))
                if body is None or not body.get('control_access') or '_section' not in body.name:
                    fail(name, 'native keypad highlight target', terminal.name)
                    continue
                if min(abs((body.matrix_world@v.co).x) for v in body.data.vertices) < 1.15:
                    fail(name, 'keypad clears conveyor frame by 15 cm', body.name)
            assert sum(bool(o.get('thermal_internal_coolant')) for o in col.objects) == 8
            vents = [o for o in col.objects if o.get('native_subpart','').endswith('ChamberVent')]
            if len(vents) != 4:
                fail(name,'four mode-controlled floor vents',scene.name)
            for check in (audit_chamber_vents,audit_pillar_side_covers,audit_pillar_pipe_sockets):
                try:
                    check(col)
                except AssertionError as error:
                    fail(name,check.__name__,str(error))
            for obj in col.objects:
                if obj.get('thermal_coolant_pump') or obj.name.startswith((name+' / injector ',name+' / pickup ',name+' / pump ')):
                    fail(name,'retired chamber fittings removed',obj.name)
        if name != 'Reactor housing' and scene.get('thermal_flow_revision'):
            walls = [o for o in col.objects if o.type=='MESH' and o.get('thermal_pressure_glass')]
            for port in ports:
                c,n,up = (Vector(port[k]) for k in ('position','normal','hot_axis'))
                across = up.cross(n)
                prefix = name+' / '+port['id']
                flange = next((o for o in col.objects if o.name.startswith(prefix+' flange') and o.get('interface_type')==port['type']), None)
                if not bare and flange is None:
                    fail(name, 'socket has its mounting flange', port['id'])
                for sign in (-1,1):
                    bore = c+up*(sign*.46)
                    seal = next(o for o in col.objects if o.name.startswith(prefix+' seated face seal '+str(sign)))
                    insert = next(o for o in col.objects if o.name.startswith(prefix+' pressure lip '+str(sign)))
                    seal_z = [(seal.matrix_world@v.co-bore).dot(n) for v in seal.data.vertices]
                    insert_z = [(insert.matrix_world@v.co-bore).dot(n) for v in insert.data.vertices]
                    receiving = bool(port.get('reactor_transition') and insert.get('thermal_reactor_coupling'))
                    if abs(min(seal_z)+.008)>1e-5 or abs(max(seal_z))>1e-5 or (not receiving and max(insert_z)>min(seal_z)+1e-5):
                        fail(name,'face seal abuts insert without overlap',seal.name)
                    if receiving:
                        if abs(min(insert_z)+.055)>1e-5 or abs(max(insert_z)-.065)>1e-5 or tree(insert).overlap(tree(seal)):
                            fail(name,'receiving lip overlaps nose only, with recessed gasket clearance',insert.name)
                        for axial, minimum in ((-.004, .311), (.030, .281)):
                            for j in range(64):
                                radial = up*math.cos(j*math.tau/64)+across*math.sin(j*math.tau/64)
                                hit = tree(insert).ray_cast(bore+n*axial,radial,.5)[0]
                                if hit is None or (hit-bore-n*axial).length < minimum:
                                    fail(name,'sleeve clears gasket and R273 reactor nose around full bore',insert.name)
                                    break
                    for j in range(8) if flange else ():
                        radial = (up*math.cos(j*math.tau/8)+across*math.sin(j*math.tau/8))*.378
                        hit = tree(flange).ray_cast(bore+radial+n*.05,-n,.20)[0]
                        if hit is None or abs((hit-bore).dot(n)+.055)>1e-4:
                            fail(name,'pressure insert has recessed counterbore shoulder',flange.name)
                            break
                    for wall in walls:
                        if wall.get('thermal_pipe_end_revision'):
                            for depth, material in ((.11,'Metal_Dull'),(.20,'ArcanePower_CoolantGlass')):
                                for j in range(8):
                                    # Sample face interiors, clear of axial rings
                                    # and cylinder edges that a BVH ray can graze.
                                    angle = (j+.37)*math.tau/8
                                    radial = up*math.cos(angle)+across*math.sin(angle)
                                    centre = bore-n*depth
                                    inner = tree(wall).ray_cast(centre,radial,.36)
                                    if inner[0] is None:continue
                                    outer = tree(wall).ray_cast(centre+radial*.40,-radial,.20)
                                    if outer[0] is None or any(wall.data.materials[wall.data.polygons[wall.data.loop_triangles[hit[2]].polygon_index].material_index].name != material for hit in (inner,outer)):
                                        fail(name,'short metal ferrule has matching inside/outside material',wall.name)
                                        break
                                    if depth == .11 and outer[0] is not None:
                                        # Shoot through the wall thickness from
                                        # the sight length toward its ferrule.
                                        metal_faces=[list(t.vertices) for t in wall.data.loop_triangles if wall.data.materials[wall.data.polygons[t.polygon_index].material_index].name=='Metal_Dull']
                                        metal_tree=BVHTree.FromPolygons([wall.matrix_world@v.co for v in wall.data.vertices],metal_faces,all_triangles=True)
                                        shoulder=(inner[0]+outer[0])*.5-n*.09
                                        hit=metal_tree.ray_cast(shoulder,n,.09)
                                        if hit[0] is None or abs((hit[0]-bore).dot(n)+.15)>1e-4 or hit[1].dot(-n)<.99:
                                            fail(name,'metal shoulder faces glass across full wall thickness',wall.name)
                                        if metal_tree.ray_cast(bore-n*.20,n,.09)[0] is not None:
                                            fail(name,'annular shoulder keeps central bore open',wall.name)
                        for vertex in wall.data.vertices:
                            delta = wall.matrix_world@vertex.co-bore
                            axial = delta.dot(n)
                            if -.0559 < axial < .002 and (delta-n*axial).length < .361:
                                fail(name,'pipe end clears seal and pressure insert',wall.name)
                                break
        if scene.get('thermal_visibility_revision'):
            glazed = [o for o in col.objects if o.get('thermal_pressure_glass')]
            stats['transparent_pressure_tubes'] = len(glazed)
            for obj in glazed:
                if not any(obj.data.materials[f.material_index].name in ('ArcanePower_ClearChamber','ArcanePower_CoolantGlass','ArcanePower_InternalCoolantGlass')
                           for f in obj.data.polygons):
                    fail(name, 'transparent pressure-wall faces', obj.name)
                if obj.get('thermal_external_pipe_style') and any(
                        obj.data.materials[f.material_index].seut.technique == 'GLASS' and
                        obj.data.materials[f.material_index].name != 'ArcanePower_CoolantGlass'
                        for f in obj.data.polygons):
                    fail(name, 'shared smoked external sight glass', obj.name)
                # Test the complete wall, including the underside and inner
                # surface. A single glass polygon cannot establish coverage.
                if obj.get('pipe_path') and not obj.get('thermal_internal_coolant'):
                    path = list(map(Vector, json.loads(obj['pipe_path'])))
                    margin = .40
                    if any(min((obj.matrix_world@f.center-end).length for end in (path[0], path[-1])) > margin
                           and obj.data.materials[f.material_index].name != 'ArcanePower_CoolantGlass'
                           for f in obj.data.polygons):
                        fail(name, 'full circumference pressure glass', obj.name)
                elif col.get('pipe_shape') in ('Tee', 'Cross'):
                    z = .46 if 'connected H ' in obj.name else -.46
                    ends = [Vector((x,y,z)) for x,y in [(-1.25,0),(1.25,0),(0,1.25)]
                            + ([(0,-1.25)] if col['pipe_shape']=='Cross' else [])]
                    if any(min((obj.matrix_world@f.center-end).length for end in ends) > .40
                           and obj.data.materials[f.material_index].name != 'ArcanePower_CoolantGlass'
                           for f in obj.data.polygons):
                        fail(name, 'full circumference branch glass', obj.name)
            for obj in col.objects:
                if not obj.get('thermal_external_pipe_clamp'):
                    continue
                owner = bpy.data.objects.get(obj.get('thermal_seated_on', ''))
                if not owner or owner.name not in col.objects or not owner.get('thermal_external_pipe_style'):
                    fail(name, 'pipe clamp has pressure-wall backing', obj.name)
                if owner and owner.get('thermal_motion_group'):
                    fail(name, 'unobstructed telescoping pressure sleeves', obj.name)
            if name.startswith('Brayton train'):
                compressor=next(o for o in col.objects if o.name.startswith(name+' / compressor tapered rotor drum'))
                turbine=next(o for o in col.objects if o.name.startswith(name+' / turbine tapered rotor drum'))
                engagement=bounds(compressor)[1].x-bounds(turbine)[0].x
                if abs(engagement-.020)>.0001 or not turbine.get('thermal_rotor_joint_revision'):
                    fail(name,'closed compressor/turbine rotor joint with 20 mm engagement',turbine.name)
                stats['rotor_joint_engagement_mm']=round(engagement*1000,2)
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
                    if (len(blades) != spec['rotor_rows']+spec.get('transition_rotor_rows',0) or any(o.parent != root or
                            o.get('thermal_blade_count') != spec['blades_per_row'] for o in blades)):
                        fail(name, 'dense solid blade rows on independent rotor', spec['subpart'])
                    if (len(stators) != spec['stator_rows']+spec.get('transition_stator_rows',0) or any(o.parent or o.get('native_subpart') or
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
                    def swept_clearance(point):
                        r, sides = radius, 48
                        if label == 'compressor':
                            start, end = C['TRAIN_CENTRES']['compressor']+1.21, C['TRAIN_CENTRES']['turbine']-1.575
                            if point.x > start:
                                r = 1.35+.50*min(1,(point.x-start)/(end-start)); sides = 96
                        return (r-casing['thermal_pressure_wall_m'])*math.cos(math.pi/sides)-math.hypot(point.y,point.z-C['TRAIN_SHAFT_Z'])
                    clearance = min((swept_clearance(o.matrix_world@v.co) for o in blades for v in o.data.vertices),default=0)
                    stats['rotor_clearance_mm'][label] = round(clearance*1000, 2)
                    if clearance < .025:
                        fail(name, '25 mm swept blade clearance', spec['subpart'])
                    if not casing.get('thermal_hollow_casing') or not any(
                        casing.data.materials[f.material_index].name == 'ArcanePower_ClearChamber'
                        for f in casing.data.polygons):
                        fail(name, 'hollow glazed inspection casing', casing.name)
                flow = [o for o in col.objects if o.get('thermal_flow_end')]
                stats['end_plenum_channels'] = len(flow)
                if len(flow) != 2:
                    fail(name, 'front compressor inlet and rear turbine outlet', scene.name)
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
                channels = [o for o in col.objects if o.get('thermal_gas_channel')]
                if len(channels) != 2 or any(o.get('thermal_internal_flow') for o in channels):
                    fail(name, 'two external socket channels; direct internal casing transition', scene.name)
                for pipe in channels:
                    if any(tree(pipe).overlap(tree(o)) for o in col.objects if 'fitted cradle' in o.name):
                        fail(name, 'flow channels clear load cradles', pipe.name)
                    walls = [o for o in col.objects if o.type == 'MESH' and any(
                        part in o.name for part in (' casing', 'split casing band',
                        'stepped end flange', 'inspection window', 'split joint'))]
                    for wall in walls:
                        if tree(pipe).overlap(tree(wall)):
                            fail(name, 'flow channels clear pressure casing and reinforcement', pipe.name+' / '+wall.name)
                if any(tree(a).overlap(tree(b)) for a, b in itertools.combinations(channels, 2)):
                    fail(name, 'separate pressure channels without intersections', scene.name)
        if scene.get('thermal_detail_revision', 0) >= 2:
            reference = json.loads((OUT/'tight-fit-before-interfaces.json').read_text())[C['BARE_PIPES'].get(name, name).replace(' mirrored', '')]
            if name.startswith('Brayton train'):
                if tuple(cells) != (5, 2, 2) or ports != C['train_ports'](name):
                    fail(name, 'compact train envelope and standard duplex sockets', scene.name)
            elif ports != reference['ports'] or list(cells) != reference['cells']:
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
            for port in ports if not bare else ():
                flange = next(o for o in col.objects if o.name.startswith(name+' / '+port['id']+' flange') and o.get('interface_type'))
                n, c = Vector(port['normal']), Vector(port['position'])
                front = max((flange.matrix_world@v.co-c).dot(n) for v in flange.data.vertices)
                if abs(front+.014) > .0001:
                    fail(name, '14 mm flange face setback', port['id'])
            if bare:
                base = C['BARE_PIPES'][name]
                if ports != json.loads(M['main_for'](base)['ports']):
                    fail(name, 'bare and framed sockets are interchangeable', scene.name)
                if any(o.get('interface_type') or o.get('thermal_pipe_casing') or any(t in o.name.lower() for t in
                       ('pipe cage', 'pipe base mounting shoe', 'flange load web', 'status bezel', 'status lens'))
                       for o in col.objects):
                    fail(name, 'pipe-only silhouette without plate or cage hardware', scene.name)
            if name.startswith('Brayton train'):
                cabinet=next(o for o in col.objects if o.name.startswith(name+' / generator switchgear'))
                low,high=bounds(cabinet)
                if max(abs((high-low)[i]-v*.7) for i,v in enumerate((1.45,3.1,3.1))) > .0001:
                    fail(name,'electrical cabinet reduced 30 percent on every axis',cabinet.name)
                deck=next(o for o in col.objects if o.name.startswith(name+' / equipment foundation'))
                if abs(low.z-bounds(deck)[1].z) > .0001 or any('switchgear pedestal' in o.name for o in col.objects):
                    fail(name,'cabinet sits directly on foundation without pedestals',cabinet.name)
                if not deck.get('thermal_refined_foundation'):
                    fail(name,'tapered foundation perimeter',deck.name)
                if any(' / load-bearing skid' in o.name or ' / transverse skid' in o.name for o in col.objects):
                    fail(name,'continuous foundation replaces underslung rails',deck.name)
                for x in (-5.8,0,5.8):
                    for y in (-2.0,0,2.0):
                        hit=tree(deck).ray_cast(Vector((x,y,-2.6)),Vector((0,0,1)),.55)
                        if hit[0] is None or abs(hit[0].z+2.5)>.0001:
                            fail(name,'foundation underside seats flat at the block bottom',deck.name)
                cable=next(o for o in col.objects if ' / compressor supply conduit' in o.name)
                motor=next(o for o in col.objects if ' / electric compressor motor' in o.name)
                terminal=next(o for o in col.objects if ' / compressor motor terminal' in o.name)
                motor_low,motor_high=bounds(motor);terminal_low,terminal_high=bounds(terminal)
                if min(terminal_low.x-motor_low.x,motor_high.x-terminal_high.x)<.0119:
                    fail(name,'motor terminal ends recessed from round motor caps',terminal.name)
                path=list(map(Vector,json.loads(cable['pipe_path'])))
                if max((b-a).angle(c-b) for a,b,c in zip(path,path[1:],path[2:])) > math.radians(25):
                    fail(name,'cable uses gradual tangent bends without pinched corners',cable.name)
                if bounds(cable)[0].z < bounds(deck)[1].z+.02:
                    fail(name,'cable clears foundation surface',cable.name)
                cradles=[o for o in col.objects if o.get('thermal_strut_revision')]
                compact=[o for o in cradles if ' / compressor fitted cradle' in o.name]
                flared=[o for o in cradles if o not in compact]
                fittings=[o for o in col.objects if o.get('thermal_strut_fitting')]
                if len(compact)!=2 or len(flared)!=4 or sum(bool(o.get('thermal_cable_bulkhead')) for o in fittings)!=12 or sum(bool(o.get('thermal_coolant_bulkhead')) for o in fittings)!=2:
                    fail(name,'two compact saddles, four flared supports, four cable bulkheads and two coolant liners',scene.name)
                cold=next(o for o in col.objects if o.get('thermal_gas_channel') and 'cold rear return' in o.name)
                obstacles=[o for o in col.objects if o.get('thermal_gas_channel') or o.get('thermal_nozzle_collar')
                           or o.get('thermal_cable_bend_radius') or 'manifold' in o.name.lower() and o.type=='MESH']
                for support in compact:
                    lo,hi=bounds(support)
                    if hi.z > -1.1599 or max(abs(lo.y),abs(hi.y)) > 1.1301:
                        fail(name,'compressor saddles stay low and tucked under the drum',support.name)
                    if any(tree(support).overlap(tree(o)) for o in obstacles):
                        fail(name,'compact compressor saddles clear pipes, cable and manifold plate',support.name)
                for fitting in fittings:
                    if bpy.data.objects.get(fitting['thermal_strut_fitting']) not in flared:
                        fail(name,'bulkhead socket belongs to an existing strut',fitting.name)
                    if any(tree(fitting).overlap(tree(pipe)) for pipe in (cold,cable)):
                        fail(name,'bulkhead bore clears its pipe or cable',fitting.name)
                # Test actual solids all the way around each passage at both
                # faces and mid-depth. An open notch cannot pass this test.
                for support in flared:
                    low_s,high_s=bounds(support)
                    for pipe,minimum,maximum in ((cable,.105,.125),(cold,.325,.36)):
                        route=list(map(Vector,json.loads(pipe['pipe_path'])))
                        for x in (low_s.x+.04,(low_s.x+high_s.x)/2,high_s.x-.04):
                            centre=next((a+(b-a)*((x-a.x)/(b.x-a.x)) for a,b in zip(route,route[1:])
                                if abs(b.x-a.x)>1e-6 and min(a.x,b.x)<=x<=max(a.x,b.x)),None)
                            if centre is None:continue
                            for i in range(32):
                                direction=Vector((0,math.cos(i*math.tau/32),math.sin(i*math.tau/32)))
                                hit=tree(support).ray_cast(centre,direction,maximum)
                                if hit[0] is None or hit[3]<minimum:
                                    fail(name,'closed strut bore encircles the complete pipe or cable',support.name)
                                    break
                stats['compact_compressor_saddles']=len(compact)
                stats['flared_struts']=len(flared)
                stats['cable_bulkheads']=sum('barrel' in o.name for o in fittings)
                generator=next(o for o in col.objects if o.name.startswith(name+' / generator casing'))
                rear=bounds(generator)[1].x
                if abs(rear-C['TRAIN_GENERATOR_REAR']) > .0001 or rear < low.x+.04:
                    fail(name,'generator casing extends directly into cabinet',generator.name)
                hood=next(o for o in col.objects if o.get('thermal_coupling_hood'))
                hlow,hhigh=bounds(hood)
                if hhigh.x < low.x+.02 or hlow.x > rear:
                    fail(name,'half-round cover seats into cabinet and extended generator',hood.name)
                for dx in (.04,.12,.20):
                    for i in range(16):
                        angle=i*math.tau/16
                        point=Vector((rear+dx,.22*math.cos(angle),C['TRAIN_SHAFT_Z']+.22*math.sin(angle)))
                        hit,normal,_,_=tree(hood).find_nearest(point)
                        if (point-hit).dot(normal) >= 0:
                            fail(name,'rear shaft fully enclosed by half-round cover',hood.name)
                            break
                stretch=C['TRAIN_GENERATOR_STRETCH']
                rear_cradle=max((o for o in col.objects if o.name.startswith(name+' / generator fitted cradle')),
                                key=lambda o: bounds(o)[1].x)
                if abs(sum(v.x for v in bounds(rear_cradle))/2-C['generator_x'](C['TRAIN_CENTRES']['generator']+.66)) > .0001:
                    fail(name,'rear support follows longer generator',rear_cradle.name)
                jackets=[o for o in col.objects if o.get('thermal_upgrade_jacket')]
                if len(jackets) != (5 if name.endswith(' upgraded') else 0):
                    fail(name,'distinct upgraded casing jackets and lower cooling fins',scene.name)
                if any('upgraded stator fin' in o.name or 'high temperature turbine cassette' in o.name for o in col.objects):
                    fail(name,'no legacy upgrade bars over inspection windows',scene.name)
                casings = [next(o for o in col.objects if o.name.startswith(name+' / '+label+' casing'))
                           for label in ('compressor', 'turbine', 'generator')]
                gaps = [bounds(b)[0].x-bounds(a)[1].x for a, b in zip(casings, casings[1:])]
                stats['casing_gaps_mm'] = [round(v*1000, 2) for v in gaps]
                if abs(gaps[0]-2.615) > .0001 or not .10 <= gaps[1] <= .13:
                    fail(name, 'compressor transition length and generator clearance', str(gaps))
                taper = next(o for o in col.objects if o.get('thermal_compressor_transition'))
                low, high = bounds(taper)
                if abs(low.x-bounds(casings[0])[1].x) > .0001 or abs(high.x-bounds(casings[1])[0].x) > .0001:
                    fail(name, 'compressor taper must join both pressure casings', taper.name)
                radii = [math.hypot((taper.matrix_world@v.co).y,(taper.matrix_world@v.co).z-C['TRAIN_SHAFT_Z']) for v in taper.data.vertices]
                if abs(max(radii)-1.85) > .0001:
                    fail(name, 'turbine outside radius stays 1.85 m', taper.name)
                if not any(taper.data.materials[f.material_index].name == 'ArcanePower_ClearChamber' for f in taper.data.polygons):
                    fail(name, 'glazed compressor transition', taper.name)
                generator = casings[2]
                if not generator.get('thermal_hollow_casing') or not any(generator.data.materials[f.material_index].name == 'ArcanePower_ClearChamber' for f in generator.data.polygons):
                    fail(name, 'glazed generator casing', generator.name)
                a,b,*_ = generator['thermal_window_angles_deg']
                factor = (math.cos(math.radians(a))-math.cos(math.radians(b)))/(math.cos(math.radians(22.5))-math.cos(math.radians(82.5)))
                if abs(factor-.8) > 1e-5 or abs(generator['thermal_window_x'][1]-generator['thermal_window_x'][0]-1.58*stretch) > 1e-5:
                    fail(name, 'generator window retains reduced height and extends with casing', generator.name)
                window_side = 1 if 'mirrored' in name else -1
                if not generator.get('thermal_single_sided_window') or any(
                        generator.data.materials[f.material_index].name == 'ArcanePower_ClearChamber'
                        and (generator.matrix_world@f.center).y*window_side < 0
                        for f in generator.data.polygons):
                    fail(name, 'opaque far wall behind generator inspection bay', generator.name)
                join = next(o for o in col.objects if o.get('thermal_generator_transition'))
                low, high = bounds(join)
                if abs(low.x-bounds(casings[1])[1].x) > .0001 or abs(high.x-bounds(generator)[0].x) > .0001:
                    fail(name, 'closed turbine-generator housing joint', join.name)
                root = next(o for o in col.objects if o.type == 'EMPTY' and o.get('native_subpart') == 'Thermal_TurbineRotor')
                windings = [o for o in col.objects if o.get('thermal_generator_winding')]
                armature = [o for o in col.objects if o.get('thermal_generator_armature')]
                winding_material = 'ArcanePower_ArmatureCyan' if name.endswith(' upgraded') else 'ArcanePower_ArmatureCopper'
                if (len(windings) != 96 or {(o.get('thermal_generator_pole'),o.get('thermal_winding_layer')) for o in windings} != set(itertools.product(range(24),range(4)))
                        or any(o.get('thermal_winding_turns') != 10 or o.parent != root or o.data.materials[0].name != winding_material for o in windings)):
                    fail(name, '24 turbine-driven poles with four layers of ten copper turns', generator.name)
                poles = [o for o in armature if 'thermal_generator_pole' in o and not o.get('thermal_generator_winding')]
                if any(abs(bounds(o)[1].x-bounds(o)[0].x-1.06*stretch) > .0001 for o in poles):
                    fail(name,'armature poles extend with the longer generator',generator.name)
                if len(poles) != 24 or any(tree(a).overlap(tree(b)) for a,b in itertools.combinations(poles+windings,2)):
                    fail(name, 'flanged generator pole cores and windings have separate volumes', generator.name)
                radius = max(math.hypot((o.matrix_world@v.co).y,(o.matrix_world@v.co).z-C['TRAIN_SHAFT_Z']) for o in armature for v in o.data.vertices)
                if (1.62-.12)*math.cos(math.pi/48)-radius < .05:
                    fail(name, 'generator armature swept casing clearance', generator.name)
                magnets = [o for o in col.objects if o.get('thermal_generator_magnet')]
                if len(magnets) != 27 or any(o.parent or o.get('native_subpart') or o.data.materials[0].name != 'Metal_Shiny' for o in magnets):
                    fail(name, '27 shiny stationary permanent magnets on generator casing', generator.name)
                for magnet in magnets:
                    points = [magnet.matrix_world@v.co for v in magnet.data.vertices]
                    angles = sorted(math.atan2(p.y,p.z-C['TRAIN_SHAFT_Z']) % math.tau for p in points)
                    gap = max(b-a for a,b in zip(angles,angles[1:]+[angles[0]+math.tau]))
                    if abs(math.degrees(math.tau-gap)-14) > .01:
                        fail(name, 'one-degree circumferential magnet gaps', magnet.name)
                    length = max(p.x for p in points)-min(p.x for p in points)
                    if min(abs(length-.32*stretch),abs(length-1.56*stretch)) > .001:
                        fail(name, 'extended inspection-side magnet end tiles', magnet.name)
                    centre = sum(points,Vector())/len(points)
                    angle = math.degrees(math.atan2(centre.y*window_side,centre.z-C['TRAIN_SHAFT_Z']))
                    if abs(angle-30) < .01 and abs(length-1.56*stretch) > .001:
                        fail(name, 'continuous uppermost visible magnet bar', magnet.name)
                if 1.31*math.cos(math.radians(.875))-radius < .05:
                    fail(name, '50 mm generator rotor-magnet swept air gap', generator.name)
                stats['generator_windings'] = sum(o['thermal_winding_turns'] for o in windings)
                stats['generator_magnet_air_gap_mm'] = round((1.31*math.cos(math.radians(.875))-radius)*1000,2)
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
            # Radiator-only edge unions sit at the edge midpoint, including
            # between two occupied cells. Standard rear pipes stay cell-centred.
            edge_union = port.get('hull_only', False)
            if edge_union and not (name == 'Hull radiator' and any(
                p.get('hull_only') and p['id'] == port['id']
                and Vector(p['position']) == pos and Vector(p['normal']) == n
                and Vector(p['hot_axis']) == up for p in C['HULL_RADIATOR_PORTS'])):
                fail(name, 'radiator edge union contract', port['id'])
            for i in (() if edge_union else range(3)):
                if i != axis:
                    offset = port.get('cell_offset', [0, 0, 0])
                    if offset != [0, 0, 0] and (C['BARE_PIPES'].get(name, name) not in ('Reactor housing', 'PRIMARY / Reactor adapter') or offset != [0, 0, .17]):
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
        if name == 'Reactor housing':
            fittings = {o.get('reactor_source_name'): o for o in col.objects if o.type == 'MESH'}
            cap = fittings['Cap central service hatch.001']
            seat = fittings['AP vent / hatch seat']
            housing = fittings['Circular upper armored housing.001']
            clearance = min(tree(seat).find_nearest(cap.matrix_world @ v.co)[3]
                            for v in cap.data.vertices)
            if tree(cap).overlap(tree(seat)) or not .009 <= clearance <= .011:
                fail(name, 'central hatch cap clears seat by 10 mm', cap.name)
            for i in range(128):
                angle = i*math.tau/128
                origin = Vector((2.045*math.cos(angle), 2.045*math.sin(angle), 3.8))
                if tree(housing).ray_cast(origin, Vector((0, 0, -1)), .30)[0] is None:
                    fail(name, 'central hatch seam has continuous housing backing', str(i))
            stats['hatch_cap_seat_clearance_mm'] = round(clearance*1000, 3)
            for radius in (2.10, 2.25, 2.40):
                for i in range(32):
                    angle = (i+.37)*math.tau/32
                    origin = Vector((radius*math.cos(angle), radius*math.sin(angle), 3.85))
                    cap_hit = tree(cap).ray_cast(origin, Vector((0, 0, -1)), .4)[0]
                    backing_hit = tree(housing).ray_cast(origin, Vector((0, 0, -1)), .4)[0]
                    if cap_hit is None or backing_hit is None or cap_hit.z-backing_hit.z < .01:
                        fail(name, 'roof cap has recessed backing safe for native vertex packing', str((radius, i)))
        if name == 'Reactor housing' and scene.get('thermal_flow_revision'):
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
            if not C['circuits_match'](a['type'], b['type']) or Vector(a['normal']).dot(Vector(b['normal'])) > -.9999 or Vector(a['hot_axis']).dot(Vector(b['hot_axis'])) < .9999:
                fail(scene.name, 'circuit or H/C reversal', an+' / '+bn)
        assemblies[scene.name] = {'instances': len(instances), 'occupied_cells': len(occupied), 'mated_sockets': len(socket_map)}
    # Stacked radiator couplings meet at cell boundaries, centred in equal
    # frame gaps. Inspect real vertices so later panel edits cannot shift them.
    stack = {}
    for name, half_height in (('Space radiator', 1.25), ('Radiator panel', 2.5)):
        bpy.context.window.scene = M['scene_for'](name)
        bpy.context.view_layer.update()
        col = M['main_for'](name)
        for label, key in (() if name == 'Space radiator' else (('radiator top rail', 'top'), ('panel carrier beam', 'bottom'))):
            obj = next(o for o in col.objects if o.name.startswith(name+' / '+label))
            points = [obj.matrix_world@v.co for v in obj.data.vertices]
            stack[name, key] = max(p.z for p in points) if key == 'top' else min(p.z for p in points)
        if name == 'Radiator panel' and abs(half_height-stack[name, 'top']-.125) > .00001:
            fail(name, 'stack connector not centred above top rail', str(stack[name, 'top']))
        if name == 'Radiator panel':
            if abs(stack[name, 'bottom']+half_height-.125) > .00001:
                fail(name, 'stack connector not centred below carrier', str(stack[name, 'bottom']))
            for obj in col.objects:
                if ' / fixed axial dock' not in obj.name: continue
                zs = [(obj.matrix_world@v.co).z for v in obj.data.vertices]
                clearance = min(zs)-stack[name, 'top'] if min(zs)>0 else stack[name, 'bottom']-max(zs)
                if clearance < .03499: fail(name, 'axial collar overlaps frame rail', obj.name)
        for collar in col.objects:
            if not any(label in collar.name for label in (' / fixed axial dock', ' / stack axis collar')):
                continue
            points = [collar.matrix_world@v.co for v in collar.data.vertices]
            sign = 1 if sum(p.z for p in points)>0 else -1
            origin = Vector((0, 0, sign*(half_height+.01)))
            inverse = collar.matrix_world.inverted()
            hit = collar.ray_cast(inverse@origin, inverse.to_3x3()@Vector((0, 0, -sign)), distance=.12)[0]
            if hit:
                fail(name, 'axial collar must be annular, not a coplanar solid cap', collar.name)
            shaft = next(o for o in col.objects if
                         any(label in o.name for label in (' / rotating axial coupling', ' / stack axis coupling'))
                         and sign*sum((o.matrix_world@v.co).z for v in o.data.vertices)>0)
            shaft_points = [shaft.matrix_world@v.co for v in shaft.data.vertices]
            recess = half_height-max(sign*p.z for p in shaft_points)
            if not .0059 <= recess <= .0061:
                fail(name, 'shaft end needs a separate 6 mm recessed cap', shaft.name)
            inverse = shaft.matrix_world.inverted()
            if not shaft.ray_cast(inverse@origin, inverse.to_3x3()@Vector((0, 0, -sign)), distance=.03)[0]:
                fail(name, 'axial end must remain closed behind the collar', shaft.name)
    # The hull fills its cells; only the requested exhaust hardware projects.
    bpy.context.window.scene = M['scene_for']('Atmospheric cooler')
    bpy.context.view_layer.update()
    cooler = M['main_for']('Atmospheric cooler')
    face = next(o for o in cooler.objects if ' / flush exhaust bulkhead' in o.name)
    low, high = bounds(face)
    if max(abs(low.x+3.75),abs(high.x-3.75),abs(low.z+3.75),abs(high.z-3.75),abs(low.y+2.5)) > .00001:
        fail('Atmospheric cooler','flush full-cell hull perimeter',face.name)
    samples=json.loads(cooler['air_exhaust_samples'])
    fans=[o for o in cooler.objects if o.type=='MESH' and o.get('cooler_exhaust_part')]
    front=min(bounds(o)[0].y for o in fans)
    if len(samples)!=18 or any(p[1]>front-.02 for p in samples):
        fail('Atmospheric cooler','exhaust probes must clear physical fan guards',str(samples))
    for x in (-1.68,1.68):
        if sum(math.hypot(p[0]-x,p[2])<1.1 for p in samples)!=9:
            fail('Atmospheric cooler','nine probes cover each fan aperture',str(x))
    port=json.loads(cooler['ports'])
    if len(port)!=1 or port[0]['position']!=[0,2.5,0] or port[0]['normal']!=[0,1,0]:
        fail('Atmospheric cooler','rear manifold on grid boundary',str(port))
    if names is None or 'Reactor housing' in names:
        try:
            audit_blast_shields()
        except AssertionError as error:
            fail('Reactor housing', 'continuous blast-shield seals', str(error))
    try:
        runpy.run_path(str(ROOT/'assets/build_tracking_radiator.py'))['audit_base']()
    except AssertionError as error:
        fail('Space radiator', 'sealed base joints and emissives', str(error))
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
