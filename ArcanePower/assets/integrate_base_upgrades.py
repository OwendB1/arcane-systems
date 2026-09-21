"""Replace the side conveyor bays with native upgrade sockets in the same base row.

Run after four_inventory_ports.py. Front/back retain inventory access; left/right
become upgrade interfaces. External controllers occupy adjacent whole grid cells.
"""
import bpy
import importlib
import math
from mathutils import Matrix, Vector

s = bpy.data.scenes['ArcanePower_ReactorPrototype']
bpy.context.window.scene = s
cols = importlib.import_module('space-engineers-utilities.seut_collections').get_collections(s)
col = cols['main'][0]
root = next(o for o in col.objects if o.parent is None)
native = {m.name: m for m in bpy.data.materials if m.library}
template = bpy.app.driver_namespace['ap_parts']['Upgrade Port LG']

for o in list(col.objects):
    remove = o.name.startswith(('Grid-aligned controller receiver', 'Grid upgrade socket',
                                 'detector_upgrade_', 'Base upgrade /'))
    remove |= o.name in ['Inventory access / side 1', 'Inventory access / side 3',
                         'detector_conveyor_1', 'detector_conveyor_3']
    if o.name.startswith('SEUT / Conveyor Frame LG'):
        center = sum((o.matrix_world @ Vector(p) for p in o.bound_box), Vector()) / 8
        remove |= abs(center.x) > 5
    if remove:
        bpy.data.objects.remove(o, do_unlink=True)

for i in (1, 3):
    rotation = Matrix.Rotation(i*math.pi/2, 4, 'Z')
    transform = rotation @ Matrix.Translation((0, -5, -2.5)) @ Matrix.Rotation(math.pi/2, 4, 'X')
    mesh = template.data.copy()
    mesh.transform(transform)
    for j, material in enumerate(mesh.materials):
        mesh.materials[j] = native.get(material.name.split('.')[0], material)
    port = bpy.data.objects.new('Base upgrade / native socket %s' % i, mesh)
    col.objects.link(port)
    port.parent = root
    port['source_asset'] = 'SEUT Common.blend / Upgrade Port LG'

    # Replace the large cargo mouth with a recessed plate sized to the upgrade kit.
    bpy.ops.mesh.primitive_cube_add(size=1, location=rotation @ Vector((0, -6.13, -2.5)))
    plate = bpy.context.object
    plate.name = 'Base upgrade / adapter plate %s' % i
    plate.rotation_euler.z = i*math.pi/2
    plate.scale = (1.98, .18, 1.98)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    for c in list(plate.users_collection):
        c.objects.unlink(plate)
    col.objects.link(plate)
    plate.parent = root
    plate.data.materials.append(native['PaintedMetal_Colorable'])
    bevel = plate.modifiers.new('Machined plate edge', 'BEVEL')
    bevel.width = .035
    bevel.segments = 3
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    bpy.ops.mesh.primitive_cube_add(size=1, location=rotation @ Vector((0, -6.13, -2.5)))
    cutter = bpy.context.object
    cutter.rotation_euler.z = i*math.pi/2
    cutter.scale = (.73, .5, .73)
    bpy.context.view_layer.objects.active = plate
    cut = plate.modifiers.new('Native socket recess', 'BOOLEAN')
    cut.operation = 'DIFFERENCE'
    cut.object = cutter
    bpy.ops.object.modifier_apply(modifier=cut.name)
    bpy.data.objects.remove(cutter, do_unlink=True)

    detector = bpy.data.objects.new('detector_upgrade_%s' % i, None)
    col.objects.link(detector)
    detector.parent = root
    detector.empty_display_type = 'CUBE'
    detector.empty_display_size = .5
    detector.location = rotation @ Vector((0, -6.22, -2.5))
    detector.rotation_euler.z = i*math.pi/2
    detector.scale = (.7, .08, .7)
    detector['purpose'] = 'ArcaneContainment native upgrade connection in bottom cell row'

s['inventory_access'] = 'Front/back: native inventory conveyor panels, detector_conveyor_0 and _2'
s['native_interface_centers'] = 'All base interfaces SE Y=-2.5; side controllers SE X=+/-7.5, Y=-2.5, Z=0'
s['upgrade_layout'] = 'Left/right base bays; raised controller receiver housings removed'
bpy.context.view_layer.update()
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
print(s['upgrade_layout'])
