"""Four retractable primary manifolds flanking the two native controller bays.

Runs as a production thermal builder. Copies the accepted reactor, cuts only
lower machinery pockets, and keeps pillars/glass/native interfaces untouched.
Scene property thermal_manifolds_deployment (0..1) sequences inward doors before
the telescoping carriage. Blender drivers are a mechanical preview, not runtime.
"""
import json
import math
from pathlib import Path

import bpy
import bmesh
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
STOW_X, DEPLOY_X = 4.76, 6.25
STROKE = DEPLOY_X-STOW_X


def build(p):
    from importlib import import_module
    cols = import_module('space-engineers-utilities.seut_collections').get_collections
    source = bpy.data.scenes['ArcanePower_ReactorPrototype']
    source_col = cols(source)['main'][0]
    copies = {}
    for obj in source_col.objects:
        copy = obj.copy()
        copy.name = 'Thermal reactor / '+obj.name
        p.col.objects.link(copy)
        copy['reactor_source_name'] = obj.name
        copies[obj] = copy
    for obj, copy in copies.items():
        copy.parent = copies.get(obj.parent)
        copy.matrix_basis = obj.matrix_basis.copy()
    # Remap references on copied details without touching the accepted source.
    names = {o.name: c.name for o, c in copies.items()}
    for copy in copies.values():
        for key in copy.keys():
            value = copy[key]
            if isinstance(value, str) and value in names:
                copy[key] = names[value]
    root = next(c for o, c in copies.items() if o.parent is None)
    p.scene['thermal_manifolds_deployment'] = 0.
    p.scene.id_properties_ui('thermal_manifolds_deployment').update(min=0., max=1.,
        description='0: standalone, covered. 1: Brayton, all four primary duplex sockets deployed.')
    p.scene['standalone_net_efficiency'] = .20
    p.scene['brayton_max_net_efficiency'] = .78
    p.scene['thermal_runtime_note'] = 'Rigged model only; no generator-mode switching code is installed.'

    def bounds(obj):
        pts = [obj.matrix_world@Vector(v) for v in obj.bound_box]
        return [min(v[i] for v in pts) for i in range(3)], [max(v[i] for v in pts) for i in range(3)]

    def cut(cutter, objects):
        bpy.context.view_layer.update()
        lo, hi = bounds(cutter)
        for obj in objects:
            a, b = bounds(obj)
            if any(b[i] < lo[i] or a[i] > hi[i] for i in range(3)):
                continue
            if obj.data.users > 1:
                obj.data = obj.data.copy()
            mod = obj.modifiers.new('Machined thermal cassette pocket', 'BOOLEAN')
            mod.operation, mod.solver, mod.object = 'DIFFERENCE', 'EXACT', cutter
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.modifier_apply(modifier=mod.name)
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=.00001)
            bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=.000005)
            bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
            bm.to_mesh(obj.data)
            bm.free()
            obj['thermal_pocket_cut'] = True
        bpy.data.objects.remove(cutter, do_unlink=True)

    # Retire the old door/vent decoration where the new machinery seats. Native
    # controller receiver, conveyor interfaces and all upper hardware survive.
    removed = []
    bpy.context.view_layer.update()
    for obj in list(copies.values()):
        if obj.type != 'MESH' or not obj['reactor_source_name'].startswith('Reactor exterior / '):
            continue
        lo, hi = bounds(obj)
        centre = (Vector(lo)+Vector(hi))/2
        if abs(centre.x) > 4.6 and 1.20 < abs(centre.y) < 3.80 and -3.62 < centre.z < -1.43:
            removed.append(obj['reactor_source_name'])
            bpy.data.objects.remove(obj, do_unlink=True)
    targets = [o for o in p.col.objects if o.type == 'MESH' and o.get('reactor_source_name', '').startswith(
        ('Lower machinery drum', 'Drum segmented armor', 'Machined perimeter collar', 'Round foundation'))]
    for side in (-1, 1):
        for y in (-2.5, 2.5):
            cutter = p.box('temporary thermal bay cutter', (side*5.43, y, -2.50), (2.14, 2.40, 2.24), chamfer=0)
            cut(cutter, targets)

    motion = []

    def driver(obj, channel, index, expression):
        curve = obj.driver_add(channel, index)
        d = curve.driver
        d.type = 'SCRIPTED'
        var = d.variables.new()
        var.name, var.type = 'deploy', 'SINGLE_PROP'
        var.targets[0].id_type = 'SCENE'
        var.targets[0].id = p.scene
        var.targets[0].data_path = '["thermal_manifolds_deployment"]'
        d.expression = expression

    def parent_joint(objects, joint):
        bpy.context.view_layer.update()
        for obj in objects:
            world = obj.matrix_world.copy()
            obj.parent = joint
            obj.matrix_world = world
            obj['thermal_motion_group'] = joint.name
            if obj.get('thermal_support'):
                obj['support_point'] = tuple(joint.matrix_world.inverted()@Vector(obj['support_point']))
                obj['support_axis'] = tuple(joint.matrix_world.to_3x3().inverted()@Vector(obj['support_axis']))
                obj['thermal_support_space'] = joint.name

    for side in (-1, 1):
        n = Vector((side, 0, 0))
        for y in (-2.5, 2.5):
            ident = ('R' if side > 0 else 'L')+('A' if y < 0 else 'B')
            # The fixed cassette's outside remains a quiet armored cheek when
            # closed. Its rear is embedded in the actual round drum, not air.
            shell = p.box(ident+' fixed manifold cassette', (side*5.27, y, -2.50),
                          (1.70, 2.46, 2.30), 'PaintedMetal_Colorable', .045)
            cutter = p.box('temporary cassette bore', (side*5.52, y, -2.50),
                           (2.0, 2.34, 2.12), chamfer=0)
            cut(cutter, [shell])
            shell['thermal_fixed_support'] = True
            # Narrow planar lip, backed around the whole pocket perimeter.
            for dz in (-1.105, 1.105):
                p.box(ident+' horizontal pocket rail', (side*6.10, y, -2.5+dz),
                      (.12, 2.46, .09), 'Metal_Dull', .012)
            for dy in (-1.145, 1.145):
                p.box(ident+' vertical pocket rail', (side*6.10, y+dy, -2.5),
                      (.12, .09, 2.12), 'Metal_Dull', .012)
            for dz in (-.46, .46):
                cutter = p.cylinder('temporary primary sleeve bore', (side*2.50, y, -2.5+dz),
                                    (side*4.65, y, -2.5+dz), .410, 'Metal_Dull', 40)
                cut(cutter, [shell]+targets)
                p.tube(ident+' fixed primary pressure sleeve', ((side*2.55, y, -2.5+dz),
                       (side*4.50, y, -2.5+dz)), .360, 'PaintedMetal_VeryDark', .070, 32)
                p.tube(ident+' seated rear pressure gland', ((side*4.38, y, -2.5+dz),
                       (side*4.50, y, -2.5+dz)), .395, 'Metal_Dull', .105, 32)
            for dy in (-.96, .96):
                p.box(ident+' carriage slide track', (side*5.30, y+math.copysign(1.08,dy), -2.5),
                      (1.60, .12, .18), 'Metal_Shiny', .009)
            joint = bpy.data.objects.new('Thermal manifold '+ident+' / carriage', None)
            p.col.objects.link(joint)
            joint.location = (side*STOW_X, y, -2.5)
            joint.empty_display_size = .10
            joint['runtime_translation_axis'] = tuple(n)
            joint['runtime_translation_metres'] = STROKE
            before = set(p.col.objects)
            p.port('primary '+ident, (side*STOW_X, y, -2.5), tuple(n), 'PRIMARY')
            p.ports[-1]['position'] = [side*DEPLOY_X, y, -2.5]
            for dz in (-.46, .46):
                p.tube(ident+' sliding primary pressure tube',
                       ((side*(STOW_X-2.05), y, -2.5+dz), (side*(STOW_X-.13), y, -2.5+dz)),
                       .275, 'Metal_Shiny', .045, 32)
            for dy in (-.96, .96):
                p.box(ident+' carriage guide runner', (side*(STOW_X-.26), y+dy, -2.5),
                      (.36, .10, .27), 'PaintedMetal_Darker', .014)
            parent_joint(set(p.col.objects)-before, joint)
            driver(joint, 'location', 0, f'{side*STOW_X}+{side*STROKE}*max(0,min(1,(deploy-.35)/.65))')
            motion.append({'id': ident, 'carriage': joint.name, 'stowed_face': [side*STOW_X, y, -2.5],
                           'deployed_face': [side*DEPLOY_X, y, -2.5], 'stroke_m': STROKE, 'doors': []})
            # Two inward-folding armor leaves stay outside the travelling
            # flange footprint. Open doors first, close only after full stow.
            for edge in (-1, 1):
                hinge = bpy.data.objects.new('Thermal manifold '+ident+' / door '+str(edge), None)
                p.col.objects.link(hinge)
                hinge.location = (side*6.04, y+edge*1.10, -2.5)
                hinge.empty_display_size = .08
                before = set(p.col.objects)
                leaf = p.panel(ident+' inward armor shutter', (side*6.04, y+edge*.55, -2.5),
                               (.060, 1.092, 2.08), tuple(n))
                for z in (-3.24, -1.76):
                    p.cylinder(ident+' shutter hinge barrel', (side*6.04, y+edge*1.10, z-.10),
                               (side*6.04, y+edge*1.10, z+.10), .042, 'Metal_Dull', 12)
                parent_joint(set(p.col.objects)-before, hinge)
                angle = -edge*side*math.pi/2
                driver(hinge, 'rotation_euler', 2, f'{angle}*max(0,min(1,deploy/.35))')
                hinge['runtime_hinge_axis'] = (0, 0, 1)
                hinge['runtime_open_angle_radians'] = angle
                motion[-1]['doors'].append(hinge.name)
    p.col['manifold_motion'] = json.dumps(motion)
    p.col['manifold_retired_details'] = json.dumps(removed)
    p.scene['thermal_manifold_revision'] = 1
    p.scene['thermal_manifold_state_order'] = 'isolate -> retract carriage -> close doors; open doors -> deploy -> admit heat'
    # A parent is provided for the new static pieces; dynamic joints remain
    # explicit roots with their own transforms for later SE subpart export.
    for obj in p.col.objects:
        if not obj.parent and obj.type != 'EMPTY':
            obj.parent = root
    bpy.context.view_layer.update()
    return {'manifolds': len(motion), 'stroke_m': STROKE, 'retired_old_details': len(removed)}


def pose(value):
    scene = bpy.data.scenes['ArcanePower_Thermal_ReactorHousing']
    assert 0 <= value <= 1
    bpy.context.window.scene = scene
    scene['thermal_manifolds_deployment'] = value
    scene.update_tag()
    scene.frame_set(scene.frame_current)
    bpy.context.view_layer.update()
    return {'deployment': value, 'scene': scene.name}
