"""Author the four thermal-reactor pillar hulls, retaining the original HKT as base.

Run apply() in live Blender. Export with --export OUTPUT_DIRECTORY in a background
process, then tools/build_reactor_pillar_collision.py combines the two native HKTs.
SEUT exports four hulls here; it cannot export more than ten objects in one batch.
"""
import importlib
from pathlib import Path
import runpy

import bmesh
import bpy
from mathutils import Matrix

ROOT = Path(__file__).resolve().parents[1]
C = importlib.import_module('space-engineers-utilities.seut_collections')


def apply():
    scene = bpy.data.scenes['ArcanePower_Thermal_ReactorHousing']
    bpy.context.window.scene = scene
    bpy.context.view_layer.update()
    cols = C.get_collections(scene)
    collision = cols['hkt'][0]
    assert all(o.get('reactor_pillar_source') for o in collision.objects), 'Do not replace unrelated authored collision'
    jackets = [o for o in cols['main'][0].objects if o.get('reactor_source_name','').startswith(
        'Reactor exterior / chamfered pillar jacket')]
    assert len(jackets) == 4
    # Refresh owned hulls when the jackets change; the accepted original housing
    # physics is a separate input and is never regenerated here.
    for obj in list(collision.objects):
        mesh = obj.data
        bpy.data.objects.remove(obj,do_unlink=True)
        if mesh.users == 0:bpy.data.meshes.remove(mesh)
    template = next(o for o in bpy.data.objects if o.type == 'MESH' and o.rigid_body)
    uv = runpy.run_path(str(ROOT/'assets/thermal_parts.py'))['uv']
    for source in jackets:
        bm = bmesh.new()
        for vertex in source.data.vertices:
            bm.verts.new(source.matrix_world@vertex.co)
        bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.00001)
        hull = bmesh.ops.convex_hull(bm,input=list(bm.verts))
        bmesh.ops.delete(bm,geom=list(set(hull['geom_interior']+hull['geom_unused'])),context='VERTS')
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
        assert all(e.is_manifold for e in bm.edges) and bm.calc_volume() > 0
        mesh = bpy.data.meshes.new('Reactor pillar convex hull')
        bm.to_mesh(mesh);bm.free()
        mesh.materials.append(bpy.data.materials['Metal_Dull'])
        obj = template.copy();obj.data = mesh;obj.parent = None
        obj.name = 'AP collision / thermal pillar '+str(len(collision.objects)+1)
        obj.matrix_world = Matrix.Identity(4)
        collision.objects.link(obj);uv(obj)
        obj.rigid_body.collision_shape = 'CONVEX_HULL'
        obj.rigid_body.use_margin = True;obj.rigid_body.collision_margin = .01
        obj['reactor_pillar_source'] = source.name
        obj.hide_render = True;obj.display_type = 'WIRE'
    collision.seut.hkt_file = ''
    collision.hide_render = True;collision.hide_viewport = True
    scene['pillar_collision_revision'] = 1
    return {'pillar_hulls':4,'base_collision':'assets/collisions/Cubes/large/ArcanePower_ReactorPrototype.hkt'}


def export(directory):
    assert bpy.app.background, 'Export collision in a separate process'
    scene = bpy.data.scenes['ArcanePower_Thermal_ReactorHousing']
    bpy.context.window.scene = scene
    col = C.get_collections(scene)['hkt'][0]
    assert len(col.objects) == 4 and scene['pillar_collision_revision'] == 1
    output = Path(directory).resolve();output.mkdir(parents=True,exist_ok=True)
    assert output.is_relative_to(ROOT/'src/Models'), 'SEUT requires staging under the mod Models directory'
    errors = importlib.import_module('space-engineers-utilities.seut_errors')
    errors.show_popup_report = lambda context,title,text: print(title+': '+text,flush=True)
    scene.seut.export_exportPath = str(output)
    col.hide_viewport = False
    bpy.context.view_layer.update()
    class Reporter:
        def report(self,kind,message):print(kind,message,flush=True)
    ops = importlib.import_module('space-engineers-utilities.export.seut_ot_export')
    utils = importlib.import_module('space-engineers-utilities.export.seut_export_utils')
    assert ops.export_hkt(Reporter(),bpy.context) == {'FINISHED'}
    result = output/(utils.get_col_filename(col)+'.hkt')
    assert result.is_file() and result.stat().st_size > 0
    return {'pillar_hkt':str(result)}


if __name__ == '__main__':
    import sys
    args = sys.argv[sys.argv.index('--')+1:]
    assert len(args) == 2 and args[0] == '--export'
    print(export(args[1]),flush=True)
