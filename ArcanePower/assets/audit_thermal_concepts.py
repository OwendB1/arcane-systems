"""Focused checks for the editable Brayton component concepts, in Blender."""
import hashlib
import json
import math
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'validation/thermal-concepts'


def audit():
    previous=bpy.context.scene
    failures=[];models={};trees={}
    def fail(model,kind,obj):failures.append({'model':model,'check':kind,'object':obj})
    def tree(obj):
        if obj.name not in trees:
            obj.data.calc_loop_triangles()
            trees[obj.name]=BVHTree.FromPolygons([obj.matrix_world@v.co for v in obj.data.vertices],[list(t.vertices) for t in obj.data.loop_triangles],all_triangles=True)
        return trees[obj.name]
    for col in bpy.data.collections:
        name=col.get('thermal_concept')
        if not name:continue
        bpy.context.window.scene=bpy.data.scenes['Thermal / '+name];bpy.context.view_layer.update()
        size=Vector(col['grid_cells'])*2.5;count=0;studs=0;decals=0;marks=0
        for obj in col.objects:
            if obj.type=='MESH':
                count+=1;ps=[obj.matrix_world@v.co for v in obj.data.vertices]
                if any(not math.isfinite(q) for p in ps for q in p):fail(name,'finite vertices',obj.name)
                if any(abs(p[i])>size[i]/2+.005 for p in ps for i in range(3)):fail(name,'envelope',obj.name)
                layer=obj.data.uv_layers.active
                if not layer or any(not math.isfinite(q) for x in layer.data for q in x.uv):fail(name,'finite UV coverage',obj.name)
                if not obj.data.materials or any(m is None or not m.library for m in obj.data.materials):fail(name,'native material',obj.name)
                if not obj.get('thermal_decal_support'):
                    bm=bmesh.new();bm.from_mesh(obj.data)
                    if any(not e.is_manifold for e in bm.edges) or bm.calc_volume(signed=True)<=1e-10:fail(name,'closed positive volume',obj.name)
                    bm.free()
            support_key=next((k for k in ('thermal_support','thermal_decal_support','thermal_marking_support') if obj.get(k)),None)
            if support_key:
                support=bpy.data.objects.get(obj[support_key])
                if not support:fail(name,'missing backing',obj.name);continue
                bvh=tree(support)
                if support_key=='thermal_support':
                    studs+=1;point=Vector(obj['support_point']);axis=Vector(obj['support_axis'])
                    # Check the entire bolt footprint, not only its center.
                    points=[p-axis*(p-point).dot(axis) for p in (obj.matrix_world@v.co for v in obj.data.vertices)]
                    tolerance=.012
                elif support_key=='thermal_decal_support':
                    decals+=1;points=[obj.matrix_world@v.co for v in obj.data.vertices];tolerance=.006
                else:
                    marks+=1;ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
                    points=[obj.matrix_world@v.co for v in mesh.vertices];ev.to_mesh_clear();tolerance=.006
                if any(bvh.find_nearest(point)[0] is None or bvh.find_nearest(point)[3]>tolerance for point in points):fail(name,'full supported footprint',obj.name)
        ports=json.loads(col['ports'])
        for port in ports:
            pos,n,up=map(Vector,(port['position'],port['normal'],port['hot_axis']))
            axis=max(range(3),key=lambda i:abs(n[i]))
            if abs(abs(pos[axis])-size[axis]/2)>.001:fail(name,'port face plane',port['id'])
            if n.dot(pos)<=0 or abs(n.length-1)>.001 or abs(n.dot(up))>.001:fail(name,'port orientation',port['id'])
            for i in range(3):
                if i==axis:continue
                index=(pos[i]+size[i]/2-1.25)/2.5
                if abs(index-round(index))>.001:fail(name,'port cell center',port['id'])
            u=up.cross(n).normalized()
            # Check the first 0.15 m through the flange/lip, before pipe bends.
            meshes=[o for o in col.objects if o.type=='MESH' and not o.get('thermal_decal_support')]
            for sign in (-1,1):
                centre=pos+up*(sign*.46)
                samples=[centre]+[centre+.20*(u*math.cos(i*math.tau/8)+up*math.sin(i*math.tau/8)) for i in range(8)]
                if any(tree(o).ray_cast(point+n*.10,-n,.25)[0] is not None for point in samples for o in meshes):
                    fail(name,'open port neck',port['id']+' '+str(sign))
        models[name]={'meshes':count,'ports':len(ports),'backed_fasteners':studs,'backed_native_decals':decals,'backed_markings':marks}
        if name.startswith('Recuperator'):
            bypasses=[o for o in col.objects if 'insulated non-working bypass' in o.name]
            neighbors=[o for o in col.objects if o.type=='MESH' and any(key in o.name for key in ('frame post','plate bank','counterflow plate','working leg manifold'))]
            for pipe in bypasses:
                for neighbor in neighbors:
                    if tree(pipe).overlap(tree(neighbor)):fail(name,'bypass clearance',pipe.name+' / '+neighbor.name)
            if tree(bypasses[0]).overlap(tree(bypasses[1])):fail(name,'bypass separation','HP / LP')
    # Full-circle blade envelope is independent of angular sampling.
    fans=[]
    col=bpy.data.collections['Thermal model / Atmospheric cooler']
    for pivot in (o for o in col.objects if o.get('runtime_axis')):
        bpy.context.window.scene=bpy.data.scenes['Thermal / Atmospheric cooler'];bpy.context.view_layer.update()
        ps=[o.matrix_world@v.co for o in col.objects if o.get('fan_pivot')==pivot.name for v in o.data.vertices]
        centre=pivot.matrix_world.translation
        radial=max(math.hypot(p.x-centre.x,p.z-centre.z) for p in ps)
        clearance=1.41-radial;grille=min(p.y for p in ps)-(-2.31)
        if clearance<.04 or grille<.10:fail('Atmospheric cooler','rotating clearance',pivot.name)
        fans.append({'pivot':pivot.name,'shroud_clearance_m':clearance,'grille_clearance_m':grille,'blades':sum(o.get('fan_pivot')==pivot.name for o in col.objects)})
    protected=json.loads((OUT/'protected-production.json').read_text())
    hashes={name:hashlib.sha256((ROOT/'assets'/name).read_bytes()).hexdigest() for name in protected}
    if protected!=hashes:fail('Production','source hash changed','production .blend files')
    layouts={}
    for scene in (s for s in bpy.data.scenes if s.get('environment') in ('atmosphere','space')):
        bpy.context.window.scene=scene;bpy.context.view_layer.update()
        live_ports={};instances=[o for o in scene.objects if o.instance_type=='COLLECTION']
        for obj in instances:
            col=obj.instance_collection
            if not col:fail(scene.name,'missing component instance',obj.name);continue
            name=col.get('thermal_concept')
            if not name:continue
            for port in json.loads(col['ports']):
                live_ports[(name,port['id'])]=dict(port,position=list(obj.matrix_world@Vector(port['position'])))
        live_ports[('Reactor','extraction')]={'position':[-13.75,-15,3.75],'type':'PRIMARY','normal':[1,0,0]}
        edges=json.loads(scene['thermal_connections']);used=set()
        for edge in edges:
            a,b=tuple(edge['from']),tuple(edge['to'])
            for key in (a,b):
                if key in used:fail(scene.name,'duplicate connection',str(key))
                used.add(key)
            if a not in live_ports or b not in live_ports:fail(scene.name,'unresolved connection',str(edge));continue
            left,right=live_ports[a],live_ports[b]
            if not (left['type']==edge['type']==right['type']):fail(scene.name,'port type mismatch',str(edge))
            paths=edge.get('channel_paths',[edge.get('path')])
            for path in paths:
                offset=Vector((0,0,path[0][2]-left['position'][2])) if edge.get('channel_paths') else Vector()
                if edge.get('channel_paths') and abs(abs(offset.z)-.46)>.001:fail(scene.name,'channel separation',str(a))
                start,end=Vector(path[0]),Vector(path[-1])
                if (start-Vector(left['position'])-offset).length>.001 or (end-Vector(right['position'])-offset).length>.001:
                    fail(scene.name,'route endpoint',str(edge['from']))
                if (Vector(path[1])-start).normalized().dot(Vector(left['normal']))<.999 or (Vector(path[-2])-end).normalized().dot(Vector(right['normal']))<.999:
                    fail(scene.name,'route approach',str(edge['from']))
        capped=set()
        if set(live_ports)!=used|capped:fail(scene.name,'unconnected port',str(set(live_ports)-used-capped))
        layouts[scene.name]={'component_instances':len(instances),'typed_connections':len(edges),'isolated_ports':len(capped)}
    expected={'Brayton train','Primary heater','Recuperator','Atmospheric cooler','Space radiator','Brayton train upgraded','Primary heater upgraded','Recuperator upgraded','Duplex straight','Duplex elbow','Duplex tee'}
    if set(models)!=expected:fail('Concepts','component set',str(set(models)^expected))
    bank=bpy.data.scenes.get('Thermal / Parallel train bank')
    if not bank:fail('Bank','missing model study','Parallel train bank')
    else:
        bpy.context.window.scene=bank;bpy.context.view_layer.update()
        trains=[o for o in bank.objects if o.instance_type=='COLLECTION']
        branches=json.loads(bank['train_bank_branches'])
        poses=[o.matrix_world@Vector(r['position']) for o in trains for r in json.loads(o.instance_collection['ports'])]
        if len(trains)!=3 or len(branches)!=6:fail('Bank','duty/standby assembly','expected three trains and six branches')
        for branch in branches:
            if not any((Vector(branch['port'])-p).length<.001 for p in poses):fail('Bank','branch endpoint',str(branch))
        for o in bank.objects:
            if o.type=='MESH' and 'shared header' in o.name:
                bm=bmesh.new();bm.from_mesh(o.data)
                if any(not e.is_manifold for e in bm.edges) or bm.calc_volume(signed=True)<=0:fail('Bank','hollow header solidity',o.name)
                bm.free()
    if len(layouts)!=4:fail('Layouts','environment/grade coverage',str(list(layouts)))
    if any('MHD' in o.name for o in bpy.data.objects):fail('Concepts','obsolete converter','unexpected object')
    bpy.context.window.scene=previous
    report={'status':'passed' if not failures else 'failed','models':models,'fans':fans,'layouts':layouts,'production_unchanged':protected==hashes,'failures':failures,
            'limits':'Component geometry, backing, UVs, port poses and fan envelopes only. Plant routing is schematic; no collision, runtime or MWM validation.'}
    (OUT/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':result=audit()
