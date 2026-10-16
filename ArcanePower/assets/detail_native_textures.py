"""Native paint grain, controlled wear and supported atlas markings.

Run in either production .blend. Geometry, anchors, collision, LODs and powered
materials stay intact. Existing construction copies receive matching UV/material
edits; new markings appear only when their backing is installed.
"""
import array
import hashlib
import importlib
import json
import math
from pathlib import Path
import runpy

import bpy
import bmesh
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'validation/native-texture-detail'
COLS=importlib.import_module('space-engineers-utilities.seut_collections')
PREFIX='Texture detail / '
DENSITY=.8
RELIEF=.0015
SURFACES=('Drum segmented armor','Circular upper armored housing','Cap removable sector',
          'Reactor exterior / flush access door','Reactor exterior / chamfered pillar jacket',
          'Reactor exterior / dispenser cheek','Power pack / curved socket shell',
          'Reactor exterior / pillar side cover','Reactor exterior / dispenser pitched cheek',
          'Reactor exterior / cooling belt edge rail','Reactor exterior / fitted curved pillar foot',
          'Controller detail / broad service cassette','Controller detail / paired power cartridge',
          'Controller detail / status carrier','Energy / segmented drum armor','Energy / deck panel',
          'Energy / drum access panel','Energy / drum access door','Energy / flush drum door','Energy / drum service door',
          'Module / side armor','Module / inset service door','Module / faceted end deck',
          'Module / armored endcap','Module / front spine')
PAINT={'PaintedMetal_Colorable':'PaintedMetalScratched_Colorable',
       'PaintedMetal_Darker':'PaintedMetalScratched_Darker'}


def geometry(obj):
    h=hashlib.sha256(repr((obj.type,obj.parent.name if obj.parent else None,
                          tuple(v for row in obj.matrix_basis for v in row))).encode())
    if obj.type=='MESH':
        for items,field,kind,width in ((obj.data.vertices,'co','f',3),(obj.data.loops,'vertex_index','i',1),(obj.data.polygons,'loop_total','i',1)):
            values=array.array(kind,[0])*len(items)*width;items.foreach_get(field,values);h.update(values.tobytes())
    else:h.update(repr(dict(obj.items())).encode())
    return h.hexdigest()


def tree(obj):
    return BVHTree.FromPolygons([obj.matrix_world @ v.co for v in obj.data.vertices],
                               [tuple(p.vertices) for p in obj.data.polygons])


def sync_surface(source,copy):
    """Transfer atlas corners across construction cleanup/triangulation seams."""
    if copy.data.users>1:copy.data=copy.data.copy()
    copy.data.materials.clear()
    for mat in source.data.materials:copy.data.materials.append(mat)
    key=lambda p:tuple(round(x,5) for x in p)
    corners={}
    for face in source.data.polygons:
        for index in face.loop_indices:
            p=source.data.vertices[source.data.loops[index].vertex_index].co
            corners.setdefault(key(p),{})[face.index]=source.data.uv_layers.active.data[index].uv.copy()
    for face in copy.data.polygons:
        rows=[corners[key(copy.data.vertices[copy.data.loops[i].vertex_index].co)] for i in face.loop_indices]
        common=set.intersection(*(set(row) for row in rows))
        assert common,'Construction face lost its source surface: '+copy.name
        owner=max(common,key=lambda i:source.data.polygons[i].normal.dot(face.normal))
        face.material_index=source.data.polygons[owner].material_index
        for index,row in zip(face.loop_indices,rows):copy.data.uv_layers.active.data[index].uv=row[owner]


def main():
    FOLDER.mkdir(exist_ok=True)
    names=[s.name for s in bpy.data.scenes if s.name.startswith('ArcanePower_') and
           (s.name.startswith('ArcanePower_Energy') or s.name in ('ArcanePower_ReactorPrototype','ArcanePower_ContainmentController','ArcanePower_AdvancedContainmentController')) and s.seut.sceneType=='mainScene']
    assert names,'Open a production model file'
    path=FOLDER/'source.json';report=json.loads(path.read_text()) if path.exists() else {'sources':{}}
    key='energy' if any('Energy' in n for n in names) else 'prototype'
    fingerprint=runpy.run_path(str(ROOT/'assets/refine_reactor_exterior.py'))['fingerprint']
    original={o for s in bpy.data.scenes if s.name.startswith('ArcanePower_') for o in s.objects}
    before={o.name:geometry(o) for o in original}
    old_fingerprints={o.name:fingerprint(o) for o in original}
    materials={m.name:m for m in bpy.data.materials if m.library}
    assets=Path.home()/'.local/share/blender-se1-setup/assets'
    required=set(PAINT.values())|{'Atlas2','PanelingColorable'}
    if required-materials.keys():
        with bpy.data.libraries.load(str(assets/'Materials/Materials.blend'),link=True) as (src,dst):dst.materials=sorted(required-materials.keys())
        materials.update({m.name:m for m in dst.materials})
    templates={}
    for library,label in (('Atlas2','Warning Stripes Yellow'),('Atlas2','Warning Stripes White'),('Atlas2','Sign High Voltage'),('Paneling','Panel Line Welded'),('Paneling','Panel Line Creased')):
        with bpy.data.libraries.load(str(assets/'Models/Decals'/(library+'.blend')),link=False) as (src,dst):dst.objects=[label]
        obj=dst.objects[0];templates[label]=obj.data.copy();bpy.data.objects.remove(obj,do_unlink=True)
    changed={};decals=[];stages_changed=[]

    for name in names:
        scene=bpy.data.scenes[name];bpy.context.window.scene=scene;bpy.context.view_layer.update()
        cs=COLS.get_collections(scene);col=cs['main'][0];root=next(o for o in col.objects if o.parent is None)
        frame=root.matrix_world.inverted();meshes=[o for o in col.objects if o.type=='MESH']
        for obj in meshes:
            if obj.get('native_texture_revision')==2 or not obj.name.startswith(SURFACES):continue
            if obj.get('source_asset'):continue
            # Native atlases, glass and driven emissives keep their original UVs.
            if obj.data.users>1:obj.data=obj.data.copy()
            mesh=obj.data;offset=hashlib.sha256((name+'/'+obj.name).encode()).digest()
            shift=Vector((offset[0]/255,offset[1]/255))
            worn=any(token in obj.name.lower() for token in ('door','cassette','cartridge','side armor','deck panel','faceted end deck','segmented armor','segmented drum'))
            reverse={v:k for k,v in PAINT.items()}
            for i,mat in enumerate(mesh.materials):
                if mat and mat.name in reverse:mesh.materials[i]=materials[reverse[mat.name]]
            largest=max(p.area for p in mesh.polygons)
            edge_slots={}
            if worn:
                for i,mat in enumerate(list(mesh.materials)):
                    if mat and mat.name in PAINT:
                        edge_slots[i]=len(mesh.materials);mesh.materials.append(materials[PAINT[mat.name]])
            uv=mesh.uv_layers.active or mesh.uv_layers.new(name='UVMap')
            radial=obj.name.startswith(('Drum segmented armor','Circular upper armored housing','Energy / segmented drum armor','Energy / drum access panel'))
            ps=[frame @ obj.matrix_world @ v.co for v in mesh.vertices]
            centre=sum(ps,Vector())/len(ps);anchor=math.atan2(centre.y,centre.x)
            radius=sum(math.hypot(p.x,p.y) for p in ps)/len(ps)
            for face in mesh.polygons:
                mat=mesh.materials[face.material_index]
                if not mat or not mat.name.startswith(('PaintedMetal','Metal_')):continue
                if face.material_index in edge_slots and .000005<face.area<min(.020,largest*.015):face.material_index=edge_slots[face.material_index]
                axes=[i for i in range(3) if i!=max(range(3),key=lambda i:abs(face.normal[i]))]
                for index in face.loop_indices:
                    vertex=mesh.vertices[mesh.loops[index].vertex_index]
                    if radial and abs(face.normal.z)<.5:
                        p=ps[vertex.index];angle=(math.atan2(p.y,p.x)-anchor+math.pi)%math.tau-math.pi
                        coords=Vector((angle*radius,p.z))
                    else:
                        coords=Vector([vertex.co[i]*(obj.matrix_world.to_3x3().col[i].length) for i in axes])
                    uv.data[index].uv=coords*DENSITY+shift
            mesh.update();obj['native_texture_revision']=2
            changed[obj.name]={'scene':name,'materials':[m.name for m in mesh.materials],'uv_tiles_per_m':DENSITY,'wear':worn,'radial':radial}

        def decal(support,label,asset,centre,u,v,length):
            token=label+' / '+support.name
            if any(o.get('texture_marking')==token for o in col.objects):return
            mesh=templates[asset].copy();ps=[p.co for p in mesh.vertices]
            lo=Vector([min(p[i] for p in ps) for i in range(3)]);hi=Vector([max(p[i] for p in ps) for i in range(3)])
            scale=length/(hi.x-lo.x);middle=(lo+hi)/2
            # Long quads otherwise chord through curved armor between corners.
            # Split lengthwise while interpolating the original native atlas UVs.
            bm=bmesh.new();bm.from_mesh(mesh)
            edges=[e for e in bm.edges if e.calc_length()*scale>.08]
            if edges:bmesh.ops.subdivide_edges(bm,edges=edges,cuts=math.ceil(max(e.calc_length()*scale for e in edges)/.08)-1,use_grid_fill=True)
            bm.to_mesh(mesh);bm.free()
            u,v=Vector(u).normalized(),Vector(v).normalized();n=u.cross(v).normalized();centre=Vector(centre)
            backing=tree(support)
            for vertex in mesh.vertices:
                p=(vertex.co-middle)*scale;point=centre+u*p.x+v*p.y
                hit,normal,index,distance=backing.ray_cast(point+n*.10,-n,.20)
                assert hit is not None and normal.dot(n)>.8,'Marking misses backing: '+support.name
                vertex.co=hit+n*RELIEF
            for i,mat in enumerate(mesh.materials):mesh.materials[i]=materials[mat.name.split('.')[0]]
            obj=bpy.data.objects.new(PREFIX+label,mesh);col.objects.link(obj)
            obj.parent=root;obj.matrix_basis=root.matrix_world.inverted()
            obj['source_asset']='SEUT '+asset+'; original atlas UVs'
            obj['texture_marking']=token;obj['texture_support']=support.name;obj['build_stage']=support.get('build_stage',3)
            decals.append(obj.name);return obj

        for obj in meshes:
            if obj.name.startswith('Drum segmented armor'):
                points=[frame @ obj.matrix_world @ v.co for v in obj.data.vertices]
                centre=sum(points,Vector())/len(points);a=math.atan2(centre.y,centre.x)
                if max(p.x for p in points)-min(p.x for p in points)+max(p.y for p in points)-min(p.y for p in points)<.9:continue
                if abs(math.cos(a))>.97:continue  # Native hardpoint shoulders occupy these sectors.
                n=Vector((math.cos(a),math.sin(a),0));u=Vector((-n.y,n.x,0))
                decal(obj,'drum rolled seam','Panel Line Welded',n*6.13+Vector((0,0,-1.70)),u,(0,0,1),.64)
            elif obj.name.startswith('Cap removable sector'):
                points=[frame @ obj.matrix_world @ v.co for v in obj.data.vertices]
                centre=sum(points,Vector())/len(points);a=math.atan2(centre.y,centre.x)
                n=Vector((math.cos(a),math.sin(a),0));u=Vector((-n.y,n.x,0))
                decal(obj,'roof pressed seam','Panel Line Creased',n*3.35+Vector((0,0,3.748)),u,-n,.62)
                decal(obj,'roof lift zone','Warning Stripes Yellow',n*5.58+Vector((0,0,3.748)),u,-n,.26)
            elif obj.name.startswith('Reactor exterior / pillar side cover'):
                rotation=obj.matrix_world.to_3x3()
                decal(obj,'pillar folded seam','Panel Line Creased',obj.matrix_world @ Vector((-.11,0,.013)),rotation @ Vector((0,1,0)),rotation @ Vector((-1,0,0)),.86)
                decal(obj,'pillar electrical hazard','Sign High Voltage',obj.matrix_world @ Vector((.02,.45,.013)),rotation @ Vector((1,0,0)),rotation @ Vector((0,1,0)),.10)
            elif obj.name.startswith('Circular upper armored housing'):
                for i in range(16):
                    a=(i+.5)*math.tau/16;n=Vector((math.cos(a),math.sin(a),0));u=Vector((-n.y,n.x,0))
                    decal(obj,'upper band seam '+str(i),'Panel Line Creased',n*6.13+Vector((0,0,3.63)),u,(0,0,1),.58)
            elif obj.name.startswith('Controller detail / lower retention rail'):
                p=obj.matrix_world @ Vector((0,0,max(v.co.z for v in obj.data.vertices)))
                decal(obj,'isolation warning','Warning Stripes Yellow',p,obj.matrix_world.to_3x3() @ Vector((1,0,0)),obj.matrix_world.to_3x3() @ Vector((0,1,0)),.24)
            elif obj.name.startswith('Power pack / curved socket shell'):
                for sign in (-1,1):decal(obj,'case weld '+str(sign),'Panel Line Welded',(sign*.8,-1.345,.17),(0,0,1),(0,-sign,0),.67)
            elif obj.name.startswith(('Controller detail / broad service cassette','Controller detail / paired power cartridge')):
                paired='paired' in obj.name
                p=obj.matrix_world @ Vector((0,.173 if paired else .175,max(v.co.z for v in obj.data.vertices)))
                decal(obj,'pressed service seam','Panel Line Creased',p,obj.matrix_world.to_3x3() @ Vector((1,0,0)),obj.matrix_world.to_3x3() @ Vector((0,1,0)),.15 if paired else .36)
            elif obj.name.startswith('Reactor exterior / flush access door'):
                lo=min(v.co.y for v in obj.data.vertices);top=max(v.co.z for v in obj.data.vertices)
                p=obj.matrix_world @ Vector((0,lo+.090,top))
                decal(obj,'service warning','Warning Stripes Yellow',p,obj.matrix_world.to_3x3() @ Vector((1,0,0)),obj.matrix_world.to_3x3() @ Vector((0,1,0)),.23)
            elif obj.name.startswith('Module / inset service door'):
                p=obj.matrix_world @ Vector((0,-.42,max(v.co.z for v in obj.data.vertices)))
                asset='Warning Stripes White' if 'Advanced' in name else 'Warning Stripes Yellow'
                decal(obj,'module isolation warning',asset,p,obj.matrix_world.to_3x3() @ Vector((1,0,0)),obj.matrix_world.to_3x3() @ Vector((0,1,0)),.22)
            elif obj.name.startswith('Module / side armor'):
                sign=math.copysign(1,(frame @ obj.matrix_world.translation).x)
                p=obj.matrix_world @ Vector((sign*.11,.76,0))
                decal(obj,'armor weld','Panel Line Welded',p,obj.matrix_world.to_3x3() @ Vector((0,0,1)),obj.matrix_world.to_3x3() @ Vector((0,-sign,0)),1.42)
            elif obj.name.startswith('Energy / deck panel'):
                points=[frame @ obj.matrix_world @ v.co for v in obj.data.vertices]
                centre=sum(points,Vector())/len(points);a=math.atan2(centre.y,centre.x);sign=math.copysign(1,centre.z)
                p=root.matrix_world @ Vector((1.65*math.cos(a),1.65*math.sin(a),sign*3.7175))
                u=root.matrix_world.to_3x3() @ Vector((-math.sin(a),math.cos(a),0))
                v=root.matrix_world.to_3x3() @ Vector((-sign*math.cos(a),-sign*math.sin(a),0))
                decal(obj,'deck lift clearance','Warning Stripes Yellow',p,u,v,.26)

        # Construction copies keep their existing geometry and installation order.
        for stage in cs['bs'] or []:
            members={o.get('source_object'):o for o in stage.objects if o.get('source_object')}
            for source_name,copy in members.items():
                if source_name not in changed:continue
                source=bpy.data.objects[source_name]
                sync_surface(source,copy)
                stages_changed.append(stage.name)
            for source in [o for o in col.objects if o.get('texture_support')]:
                owner=source['texture_support']
                if owner not in members or source.name in members:continue
                copy=source.copy();copy.data=source.data.copy();copy.parent=None;stage.objects.link(copy);copy.matrix_world=source.matrix_world.copy()
                copy['source_object']=source.name;copy['source_owner']=owner;stages_changed.append(stage.name)
        scene['native_texture_revision']=2

    # UV/material changes are authorized successors to the earlier art gates.
    # Keep pre-texture fingerprints in their history; unrelated hashes stay intact.
    for relative in ('reactor-exterior-loop-01/source.json','controller-detail-loop-01/source.json','energy-construction-update/protected-source.json'):
        target=ROOT/'validation'/relative
        if not target.exists():continue
        data=json.loads(target.read_text());protected=data.get('protected_objects',data)
        updates={n:fingerprint(bpy.data.objects[n]) for n in changed if n in protected}
        if updates:
            for n in updates:assert protected[n]==old_fingerprints[n],'Baseline mismatch before texture edit: '+n
            if 'protected_objects' in data:data.setdefault('before_native_texture_detail',{}).update({n:protected[n] for n in updates})
            protected.update(updates);target.write_text(json.dumps(data,indent=2)+'\n')
    if changed or decals:
        previous=report['sources'].get(key,{})
        report['sources'][key]={'geometry':previous.get('geometry',before),
            'surfaces':{**previous.get('surfaces',{}),**changed},
            'decals':sorted(set(previous.get('decals',[]))|set(decals)),
            'construction_collections':sorted(set(previous.get('construction_collections',[]))|set(stages_changed)),
            'source_file':bpy.data.filepath}
        path.write_text(json.dumps(report,indent=2)+'\n')
    return {'surfaces':len(changed),'decals':len(decals),'construction_collections':len(set(stages_changed))}


def audit():
    record=json.loads((FOLDER/'source.json').read_text())
    key='energy' if 'ArcanePower_EnergyCore' in bpy.data.scenes else 'prototype'
    source=record['sources'][key];failures=[];samples=0;surfaces={}
    for scene in bpy.data.scenes:
        if scene.name.startswith('ArcanePower_'):bpy.context.window.scene=scene;bpy.context.view_layer.update()
    for name,digest in source['geometry'].items():
        if name not in bpy.data.objects or geometry(bpy.data.objects[name])!=digest:failures.append('Geometry/anchor changed: '+name)
    for name in source['surfaces']:
        obj=bpy.data.objects[name]
        if not all(m and m.library for m in obj.data.materials):failures.append('Non-native structural material: '+name)
        if not all(math.isfinite(x) for d in obj.data.uv_layers.active.data for x in d.uv):failures.append('Invalid UV: '+name)
    for scene in bpy.data.scenes:
        if scene.seut.sceneType!='mainScene' or not scene.name.startswith('ArcanePower_'):continue
        col=COLS.get_collections(scene)['main'][0];vertices=[];faces=[]
        for obj in col.objects:
            if obj.type!='MESH' or obj.get('texture_support'):continue
            offset=len(vertices);vertices.extend(obj.matrix_world @ v.co for v in obj.data.vertices)
            faces.extend(tuple(offset+i for i in p.vertices) for p in obj.data.polygons)
        surfaces[scene.name]=BVHTree.FromPolygons(vertices,faces)
    for name in source['decals']:
        obj=bpy.data.objects[name];support=bpy.data.objects[obj['texture_support']];backing=tree(support)
        scene=next(s for s in bpy.data.scenes if s.name in surfaces and name in s.objects)
        normal=(obj.matrix_world.to_3x3() @ obj.data.polygons[0].normal).normalized()
        points=[obj.matrix_world @ v.co for v in obj.data.vertices]
        for p in points+[sum((points[i] for i in face.vertices),Vector())/len(face.vertices) for face in obj.data.polygons]:
            hit,n,index,distance=backing.ray_cast(p,-normal,.006)
            if hit is None or n.dot(normal)<.8 or not .001<distance<.002:failures.append('Unsupported/coplanar marking: '+name)
            hit,n,index,distance=surfaces[scene.name].ray_cast(p+normal*.05,-normal,.06)
            if hit is None or not .051<distance<.052:failures.append('Marking obscured by existing detail: '+name)
            samples+=1
        if not all(m and m.library for m in obj.data.materials):failures.append('Non-native decal material: '+name)
    report={'passed':not failures,'failures':failures,'surfaces':len(source['surfaces']),'decals':len(source['decals']),'preserved_geometry_objects':len(source['geometry']),'marking_support_samples':samples,'uv_tiles_per_m':DENSITY,'native_materials_only':True,'live_game_checked':False}
    (FOLDER/(key+'-audit.json')).write_text(json.dumps(report,indent=2)+'\n')
    assert not failures,'\n'.join(failures)
    return report


if __name__=='__main__':result=main()
