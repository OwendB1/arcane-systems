"""Derive reversed fittings from finished mains, preserving native detail/UVs.

The elbow reflects across Y. The riser keeps its accepted pressure geometry,
but puts H on the outer arc: both socket axes, markings and indicators change
together. Bare forms use build_thermal_models.build_bare_pipe afterward.
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
    base = m['CONTRACT']['REVERSED_PIPES'][name]
    source_scene, source = m['scene_for'](base), m['main_for'](base)
    bpy.context.window.scene = source_scene
    bpy.context.view_layer.update()
    assert source_scene['thermal_phase'] == 'textures'
    assert all(o.parent is None for o in source.objects), 'Pipe mains must be static'
    poses = {o: o.matrix_world.copy() for o in source.objects}
    ports = json.loads(source['ports'])
    elbow = base.endswith('Elbow')
    reflect = Matrix.Diagonal((1, -1, 1, 1))
    p = m['Parts'](name)
    for key, value in source.items():
        if key != 'seut':
            p.col[key] = value
    p.col['thermal_model'] = name
    p.col['pipe_shape'] = name.split(' / ')[1]
    copies = {}
    for old in source.objects:
        obj = old.copy()
        if old.data:
            obj.data = old.data.copy()
        obj.animation_data_clear()
        suffix = old.name.removeprefix(base+' / ')
        if not elbow:
            for left, right in (('insulated H channel', 'insulated C channel'),
                                ('hot indicator', 'cold indicator')):
                if left in suffix:
                    suffix = suffix.replace(left, right)
                elif right in suffix:
                    suffix = suffix.replace(right, left)
        obj.name = name+' / '+suffix
        p.col.objects.link(obj)
        copies[old] = obj
    renamed = {old.name: obj.name for old, obj in copies.items()}
    for old, obj in copies.items():
        pose = poses[old]
        obj.matrix_world = pose
        if elbow:
            if obj.get('thermal_text'):
                # Local horizontal reflection restores readable text glyphs.
                obj.matrix_world = reflect @ pose @ Matrix.Diagonal((-1, 1, 1, 1))
            elif obj.type == 'MESH':
                obj.data.transform(reflect @ pose)
                mesh = bmesh.new(); mesh.from_mesh(obj.data)
                bmesh.ops.reverse_faces(mesh, faces=list(mesh.faces))
                mesh.to_mesh(obj.data); mesh.free()
                obj.matrix_world = Matrix.Identity(4)
                if obj.get('source_asset') and obj.data.uv_layers.active:
                    uv = obj.data.uv_layers.active.data
                    lo, hi = min(v.uv.x for v in uv), max(v.uv.x for v in uv)
                    for v in uv:
                        v.uv.x = lo+hi-v.uv.x
                if 'thermal_bore_axis' in obj:
                    axis = reflect.to_3x3() @ pose.to_3x3().col[obj['thermal_bore_axis']]
                    obj['thermal_bore_axis'] = max(range(3), key=lambda i: abs(axis[i]))
                obj.data.update()
            else:
                # Preserve a proper frame and its world-space hot direction.
                obj.matrix_world = reflect @ pose @ Matrix.Diagonal((-1, 1, 1, 1))
            for key in ('support_point', 'support_axis', 'thermal_nozzle_centre', 'thermal_nozzle_normal'):
                if key in obj:
                    obj[key] = reflect.to_3x3() @ Vector(obj[key])
            if obj.get('pipe_path'):
                obj['pipe_path'] = json.dumps([list(reflect @ Vector(v)) for v in json.loads(obj['pipe_path'])])
        else:
            for slot in obj.material_slots:
                if slot.material and slot.material.name in ('ThermalHot', 'ThermalCold'):
                    slot.material = bpy.data.materials['ThermalCold' if slot.material.name == 'ThermalHot' else 'ThermalHot']
            if obj.get('port_id'):
                obj['hot_axis'] = tuple(-v for v in obj['hot_axis'])
            if obj.get('thermal_text') in ('H', 'C'):
                support = obj['thermal_marking_support']
                port = next(port for port in ports if support == base+' / '+port['id']+' flange')
                obj.location += Vector(port['hot_axis'])*(-.92 if obj['thermal_text'] == 'H' else .92)
        for key, value in list(obj.items()):
            if isinstance(value, str) and value in renamed:
                obj[key] = renamed[value]
    p.ports = ports
    for port in p.ports:
        if elbow:
            for key in ('position', 'normal', 'hot_axis'):
                port[key] = list(reflect.to_3x3() @ Vector(port[key]))
        else:
            port['hot_axis'] = [-v for v in port['hot_axis']]
    p.finish()
    for key, value in source_scene.items():
        if key.startswith('thermal_') and key != 'thermal_model':
            p.scene[key] = value
    p.scene['thermal_reversed_of'] = base
    bpy.context.view_layer.update()
    runpy.run_path(str(ROOT/'assets/refine_thermal_flow.py'))['record'](p)
    runpy.run_path(str(ROOT/'assets/enclose_thermal_pipes.py'))['audit'](p)
    return m['record'](name)


if __name__ == '__main__':
    result = build(globals()['MODEL_NAME'])
