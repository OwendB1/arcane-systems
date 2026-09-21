"""Replace blocky pillar feet and flat upgrade adapters with curved housing details."""
import bpy
import bmesh
import importlib
import math
from mathutils import Vector

s = bpy.data.scenes['ArcanePower_ReactorPrototype']
bpy.context.window.scene = s
col = importlib.import_module('space-engineers-utilities.seut_collections').get_collections(s)['main'][0]
root = next(o for o in col.objects if o.parent is None)
native = {m.name: m for m in bpy.data.materials if m.library}

for obj in list(col.objects):
    if obj.name.startswith(('Spine base foot', 'Base upgrade / adapter plate', 'Integrated support /', 'Integrated upgrade /')):
        bpy.data.objects.remove(obj, do_unlink=True)


def project_uv(mesh, only_degenerate=False):
    uv = mesh.uv_layers.active or mesh.uv_layers.new(name='UVMap')
    for face in mesh.polygons:
        if only_degenerate and any((uv.data[i].uv-uv.data[face.loop_start].uv).length > 1e-6 for i in face.loop_indices):
            continue
        axes = [i for i in range(3) if i != max(range(3), key=lambda i: abs(face.normal[i]))]
        for i in face.loop_indices:
            v = mesh.vertices[mesh.loops[i].vertex_index].co
            uv.data[i].uv = (v[axes[0]]/2.5, v[axes[1]]/2.5)


def solid(name, vertices, segments):
    faces = [(4*i+j, 4*(i+1)+j, 4*(i+1)+(j+1)%4, 4*i+(j+1)%4)
             for i in range(segments) for j in range(4)]
    faces += [(3, 2, 1, 0), tuple(4*segments+j for j in range(4))]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    mesh.materials.append(native['PaintedMetal_Colorable'])
    project_uv(mesh)
    obj = bpy.data.objects.new(name, mesh)
    col.objects.link(obj)
    obj.parent = root
    bpy.context.view_layer.objects.active = obj
    bevel = obj.modifiers.new('Machined housing edges', 'BEVEL')
    bevel.width = .025
    bevel.segments = 3
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    return obj


# The low curved saddle flares into the deck while supporting the spine and pipes.
for i in range(4):
    center = -math.pi/4+i*math.pi/2
    vertices = []
    for step in range(13):
        t = -1+step/6
        for radius, z, spread in [(4.22, -1.32, .18), (5.88, -1.32, .18),
                                  (5.55, -.98, .145), (4.54, -.98, .145)]:
            a = center+t*spread
            vertices.append((radius*math.cos(a), radius*math.sin(a), z))
    solid('Integrated support / curved pillar saddle %s' % i, vertices, 12)

# Curved socket surround: raised only around the native fitting, feathered into
# the drum at its perimeter. The actual socket and detector remain untouched.
for side in (-1, 1):
    center = 0 if side > 0 else math.pi
    vertices = []
    for step in range(17):
        u = -.8+step*.1
        a = center+u/6.235
        half_height = .78-max(0, abs(u)-.66)
        outer = 6.235-.145*(abs(u)/.8)**2
        for radius, z in [(5.92, -2.5-half_height), (outer, -2.5-half_height),
                          (outer, -2.5+half_height), (5.92, -2.5+half_height)]:
            vertices.append((radius*math.cos(a), radius*math.sin(a), z))
    obj = solid('Integrated upgrade / curved socket surround %s' % side, vertices, 16)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(side*6.13, 0, -2.5))
    cutter = bpy.context.object
    cutter.scale = (.8, .73, .73)
    cutter.data.materials.append(native['PaintedMetal_Colorable'])
    bpy.context.view_layer.objects.active = obj
    cut = obj.modifiers.new('Native upgrade socket aperture', 'BOOLEAN')
    cut.operation = 'DIFFERENCE'
    cut.object = cutter
    bpy.ops.object.modifier_apply(modifier=cut.name)
    bpy.data.objects.remove(cutter, do_unlink=True)
    project_uv(obj.data, only_degenerate=True)

# Booleans may introduce an empty material slot and collapsed UVs on new cut walls.
# Repair those walls on authored housing meshes while preserving existing mappings.
for obj in col.objects:
    if obj.type != 'MESH' or not any(m is None for m in obj.data.materials):
        continue
    for face in obj.data.polygons:
        if obj.data.materials[face.material_index] is None:
            face.material_index = 0
    for i in reversed(range(len(obj.data.materials))):
        if obj.data.materials[i] is None:
            obj.data.materials.pop(index=i)
    project_uv(obj.data, only_degenerate=True)

s['support_integration'] = 'Curved tapered pillar saddles and drum-shaped upgrade surrounds; native interfaces unchanged'
bpy.context.view_layer.update()
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
print(s['support_integration'])
