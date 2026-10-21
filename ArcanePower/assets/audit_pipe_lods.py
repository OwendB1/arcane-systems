"""Check real derived pipe collars: closed rings, UVs and unchanged main art.

Run in live Blender or with the production thermal blend in background mode.
"""
import hashlib
import json
import math
from pathlib import Path
import runpy

import bpy
import bmesh

ROOT = Path(__file__).resolve().parents[1]


def audit():
    export = runpy.run_path(str(ROOT/'assets/export_thermal_models.py'))
    previous = bpy.context.scene
    rows = []

    def fingerprint(col):
        return hashlib.sha256(repr([(o.name, [tuple(v.co) for v in o.data.vertices],
            [tuple(p.vertices) for p in o.data.polygons], [tuple(v.uv) for v in o.data.uv_layers.active.data])
            for o in col.objects if o.type == 'MESH']).encode()).hexdigest()

    try:
        for shape in ('Straight', 'Riser', 'Roll adapter', 'Tee'):
            name = 'PRIMARY / '+shape+' bare'
            source = export['M']['main_for'](name)
            before = fingerprint(source)
            prepared = export['prepare'](name)
            scene = bpy.data.scenes[prepared['scenes'][-1]]
            cols = export['C'].get_collections(scene)
            main = cols['main'][0]
            previous_count = export['tris'](main)
            for col in sorted((c for c in cols['lod'] if c.seut.ref_col == main), key=lambda c: c.seut.type_index):
                count = export['tris'](col)
                assert 0 < count < previous_count, (name, 'LOD budgets must decrease', count, previous_count)
                previous_count = count
                rings = [o for o in col.objects if o.get('lod_collar_sides')]
                assert rings, (name, 'Missing controlled collar simplification')
                for obj in rings:
                    bm = bmesh.new(); bm.from_mesh(obj.data)
                    assert all(e.is_manifold for e in bm.edges) and bm.calc_volume(signed=True) > 0, obj.name
                    bm.free()
                    original = bpy.data.objects[obj['lod_source']]
                    vertices = {tuple(v.co) for v in original.data.vertices}
                    assert all(tuple(v.co) in vertices for v in obj.data.vertices), 'Collar vertices left the original surface'
                    mesh = obj.data; mesh.calc_loop_triangles(); uv = mesh.uv_layers.active
                    assert uv and all(math.isfinite(v) for p in uv.data for v in p.uv)
                    assert all(abs((uv.data[t.loops[1]].uv-uv.data[t.loops[0]].uv).cross(
                        uv.data[t.loops[2]].uv-uv.data[t.loops[0]].uv)) > 1e-11
                        for t in mesh.loop_triangles if t.area > 1e-8), 'Collapsed collar UVs'
                rows.append({'model': name, 'level': col.seut.type_index, 'triangles': count,
                             'collars': len(rings), 'radial_sides': sorted({o['lod_collar_sides'] for o in rings})})
            assert fingerprint(source) == before, 'LOD generation changed authored main geometry or UVs'
    finally:
        bpy.context.window.scene = previous
    report = {'status': 'passed', 'checks': 'Closed positive collars, uniform radial sectors, original surface vertices, complete UVs, decreasing LOD budgets and unchanged mains', 'models': rows}
    (ROOT/'validation/thermal-models/pipe-lods.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    print(audit())
