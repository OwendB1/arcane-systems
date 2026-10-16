"""Protect accepted mains while deliberately replacing their derived meshes."""
import importlib
import json
import math
from pathlib import Path
import runpy

import bpy

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'validation/reactor-texture-lod-loop'
COLS=importlib.import_module('space-engineers-utilities.seut_collections')
FINGERPRINT=runpy.run_path(str(ROOT/'assets/refine_reactor_exterior.py'))['fingerprint']


def begin():
    """Retain old evidence, explicitly retire only authorized BS/LOD baselines."""
    FOLDER.mkdir(exist_ok=True)
    family='energy' if 'ArcanePower_EnergyCore' in bpy.data.scenes else 'prototype'
    path=FOLDER/(family+'-protected.json')
    if path.exists():return {'baseline_exists':True}
    derived=set();protected={}
    for scene in bpy.data.scenes:
        if not scene.name.startswith('ArcanePower_'):continue
        bpy.context.window.scene=scene;bpy.context.view_layer.update()
        cs=COLS.get_collections(scene)
        for kind in ('main','hkt'):
            for col in cs.get(kind) or []:
                protected.update({o.name:FINGERPRINT(o) for o in col.objects})
        for kind in ('bs','lod'):
            for col in cs.get(kind) or []:derived.update(o.name for o in col.objects)
    retired={}
    for relative in ('reactor-exterior-loop-01/source.json','controller-detail-loop-01/source.json','energy-construction-update/protected-source.json','native-texture-detail/source.json'):
        target=ROOT/'validation'/relative
        if not target.exists():continue
        data=json.loads(target.read_text())
        mapping=data['sources'][family]['geometry'] if relative.startswith('native-texture') else data.get('protected_objects',data)
        previous={n:mapping.pop(n) for n in list(mapping) if n in derived}
        if previous:
            retired[relative]=previous
            target.write_text(json.dumps(data,indent=2)+'\n')
    path.write_text(json.dumps({'source':bpy.data.filepath,'protected_objects':protected,'retired_derived_baselines':retired},indent=2)+'\n')
    return {'protected_main_collision_objects':len(protected),'retired_derived_entries':sum(map(len,retired.values()))}


def main():
    family='energy' if 'ArcanePower_EnergyCore' in bpy.data.scenes else 'prototype'
    baseline=json.loads((FOLDER/(family+'-protected.json')).read_text())
    failures=[];rows={}
    for scene in bpy.data.scenes:
        if not scene.name.startswith('ArcanePower_'):continue
        bpy.context.window.scene=scene;bpy.context.view_layer.update()
        cs=COLS.get_collections(scene);main=cs['main'][0]
        for col in (cs.get('bs') or [])+(cs.get('lod') or []):
            if not col.objects:continue
            for obj in col.objects:
                if obj.type!='MESH':failures.append('Non-mesh derived object: '+obj.name);continue
                if not obj.data.uv_layers or not all(math.isfinite(x) for d in obj.data.uv_layers.active.data for x in d.uv):failures.append('Invalid derived UVs: '+obj.name)
                if obj.get('texture_support') and col.seut.col_type=='bs':
                    owners={o.get('source_object') for o in col.objects}
                    if obj['texture_support'] not in owners:failures.append('Missing decal backing: '+obj.name)
                if col.seut.col_type=='bs' and any(m and any(t in m.name for t in ('Emissive','ArcanePlasma','ClearChamber','EnergyGlow','EnergyFill','EnergyStatus')) for m in obj.data.materials):failures.append('Powered/glazed construction mesh: '+obj.name)
            rows[col.name]={'objects':len(col.objects),'triangles':sum(len(p.vertices)-2 for o in col.objects if o.type=='MESH' for p in o.data.polygons)}
        main_count=sum(len(p.vertices)-2 for o in main.objects if o.type=='MESH' for p in o.data.polygons)
        lods=sorted((c for c in cs.get('lod') or [] if c.seut.ref_col==main and c.objects),key=lambda c:c.seut.type_index)
        previous=main_count
        for col in lods:
            count=rows[col.name]['triangles']
            if not 0<count<previous:failures.append('LOD fails progressive reduction: '+col.name)
            previous=count
    for name,sha in baseline['protected_objects'].items():
        if name not in bpy.data.objects or FINGERPRINT(bpy.data.objects[name])!=sha:failures.append('Accepted main/collision changed: '+name)
    report={'passed':not failures,'failures':failures,'protected_main_collision_objects':len(baseline['protected_objects']),'collections':rows,'live_game_checked':False}
    (FOLDER/(family+'-derived-audit.json')).write_text(json.dumps(report,indent=2)+'\n')
    assert not failures,'\n'.join(failures)
    return report


if __name__=='__main__':result=main()
