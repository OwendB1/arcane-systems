"""Replace the legacy reactor colliders with baked, walkable housing geometry.

Run in the current prototype blend through Blender MCP. Only the main scene's
collision collection changes. Ten convex bodies: base, roof and eight panes.
Moving hatch physics remain outside this static housing collision model.
"""
import importlib
import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
scene = bpy.data.scenes['ArcanePower_ReactorPrototype']
bpy.context.window.scene = scene
collections = importlib.import_module('space-engineers-utilities.seut_collections').get_collections(scene)
main, collision = collections['main'][0], collections['hkt'][0]
collision.hide_viewport = False
bpy.context.view_layer.update()


def points(prefix):
    return [obj.matrix_world @ v.co for obj in main.objects
            if obj.type == 'MESH' and obj.name.startswith(prefix) for v in obj.data.vertices]


glass = points('Curved chamber / pane')
deck = points('Deck removable plate')
rims = points('Upper armored rim')
assert glass and deck and rims, 'Expected the current widened reactor housing'
radius = max(p.xy.length for p in glass)
glass_bottom, glass_top = min(p.z for p in glass), max(p.z for p in glass)
deck_top = max(p.z for p in deck)
roof_bottom, roof_top = min(p.z for p in rims), max(p.z for p in rims)
housing_radius = max(p.xy.length for p in rims)
assert 4.9 < radius < 5 and 6.2 < housing_radius < 6.25

# Preserve a local rollback copy before replacing any authored collision.
backup = Path.home() / '.cache/arcane-power/collision/before.blend'
backup.parent.mkdir(parents=True, exist_ok=True)
if not backup.exists():
    bpy.ops.wm.save_as_mainfile(filepath=str(backup), copy=True)

for obj in list(collision.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
collision.seut.hkt_file = ''
material = next(m for m in bpy.data.materials if m.name == 'Metal_Dull' and m.library)


def hull(name, vertices):
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    for p in vertices:
        bm.verts.new(p)
    result = bmesh.ops.convex_hull(bm, input=list(bm.verts))
    bmesh.ops.delete(bm, geom=list(set(result['geom_interior'] + result['geom_unused'])), context='VERTS')
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    mesh.materials.append(material)
    uv = mesh.uv_layers.new(name='UVMap')
    for polygon in mesh.polygons:
        axes = [i for i in range(3) if i != max(range(3), key=lambda i: abs(polygon.normal[i]))]
        for index in polygon.loop_indices:
            p = mesh.vertices[mesh.loops[index].vertex_index].co
            uv.data[index].uv = (p[axes[0]] / 2.5, p[axes[1]] / 2.5)
    obj = bpy.data.objects.new(name, mesh)
    collision.objects.link(obj)
    # SE consumes Havok shapes, not a Blender rigid-body scene. Bake the entire
    # placement into vertices so no body transform is needed to position a shape.
    obj.matrix_world = Matrix.Identity(4)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.rigidbody.object_add(type='ACTIVE')
    obj.rigid_body.collision_shape = 'CONVEX_HULL'
    obj.rigid_body.use_margin = True
    obj.rigid_body.collision_margin = .01
    obj.display_type = 'WIRE'
    obj.hide_render = True
    return obj


def cylinder(name, bottom, top):
    return hull(name, [(housing_radius * math.cos(i * math.tau / 64),
                        housing_radius * math.sin(i * math.tau / 64), z)
                       for z in (bottom, top) for i in range(64)])


# A complete drum supports the visible deck throughout, including its centre.
# The old four boxes left a central hole and projected beyond the round housing.
cylinder('AP collision / base and platform', -3.75, deck_top)
cylinder('AP collision / roof platform', roof_bottom, roof_top)
for sector in range(8):
    start = math.pi / 4 + sector * math.pi / 4
    hull('AP collision / glass %02d' % sector,
         [(r * math.cos(start + i * math.pi / 64),
           r * math.sin(start + i * math.pi / 64), z)
          for i in range(17) for r in (radius - .08, radius)
          for z in (glass_bottom, glass_top)])

scene['reactor_collision_revision'] = 'baked-platforms-eight-panes-v1'
scene.seut.export_sbc_type = 'none'
bpy.context.view_layer.update()
assert len(collision.objects) == 10
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / 'assets/arcane-power-prototype.blend'))
print('Saved 10 baked convex colliders; deck Z=%.3f, roof Z=%.3f, glass R=%.3f' %
      (deck_top, roof_top, radius))
