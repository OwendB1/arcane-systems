"""Sealed Arcane rotary union: native stator and separate advanced-rotor head.

Author in the visible thermal production file. This does not export anything.
The tracking radiator keeps its same-grid subpart and uses the same side armor.
"""
import json
import math
from pathlib import Path
import runpy
import bpy
import bmesh
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = runpy.run_path(str(ROOT/'assets/thermal_model_contract.py'))
HEAD_CENTRE = CONTRACT['PIPE_ROTOR_HEAD_CENTRE']
DISPLACEMENT = CONTRACT['PIPE_ROTOR_DISPLACEMENT']
CUFF_BOTTOM = CONTRACT['PIPE_ROTOR_CUFF_BOTTOM']


def cut(p, target, cutter):
    bpy.context.view_layer.objects.active = target
    mod = target.modifiers.new('Machined sealed recess', 'BOOLEAN')
    mod.operation, mod.solver, mod.object = 'DIFFERENCE', 'EXACT', cutter
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)
    runpy.run_path(str(ROOT/'assets/thermal_parts.py'))['uv'](target)


def side_shell(p, detailed=False):
    """Full-cell closed walls, with inset service covers backed by solid armor."""
    for axis in (0, 1):
        for sign in (-1, 1):
            n = Vector((sign if axis == 0 else 0, sign if axis == 1 else 0, 0))
            u, v = Vector((0, 0, 1)).cross(n), Vector((0, 0, 1))
            frame = Matrix((u, v, n)).transposed().to_4x4()
            # Butt the walls against each other and the end caps. Overlapping
            # full-size slabs produced coplanar exterior strips at every edge.
            size = ((.10, 2.5, 2.30) if axis == 0 else (2.30, .10, 2.30)) if detailed else (
                (.10, 2.5, 2.5) if axis == 0 else (2.5, .10, 2.5))
            wall = p.box('rotor side armor', n*1.20, size, 'PaintedMetal_Colorable', 0)
            wall['pipe_rotor_collision'] = True
            recess = p.box('temporary service recess', (0, 0, 0), (1.82, 1.86, .08), chamfer=.003)
            recess.matrix_world = frame; recess.location = n*1.25
            cut(p, wall, recess)
            gasket = p.box('service cover gasket', (0, 0, 0), (1.80, 1.84, .016), 'PaintedMetal_VeryDark', .003)
            gasket.matrix_world = frame; gasket.location = n*1.220
            panel = p.box('inset rotor service cover', (0, 0, 0), (1.74, 1.78, .018), 'PaintedMetal_Darker', .003)
            panel.matrix_world = frame; panel.location = n*1.231
            gasket['thermal_seated_on'] = panel['thermal_seated_on'] = wall.name
            for x in (-.76, .76):
                for z in (-.78, .78):
                    p.bolt('service captive bolt', n*1.240+u*x+v*z, n, panel, .027)
            p.label(panel, 'ARCANE / ROTARY UNION', n*1.241+v*.50, u, v, .072)
            p.label(panel, 'SEALED HULL CASING', n*1.241-v*.58, u, v, .055)
            p.hazard(panel, n*1.242-v*.12, u, v, width=.30)
            if detailed:
                # Recessed paired channel lamps and an inset machined latch.
                for x,material in ((-.53,'ThermalHot'),(.53,'ThermalCold')):
                    at = u*x+v*.03
                    pocket = p.box('temporary lamp pocket', (0,0,0), (.106,.43,.024), chamfer=0)
                    pocket.matrix_world=frame; pocket.location=n*1.24+at
                    cut(p,panel,pocket)
                    bezel=p.box('channel lamp bezel',(0,0,0),(.098,.422,.008),'PaintedMetal_VeryDark',.001)
                    bezel.matrix_world=frame;bezel.location=n*1.232+at
                    bezel['thermal_seated_on']=panel.name
                    lamp=p.box('recessed channel emitter',(0,0,0),(.036,.32,.004),material,.001)
                    lamp.matrix_world=frame;lamp.location=n*1.238+at
                    lamp['pipe_rotor_emitter']=True
                    lamp['thermal_seated_on']=bezel.name
                    p.label(panel,'H' if x<0 else 'C',n*1.241+u*x-v*.25,u,v,.055)
                latch=p.box('service latch insert',(0,0,0),(.32,.075,.006),'Metal_Dull',.001)
                latch.matrix_world=frame;latch.location=n*1.242-v*.40
                latch['thermal_seated_on']=panel.name
                for x in (-.12,.12):
                    # Recessed slot marks sit on the latch, clear of its bevel.
                    slot=p.box('latch tool slot',(0,0,0),(.008,.033,.001),'PaintedMetal_VeryDark',0)
                    slot.matrix_world=frame;slot.location=n*1.2456+u*x-v*.40
                    slot['thermal_seated_on']=latch.name


def arc(p, label, inner, outer, bottom, top, start, end, material):
    """Closed, supported annular inlay with separate cap and curved-wall UVs."""
    count=max(2,round((end-start)/math.tau*96))
    verts=[(r*math.cos(a),r*math.sin(a),z)
           for z in (bottom,top) for r in (inner,outer)
           for a in (start+(end-start)*i/count for i in range(count+1))]
    n=count+1
    faces=[]
    for i in range(count):
        faces.extend(((i,i+1,n+i+1,n+i),(2*n+i,3*n+i,3*n+i+1,2*n+i+1),
                      (i,2*n+i,2*n+i+1,i+1),(n+i,n+i+1,3*n+i+1,3*n+i)))
    faces.extend(((0,n,3*n,2*n),(count,2*n+count,3*n+count,n+count)))
    obj=p.mesh(label,verts,faces,material)
    uv=obj.data.uv_layers.active
    for face in obj.data.polygons:
        curved=abs(face.normal.z)<.01 and face.index<count*4 and face.index%4>=2
        face.use_smooth=curved
        for li in face.loop_indices:
            idx=obj.data.loops[li].vertex_index
            point=obj.data.vertices[idx].co
            if curved:
                uv.data[li].uv=((end-start)*(idx%n)/count*outer*.8,point.z*.8)
            elif abs(face.normal.z)>.99:
                uv.data[li].uv=(point.x*.8,point.y*.8)
            else:
                uv.data[li].uv=(math.hypot(point.x,point.y)*.8,point.z*.8)
    return obj


def bearing(p, head, cap):
    # Round fastener pockets may keep smooth walls; the broad caps stay flat.
    cap['thermal_bore_axis']=2
    if head:
        # The complete cuff belongs to the native head and follows both its
        # rotation and displacement. The closed spindle slides inside the seat.
        p.cylinder('rotating cuff core',(0,0,CUFF_BOTTOM),(0,0,-1.18),.78,'Metal_Dull',96)
        p.tube('polished telescoping cuff',[(0,0,-1.82),(0,0,-1.30)],.80,'Metal_Shiny',.025,96)
        for label,lo,hi,radius in (
                ('lower lip',-1.31,-1.302,.91),('inlay backing',-1.302,-1.274,.898),
                ('upper shoulder',-1.274,-1.17,.91)):
            shoulder=p.tube('rotating cuff '+label,[(0,0,lo),(0,0,hi)],radius,'Metal_Dull',radius-.77,96)
            if label=='inlay backing':backing=shoulder
        for i in range(4):
            obj=arc(p,'rotating cuff cyan inlay',.895,.904,-1.301,-1.275,
                    i*math.pi/2+.10,(i+1)*math.pi/2-.10,'ThermalCold')
            obj['pipe_rotor_emitter']=True
            n=Vector((math.cos(i*math.pi/2),math.sin(i*math.pi/2),0))
            p.bolt('rotating cuff segment screw',n*.905+Vector((0,0,-1.288)),n,backing,.018)
        for obj in p.col.objects:
            if 'cuff' in obj.name:
                obj['pipe_rotor_spindle']=True
                obj['lod_keep']=True
        marker(p,'wheel',(0,0,0))
    else:
        # Deep closed well: 70 mm bottom clearance at minimum displacement,
        # at least 295 mm engagement at maximum displacement.
        p.cylinder('fixed pressure bulkhead',(0,0,.60),(0,0,.68),.96,'PaintedMetal_VeryDark',96)
        p.tube('rotary bearing seal',[(0,0,.66),(0,0,1.245)],.93,'PaintedMetal_VeryDark',.11,96)
        p.tube('machined bearing rim',[(0,0,1.205),(0,0,1.245)],1.02,'Metal_Shiny',.09,96)
        # Native stators constrain the head's block origin, not its wheel dummy.
        marker(p,'electric_motor',(0,0,HEAD_CENTRE))
        for obj in p.col.objects:
            if any(label in obj.name for label in ('fixed pressure bulkhead','rotary bearing seal','machined bearing rim')):
                obj['lod_keep']=True
        cap['lod_keep']=True
    n=Vector((0,0,-1 if head else 1))
    for i in range(8):
        a=math.tau*i/8+math.pi/8
        point=Vector((1.09*math.cos(a),1.09*math.sin(a),n.z*1.25))
        cut(p,cap,p.cylinder('temporary bearing fastener pocket',point-n*.023,point+n*.03,.052,sides=24))
        p.bolt('bearing retainer bolt',point-n*.015,n,cap,.032)


def marker(p, name, at, normal=(0, 0, 1), scale=.1):
    obj = bpy.data.objects.new(p.name+' / '+name, None)
    p.col.objects.link(obj)
    obj.location = at
    obj.rotation_euler = Vector(normal).to_track_quat('Z', 'Y').to_euler()
    obj.scale = (scale, scale, scale)
    obj.empty_display_size = 1
    obj['native_dummy'] = name
    return obj


def build(name):
    assert name in ('Pipe rotor', 'Pipe rotor head')
    m = runpy.run_path(str(ROOT/'assets/build_thermal_models.py'))
    p = m['Parts'](name, existing=m['CONTRACT']['subtype'](name) in bpy.data.scenes)
    for obj in list(p.col.objects): bpy.data.objects.remove(obj, do_unlink=True)
    p.ports = []
    flow = runpy.run_path(str(ROOT/'assets/refine_thermal_flow.py'))
    flow['materials'](p)
    side_shell(p, detailed=True)
    head = name.endswith('head')
    bearing_cap=None
    for sign in (-1, 1):
        cap = p.box('rotor end armor', (0, 0, sign*1.20), (2.5, 2.5, .10), 'PaintedMetal_Darker', 0)
        cap['pipe_rotor_collision'] = True
        if (sign == 1) == head:
            cut(p, cap, p.box('temporary socket aperture', (0, 0, sign*1.20), (1.98, 1.98, .4), chamfer=0))
        elif not head:
            cut(p, cap, p.cylinder('temporary bearing bore', (0, 0, .8), (0, 0, 1.4), .86, sides=96))
            cap['thermal_bore_axis'] = 2
        if (sign == -1) == head:bearing_cap=cap
    n = (0, 0, 1 if head else -1)
    p.port('CO2', (0, 0, n[2]*1.25), n, 'CO2', (0, 1, 0))
    for sign in (-1, 1):
        centre = Vector((0, sign*.46, n[2]*1.25))
        p.cylinder('sealed channel bulkhead', centre-Vector(n)*.36, centre-Vector(n)*.28,
                   .28, 'PaintedMetal_VeryDark', 48)
    bearing(p,head,bearing_cap)
    marker(p, 'detector_conveyor_001', (0, 0, n[2]*1.25), n, .50)
    refine = runpy.run_path(str(ROOT/'assets/refine_thermal_models.py'))
    refine['tighten_ports'](p)
    refine['mesh_markings'](p)
    refine['pressure_seal_fit'](p)
    for obj in p.col.objects:
        if obj.type == 'MESH': refine['cylindrical_uv'](obj, Vector((.17, .31)))
    p.finish(); p.scene['thermal_phase'] = 'textures'
    p.scene['pipe_rotor_revision'] = 2
    p.scene['thermal_detail_revision'] = p.scene['thermal_texture_revision'] = 1
    # Reuse the standard duplex flow overlay up to the sealed rotary union.
    data = json.loads((ROOT/'assets/thermal-flow-paths.json').read_text())
    data['models'][p.scene.name] = [flow['path_row']([(0, sign*.46, n[2]*1.25), (0, sign*.46, 0)],
        'CO2', sign > 0, 0, .16, label='rotary union channel') for sign in (-1, 1)]
    (ROOT/'assets/thermal-flow-paths.json').write_text(json.dumps(data, indent=2)+'\n')
    return m['record'](name)


def review(angle=0, displacement=0):
    assert DISPLACEMENT[0] <= displacement <= DISPLACEMENT[1]
    r = runpy.run_path(str(ROOT/'assets/review_thermal_models.py'))
    scene, p = r['fresh']('pipe rotor')
    r['instance'](scene, 'Pipe rotor', (0, 0, 0))
    r['instance'](scene, 'Pipe rotor head', (0, 0, HEAD_CENTRE+displacement), Matrix.Rotation(angle, 3, 'Z'))
    r['instance'](scene, 'Space radiator', (4, 0, 0))
    r['engineer'](p, (-3.25, -.25))
    for obj in p.col.objects: obj.location.z -= 1.25
    return r['view'](scene.name, target=(.5, 0, 1.3), direction=(.2,-1,.05), distance=13)


def review_travel():
    """Unsaved live comparison of the native displacement range."""
    r=runpy.run_path(str(ROOT/'assets/review_thermal_models.py'))
    scene,p=r['fresh']('pipe rotor travel')
    for x,displacement,label in ((-3.5,DISPLACEMENT[0],'10 CM / MIN'),
                                  (0,0,'20 CM / DEFAULT'),(3.5,DISPLACEMENT[1],'30 CM / MAX')):
        r['instance'](scene,'Pipe rotor',(x,0,0))
        r['instance'](scene,'Pipe rotor head',(x,0,HEAD_CENTRE+displacement),Matrix.Rotation(.20,3,'Z'))
        plaque=p.box('gap label backing',(x,0,-1.55),(2.0,.02,.24),'PaintedMetal_VeryDark',.002)
        p.label(plaque,label,(x,-.012,-1.55),size=.12)
    r['engineer'](p,(-6.0,0))
    for obj in p.col.objects:
        if 'engineer' in obj.name:obj.location.z-=1.25
    return r['view'](scene.name,target=(-.5,0,1.3),direction=(.12,-1,.015),distance=18)


def audit():
    m = runpy.run_path(str(ROOT/'assets/build_thermal_models.py'))
    checked = samples = 0
    geometry={}
    measurements={}
    for name in ('Pipe rotor', 'Pipe rotor head'):
        s, col = m['scene_for'](name), m['main_for'](name)
        bpy.context.window.scene = s; bpy.context.view_layer.update()
        assert tuple(s['se_definition_size']) == (1, 1, 1)
        assert len([o for o in col.objects if o.get('pipe_rotor_collision')]) == 6
        assert len(json.loads(col['ports'])) == 1
        vertices, faces = [], []
        for obj in col.objects:
            if obj.type != 'MESH' or obj.get('thermal_text') or obj.get('source_asset'): continue
            bm = bmesh.new(); bm.from_mesh(obj.data)
            assert all(e.is_manifold for e in bm.edges), obj.name
            bm.free(); checked += 1
            offset = len(vertices)
            points=[obj.matrix_world@v.co for v in obj.data.vertices]
            vertices.extend(points)
            faces.extend(tuple(offset+i for i in face.vertices) for face in obj.data.polygons)
            measurements[obj.name]=dict(low=min(v.z for v in points),high=max(v.z for v in points),
                radius=max(math.hypot(v.x,v.y) for v in points))
        tree = BVHTree.FromPolygons(vertices, faces)
        geometry[name]=(vertices,faces,tree)
        for axis in range(3):
            axes = [i for i in range(3) if i != axis]
            for sign in (-1, 1):
                n = Vector(tuple(sign if i == axis else 0 for i in range(3)))
                for a in range(-12, 13):
                    for b in range(-12, 13):
                        point = n*1.26
                        point[axes[0]], point[axes[1]] = a*.1, b*.1
                        assert tree.ray_cast(point, -n, .75)[0] is not None, (name, 'Open hull', tuple(point))
                        samples += 1
        native = {o['native_dummy']:o for o in col.objects if o.get('native_dummy')}
        key = 'wheel' if name.endswith('head') else 'electric_motor'
        assert abs(native[key].location.z-(0 if name.endswith('head') else HEAD_CENTRE)) < 1e-6
        # Coplanar EXTERIOR armor patches must not overlap across objects.
        for axis in range(3):
            axes=[i for i in range(3) if i!=axis]
            for sign in (-1,1):
                patches=[]
                for obj in col.objects:
                    if not obj.get('pipe_rotor_collision'):continue
                    for face in obj.data.polygons:
                        ps=[obj.matrix_world@obj.data.vertices[i].co for i in face.vertices]
                        if all(abs(v[axis]-sign*1.25)<1e-5 for v in ps):
                            patches.append((obj.name,[(min(v[i] for v in ps),max(v[i] for v in ps)) for i in axes]))
                for i,(a,ra) in enumerate(patches):
                    for b,rb in patches[i+1:]:
                        if a!=b:
                            assert not all(min(x[1],y[1])-max(x[0],y[0])>1e-5 for x,y in zip(ra,rb)),(a,b,'Coplanar armor')
    core=measurements['Pipe rotor head / rotating cuff core']
    sleeve=measurements['Pipe rotor head / polished telescoping cuff']
    bulkhead=measurements['Pipe rotor / fixed pressure bulkhead']
    seal=measurements['Pipe rotor / rotary bearing seal']
    min_centre,max_centre=(HEAD_CENTRE+d for d in DISPLACEMENT)
    clearance=min_centre+core['low']-bulkhead['high']
    engagement=seal['high']-(max_centre+core['low'])
    assert clearance>=.069 and engagement>=.294
    # Inradius accounts for the actual polygon bore, including arbitrary rotation.
    seat=next(o for o in m['main_for']('Pipe rotor').objects if o.name.endswith(' / rotary bearing seal'))
    bore=min(math.hypot(v.co.x,v.co.y) for v in seat.data.vertices)
    radial_clearance=bore*math.cos(math.pi/96)-sleeve['radius']
    assert radial_clearance>.019
    # Verify actual mesh surfaces at min/default/max over a complete turn.
    head_vertices,head_faces,_=geometry['Pipe rotor head']
    poses=0
    for displacement in (DISPLACEMENT[0],0,DISPLACEMENT[1]):
        for degrees in range(0,360,5):
            transform=Matrix.Translation((0,0,HEAD_CENTRE+displacement))@Matrix.Rotation(math.radians(degrees),4,'Z')
            moving=BVHTree.FromPolygons([transform@v for v in head_vertices],head_faces)
            assert not geometry['Pipe rotor'][2].overlap(moving),(displacement,degrees,'Joint surface collision')
            poses+=1
    return {'closed_solids':checked,'hull_samples':samples,'sweep_poses':poses,
            'head_centre_m':HEAD_CENTRE,'displacement_m':DISPLACEMENT,
            'casing_gap_m':[min_centre-2.5,max_centre-2.5],
            'bottom_clearance_m':clearance,'minimum_engagement_m':engagement,
            'radial_clearance_m':radial_clearance,
            'native_joint':'electric_motor to head block origin; wheel at zero','exported':False}
