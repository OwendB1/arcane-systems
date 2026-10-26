"""Native, separately selectable terminal panels on the two primary blocks.

Run apply_energy(scene) or apply_reactor(scene, main) in the authoring file.
The supplied pose is in the owning root's frame; native sockets stay untouched.
"""
from pathlib import Path
import importlib

import bpy
from mathutils import Matrix, Vector


def highlight_terminal(dummy, body):
    """Native contour selection requires both an exported section and its link."""
    if '_section' not in body.name:
        body.name += '_section'
    dummy['highlight'] = body.name
    dummy.seut.highlight_objects.clear()
    dummy.seut.highlight_objects.add().obj = body


def panel(scene, main, root, position, normal, prefix, detector_name):
    bpy.context.window.scene = scene
    bpy.context.view_layer.update()
    normal = Vector(normal).normalized()
    right = Vector((0, 0, 1)).cross(normal).normalized()
    pose = Matrix((right, normal.cross(right), normal)).transposed().to_4x4()
    pose.translation = position
    detector_offset = Matrix.Translation((0,0,.047)) @ Matrix.Diagonal((.25,.51,.10,1))
    existing = next((o for o in main.objects if o.name == detector_name), None)
    if existing:
        old_pose = existing.matrix_basis @ detector_offset.inverted()
        delta = pose @ old_pose.inverted()
        for obj in main.objects:
            if obj.type == 'MESH' and obj.get('control_access') and obj.name in {
                    prefix+label for label in ('terminal_section', 'terminal screen', 'terminal backing')}:
                obj.data.transform(delta)
        existing.matrix_basis = pose @ detector_offset
        bpy.context.view_layer.update()
        return existing
    library = Path.home()/'.local/share/blender-se1-setup/assets/Models/Common.blend'
    with bpy.data.libraries.load(str(library), link=False) as (_, loaded):
        loaded.objects = ['Terminal LG', 'Terminal Screen']
    source_parts = list(loaded.objects)
    body = source_parts[0].data
    # Normalize the pair together, retaining the screen's seating and native UVs.
    center = Vector(((min(v.co.x for v in body.vertices)+max(v.co.x for v in body.vertices))/2,
                     (min(v.co.y for v in body.vertices)+max(v.co.y for v in body.vertices))/2,
                     min(v.co.z for v in body.vertices)))
    transform = pose @ Matrix.Translation(Vector((0, 0, .018))-center)
    meshes = []
    for source, label in zip(source_parts, ('terminal_section', 'terminal screen')):
        mesh = source.data.copy()
        mesh.transform(transform)
        for i, material in enumerate(mesh.materials):
            mesh.materials[i] = next((m for m in bpy.data.materials
                if m.library and m.name == material.name.split('.')[0]), material)
        obj = bpy.data.objects.new(prefix+label, mesh)
        main.objects.link(obj)
        obj.parent = root
        obj['source_asset'] = 'SEUT Common.blend / '+source.name.split('.')[0]
        obj['build_stage'] = 3 if label.endswith('_section') else 4
        obj['control_access'] = True
        meshes.append(obj)
    for source in source_parts:
        bpy.data.objects.remove(source, do_unlink=True)
    # Solid backing with clipped corners; its back is seated inside the casing.
    x, y, cut = .15, .28, .012
    outline = [(-x+cut,-y),(x-cut,-y),(x,-y+cut),(x,y-cut),
               (x-cut,y),(-x+cut,y),(-x,y-cut),(-x,-y+cut)]
    verts = [pose @ Vector((x,y,z)) for z in (-.018,.022) for x,y in outline]
    faces = [tuple(reversed(range(8))), tuple(range(8,16))]
    faces += [(i,(i+1)%8,(i+1)%8+8,i+8) for i in range(8)]
    mesh = bpy.data.meshes.new(prefix+'terminal backing')
    mesh.from_pydata(verts, [], faces)
    mesh.materials.append(bpy.data.materials['PaintedMetal_Darker'])
    uv = mesh.uv_layers.new(name='UVMap')
    for face in mesh.polygons:
        axes = [i for i in range(3) if i != max(range(3), key=lambda i:abs(face.normal[i]))]
        for li in face.loop_indices:
            p = mesh.vertices[mesh.loops[li].vertex_index].co
            uv.data[li].uv = (p[axes[0]]*.8+.17,p[axes[1]]*.8+.41)
    backing = bpy.data.objects.new(prefix+'terminal backing', mesh)
    main.objects.link(backing)
    backing.parent = root
    backing['build_stage'] = 3
    backing['control_access'] = True
    dummy = bpy.data.objects.new(detector_name, None)
    main.objects.link(dummy)
    dummy.parent = root
    dummy.matrix_basis = pose @ detector_offset
    dummy.empty_display_type = 'CUBE'
    dummy.empty_display_size = .5
    highlight_terminal(dummy, meshes[0])
    dummy['purpose'] = 'Dedicated native control-panel access, separate from inventory and upgrade sockets'
    dummy['control_access'] = True
    bpy.context.view_layer.update()
    return dummy


def apply_energy(scene):
    cols = importlib.import_module('space-engineers-utilities.seut_collections')
    main = cols.get_collections(scene)['main'][0]
    root = next(o for o in main.objects if o.parent is None)
    return panel(scene, main, root, (-.916457,3.25,-2.25),(-.920646,-.390398,0),
                 'Energy / control ', 'detector_terminal_control')


def apply_reactor(scene, main):
    root = next(o for o in main.objects if o.get('reactor_source_name') == 'ArcanePower_ReactorPrototype root')
    # Seat on the flat armor strips beside both inventory hatches. The keypad
    # clears the conveyor frame by 15 cm and its backing stays inside the strip.
    panels = []
    for sign, suffix in ((1, ''), (-1, '_opposite')):
        panels.append(panel(scene, main, root, (sign*1.26,sign*-6.026703,-2.25),
                            (sign*.208776265,sign*-.977963448,0),
                            'Thermal reactor / control '+('opposite ' if suffix else ''),
                            'Thermal reactor / detector_terminal_control'+suffix))
    return panels
