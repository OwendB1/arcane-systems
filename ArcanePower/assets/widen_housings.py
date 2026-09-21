"""Widen round housings into the existing port envelope; add centred axial conveyors.

Run after integrate_base_upgrades.py and flush_roof.py. Native interface meshes
remain unscaled, at the fixed 5x3x5 block faces. No game deployment is performed.
"""
import bpy
import importlib
import math
from mathutils import Matrix, Vector, geometry

s = bpy.data.scenes['ArcanePower_ReactorPrototype']
assert not s.get('housings_widened'), 'Already widened; use the saved model for further edits'
bpy.context.window.scene = s
cols = importlib.import_module('space-engineers-utilities.seut_collections').get_collections(s)
col = cols['main'][0]
root = next(o for o in col.objects if o.parent is None)
native = {m.name: m for m in bpy.data.materials if m.library}
parts = bpy.app.driver_namespace['ap_parts']


def bounds(obj):
    points = [obj.matrix_world @ Vector(v) for v in obj.bound_box]
    return min(p.z for p in points), max(p.z for p in points)


def fixed_interface(obj):
    return obj.name.startswith(('Radial conveyor trunk', 'Inventory access /', 'Base upgrade /', 'SEUT / Conveyor'))


def conveyor_cutter(center, rotation, depth):
    # Match the native frame's clipped corners, with a 10 mm fitting allowance.
    points = [Vector(p) for p in sorted({(round(v.co.x, 4), round(v.co.y, 4))
                                      for v in parts['Conveyor Frame LG'].data.vertices})]
    outline = [points[i]*1.01 for i in geometry.convex_hull_2d(points)]
    n = len(outline)
    vertices = [(p.x, p.y, z) for z in (-depth/2, depth/2) for p in outline]
    faces = [(i, (i+1)%n, (i+1)%n+n, i+n) for i in range(n)]
    faces.extend([tuple(reversed(range(n))), tuple(range(n, 2*n))])
    mesh = bpy.data.meshes.new('Native frame recess cutter')
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    cutter = bpy.data.objects.new('Temporary native frame recess', mesh)
    bpy.context.scene.collection.objects.link(cutter)
    cutter.matrix_world = Matrix.Translation(center) @ rotation
    return cutter


roof = [o for o in col.objects if o.type == 'MESH' and bounds(o)[0] > 2.75
        and not o.name.startswith('Curved chamber /')]
roof_radius = max(math.hypot(*(o.matrix_world @ v.co)[:2]) for o in roof for v in o.data.vertices)
roof_factor = 6.24 / roof_radius
for obj in list(col.objects):
    if obj.type != 'MESH' or fixed_interface(obj) or obj.name == 'Prototype faceted plasma':
        continue
    if obj.name.startswith('Trunk top armored panel') or (obj.name.startswith('SEUT / Tech Panel') and bounds(obj)[1] < -1.1):
        bpy.data.objects.remove(obj, do_unlink=True)
        continue
    low, high = bounds(obj)
    factor = roof_factor if obj in roof else (6.24/5.4 if high < -1.2 else 1.2)
    if obj.name.startswith('Curved chamber /'):
        factor = 1.2
    mesh = obj.data.copy()
    mesh.transform(obj.matrix_world)
    for vertex in mesh.vertices:
        vertex.co.x *= factor
        vertex.co.y *= factor
    obj.data = mesh
    obj.matrix_basis.identity()

# Collision follows the expanded floor/cap/chamber. Fixed port positions do not move.
for obj in cols['hkt'][0].objects:
    factor = 1.2 if obj.name.startswith('Curved chamber collision') else (6.24/4.5 if obj.location.z > 2 else (6.24/5.4 if obj.location.z < -3 else 1))
    obj.location.x *= factor
    obj.location.y *= factor
    for vertex in obj.data.vertices:
        vertex.co.x *= factor
        vertex.co.y *= factor

for sign, label in [(1, 'top'), (-1, 'bottom')]:
    rotation = Matrix.Rotation(0 if sign > 0 else math.pi, 4, 'X')
    # Clear the actual roof/floor skins so the port is not buried under the shell.
    cutter = conveyor_cutter((0, 0, sign*3.6), rotation, .7)
    for obj in list(col.objects):
        if obj == cutter or obj.type != 'MESH' or fixed_interface(obj) or obj.name.startswith('Axial conveyor /'):
            continue
        low, high = bounds(obj)
        if (sign > 0 and high < 3.25) or (sign < 0 and low > -3.25):
            continue
        points = [obj.matrix_world @ Vector(v) for v in obj.bound_box]
        if any(min(p[i] for p in points) > 1.01 or max(p[i] for p in points) < -1.01 for i in (0, 1)):
            continue
        bpy.context.view_layer.objects.active = obj
        cut = obj.modifiers.new('Axial conveyor access recess', 'BOOLEAN')
        cut.operation = 'DIFFERENCE'
        cut.object = cutter
        bpy.ops.object.modifier_apply(modifier=cut.name)
    bpy.data.objects.remove(cutter, do_unlink=True)

    for name in ['Conveyor Frame LG', 'Conveyor Access LG']:
        mesh = parts[name].data.copy()
        # Both native parts end at the exact outer grid face, within 1 mm.
        source_top = max(v.co.z for v in mesh.vertices)
        mesh.transform(Matrix.Translation((0, 0, sign*(3.749-source_top))) @ rotation)
        for i, material in enumerate(mesh.materials):
            mesh.materials[i] = native.get(material.name.split('.')[0], material)
        obj = bpy.data.objects.new('Axial conveyor / %s / %s' % (label, name), mesh)
        col.objects.link(obj)
        obj.parent = root
        obj['source_asset'] = 'SEUT Common.blend / '+name
    detector = bpy.data.objects.new('detector_conveyor_'+label, None)
    col.objects.link(detector)
    detector.parent = root
    detector.empty_display_type = 'CUBE'
    detector.empty_display_size = .5
    detector.location = (0, 0, sign*3.72)
    detector.scale = (1.38, 1.38, .08)
    detector['purpose'] = 'Centred vertical grid conveyor + native inventory interaction'

# Final port clearance: radial service greebles must not cover the native hatches.
for obj in list(col.objects):
    if obj.type != 'MESH':
        continue
    if obj.name.startswith(('Heat exchanger fin', 'SEUT / Maintenance Box')):
        center = sum((obj.matrix_world @ Vector(v) for v in obj.bound_box), Vector()) / 8
        if max(abs(center.x), abs(center.y)) > 5.7 and min(abs(center.x), abs(center.y)) < .9:
            bpy.data.objects.remove(obj, do_unlink=True)
            continue
    if obj.name.startswith('SEUT / Conveyor Frame LG'):
        center = sum((obj.matrix_world @ Vector(v) for v in obj.bound_box), Vector()) / 8
        axis = 0 if abs(center.x) > abs(center.y) else 1
        extent = max(abs(v.co[axis]) for v in obj.data.vertices)
        offset = math.copysign(max(0, extent-6.249), center[axis])
        for vertex in obj.data.vertices:
            vertex.co[axis] -= offset

# Clear the newly expanded barrel skin behind each fixed native interface.
for side in range(4):
    rotation = Matrix.Rotation(side*math.pi/2, 4, 'Z')
    center = rotation @ Vector((0, -6.15, -2.5))
    if side in (0, 2):
        cutter = conveyor_cutter(center, rotation @ Matrix.Rotation(math.pi/2, 4, 'X'), .8)
    else:
        bpy.ops.mesh.primitive_cube_add(size=1, location=center)
        cutter = bpy.context.object
        cutter.scale = (1.42, .8, 1.42)
        cutter.rotation_euler.z = side*math.pi/2
    bpy.context.view_layer.update()
    cp = [cutter.matrix_world @ Vector(v) for v in cutter.bound_box]
    for obj in list(col.objects):
        if obj == cutter or obj.type != 'MESH' or fixed_interface(obj) or obj.name.startswith('Axial conveyor /'):
            continue
        op = [obj.matrix_world @ Vector(v) for v in obj.bound_box]
        if any(max(p[i] for p in op) < min(p[i] for p in cp) or min(p[i] for p in op) > max(p[i] for p in cp) for i in range(3)):
            continue
        bpy.context.view_layer.objects.active = obj
        cut = obj.modifiers.new('Clear expanded barrel at native interface', 'BOOLEAN')
        cut.operation = 'DIFFERENCE'
        cut.object = cutter
        bpy.ops.object.modifier_apply(modifier=cut.name)
    bpy.data.objects.remove(cutter, do_unlink=True)

s['housings_widened'] = True
s['round_housing_radius'] = 6.24
s['inventory_access'] = 'Front/back plus centred roof/floor conveyors; left/right base upgrade sockets'
s['native_interface_centers'] = 'Side ports at horizontal +/-6.22 m, SE Y=-2.5; axial conveyors at SE Y=+/-3.72; all grid-centred'
bpy.context.view_layer.update()
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
print(s['inventory_access'], 'roof radial scale', roof_factor)
