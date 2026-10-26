"""Focused controller geometry, seating and preservation checks; Blender only."""
import bpy
import bmesh
import importlib
import json
import math
import runpy
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT=Path(__file__).resolve().parents[1]
PREFIX='Controller detail / '


def main():
    source=json.loads((ROOT/'validation/controller-detail-loop-01/source.json').read_text())
    fingerprint=runpy.run_path(str(ROOT/'assets/refine_reactor_exterior.py'))['fingerprint']
    failures=[];rows=[]
    def require(ok,message):
        if not ok:failures.append(message)
    for name,sha in source['protected_objects'].items():require(name in bpy.data.objects and fingerprint(bpy.data.objects[name])==sha,'Protected object changed: '+name)
    for name,record in source['variants'].items():
        scene=bpy.data.scenes[name];bpy.context.window.scene=scene;bpy.context.view_layer.update()
        col=importlib.import_module('space-engineers-utilities.seut_collections').get_collections(scene)['main'][0]
        meshes=[o for o in col.objects if o.type=='MESH'];details=[o for o in meshes if o.name.startswith(PREFIX)]
        shell=bpy.data.objects[record['shell']];trees={}
        def points(o):return [o.matrix_world @ v.co for v in o.data.vertices]
        def tree(o):
            if o not in trees:trees[o]=BVHTree.FromPolygons(points(o),[tuple(p.vertices) for p in o.data.polygons])
            return trees[o]
        rims=[o for o in details if o.name.startswith(PREFIX+'stepped receiver')]
        require(scene.get('controller_receiver_revision')==2,name+': receiver seating repair missing')
        require(scene.get('controller_aperture_revision')==1,name+': receiver wall clearance missing')
        rim_samples=0;cover_gaps=[]
        for rim in rims:
            w=2*max(v.co.x for v in rim.data.vertices);h=2*max(v.co.y for v in rim.data.vertices)
            require(abs(max(v.co.z for v in rim.data.vertices)-.006)<.00001,rim.name+': rim is coplanar with casing')
            normal=(rim.matrix_world.to_3x3() @ Vector((0,0,1))).normalized()
            for axis,half in ((0,w/2),(1,h/2)):
                for sign in (-1,1):
                    point=Vector((0,0,-.008));point[axis]=sign*(half-.025)
                    direction=Vector((0,0,0));direction[axis]=sign
                    hit,n,index,distance=tree(shell).ray_cast(rim.matrix_world@point,rim.matrix_world.to_3x3()@direction,.02)
                    require(hit is not None and .009<distance<.011,rim.name+': inner wall coincides with casing aperture')
            for x,y in ((w/2-.008,0),(-w/2+.008,0),(0,h/2-.008),(0,-h/2+.008)):
                p=rim.matrix_world @ Vector((x,y,.006));hit,n,index,distance=tree(shell).ray_cast(p,-normal,.010)
                require(hit is not None and n.dot(normal)>.9 and .0055<distance<.0065,rim.name+': lip overlaps casing or lacks backing');rim_samples+=1
        for panel in [o for o in details if o.name.startswith(tuple(PREFIX+x for x in ('broad service cassette','paired power cartridge','side inspection cover','status carrier')))]:
            rim=min(rims,key=lambda r:(r.matrix_world.translation-panel.matrix_world.translation).length)
            local=rim.matrix_world.inverted();ps=[local @ p for p in points(panel)]
            gap=min(max(v.co[i] for v in rim.data.vertices[32:40])-max(abs(p[i]) for p in ps) for i in (0,1))
            require(gap>=.004,panel.name+': cover intersects lower receiver shoulder');cover_gaps.append(gap)
        for p in record['rear_shell_vertices']:require(any((v.co-Vector(p)).length<.00001 for v in shell.data.vertices),name+': curved adapter or native socket changed')
        for obj in meshes:
            bm=bmesh.new();bm.from_mesh(obj.data)
            if not obj.get('source_asset'):
                require(all(e.is_manifold and e.is_contiguous for e in bm.edges),obj.name+': open or inconsistent solid')
                require(bm.calc_volume(signed=True)>1e-10,obj.name+': inverted or empty solid')
            bm.free()
            require(bool(obj.data.uv_layers),obj.name+': UVs missing')
            require(all(math.isfinite(x) for uv in obj.data.uv_layers for d in uv.data for x in d.uv),obj.name+': invalid UV')
            require(all(m and m.library for m in obj.data.materials),obj.name+': non-native material')
            require(all(m.type!='BEVEL' or m.segments==1 for m in obj.modifiers),obj.name+': rounded structural fillet')
            # Only the new receiver lips stand 6 mm proud of the accepted case.
            lip=.006 if obj in rims else .0015 if obj.get('texture_support') else 0
            require(all(abs(p.x)<=.8001+lip and -1.3813<=p.y<=-.9959 and -.3301<=p.z<=.6701+lip for p in points(obj)),obj.name+': detail exceeds accepted pack bounds')
        screws=[o for o in details if o.name.startswith(PREFIX+'captive screw')]
        for obj in screws:
            support=bpy.data.objects.get(obj.get('support',''));require(support is not None,obj.name+': screw support missing')
            if support:
                normal=(obj.matrix_world.to_3x3() @ Vector((0,0,1))).normalized()
                hit,n,index,distance=tree(support).ray_cast(obj.matrix_world.translation-normal*.003,normal,.020)
                require(hit is not None and n.dot(normal)>.9,obj.name+': screw floats above its support')
        faces=[o for o in details if 'fastener_body' in o]
        for obj in faces:
            body=bpy.data.objects.get(obj['fastener_body']);require(body in meshes,obj.name+': screw body missing')
            normal=(obj.matrix_world.to_3x3() @ Vector((0,0,1))).normalized();origin=obj.matrix_world.translation+normal*.001
            for other in meshes:
                if other in (obj,body):continue
                hit,n,index,distance=tree(other).ray_cast(origin,normal,.025)
                require(hit is None,obj.name+': screw head buried by '+other.name)
        vane_samples=0;bridge_samples=0
        for obj in details:
            if obj.name.startswith(PREFIX+'supported cooling vane'):
                support=bpy.data.objects[obj['support']];normal=(support.matrix_world.to_3x3() @ Vector((0,0,1))).normalized()
                for x in (min(v.co.x for v in obj.data.vertices)+.002,max(v.co.x for v in obj.data.vertices)-.002):
                    p=obj.matrix_world @ Vector((x,0,0));hit,n,index,distance=tree(support).ray_cast(p,normal,.06)
                    require(hit is not None and n.dot(normal)>.9,obj.name+': unsupported cooling-vane end');vane_samples+=1
            if 'support_0' in obj:
                fin='heat spreader' in obj.name;normal=(obj.matrix_world.to_3x3() @ Vector((0,0,1))).normalized()
                depth=max(v.co.z for v in obj.data.vertices)-min(v.co.z for v in obj.data.vertices)
                for i,offset in enumerate((-.105,.105) if fin else (-.235,.235)):
                    support=bpy.data.objects.get(obj['support_'+str(i)]);require(support is not None,obj.name+': terminal or saddle missing')
                    p=obj.matrix_world @ Vector((0,offset,depth/2+.002) if fin else (offset,0,depth/2+.002))
                    hit,n,index,distance=tree(support).ray_cast(p,-normal,depth+.003) if support else (None,None,None,None)
                    require(hit is not None and n.dot(normal)>.9,obj.name+': bus or fin misses its support');bridge_samples+=1
        lamps=[o for o in details if o.name.startswith(PREFIX+'seated status emitter')]
        require(len(lamps)==(2 if 'Advanced' in name else 1),name+': wrong tier lamp count')
        for obj in lamps:
            backing=bpy.data.objects[obj['support']];normal=(obj.matrix_world.to_3x3() @ Vector((0,0,1))).normalized()
            lamp_front=max(p.dot(normal) for p in points(obj));backing_front=max(p.dot(normal) for p in points(backing))
            require(lamp_front-backing_front>.004,obj.name+': coplanar status lamp/backing')
        rows.append({'scene':name,'main_meshes':len(meshes),'triangles':sum(len(p.vertices)-2 for o in meshes for p in o.data.polygons),'seated_screws':len(screws),'visible_screw_heads':len(faces),'vane_support_samples':vane_samples,'bus_fin_support_samples':bridge_samples,'rear_vertices_preserved':len(record['rear_shell_vertices']),'tier_lamps':len(lamps),'receiver_backing_samples':rim_samples,'receiver_face_relief_m':.006,'minimum_cover_clearance_m':min(cover_gaps)})
    report={'passed':not failures,'failures':failures,'protected_objects_unchanged':len(source['protected_objects']),'variants':rows,'live_game_checked':False}
    (ROOT/'validation/controller-detail-loop-01/geometry.json').write_text(json.dumps(report,indent=2)+'\n')
    if failures:raise AssertionError('\n'.join(failures))
    return report


if __name__=='__main__':result=main()
