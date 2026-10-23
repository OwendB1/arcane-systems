"""Derive the opposite-handed turbine from its finished single-socket main.

Reflection is baked into private meshes, with corrected winding and readable
markings. Native rotor roots retain proper transforms and their original pivots.
"""
import json
from pathlib import Path
import runpy

import bpy
import bmesh
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]


def build(name):
    m = runpy.run_path(str(ROOT/'assets/build_thermal_models.py'))
    base = name.replace(' mirrored', '')
    assert name != base and base in ('Brayton train', 'Brayton train upgraded')
    source_scene, source = m['scene_for'](base), m['main_for'](base)
    bpy.context.window.scene = source_scene
    bpy.context.view_layer.update()
    assert source_scene['thermal_phase'] == 'textures' and len(json.loads(source['ports'])) == 1
    poses = {obj: obj.matrix_world.copy() for obj in source.objects}
    p = m['Parts'](name)
    reflect = Matrix.Diagonal((1, -1, 1, 1))
    copies = {}
    for old in source.objects:
        obj = old.copy()
        if old.data: obj.data = old.data.copy()
        obj.animation_data_clear()
        obj.parent = None
        obj.name = name+' / '+old.name.removeprefix(base+' / ')
        p.col.objects.link(obj)
        copies[old] = obj
    renamed = {old.name: obj.name for old, obj in copies.items()}
    for old, obj in copies.items():
        pose = poses[old]
        if obj.type == 'MESH' and obj.get('thermal_text'):
            # Keep an outward local text frame as well as readable glyphs.
            obj.matrix_world = reflect @ pose @ Matrix.Diagonal((-1, 1, 1, 1))
        elif obj.type == 'MESH':
            local = Matrix.Identity(4)
            parent = copies.get(old.parent)
            pivot = reflect @ poses[old.parent].translation if parent else Vector((0, 0, 0))
            transform = Matrix.Translation(-pivot) @ reflect @ pose @ local
            obj.data.transform(transform)
            if transform.determinant() < 0:
                mesh = bmesh.new(); mesh.from_mesh(obj.data)
                bmesh.ops.reverse_faces(mesh, faces=list(mesh.faces))
                mesh.to_mesh(obj.data); mesh.free()
            if obj.get('source_asset') and obj.data.uv_layers.active:
                # Reflect atlas decals back within their own UV rectangle.
                uv = obj.data.uv_layers.active.data
                lo, hi = min(v.uv.x for v in uv), max(v.uv.x for v in uv)
                for v in uv: v.uv.x = lo+hi-v.uv.x
            obj.parent = parent
            obj.matrix_parent_inverse = Matrix.Identity(4)
            obj.matrix_basis = Matrix.Identity(4)
            obj.data.update()
            if 'thermal_bore_axis' in obj:
                axis = reflect.to_3x3() @ pose.to_3x3().col[obj['thermal_bore_axis']]
                obj['thermal_bore_axis'] = max(range(3), key=lambda i: abs(axis[i]))
        else:
            obj.matrix_world = reflect @ pose @ reflect
        for key, value in list(obj.items()):
            if isinstance(value, str) and value in renamed: obj[key] = renamed[value]
        for key in ('support_point', 'support_axis', 'thermal_nozzle_centre', 'thermal_nozzle_normal',
                    'native_pivot_blender', 'native_axis_blender'):
            if key in obj: obj[key] = reflect.to_3x3() @ Vector(obj[key])
        if obj.get('pipe_path'):
            obj['pipe_path'] = json.dumps([list(reflect @ Vector(v)) for v in json.loads(obj['pipe_path'])])
        if old.type == 'EMPTY' and old.get('native_subpart'):
            driver = obj.driver_add('rotation_euler', 0).driver
            var = driver.variables.new(); var.name = 'angle'; var.type = 'SINGLE_PROP'
            var.targets[0].id = obj; var.targets[0].data_path = '["preview_angle_degrees"]'
            driver.expression = 'angle*pi/180'
    p.ports = m['CONTRACT']['train_ports'](name)
    p.finish()
    for key, value in source_scene.items():
        if key.startswith('thermal_') and key != 'thermal_model': p.scene[key] = value
    p.scene['thermal_mirror_of'] = base
    bpy.context.view_layer.update()
    runpy.run_path(str(ROOT/'assets/refine_thermal_flow.py'))['record'](p)
    return m['record'](name)


if __name__ == '__main__':
    result = build(globals()['MODEL_NAME'])
