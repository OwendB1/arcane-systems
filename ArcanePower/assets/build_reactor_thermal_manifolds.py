"""Primary pipe heads behind the reactor's original curved lower armor.

Each original panel splits along a radial plane. Leaves first inset 0.36 m,
then slide around the drum under neighbouring armor. Only then do the two male
pipe heads extend. Controller receivers, collars, glass and pillars stay intact.
The native lower bay centre is Z=-2.33; a one-cell transition restores the pipe
kit's Z=-2.5 lattice. Drivers preview mechanics only; no runtime mode code here.
"""
import json
import math
from pathlib import Path

import bpy
import bmesh
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
STOW_X, DEPLOY_X = 4.84, 6.25
STROKE = DEPLOY_X-STOW_X
CENTRE_Z = -2.33
INSET = .36
SLIDE = .155


def rounded_manifold(p, ident, side, y):
    """Twin isolated bores in a curved casting, with a moving rear connector.

    The 1.466 m capsule fits the original armor opening. Chamfered end rings
    keep the housing edges crisp; only the functional capsule is smooth.
    """
    count = 24
    outline = []
    for sign in (1, -1):
        for i in range(count+1):
            a = i*math.pi/count+(0 if sign > 0 else math.pi)
            outline.append((.42*math.cos(a), sign*.46+.273*math.sin(a)))
    verts = []
    profile = ((-.29, .96), (-.27, 1.), (-.15, 1.), (-.13, .96))
    for x, scale in profile:
        # Chamfer the capsule's perimeter without moving the bore centres.
        for dy, dz in outline:
            centre = .46 if dz > 0 else -.46
            verts.append((side*(STOW_X+x), y+dy*scale,
                          CENTRE_Z+centre+(dz-centre)*scale))
    n = len(outline)
    faces = [tuple(reversed(range(n))), tuple(range(3*n, 4*n))]
    for k in range(3):
        faces.extend((k*n+j, k*n+(j+1)%n, (k+1)*n+(j+1)%n, (k+1)*n+j)
                     for j in range(n))
    body = p.mesh(ident+' rounded twin-bore manifold', verts, faces, 'Metal_Dull')
    for sign in (-1, 1):
        z = CENTRE_Z+sign*.46
        bore = p.cylinder('temporary rounded manifold bore',
                          (side*(STOW_X-.50), y, z), (side*STOW_X, y, z), .232, sides=40)
        bpy.context.view_layer.objects.active = body
        mod = body.modifiers.new('Isolated primary through bore', 'BOOLEAN')
        mod.operation, mod.solver, mod.object = 'DIFFERENCE', 'EXACT', bore
        bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(bore, do_unlink=True)
    # The stock metric UV helper also covers the new through-bore surfaces.
    from runpy import run_path
    run_path(str(ROOT/'assets/build_thermal_concepts.py'))['uv'](body)
    body.data.materials.append(p.native['PaintedMetal_Darker'])
    for face in body.data.polygons:
        face.use_smooth = abs(face.normal.x) < .01 and abs(face.normal.z) > .01
        face.material_index = int(abs(face.normal.x) < .01)
    body['thermal_rounded_manifold'] = ident
    body['isolated_bore_radius_m'] = .232
    # A compact rounded bridge fills the gap between the casting and the
    # curved shell. A separate extending tail remains in the bulkhead guide;
    # its native axial-scale preview avoids entering the protected ring well.
    connector_verts = []
    for x, ry, rz in ((-.395, .16, .060), (-.355, .25, .155), (-.20, .25, .155)):
        for i in range(32):
            a = i*math.tau/32
            connector_verts.append((side*(STOW_X+x), y+ry*math.cos(a),
                                    CENTRE_Z+rz*math.sin(a)))
    connector_faces = [tuple(reversed(range(32))), tuple(range(64, 96))]
    for k in range(2):
        connector_faces.extend((k*32+j, k*32+(j+1)%32,
                                (k+1)*32+(j+1)%32, (k+1)*32+j) for j in range(32))
    connector = p.mesh(ident+' rounded moving housing connector', connector_verts,
                       connector_faces, 'PaintedMetal_Darker')
    for face in connector.data.polygons[2:]:
        face.use_smooth = True
    connector['thermal_moving_connector'] = ident
    connector['thermal_manifold_body'] = body.name
    anchor = Vector((side*(STOW_X-.72), y, CENTRE_Z))
    tail = p.cylinder(ident+' extending connector tail', anchor,
                      (side*(STOW_X-.375), y, CENTRE_Z), .060, 'PaintedMetal_Darker', 32)
    for vertex in tail.data.vertices:
        vertex.co -= anchor
        vertex.co.y *= .16/.060
    tail.location = anchor
    tail['thermal_extending_connector'] = ident
    tail['runtime_scale_axis'] = 'local X; fixed guide anchor'
    tail['runtime_scale_deployed'] = 1+STROKE/.345
    face_x = side*(STOW_X-.13)
    for dy in (-.32, .32):
        for dz in (-.10, .10):
            p.bolt(ident+' manifold captive stud', (face_x, y+dy, CENTRE_Z+dz),
                   (side, 0, 0), body, .018)
    label = p.label(body, 'PRIMARY', (face_x+side*.0015, y, CENTRE_Z),
                    (0, side, 0), (0, 0, 1), .055)
    label.data.materials.clear()
    label.data.materials.append(p.native['PaintedMetal_VeryDark'])
    return body, connector


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
    names = {o.name: c.name for o, c in copies.items()}
    for copy in copies.values():
        for key in copy.keys():
            value = copy[key]
            if key != 'reactor_source_name' and isinstance(value, str) and value in names:
                copy[key] = names[value]
    root = next(c for o, c in copies.items() if o.parent is None)
    p.scene['thermal_manifolds_deployment'] = 0.
    p.scene.id_properties_ui('thermal_manifolds_deployment').update(min=0., max=1.,
        description='0: standalone, original curved armor closed. 1: Brayton, pipe heads exposed.')
    p.scene['standalone_net_efficiency'] = .20
    p.scene['brayton_max_net_efficiency'] = .78
    p.scene['thermal_runtime_note'] = 'Model rig only. Standalone/Brayton switching is not installed in runtime.'
    bpy.context.view_layer.update()

    # The accepted panels contain the later service-door booleans. Reuse their
    # exact uncut geometry from the preserved checkpoint so no old hatch hole
    # remains in a closed manifold cover. Bounds/profile match the current panel.
    template_name = 'Uncut curved manifold armor template'
    template = bpy.data.meshes.get(template_name)
    if template is None:
        path = ROOT/'assets/arcane-power-before-exterior-detail.blend'
        with bpy.data.libraries.load(str(path), link=False) as (src, dst):
            dst.objects = ['Drum segmented armor.025']
        obj = dst.objects[0]
        template = obj.data
        template.transform(obj.matrix_world)
        template.name = template_name
        template.use_fake_user = True
        bpy.data.objects.remove(obj, do_unlink=True)
    for i, material in enumerate(template.materials):
        template.materials[i] = p.native[material.name.split('.')[0]]
    template['source_checkpoint'] = 'arcane-power-before-exterior-detail.blend'

    def centre(obj):
        return sum((obj.matrix_world@v.co for v in obj.data.vertices), Vector())/len(obj.data.vertices)

    def delta(a, b):
        return (a-b+math.pi)%math.tau-math.pi

    armor = [o for o in source_col.objects if o.type == 'MESH' and
             o.name.startswith('Drum segmented armor') and max((o.matrix_world@v.co).z for v in o.data.vertices) < 0]
    bays = []
    for side in (-1, 1):
        for y in (-2.5, 2.5):
            angle = math.atan2(y, side*5.5)
            panel = min(armor, key=lambda o: abs(delta(math.atan2(centre(o).y, centre(o).x), angle)))
            at = centre(panel)
            bays.append((side, y, panel, math.atan2(at.y, at.x)))
    removed = []
    for obj in list(copies.values()):
        if obj.type != 'MESH' or not obj['reactor_source_name'].startswith(('Reactor exterior / ', 'Texture detail / ')):
            continue
        at = centre(obj)
        if -3.08 < at.z < -1.58 and math.hypot(at.x, at.y) > 5.80 and any(
                abs(delta(math.atan2(at.y, at.x), a)) < .11 for _, _, _, a in bays):
            removed.append(obj['reactor_source_name'])
            bpy.data.objects.remove(obj, do_unlink=True)

    def sector(label, angle, half_span, inner, outer, z0, z1, mat='Metal_Dull'):
        count = max(8, math.ceil(half_span*2/.025))
        verts = []
        for i in range(count+1):
            a = angle-half_span+2*half_span*i/count
            verts.extend((r*math.cos(a), r*math.sin(a), z) for r, z in
                         ((inner, z0), (outer, z0), (outer, z1), (inner, z1)))
        faces = [(3, 2, 1, 0), tuple(range(count*4, count*4+4))]
        for i in range(count):
            for j in range(4):
                faces.append((4*i+j, 4*(i+1)+j, 4*(i+1)+(j+1)%4, 4*i+(j+1)%4))
        return p.mesh(label, verts, faces, mat)

    def cut(cutter, targets):
        bpy.context.view_layer.update()
        for obj in targets:
            if obj.data.users > 1:
                obj.data = obj.data.copy()
            mod = obj.modifiers.new('Internal curved manifold pocket', 'BOOLEAN')
            mod.operation, mod.solver, mod.object = 'DIFFERENCE', 'EXACT', cutter
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.modifier_apply(modifier=mod.name)
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=.00001)
            bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=.000005)
            # The original drum has a coincident radial cap at its mesh seam.
            # Welding after booleans exposes that internal face; removing it
            # restores two faces per edge without changing the solid's volume.
            internal = [f for f in bm.faces if all(len(e.link_faces) > 2 for e in f.edges)]
            if internal:
                bmesh.ops.delete(bm, geom=internal, context='FACES_ONLY')
            bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
            bm.to_mesh(obj.data)
            bm.free()
            layer = obj.data.uv_layers.active
            obj.data.calc_loop_triangles()
            # Boolean pocket walls can inherit a collapsed edge of the old
            # UVs. Repair those faces only, preserving accepted exterior UVs.
            collapsed = {t.polygon_index for t in obj.data.loop_triangles if t.area > 1e-8
                         and abs((layer.data[t.loops[1]].uv-layer.data[t.loops[0]].uv).cross(
                             layer.data[t.loops[2]].uv-layer.data[t.loops[0]].uv)) < 1e-11}
            for face in obj.data.polygons:
                if not obj.get('reactor_source_name') or face.index in collapsed:
                    axes = [i for i in range(3) if i != max(range(3), key=lambda j: abs(face.normal[j]))]
                    for li in face.loop_indices:
                        point = obj.data.vertices[obj.data.loops[li].vertex_index].co
                        layer.data[li].uv = (point[axes[0]]*.8+.17, point[axes[1]]*.8+.41)
            obj['thermal_pocket_cut'] = True
        bpy.data.objects.remove(cutter, do_unlink=True)

    def driver(obj, channel, index, expression):
        d = obj.driver_add(channel, index).driver
        d.type = 'SCRIPTED'
        var = d.variables.new()
        var.name, var.type = 'deploy', 'SINGLE_PROP'
        var.targets[0].id_type = 'SCENE'
        var.targets[0].id = p.scene
        var.targets[0].data_path = '["thermal_manifolds_deployment"]'
        d.expression = expression

    def joint_parent(objects, joint):
        bpy.context.view_layer.update()
        for obj in objects:
            world = obj.matrix_world.copy()
            obj.parent = joint
            obj.matrix_world = world
            obj['thermal_motion_group'] = joint.name
            if obj.get('thermal_support'):
                inv = joint.matrix_world.inverted()
                obj['support_point'] = tuple(inv@Vector(obj['support_point']))
                obj['support_axis'] = tuple(inv.to_3x3()@Vector(obj['support_axis']))
                obj['thermal_support_space'] = joint.name

    def split_panel(original, angle, half, ident):
        mesh = template.copy()
        mesh.transform(Matrix.Rotation(angle-math.pi/8, 4, 'Z'))
        tangent = Vector((-math.sin(angle), math.cos(angle), 0))
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.bisect_plane(bm, geom=list(bm.verts)+list(bm.edges)+list(bm.faces),
            dist=.000001, plane_co=tangent*(half*.003), plane_no=tangent,
            clear_inner=half > 0, clear_outer=half < 0)
        caps = bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary], sides=0)['faces']
        layer = bm.loops.layers.uv.active
        for face in caps:
            for loop in face.loops:
                loop[layer].uv = (loop.vert.co.dot(Vector((math.cos(angle), math.sin(angle), 0)))*.4,
                                  loop.vert.co.z*.4)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.to_mesh(mesh)
        bm.free()
        obj = bpy.data.objects.new('Curved manifold '+ident+' / original armor half '+str(half), mesh)
        p.col.objects.link(obj)
        obj['original_curved_panel'] = original.name
        obj['uncut_original_checkpoint'] = template['source_checkpoint']
        obj['thermal_cover'] = True
        obj['native_uv_preserved'] = True
        return obj

    drum = [o for o in p.col.objects if o.type == 'MESH' and o.get('reactor_source_name', '').startswith('Lower machinery drum')]
    # Fill the old 1.42 m conveyor opening directly, including its exposed
    # lower notch. The skin follows the drum/armor step and meets the original
    # aperture edges; avoid coplanar boolean subtraction against that armor.
    for obj in list(p.col.objects):
        if obj.get('reactor_source_name', '').startswith('AP upgrade socket / lower armor infill'):
            bpy.data.objects.remove(obj, do_unlink=True)
    for side in (-1, 1):
        count = 32
        verts = []
        for i in range(count+1):
            y = -.71+1.42*i/count
            inner = side*math.sqrt(6.00**2-y*y)
            drum_x = side*math.sqrt(6.124**2-y*y)
            armor_x = side*math.sqrt(6.158**2-y*y)
            verts.extend(((inner, y, -3.21), (drum_x, y, -3.21),
                          (drum_x, y, -3.07), (armor_x, y, -3.07),
                          (armor_x, y, -1.79), (inner, y, -1.79)))
        faces = [tuple(reversed(range(6))), tuple(range(count*6, count*6+6))]
        for i in range(count):
            faces.extend((i*6+j, i*6+(j+1)%6, (i+1)*6+(j+1)%6, (i+1)*6+j)
                         for j in range(6))
        backing = p.mesh('restored controller backing '+str(side), verts, faces,
                         'PaintedMetal_Colorable')
        aperture = p.box('temporary native controller aperture', (side*6.10, 0, CENTRE_Z),
                         (1., .60, .60), chamfer=.04)
        cut(aperture, [backing])
        backing['thermal_controller_backing'] = side
        backing['native_socket_preserved'] = True
    motion = []
    for side, y, original, angle in bays:
        ident = ('R' if side > 0 else 'L')+('A' if y < 0 else 'B')
        # Only the original drum gets internal pockets. Original perimeter
        # collars/foundation, neighbouring armor and controller seat survive.
        window = sector('temporary original armor opening', angle, .117, 5.45, 6.30, -3.075, -1.585)
        cut(window, drum)
        storage = sector('temporary side storage pocket', angle, .292, 5.55, 6.005, -3.075, -1.585)
        cut(storage, drum)
        # The original twin bores do not clear the new shared casting. Give
        # its full travel a real internal pocket, behind the unchanged armor.
        pocket = p.box('temporary rounded casting travel pocket',
                       (side*5.365, y, CENTRE_Z), (1.89, .88, 1.49), chamfer=0)
        cut(pocket, drum)
        bpy.data.objects.remove(copies[original], do_unlink=True)
        for z0, z1 in ((-3.145, -3.080), (-1.580, -1.515)):
            rail = sector(ident+' hidden curved guide channel', angle, .292, 5.55, 6.10, z0, z1)
            rail['thermal_fixed_support'] = True
        rear = p.box(ident+' internal pressure bulkhead', (side*4.35, y, CENTRE_Z),
                     (.12, 1.24, 1.68), 'PaintedMetal_Darker', .018)
        guide = p.cylinder('temporary moving connector guide',
                           (side*3.95, y, CENTRE_Z), (side*5.10, y, CENTRE_Z), .080, sides=32)
        for vertex in guide.data.vertices:
            vertex.co.y = y+(vertex.co.y-y)*2.25
        cut(guide, [rear]+drum)
        for sign in (-1, 1):
            z = CENTRE_Z+sign*.46
            bore = p.cylinder('temporary sleeve bore', (side*3.10, y, z), (side*5.10, y, z), .335, sides=40)
            cut(bore, [rear]+drum)
            # Stagger ends inside the gland; coplanar annular caps flicker.
            p.tube(ident+' fixed telescopic sleeve', ((side*3.15, y, z), (side*4.375, y, z)),
                   .320, 'PaintedMetal_VeryDark', .030, 40)
            p.tube(ident+' anchored pressure gland', ((side*4.32, y, z), (side*4.45, y, z)),
                   .375, 'Metal_Dull', .085, 40)
        for dy in (-.50, .50):
            for dz in (-.72, .72):
                p.bolt(ident+' captive bulkhead stud', (side*4.408, y+dy, CENTRE_Z+dz),
                       (side, 0, 0), rear, .025)
        p.label(rear, 'PRIMARY', (side*4.412, y+side*.40, CENTRE_Z), (0, side, 0), (0, 0, 1), .055)
        intermediate = bpy.data.objects.new('Thermal manifold '+ident+' / intermediate sleeve', None)
        p.col.objects.link(intermediate)
        intermediate.location = (side*4.50, y, CENTRE_Z)
        intermediate.empty_display_size = .06
        intermediate['runtime_translation_axis'] = (side, 0, 0)
        intermediate['runtime_translation_metres'] = STROKE/2
        before = set(p.col.objects)
        for sign in (-1, 1):
            z = CENTRE_Z+sign*.46
            p.tube(ident+' intermediate pressure sleeve', ((side*3.40, y, z), (side*4.50, y, z)),
                   .280, 'Metal_Dull', .010, 40)
        joint_parent(set(p.col.objects)-before, intermediate)
        driver(intermediate, 'location', 0, f'{side*4.50}+{side*STROKE/2}*max(0,min(1,(deploy-.45)/.55))')
        carriage = bpy.data.objects.new('Thermal manifold '+ident+' / carriage', None)
        p.col.objects.link(carriage)
        carriage.location = (side*STOW_X, y, CENTRE_Z)
        carriage.empty_display_size = .08
        carriage['runtime_translation_axis'] = (side, 0, 0)
        carriage['runtime_translation_metres'] = STROKE
        before = set(p.col.objects)
        for sign in (-1, 1):
            z = CENTRE_Z+sign*.46
            stem = p.tube(ident+' sliding '+('H' if sign > 0 else 'C')+' primary stem',
                [(side*x, y, z) for x in (STOW_X-1.15, STOW_X-.26)],
                .265, 'Metal_Dull', .035, 40)
            stem['thermal_pressure_part'] = True
            neck = p.tube(ident+' manifold outlet '+('H' if sign > 0 else 'C'),
                [(side*x, y, z) for x in (STOW_X-.15, STOW_X-.11, STOW_X-.09, STOW_X-.075)],
                .265, 'Metal_Dull', .035, 40)
            neck.data.materials.append(p.native['PaintedMetal_Yellow' if sign > 0 else 'PaintedMetal_Clean'])
            for face in neck.data.polygons:
                if STOW_X-.11 < abs(face.center.x) < STOW_X-.09 and abs(face.normal.x) < .01:
                    face.material_index = 1
            p.tube(ident+' compact sealing nose', ((side*(STOW_X-.08), y, z), (side*STOW_X, y, z)),
                   .273, 'Metal_Dull', .038, 40)
        rounded_manifold(p, ident, side, y)
        joint_parent(set(p.col.objects)-before, carriage)
        tail = next(o for o in carriage.children if o.get('thermal_extending_connector') == ident)
        travel = 'max(0,min(1,(deploy-.45)/.55))'
        driver(tail, 'location', 0, f'{-side*.72}-{side*STROKE}*{travel}')
        driver(tail, 'scale', 0, f'1+{STROKE/.345}*{travel}')
        driver(carriage, 'location', 0, f'{side*STOW_X}+{side*STROKE}*max(0,min(1,(deploy-.45)/.55))')
        port = {'id': 'primary '+ident, 'type': 'PRIMARY', 'position': [side*DEPLOY_X, y, CENTRE_Z],
                'normal': [side, 0, 0], 'hot_axis': [0, 0, 1], 'cell_offset': [0, 0, .17],
                'adapter': 'PRIMARY / Reactor adapter'}
        p.ports.append(port)
        row = {'id': ident, 'carriage': carriage.name, 'stroke_m': STROKE, 'source_panel': original.name,
               'intermediate_stage': intermediate.name,
               'panel_angle': angle, 'stowed_face': [side*STOW_X, y, CENTRE_Z],
               'deployed_face': port['position'], 'cover_slides': []}
        for half in (-1, 1):
            slide = bpy.data.objects.new('Thermal manifold '+ident+' / curved slide '+str(half), None)
            p.col.objects.link(slide)
            slide.empty_display_size = .07
            leaf = split_panel(original, angle, half, ident)
            # Preserve native atlas UVs and project every decal corner onto its
            # actual armor leaf. Marks travel with the leaf, never over the gap.
            a = angle+half*.055
            n = Vector((math.cos(a), math.sin(a), 0))
            u = Vector((-n.y, n.x, 0))
            mark = p.hazard(leaf, n*6.20+Vector((0, 0, -2.78)), u, (0, 0, 1),
                            'Sign High Pressure' if half < 0 else 'Sign Remote Operated', .13)
            backing = BVHTree.FromPolygons([v.co for v in leaf.data.vertices], [tuple(f.vertices) for f in leaf.data.polygons])
            for vertex in mark.data.vertices:
                hit, normal, _, _ = backing.ray_cast(vertex.co+n*.10, -n, .30)
                assert hit is not None, 'Cover marking must have continuous backing'
                vertex.co = hit+normal*.0015
            joint_parent([leaf, mark], slide)
            turn = f'({half*SLIDE}*max(0,min(1,(deploy-.15)/.25)))'
            inset = f'({INSET}*max(0,min(1,deploy/.15)))'
            driver(slide, 'rotation_euler', 2, turn)
            driver(slide, 'location', 0, f'-{inset}*cos({angle}+{turn})')
            driver(slide, 'location', 1, f'-{inset}*sin({angle}+{turn})')
            slide['runtime_slide_axis'] = 'arc about reactor Z'
            slide['runtime_slide_radians'] = half*SLIDE
            slide['runtime_radial_inset_m'] = INSET
            row['cover_slides'].append(slide.name)
        motion.append(row)
    p.col['manifold_motion'] = json.dumps(motion)
    p.col['manifold_retired_details'] = json.dumps(removed)
    p.scene['thermal_manifold_revision'] = 4
    p.scene['thermal_manifold_state_order'] = 'isolate -> retract pipes -> slide armor closed -> seat; reverse to expose'
    for obj in p.col.objects:
        if not obj.parent and obj.type != 'EMPTY':
            obj.parent = root
    bpy.context.view_layer.update()
    return {'manifolds': len(motion), 'original_curved_armor_halves': 8, 'pipe_stroke_m': STROKE,
            'sideways_slide_rad': SLIDE, 'pocket_inset_m': INSET, 'retired_old_details': len(removed)}


def pose(value):
    scene = bpy.data.scenes['ArcanePower_Thermal_ReactorHousing']
    assert 0 <= value <= 1
    bpy.context.window.scene = scene
    scene['thermal_manifolds_deployment'] = value
    scene.update_tag()
    scene.frame_set(scene.frame_current)
    bpy.context.view_layer.update()
    return {'deployment': value, 'scene': scene.name}
