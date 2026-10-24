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
           'CO2_LP': 'PaintedMetal_Clean', 'CO2': 'PaintedMetal_Clean'}
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


def pressure_seal_fit(p):
    """Seat the socket insert in a counterbore, with a butt seal and pipe end.

    The old through bore coincided with the insert's inside wall, while the
    pipe and seal passed through both. Keep socket coordinates and bore clear.
    """
    if p.name == 'Reactor housing' or p.col.get('thermal_seal_fit_revision') == 1:
        return
    key = 'Thermal pressure flange / stepped seal seat'
    template = bpy.data.meshes.get(key)
    if template is None:
        plate = p.box('temporary seal seat', (0,0,-.074), (2.04,2.04,.12), 'PaintedMetal_Colorable', .003)
        for sign in (-1,1):
            for label, low, high, radius in [('pipe bore',-.16,.02,.360), ('insert counterbore',-.055,.02,.390)]:
                cutter = p.cylinder('temporary '+label,(0,sign*.46,low),(0,sign*.46,high),radius,sides=32)
                bpy.context.view_layer.objects.active = plate
                mod = plate.modifiers.new(label,'BOOLEAN')
                mod.operation,mod.solver,mod.object = 'DIFFERENCE','EXACT',cutter
                bpy.ops.object.modifier_apply(modifier=mod.name)
                bpy.data.objects.remove(cutter,do_unlink=True)
        template = plate.data
        template.transform(plate.matrix_world)
        M['BUILD']['uv'](plate)
        template.name,template.use_fake_user = key,True
        bpy.data.objects.remove(plate,do_unlink=True)
    for port in p.ports:
        c,n,up = (Vector(port[k]) for k in ('position','normal','hot_axis'))
        prefix = p.name+' / '+port['id']
        flange = next(o for o in p.col.objects if o.name.startswith(prefix+' flange') and o.get('interface_type')==port['type'])
        flange.data = template
        flange['thermal_seal_fit_revision'] = 1
        for sign in (-1,1):
            bore = c+up*(sign*.46)
            insert = next(o for o in p.col.objects if o.name.startswith(prefix+' pressure lip '+str(sign)))
            temp = p.tube('temporary pressure insert',[bore-n*.055,bore-n*.008],.385,'Metal_Dull',.110,32)
            temp.data.transform(insert.matrix_world.inverted())
            insert.data = temp.data
            insert['pipe_path'],insert['pipe_radius'] = temp['pipe_path'],temp['pipe_radius']
            insert['thermal_seal_fit_revision'] = 1
            bpy.data.objects.remove(temp,do_unlink=True)
            seal = next(o for o in p.col.objects if o.name.startswith(prefix+' seated face seal '+str(sign)))
            temp = p.tube('temporary butt seal',[bore-n*.008,bore],.308,'PaintedMetal_VeryDark',.033,32)
            temp.data.transform(seal.matrix_world.inverted())
            seal.data = temp.data
            seal['pipe_path'],seal['pipe_radius'] = temp['pipe_path'],temp['pipe_radius']
            seal['thermal_seal_fit_revision'] = 1
            bpy.data.objects.remove(temp,do_unlink=True)
            for obj in p.col.objects:
                if not obj.get('thermal_pressure_glass') or obj.get('thermal_internal_coolant'):
                    continue
                path = list(map(Vector,json.loads(obj['pipe_path']))) if obj.get('pipe_path') else []
                if path and min((end-bore).length for end in (path[0],path[-1])) > .12:
                    continue
                if obj.data.users>1:obj.data=obj.data.copy()
                inverse = obj.matrix_world.inverted()
                for vertex in obj.data.vertices:
                    point = obj.matrix_world@vertex.co
                    axial = (point-bore).dot(n)
                    radial = point-bore-n*axial
                    if -.10 < axial < .002 and radial.length < .361:
                        vertex.co = inverse@(point+n*(-.056+axial*.44-axial))
                for i,point in enumerate(path):
                    axial = (point-bore).dot(n)
                    if (point-bore).length < .10 and axial > -.10:
                        path[i] = point+n*(-.056+axial*.44-axial)
                if path:obj['pipe_path'] = json.dumps([list(v) for v in path])
                obj['thermal_seal_fit_revision'] = 1
                obj.data.update()
    p.col['thermal_seal_fit_revision'] = 1


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
            low_mount = bottom > -1
            if low_mount:
                section = ((-.70,bottom),(-.70,bottom+.30),(-.35,-.60),
                           (-.130,-.60),(-.130,-.74),(-.46,bottom+.05),(-.46,bottom))
            if existing:
                section = ((depth, -1.24), (depth, -.86), (-.130, -.86), (-.130, -1.02))
            verts = [c+n*x+up*z+u*(side*.80+t) for t in (-.06, .06) for x, z in section]
            count = len(section)
            faces = [tuple(reversed(range(count))), tuple(range(count, 2*count))]
            faces += [(i, (i+1)%count, (i+1)%count+count, i+count) for i in range(count)]
            cheek = p.mesh('manifold skid bracket', verts, faces, 'PaintedMetal_Colorable')
            cheek['thermal_bracket_port'] = port['id']
            cheek['thermal_bracket_side'] = side
            cheek['thermal_low_mount'] = low_mount
            if existing:
                cheek['thermal_existing_post'] = existing.name
                continue
            point = c-n*.58+u*(side*.80)
            point.z = deck_z+.03
            size = (.34, .14, .07) if abs(n.x) > .5 else (.14, .34, .07)
            foot = p.box('manifold bracket foot', point, size, 'Metal_Dull', .002)
            p.bolt('manifold bracket anchor', point+Vector((0, 0, .037)), (0, 0, 1), foot, .025)


def mesh_markings(p):
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


def train_series_plate(p):
    """Match the upgraded identification plate on the standard compressor."""
    if p.name.endswith(' upgraded') or named(p,'compressor series plate'):
        return
    x=M['CONTRACT']['TRAIN_CENTRES']['compressor']
    side=1 if ' mirrored' in p.name else -1
    p.box('compressor series mount',(x,side*1.05,-.45),(1.12,.60,.82),'PaintedMetal_Colorable')
    plate=p.panel('compressor series plate',(x,side*1.41,-.45),(1.0,.14,.72),(0,side,0))
    p.label(plate,'EX / 1200 B',(x,side*1.482,-.45),(-side,0,0),(0,0,1),.11)


def train_plinth(p):
    """Continuous foundation from the block floor to the existing deck."""
    deck = named(p, 'equipment foundation')[0]
    rings=[]
    for hx,hy,z in ((6.15,2.30,-p.size.z/2),(6.15,2.30,-2.30),(6.025,2.125,-2.06)):
        cut=.30
        rings.extend((x,y,z) for x,y in ((-hx+cut,-hy),(hx-cut,-hy),(hx,-hy+cut),
            (hx,hy-cut),(hx-cut,hy),(-hx+cut,hy),(-hx,hy-cut),(-hx,-hy+cut)))
    obj=p.mesh('temporary foundation perimeter',rings,
        [tuple(reversed(range(8))),tuple(range(16,24))]
        +[(j+i,j+(i+1)%8,j+(i+1)%8+8,j+i+8) for j in (0,8) for i in range(8)],'PaintedMetal_Colorable')
    obj.data.materials.append(p.native['PaintedMetal_Darker'])
    obj.data.polygons[1].material_index=1
    deck.data=obj.data; deck.matrix_world=obj.matrix_world.copy()
    deck['thermal_refined_foundation']=True
    bpy.data.objects.remove(obj,do_unlink=True)
    for skid in named(p,'load-bearing skid')+named(p,'transverse skid'):
        bpy.data.objects.remove(skid,do_unlink=True)
    return deck


def train_foundation(p):
    deck=train_plinth(p)
    for x,length in ((-3.0,1.25),(-1.4,1.25),(5.45,.60)):
        for side in (-1,1):
            cover=p.panel('foundation inspection insert',(x,side*1.83,-2.047),
                (length,.32,.026),(0,0,1))
            cover['thermal_seated_on']=deck.name


def train(p):
    shaft_z = M['CONTRACT']['TRAIN_SHAFT_Z']
    cx,tx,gx,bx=(M['CONTRACT']['TRAIN_CENTRES'][k] for k in ('compressor','turbine','generator','cabinet'))
    for label, x, old_length, length in (
            ('compressor', cx, 2.0, 2.42), ('turbine', tx, 2.75, 3.15),
            ('generator', gx, 2.0, 2.0)):
        stretch(named(p, label+' casing')[0], 0, x, length/old_length)
        for cover in named(p, label+' bolted end cover'):
            side = math.copysign(1, centre(cover).x-x)
            move(p, [cover], (side*(length-old_length)/2, 0, 0))
        for obj in named(p, label+' fitted cradle')+named(p, label+' split casing band'):
            side = math.copysign(1, centre(obj).x-x)
            move(p, [obj], (side*(length-old_length)*.33, 0, 0))
    # Lower saddles follow the drum and leave the inlet plenum unobstructed.
    for cradle in named(p, 'turbine fitted cradle'):
        move(p, [cradle], (.50 if centre(cradle).x < tx else -.50, 0, 0))
    for cradle in named(p, 'compressor fitted cradle'):
        if centre(cradle).x > cx:move(p, [cradle], (-.55, 0, 0))
    for band in named(p, 'generator split casing band'):
        move(p, [band], (math.copysign(.24*M['CONTRACT']['TRAIN_GENERATOR_STRETCH'],centre(band).x-gx),0,0))
    for label, x, length, radius in (('compressor',cx,2.42,1.35),
                                    ('turbine',tx,3.15,1.85),('generator',gx,2.0,1.62)):
        for sign in (-1,1):
            end=x+sign*length/2
            if label=='generator':end=M['CONTRACT']['generator_x'](end)
            ring=p.tube(label+' stepped end flange',[(end-.025,0,shaft_z),(end+.025,0,shaft_z)],
                        radius+.035,'Metal_Dull',.09,64)
            ring['thermal_seated_on']=named(p,label+' casing')[0].name
    motor = named(p, 'electric compressor motor')[0]
    stretch(motor, 0, cx-1.30, .48/.70)
    move(p, [motor], (-.19, 0, 0))
    move(p, named(p, 'compressor motor cradle')+named(p, 'compressor motor terminal'), (-.19, 0, 0))
    casing = named(p, 'turbine casing')[0]
    for side in (-1, 1):
        flange = p.box('turbine split joint', (tx, side*1.86, shaft_z),
                       (3.05, .22, .16), 'Metal_Dull', .003)
        flange['thermal_seated_on'] = casing.name
        for x in (tx-1.30, tx-.65, tx, tx+.65, tx+1.30):
            p.bolt('split joint stud', (x, side*1.972, shaft_z), (0, side, 0), flange, .028)
    train_foundation(p)
    train_series_plate(p)
    cabinet = named(p, 'generator switchgear')[0]
    cabinet_centre = centre(cabinet)
    at = lambda offset: cabinet_centre+Vector(offset)*.7
    pod(p, at((0, -1.68, -.32)), .76*.7, .68*.7)
    door = named(p, 'supported switchgear door')[0]
    for z in (-.82, .92):
        hinge = p.box('switchgear hinge', at((-.56, -1.66, z)), Vector((.12, .10, .30))*.7, 'Metal_Dull', .003)
        hinge['thermal_seated_on'] = door.name
    p.box('switchgear latch foot', at((.53, -1.67, .10)), Vector((.12, .10, .45))*.7, 'Metal_Dull', .003)
    p.box('switchgear latch', at((.53, -1.74, .10)), Vector((.075, .08, .32))*.7, 'PaintedMetal_VeryDark', .003)
    p.label(door,'II / EX' if p.name.endswith(' upgraded') else 'STD',
            at((0,-1.631,-1.08)),size=.085)
    for x in (tx-.80, tx+.80):
        foot = p.box('turbine inspection boss', (x, .0, shaft_z+1.83), (.20, .38, .16), 'Metal_Dull', .014)
        p.bolt('inspection boss plug', (x, 0, shaft_z+1.912), (0, 0, 1), foot, .035)

    start, end = cx+1.21, tx-1.575
    sides=64
    rings=((start,1.35),(end,1.85),(start,1.23),(end,1.73))
    verts=[(x,r*math.cos(i*math.tau/sides),shaft_z+r*math.sin(i*math.tau/sides))
           for x,r in rings for i in range(sides)]
    faces=[]
    for a,b in ((0,1),(1,3),(3,2),(2,0)):
        faces.extend((a*sides+i,a*sides+(i+1)%sides,b*sides+(i+1)%sides,b*sides+i) for i in range(sides))
    taper=p.mesh('compressor expanding casing',verts,faces,'PaintedMetal_Darker')
    for f in taper.data.polygons:f.use_smooth=f.index//sides in (0,2)
    taper['thermal_compressor_transition']=True
    taper['thermal_pressure_wall_m']=.12


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
    if name == 'Atmospheric cooler' and M['scene_for'](name).get('cooler_integrated_revision'):
        return M['record'](name)
    if name in ('Space radiator','Radiator panel') and M['scene_for'](name).get('radiator_tracking_revision'):
        return M['record'](name)
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
        {'Brayton train': train, 'Atmospheric cooler': cooler, 'Space radiator': radiator}[name.removesuffix(' upgraded')](p)
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
        if cheek.get('thermal_low_mount'):continue
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
        cx,tx,gx,bx=(M['CONTRACT']['TRAIN_CENTRES'][k] for k in ('compressor','turbine','generator','cabinet'))
        cabinet = named(p, 'generator switchgear')[0]
        c = centre(cabinet)
        at = lambda offset: c+Vector(offset)*.7
        for y in (-.80, .80):
            mark(p, cabinet, 'Square Vent', at((.727,y,-.25)), (0, 1, 0), (0, 0, 1), .85*.7, 'Atlas3')
        mark(p, cabinet, 'Square Vent', at((.727,0,1.06)), (0, 1, 0), (0, 0, 1), .48*.7, 'Atlas3')
        door = named(p, 'supported switchgear door')[0]
        mark(p, door, 'Square Vent', at((0,-1.632,1.05)), (1, 0, 0), (0, 0, 1), .45*.7, 'Atlas3')
        compressor = named(p, 'compressor casing')[0]
        mark(p, compressor, 'Square Vent', (cx, 1.275, M['CONTRACT']['TRAIN_SHAFT_Z']-.45), (-1, 0, 0), (0, 0, 1), .45, 'Atlas3')
        # The generator casing is reshaped by the visibility pass. Project its
        # service marking there, after the inspection aperture is final.
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
    if name == 'Atmospheric cooler' and M['scene_for'](name).get('cooler_integrated_revision'):
        return M['record'](name)
    if name in ('Space radiator','Radiator panel') and M['scene_for'](name).get('radiator_tracking_revision'):
        return M['record'](name)
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
        pressure = {'PRIMARY': 'PRIMARY', 'CO2_HP': '22 MPa', 'CO2_LP': '8 MPa', 'CO2': 'DUPLEX'}[port['type']]
        if port['type'] != 'PRIMARY':
            p.label(flange, pressure, centre-n*.012, u, up, .065)
    for obj in list(p.col.objects):
        if obj.type == 'FONT':
            obj.data.body = obj.data.body.replace('1200 C', '2200 C').replace('OPT / III', 'EX / 2200 C')
    for panel in named(p, 'instrument service cassette'):
        width = .20 if name == 'Atmospheric cooler' else .252 if name.startswith('Brayton train') else .36
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
    mesh_markings(p)
    p.scene['thermal_texture_revision'] = REVISION
    p.scene['thermal_phase'] = 'textures'
    bpy.context.view_layer.update()
    runpy.run_path(str(ROOT/'assets/refine_thermal_visibility.py'))['apply'](name)
    runpy.run_path(str(ROOT/'assets/refine_thermal_flow.py'))['apply'](name)
    return M['record'](name)
