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
    # End collars and the original split band/cradle seats stay metal. The two
    # upper side apertures contain glass through the full pressure-wall thickness.
    window = length*(.298 if label == 'turbine' else .225)
    left, right = x-window, x+window
    obj = p.tube('temporary inspection casing', [(x-length/2, 0, .45),
        (left, 0, .45), (right, 0, .45), (x+length/2, 0, .45)],
        radius, 'PaintedMetal_Darker', .12, 48)
    outside, inside = glass_slots(p, obj)
    for face in obj.data.polygons:
        c = face.center
        angle = math.degrees(math.atan2(-c.y, c.z-.45)) % 360
        if left < c.x < right and (22.5 < angle < 82.5 or 277.5 < angle < 337.5):
            radial = Vector((0, c.y, c.z-.45))
            face.material_index = outside if face.normal.dot(radial) > 0 else inside
    old.data = obj.data
    old['thermal_hollow_casing'] = True
    old['thermal_pressure_wall_m'] = .12
    old['thermal_window_x'] = (left, right)
    old['thermal_window_angles_deg'] = (22.5, 82.5, 277.5, 337.5)
    old['thermal_visibility_revision'] = REVISION
    bpy.data.objects.remove(obj, do_unlink=True)
    # Narrow machined rails cover the aperture edges, with supported captive
    # fasteners; no opaque panel or former decorative rib blocks the window.
    for degrees in (22.5, 82.5, 277.5, 337.5):
        a = math.radians(degrees)
        radial = Vector((0, -math.sin(a), math.cos(a)))
        rail = p.box(label+' inspection window rail', (x, 0, .45),
                     (right-left+.10, .065, .055), 'Metal_Dull', .003)
        rail.rotation_euler.x = a
        rail.location += radial*(radius+.017)
        rail['thermal_seated_on'] = old.name
        for sx in (left+.10, x, right-.10):
            point = Vector((sx, 0, .45))+radial*(radius+.043)
            p.bolt(label+' window captive stud', point, radial, rail, .022)
    for sx in (left-.025, right+.025):
        frame = p.tube(label+' inspection window end frame',
                       [(sx-.025, 0, .45), (sx+.025, 0, .45)],
                       radius+.027, 'Metal_Dull', .045, 96)
        frame['thermal_seated_on'] = old.name
    return old


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
                              .45+radius*math.sin(angle)+tangent*math.cos(angle)))
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
    lo, hi = (-2.26, -.44) if turbine else (-4.78, -3.72)
    drum_lo, drum_hi = (-2.85, .15) if turbine else (-5.40, -3.10)
    def hub(x):
        t = (x-drum_lo)/(drum_hi-drum_lo)
        return 1.19-.30*t if turbine else .69+.27*t
    # The continuous tapered drum carries the blade roots; the flow is annular.
    sides = 96
    verts = [(x, hub(x)*math.cos(j*math.tau/sides), .45+hub(x)*math.sin(j*math.tau/sides))
             for x in (drum_lo, drum_hi) for j in range(sides)]
    faces = [tuple(reversed(range(sides))), tuple(range(sides, 2*sides))]
    faces += [(j, (j+1)%sides, (j+1)%sides+sides, j+sides) for j in range(sides)]
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
            ring = p.tube(label+' stationary carrier', [(x-.023, 0, .45), (x+.023, 0, .45)],
                          radius-.09, 'Metal_Dull', .035, 96)
            ring['thermal_stator_carrier'] = True
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


def end_plenum_pipes(p, casings):
    # H: heater -> turbine front -> rear exhaust -> recovery.
    # C: cooling -> compressor front -> rear discharge -> heater.
    channels = [
        ('HP hot inlet', 'turbine', -1, -2.64, 1.71),
        ('HP compressed return', 'compressor', -1, -3.38, .79),
        ('LP hot exhaust', 'turbine', 1, -.06, 1.71),
        ('LP cooled inlet', 'compressor', 1, -5.12, .79),
    ]
    for label, machine, sign, x, height in channels:
        radius = 1.85 if machine == 'turbine' else 1.35
        angle = math.pi/6 if machine == 'turbine' else math.asin(.34/radius)
        normal = Vector((0, sign*math.cos(angle), math.sin(angle)))
        origin = Vector((x, 0, .45))
        centre = origin+normal*radius
        end = origin+normal*(radius-.145)
        lead = origin+normal*(radius+.95)
        start = (-2.5, sign*3.75, height)
        if machine == 'compressor':
            path = [start, (-2.5, sign*3.10, height), (x, sign*3.10, height), lead, end]
        else:
            path = [start, (-2.5, sign*3.02, height), lead, end]
        pipe = p.tube(label, rounded_path(path), .29, 'Metal_Dull', .045, 32)
        pipe['thermal_flow_machine'] = machine
        pipe['thermal_flow_end'] = 'front' if label in ('HP hot inlet', 'LP cooled inlet') else 'rear'
        pipe['thermal_flow_channel'] = label
        pipe['thermal_nozzle_centre'] = centre
        pipe['thermal_nozzle_normal'] = normal
        # Open the pressure wall at the opaque end plenum, outside the windows.
        casing = casings[machine]
        cutter = p.cylinder('temporary end plenum bore', centre-normal*.35,
                            centre+normal*.40, .245, sides=32)
        bands = [o for o in p.col.objects if o.name.startswith(p.name+' / '+machine+' split casing band')]
        for target in [casing]+bands:
            bpy.context.view_layer.objects.active = target
            mod = target.modifiers.new('Seated '+label+' bore', 'BOOLEAN')
            mod.operation, mod.solver, mod.object = 'DIFFERENCE', 'EXACT', cutter
            bpy.ops.object.modifier_apply(modifier=mod.name)
            M['BUILD']['uv'](target)
        bpy.data.objects.remove(cutter, do_unlink=True)
        # A short pressure collar seats on the curved casing around the nozzle.
        collar = p.tube(label+' nozzle collar', [centre-normal*.11, centre+normal*.10], .310, 'Metal_Dull', .065, 32)
        collar['thermal_nozzle_collar'] = True
    for casing in casings.values():
        M['BUILD']['uv'](casing)


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
        casings = {'turbine': inspection_casing(p, 'turbine', -1.35, 3.15, 1.85),
                   'compressor': inspection_casing(p, 'compressor', -4.25, 2.42, 1.35)}
        end_plenum_pipes(p, casings)
        for spec in RIG['rotors']:
            rotor(p, spec)
    pipes = transparent_pipes(p)
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
