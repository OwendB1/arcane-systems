"""Add the v02 startup study to an open v01/v02 file, preserving earlier studies."""
import bpy
import math
from pathlib import Path
from mathutils import Vector

OUT = Path(__file__).resolve().parent
base_path = OUT / 'build_mockups.py'
ns = {'__file__': str(base_path), '__name__': 'ap_helpers'}
exec(compile(base_path.read_text(), str(base_path), 'exec'), ns)
ns['M'] = {key: bpy.data.materials['AP / ' + key] for key in
           ['Hull', 'Edge', 'Dark', 'Panel', 'Copper', 'Cyan', 'Amber', 'Violet', 'White', 'Human', 'Floor']}
box, cylinder, annulus, empty, text, human = [ns[k] for k in ['box', 'cylinder', 'annulus', 'empty', 'text', 'human']]
finish = ns['finish']


def keys(o, prop, values):
    for frame, value in values:
        setattr(o, prop, value)
        o.keyframe_insert(data_path=prop, frame=frame)


def visible_from(o, frame):
    for prop in ['hide_render', 'hide_viewport']:
        keys(o, prop, [(1, True), (frame-1, True), (frame, False)])


def port(root, angle):
    p = empty('Conveyor connection / grid face', parent=root)
    p.rotation_euler.z = angle
    box('Conveyor throat', (0, -6.24, 1.25), (2.08, .20, 2.08), 'Dark', p)
    for x in [-.94, .94]:
        box('Yellow conveyor border', (x, -6.37, 1.25), (.16, .12, 2.0), 'Yellow', p, .035)
    for z in [.31, 2.19]:
        box('Yellow conveyor border', (0, -6.37, z), (1.85, .12, .16), 'Yellow', p, .035)
    box('Recessed transfer gate', (0, -6.37, 1.25), (1.46, .04, 1.46), 'Panel', p, .14)
    for x in [-.55, .55]:
        for z in [.70, 1.80]:
            box('Port locking dog', (x, -6.44, z), (.24, .12, .24), 'Edge', p, .035)
    dummy = empty('detector_conveyor / provisional', (0, -6.25, 1.25), p)
    dummy['note'] = 'Visual alignment only; validate game dummy axes during export'


def build_startup():
    assert '06 Tile assembly startup' not in bpy.data.scenes, 'Preserve existing startup edits by using a new version.'
    ns['material']('Yellow', (.9, .56, .04), .35, .5)
    ns['material']('FieldTile', (.075, .38, .53), .35, .34, .8)
    # Preview material uses the installed vanilla paint texture, with our blue-grey tint.
    paint = ns['material']('SE paint study', (.20, .29, .35), .35, .55)
    tex_path = Path('/home/owendb/.local/share/blender-se1-setup/assets/Textures/Models/Cubes/PaintedMetalColorable_cm.TIF')
    assert tex_path.exists()
    tree = paint.node_tree
    tex = tree.nodes.new('ShaderNodeTexImage')
    tex.image = bpy.data.images.load(str(tex_path), check_existing=True)
    mix = tree.nodes.new('ShaderNodeMixRGB')
    mix.blend_type = 'MULTIPLY'
    mix.inputs[0].default_value = .65
    mix.inputs[1].default_value = (.24, .34, .40, 1)
    tree.links.new(tex.outputs['Color'], mix.inputs[2])
    tree.links.new(mix.outputs[0], tree.nodes['Principled BSDF'].inputs['Base Color'])
    ns['M']['Paint'] = paint
    s = ns['scene']('06 Tile assembly startup', (0, 0, 4.4), (16, -23, 16), 23.5)
    s.frame_end = 480
    s.render.resolution_x, s.render.resolution_y = 1440, 1080
    root = empty('V02 / grid-integrated reactor startup')
    root['provisional_grid_envelope'] = '5 x 5 x 5 large-grid cells; 12.5 m cube'
    box('Grid foundation', (0, 0, .25), (12.5, 12.5, .5), 'Panel', root, .12)
    for x in [-5, 5]:
        box('Side machinery housing', (x, 0, 1.5), (2.5, 12.5, 2.0), 'Paint', root, .18)
    for y in [-5, 5]:
        box('End machinery housing', (0, y, 1.5), (7.5, 2.5, 2.0), 'Paint', root, .18)
    annulus('Open ring bay / rim', (0, 0, 2.43), 3.45, .30, .16, 'Edge', root)
    cylinder('Lower injector', (0, 0, 1.05), .40, .65, 'Dark', root)
    for angle in [0, math.pi/2, math.pi, -math.pi/2]:
        port(root, angle)
        face = empty('Grid face panel layout', parent=root)
        face.rotation_euler.z = angle
        for x in [-5, -2.5, 2.5, 5]:
            box('Recessed cargo-style service panel', (x, -6.23, 1.40), (2.05, .10, 1.5), 'Dark', face)
            box('Painted service hatch', (x, -6.30, 1.4), (1.78, .10, 1.23), 'Paint', face, .14)
            for xx in [x-.80, x+.80]:
                box('Hatch corner reinforcement', (xx, -6.38, 1.4), (.13, .10, .9), 'Edge', face, .025)
            box('Service latch', (x+.45, -6.4, 1.4), (.11, .08, .30), 'Dark', face, .02)
    for x in [-4.65, 4.65]:
        for y in [-4.65, 4.65]:
            box('Reinforced corner upright', (x, y, 6.0), (.65, .75, 7.0), 'Paint', root)
            box('Upright foot', (x, y, 2.65), (1.15, 1.25, .40), 'Edge', root)
            box('Inset structural rail', (x, y-.39, 6.0), (.26, .045, 5.2), 'Dark', root, .015)
            box('Field status strip', (x, y-.42, 6.8), (.09, .02, 1.0), 'Cyan', root, .005)
    box('Upper machinery bridge', (0, 0, 9.65), (10.3, 10.3, .75), 'Paint', root, .24)
    cylinder('Upper field cap', (0, 0, 9.1), 3.45, .38, 'Dark', root, 16)
    annulus('Upper coil seat', (0, 0, 8.9), 2.8, .22, .15, 'Copper', root)
    for x in [-2.5, 0, 2.5]:
        box('Cap grid panel', (x, 0, 10.08), (2.25, 8.6, .12), 'Panel', root)
    for side in [-1, 1]:
        box('Containment controller', (side*4.8, -3.6, 3.25), (1.7, 1.4, 1.4), 'Paint', root)
        box('Controller display', (side*4.8, -4.33, 3.5), (.8, .04, .32), 'Cyan', root, .01)
        text('FIELD CTRL', (side*4.8-.55, -4.36, 3.1), .16, 'White', root)
    # Four heads around the injector, all inside the rings' inner radius.
    nozzles = []
    for i, (x, y) in enumerate([(-.68, -.68), (.68, -.68), (.68, .68), (-.68, .68)]):
        box(f'Dispenser {i+1} / feeder stem', (x, y, 1.80), (.35, .35, 2.2), 'Dark', root)
        box(f'Dispenser {i+1} / tile head', (x, y, 3.0), (.5, .5, .28), 'Edge', root)
        box(f'Dispenser {i+1} / emission slot', (x, y, 3.16), (.3, .18, .035), 'Cyan', root, .01)
        nozzles.append(Vector((x, y, 3.18)))
    # Establish the storage volume before rotating rings into gyroscopic poses.
    for i, radius in enumerate([1.78, 2.48]):
        axis = empty(f'Deploying ring {i+1} / lift and tilt', parent=root)
        axis['ring_index'] = i
        z0 = 1.08+i*.50
        keys(axis, 'location', [(1, (0, 0, z0)), (30+i*10, (0, 0, z0)), (120, (0, 0, 5.90))])
        tilt = (math.radians(65), .15, 0) if i == 0 else (.25, math.radians(72), .6)
        keys(axis, 'rotation_euler', [(1, (0, 0, 0)), (360, (0, 0, 0)), (405, tilt)])
        rotor = empty(f'Deploying ring {i+1} / spin', parent=axis)
        annulus('Rising ring / housing', (0, 0, 0), radius, .18, .20, 'Edge', rotor)
        for j in range(12):
            annulus('Rising ring / inlay', (0, 0, .115), radius, .08, .025, 'Cyan', rotor,
                    j*math.tau/12+.03, j*math.tau/12+.40)
        box('Rising ring / index lug', (radius, 0, 0), (.28, .28, .29), 'Yellow', rotor, .025)
        keys(rotor, 'rotation_euler', [(1, (0, 0, 0)), (415, (0, 0, 0)),
                                     (480, (0, 0, (1 if i == 0 else -1)*math.tau))])
    # An 80-face icosphere: 20 packets, one face from each dispenser per packet.
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1.35)
    source = bpy.context.object
    faces = [[source.data.vertices[i].co.copy() for i in poly.vertices] for poly in source.data.polygons]
    bpy.data.objects.remove(source, do_unlink=True)
    faces.sort(key=lambda vs: (round(sum(v.z for v in vs)/3, 3), math.atan2(sum(v.y for v in vs), sum(v.x for v in vs))))
    assert len(faces) == 80 and all(len(vs) == 3 for vs in faces)
    for i, vertices in enumerate(faces):
        batch, head = divmod(i, 4)
        center = sum(vertices, Vector()) / 3
        mesh = bpy.data.meshes.new(f'Containment tile {i+1:02}')
        mesh.from_pydata([tuple((v-center)*.962) for v in vertices], [], [(0, 1, 2)])
        mesh.update()
        tile = bpy.data.objects.new(f'Tile {i+1:02} / batch {batch+1:02} / dispenser {head+1}', mesh)
        s.collection.objects.link(tile)
        finish(tile, tile.name, 'FieldTile', root)
        solid = tile.modifiers.new('Tile thickness / visual only', 'SOLIDIFY')
        solid.thickness = .018
        start = 200+batch*8
        tile['batch'], tile['dispenser'], tile['arrival_frame'] = batch+1, head+1, start+7
        visible_from(tile, start)
        keys(tile, 'location', [(start, nozzles[head]), (start+3, nozzles[head]+Vector((0, 0, .85))),
                                (start+7, center+Vector((0, 0, 5.9)))])
        keys(tile, 'scale', [(start, (.28,)*3), (start+7, (1,)*3)])
    core = ns['sphere']('Ignition / inner plasma', (0, 0, 5.9), .78, 'Amber', root)
    visible_from(core, 415)
    keys(core, 'scale', [(415, (.01,)*3), (440, (1,)*3)])
    human((-5.5, -7.2, 0), root)
    text('ARCANE POWER / DEPLOYABLE CONTAINMENT', (-5.8, -6.4, 2.16), .25, 'White', root)
    for label, frame in [('01 PARKED', 1), ('02 RINGS RISE', 30), ('03 RINGS RAISED', 120),
                         ('04 TILE ASSEMBLY / 4 PER BATCH', 200), ('05 SHELL COMPLETE / 80 TILES', 359),
                         ('06 RINGS TILT', 360), ('07 IGNITION', 415), ('08 RUNNING', 440)]:
        s.timeline_markers.new(label, frame=frame)
    s['visual_prototype_only'] = True
    s['tile_count'] = 80
    s['batch_size'] = 4
    s.frame_set(430)
    return s


if __name__ == '__main__':
    build_startup()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'arcane-power-mockups-v02.blend'))
