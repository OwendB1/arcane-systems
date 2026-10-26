"""Refine the finished reactor exterior in the visible prototype file.

Run once from the before-exterior-detail checkpoint. Dispensers, native ports,
the chamber, subparts, collision and derived geometry are protected by hashes.
"""
import array
import hashlib
import importlib
import json
import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
COLS = importlib.import_module('space-engineers-utilities.seut_collections')
NAME = 'ArcanePower_ReactorPrototype'
PREFIX = 'Reactor exterior / '


def fingerprint(obj):
    h = hashlib.sha256()
    h.update(repr((obj.type, obj.parent.name if obj.parent else None,
                   tuple(v for row in obj.matrix_basis for v in row), dict(obj.items()))).encode())
    if obj.type == 'MESH':
        for items, field, kind, width in ((obj.data.vertices, 'co', 'f', 3), (obj.data.loops, 'vertex_index', 'i', 1)):
            values = array.array(kind, [0])*len(items)*width
            items.foreach_get(field, values); h.update(values.tobytes())
        for uv in obj.data.uv_layers:
            values = array.array('f', [0])*len(uv.data)*2
            uv.data.foreach_get('uv', values); h.update(values.tobytes())
        h.update(repr([m.name if m else None for m in obj.data.materials]).encode())
    return h.hexdigest()


def mutable(obj):
    return obj.name.startswith(('Drum segmented armor', 'Lower machinery drum',
        'Circular upper armored housing', 'Cap removable sector', 'Cap rim cooling inset',
        'Cap rim vent louver', 'SEUT / Maintenance Box', 'Heat exchanger fin',
        'Structural spine', 'Spine bolted collar', 'Spine recessed channel',
        'Spine status emitter', 'SEUT / Tech Panel', 'Coolant riser pipe', 'Pipe coupling',
        'SEUT / Wire Vent', 'Integrated support / curved pillar saddle', 'Upper radial bracket')) or (obj.name.startswith('SEUT / Large Screw') and max(v.co.z for v in obj.data.vertices) > 3.5)


def fit_roof_surfaces(col):
    """Seat the thermal roof fittings without coincident visible surfaces."""
    bpy.context.view_layer.update()
    source = lambda o: o.get('reactor_source_name', o.name)
    cap = next(o for o in col.objects if source(o).startswith('Cap central service hatch')
               and min((o.matrix_world @ v.co).z for v in o.data.vertices) > 3.5)
    # Clear the complete 2.04 m seat OD. Burying this edge in the seat left
    # almost-coplanar top faces and a visible intersection at grazing angles.
    # The housing at Z3.525 backs the narrow seam around its full perimeter.
    if min((cap.matrix_world @ v.co).xy.length for v in cap.data.vertices) < 2.049:
        cap.data = cap.data.copy()
        inverse = cap.matrix_world.inverted()
        for vertex in cap.data.vertices:
            point = cap.matrix_world @ vertex.co
            radius = math.hypot(point.x, point.y)
            if radius < 2.1:
                point.x *= 2.05/radius; point.y *= 2.05/radius
                vertex.co = inverse @ point
        cap.data.update()
    if col.get('roof_surface_fit_revision') == 1:
        return {'already_fitted': True, 'cap_opening_radius_m': 2.05}
    targets = [o for o in col.objects if source(o).startswith(
        ('Circular upper armored housing', 'Cap removable sector'))
        and max((o.matrix_world @ v.co).z for v in o.data.vertices) > 3.5]
    receivers = [o for o in col.objects if source(o).startswith('Reactor exterior / service receiver')
                 and o.matrix_world.translation.z > 3.5]
    assert len(receivers) == 16, 'Expected sixteen roof service bays'
    # Recess the complete receiver, rather than cutting only its inner opening.
    # A 10 mm perimeter seam is backed by the housing below the 3.57 m floor.
    for receiver in receivers:
        bpy.ops.mesh.primitive_cube_add(size=1)
        cutter = bpy.context.object
        cutter.data.materials.clear(); cutter.data.materials.append(bpy.data.materials['Metal_Dull'])
        cutter.dimensions = (1.08, 1.05, .24)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        bevel = cutter.modifiers.new('Receiver corner clearance', 'BEVEL')
        bevel.width = .024; bevel.segments = 1
        bpy.ops.object.modifier_apply(modifier=bevel.name)
        cutter.matrix_world = receiver.matrix_world @ Matrix.Translation((0, 0, -.057))
        bpy.context.view_layer.update()
        cp = [cutter.matrix_world @ Vector(v) for v in cutter.bound_box]
        for obj in targets:
            op = [obj.matrix_world @ Vector(v) for v in obj.bound_box]
            if any(max(p[i] for p in op) < min(p[i] for p in cp)
                   or min(p[i] for p in op) > max(p[i] for p in cp) for i in range(3)):
                continue
            if obj.data.users > 1: obj.data = obj.data.copy()
            mod = obj.modifiers.new('Full roof receiver recess', 'BOOLEAN')
            mod.operation = 'DIFFERENCE'; mod.solver = 'EXACT'; mod.object = cutter
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(cutter, do_unlink=True)
    # Boolean walls need their own projected UVs; retain all usable old UVs.
    for obj in targets:
        mesh = obj.data
        bm = bmesh.new(); bm.from_mesh(mesh)
        bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=.00001)
        bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=.000005)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        assert all(e.is_manifold for e in bm.edges), obj.name+': open roof solid'
        bm.to_mesh(mesh); bm.free()
        mesh.calc_loop_triangles(); uv = mesh.uv_layers.active.data
        collapsed = {t.polygon_index for t in mesh.loop_triangles if t.area > 1e-8
            and abs((uv[t.loops[1]].uv-uv[t.loops[0]].uv).cross(
                    uv[t.loops[2]].uv-uv[t.loops[0]].uv)) < 1e-11}
        for index in collapsed:
            face = mesh.polygons[index]
            axes = [i for i in range(3) if i != max(range(3), key=lambda j: abs(face.normal[j]))]
            for loop in face.loop_indices:
                p = mesh.vertices[mesh.loops[loop].vertex_index].co
                uv[loop].uv = (p[axes[0]]*.8+.17, p[axes[1]]*.8+.41)
    screws = 0
    for obj in col.objects:
        if not source(obj).startswith('Reactor exterior / native screw face'): continue
        if min((obj.matrix_world @ v.co).z for v in obj.data.vertices) < 3.5: continue
        body = bpy.data.objects[obj['fastener_body']]
        top = max((body.matrix_world @ v.co).z for v in body.data.vertices)
        # Half-precision native positions collapsed the old 0.5 mm decal gap.
        obj.data = obj.data.copy(); inverse = obj.matrix_world.inverted()
        for vertex in obj.data.vertices:
            point = obj.matrix_world @ vertex.co; point.z = min(top+.002, 3.75)
            vertex.co = inverse @ point
        obj.data.update(); screws += 1
    col['roof_surface_fit_revision'] = 1
    return {'receiver_recesses': len(receivers), 'screw_faces': screws, 'cap_opening_radius_m': 2.05}


def main():
    scene = bpy.data.scenes[NAME]
    assert not scene.get('exterior_detail_revision'), 'Refinement already applied'
    bpy.context.window.scene = scene; bpy.context.view_layer.update()
    cols = COLS.get_collections(scene); col = cols['main'][0]
    root = next(o for o in col.objects if o.parent is None)
    folder = ROOT/'validation/reactor-exterior-loop-01'; folder.mkdir(exist_ok=True)

    def checkpoint():
        bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/arcane-power-exterior-work-in-progress.blend'),copy=True)
    protected = {o for s in bpy.data.scenes if s.name.startswith('ArcanePower_')
                 for c in s.collection.children_recursive for o in c.objects}
    protected -= {o for o in col.objects if mutable(o)}
    baseline = {o.name: fingerprint(o) for o in protected}
    native = {m.name: m for m in bpy.data.materials if m.library}
    assets = Path.home()/'.local/share/blender-se1-setup/assets'
    if 'BlackMattePlastic' not in native:
        with bpy.data.libraries.load(str(assets/'Materials/Materials.blend'), link=True) as (source, target):
            target.materials = ['BlackMattePlastic']
        native['BlackMattePlastic'] = target.materials[0]
    with bpy.data.libraries.load(str(assets/'Models/Decals/Atlas3.blend'), link=False) as (source, target):
        target.objects = ['Large Screw']
    screw_mesh = target.objects[0].data.copy(); bpy.data.objects.remove(target.objects[0], do_unlink=True)
    with bpy.data.libraries.load(str(assets/'Models/Decals/TextAtlas.blend'), link=False) as (source, target):
        target.objects = ['1', '2', '3', '4']
    glyphs = {key: o.data.copy() for key, o in zip(('1', '2', '3', '4'), target.objects)}
    for o in target.objects: bpy.data.objects.remove(o, do_unlink=True)

    def finish(obj, label, material):
        obj.name = PREFIX+label; obj.parent = root
        for c in list(obj.users_collection): c.objects.unlink(obj)
        col.objects.link(obj); obj.data.materials.clear(); obj.data.materials.append(native[material])
        uv = obj.data.uv_layers.active or obj.data.uv_layers.new(name='UVMap')
        for face in obj.data.polygons:
            axes = [i for i in range(3) if i != max(range(3), key=lambda a: abs(face.normal[a]))]
            for index in face.loop_indices:
                p = obj.data.vertices[obj.data.loops[index].vertex_index].co
                uv.data[index].uv = (p[axes[0]]*.4, p[axes[1]]*.4)
        return obj

    def box(label, frame, position, size, material='PaintedMetal_Darker', chamfer=.006):
        bpy.ops.mesh.primitive_cube_add(size=1)
        obj = bpy.context.object; obj.dimensions = size
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        if chamfer:
            mod = obj.modifiers.new('Single flat chamfer', 'BEVEL'); mod.width = chamfer; mod.segments = 1
            bpy.ops.object.modifier_apply(modifier=mod.name)
        finish(obj, label, material); obj.matrix_basis = frame @ Matrix.Translation(position)
        return obj

    def cut(cutter, targets):
        bpy.context.view_layer.update()
        cp = [cutter.matrix_world @ Vector(v) for v in cutter.bound_box]
        for obj in targets:
            op = [obj.matrix_world @ Vector(v) for v in obj.bound_box]
            if any(max(p[i] for p in op) < min(p[i] for p in cp) or min(p[i] for p in op) > max(p[i] for p in cp) for i in range(3)): continue
            if obj.data.users > 1: obj.data = obj.data.copy()
            mod = obj.modifiers.new('Real service recess', 'BOOLEAN'); mod.operation = 'DIFFERENCE'; mod.solver = 'EXACT'; mod.object = cutter
            bpy.context.view_layer.objects.active = obj; bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(cutter, do_unlink=True)

    def radial(angle, radius, z):
        n = Vector((math.cos(angle), math.sin(angle), 0)); t = Vector((-n.y, n.x, 0))
        frame = Matrix((t, Vector((0, 0, 1)), n)).transposed().to_4x4(); frame.translation = n*radius+Vector((0, 0, z))
        return frame

    def outline(w, h, c):
        return [(-w+c,-h),(w-c,-h),(w,-h+c),(w,h-c),(w-c,h),(-w+c,h),(-w,h-c),(-w,-h+c)]

    def receiver(frame, w, h, targets):
        outer = outline(w/2,h/2,.024); mouth = outline(w/2-.06,h/2-.06,.014); ledge = outline(w/2-.09,h/2-.09,.010)
        loops = [(0,outer),(0,mouth),(-.025,mouth),(-.025,ledge),(-.160,ledge),(-.160,outer)]
        vertices = [(x,y,z) for z,loop in loops for x,y in loop]
        faces = [(k*8+i,k*8+(i+1)%8,((k+1)%6)*8+(i+1)%8,((k+1)%6)*8+i) for k in range(6) for i in range(8)]
        mesh = bpy.data.meshes.new('Stepped service receiver'); mesh.from_pydata(vertices,[],faces)
        bm = bmesh.new(); bm.from_mesh(mesh); bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces)); bm.to_mesh(mesh); bm.free(); mesh.update()
        rim = bpy.data.objects.new(PREFIX+'service receiver',mesh); col.objects.link(rim)
        finish(rim,'service receiver','PaintedMetal_Colorable'); rim.matrix_basis = frame
        floor = box('pocket floor',frame,(0,0,-.125),(w-.055,h-.055,.060),'PaintedMetal_VeryDark',.012)
        cut(box('temporary aperture',frame,(0,0,-.04),(w-.12,h-.12,.32),chamfer=.014),targets)
        return rim, floor

    def native_face(mesh, label, frame, x, y, z, width, body=None):
        mesh = mesh.copy(); ps = [v.co for v in mesh.vertices]
        low = Vector([min(p[i] for p in ps) for i in range(3)]); high = Vector([max(p[i] for p in ps) for i in range(3)])
        scale = width/(high.x-low.x)
        mesh.transform(frame @ Matrix.Translation((x,y,z)) @ Matrix.Scale(scale,4) @ Matrix.Translation((-(low.x+high.x)/2,-(low.y+high.y)/2,-low.z)))
        for i,m in enumerate(mesh.materials): mesh.materials[i] = native.get(m.name.split('.')[0],m)
        obj = bpy.data.objects.new(PREFIX+label,mesh); col.objects.link(obj); obj.parent = root; obj['source_asset'] = 'SEUT native atlas; UVs preserved'
        if body: obj['fastener_body'] = body.name
        return obj

    def bolt(frame, x, y, support, front=-.003):
        bpy.ops.mesh.primitive_cylinder_add(vertices=8,radius=.014,depth=.008)
        obj = finish(bpy.context.object,'captive screw','Metal_Shiny'); obj.matrix_basis = frame @ Matrix.Translation((x,y,front-.002)); obj['support'] = support.name
        native_face(screw_mesh,'native screw face',frame,x,y,front+.0025,.024,obj)
        return obj

    def number(frame, key, x, y, front=-.003):
        box('equipment number stock',frame,(x,y,front+.001),(.080,.105,.004),'BlackMattePlastic',.003)
        native_face(glyphs[key],'native equipment number',frame,x,y,front+.0035,.035)

    def door(frame, w, h, floor, key, roof=False):
        thick = .110 if roof else .028
        panel = box('flush access door',frame,(0,0,-.003-thick/2),(w,h,thick),'PaintedMetal_Darker',.014)
        for x in (-w/2+.065,w/2-.065):
            for y in (-h/2+.065,h/2-.065): bolt(frame,x,y,panel)
        if roof:
            cut(box('temporary pull recess',frame,(0,-.10,-.025),(.32,.19,.120),chamfer=.014),[panel])
            for x in (-.105,.105): box('recessed pull foot',frame,(x,-.10,-.063),(.026,.045,.060),'Metal_Dull',.003)
            box('recessed pull grip',frame,(0,-.10,-.029),(.235,.035,.020),'Metal_Shiny',.003)
        else:
            for x in (-.085,.085): box('panel pull foot',frame,(x,-h*.17,.008),(.030,.045,.035),'Metal_Dull',.003)
            box('panel pull grip',frame,(0,-h*.17,.027),(.200,.032,.019),'Metal_Shiny',.003)
        number(frame,key,0,h*.24)
        return panel

    def vent(frame, w, h, rim, count=6):
        for i in range(count):
            y=-h/2+(i+.5)*h/count
            vane=box('recessed louver',frame,(0,y,-.055),(w,.054,.090),'Metal_Dull',.003)
            vane.matrix_basis = frame @ Matrix.Translation((0,y,-.055)) @ Matrix.Rotation(math.radians(25),4,'X'); vane['support'] = rim.name

    # Lower service bays: cardinal native inventory and upgrade faces stay clear.
    armor = [o for o in col.objects if o.name.startswith('Drum segmented armor')]
    lower = next(o for o in col.objects if o.name.startswith('Lower machinery drum'))
    upper = next(o for o in col.objects if o.name.startswith('Circular upper armored housing'))
    roof_sectors = [o for o in col.objects if o.name.startswith('Cap removable sector')]
    for obj in list(col.objects):
        if obj.name.startswith(('SEUT / Maintenance Box','Heat exchanger fin','Cap rim cooling inset','Cap rim vent louver','SEUT / Wire Vent')) or (obj.name.startswith('SEUT / Large Screw') and max(v.co.z for v in obj.data.vertices)>3.5):
            bpy.data.objects.remove(obj,do_unlink=True)
    for quadrant in range(4):
        for style in range(4):
            angle=math.radians(22.5+15*style+90*quadrant); frame=radial(angle,6.163,-2.32)
            rim,floor=receiver(frame,1.16,1.08,[lower]+armor)
            if style==0:
                door(frame,1.026,.946,floor,'1')
                for y in (-.27,.27): box('door hinge',frame,(-.520,y,-.012),(.064,.100,.070),'Metal_Dull',.004)
            elif style==1:
                vent(frame,1.02,.86,rim,7)
                for x in (-.545,.545):
                    for y in (-.46,.46): bolt(frame,x,y,rim,0)
            elif style==2:
                for x,key in ((-.26,'2'),(.26,'3')):
                    f=frame @ Matrix.Translation((x,0,0));door(f,.494,.946,floor,key)
                box('split-door mullion',frame,(0,0,-.085),(.060,.96,.12),'Metal_Dull',.003)
            else:
                door(frame @ Matrix.Translation((0,.20,0)),1.026,.535,floor,'4')
                box('service-bay divider',frame,(0,-.10,-.085),(1.04,.080,.12),'Metal_Dull',.003)
                vent(frame @ Matrix.Translation((0,-.31,0)),1.02,.30,rim,3)
        checkpoint()
    # Roof sectors get alternating flush inspection hatches and deep vent trays.
    for i in range(16):
        angle=(i+.5)*math.tau/16
        frame=Matrix.Translation((5.05*math.cos(angle),5.05*math.sin(angle),3.747)) @ Matrix.Rotation(angle+math.pi/2,4,'Z')
        rim,floor=receiver(frame,1.06,1.03,[upper]+roof_sectors)
        if i%2:door(frame,.926,.896,floor,str(i//4+1),True)
        else:
            vent(frame,.92,.87,rim,7)
            for x in (-.475,.475):
                for y in (-.46,.46):bolt(frame,x,y,rim,0)
    checkpoint()
    # Bulkier spine jackets, with open pipe channels and hard end yokes.
    for obj in list(col.objects):
        if obj.name.startswith(('Structural spine','Spine bolted collar','Spine recessed channel')):bpy.data.objects.remove(obj,do_unlink=True)
    for i in range(4):
        angle=-math.pi/4+i*math.pi/2; frame=radial(angle,5.10,.80)
        body=box('chamfered pillar jacket',frame,(0,0,0),(1.60,3.80,1.00),'PaintedMetal_Colorable',.045)
        for x in (-.564,.564):
            cut(box('temporary pipe channel',frame,(x,0,.36),(.40,3.92,.46),chamfer=.018),[body])
        # Physical access cover below the existing status emitter.
        f=radial(angle,5.602,-.29);rim,floor=receiver(f,.70,.84,[body]);door(f,.566,.706,floor,str(i+1))
        f=radial(angle,5.602,1.99);rim,floor=receiver(f,.70,.45,[body]);vent(f,.56,.29,rim,3)
        box('pillar status backing',radial(angle,5.575,1.031),(0,0,0),(.180,1.13,.050),'PaintedMetal_VeryDark',.008)
        for z in (-.94,2.43):
            f=radial(angle,5.29,z);yoke=box('pillar end yoke',f,(0,0,0),(1.70,.22,.48),'Metal_Dull',.025)
            for x in (-.72,.72):bolt(f @ Matrix.Translation((0,0,.24)),x,0,yoke,0)
    for obj in col.objects:
        if not obj.name.startswith(('Coolant riser pipe','Pipe coupling','Spine status emitter','SEUT / Tech Panel')):continue
        ps=[obj.matrix_world @ v.co for v in obj.data.vertices];center=sum(ps,Vector())/len(ps)
        angle=min((-math.pi/4+i*math.pi/2 for i in range(4)),key=lambda a:abs((math.atan2(center.y,center.x)-a+math.pi)%math.tau-math.pi))
        n=Vector((math.cos(angle),math.sin(angle),0))
        delta=.44 if obj.name.startswith(('Coolant riser pipe','Pipe coupling')) else (.060 if obj.name.startswith('Spine status emitter') else .1005)
        if obj.data.users>1:obj.data=obj.data.copy()
        obj.data.transform(Matrix.Translation(n*delta));obj.data.update()
    import runpy
    runpy.run_path(str(ROOT/'assets/refine_reactor_band.py'),run_name='__main__')
    runpy.run_path(str(ROOT/'assets/refine_reactor_pillars.py'),run_name='__main__')
    runpy.run_path(str(ROOT/'assets/refine_reactor_dispenser_mounts.py'),run_name='__main__')
    for name,sha in baseline.items():assert fingerprint(bpy.data.objects[name])==sha,'Protected object changed: '+name
    scene['exterior_detail_revision']=1
    scene['exterior_detail_scope']='Finished housing and bulkier chamfered pillars; dispensers, native interfaces, chamber, subparts, collision and construction art preserved'
    report={'revision':1,'protected_objects':baseline,'dispensers_unchanged':True,'native_interfaces_unchanged':True,'main_source':str(Path(__file__).resolve()),'live_game_checked':False}
    (folder/'source.json').write_text(json.dumps(report,indent=2)+'\n')
    runpy.run_path(str(ROOT/'assets/detail_native_textures.py'))['main']()
    bpy.context.view_layer.update()
    checkpoint()
    return {'revision':1,'new_meshes':sum(o.name.startswith(PREFIX) for o in col.objects),'protected_objects':len(baseline)}


if __name__=='__main__':result=main()
