"""Native glass pressure walls, hollow inspection casings and shaft-local rotors.

Apply after the settled geometry/texture stages, in the live production file.
Preview angles are authoring controls; ThermalRotors.cs owns in-game motion.
"""
import json
import math
import bisect
import time
from pathlib import Path
import runpy

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(str(ROOT/'assets/build_thermal_models.py'))
RIG = json.loads((ROOT/'assets/thermal-rotor-runtime.json').read_text())
REVISION = 2
SHAFT_Z = M['CONTRACT']['TRAIN_SHAFT_Z']
CENTRES = M['CONTRACT']['TRAIN_CENTRES']


def nearest(point, path):
    candidates = []
    for a, b in zip(path, path[1:]):
        axis = b-a
        at = a+axis*max(0, min(1, (point-a).dot(axis)/axis.length_squared))
        candidates.append(((point-at).length_squared, at))
    return min(candidates, key=lambda r: r[0])[1]


def glass_slots(p, obj):
    # Reuse the reactor's registered native glass and its repaired Blender
    # preview. Stock SEUT GlassOutside loses packed alpha in the library TIF.
    material = bpy.data.materials['ArcanePower_ClearChamber']
    assert material.seut.technique == 'GLASS'
    if material.name not in obj.data.materials:
        obj.data.materials.append(material)
    index = obj.data.materials.find(material.name)
    return index, index


def transparent_pipes(p):
    changed = 0
    for obj in list(p.col.objects):
        branch = ' / connected ' in obj.name
        if obj.type != 'MESH' or not (obj.get('pipe_path') or branch):
            continue
        if branch:
            z = .46 if 'connected H ' in obj.name else -.46
            paths = [[Vector((-1.25, 0, z)), Vector((1.25, 0, z))],
                     [Vector((0, 0, z)), Vector((0, 1.25, z))]]
            if p.col.get('pipe_shape') == 'Cross':
                paths.append([Vector((0, 0, z)), Vector((0, -1.25, z))])
        else:
            path = list(map(Vector, json.loads(obj['pipe_path'])))
            if obj.get('pipe_radius', 0) > .36 or sum((b-a).length for a, b in zip(path, path[1:])) < .55:
                continue
            # Preserve electrical conduits, pressure lips and short socket collars.
            if obj.get('pipe_radius', 0) < .20:
                continue
            paths = [path]
        if obj.data.users > 1:
            obj.data = obj.data.copy()
        outside, inside = glass_slots(p, obj)
        ends = [path[-1] for path in paths]
        ends.append(paths[0][0])
        for face in obj.data.polygons:
            point = obj.matrix_world@face.center
            if min((point-end).length for end in ends) < .40:
                continue
            at = min((nearest(point, path) for path in paths), key=lambda c: (point-c).length_squared)
            normal = obj.matrix_world.to_3x3()@face.normal
            face.material_index = outside if normal.dot(point-at) > 0 else inside
        obj['thermal_pressure_glass'] = True
        obj['thermal_visibility_revision'] = REVISION
        changed += 1
    return changed


def inspection_casing(p, label, x, length, radius):
    old = next(o for o in p.col.objects if o.name.startswith(p.name+' / '+label+' casing'))
    if label == 'generator':
        x = M['CONTRACT']['generator_x'](x)
        length *= M['CONTRACT']['TRAIN_GENERATOR_STRETCH']
    # End collars and the original split band/cradle seats stay metal. The two
    # upper side apertures contain glass through the full pressure-wall thickness.
    # Leave a full nozzle diameter and clearance between end/window flanges.
    window = length*({'turbine': .275, 'compressor': .20, 'generator': .395}[label])
    left, right = x-window, x+window
    rear = M['CONTRACT']['TRAIN_GENERATOR_REAR'] if label == 'generator' else x+length/2
    obj = p.tube('temporary inspection casing', [(x-length/2, 0, SHAFT_Z),
        (left, 0, SHAFT_Z), (right, 0, SHAFT_Z), (rear, 0, SHAFT_Z)],
        radius, 'PaintedMetal_Darker', .12, 48)
    angles = (22.5,82.5,277.5,337.5)
    if label == 'generator':
        top, bottom = math.cos(math.radians(22.5)), math.cos(math.radians(82.5))
        middle, half_height = (top+bottom)/2, (top-bottom)*.4
        a,b = (math.degrees(math.acos(v)) for v in (middle+half_height,middle-half_height))
        angles = (a,b,360-b,360-a)
        knots = (0,22.5,82.5,90,180,270,277.5,337.5,360)
        targets = (0,a,b,90,180,270,360-b,360-a,360)
        for vertex in obj.data.vertices:
            point = vertex.co
            angle = math.degrees(math.atan2(-point.y,point.z-SHAFT_Z)) % 360
            interval = min(len(knots)-2,bisect.bisect_right(knots,angle)-1)
            t = (angle-knots[interval])/(knots[interval+1]-knots[interval])
            mapped = math.radians(targets[interval]+t*(targets[interval+1]-targets[interval]))
            r = math.hypot(point.y,point.z-SHAFT_Z)
            point.y,point.z = -r*math.sin(mapped),SHAFT_Z+r*math.cos(mapped)
        obj.data.update(); M['BUILD']['uv'](obj)
    outside, inside = glass_slots(p, obj)
    armor = None
    if p.name.endswith(' upgraded'):
        armor = len(obj.data.materials)
        obj.data.materials.append(p.native['PaintedMetal_Colorable'])
    for face in obj.data.polygons:
        c = face.center
        angle = math.degrees(math.atan2(-c.y, c.z-SHAFT_Z)) % 360
        if left < c.x < right and (angles[0] < angle < angles[1] or
                (label != 'generator' and angles[2] < angle < angles[3])):
            radial = Vector((0, c.y, c.z-SHAFT_Z))
            face.material_index = outside if face.normal.dot(radial) > 0 else inside
        elif armor is not None and face.normal.dot(Vector((0,c.y,c.z-SHAFT_Z))) > .2:
            face.material_index = armor
    old.data = obj.data
    old['thermal_hollow_casing'] = True
    old['thermal_pressure_wall_m'] = .12
    old['thermal_window_x'] = (left, right)
    old['thermal_window_angles_deg'] = angles
    if label == 'generator':
        old['thermal_window_height_factor'] = .8
        old['thermal_single_sided_window'] = True
    old['thermal_visibility_revision'] = REVISION
    bpy.data.objects.remove(obj, do_unlink=True)
    # Narrow machined rails cover the aperture edges, with supported captive
    # fasteners; no opaque panel or former decorative rib blocks the window.
    for degrees in (angles[:2] if label == 'generator' else angles):
        a = math.radians(degrees)
        radial = Vector((0, -math.sin(a), math.cos(a)))
        rail = p.box(label+' inspection window rail', (x, 0, SHAFT_Z),
                     (right-left+.10, .065, .055), 'Metal_Dull', .003)
        rail.rotation_euler.x = a
        rail.location += radial*(radius+.017)
        rail['thermal_seated_on'] = old.name
        for sx in (left+.10, x, right-.10):
            point = Vector((sx, 0, SHAFT_Z))+radial*(radius+.043)
            p.bolt(label+' window captive stud', point, radial, rail, .022)
    for sx in (left-.025, right+.025):
        frame = p.tube(label+' inspection window end frame',
                       [(sx-.025, 0, SHAFT_Z), (sx+.025, 0, SHAFT_Z)],
                       radius+.027, 'Metal_Dull', .045, 96)
        frame['thermal_seated_on'] = old.name
    return old


def casing_sector(p,label,x0,x1,inner,outer,a0,a1,material):
    """A closed pressure-jacket segment seated on a curved housing."""
    steps=math.ceil(abs(a1-a0)/3)
    angles=[math.radians(a0+(a1-a0)*i/steps) for i in range(steps+1)]
    n=len(angles)
    verts=[(x,-r*math.sin(a),SHAFT_Z+r*math.cos(a))
           for x in (x0,x1) for r in (inner,outer) for a in angles]
    faces=[]
    for a,b in ((0,n),(n,3*n),(3*n,2*n),(2*n,0)):
        faces.extend((a+j,a+j+1,b+j+1,b+j) for j in range(n-1))
    faces.extend(((0,n,3*n,2*n),(n-1,2*n-1,4*n-1,3*n-1)))
    obj=p.mesh(label,verts,faces,material)
    obj['thermal_upgrade_jacket']=True
    return obj


def upgrade_jackets(p,casings,generator):
    if not p.name.endswith(' upgraded'):return
    x=CENTRES['turbine']
    for dx in (-.30,.30):
        obj=casing_sector(p,'high temperature crown cassette',x+dx-.23,x+dx+.23,
                           1.845,1.96,-18,18,'PaintedMetal_Colorable')
        obj['thermal_seated_on']=casings['turbine'].name
        for degrees in (-12,12):
            a=math.radians(degrees)
            normal=Vector((0,-math.sin(a),math.cos(a)))
            p.bolt('crown cassette captive stud',Vector((x+dx,0,SHAFT_Z))+normal*1.965,
                   normal,obj,.025)
    for dx in (-.26,0,.26):
        x=M['CONTRACT']['generator_x'](CENTRES['generator']+dx)
        obj=casing_sector(p,'upgraded lower stator cooling fin',x-.05,
            x+.05,1.615,1.735,108,148,'Metal_Dull')
        obj['thermal_seated_on']=generator.name


def transition_casing(p, label, start, end, r0, r1, window=False):
    """Closed annular shell, with glazed sectors through its full wall."""
    sides = 96
    stations = [start, start+.15, end-.15, end] if window else [start, end]
    def radius(x): return r0+(r1-r0)*(x-start)/(end-start)
    verts = [(x, -r*math.sin(j*math.tau/sides), SHAFT_Z+r*math.cos(j*math.tau/sides))
             for x in stations for r in (radius(x), radius(x)-.12) for j in range(sides)]
    faces = []
    for k in range(len(stations)-1):
        for ring in (0, 1):
            a, b = k*2*sides+ring*sides, (k+1)*2*sides+ring*sides
            faces += [(a+j, a+(j+1)%sides, b+(j+1)%sides, b+j) for j in range(sides)]
    for k in (0, len(stations)-1):
        a = k*2*sides
        faces += [(a+j,a+(j+1)%sides,a+sides+(j+1)%sides,a+sides+j) for j in range(sides)]
    obj = p.mesh(label, verts, faces, 'PaintedMetal_Darker')
    obj['thermal_pressure_wall_m'] = .12
    obj['thermal_transition_span'] = (start, end)
    obj['thermal_transition_radii'] = (r0, r1)
    glass, _ = glass_slots(p, obj) if window else (0, 0)
    armor=None
    if p.name.endswith(' upgraded'):
        armor=len(obj.data.materials)
        obj.data.materials.append(p.native['PaintedMetal_Colorable'])
    for face in obj.data.polygons:
        c = face.center
        face.use_smooth = face.index < 2*sides*(len(stations)-1)
        angle = math.degrees(math.atan2(-c.y, c.z-SHAFT_Z)) % 360
        if window and stations[1] < c.x < stations[-2] and (22.5 < angle < 82.5 or 277.5 < angle < 337.5):
            face.material_index = glass
        elif armor is not None and face.normal.dot(Vector((0,c.y,c.z-SHAFT_Z))) > .2:
            face.material_index=armor
    if not window: return obj
    obj['thermal_window_x'] = (stations[1], stations[-2])
    obj['thermal_window_angles_deg'] = (22.5, 82.5, 277.5, 337.5)
    # Rails follow the cone generators instead of floating over the slope.
    from mathutils import Matrix
    for degrees in (22.5, 82.5, 277.5, 337.5):
        a = math.radians(degrees)
        radial = Vector((0, -math.sin(a), math.cos(a)))
        left, right = stations[1]-.025, stations[-2]+.025
        pa = Vector((left,0,SHAFT_Z))+radial*(radius(left)+.017)
        pb = Vector((right,0,SHAFT_Z))+radial*(radius(right)+.017)
        along = (pb-pa).normalized()
        tangent = Vector((0,math.cos(a),math.sin(a)))
        normal = along.cross(tangent)
        rail = p.box(label+' inspection window rail', (pa+pb)/2, ((pb-pa).length,.065,.055), 'Metal_Dull', .003)
        rail.rotation_euler = Matrix((along,tangent,normal)).transposed().to_euler()
        rail['thermal_seated_on'] = obj.name
        for x in (left+.10,(left+right)/2,right-.10):
            point = Vector((x,0,SHAFT_Z))+radial*(radius(x)+.017)+normal*.028
            p.bolt(label+' window captive stud',point,normal,rail,.022)
    for x in (stations[1]-.025, stations[-2]+.025):
        frame = p.tube(label+' inspection window end frame',[(x-.025,0,SHAFT_Z),(x+.025,0,SHAFT_Z)],
                       radius(x)+.032,'Metal_Dull',.055,96)
        frame['thermal_seated_on'] = obj.name
    return obj


def generator_armature(p):
    """Wound rotor shares the turbine shaft; bearing supports stay stationary."""
    name = 'ArcanePower_ArmatureCopper'
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = p.native['Metal_Shiny'].copy(); mat.name = name
    if not mat.get('thermal_armature_copper'):
        folder = ROOT/'src/Textures/Models/ArcanePower/Thermal'
        # Native packed textures, so copper survives MWM export and armor skins.
        for node, suffix, color in [('CM','cm',(.63,.29,.095,1)),
                                    ('NG','ng',(.5,.5,1,.64)),('ADD','add',(1,0,0,0))]:
            img = bpy.data.images.new('Armature copper '+suffix,width=16,height=16,alpha=True)
            img.colorspace_settings.name = 'sRGB' if suffix == 'cm' else 'Non-Color'
            img.alpha_mode = 'CHANNEL_PACKED'; img.pixels.foreach_set(list(color)*256)
            img.filepath_raw = str(folder/('ArmatureCopper_'+suffix+'.png'))
            img.file_format = 'PNG'; img.save()
            tex = mat.node_tree.nodes.get(node)
            if tex is None:
                tex = mat.node_tree.nodes.new('ShaderNodeTexImage'); tex.name = node
                group = mat.node_tree.nodes['SEUT_NODE_GROUP']
                mat.node_tree.links.new(tex.outputs['Color'],group.inputs[node+' Color'])
                mat.node_tree.links.new(tex.outputs['Alpha'],group.inputs[node+' Alpha'])
            tex.image = img
        group = mat.node_tree.nodes['SEUT_NODE_GROUP']
        group.inputs['Color Override Alpha'].default_value = 0
        mat['thermal_armature_copper'] = True
    # SEUT validates texture channel labels as well as node names.
    for channel in ('CM', 'NG', 'ADD'):
        mat.node_tree.nodes[channel].label = channel
    p.native[name] = mat
    steel_name = 'ArcanePower_ArmatureSteel'
    steel = bpy.data.materials.get(steel_name)
    if steel is None:
        steel = p.native['Metal_Dull'].copy(); steel.name = steel_name
        img = bpy.data.images.new('Armature steel laminations',width=64,height=16,alpha=True)
        img.colorspace_settings.name = 'sRGB'; img.alpha_mode = 'CHANNEL_PACKED'
        pixels = []
        for y in range(16):
            for u in range(64):
                tone = .14 if u < 3 else .42
                pixels.extend((tone*.95,tone*.98,tone,1))
        img.pixels.foreach_set(pixels)
        img.filepath_raw = str(ROOT/'src/Textures/Models/ArcanePower/Thermal/ArmatureSteel_cm.png')
        img.file_format = 'PNG'; img.save()
        steel.node_tree.nodes['CM'].image = img
        steel['thermal_laminated_steel'] = True
    p.native[steel_name] = steel
    x = M['CONTRACT']['generator_x'](CENTRES['generator'])
    stretch = M['CONTRACT']['TRAIN_GENERATOR_STRETCH']
    owned = {p.cylinder('generator laminated armature',(x-.81*stretch,0,SHAFT_Z),(x+.81*stretch,0,SHAFT_Z),.80,'Metal_Dull',64)}
    # Salient poles: an I-shaped section from the shaft end, with copper
    # wrapped around the narrow web between the root and broad pole shoe.
    # Twenty-four slotted teeth form a cylindrical laminated armature.
    # Each pole has four close-packed layers of ten rounded turns.
    for i in range(24):
        a = i*math.tau/24+math.pi/48
        radial = Vector((0,math.cos(a),math.sin(a)))
        tangent = Vector((0,-math.sin(a),math.cos(a)))
        def arc(r,angle):
            t = math.radians(angle)
            return (r*math.sin(t),r*math.cos(t))
        section = [arc(.78,-7+j*1.75) for j in range(9)]
        section += [arc(.89,7),(.035,.89),(.035,1.145),arc(1.145,6.5)]
        section += [arc(1.23,6.5-j*1.625) for j in range(9)]
        section += [arc(1.145,-6.5),(-.035,1.145),(-.035,.89),arc(.89,-7)]
        count = len(section)
        verts = [Vector((x+u*stretch,0,SHAFT_Z))+tangent*v+radial*r for u in (-.53,.53) for v,r in section]
        faces = [tuple(reversed(range(count))),tuple(range(count,2*count))]
        faces += [(j,(j+1)%count,(j+1)%count+count,j+count) for j in range(count)]
        pole = p.mesh('generator flanged armature pole',verts,faces,steel_name)
        uv = pole.data.uv_layers.active
        for face in pole.data.polygons:
            if abs(face.normal.x) > .9: continue
            axis = 1 if abs(face.normal.z) > abs(face.normal.y) else 2
            for li in face.loop_indices:
                point = pole.data.vertices[pole.data.loops[li].vertex_index].co
                uv.data[li].uv = ((point.x-x)/.035,point[axis])
        pole['thermal_generator_pole'] = i
        owned.add(pole)
        for layer in range(4):
            verts, faces = [], []
            width, half = .057+layer*.013, (.58+layer*.013)*stretch
            for turn in range(10):
                r = .909+turn*.024
                # Straight slot conductors join true semicircular end turns.
                # Functional conductor curvature is separate from hard-edged
                # housings. Use analytic normals to keep each turn round.
                points = []
                for centre,start in ((half-width,-90),(-half+width,90)):
                    for step in range(13):
                        angle = math.radians(start+step*15)
                        normal = Vector((math.cos(angle),0,0))+tangent*math.sin(angle)
                        point = Vector((x+centre,0,SHAFT_Z))+radial*r+normal*width
                        points.append((point,normal))
                offset = len(verts)
                for j, (point,across) in enumerate(points):
                    verts += [point+radial*(.0107*math.cos(k*math.tau/6))+across*(.006*math.sin(k*math.tau/6)) for k in range(6)]
                    faces += [tuple(offset+v for v in (j*6+k,j*6+(k+1)%6,((j+1)%len(points))*6+(k+1)%6,((j+1)%len(points))*6+k)) for k in range(6)]
            coil = p.mesh('generator copper winding layer',verts,faces,name)
            for face in coil.data.polygons: face.use_smooth = True
            coil['thermal_generator_winding'] = True
            coil['thermal_generator_pole'] = i
            coil['thermal_winding_layer'] = layer
            coil['thermal_winding_turns'] = 10
            owned.add(coil)
    for sign in (-1,1):
        ring = p.tube('generator armature retaining band',[(x+sign*.79*stretch-.035,0,SHAFT_Z),(x+sign*.79*stretch+.035,0,SHAFT_Z)],
                      .84,'Metal_Shiny',.065,64)
        owned.add(ring)
        p.tube('generator stationary bearing',[(x+sign*.86*stretch-.035,0,SHAFT_Z),(x+sign*.86*stretch+.035,0,SHAFT_Z)],
               .40,'Metal_Dull',.15,48)
    for obj in owned: obj['thermal_generator_armature'] = True
    # Fixed magnets follow the casing. The single inspection side uses end
    # tiles reaching toward the centre; the far wall stays fully enclosed.
    for sector in range(24):
        degrees = sector*15
        # The topmost visible row (30 degrees) bridges the full bay.
        window = 37.5 < degrees < 82.5
        spans = ((x-.78*stretch,x-.46*stretch),(x+.46*stretch,x+.78*stretch)) if window else ((x-.78*stretch,x+.78*stretch),)
        # Fourteen-degree tiles on a fifteen-degree pitch leave one degree,
        # one third of the former three-degree inter-magnet clearance.
        angles = [math.radians(degrees-7+j*1.75) for j in range(9)]
        for lo,hi in spans:
            verts = [(sx,-r*math.sin(a),SHAFT_Z+r*math.cos(a)) for sx in (lo,hi) for r in (1.31,1.51) for a in angles]
            faces = []
            for a,b in ((0,9),(9,27),(27,18),(18,0)):
                faces += [(a+j,a+j+1,b+j+1,b+j) for j in range(8)]
            faces += [(0,9,27,18),(8,17,35,26)]
            magnet = p.mesh('generator stationary permanent magnet',verts,faces,'Metal_Shiny')
            bpy.context.view_layer.objects.active = magnet
            bevel = magnet.modifiers.new('Rounded magnet edges','BEVEL')
            bevel.width = .012; bevel.segments = 3; bevel.limit_method = 'ANGLE'; bevel.angle_limit = .35
            bpy.ops.object.modifier_apply(modifier=bevel.name)
            M['BUILD']['uv'](magnet)
            magnet['thermal_generator_magnet'] = True
            magnet['thermal_seated_on'] = next(o.name for o in p.col.objects if o.name.startswith(p.name+' / generator casing'))
    return owned


def blade_row(p, label, x, hub, tip, chord, pitch, count, stage):
    """One export mesh per row, containing closed, twisted airfoil solids."""
    profile = [(-.50, 0), (-.30, .055), (.08, .050), (.48, .012),
               (.50, -.004), (.08, -.025), (-.30, -.030)]
    verts, faces = [], []
    n = len(profile)
    for i in range(count):
        start = len(verts)
        angle = (i+stage*.37)*math.tau/count
        for k in range(5):
            t = k/4
            radius = hub+(tip-hub)*t
            twist = pitch+math.copysign(math.radians(12)*(1-t), pitch)
            for u, v in profile:
                axial = chord*(u*math.cos(twist)-v*math.sin(twist))
                tangent = chord*(u*math.sin(twist)+v*math.cos(twist))
                verts.append((x+axial+.012*t, radius*math.cos(angle)-tangent*math.sin(angle),
                              SHAFT_Z+radius*math.sin(angle)+tangent*math.cos(angle)))
        local = [tuple(reversed(range(n))), tuple(range(4*n, 5*n))]
        local += [(k*n+j, k*n+(j+1)%n, (k+1)*n+(j+1)%n, (k+1)*n+j)
                  for k in range(4) for j in range(n)]
        faces.extend(tuple(start+j for j in f) for f in local)
    obj = p.mesh(label, verts, faces, 'Metal_Shiny')
    for face in obj.data.polygons:
        face.use_smooth = face.index % 30 >= 2
    obj['thermal_blade_count'] = count
    obj['thermal_blade_row'] = stage
    obj['thermal_blade_tip_radius_m'] = tip
    obj['thermal_row_x'] = x
    return obj


def close_rotor_joint(p):
    """Seat the turbine nose over the compressor drum with 20 mm engagement.

    Preserve the blade-bearing drum surface, UVs, pivots and separate rotors.
    The small tapered nose covers the former 200 mm open axial gap.
    """
    obj = next(o for o in p.col.objects if o.name.startswith(p.name+' / turbine tapered rotor drum'))
    if obj.get('thermal_rotor_joint_revision') == 1:
        return obj
    bpy.context.view_layer.update()
    old = obj.data
    world = [obj.matrix_world @ v.co for v in old.vertices]
    front = min(v.x for v in world)
    caps = [f for f in old.polygons if all(abs(world[i].x-front)<1e-5 for i in f.vertices)]
    assert len(caps)==1 and len(caps[0].vertices)==96, 'Unexpected turbine nose topology'
    ring = sorted(caps[0].vertices, key=lambda i:math.atan2(world[i].z-SHAFT_Z,world[i].y))
    vertices = [v.co.copy() for v in old.vertices]
    inverse = obj.matrix_world.inverted()
    for i in ring:
        radial = Vector((0,world[i].y,world[i].z-SHAFT_Z)).normalized()*1.15
        vertices.append(inverse @ Vector((CENTRES['turbine']-1.72,radial.y,SHAFT_Z+radial.z)))
    retained = [f for f in old.polygons if f!=caps[0]]
    faces = [tuple(f.vertices) for f in retained]
    start, count = len(old.vertices), len(ring)
    faces.append(tuple(reversed(range(start,start+count))))
    faces += [(start+j,start+(j+1)%count,ring[(j+1)%count],ring[j]) for j in range(count)]
    mesh = bpy.data.meshes.new(old.name+' / seated nose')
    mesh.from_pydata(vertices,[],faces)
    for material in old.materials:mesh.materials.append(material)
    for layer in old.uv_layers:
        uv = mesh.uv_layers.new(name=layer.name)
        for face, source in zip(mesh.polygons,retained):
            face.material_index=source.material_index;face.use_smooth=source.use_smooth
            for li, old_li in zip(face.loop_indices,source.loop_indices):uv.data[li].uv=layer.data[old_li].uv
        for face in list(mesh.polygons)[len(retained):]:
            cap = face.index==len(retained);face.use_smooth=not cap
            for li in face.loop_indices:
                v=obj.matrix_world @ mesh.vertices[mesh.loops[li].vertex_index].co
                uv.data[li].uv=(v.y*.8,v.z*.8) if cap else (v.x*.8,math.atan2(v.z-SHAFT_Z,v.y)*1.15*.8)
    obj.data=mesh
    obj['thermal_rotor_joint_revision']=1
    return obj


def rotor(p, spec):
    label, pivot = spec['id'], Vector(spec['pivot_blender'])
    root = bpy.data.objects.new(p.name+' / '+spec['subpart'], None)
    p.col.objects.link(root)
    root.location = pivot
    root.empty_display_size = .20
    root['native_subpart'] = spec['subpart']
    root['native_pivot_blender'] = pivot
    root['native_axis_blender'] = (1, 0, 0)
    root['preview_angle_degrees'] = 0.
    root.id_properties_ui('preview_angle_degrees').update(min=0, max=360,
        description='Manual rotor inspection pose; game motion is driven by ThermalRotors.cs')
    turbine = label == 'turbine'
    radius, tip, chord = (1.85, 1.695, .16) if turbine else (1.35, 1.195, .075)
    lo, hi = (pivot.x-.91, pivot.x+.91) if turbine else (pivot.x-.53, pivot.x+.53)
    drum_lo, drum_hi = (pivot.x-1.50, pivot.x+1.50) if turbine else (pivot.x-1.15, CENTRES['turbine']-1.70)
    def hub(x):
        t = (x-drum_lo)/(drum_hi-drum_lo)
        if turbine: return 1.19-.30*t
        knee = pivot.x+1.15
        return .69+.27*(x-drum_lo)/(knee-drum_lo) if x <= knee else .96+.18*(x-knee)/(drum_hi-knee)
    # The continuous tapered drum carries the blade roots; the flow is annular.
    sides = 96
    verts = [(x, hub(x)*math.cos(j*math.tau/sides), SHAFT_Z+hub(x)*math.sin(j*math.tau/sides))
             for x in ((drum_lo, drum_hi) if turbine else (drum_lo,pivot.x+1.15,drum_hi)) for j in range(sides)]
    rings = len(verts)//sides
    faces = [tuple(reversed(range(sides))), tuple(range((rings-1)*sides, rings*sides))]
    faces += [(k*sides+j,k*sides+(j+1)%sides,(k+1)*sides+(j+1)%sides,(k+1)*sides+j)
              for k in range(rings-1) for j in range(sides)]
    drum = p.mesh(label+' tapered rotor drum', verts, faces, 'Metal_Dull')
    for face in drum.data.polygons[2:]:
        face.use_smooth = True
    owned = {drum}
    row_count = spec['rotor_rows']+spec['stator_rows']
    for row in range(row_count):
        x = lo+(hi-lo)*row/(row_count-1)
        rotating = row % 2 == 1
        count = spec['blades_per_row'] if rotating else spec['vanes_per_row']
        obj = blade_row(p, label+(' blade row' if rotating else ' stator vane row'), x,
                        hub(x)-.012 if rotating else hub(x)+.035,
                        tip if rotating else radius-.112, chord,
                        math.radians(32 if rotating else -32), count, row//2+1)
        obj['thermal_rotating'] = rotating
        if rotating:
            owned.add(obj)
        else:
            ring = p.tube(label+' stationary carrier', [(x-.023, 0, SHAFT_Z), (x+.023, 0, SHAFT_Z)],
                          radius-.09, 'Metal_Dull', .035, 96)
            ring['thermal_stator_carrier'] = True
    if not turbine:
        start, end = CENTRES['compressor']+1.21, CENTRES['turbine']-1.575
        count_rows = spec['transition_rotor_rows']+spec['transition_stator_rows']
        def shell_radius(x): return 1.35+.50*max(0,min(1,(x-start)/(end-start)))
        for row in range(count_rows):
            x = pivot.x+.66+(end-.23-pivot.x-.66)*row/(count_rows-1)
            rotating = row % 2 == 0
            outer = shell_radius(x)
            # Leading edge is the smallest bore along each blade's sweep.
            tip = shell_radius(x-.08)-.12-.040 if rotating else outer-.112
            obj = blade_row(p,'compressor'+(' blade row' if rotating else ' stator vane row'),x,
                            hub(x)-.012 if rotating else hub(x)+.045,tip,.13,
                            math.radians(32 if rotating else -32),
                            spec['blades_per_row'] if rotating else spec['vanes_per_row'],8+row//2)
            obj['thermal_rotating'] = rotating
            obj['thermal_transition_stage'] = True
            if rotating: owned.add(obj)
            else:
                ring = p.tube('compressor stationary carrier',[(x-.023,0,SHAFT_Z),(x+.023,0,SHAFT_Z)],
                              outer-.09,'Metal_Dull',.045,96)
                ring['thermal_stator_carrier'] = True
    else:
        owned.update(generator_armature(p))
    shaft_label = 'turbine generator shaft' if turbine else 'independent compressor shaft'
    owned.update(o for o in p.col.objects if o.name.startswith(p.name+' / '+shaft_label))
    bpy.context.view_layer.update()
    for obj in owned:
        world = obj.matrix_world.copy()
        obj.parent = root
        obj.matrix_world = world
        obj['native_subpart'] = spec['subpart']
    driver = root.driver_add('rotation_euler', 0).driver
    var = driver.variables.new()
    var.name = 'angle'
    var.type = 'SINGLE_PROP'
    var.targets[0].id = root
    var.targets[0].data_path = '["preview_angle_degrees"]'
    driver.expression = 'angle*pi/180'
    root['thermal_rotor_tip_clearance_m'] = radius-.12-tip
    if turbine:close_rotor_joint(p)
    return root


def rounded_path(points, radius=.34):
    """Tangent arcs at pipe bends; no decorative housing fillets."""
    points = list(map(Vector, points))
    out = [points[0]]
    for a, b, c in zip(points, points[1:], points[2:]):
        incoming, outgoing = (b-a).normalized(), (c-b).normalized()
        angle = incoming.angle(outgoing)
        if angle < 1e-5:
            continue
        trim = min(radius*math.tan(angle/2), (b-a).length*.48, (c-b).length*.48)
        r = trim/math.tan(angle/2)
        start, end = b-incoming*trim, b+outgoing*trim
        axis = incoming.cross(outgoing).normalized()
        centre = start+axis.cross(incoming)*r
        radial = start-centre
        from mathutils import Quaternion
        out.extend(centre+Quaternion(axis, angle*j/8)@radial for j in range(9))
    return [list(p) for p in out+[points[-1]]]


def compressor_cable(p):
    """A round cable follows tangent bends above the deck, with a seated gland."""
    cx,bx=CENTRES['compressor'],CENTRES['cabinet']
    for obj in list(p.col.objects):
        if ' / compressor supply conduit' in obj.name or ' / cabinet cable gland' in obj.name:
            bpy.data.objects.remove(obj,do_unlink=True)
    path=rounded_path(((bx,-1.11,-1.77),(bx,-1.45,-1.77),(bx,-2.00,-1.91),
        (cx-1.73,-2.00,-1.91),(cx-1.73,-2.00,SHAFT_Z),
        (cx-1.73,-.90,SHAFT_Z),(cx-1.49,-.72,SHAFT_Z)),.24)
    side=1 if ' mirrored' in p.name else -1
    if side==1:path=[(x,-y,z) for x,y,z in path]
    cable=p.tube('compressor supply conduit',path,.09,'PaintedMetal_VeryDark',.025,24)
    cable['thermal_cable_bend_radius']=.24
    p.tube('cabinet cable gland',((bx,side*1.13,-1.77),(bx,side*1.27,-1.77)),
           .125,'Metal_Dull',.04,24)
    return cable


def end_plenum_pipes(p, casings):
    # One duplex socket: H enters the compressor front, crosses its expanding
    # pressure casing directly into the turbine, then C returns from the rear.
    channels = [
        ('hot compressor inlet', 'compressor', -1, CENTRES['compressor']-.87, -.79, True),
        ('cold rear return', 'turbine', -1, CENTRES['turbine']+1.29, -1.71, False),
    ]
    for label, machine, sign, x, height, front in channels:
        radius = 1.85 if machine == 'turbine' else 1.35
        run_y = 1.55 if sign < 0 else 2.17
        normal = Vector((0, sign*run_y, height-SHAFT_Z)).normalized()
        origin = Vector((x, 0, SHAFT_Z))
        centre = origin+normal*radius
        end = origin+normal*(radius-.20)
        lead = Vector((x, sign*run_y, height))
        start = Vector((M['CONTRACT']['TRAIN_PORTS'][0]['position'][0], sign*2.5, height))
        if sign < 0:
            if front:
                # Tangent S transition into casing 1, with a straight socket
                # neck and radial nozzle neck instead of two cramped elbows.
                neck = start+Vector((0, .40, 0))
                lead = centre+normal*.26
                a, b = neck+Vector((0, .28, 0)), lead+normal*.32
                curve = [(1-t)**3*neck+3*(1-t)**2*t*a+3*(1-t)*t*t*b+t**3*lead
                         for t in (i/20 for i in range(21))]
                path = [start]+curve+[end]
            else:
                path = rounded_path([start, (start.x, -run_y, height), lead, end], .48)
            pipe = p.tube(label, path, .29, 'Metal_Dull', .045, 32)
            pipe['thermal_gas_channel'] = True
        casing = casings[machine]
        cutter = p.cylinder('temporary end plenum bore', centre-normal*.35,
                            centre+normal*.40, .305, sides=32)
        bands = [o for o in p.col.objects if any(o.name.startswith(p.name+' / '+machine+part)
                 for part in (' split casing band', ' stepped end flange', ' inspection window end frame'))]
        for target in [casing]+bands:
            bpy.context.view_layer.objects.active = target
            mod = target.modifiers.new('Seated '+label+' bore', 'BOOLEAN')
            mod.operation, mod.solver, mod.object = 'DIFFERENCE', 'EXACT', cutter
            bpy.ops.object.modifier_apply(modifier=mod.name)
            M['BUILD']['uv'](target)
        bpy.data.objects.remove(cutter, do_unlink=True)
        collar = p.tube(label+' nozzle collar', [centre-normal*.11, centre+normal*.10], .365, 'Metal_Dull', .060, 32)
        collar['thermal_nozzle_collar'] = True
        collar['thermal_flow_machine'] = machine
        collar['thermal_flow_end'] = 'front' if front else 'rear'
        collar['thermal_flow_channel'] = label
        collar['thermal_nozzle_centre'] = centre
        collar['thermal_nozzle_normal'] = normal
    clear_pipe_supports(p)
    for casing in casings.values():
        M['BUILD']['uv'](casing)


def clear_pipe_supports(p):
    """Closed service bores in load cradles; clearance for socket brackets."""
    import bmesh
    from mathutils.bvhtree import BVHTree
    def tree(obj):
        return BVHTree.FromPolygons([obj.matrix_world@v.co for v in obj.data.vertices],
                                   [list(f.vertices) for f in obj.data.polygons])
    runpy.run_path(str(ROOT/'assets/refine_train_supports.py'))['refine'](p)
    supports = [o for o in p.col.objects if 'manifold skid bracket' in o.name]
    for pipe in list(p.col.objects):
        if not pipe.get('thermal_gas_channel') and not pipe.get('thermal_nozzle_collar') and not pipe.get('thermal_strut_fitting') and 'compressor supply conduit' not in pipe.name:
            continue
        path = list(map(Vector, json.loads(pipe['pipe_path'])))
        path[0] -= (path[1]-path[0]).normalized()*.04
        path[-1] += (path[-1]-path[-2]).normalized()*.04
        cutter = p.tube('temporary support clearance', path, pipe['pipe_radius']+.035, 'Metal_Dull', .045, 32)
        mesh = bmesh.new();mesh.from_mesh(cutter.data);mesh.verts.ensure_lookup_table()
        bmesh.ops.delete(mesh, geom=[v for v in mesh.verts if v.index%64 >= 32], context='VERTS')
        bmesh.ops.holes_fill(mesh, edges=[e for e in mesh.edges if e.is_boundary], sides=0)
        bmesh.ops.recalc_face_normals(mesh, faces=list(mesh.faces));mesh.to_mesh(cutter.data);mesh.free()
        clearance = tree(cutter)
        for support in supports:
            if not clearance.overlap(tree(support)):continue
            bpy.context.view_layer.objects.active = support
            mod = support.modifiers.new('Pipe clearance pocket', 'BOOLEAN')
            mod.operation, mod.solver, mod.object = 'DIFFERENCE', 'EXACT', cutter
            bpy.ops.object.modifier_apply(modifier=mod.name)
            support['thermal_pipe_clearance_m'] = .035
            M['BUILD']['uv'](support)
        bpy.data.objects.remove(cutter, do_unlink=True)


def apply(name):
    assert name != 'Reactor housing', 'Preserve the accepted reactor/manifold rig'
    p = M['Parts'](name, existing=True)
    if p.scene.get('thermal_visibility_revision') == REVISION:
        return {'model': name, 'status': 'current'}
    assert not name.startswith('Brayton train') or not p.scene.get('thermal_visibility_revision'), 'Rebuild the train base when changing the mechanical revision'
    assert p.scene['thermal_phase'] == 'textures'
    before = set(p.col.objects)
    pipes = 0
    if name.startswith('Brayton train'):
        for obj in list(p.col.objects):
            if obj.name.startswith(p.name+' / turbine inspection rib'):
                bpy.data.objects.remove(obj, do_unlink=True)
        casings = {'turbine': inspection_casing(p, 'turbine', CENTRES['turbine'], 3.15, 1.85),
                   'compressor': inspection_casing(p, 'compressor', CENTRES['compressor'], 2.42, 1.35)}
        generator = inspection_casing(p,'generator',CENTRES['generator'],2.0,1.62)
        runpy.run_path(str(ROOT/'assets/refine_thermal_models.py'))['mark'](
            p, generator, 'Tech Panel', (M['CONTRACT']['generator_x'](CENTRES['generator']),1.622,SHAFT_Z),
            (-1,0,0), (0,0,1), .40, 'Atlas3')
        upgrade_jackets(p,casings,generator)
        old = next(o for o in p.col.objects if o.get('thermal_compressor_transition'))
        bpy.data.objects.remove(old,do_unlink=True)
        taper = transition_casing(p,'compressor expanding casing',CENTRES['compressor']+1.21,
                                  CENTRES['turbine']-1.575,1.35,1.85,window=True)
        taper['thermal_compressor_transition'] = True
        taper = transition_casing(p,'generator steep transition',CENTRES['turbine']+1.575,
                                  CENTRES['generator']-1,1.85,1.62)
        taper['thermal_generator_transition'] = True
        compressor_cable(p)
        end_plenum_pipes(p, casings)
        for spec in RIG['rotors']:
            rotor(p, spec)
    pipes = transparent_pipes(p)
    if name.startswith('Brayton train'):
        runpy.run_path(str(ROOT/'assets/refine_train_service_details.py'))['apply'](p)
    for obj in set(p.col.objects)-before:
        obj['thermal_visibility_revision'] = REVISION
    p.scene['thermal_visibility_revision'] = REVISION
    bpy.context.view_layer.update()
    M['record'](name)
    return {'model': name, 'transparent_pipes': pipes, 'rotors': 2 if name.startswith('Brayton train') else 0}


def preview(name, samples_path, start=0, duration=60):
    """Replay compiled C# samples [time, phases, rpms, pressure, heat] in the UI.

    No Blender action is exported. Changing scene or setting the returned state's
    running flag false stops the preview and restores the zero authoring pose.
    """
    samples = json.loads(Path(samples_path).read_text())
    assert samples and all(len(row) == 7 and all(math.isfinite(v) for v in row) for row in samples)
    times = [row[0] for row in samples]
    assert all(a < b for a, b in zip(times, times[1:]))
    p = M['Parts'](name, existing=True)
    roots = [next(o for o in p.col.objects if o.type == 'EMPTY' and o.get('native_subpart') == spec['subpart'])
             for spec in RIG['rotors']]
    key = 'thermal_rotor_preview'
    assert not bpy.app.driver_namespace.get(key, {}).get('running'), 'Stop the current preview first'
    state = {'running': True, 'source': str(samples_path), 'model': name}
    bpy.app.driver_namespace[key] = state
    clock = time.monotonic()

    def step():
        elapsed = time.monotonic()-clock
        if not state['running'] or elapsed >= duration or bpy.context.scene != p.scene:
            state['running'] = False
            for root in roots:
                root['preview_angle_degrees'] = 0.
                root.update_tag()
            return None
        row = samples[max(0, min(len(samples)-1, bisect.bisect_right(times, start+elapsed)-1))]
        for root, phase in zip(roots, row[1:3]):
            root['preview_angle_degrees'] = math.degrees(phase)
            root.update_tag()
        state['sample'] = row
        bpy.context.view_layer.update()
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        return 1/60

    bpy.app.timers.register(step, first_interval=.01)
    return state
