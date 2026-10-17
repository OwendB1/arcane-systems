"""Main-mesh hardware and native SE texture refinement for the thermal family.

Run geometry(name), inspect, then textures(name) in the production live file.
Ports, cell sizes and the accepted reactor variant are preserved. Rebuilding a
refined base replays these stages through build_thermal_models.rebuild_base().
"""
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
ASSETS = Path.home()/'.local/share/blender-se1-setup/assets/Models/Decals'
COLOURS = {'PRIMARY': 'PaintedMetal_Yellow', 'CO2_HP': 'BlueFrostedMetal',
           'CO2_LP': 'PaintedMetal_Clean'}
REVISION = 2


def parts(name):
    assert name != 'Reactor housing', 'Keep the accepted reactor on its own builder'
    return M['Parts'](name, existing=True)


def named(p, label):
    return [o for o in p.col.objects if o.name.startswith(p.name+' / '+label)
            and not o.get('thermal_support')]


def centre(obj):
    points = [obj.matrix_world@v.co for v in obj.data.vertices]
    return Vector([(min(v[i] for v in points)+max(v[i] for v in points))/2 for i in range(3)])


def move(p, roots, delta):
    """Move fitted parts together with their supported hardware and markings."""
    selected = set(roots)
    while True:
        names = {o.name for o in selected}
        joined = {o for o in p.col.objects if any(o.get(k) in names for k in (
            'thermal_support', 'thermal_decal_support', 'thermal_marking_support', 'thermal_seated_on'))}
        if joined <= selected:
            break
        selected |= joined
    delta = Vector(delta)
    for obj in selected:
        obj.location += delta
        if obj.get('support_point') and not obj.get('thermal_support_space'):
            obj['support_point'] = Vector(obj['support_point'])+delta
        if obj.get('pipe_path'):
            obj['pipe_path'] = json.dumps([list(Vector(v)+delta) for v in json.loads(obj['pipe_path'])])


def stretch(obj, axis, origin, factor):
    inverse = obj.matrix_world.inverted()
    for vertex in obj.data.vertices:
        point = obj.matrix_world@vertex.co
        point[axis] = origin+(point[axis]-origin)*factor
        vertex.co = inverse@point
    obj.data.update()


def tighten_ports(p):
    """Replace the concept flange with a sharp, closely seated production face."""
    key = 'Thermal production precision flange / 2'
    template = bpy.data.meshes.get(key)
    if template is None:
        plate = p.box('temporary precision flange', (0, 0, -.074),
                      (2.04, 2.04, .12), 'PaintedMetal_Colorable', .003)
        for sign in (-1, 1):
            cutter = p.cylinder('temporary flange bore', (0, sign*.46, -.3),
                                (0, sign*.46, .1), .275, sides=32)
            bpy.context.view_layer.objects.active = plate
            mod = plate.modifiers.new('Machined pressure bore', 'BOOLEAN')
            mod.operation, mod.solver, mod.object = 'DIFFERENCE', 'EXACT', cutter
            bpy.ops.object.modifier_apply(modifier=mod.name)
            bpy.data.objects.remove(cutter, do_unlink=True)
        template = plate.data
        template.transform(plate.matrix_world)
        M['BUILD']['uv'](plate)
        template.name, template.use_fake_user = key, True
        bpy.data.objects.remove(plate, do_unlink=True)
    for port in p.ports:
        n, c = Vector(port['normal']), Vector(port['position'])
        prefix = p.name+' / '+port['id']
        flange = next(o for o in p.col.objects if o.name.startswith(prefix+' flange')
                      and o.get('interface_type') == port['type'])
        flange.data = template
        flange['thermal_chamfer_m'], flange['thermal_chamfer_segments'] = .003, 1
        flange['thermal_bore_axis'] = 2
        flange['thermal_face_setback_m'] = .014
        for obj in list(p.col.objects):
            if obj.get('thermal_support') == flange.name:
                obj.location += n*.023
                obj['support_point'] = Vector(obj['support_point'])+n*.023
            elif obj.get('thermal_marking_support') == flange.name:
                obj.location += n*.026
            elif obj.name.startswith(prefix+' pressure lip '):
                for vertex in obj.data.vertices:
                    d = (vertex.co-c).dot(n)
                    vertex.co += n*(-.055+(d+.075)*(.047/.057)-d)
                path = []
                for point in map(Vector, json.loads(obj['pipe_path'])):
                    d = (point-c).dot(n)
                    path.append(list(point+n*(-.055+(d+.075)*(.047/.057)-d)))
                obj['pipe_path'] = json.dumps(path)
                obj['thermal_port_fit'] = REVISION
                obj.data.update()


def mark(p, support, asset, centre, u, v, width, library='Atlas2'):
    """Project a native atlas asset onto real backing, preserving its UVs."""
    key = 'Thermal detail template / '+library+' / '+asset
    template = bpy.data.meshes.get(key)
    if template is None:
        with bpy.data.libraries.load(str(ASSETS/(library+'.blend')), link=False) as (src, dst):
            assert asset in src.objects, asset
            dst.objects = [asset]
        obj = dst.objects[0]
        template = obj.data.copy()
        template.name = key
        template.use_fake_user = True
        bpy.data.objects.remove(obj, do_unlink=True)
    mesh = template.copy()
    points = [v.co for v in mesh.vertices]
    lo = Vector([min(v[i] for v in points) for i in range(3)])
    hi = Vector([max(v[i] for v in points) for i in range(3)])
    scale, middle = width/(hi.x-lo.x), (lo+hi)/2
    bm = bmesh.new()
    bm.from_mesh(mesh)
    # Chords across a faceted cylinder can sink below the backing even when
    # every projected vertex is outside. Flat panels need no extra density.
    step = .02 if any(f.use_smooth for f in support.data.polygons) else .08
    edges = [e for e in bm.edges if e.calc_length()*scale > step]
    if edges:
        bmesh.ops.subdivide_edges(bm, edges=edges,
            cuts=math.ceil(max(e.calc_length()*scale for e in edges)/step)-1, use_grid_fill=True)
    bm.to_mesh(mesh)
    bm.free()
    u, v, centre = Vector(u).normalized(), Vector(v).normalized(), Vector(centre)
    n = u.cross(v).normalized()
    bpy.context.view_layer.update()
    backing = BVHTree.FromPolygons([support.matrix_world@v.co for v in support.data.vertices],
                                  [list(f.vertices) for f in support.data.polygons])
    for vertex in mesh.vertices:
        point = (vertex.co-middle)*scale
        origin = centre+u*point.x+v*point.y
        hit, normal, _, _ = backing.ray_cast(origin+n*.12, -n, .30)
        assert hit is not None and normal.dot(n) > .65, 'Native marking misses backing: '+support.name
        vertex.co = hit+n*.0015
    for i, material in enumerate(mesh.materials):
        mesh.materials[i] = p.native[material.name.split('.')[0]]
    obj = bpy.data.objects.new(p.name+' / detail '+asset, mesh)
    p.col.objects.link(obj)
    obj['thermal_decal_support'] = support.name
    obj['source_asset'] = 'SEUT '+library+' / '+asset+'; original UVs'
    return obj


def pod(p, centre, width=1.05, height=.62):
    """A supported service/instrument cassette with a native face."""
    return p.panel('instrument service cassette', centre, (width, .14, height))


def anchors(p):
    deck = named(p, 'equipment foundation')[0]
    z = -p.size.z/2+.444
    for x in (-p.size.x/2+.60, p.size.x/2-.60):
        for y in (-p.size.y/2+.80, p.size.y/2-.80):
            p.bolt('skid anchor', (x, y, z), (0, 0, 1), deck, .045)


def manifold_stands(p):
    """Angular load paths under the sockets, clear of both flowing channels."""
    deck_z = -p.size.z/2+.44
    for port in p.ports:
        n, up, c = (Vector(port[k]) for k in ('normal', 'hot_axis', 'position'))
        u = up.cross(n)
        bottom = deck_z+.02-c.z
        for side in (-1, 1):
            root = c-n*.58+u*(side*.80)
            posts = named(p, 'counterflow frame post')+named(p, 'cooler corner support')
            existing = None
            for post in posts:
                points = [post.matrix_world@v.co for v in post.data.vertices]
                if all(min(v[i] for v in points) < root[i] < max(v[i] for v in points) for i in (0, 1)):
                    existing = post
                    depth = max((v-c).dot(n) for v in points)-.02
                    break
            section = ((-.70, bottom), (-.70, -1.10), (-.35, -.86),
                       (-.130, -.86), (-.130, -1.02), (-.46, -1.24), (-.46, bottom))
            if existing:
                section = ((depth, -1.24), (depth, -.86), (-.130, -.86), (-.130, -1.02))
            verts = [c+n*x+up*z+u*(side*.80+t) for t in (-.06, .06) for x, z in section]
            count = len(section)
            faces = [tuple(reversed(range(count))), tuple(range(count, 2*count))]
            faces += [(i, (i+1)%count, (i+1)%count+count, i+count) for i in range(count)]
            cheek = p.mesh('manifold skid bracket', verts, faces, 'PaintedMetal_Colorable')
            cheek['thermal_bracket_port'] = port['id']
            cheek['thermal_bracket_side'] = side
            if existing:
                cheek['thermal_existing_post'] = existing.name
                continue
            point = c-n*.58+u*(side*.80)
            point.z = deck_z+.03
            size = (.34, .14, .07) if abs(n.x) > .5 else (.14, .34, .07)
            foot = p.box('manifold bracket foot', point, size, 'Metal_Dull', .002)
            p.bolt('manifold bracket anchor', point+Vector((0, 0, .037)), (0, 0, 1), foot, .025)


def train(p):
    for label, x, old_length, length in (
            ('compressor', -4.25, 2.0, 2.42), ('turbine', -1.35, 2.75, 3.15),
            ('generator', 2.05, 3.25, 3.40)):
        stretch(named(p, label+' casing')[0], 0, x, length/old_length)
        for cover in named(p, label+' bolted end cover'):
            side = math.copysign(1, centre(cover).x-x)
            move(p, [cover], (side*(length-old_length)/2, 0, 0))
        for obj in named(p, label+' fitted cradle')+named(p, label+' split casing band'):
            side = math.copysign(1, centre(obj).x-x)
            move(p, [obj], (side*(length-old_length)*.33, 0, 0))
    motor = named(p, 'electric compressor motor')[0]
    stretch(motor, 0, -5.55, .48/.70)
    move(p, [motor], (-.19, 0, 0))
    move(p, named(p, 'compressor motor cradle')+named(p, 'compressor motor terminal'), (-.19, 0, 0))
    casing = named(p, 'turbine casing')[0]
    for side in (-1, 1):
        flange = p.box('turbine split joint', (-1.35, side*1.86, .45),
                       (3.05, .22, .16), 'Metal_Dull', .003)
        flange['thermal_seated_on'] = casing.name
        for x in (-2.65, -2, -1.35, -.7, -.05):
            p.bolt('split joint stud', (x, side*1.972, .45), (0, side, 0), flange, .028)
    pod(p, (4.4, -1.68, -.62), .76, .68)
    door = named(p, 'supported switchgear door')[0]
    for z in (-1.12, .62):
        hinge = p.box('switchgear hinge', (3.64, -1.66, z), (.12, .10, .30), 'Metal_Dull', .010)
        hinge['thermal_seated_on'] = door.name
    p.box('switchgear latch foot', (5.02, -1.67, -.20), (.12, .10, .45), 'Metal_Dull', .010)
    p.box('switchgear latch', (5.02, -1.74, -.20), (.075, .08, .32), 'PaintedMetal_VeryDark', .008)
    for x in (-2.15, -.55):
        foot = p.box('turbine inspection boss', (x, .0, 2.28), (.20, .38, .16), 'Metal_Dull', .014)
        p.bolt('inspection boss plug', (x, 0, 2.362), (0, 0, 1), foot, .035)


def heater(p):
    for post in named(p, 'exchanger corner post'):
        stretch(post, 2, -3.35, 6.17/6.5)
    for obj in named(p, 'isolated exchanger vessel')+named(p, 'pressure vessel band'):
        c = centre(obj)
        inverse = obj.matrix_world.inverted()
        factor = 1.02/.75 if 'isolated exchanger vessel' in obj.name else 1.08/.82
        for vertex in obj.data.vertices:
            point = obj.matrix_world@vertex.co
            for axis in (0, 1):
                point[axis] = math.copysign(1.12, c[axis])+(point[axis]-c[axis])*factor
            vertex.co = inverse@point
        obj.data.update()
        if obj.get('pipe_path'):
            path = json.loads(obj['pipe_path'])
            for point in path:
                for axis in (0, 1):
                    point[axis] = math.copysign(1.12, c[axis])+(point[axis]-c[axis])*factor
            obj['pipe_path'] = json.dumps(path)
            obj['pipe_radius'] *= factor
            uv = obj.data.uv_layers.active
            for face in obj.data.polygons:
                for li in face.loop_indices:
                    if abs(face.normal.z) > .99:
                        uv.data[li].uv *= factor
                    else:
                        uv.data[li].uv.y *= factor
    for x in (-1.34, 1.34):
        hatch = p.panel('top exchanger access', (x, 0, 2.87), (2.60, 4.80, .08), (0, 0, 1))
        hatch['thermal_detail_role'] = 'pressure service hatch'
    for sign in (-1, 1):
        z = sign*.46
        p.tube('primary isolation valve body', ((-2.94, 0, z), (-2.66, 0, z)),
               .38, 'Metal_Dull', .10, 32)
        valve = p.box('primary valve actuator', (-2.80, -.40, z),
                      (.34, .30, .26), 'PaintedMetal_Darker', .015)
        p.label(valve, 'H' if sign > 0 else 'C', (-2.80, -.552, z), size=.10)
    pod(p, (1.55, -2.90, -1.50), .76, .58)
    for sign in (-1, 1):
        # Two planes clear the crossing; both ends seat inside the rear posts.
        y = 2.63+sign*.09
        a, b = Vector((-2.6, y, sign*2.3)), Vector((2.6, y, -sign*2.3))
        beam = p.box('rear exchanger diagonal', (a+b)/2, (.16, .16, (b-a).length), 'Metal_Dull', .012)
        beam.rotation_mode = 'QUATERNION'
        beam.rotation_quaternion = (b-a).to_track_quat('Z', 'Y')
        for end in (a, b):
            post = min(named(p, 'exchanger corner post'),
                       key=lambda o: (o.location-Vector((end.x, 2.6, 0))).length)
            p.bolt('rear brace fixing', (end.x, 2.842, end.z), (0, 1, 0), post, .035)


def recuperator(p):
    for obj in named(p, 'counterflow plate'):
        bpy.data.objects.remove(obj, do_unlink=True)
    for x in (-1.55, 1.55):
        for i in range(42):
            p.box('counterflow plate', (x, 0, -2.4+i*4.8/41),
                  (2.65, 3.5, .095), 'Metal_Dull', .0015)
        p.box('plate bank foundation seat', (x, 0, -3.03), (.40, 3.30, .60), 'PaintedMetal_Colorable', .003)
    clamps = named(p, 'plate bank end clamp')
    for obj in clamps:
        for vertex in obj.data.vertices:
            vertex.co.y *= 4.0/3.7
        obj.data.update()
    for x in (-1.55, 1.55):
        for y in (-1.87, 1.87):
            for side in (-1, 1):
                support = min(clamps, key=lambda o: (o.location-Vector((x, 0, side*2.6))).length)
                nut = p.cylinder('plate stack tie nut', (x, y, side*2.75),
                                 (x, y, side*2.86), .11, 'Metal_Shiny', 6)
                nut['thermal_support'] = support.name
                nut['support_point'] = (x, y, side*2.75)
                nut['support_axis'] = (0, 0, side)
    pod(p, (0, -2.17, 2.10), .76, .66)
    # The concept's rail labels faced inward. Keep identifiers clear of the pod.
    for obj in list(p.col.objects):
        if obj.type == 'FONT' and obj.data.body == 'RECUPERATOR / COUNTERFLOW':
            bpy.data.objects.remove(obj, do_unlink=True)
    for rail in named(p, 'bank identifier rail'):
        side = math.copysign(1, rail.location.y)
        for text, x in (('RECUPERATOR', side*1.65), ('COUNTERFLOW', -side*1.65)):
            p.label(rail, text, (x, rail.location.y+side*.062, 2.1),
                    (-side, 0, 0), (0, 0, 1), .13)


def cooler(p):
    named(p, 'fan mounting face')[0]['thermal_bore_axis'] = 1
    for obj in list(p.col.objects):
        if obj.type == 'FONT' and obj.data.body == 'ATMOSPHERIC COOLER / KEEP CLEAR':
            bpy.data.objects.remove(obj, do_unlink=True)
    for z in (-1.82, 2.58):
        for x in (-1.60, 1.60):
            cover = p.panel('plenum service cover', (x, -1.576, z), (3.08, .08, .82))
            cover['thermal_detail_role'] = 'plenum access'
            if z > 0:
                p.label(cover, 'ATMOSPHERIC COOLER' if x < 0 else 'KEEP CLEAR',
                        (x, -1.618, 2.91), size=.10)
    shrouds = named(p, 'fan shroud')
    for x in (-1.68, 1.68):
        shroud = min(shrouds, key=lambda o: abs(sum(v.co.x for v in o.data.vertices)/len(o.data.vertices)-x))
        for i in range(8):
            a = i*math.tau/8
            point = Vector((x+1.47*math.cos(a), -2.30, .4+1.47*math.sin(a)))
            clip = p.cylinder('fan guard retainer', point+Vector((0, .003, 0)),
                              point-Vector((0, .045, 0)), .045, 'Metal_Dull', 8)
            clip['thermal_seated_on'] = shroud.name
            p.bolt('guard captive screw', point-Vector((0, .047, 0)), (0, -1, 0), clip, .018)
        p.cylinder('fan rotor nose', (x, -2.03, .4), (x, -2.12, .4), .34, 'PaintedMetal_Colorable', 32)
    pod(p, (0, -1.59, .4), .28, .72)


def radiator(p):
    # Tile spacing follows one 10 mm joint, rather than broad blockout gaps.
    for tile in named(p, 'high emissivity radiator tile'):
        stretch(tile, 0, tile.location.x, .88/.86)
        stretch(tile, 2, tile.location.z, .625/.60)
    for x in (-1.55, 1.55):
        for side in (-1, 1):
            for dx in (-1.25, 1.25):
                for z in (-2.52, 3.02):
                    clip = p.box('radiator tile retention shoe', (x+dx, side*.18, z),
                                 (.24, .10, .10), 'Metal_Dull', .010)
                    p.bolt('tile retention screw', (x+dx, side*.232, z), (0, side, 0), clip, .021)
    for x in (-.35, .35):
        p.box('pump cassette handle foot', (x, -.49, -3.0), (.09, .10, .10), 'Metal_Dull', .008)
    p.box('pump cassette pull', (0, -.55, -3.0), (.80, .07, .07), 'Metal_Shiny', .008)


def pipe(p):
    # These sleeves duplicated the conduit OD and caused coincident surfaces.
    # Machine stubs are narrower and keep their adapters.
    for obj in list(p.col.objects):
        if ' neck sleeve' in obj.name:
            bpy.data.objects.remove(obj, do_unlink=True)
    for obj in named(p, 'flange load gusset'):
        bpy.data.objects.remove(obj, do_unlink=True)
    for port in p.ports:
        n, up, c = (Vector(port[k]) for k in ('normal', 'hot_axis', 'position'))
        u = up.cross(n)
        for a in (-1, 1):
            for b in (-1, 1):
                section = ((.72, -.130), (.99, -.130), (.99, -.38), (.87, -.38))
                verts = [c+u*(a*x)+n*z+up*(b*.93+t) for t in (-.07, .07) for x, z in section]
                web = p.mesh('flange load web', verts,
                    [(3, 2, 1, 0), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5),
                     (2, 3, 7, 6), (3, 0, 4, 7)], 'Metal_Dull')
                web['thermal_seated_on'] = next(o.name for o in p.col.objects
                    if o.name.startswith(p.name+' / '+port['id']+' flange') and o.get('interface_type'))
    deck = named(p, 'pipe base mounting shoe')[0]
    for x in (-.75, .75):
        for y in (-.75, .75):
            p.bolt('pipe cage anchor', (x, y, -1.106), (0, 0, 1), deck, .035)
    channels = named(p, 'insulated ')+named(p, 'reactor transition ')
    if channels:
        samples = []
        for obj in channels:
            path = [Vector(v) for v in json.loads(obj['pipe_path'])]
            lengths = [(b-a).length for a, b in zip(path, path[1:])]
            distance = sum(lengths)*.50
            for a, b, length in zip(path, path[1:], lengths):
                if distance <= length:
                    samples.append((a.lerp(b, distance/length), (b-a).normalized()))
                    break
                distance -= length
    else:
        samples = [(Vector((-.65, 0, z)), Vector((1, 0, 0))) for z in (-.46, .46)]
    for point, axis in samples:
        clamp = p.tube('insulation retaining clamp', (point-axis*.055, point+axis*.055),
                       .395, 'Metal_Dull', .045, 32)
        up = Vector((0, 0, 1)) if abs(axis.z) < .9 else Vector((0, 1, 0))
        up = (up-axis*up.dot(axis)).normalized()
        p.bolt('insulation clamp screw', point+up*.397, up, clamp, .025)


def geometry(name):
    p = parts(name)
    if p.scene.get('thermal_detail_revision') == REVISION:
        return M['record'](name)
    assert p.scene['thermal_phase'] == 'base'
    before = set(p.col.objects)
    tighten_ports(p)
    if ' / ' in name:
        pipe(p)
    else:
        manifold_stands(p)
        anchors(p)
        {'Brayton train': train, 'Primary heater': heater, 'Recuperator': recuperator,
         'Atmospheric cooler': cooler, 'Space radiator': radiator}[name.removesuffix(' upgraded')](p)
    for obj in set(p.col.objects)-before:
        obj['thermal_detail_revision'] = REVISION
    p.scene['thermal_detail_revision'] = REVISION
    p.scene['thermal_phase'] = 'geometry'
    return M['record'](name)


def cylindrical_uv(obj, shift):
    mesh = obj.data
    if len(mesh.polygons) < 10 or len(mesh.polygons[0].vertices) < 10 or len(mesh.polygons[1].vertices) != len(mesh.polygons[0].vertices):
        return False
    a, b = mesh.polygons[0].center, mesh.polygons[1].center
    axis = (b-a).normalized()
    point = mesh.vertices[mesh.polygons[0].vertices[0]].co-a
    radius = point.length
    if not radius or any(abs((mesh.vertices[i].co-a).length-radius) > 1e-4 for i in mesh.polygons[0].vertices):
        return False
    u = point.normalized()
    v = axis.cross(u).normalized()
    uv = mesh.uv_layers.active
    for face in mesh.polygons:
        cap = abs(face.normal.dot(axis)) > .99
        angles = [math.atan2((mesh.vertices[mesh.loops[li].vertex_index].co-a).dot(v),
                            (mesh.vertices[mesh.loops[li].vertex_index].co-a).dot(u)) for li in face.loop_indices]
        seam = max(angles)-min(angles) > math.pi
        for li, angle in zip(face.loop_indices, angles):
            point = mesh.vertices[mesh.loops[li].vertex_index].co-a
            if cap:
                coords = Vector((point.dot(u), point.dot(v)))
            else:
                coords = Vector((point.dot(axis), (angle+math.tau if seam and angle < 0 else angle)*radius))
            uv.data[li].uv = coords*.8+shift
    obj['uv_method'] = 'metric cylindrical caps and wall; 0.8 tiles/m'
    return True


def asset_details(p):
    """Fit native cover, intake and seam assets to settled mechanical surfaces."""
    name = p.name.removesuffix(' upgraded')
    for cheek in named(p, 'manifold skid bracket'):
        port = next(r for r in p.ports if r['id'] == cheek['thermal_bracket_port'])
        n, up, c = (Vector(port[k]) for k in ('normal', 'hot_axis', 'position'))
        side = cheek['thermal_bracket_side']
        if cheek.get('thermal_existing_post'):
            mark(p, cheek, 'Panel Line Welded', c-n*.24-up*.8585+up.cross(n)*(side*.80),
                 n, up.cross(n), .17, 'Paneling')
        else:
            mark(p, cheek, 'Panel Line Welded', c-n*.58-up*2.2+up.cross(n)*(side*.8615),
                 up, n*side, 1.30, 'Paneling')
    if name == 'Brayton train':
        cabinet = named(p, 'generator switchgear')[0]
        for y in (-.80, .80):
            mark(p, cabinet, 'Square Vent', (5.402, y, -.55), (0, 1, 0), (0, 0, 1), .85, 'Atlas3')
        mark(p, cabinet, 'Square Vent', (5.402, 0, .76), (0, 1, 0), (0, 0, 1), .48, 'Atlas3')
        door = named(p, 'supported switchgear door')[0]
        mark(p, door, 'Square Vent', (4.4, -1.632, .75), (1, 0, 0), (0, 0, 1), .45, 'Atlas3')
        compressor = named(p, 'compressor casing')[0]
        mark(p, compressor, 'Square Vent', (-4.25, 1.275, 0), (-1, 0, 0), (0, 0, 1), .45, 'Atlas3')
        generator = named(p, 'generator casing')[0]
        mark(p, generator, 'Tech Panel', (2.05, 1.622, .45), (-1, 0, 0), (0, 0, 1), .40, 'Atlas3')
    elif name == 'Primary heater':
        for lid in named(p, 'top exchanger access'):
            mark(p, lid, 'Square Vent', lid.location+Vector((0, -1.35, .042)),
                 (1, 0, 0), (0, 1, 0), .70, 'Atlas3')
            for dx in (-.98, .98):
                mark(p, lid, 'Long Screw Plate', lid.location+Vector((dx, 1.62, .042)),
                     (1, 0, 0), (0, 1, 0), .23, 'Atlas3')
        for panel in named(p, 'front service cassette'):
            x = panel.location.x
            mark(p, panel, 'Square Vent', (x, -2.832, -.20), (1, 0, 0), (0, 0, 1), .45, 'Atlas3')
            if x < 0:
                mark(p, panel, 'Square Vent', (x, -2.832, -1.50), (1, 0, 0), (0, 0, 1), .45, 'Atlas3')
        for panel in named(p, 'exotic hot end service cassette'):
            x = panel.location.x
            mark(p, panel, 'Tech Panel', (x, 2.832, -.58), (-1, 0, 0), (0, 0, 1), .16, 'Atlas3')
            mark(p, panel, 'Sign Fire Hazard', (x+.63, 2.832, 1.70), (-1, 0, 0), (0, 0, 1), .16)
    elif name == 'Recuperator':
        for clamp in named(p, 'plate bank end clamp'):
            if clamp.location.z > 0:
                mark(p, clamp, 'Square Vent', clamp.location+Vector((0, 0, .152)),
                     (1, 0, 0), (0, 1, 0), .62, 'Atlas3')
        for post in named(p, 'counterflow frame post'):
            side = math.copysign(1, post.location.y)
            mark(p, post, 'Long Screw Plate', (post.location.x, side*2.177, 1.15),
                 (-side, 0, 0), (0, 0, 1), .14, 'Atlas3')
        for bridge in named(p, 'manifold heat bridge'):
            side = math.copysign(1, bridge.location.y)
            mark(p, bridge, 'Panel Line Welded', bridge.location+Vector((0, side*.042, 0)),
                 (-side, 0, 0), (0, 0, 1), .80, 'Paneling')
    elif name == 'Atmospheric cooler':
        for panel in named(p, 'plenum service cover'):
            for dx in (-.72, .72):
                mark(p, panel, 'Square Vent', panel.location+Vector((dx, -.042, -.06 if panel.location.z > 0 else 0)),
                     (1, 0, 0), (0, 0, 1), .60, 'Atlas3')
    elif name == 'Space radiator':
        panel = named(p, 'radiator pump service')[0]
        mark(p, panel, 'Tech Panel', (-.25, -.477, -2.76), (1, 0, 0), (0, 0, 1), .24, 'Atlas3')
        for obj in p.col.objects:
            if obj.type == 'FONT' and obj.data.body == 'PUMP':
                obj.location = (.30, -.477, -2.70)
                obj.data.size = .08


def textures(name):
    p = parts(name)
    if p.scene.get('thermal_texture_revision') == REVISION:
        runpy.run_path(str(ROOT/'assets/refine_thermal_visibility.py'))['apply'](name)
        runpy.run_path(str(ROOT/'assets/refine_thermal_flow.py'))['apply'](name)
        return M['record'](name)
    assert p.scene['thermal_phase'] == 'geometry'
    original = list(p.col.objects)
    for obj in original:
        if obj.type != 'MESH' or obj.get('source_asset') or obj.get('thermal_decal_support'):
            continue
        if obj.data.users > 1:
            obj.data = obj.data.copy()
        digest = hashlib.sha256(obj.name.encode()).digest()
        shift = Vector((digest[0]/255, digest[1]/255))
        cylindrical_uv(obj, shift)
        obj['thermal_surface_revision'] = REVISION
        # Broad native paint stays quiet; wear is restricted to small chamfers.
        slots = {}
        for i, material in enumerate(list(obj.data.materials)):
            worn = {'PaintedMetal_Colorable': 'PaintedMetalScratched_Colorable',
                    'PaintedMetal_Darker': 'PaintedMetalScratched_Darker'}.get(material.name)
            if worn:
                slots[i] = len(obj.data.materials)
                obj.data.materials.append(p.native[worn])
        largest = max((f.area for f in obj.data.polygons), default=0)
        for face in obj.data.polygons:
            if face.material_index in slots and 1e-5 < face.area < min(.018, largest*.012):
                face.material_index = slots[face.material_index]
    for port in p.ports:
        n, up = Vector(port['normal']), Vector(port['hot_axis'])
        u, centre = up.cross(n), Vector(port['position'])
        prefix = p.name+' / '+port['id']
        flange = next(o for o in original if o.type == 'MESH'
                      and o.name.startswith(prefix+' flange') and o.get('interface_type') == port['type'])
        for obj in original:
            if obj.type == 'MESH' and obj.name.startswith(prefix+' pressure lip '):
                mesh = obj.data
                mesh.materials.append(p.native[COLOURS[port['type']]])
                # Keep the circuit accent visible head-on as well as from the
                # side; the inner bore and rear seating face stay machined.
                for face in mesh.polygons:
                    if face.index < len(mesh.vertices)//4 or face.normal.dot(n) > .9:
                        face.material_index = len(mesh.materials)-1
            elif obj.type == 'FONT' and obj.get('thermal_marking_support') == flange.name and obj.data.body == port['type'].replace('_', ' / '):
                obj.location = centre+up*.92-n*.012
        pressure = {'PRIMARY': 'PRIMARY', 'CO2_HP': '22 MPa', 'CO2_LP': '8 MPa'}[port['type']]
        if port['type'] != 'PRIMARY':
            p.label(flange, pressure, centre-n*.012, u, up, .065)
    for obj in list(p.col.objects):
        if obj.type == 'FONT':
            obj.data.body = obj.data.body.replace('1200 C', '2200 C').replace('OPT / III', 'EX / 2200 C')
    for panel in named(p, 'instrument service cassette'):
        width = .20 if name == 'Atmospheric cooler' else .36
        mark(p, panel, 'Tech Panel', panel.location+Vector((0, -.072, 0)), (1, 0, 0), (0, 0, 1), width, 'Atlas3')
    for panel in named(p, 'top exchanger access'):
        mark(p, panel, 'Sign High Pressure', panel.location+Vector((0, 0, .042)), (1, 0, 0), (0, 1, 0), .32)
        mark(p, panel, 'Panel Line Creased', panel.location+Vector((0, .95, .042)), (1, 0, 0), (0, 1, 0), 2.10, 'Paneling')
    asset_details(p)
    for obj in original:
        if obj.type != 'MESH' or not obj.get('thermal_support'):
            continue
        axis = Vector(obj['support_axis']).normalized()
        centre = Vector(obj['support_point'])+axis*.0105
        if obj.name.startswith(p.name+' / plate stack tie nut'):
            centre = Vector(obj['support_point'])+axis*.1115
        up = Vector((0, 0, 1)) if abs(axis.z) < .9 else Vector((0, 1, 0))
        u = up.cross(axis).normalized()
        v = axis.cross(u).normalized()
        points = [obj.matrix_world@x.co for x in obj.data.vertices]
        radius = max(((x-Vector(obj['support_point']))-axis*(x-Vector(obj['support_point'])).dot(axis)).length for x in points)
        mark(p, obj, 'Large Screw', centre, u, v, radius*1.05, 'Atlas3')
    # Font curves are flattened to native-material mesh markings for SEUT.
    for old in list(p.col.objects):
        if old.type != 'FONT':
            continue
        deps = bpy.context.evaluated_depsgraph_get()
        mesh = bpy.data.meshes.new_from_object(old.evaluated_get(deps))
        name_before = old.name
        old.name += ' / converting'
        obj = bpy.data.objects.new(name_before, mesh)
        p.col.objects.link(obj)
        obj.parent = old.parent
        obj.matrix_world = old.matrix_world.copy()
        for key in old.keys():
            obj[key] = old[key]
        obj['thermal_text'] = old.data.body
        obj['thermal_decal_support'] = old['thermal_marking_support']
        M['BUILD']['uv'](obj)
        bpy.data.objects.remove(old, do_unlink=True)
    p.scene['thermal_texture_revision'] = REVISION
    p.scene['thermal_phase'] = 'textures'
    bpy.context.view_layer.update()
    runpy.run_path(str(ROOT/'assets/refine_thermal_visibility.py'))['apply'](name)
    runpy.run_path(str(ROOT/'assets/refine_thermal_flow.py'))['apply'](name)
    return M['record'](name)
