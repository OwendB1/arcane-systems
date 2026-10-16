"""Finished controller details; retain the curved socket and native anchors.

Run on the saved prototype or after build_external_hardware creates the shells.
The two variants share a case, with different service and power hardware.
"""
import bpy
import bmesh
import importlib
import json
import math
import runpy
from pathlib import Path
from mathutils import Matrix,Vector

ROOT=Path(__file__).resolve().parents[1]
NAMES=('ArcanePower_ContainmentController','ArcanePower_AdvancedContainmentController')
PREFIX='Controller detail / '
COLS=importlib.import_module('space-engineers-utilities.seut_collections')


def receiver_profile(w,h,shoulder=.040):
    def outline(x,y,c):return [(-x+c,-y),(x-c,-y),(x,-y+c),(x,y-c),(x-c,y),(-x+c,y),(-x,y-c),(-x,-y+c)]
    # Raised lip clears the casing; the lower shoulder leaves clearance around
    # both the main cassettes and the narrower side inspection covers.
    loops=[(.006,outline(w/2,h/2,.014)),(.006,outline(w/2-.025,h/2-.025,.010)),(-.018,outline(w/2-.025,h/2-.025,.010)),(-.018,outline(w/2-shoulder,h/2-shoulder,.008)),(-.065,outline(w/2-shoulder,h/2-shoulder,.008)),(-.065,outline(w/2,h/2,.014))]
    return [(x,y,z) for z,loop in loops for x,y in loop]


def fit_receiver_rims(scene,col):
    if scene.get('controller_receiver_revision')==2:return False
    rims=[o for o in col.objects if o.name.startswith(PREFIX+'stepped receiver')]
    assert rims,scene.name+': no receivers to repair'
    covers=[o for o in col.objects if o.name.startswith(tuple(PREFIX+x for x in ('broad service cassette','paired power cartridge','side inspection cover','status carrier')))]
    for panel in covers:
        if panel.name.startswith(PREFIX+'status carrier'):
            if panel.data.users>1:panel.data=panel.data.copy()
            scale=.093/(2*max(v.co.y for v in panel.data.vertices))
            for v in panel.data.vertices:v.co.y*=scale
            panel.data.update()
    for obj in rims:
        if obj.data.users>1:obj.data=obj.data.copy()
        w=2*max(v.co.x for v in obj.data.vertices);h=2*max(v.co.y for v in obj.data.vertices)
        assert len(obj.data.vertices)==48,obj.name+': unexpected receiver topology'
        cover=next((o for o in covers if (o.matrix_world.translation-obj.matrix_world.translation).length<.04),None)
        shoulder=(.026 if cover.name.startswith(PREFIX+'status carrier') else .028) if cover else .040
        for v,p in zip(obj.data.vertices,receiver_profile(w,h,shoulder)):v.co=p
        obj.data.update()
        for face in obj.data.polygons:
            axes=[i for i in range(3) if i!=max(range(3),key=lambda a:abs(face.normal[a]))]
            for index in face.loop_indices:
                p=obj.data.vertices[obj.data.loops[index].vertex_index].co
                obj.data.uv_layers.active.data[index].uv=(p[axes[0]]*.4,p[axes[1]]*.4)
    scene['controller_receiver_revision']=2
    return True


def main(names=NAMES):
    folder=ROOT/'validation/controller-detail-loop-01';folder.mkdir(exist_ok=True)
    fingerprint=runpy.run_path(str(ROOT/'assets/refine_reactor_exterior.py'))['fingerprint']
    path=folder/'source.json'
    report=json.loads(path.read_text()) if path.exists() else {'protected_objects':{},'variants':{}}
    native={m.name:m for m in bpy.data.materials if m.library}
    checkpoint=ROOT/'assets/arcane-power-before-controller-detail.blend'
    if not checkpoint.exists():bpy.ops.wm.save_as_mainfile(filepath=str(checkpoint),copy=True)
    changed=[]
    with bpy.data.libraries.load(str(Path.home()/'.local/share/blender-se1-setup/assets/Models/Decals/Atlas3.blend'),link=False) as (source,target):target.objects=['Large Screw']
    screw=target.objects[0].data.copy();bpy.data.objects.remove(target.objects[0],do_unlink=True)
    with bpy.data.libraries.load(str(Path.home()/'.local/share/blender-se1-setup/assets/Models/Decals/TextAtlas.blend'),link=False) as (source,target):target.objects=['1','2']
    glyphs={key:o.data.copy() for key,o in zip(('1','2'),target.objects)}
    for o in target.objects:bpy.data.objects.remove(o,do_unlink=True)

    for name in names:
        scene=bpy.data.scenes[name]
        scene.seut.paint_color=bpy.data.scenes['ArcanePower_ReactorPrototype'].seut.paint_color[:]
        if scene.get('controller_detail_revision')==1:
            bpy.context.window.scene=scene;bpy.context.view_layer.update()
            if fit_receiver_rims(scene,COLS.get_collections(scene)['main'][0]):changed.append(name)
            continue
        advanced='Advanced' in name;bpy.context.window.scene=scene;bpy.context.view_layer.update()
        col=COLS.get_collections(scene)['main'][0];root=next(o for o in col.objects if o.parent is None)
        shell=next(o for o in col.objects if o.name.startswith('Power pack / curved socket shell'))
        original_main={o.name:fingerprint(o) for o in col.objects if o.type=='MESH'}
        # Preserve unrelated reactor art, all controller detectors and derived
        # collections. Rear shell corners are also checked after every boolean.
        protected=set(bpy.data.scenes['ArcanePower_ReactorPrototype'].objects)
        for controller_name in NAMES:
            s=bpy.data.scenes[controller_name];main_col=COLS.get_collections(s)['main'][0]
            protected.update(o for o in main_col.objects if o.type!='MESH')
            protected.update(o for c in s.collection.children_recursive if c!=main_col for o in c.objects)
        for o in protected:report['protected_objects'].setdefault(o.name,fingerprint(o))
        rear=[list(v.co) for v in shell.data.vertices if v.co.y< -1.07]

        def mesh_object(label,vertices,faces,material,frame=Matrix.Identity(4)):
            mesh=bpy.data.meshes.new(label);mesh.from_pydata(vertices,[],faces)
            bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free();mesh.update()
            mesh.materials.append(native[material]);uv=mesh.uv_layers.new(name='UVMap')
            for face in mesh.polygons:
                axes=[i for i in range(3) if i!=max(range(3),key=lambda a:abs(face.normal[a]))]
                for index in face.loop_indices:
                    p=mesh.vertices[mesh.loops[index].vertex_index].co;uv.data[index].uv=(p[axes[0]]*.4,p[axes[1]]*.4)
            obj=bpy.data.objects.new(PREFIX+label,mesh);col.objects.link(obj);obj.parent=root;obj.matrix_basis=frame
            return obj

        def outline(w,h,c):return [(-w+c,-h),(w-c,-h),(w,-h+c),(w,h-c),(w-c,h),(-w+c,h),(-w,h-c),(-w,-h+c)]

        def box(label,frame,position,size,material='PaintedMetal_Darker',corner=.006):
            w,h,d=size;loop=outline(w/2,h/2,min(corner,w/4,h/4));vertices=[(x,y,z) for z in (-d/2,d/2) for x,y in loop]
            faces=[tuple(reversed(range(8))),tuple(range(8,16))]+[(i,(i+1)%8,(i+1)%8+8,i+8) for i in range(8)]
            return mesh_object(label,vertices,faces,material,frame @ Matrix.Translation(position))

        def cut(cutter,target):
            if target.data.users>1:target.data=target.data.copy()
            mod=target.modifiers.new('Machined controller recess','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter
            bpy.context.view_layer.objects.active=target;bpy.context.view_layer.update();bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(cutter,do_unlink=True)

        def native_face(template,label,frame,x,y,z,width):
            mesh=template.copy();ps=[v.co for v in mesh.vertices];lo=Vector([min(p[i] for p in ps) for i in range(3)]);hi=Vector([max(p[i] for p in ps) for i in range(3)])
            mesh.transform(Matrix.Scale(width/(hi.x-lo.x),4) @ Matrix.Translation((-(lo.x+hi.x)/2,-(lo.y+hi.y)/2,-lo.z)))
            for i,m in enumerate(mesh.materials):mesh.materials[i]=native.get(m.name.split('.')[0],m)
            obj=bpy.data.objects.new(PREFIX+label,mesh);col.objects.link(obj);obj.parent=root;obj.matrix_basis=frame @ Matrix.Translation((x,y,z));obj['source_asset']='SEUT native atlas; original UVs'
            return obj

        def bolt(frame,x,y,support,front=.002,width=.024):
            r=width*.52;vertices=[(r*math.cos(j*math.tau/8),r*math.sin(j*math.tau/8),z) for z in (-.004,.004) for j in range(8)]
            faces=[tuple(reversed(range(8))),tuple(range(8,16))]+[(j,(j+1)%8,(j+1)%8+8,j+8) for j in range(8)]
            body=mesh_object('captive screw',vertices,faces,'Metal_Shiny',frame @ Matrix.Translation((x,y,front-.002)));body['support']=support.name
            face=native_face(screw,'native screw face',frame,x,y,front+.0025,width);face['fastener_body']=body.name

        def pocket(frame,w,h,shoulder=.040):
            verts=receiver_profile(w,h,shoulder);faces=[(k*8+i,k*8+(i+1)%8,((k+1)%6)*8+(i+1)%8,((k+1)%6)*8+i) for k in range(6) for i in range(8)]
            rim=mesh_object('stepped receiver',verts,faces,'PaintedMetal_Colorable',frame)
            floor=box('receiver floor',frame,(0,0,-.060),(w-.025,h-.025,.022),'PaintedMetal_VeryDark')
            cut(box('temporary aperture',frame,(0,0,-.010),(w-.05,h-.05,.100)),shell)
            return rim,floor

        def cover(frame,w,h,label):
            rim,floor=pocket(frame,w+.08,h+.08,.028)
            panel=box(label,frame,(0,0,-.011),(w,h,.022),'PaintedMetal_Darker',.015)
            for x in (-w/2+.045,w/2-.045):
                for y in (-h/2+.045,h/2-.045):bolt(frame,x,y,panel)
            return panel

        def louvers(frame,w,h,count):
            rim,floor=pocket(frame,w,h)
            for i in range(count):
                y=-(h-.09)/2+(i+.5)*(h-.09)/count
                vane=box('supported cooling vane',frame,(0,y,-.030),(w-.068,.025,.044),'Metal_Dull',.002)
                vane.matrix_basis=frame @ Matrix.Translation((0,y,-.030)) @ Matrix.Rotation(math.radians(20),4,'X');vane['support']=rim.name
            return rim

        # Remove the coarse face furniture, retaining the exact curved adapter.
        for o in list(col.objects):
            if o.type=='MESH' and o!=shell:bpy.data.objects.remove(o,do_unlink=True)
        up=Vector((0,0,1));normal=Vector((0,1,0));t=up.cross(normal)
        front=Matrix((t,up,normal)).transposed().to_4x4();front.translation=(0,-1.045,.17)
        for x in (-.685,.685):
            for y in (-.38,.38):bolt(front,x,y,shell)
        # Recessed lamps have supported black bezels and retain native Emissive.
        header=front @ Matrix.Translation((0,.355,0))
        rim,floor=pocket(header,1.16,.155,.026)
        header_panel=box('status carrier',header,(0,0,-.018),(1.08,.093,.028),'PaintedMetal_Darker')
        for i in range(2 if advanced else 1):
            y=.025-i*.05 if advanced else 0
            stock=box('status lamp seat',header,(0,y,-.001),(.650,.032,.010),'PaintedMetal_VeryDark',.003)
            lamp=box('seated status emitter',header,(0,y,.005),(.598,.017,.009),'Emissive',.002);lamp['support']=stock.name
        stock=box('tier number stock',header,(-.448,0,.001),(.086,.080,.010),'BlackMattePlastic',.004)
        native_face(glyphs['2' if advanced else '1'],'tier number',header,-.448,0,.007,.031)
        # Positive mechanical stops and a lower removable retaining rail.
        rail=box('lower retention rail',front,(0,-.405,-.004),(1.18,.065,.030),'Metal_Dull',.008)
        for x in (-.51,.51):bolt(front @ Matrix.Translation((0,-.405,.011)),x,0,rail,0)
        for sign in (-1,1):
            f=front @ Matrix.Translation((sign*.62,.245,0))
            box('retention rail catch',f,(0,0,.002),(.07,.065,.035),'Metal_Dull',.006)

        if not advanced:
            f=front @ Matrix.Translation((-.15,-.045,0));panel=cover(f,.74,.43,'broad service cassette')
            # Two seated feet carry a physical release handle.
            for x in (-.18,.18):box('cassette pull foot',f,(x,-.11,.010),(.035,.050,.045),'Metal_Dull',.004)
            box('cassette release handle',f,(0,-.11,.033),(.395,.033,.023),'Metal_Shiny',.004)
            # Three shallow stiffening ribs give the broad cover a folded face.
            for x in (-.17,0,.17):box('cassette pressed rib',f,(x,.055,.003),(.055,.16,.012),'PaintedMetal_Colorable',.006)
            louvers(front @ Matrix.Translation((.47,-.045,0)),.255,.52,7)
            for y in (-.18,-.015,.15):
                latch=box('standard side latch',front,(-.64,y,.001),(.065,.090,.028),'Metal_Dull')
                bolt(front,-.64,y,latch,.015,.019)
        else:
            for sign in (-1,1):
                f=front @ Matrix.Translation((sign*.28,-.045,0));panel=cover(f,.37,.39,'paired power cartridge')
                for x in (-.105,-.035,.035,.105):
                    # Fins end on two real spreader saddles, above the cover.
                    saddles=[box('fin saddle',f,(x,y,.005),(.038,.040,.020),'Metal_Dull',.003) for y in (-.105,.105)]
                    fin=box('cartridge heat spreader',f,(x,0,.024),(.020,.245,.028),'Metal_Dull',.003)
                    for i,saddle in enumerate(saddles):fin['support_'+str(i)]=saddle.name
                louvers(front @ Matrix.Translation((sign*.615,-.045,0)),.145,.51,7)
            for y in (-.305,.235):
                # Crossbars contact their terminal posts; no floating buses.
                posts=[]
                for x in (-.28,.28):
                    post=box('bus terminal post',front,(x,y,.007),(.105,.065,.040),'PaintedMetal_Darker')
                    posts.append(post)
                    bolt(front,x,y,post,.027,.022)
                bus=box('connected power bus',front,(0,y,.021),(.49,.033,.025),'Metal_Shiny',.003)
                for i,post in enumerate(posts):bus['support_'+str(i)]=post.name
            box('bus spine seat',front,(0,-.035,-.004),(.058,.55,.025),'PaintedMetal_VeryDark',.005)
            box('power bus spine',front,(0,-.035,.016),(.028,.55,.020),'Metal_Dull',.003)

        # Top and side faces also receive supported detail at engineer scale.
        top=Matrix.Translation((0,-1.215,.670))
        louvers(top,1.05,.145,2 if advanced else 1)
        for sign in (-1,1):
            normal=Vector((sign,0,0));horizontal=up.cross(normal)
            side=Matrix((horizontal,up,normal)).transposed().to_4x4();side.translation=(sign*.8,-1.245,.17)
            if advanced:louvers(side,.145,.47,6)
            else:
                pocket(side,.145,.39,.028)
                panel=box('side inspection cover',side,(0,0,-.021),(.080,.325,.022),'PaintedMetal_Darker',.006)
                for y in (-.12,.12):bolt(side @ Matrix.Translation((0,0,-.010)),0,y,panel,.002,.017)
        scene['controller_detail_revision']=1
        scene['controller_receiver_revision']=2
        scene['controller_detail_variant']='Paired power cartridges, connected buses and dual cooling' if advanced else 'Broad service cassette and passive cooling bank'
        report['variants'][name]={'rear_shell_vertices':rear,'shell':shell.name,'before_main':original_main,'detail':scene['controller_detail_variant']}
        changed.append(name)
        bpy.context.view_layer.update()
        path.write_text(json.dumps(report,indent=2)+'\n')
        bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/arcane-power-prototype.blend'))

    if changed:
        # Existing installed views use collection instances and update directly.
        # Refresh the older loose-object authoring lineup as well.
        review=bpy.data.scenes.get('Arcane Power external hardware review')
        if review:
            for name,offset in zip(NAMES,((-3,-7,0),(1,-7,0))):
                if name not in changed:continue
                for o in list(review.objects):
                    if o.name.startswith(name+' / '):bpy.data.objects.remove(o,do_unlink=True)
                for o in COLS.get_collections(bpy.data.scenes[name])['main'][0].objects:
                    if o.type!='MESH':continue
                    copy=bpy.data.objects.new(name+' / '+o.name,o.data);review.collection.objects.link(copy);copy.matrix_world=Matrix.Translation(offset) @ o.matrix_world
        # These controller edits are authorized successors to the reactor audit's
        # protected old controller meshes. Retain old hashes as history.
        reactor_path=ROOT/'validation/reactor-exterior-loop-01/source.json'
        if reactor_path.exists():
            record=json.loads(reactor_path.read_text());protected=record['protected_objects']
            for name in changed:
                for old,sha in report['variants'][name]['before_main'].items():
                    if old in protected:record.setdefault('controller_main_before_detail',{})[old]=protected.pop(old)
                for o in COLS.get_collections(bpy.data.scenes[name])['main'][0].objects:
                    if o.type=='MESH':protected[o.name]=fingerprint(o)
            reactor_path.write_text(json.dumps(record,indent=2)+'\n')
        runpy.run_path(str(ROOT/'assets/detail_native_textures.py'))['main']()
        bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/arcane-power-prototype.blend'))
        bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/arcane-power-exterior-work-in-progress.blend'),copy=True)
    return {'changed':changed,'saved':bpy.data.filepath}


if __name__=='__main__':result=main(globals().get('CONTROLLER_NAMES',NAMES))
