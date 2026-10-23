"""Flared load cradles with closed coolant bores and cable bulkhead glands.

Called by the visibility pass before pipe finishes, or applied to finished
trains in the live production file without rebuilding their accepted machinery.
"""
import json
import math
from pathlib import Path
import runpy

import bpy
import bmesh
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(str(ROOT/'assets/build_thermal_models.py'))


def bounds(obj):
    points = [obj.matrix_world@v.co for v in obj.data.vertices]
    return [Vector([fn(v[i] for v in points) for i in range(3)]) for fn in (min, max)]


def shape(p):
    """Use low compressor saddles; flare the larger drums' service struts."""
    for obj in list(p.col.objects):
        if obj.get('thermal_strut_fitting'):
            bpy.data.objects.remove(obj, do_unlink=True)
    supports = []
    for label, radius in (('compressor',1.35), ('turbine',1.85), ('generator',1.62)):
        cradles = sorted((o for o in p.col.objects if o.name.startswith(p.name+' / '+label+' fitted cradle')),
                         key=lambda o: bounds(o)[0].x)
        assert len(cradles) == 2, (p.name, label)
        for index, old in enumerate(cradles):
            low, high = bounds(old)
            x, width = (low.x+high.x)/2, high.x-low.x
            r, z = radius-.008, M['CONTRACT']['TRAIN_SHAFT_Z']
            compact = label == 'compressor'
            if compact:
                # Seat only the underside of the smaller drum. Its manifold
                # and pipe routes pass above/outside these compact supports.
                x = M['CONTRACT']['TRAIN_CENTRES']['compressor']+(-.7986,.2486)[index]
                top = -1.16
                angle = math.asin((z-top)/r)
                profile = [(-1.10,-2.14),(1.10,-2.14),(1.13,-2.11),
                           (1.13,-1.90),(.94,top),(r*math.cos(angle),top)]
                profile += [(r*math.cos(a),z-r*math.sin(a)) for a in
                            (angle+(math.pi-2*angle)*i/20 for i in range(1,21))]
                profile += [(-.94,top),(-1.13,-1.90),(-1.13,-2.11)]
            else:
                profile = [(-2.14,-2.14),(2.14,-2.14),(2.17,-2.11),(2.17,-1.55),
                           (r+.08,z-.22),(r+.08,z),(r,z)]
                profile += [(r*math.cos(i*math.pi/32),z-r*math.sin(i*math.pi/32)) for i in range(1,33)]
                profile += [(-r-.08,z),(-r-.08,z-.22),(-2.17,-1.55),(-2.17,-2.11)]
            n = len(profile)
            verts = [(x+dx,y,h) for dx in (-width/2,width/2) for y,h in profile]
            faces = [tuple(reversed(range(n))),tuple(range(n,2*n))]
            faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
            fresh = p.mesh('temporary flared cradle',verts,faces,'PaintedMetal_Colorable')
            old.data = fresh.data
            old.matrix_world = Matrix.Identity(4)
            bpy.data.objects.remove(fresh,do_unlink=True)
            old['thermal_strut_revision'] = 2
            old['thermal_compact_compressor_saddle'] = compact
            supports.append(old)
    bpy.context.view_layer.update()
    return supports


def closed_cutter(p, pipe, clearance):
    path = list(map(Vector,json.loads(pipe['pipe_path'])))
    path[0] -= (path[1]-path[0]).normalized()*.04
    path[-1] += (path[-1]-path[-2]).normalized()*.04
    cutter = p.tube('temporary strut bore',path,pipe['pipe_radius']+clearance,'Metal_Dull',.02,32)
    bm = bmesh.new(); bm.from_mesh(cutter.data); bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm,geom=[v for v in bm.verts if v.index%64 >= 32],context='VERTS')
    bmesh.ops.holes_fill(bm,edges=[e for e in bm.edges if e.is_boundary],sides=0)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(cutter.data); bm.free()
    return cutter


def refine(p):
    from mathutils.bvhtree import BVHTree
    def tree(obj):
        return BVHTree.FromPolygons([obj.matrix_world@v.co for v in obj.data.vertices],
                                   [list(f.vertices) for f in obj.data.polygons])
    supports = shape(p)
    pipes = [o for o in p.col.objects if o.get('thermal_gas_channel') or o.get('thermal_nozzle_collar')
             or o.get('thermal_cable_bend_radius')]
    for pipe in pipes:
        cable = bool(pipe.get('thermal_cable_bend_radius'))
        cutter = closed_cutter(p,pipe,.022 if cable else .045)
        cutting = tree(cutter)
        for support in supports:
            if not cutting.overlap(tree(support)):
                continue
            bpy.context.view_layer.objects.active = support
            mod = support.modifiers.new('Closed service bore','BOOLEAN')
            mod.operation,mod.solver,mod.object = 'DIFFERENCE','EXACT',cutter
            bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(cutter,do_unlink=True)
    surface = runpy.run_path(str(ROOT/'assets/refine_thermal_models.py'))
    side = 1 if ' mirrored' in p.name else -1
    for support in supports:
        low, high = bounds(support)
        surface['cylindrical_uv'](support,Vector((.31,.57)))
        support['thermal_pipe_clearance_m'] = .045
        support['thermal_surface_revision'] = surface['REVISION']
        if support.get('thermal_compact_compressor_saddle'):
            continue
        # Metal bulkhead barrel spans the full strut; paired round sockets connect
        # the exposed cable runs, with a separate bore from the coolant pipe.
        for label, a, b, radius, wall, sides, material in (
            ('cable bulkhead barrel',low.x-.045,high.x+.045,.108,.012,32,'Metal_Dull'),
            ('cable bulkhead front socket',low.x-.060,low.x-.006,.130,.030,40,'Metal_Shiny'),
            ('cable bulkhead rear socket',high.x+.006,high.x+.060,.130,.030,40,'Metal_Shiny')):
            obj = p.tube(label,[(a,side*2.00,-1.91),(b,side*2.00,-1.91)],radius,material,wall,sides)
            obj['thermal_strut_fitting'] = support.name
            obj['thermal_cable_bulkhead'] = True
        if high.x < M['CONTRACT']['TRAIN_CENTRES']['turbine']+1.0:
            # The two turbine cradles cross the straight return run. The last two
            # support the generator beyond the return nozzle and carry cable only.
            cold = next(o for o in pipes if o.get('thermal_gas_channel') and 'cold rear return' in o.name)
            path = list(map(Vector,json.loads(cold['pipe_path'])))
            clipped = []
            for a,b in zip(path,path[1:]):
                if b.x-a.x < 1e-6:continue
                begin,end = max(a.x,low.x-.025),min(b.x,high.x+.025)
                if end <= begin:continue
                for x in (begin,end):
                    point = a+(b-a)*((x-a.x)/(b.x-a.x))
                    if not clipped or (point-clipped[-1]).length > 1e-6:clipped.append(point)
            obj = p.tube('coolant strut liner',clipped,.331,'Metal_Dull',.030,32)
            obj['thermal_strut_fitting'] = support.name
            obj['thermal_coolant_bulkhead'] = True
    bpy.context.view_layer.update()
    p.scene['thermal_strut_revision'] = 2
    return supports


def apply(name):
    assert name.startswith('Brayton train')
    p = M['Parts'](name,existing=True)
    v = runpy.run_path(str(ROOT/'assets/refine_thermal_visibility.py'))
    v['compressor_cable'](p)
    v['clear_pipe_supports'](p)
    # Re-space the existing glass rings around the newly occupied support spans.
    p.col['thermal_external_jacket_revision'] = 0
    p.native['ArcanePower_CoolantGlass'] = bpy.data.materials['ArcanePower_CoolantGlass']
    runpy.run_path(str(ROOT/'assets/refine_thermal_flow.py'))['external_pipe_jackets'](p)
    return M['record'](name)
