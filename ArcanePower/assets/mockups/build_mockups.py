"""Run in Blender's Python console/MCP. Each build_* call creates a review scene.

Original editable blockouts, metres, Z up; not game-ready exports.
"""
import bpy
import math
from pathlib import Path
from mathutils import Vector

OUT = Path(__file__).resolve().parent
TAU = math.tau
M = {}


def material(name, rgb, metal=0.0, rough=0.4, emission=0.0):
    m = bpy.data.materials.new('AP / ' + name)
    m.diffuse_color = (*rgb, 1)
    m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (*rgb, 1)
    p.inputs['Metallic'].default_value = metal
    p.inputs['Roughness'].default_value = rough
    p.inputs['Emission Color'].default_value = (*rgb, 1)
    p.inputs['Emission Strength'].default_value = emission
    M[name] = m
    return m


def setup_materials():
    for name, color, metal, rough, emission in [
        ('Hull', (.20, .29, .35), .65, .33, 0),
        ('Edge', (.39, .48, .51), .75, .28, 0),
        ('Dark', (.025, .045, .057), .5, .4, 0),
        ('Panel', (.10, .17, .22), .6, .36, 0),
        ('Copper', (.63, .29, .095), .65, .34, 0),
        ('Cyan', (.025, .72, 1), .2, .25, 3),
        ('Amber', (1, .33, .035), .2, .25, 3),
        ('Violet', (.56, .10, 1), .2, .25, 3),
        ('White', (.75, .89, .94), .0, .45, .25),
        ('Human', (.88, .50, .13), .2, .5, 0),
        ('Floor', (.026, .043, .061), .15, .6, 0),
    ]:
        material(name, color, metal, rough, emission)


def finish(o, name, mat, parent=None):
    o.name = name
    if mat:
        o.data.materials.append(M[mat])
    if parent:
        o.parent = parent
    return o


def box(name, pos, size, mat='Hull', parent=None, bevel=.08):
    bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
    o = bpy.context.object
    o.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        b = o.modifiers.new('Blockout edge bevel', 'BEVEL')
        b.width = bevel
        b.segments = 2
        o.modifiers.new('Weighted corner normals', 'WEIGHTED_NORMAL')
    return finish(o, name, mat, parent)


def cylinder(name, pos, radius, depth, mat='Hull', parent=None, vertices=48):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=pos)
    o = bpy.context.object
    b = o.modifiers.new('Edge bevel', 'BEVEL')
    b.width = .06
    b.segments = 2
    o.modifiers.new('Weighted normals', 'WEIGHTED_NORMAL')
    return finish(o, name, mat, parent)


def sphere(name, pos, radius, mat, parent=None, scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=radius, location=pos)
    o = bpy.context.object
    o.scale = scale
    return finish(o, name, mat, parent)


def empty(name, pos=(0, 0, 0), parent=None):
    o = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(o)
    o.location = pos
    o.parent = parent
    o.empty_display_size = .4
    return o


def annulus(name, pos, radius, width, depth, mat, parent=None, start=0, end=TAU):
    # Rectangular ring section: light enough for many independently editable rings.
    n = max(4, round(64 * (end-start) / TAU))
    verts = []
    for i in range(n+1):
        a = start + (end-start)*i/n
        for r, z in [(radius-width/2, -depth/2), (radius+width/2, -depth/2),
                     (radius+width/2, depth/2), (radius-width/2, depth/2)]:
            verts.append((r*math.cos(a), r*math.sin(a), z))
    faces = []
    for i in range(n):
        for j in range(4):
            faces.append((4*i+j, 4*i+(j+1)%4, 4*(i+1)+(j+1)%4, 4*(i+1)+j))
    faces += [(3, 2, 1, 0), tuple(4*n+j for j in range(4))]
    mesh = bpy.data.meshes.new(name)
    # This cross-section order winds toward the solid; reverse it for outward faces.
    mesh.from_pydata(verts, [], [tuple(reversed(face)) for face in faces])
    mesh.update()
    o = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(o)
    o.location = pos
    return finish(o, name, mat, parent)


def text(body, pos, size=.35, mat='White', parent=None, rotation=(math.pi/2, 0, 0)):
    curve = bpy.data.curves.new(body, 'FONT')
    curve.body = body
    curve.size = size
    curve.extrude = .001
    o = bpy.data.objects.new(body, curve)
    bpy.context.collection.objects.link(o)
    o.location = pos
    o.rotation_euler = rotation
    return finish(o, body, mat, parent)


def animate_spin(o, direction=1, period=240):
    start = o.rotation_euler.z
    o.keyframe_insert(data_path='rotation_euler', frame=1, index=2)
    o.rotation_euler.z = start + direction*TAU
    o.keyframe_insert(data_path='rotation_euler', frame=period+1, index=2)
    # Blender 5 uses layered actions; make the loop linear through its slot.
    action = o.animation_data.action
    for layer in action.layers:
        for strip in layer.strips:
            bag = strip.channelbag(o.animation_data.action_slot)
            for fc in bag.fcurves:
                for key in fc.keyframe_points:
                    key.interpolation = 'LINEAR'
                fc.modifiers.new('CYCLES')


def human(pos, parent=None):
    p = empty('Scale reference / 1.8 m human', pos, parent)
    sphere('Helmet', (0, 0, 1.62), .18, 'White', p)
    box('Suit torso', (0, 0, 1.17), (.43, .27, .58), 'Human', p)
    for x in [-.13, .13]:
        box('Suit leg', (x, 0, .48), (.17, .21, .75), 'White', p, .06)
    for x in [-.31, .31]:
        box('Suit arm', (x, 0, 1.10), (.15, .20, .59), 'Human', p, .06)


def scene(name, target, camera_pos, ortho):
    s = bpy.data.scenes.new(name)
    bpy.context.window.scene = s
    s.unit_settings.system = 'METRIC'
    s.unit_settings.length_unit = 'METERS'
    s.render.engine = 'CYCLES'
    s.cycles.samples = 24
    s.cycles.use_denoising = True
    s.render.resolution_x = 1600
    s.render.resolution_y = 1000
    s.render.resolution_percentage = 100
    s.render.image_settings.file_format = 'PNG'
    s.render.fps = 24
    s.frame_start, s.frame_end = 1, 240
    s.world = bpy.data.worlds.new(name + ' / World')
    s.world.use_nodes = True
    s.world.node_tree.nodes['Background'].inputs[0].default_value = (.16, .22, .30, 1)
    s.world.node_tree.nodes['Background'].inputs[1].default_value = .4
    box('Studio floor', (target[0], target[1], -.20), (100, 80, .30), 'Floor', bevel=0)
    for label, position, power, size in [
        ('Key', (target[0]+2, -12, 24), 12000, 18),
        ('Fill', (target[0]-15, -2, 14), 9000, 16),
        ('Rim', (target[0]+12, 10, 20), 18000, 12),
    ]:
        data = bpy.data.lights.new(label, 'AREA')
        data.energy, data.shape, data.size = power, 'DISK', size
        o = bpy.data.objects.new(label, data)
        s.collection.objects.link(o)
        o.location = position
        o.rotation_euler = (Vector(target)-o.location).to_track_quat('-Z', 'Y').to_euler()
    data = bpy.data.cameras.new('Review camera')
    c = bpy.data.objects.new('Review camera', data)
    s.collection.objects.link(c)
    c.location = camera_pos
    c.rotation_euler = (Vector(target)-c.location).to_track_quat('-Z', 'Y').to_euler()
    data.type, data.ortho_scale = 'ORTHO', ortho
    s.camera = c
    return s


def reactor(kind, count, offset=(0, 0, 0), scale=1):
    fuel = ['Cyan', 'Amber', 'Violet'][count-2]
    root = empty(f'{kind} / T{count-1} / {count} rings', offset)
    root.scale = (scale,)*3
    root['nominal_envelope_m'] = '12.5 x 12.5 x 10; provisional'
    root['ring_count'] = count
    root['fuel_tier'] = count-1
    box('Foundation / service deck', (0, 0, .35), (11.2, 11.2, .7), 'Panel', root, .24)
    cylinder('Lower machinery drum', (0, 0, 1.05), 4.8, 1.4, 'Hull', root, 16)
    annulus('Lower rim', (0, 0, 1.8), 4.1, .38, .26, 'Edge', root)
    cylinder('Reaction pedestal', (0, 0, 2.0), 2.5, .42, 'Dark', root)
    annulus('Pedestal field emitter', (0, 0, 2.23), 2.15, .12, .08, fuel, root)
    cylinder('Upper containment cap', (0, 0, 8.45), 3.9, .9, 'Hull', root, 16)
    cylinder('Cap crown', (0, 0, 9.12), 3.2, .48, 'Panel', root, 16)
    annulus('Upper cap seal', (0, 0, 8.02), 3.1, .15, .12, 'Copper', root)
    for x in [-3.65, 3.65]:
        for y in [-3.65, 3.65]:
            box('Containment frame upright', (x, y, 4.65), (.52, .65, 6.1), 'Hull', root)
            box('Frame foot', (x, y, 1.7), (1.0, 1.0, .65), 'Edge', root)
            box('Frame cap support', (x*.87, y*.87, 7.9), (1.25, 1.25, .55), 'Edge', root)
            box('Frame status strip', (x, y-.34, 5.05), (.12, .035, 1.3), fuel, root, .01)
    for q in range(4):
        socket = empty(f'Controller socket {q+1}', parent=root)
        socket.rotation_euler.z = q*math.pi/2
        box('Socket backing', (0, -4.48, 2.0), (1.8, .30, 1.85), 'Dark', socket)
        if q < count:
            box('Containment controller ' + str(q+1), (0, -4.93, 2.0), (1.55, .9, 1.55), 'Hull', socket)
            box('Controller inset', (0, -5.40, 2.12), (1.1, .05, .75), 'Panel', socket)
            box('Controller screen', (0, -5.44, 2.22), (.66, .03, .28), fuel, socket, .01)
            text(f'C{q+1:02}', (-.35, -5.47, 1.73), .23, 'White', socket)
        else:
            text('SPARE', (-.52, -4.66, 1.94), .20, 'Edge', socket)
    for q in range(12):
        a = q*TAU/12
        p = box('Drum panel', (4.73*math.cos(a), 4.73*math.sin(a), 1.05), (.75, .10, .75), 'Panel', root)
        p.rotation_euler.z = a-math.pi/2
    # Exhaust connection is separate from upgrade sockets and power transfer.
    duct = box('Dedicated exhaust takeoff', (1.9, 4.55, 3.0), (1.9, 2.6, 1.65), 'Dark', root)
    box('Exhaust flange', (1.9, 5.65, 3.0), (2.25, .24, 2.0), 'Copper', root)
    if kind == 'GYRO':
        sphere('Faceted plasma core', (0, 0, 5.15), 1.15, fuel, root)
        sphere('Core structural cage', (0, 0, 5.15), 1.21, 'Dark', root)
        cage = bpy.context.object
        wire = cage.modifiers.new('Core lattice', 'WIREFRAME')
        wire.thickness = .025
    else:
        cylinder('Plasma column', (0, 0, 4.9), .58, 4.8, fuel, root, 24)
        for z in [2.55, 7.25]:
            cylinder('Column injector', (0, 0, z), 1.25, .5, 'Edge', root)
    for i in range(count):
        r = 1.48 + .36*i if kind == 'GYRO' else 2.65
        z = 5.15 if kind == 'GYRO' else 3.0 + 1.2*i
        gimbal = empty(f'Ring {i+1} / axis', (0, 0, z), root)
        if kind == 'GYRO':
            gimbal.rotation_euler = [(math.radians(65), .20, 0),
                                     (.35, math.radians(76), .55),
                                     (math.radians(35), -.4, .8),
                                     (math.radians(80), -.3, -.5)][i]
            animate_spin(gimbal, 1 if i%2 == 0 else -1, 480+120*i)
        rotor = empty(f'Ring {i+1} / animated rotor', parent=gimbal)
        annulus(f'Ring {i+1} / metal band', (0, 0, 0), r, .18, .20, 'Edge', rotor)
        for j in range(8):
            a = j*TAU/8
            annulus(f'Ring {i+1} / emissive segment {j+1}', (0, 0, .112), r, .085, .028, fuel, rotor, a+.035, a+.58)
        # Asymmetric index lug makes ring motion legible even in plain solid view.
        box(f'Ring {i+1} / index lug', (r, 0, 0), (.32, .28, .30), 'Copper', rotor, .035)
        animate_spin(rotor, 1 if i%2 == 0 else -1)
    if scale == 1:
        human((-4.8, -5.8, .7), root)
    text(f'{kind}  /  T{count-1}  /  {count} RINGS', (-5.1, -5.65, .35), .4, 'White', root)
    return root


def build_reactors(kind):
    s = scene('01 Gyroscopic reactors' if kind == 'GYRO' else '02 Column reactors',
              (15, 0, 3.8), (30, -40, 27), 49)
    for tier in range(2, 5):
        reactor(kind, tier, ((tier-2)*15, 0, 0))
    s.frame_set(1)
    return s


def build_battery():
    s = scene('03 Energy Core', (0, 0, 3.4), (14, -20, 15), 18)
    root = empty('Arcane Energy Core / expandable storage')
    box('Storage foundation', (0, 0, .35), (9, 8, .7), 'Panel', root)
    cylinder('Core pedestal', (0, 0, 1.2), 2.8, 1, 'Hull', root, 16)
    sphere('Stored energy volume', (0, 0, 4.3), 1.65, 'Cyan', root)
    for i in range(3):
        axis = empty('Storage field axis', (0, 0, 4.3), root)
        axis.rotation_euler.x = i*math.pi/3
        band = annulus('Storage field lattice', (0, 0, 0), 1.88+.13*i, .12, .14, 'Edge', axis)
        animate_spin(axis, 1, 720)
    for x in [-2.65, 2.65]:
        for y in [-2.45, 2.45]:
            box('Stabilizer column', (x, y, 3.9), (.65, .75, 5.5), 'Hull', root)
            box('Stabilizer inlay', (x, y-.4, 4.5), (.16, .035, 2.8), 'Cyan', root, .01)
    box('Top bridge', (0, 0, 6.95), (6.1, 5.7, .8), 'Hull', root, .22)
    for x in [-3.7, 3.7]:
        for z in [1.75, 3.55]:
            box('Capacity module / MWh', (x, 0, z), (1.6, 3.5, 1.5), 'Hull', root)
            box('Capacity inset', (x, -1.79, z), (1.23, .07, .9), 'Dark', root)
            for n in range(3):
                box('Charge segment', (x-.36+n*.36, -1.84, z), (.19, .03, .58), 'Cyan', root, .01)
    for x in [-1.65, 1.65]:
        box('Transfer module / MW', (x, -3.4, 1.65), (1.7, 1.55, 1.8), 'Hull', root)
        box('Transfer grille', (x, -4.2, 1.65), (1.3, .08, 1.1), 'Dark', root)
        for n in range(3):
            box('Transfer copper conductor', (x, -4.27, 1.3+n*.32), (1.05, .06, .12), 'Copper', root, .02)
    human((4.8, -3.9, 0), root)
    text('ARCANE ENERGY CORE', (-3.8, -4.1, .33), .39, 'White', root)
    text('CAPACITY / MWh', (-5.8, -3, .1), .28, 'Cyan', rotation=(0, 0, 0))
    s.frame_set(1)
    return s


def vent(x, state):
    root = empty('Vent / ' + state, (x, 0, 0))
    box('Dedicated exhaust duct', (0, 1.2, 2.4), (3.2, 4.6, 3.2), 'Panel', root)
    for y in [0, 1.5, 3]:
        box('Duct collar', (0, y, 2.4), (3.55, .22, 3.55), 'Hull', root)
    box('Hull interface', (0, -1.15, 2.4), (5.3, .55, 4.9), 'Hull', root, .2)
    box('Outlet throat', (0, -1.49, 2.4), (3.9, .13, 3.6), 'Dark', root)
    for sign in [-1, 1]:
        shutter = box('Sliding shutter / ' + state, (sign*.96, -1.7, 2.4), (1.88, .20, 3.55), 'Edge', root)
        shutter['state_preview'] = state
        closed_x, opened_x = sign*.96, sign*2.15
        for frame, value in [(1, closed_x), (35, closed_x), (75, opened_x), (165, opened_x), (210, closed_x), (240, closed_x)]:
            shutter.location.x = value
            shutter.keyframe_insert(data_path='location', frame=frame, index=0)
        if state == 'CLOSED':
            shutter.animation_data_clear()
            shutter.location.x = closed_x
        elif state == 'OPEN':
            shutter.animation_data_clear()
            shutter.location.x = opened_x
    for x1 in [-2.42, 2.42]:
        box('Outlet warning lamp', (x1, -1.5, 3.8), (.14, .1, .5), 'Amber', root, .02)
    if state == 'VENTING':
        plume = empty('Discharge preview / actual flow placeholder', (0, -1.9, 2.4), root)
        # Stylized exhaust mesh, not a particle/export implementation.
        for i in range(4):
            bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=.07, radius2=.65-i*.11, depth=5.6-i*.75,
                                           location=(0, -2.8+i*.3, 0))
            o = bpy.context.object
            o.rotation_euler.x = -math.pi/2
            finish(o, 'Plasma discharge core', 'Amber' if i == 0 else 'White', plume)
        for i in range(5):
            ring = annulus('Discharge shock band', (0, -i*.95-.2, 0), .70-i*.09, .045, .065, 'Amber', plume)
            ring.rotation_euler.x = math.pi/2
        for frame, value in [(1, .001), (75, .001), (90, 1), (145, 1), (165, .001), (240, .001)]:
            plume.scale = (value,)*3
            plume.keyframe_insert(data_path='scale', frame=frame)
    human((3.2, 0, 0), root)
    text(state, (-2.4, -1.48, .22), .42, 'White', root)


def build_vents():
    s = scene('04 Vent states', (9, -1, 2), (22, -30, 23), 36)
    for x, state in [(0, 'CLOSED'), (9, 'OPEN'), (18, 'VENTING')]:
        vent(x, state)
    s.frame_set(115)
    return s


def build_scale():
    s = scene('05 Scale study', (8, 0, 3), (22, -32, 23), 34)
    reactor('GYRO', 4, (0, 0, 0))
    reactor('GYRO', 4, (14, 0, 0), .6)
    human((19, -3, 0))
    text('12.5 m ENVELOPE', (-5, -7, .1), .5, rotation=(0, 0, 0))
    text('7.5 m ENVELOPE / 60%', (10, -5, .1), .45, rotation=(0, 0, 0))
    box('Arcane Core scale proxy / 1 large-grid cell', (22, 0, 1.25), (2.5, 2.5, 2.5), 'Hull')
    text('2.5 m CORE PROXY', (20, -3, .1), .32, rotation=(0, 0, 0))
    s.frame_set(1)
    return s


def save_review():
    for s in bpy.data.scenes:
        if s.name[:2] in ['01', '02', '03', '04', '05']:
            s['review_status'] = 'Original design blockout; not game-ready'
            s.render.filepath = str(OUT / 'previews' / (s.name[:2] + '.png'))
    bpy.context.window.scene = bpy.data.scenes['01 Gyroscopic reactors']
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.region_3d.view_perspective = 'CAMERA'
                area.spaces.active.shading.type = 'MATERIAL'
                area.spaces.active.overlay.show_overlays = False
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'arcane-power-mockups-v01.blend'))
    print('Saved five review scenes:', str(OUT))


if __name__ == '__main__':
    assert not any(s.name.startswith(('01 Gyroscopic', '02 Column', '03 Energy', '04 Vent', '05 Scale'))
                   for s in bpy.data.scenes), 'Build into a fresh file to preserve existing mockup edits.'
    setup_materials()
    build_reactors('GYRO')
    build_reactors('COLUMN')
    build_battery()
    build_vents()
    build_scale()
    save_review()
