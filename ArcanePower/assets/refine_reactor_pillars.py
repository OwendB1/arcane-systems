"""Finish pillar seats and all exposed faces. PILLAR_INDICES limits a live batch."""
import bpy,bmesh,importlib,json,math
from pathlib import Path
from mathutils import Matrix,Vector

ROOT=Path(__file__).resolve().parents[1]
PREFIX='Reactor exterior / '


def main(indices):
    scene=bpy.data.scenes['ArcanePower_ReactorPrototype'];bpy.context.window.scene=scene;bpy.context.view_layer.update()
    col=importlib.import_module('space-engineers-utilities.seut_collections').get_collections(scene)['main'][0]
    root=next(o for o in col.objects if o.parent is None);native={m.name:m for m in bpy.data.materials if m.library}

    def mesh_object(label,vertices,faces,material,frame=Matrix.Identity(4)):
        mesh=bpy.data.meshes.new(label);mesh.from_pydata(vertices,[],faces);mesh.update()
        bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
        mesh.materials.append(native[material]);uv=mesh.uv_layers.new(name='UVMap')
        for face in mesh.polygons:
            axes=[i for i in range(3) if i!=max(range(3),key=lambda a:abs(face.normal[a]))]
            for index in face.loop_indices:
                p=mesh.vertices[mesh.loops[index].vertex_index].co;uv.data[index].uv=(p[axes[0]]*.4,p[axes[1]]*.4)
        obj=bpy.data.objects.new(PREFIX+label,mesh);col.objects.link(obj);obj.parent=root;obj.matrix_basis=frame
        return obj

    def outline(w,h,c):return [(-w+c,-h),(w-c,-h),(w,-h+c),(w,h-c),(w-c,h),(-w+c,h),(-w,h-c),(-w,-h+c)]

    def box(label,frame,position,size,material='PaintedMetal_Darker',corner=.008):
        w,h,d=size;loop=outline(w/2,h/2,min(corner,w/4,h/4));verts=[(x,y,z) for z in (-d/2,d/2) for x,y in loop]
        faces=[tuple(reversed(range(8))),tuple(range(8,16))]+[(i,(i+1)%8,(i+1)%8+8,i+8) for i in range(8)]
        return mesh_object(label,verts,faces,material,frame @ Matrix.Translation(position))

    def cut(cutter,target):
        if target.data.users>1:target.data=target.data.copy()
        mod=target.modifiers.new('Machined inspection recess','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter
        bpy.context.view_layer.objects.active=target;bpy.context.view_layer.update();bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(cutter,do_unlink=True)

    # The original lamp, backing and jacket all ended at R6.10 after the
    # outboard translation. Machine a real pocket rather than overlaying them.
    if scene.get('pillar_status_revision')!=1:
        checkpoint=ROOT/'assets/arcane-power-before-status-insets.blend'
        if not checkpoint.exists():bpy.ops.wm.save_as_mainfile(filepath=str(checkpoint),copy=True)
        for i in range(4):
            angle=-math.pi/4+i*math.pi/2;n=Vector((math.cos(angle),math.sin(angle),0));t=Vector((-n.y,n.x,0));up=Vector((0,0,1))
            def nearest(prefix):
                return min((o for o in col.objects if o.name.startswith(prefix)),key=lambda o:((sum((o.matrix_world @ v.co for v in o.data.vertices),Vector())/len(o.data.vertices))-n*6.08-up*1.031).length_squared)
            body=nearest(PREFIX+'chamfered pillar jacket')
            backing=nearest(PREFIX+'pillar status backing')
            emitter=nearest('Spine status emitter')
            frame=Matrix((t,up,n)).transposed().to_4x4();frame.translation=n*6.10+up*1.031
            cut(box('temporary status aperture',frame,(0,0,.0025),(.200,1.150,.135),'PaintedMetal_VeryDark',.010),body)
            # Backing overlaps the pocket floor by 4 mm. The luminous face is
            # 13 mm above the backing, still 6 mm behind the jacket face.
            for obj,front in ((backing,6.081),(emitter,6.094)):
                current=max((obj.matrix_world @ v.co).dot(n) for v in obj.data.vertices)
                obj.matrix_world=Matrix.Translation(n*(front-current)) @ obj.matrix_world
            backing['status_jacket']=body.name
            emitter['status_backing']=backing.name
        scene['pillar_status_revision']=1
        bpy.context.view_layer.update()
        bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/arcane-power-prototype.blend'))
        bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/arcane-power-exterior-work-in-progress.blend'),copy=True)

    def subdivided(loop):
        return [(a[0]+(b[0]-a[0])*j/count,a[1]+(b[1]-a[1])*j/count)
                for i,(a,b) in enumerate(zip(loop,loop[1:]+loop[:1])) for count in [8 if i in (0,4) else 1] for j in range(count)]

    def seat(angle,label,planes,material='PaintedMetal_Colorable'):
        n=Vector((math.cos(angle),math.sin(angle),0));t=Vector((-n.y,n.x,0));verts=[]
        for z,w,inner,outer,curved in planes:
            loop=subdivided(outline(w/2,(outer-inner)/2,.050))
            for x,y in loop:
                r=(inner+outer)/2+y;depth=math.sqrt(r*r-x*x) if curved else r
                verts.append(tuple(t*x+n*depth+Vector((0,0,z))))
        count=len(verts)//len(planes);faces=[tuple(reversed(range(count))),tuple(range((len(planes)-1)*count,len(verts)))]
        faces.extend((k*count+i,k*count+(i+1)%count,(k+1)*count+(i+1)%count,(k+1)*count+i) for k in range(len(planes)-1) for i in range(count))
        return mesh_object(label,verts,faces,material)

    if scene.get('pillar_support_revision')!=1:
        if not (ROOT/'assets/arcane-power-before-pillar-joints.blend').exists():bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/arcane-power-before-pillar-joints.blend'),copy=True)
        replaced={}
        for obj in list(col.objects):
            if obj.name.startswith(('Integrated support / curved pillar saddle','Upper radial bracket',PREFIX+'outboard pillar foot',PREFIX+'pillar roof bridge',PREFIX+'fitted curved pillar foot',PREFIX+'fitted pillar roof seat')):
                replaced[obj.name]=True;bpy.data.objects.remove(obj,do_unlink=True)
        path=ROOT/'validation/reactor-exterior-loop-01/source.json'
        if path.exists():
            report=json.loads(path.read_text());protected=report['protected_objects']
            report.setdefault('replaced_original_pillar_supports',{}).update({name:protected.pop(name) for name in list(protected) if name in replaced})
            path.write_text(json.dumps(report,indent=2)+'\n')

        for i in range(4):
            angle=-math.pi/4+i*math.pi/2
            seat(angle,'fitted curved pillar foot',[(-1.42,1.78,5.03,6.215,True),(-1.30,1.78,5.03,6.215,True),(-1.02,1.62,5.10,6.10,False)])
            seat(angle,'fitted pillar roof seat',[(2.60,1.62,5.10,6.10,False),(2.84,1.78,4.94,6.16,True),(2.94,1.78,4.94,6.16,True)])
        scene['pillar_support_revision']=1
        bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/arcane-power-prototype.blend'))

    if scene.get('pillar_foot_revision')!=3:
        checkpoint=ROOT/'assets/arcane-power-before-stepped-feet.blend'
        if not checkpoint.exists():bpy.ops.wm.save_as_mainfile(filepath=str(checkpoint),copy=True)
        for obj in list(col.objects):
            if obj.name.startswith(PREFIX+'fitted curved pillar foot'):bpy.data.objects.remove(obj,do_unlink=True)
        for i in range(4):
            angle=-math.pi/4+i*math.pi/2
            # A shallow curved flange follows the drum. Its narrow neck seats
            # the jacket without the former broad sloping front apron.
            # R6.155 also fits inside the collar between its polygon corners.
            seat(angle,'fitted curved pillar foot',[(-1.415,1.76,5.04,6.155,True),(-1.285,1.76,5.04,6.155,True),(-1.235,1.64,5.09,6.105,False),(-1.045,1.64,5.09,6.105,False)])
        scene['pillar_foot_revision']=3
        bpy.context.view_layer.update()
        bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/arcane-power-prototype.blend'))
        bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/arcane-power-exterior-work-in-progress.blend'),copy=True)

    active=[i for i in indices if scene.get('pillar_surface_revision_'+str(i))!=1]
    if not active:return {'already_applied':True}
    with bpy.data.libraries.load(str(Path.home()/'.local/share/blender-se1-setup/assets/Models/Decals/Atlas3.blend'),link=False) as (source,target):target.objects=['Large Screw']
    template=target.objects[0].data.copy();bpy.data.objects.remove(target.objects[0],do_unlink=True)

    def bolt(frame,x,y,support):
        verts=[(.012*math.cos(i*math.tau/8),.012*math.sin(i*math.tau/8),z) for z in (-.004,.004) for i in range(8)]
        faces=[tuple(reversed(range(8))),tuple(range(8,16))]+[(i,(i+1)%8,(i+1)%8+8,i+8) for i in range(8)]
        body=mesh_object('pillar cover screw',verts,faces,'Metal_Shiny',frame @ Matrix.Translation((x,y,-.006)))
        body['support']=support.name
        mesh=template.copy();ps=[v.co for v in mesh.vertices];lo=Vector([min(p[i] for p in ps) for i in range(3)]);hi=Vector([max(p[i] for p in ps) for i in range(3)]);scale=.021/(hi.x-lo.x)
        mesh.transform(frame @ Matrix.Translation((x,y,-.0015)) @ Matrix.Scale(scale,4) @ Matrix.Translation((-(lo.x+hi.x)/2,-(lo.y+hi.y)/2,-lo.z)))
        for j,m in enumerate(mesh.materials):mesh.materials[j]=native.get(m.name.split('.')[0],m)
        face=bpy.data.objects.new(PREFIX+'native pillar screw face',mesh);col.objects.link(face);face.parent=root;face['source_asset']='SEUT Atlas3 Large Screw';face['fastener_body']=body.name

    def pocket(frame,w,h,body):
        loops=[(0,outline(w/2,h/2,.015)),(0,outline(w/2-.04,h/2-.04,.010)),(-.025,outline(w/2-.04,h/2-.04,.010)),(-.025,outline(w/2-.065,h/2-.065,.008)),(-.080,outline(w/2-.065,h/2-.065,.008)),(-.080,outline(w/2,h/2,.015))]
        verts=[(x,y,z) for z,loop in loops for x,y in loop];faces=[(k*8+i,k*8+(i+1)%8,((k+1)%6)*8+(i+1)%8,((k+1)%6)*8+i) for k in range(6) for i in range(8)]
        rim=mesh_object('pillar inspection receiver',verts,faces,'PaintedMetal_Colorable',frame)
        box('pillar inspection floor',frame,(0,0,-.0725),(w-.04,h-.04,.025),'PaintedMetal_VeryDark')
        cut(box('temporary pillar aperture',frame,(0,0,-.025),(w-.08,h-.08,.13)),body)
        return rim

    def cover(frame,w,h,side=False):
        panel=box('pillar side cover' if side else 'pillar inner cover',frame,(0,0,-.017),(w,h,.026),'PaintedMetal_Darker',.010)
        for x in (-w/2+.052,w/2-.052):
            for y in (-h/2+.065,h/2-.065):bolt(frame,x,y,panel)
        if side:
            cut(box('temporary cover keyway',frame,(0,0,-.005),(.15,.040,.020),'Metal_Dull',.006),panel)
        return panel

    for i in active:
        angle=-math.pi/4+i*math.pi/2;n=Vector((math.cos(angle),math.sin(angle),0));t=Vector((-n.y,n.x,0));up=Vector((0,0,1))
        bodies=[o for o in col.objects if o.name.startswith(PREFIX+'chamfered pillar jacket')]
        body=min(bodies,key=lambda o:(o.matrix_world.translation-(n*5.60+up*.80)).length_squared)
        for sign in (-1,1):
            normal=t*sign;horizontal=-n*sign
            frame=Matrix((horizontal,up,normal)).transposed().to_4x4();frame.translation=n*5.40+t*(sign*.802)+up*.80
            pocket(frame,.46,3.00,body)
            box('side cover cross seat',frame,(0,0,-.050),(.40,.060,.050),'Metal_Dull')
            for h in (-.731,.731):cover(frame @ Matrix.Translation((0,h,0)),.366,1.436,True)
        frame=Matrix((-t,up,-n)).transposed().to_4x4();frame.translation=n*5.098+up*.80
        rim=pocket(frame,1.10,2.95,body)
        for h in (-.99,.99):cover(frame @ Matrix.Translation((0,h,0)),1.006,.860)
        for h in (-.545,.545):box('inner cover cross seat',frame,(0,h,-.050),(1.04,.060,.050),'Metal_Dull')
        for j in range(5):
            vane=box('inner pillar cooling vane',frame,(0,-.40+j*.20,-.045),(1.00,.100,.060),'Metal_Dull',.004)
            vane.matrix_basis=frame @ Matrix.Translation((0,-.40+j*.20,-.045)) @ Matrix.Rotation(math.radians(18),4,'X');vane['support']=rim.name
        scene['pillar_surface_revision_'+str(i)]=1
        bpy.context.view_layer.update()
        bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/arcane-power-prototype.blend'))
        bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/arcane-power-exterior-work-in-progress.blend'),copy=True)
    return {'finished_pillars':active,'support_revision':1,'saved':bpy.data.filepath}


if __name__=='__main__':result=main(globals().get('PILLAR_INDICES',range(4)))
