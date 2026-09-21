"""Restore a true 80-triangle sphere after housing scaling; radius 1.30 m."""
import bpy
import bmesh
import math
import importlib
from mathutils import Vector

s = bpy.data.scenes['ArcanePower_ReactorPrototype']
bpy.context.window.scene = s
core = next(o for o in s.objects if o.name == 'Prototype faceted plasma')
center = sum((core.matrix_world @ v.co for v in core.data.vertices), Vector()) / len(core.data.vertices)
materials = list(core.data.materials)
mesh = bpy.data.meshes.new('Spherical containment field / 80 triangles')
bm = bmesh.new()
bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.30)
bm.to_mesh(mesh)
bm.free()
for vertex in mesh.vertices:
    vertex.co += center
for material in materials:
    mesh.materials.append(material)
uv = mesh.uv_layers.new(name='UVMap')
for polygon in mesh.polygons:
    polygon.use_smooth = False
    for loop in polygon.loop_indices:
        p = (mesh.vertices[mesh.loops[loop].vertex_index].co-center).normalized()
        uv.data[loop].uv = (.5+math.atan2(p.y, p.x)/math.tau, .5+math.asin(p.z)/math.pi)
core.data = mesh
core.matrix_basis.identity()
core['radius_m'] = 1.30
core['keep_spherical'] = True

# Compare sphere radius to the closest vertex on the inner ring, including its lug.
ring = bpy.data.scenes['ArcanePower_Ring1']
col = importlib.import_module('space-engineers-utilities.seut_collections').get_collections(ring)['main'][0]
inner_radius = min(math.hypot(*(o.matrix_world @ v.co)[:2]) for o in col.objects if o.type == 'MESH' for v in o.data.vertices)
assert inner_radius > 1.30
assert all(abs((v.co-center).length-1.30) < 1e-5 for v in mesh.vertices)
assert len(mesh.polygons) == 80
s['containment_field'] = 'True 80-triangle sphere, R1.30 m; uniform radius, independent of housing scaling'
bpy.context.view_layer.update()
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
print(s['containment_field'], 'inner ring vertex radius', round(inner_radius, 3))
