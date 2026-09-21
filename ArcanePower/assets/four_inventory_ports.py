"""Give all four grid-facing conveyor mouths native SE inventory access panels.

Run after fit_three_cells.py. Detector `conveyor` is registered to
MyUseObjectInventory in SE1, supporting inventory, terminal and build planner.
"""
import bpy
import importlib
import math
from mathutils import Matrix, Vector

s = bpy.data.scenes['ArcanePower_ReactorPrototype']
assert s.get('three_cells_applied'), 'Fit the three-cell housing first'
bpy.context.window.scene = s
cols = importlib.import_module('space-engineers-utilities.seut_collections').get_collections(s)
col = cols['main'][0]
root = next(o for o in col.objects if o.parent is None)
native = {m.name: m for m in bpy.data.materials if m.library}
template = bpy.app.driver_namespace['ap_parts']['Conveyor Access LG']

for o in list(col.objects):
    if o.name.startswith(('SEUT / Conveyor Access LG', 'SEUT / Conveyor LG',
                          'Inventory access /', 'detector_conveyor_', 'detector_terminal')):
        bpy.data.objects.remove(o, do_unlink=True)

for i in range(4):
    rotation = Matrix.Rotation(i * math.pi/2, 4, 'Z')
    # The native asset's face is local Z=1.2567. Recess by 7 mm to stay in the cell.
    transform = rotation @ Matrix.Translation((0, -4.993, -2.5)) @ Matrix.Rotation(math.pi/2, 4, 'X')
    mesh = template.data.copy()
    mesh.transform(transform)
    for j, material in enumerate(mesh.materials):
        mesh.materials[j] = native.get(material.name.split('.')[0], material)
    panel = bpy.data.objects.new('Inventory access / side %s' % i, mesh)
    col.objects.link(panel)
    panel.parent = root
    panel['source_asset'] = 'SEUT Common.blend / Conveyor Access LG'

    # Re-cut each real housing in its own rotated coordinate frame. This also
    # fixes the original mockup's shared-position recess cutters on the side faces.
    center = rotation @ Vector((0, -5.15, -2.5))
    trunks = [o for o in col.objects if o.name.startswith('Radial conveyor trunk')]
    trunk = min(trunks, key=lambda o: ((sum((o.matrix_world @ Vector(p) for p in o.bound_box), Vector())/8)-center).length)
    if not trunk.get('inventory_access_recess'):
        bpy.ops.mesh.primitive_cube_add(size=1, location=rotation @ Vector((0, -6.15, -2.5)))
        cutter = bpy.context.object
        cutter.name = 'Temporary inventory access recess'
        cutter.scale = (1.42, .70, 1.42)
        cutter.rotation_euler.z = i * math.pi/2
        bpy.context.view_layer.objects.active = trunk
        modifier = trunk.modifiers.new('Accessible native conveyor panel', 'BOOLEAN')
        modifier.operation = 'DIFFERENCE'
        modifier.solver = 'EXACT'
        modifier.object = cutter
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        bpy.data.objects.remove(cutter, do_unlink=True)
        trunk['inventory_access_recess'] = True

    # A broad, shallow interactive box over the full hatch. Its center remains
    # within the outermost 2.5 m grid cell, pointing outward for conveyor matching.
    detector = bpy.data.objects.new('detector_conveyor_%s' % i, None)
    col.objects.link(detector)
    detector.parent = root
    detector.empty_display_type = 'CUBE'
    detector.empty_display_size = .5
    detector.location = rotation @ Vector((0, -6.22, -2.5))
    detector.rotation_euler.z = i * math.pi/2
    detector.scale = (1.38, .08, 1.38)
    detector['purpose'] = 'Native conveyor endpoint + OpenInventory/OpenTerminal/BuildPlanner/Deposit'

s['inventory_access'] = 'Four native Conveyor Access LG panels; detector_conveyor_0..3, bottom cell row'
bpy.context.view_layer.update()
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
print(s['inventory_access'])
