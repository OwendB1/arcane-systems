"""Check battery construction progression against its current finished models."""
import bpy
import bmesh
import importlib
import json
import math
import runpy
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]


def main():
    folder=ROOT/'validation/energy-construction-update'
    protected=json.loads((folder/'protected-source.json').read_text())
    fingerprint=runpy.run_path(str(ROOT/'assets/refine_reactor_exterior.py'))['fingerprint']
    cols=importlib.import_module('space-engineers-utilities.seut_collections')
    names=runpy.run_path(str(ROOT/'assets/build_construction_stages.py'))['ENERGY']
    failures=[];rows={}
    def require(ok,message):
        if not ok:failures.append(message)
    # Refresh inactive scene matrices before comparing copied subpart poses.
    for scene in bpy.data.scenes:
        if scene.name.startswith('ArcanePower_'):
            bpy.context.window.scene=scene;bpy.context.view_layer.update()
    for name,sha in protected.items():require(name in bpy.data.objects and fingerprint(bpy.data.objects[name])==sha,'Finished/collision/LOD object changed: '+name)
    for name in names:
        scene=bpy.data.scenes[name];bpy.context.window.scene=scene;bpy.context.view_layer.update();cs=cols.get_collections(scene)
        main=cs['main'][0];root=next(o for o in main.objects if o.parent is None);frame=root.matrix_world.inverted()
        sources={o.name:o for o in main.objects};stages=sorted(cs['bs'],key=lambda c:c.seut.type_index)
        require([c.seut.type_index for c in stages]==[1,2,3],name+': expected three construction stages')
        previous=set();counts=[];stage_rows=[];core=name.endswith('Core')
        for collection in stages:
            stage=collection.seut.type_index;members={o.get('source_object'):o for o in collection.objects if o.get('source_object')};triangles=0;static={}
            require(all(o.type=='MESH' for o in collection.objects),name+': animated stage dummy')
            require(any(m and m.name=='Construction' for o in collection.objects for m in o.data.materials),name+': missing weld steel')
            require(previous.issubset(members),name+': equipment disappears during armor installation')
            for obj in collection.objects:
                mesh=obj.data;triangles+=sum(len(p.vertices)-2 for p in mesh.polygons)
                require(bool(mesh.uv_layers),obj.name+': missing UVs')
                require(all(math.isfinite(x) for uv in mesh.uv_layers for d in uv.data for x in d.uv),obj.name+': invalid UV')
                require(all(m and m.library and not any(s in m.name for s in ('Emissive','EnergyGlow','EnergyFill','EnergyStatus','ClearChamber')) for m in mesh.materials),obj.name+': powered, glazed or non-native stage material')
                used={l.vertex_index for l in mesh.loops};points=[frame @ obj.matrix_world @ mesh.vertices[i].co for i in used]
                half=(3.751,3.751,3.751) if core else (1.251,1.251,3.751)
                require(all(math.isfinite(p[i]) and abs(p[i])<=half[i] for p in points for i in range(3)),obj.name+': incorrect construction scale/offset')
                bm=bmesh.new();bm.from_mesh(mesh)
                require(all(f.calc_area()>1e-8 for f in bm.faces),obj.name+': collapsed construction triangle')
                if not obj.get('source_object'):
                    require(all(e.is_manifold and e.is_contiguous for e in bm.edges),obj.name+': open/inconsistent weld frame')
                    require(bm.calc_volume(signed=True)>0,obj.name+': inverted weld frame')
                bm.free()
                source=bpy.data.objects.get(obj.get('source_object',''))
                if not source:continue
                owner=obj.get('source_owner',source.name)
                if obj.get('construction_static_subpart'):
                    dummy=sources.get(owner);require(dummy is not None,obj.name+': missing static subpart mount')
                    expected=dummy.matrix_world @ source.matrix_world if dummy else obj.matrix_world
                    static[owner]=static.get(owner,0)+1
                    require('Rotor' not in obj['construction_static_subpart'],obj.name+': charged field in unfinished stage')
                else:
                    expected=source.matrix_world
                    require(source.get('build_stage',3)<=3,obj.name+': finished-only component in construction stage')
                    require(owner==source.name or owner in members,obj.name+': fitting has no installed owner')
                    if source.get('fastener_body'):require(source['fastener_body'] in members,obj.name+': fastener face floats without its body')
                require(max(abs(a-b) for ra,rb in zip(expected,obj.matrix_world) for a,b in zip(ra,rb))<.00001,obj.name+': source part offset changed')
            if stage==1:require(not members,name+': fitted equipment in bare frame')
            if stage>=2:
                ports=sum('native upgrade port' in source for source in members)
                require(ports==(12 if core else 3),name+': triple mating sections missing')
                if 'Stabilizer' in name:require(len(static)==3 and len(set(static.values()))==1,name+': three complete static fans required')
            if stage==3:
                if core:require(sum(n.startswith('Energy / segmented drum armor') for n in members)==18,name+': partial drum panel grouping changed')
                else:
                    require(sum(n.startswith('Module / side armor') for n in members)==3,name+': expected one fitted armor side')
                    require(sum(n.startswith('Module / armored endcap') for n in members)==1,name+': expected one complete end deck')
                    require(sum(n.startswith('Module / inset service door') for n in members)==3,name+': service assemblies not grouped with panels')
            previous=set(members);counts.append(triangles)
            stage_rows.append({'stage':stage,'meshes':len(collection.objects),'triangles':triangles,'source_components':len(members),'static_subparts':static})
        require(counts[0]<counts[1]<counts[2],name+': stages do not increase in assembly detail')
        rows[name]=stage_rows
    report={'passed':not failures,'failures':failures,'protected_objects_unchanged':len(protected),'source':rows,'live_game_checked':False}
    (folder/'geometry.json').write_text(json.dumps(report,indent=2)+'\n')
    if failures:raise AssertionError('\n'.join(failures))
    return report


if __name__=='__main__':result=main()
