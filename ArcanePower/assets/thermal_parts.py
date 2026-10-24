"""Shared mesh primitives and base machines for the production thermal builders.

Scene creation, grid/socket contracts and rebuild orchestration live in
build_thermal_models.py. Current cooler and radiator builders own their layouts.
"""
import hashlib
import math
import runpy
from pathlib import Path

import bpy
import bmesh
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
ASSETS = Path.home()/'.local/share/blender-se1-setup/assets'


def uv(obj):
    layer=obj.data.uv_layers.active or obj.data.uv_layers.new(name='UVMap')
    shift=hashlib.sha256(obj.name.encode()).digest()
    for face in obj.data.polygons:
        axes=[i for i in range(3) if i!=max(range(3),key=lambda j:abs(face.normal[j]))]
        for i in face.loop_indices:
            p=obj.data.vertices[obj.data.loops[i].vertex_index].co
            layer.data[i].uv=(p[axes[0]]*.8+shift[0]/255,p[axes[1]]*.8+shift[1]/255)


class Parts:

    def mesh(self,label,verts,faces,mat='PaintedMetal_Darker'):
        mesh=bpy.data.meshes.new('Thermal / '+label);mesh.from_pydata(verts,[],faces)
        bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
        obj=bpy.data.objects.new(self.name+' / '+label,mesh);self.col.objects.link(obj);mesh.materials.append(self.native[mat]);uv(obj)
        return obj

    def box(self,label,p,size,mat='PaintedMetal_Darker',chamfer=.025):
        bm=bmesh.new();bmesh.ops.create_cube(bm,size=1)
        for v in bm.verts:v.co=Vector([v.co[i]*size[i] for i in range(3)])
        if chamfer:bmesh.ops.bevel(bm,geom=list(bm.edges),offset=min(chamfer,min(size)*.18),segments=1,affect='EDGES')
        mesh=bpy.data.meshes.new('Thermal / '+label);bm.to_mesh(mesh);bm.free()
        obj=bpy.data.objects.new(self.name+' / '+label,mesh);self.col.objects.link(obj);mesh.materials.append(self.native[mat]);uv(obj);obj.location=p
        return obj

    def tube(self,label,path,radius,mat='Metal_Dull',wall=.045,sides=24):
        path=[Vector(p) for p in path];verts=[]
        for i,p in enumerate(path):
            tangent=(path[min(i+1,len(path)-1)]-path[max(i-1,0)]).normalized()
            u=Vector((0,0,1)) if abs(tangent.z)<.95 else Vector((0,1,0));u=(u-tangent*u.dot(tangent)).normalized();v=tangent.cross(u)
            for r in (radius,radius-wall):
                verts.extend(p+r*(u*math.cos(j*math.tau/sides)+v*math.sin(j*math.tau/sides)) for j in range(sides))
        faces=[]
        for k in range(len(path)-1):
            for ring in (0,1):
                a=k*sides*2+ring*sides;b=(k+1)*sides*2+ring*sides
                for j in range(sides):faces.append((a+j,a+(j+1)%sides,b+(j+1)%sides,b+j))
        for k in (0,len(path)-1):
            a=k*sides*2
            for j in range(sides):faces.append((a+j,a+(j+1)%sides,a+sides+(j+1)%sides,a+sides+j))
        obj=self.mesh(label,verts,faces,mat)
        for face in obj.data.polygons[:2*sides*(len(path)-1)]:face.use_smooth=True
        return obj

    def cylinder(self,label,a,b,radius,mat='Metal_Dull',sides=32):
        a,b=Vector(a),Vector(b);frame=(b-a).to_track_quat('Z','Y').to_matrix()
        verts=[a+frame @ Vector((radius*math.cos(j*math.tau/sides),radius*math.sin(j*math.tau/sides),z)) for z in (0,(b-a).length) for j in range(sides)]
        faces=[tuple(reversed(range(sides))),tuple(range(sides,sides*2))]+[(j,(j+1)%sides,(j+1)%sides+sides,j+sides) for j in range(sides)]
        obj=self.mesh(label,verts,faces,mat)
        for face in obj.data.polygons[2:]:face.use_smooth=True
        return obj

    def bolt(self,label,p,n,support,r=.033):
        p,n=Vector(p),Vector(n).normalized()
        obj=self.cylinder(label,p-n*.009,p+n*.009,r,'Metal_Shiny',6);obj['thermal_support']=support.name;obj['support_axis']=tuple(n);obj['support_point']=tuple(p)
        self.support.append(obj.name);return obj

    def panel(self,label,p,size,n=(0,-1,0)):
        obj=self.box(label,p,size,'PaintedMetal_Darker',.015)
        axis=max(range(3),key=lambda i:abs(n[i]));axes=[i for i in range(3) if i!=axis]
        for a in (-1,1):
            for b in (-1,1):
                point=Vector(p)+Vector(n)*(size[axis]/2-.004)
                point[axes[0]]+=a*(size[axes[0]]/2-.095);point[axes[1]]+=b*(size[axes[1]]/2-.095)
                self.bolt(label+' captive bolt',point,n,obj)
        return obj

    def branch_pipe(self,label,a,b,branches,radius=.355,wall=.075):
        """One hollow manifold with connected bores through all branches."""
        obj=self.cylinder(label,a,b,radius,'PaintedMetal_Darker',32)
        def boolean(other,operation):
            bpy.context.view_layer.objects.active=obj
            mod=obj.modifiers.new('Manifold '+operation,'BOOLEAN');mod.operation=operation;mod.solver='EXACT';mod.object=other
            bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(other,do_unlink=True)
            bm=bmesh.new();bm.from_mesh(obj.data)
            bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.00002)
            bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=.00001)
            bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(obj.data);bm.free()
        def branch(label,start,end,r):
            cutter=self.cylinder(label,start,end,r,'PaintedMetal_Darker')
            # Offset branch tessellation to avoid coincident cylinder edges.
            origin=Vector(start);rotation=Matrix.Rotation(math.pi/64,3,(Vector(end)-origin).normalized())
            for vertex in cutter.data.vertices:vertex.co=origin+rotation@(vertex.co-origin)
            return cutter
        for start,end in branches:boolean(branch('temporary outer branch',start,end,radius),'UNION')
        direction=(Vector(b)-Vector(a)).normalized()
        boolean(self.cylinder('temporary main bore',Vector(a)-direction*.15,Vector(b)+direction*.15,radius-wall),'DIFFERENCE')
        for start,end in branches:
            direction=(Vector(end)-Vector(start)).normalized()
            boolean(branch('temporary branch bore',start,Vector(end)+direction*.15,radius-wall),'DIFFERENCE')
        uv(obj);return obj

    def port(self,label,p,n,kind='PRIMARY',up=(0,0,1)):
        p,n,up=Vector(p),Vector(n).normalized(),Vector(up).normalized()
        assert abs(n.dot(up))<1e-6,'Duplex hot axis must lie in the port face'
        u=up.cross(n).normalized()
        frame=Matrix((u,up,n)).transposed().to_4x4();frame.translation=p
        # A common flange with two real machined bores. Build once, then share.
        template=bpy.data.meshes.get('Thermal shared duplex flange')
        if template is None:
            plate=self.box('duplex flange master',(0,0,-.10),(2.04,2.04,.12),'PaintedMetal_Colorable',.045)
            for sign in (-1,1):
                cutter=self.cylinder('temporary port bore',(0,sign*.46,-.35),(0,sign*.46,.15),.275,'Metal_Dull',32)
                bpy.context.view_layer.objects.active=plate
                modifier=plate.modifiers.new('Machined through bore','BOOLEAN');modifier.operation='DIFFERENCE';modifier.solver='EXACT';modifier.object=cutter
                bpy.ops.object.modifier_apply(modifier=modifier.name);bpy.data.objects.remove(cutter,do_unlink=True)
            template=plate.data;template.transform(plate.matrix_world);uv(plate);template.name='Thermal shared duplex flange';template['flange_revision']=1;bpy.data.objects.remove(plate,do_unlink=True)
        plate=bpy.data.objects.new(self.name+' / '+label+' flange',template);self.col.objects.link(plate);plate.matrix_world=frame
        for sign in (-1,1):
            centre=p+up*(sign*.46)
            self.tube(label+' pressure lip '+str(sign),(centre-n*.075,centre-n*.018),.385,'Metal_Dull',.11)
            self.tube(label+' seated face seal '+str(sign),(centre-n*.022,centre),.308,'PaintedMetal_VeryDark',.04)
            # Positive top and return bottom remain separate through elbows.
            for x in (-.79,.79):self.bolt(label+' flange bolt',p+u*x+up*(sign*.79)-n*.035,n,plate)
        marker=bpy.data.objects.new(self.name+' / PORT '+label,None);self.col.objects.link(marker);marker.matrix_world=frame;marker.empty_display_size=.15
        marker['port_type']=kind;marker['port_id']=label;marker['hot_axis']=(0,1,0);self.ports.append({'id':label,'type':kind,'position':list(p),'normal':list(n),'hot_axis':list(up)})
        self.label(plate,kind.replace('_',' / '),p+up*.84-n*.038,u,up,.095)
        for sign,text in ((1,'H'),(-1,'C')):self.label(plate,text,p+up*(sign*.46)+u*.60-n*.038,u,up,.10)
        return plate

    def base(self):
        x,y,z=self.size;floor=-z/2
        for sign in (-1,1):
            self.box('load-bearing skid',(0,sign*(y/2-.52),floor+.20),(x-.30,.52,.40),'PaintedMetal_Colorable',.035)
        for px in (-x/2+.55,0,x/2-.55):
            self.box('transverse skid',(px,0,floor+.29),(.46,y-.45,.28),'Metal_Dull',.025)
        self.box('equipment foundation',(0,0,floor+.34),(x-.45,y-.75,.20),'PaintedMetal_Darker',.025)
        return floor

    def saddle(self,label,x,radius,centre=.45,width=.55):
        floor=-self.size.z/2+.4;r=radius-.008
        points=[(-r+.16,floor),(r-.16,floor),(r+.08,centre-.22),(r+.08,centre),(r,centre)]
        points.extend((r*math.cos(i*math.pi/20),centre-r*math.sin(i*math.pi/20)) for i in range(1,21));points.extend(((-r-.08,centre),(-r-.08,centre-.22)))
        verts=[(x+dx,y,z) for dx in (-width/2,width/2) for y,z in points];count=len(points)
        return self.mesh(label,verts,[tuple(reversed(range(count))),tuple(range(count,count*2))]+[(i,(i+1)%count,(i+1)%count+count,i+count) for i in range(count)],'PaintedMetal_Colorable')

    def hazard(self,support,centre,u,v,asset='Sign High Pressure',width=.24):
        key='Thermal native template / '+asset;template=bpy.data.meshes.get(key)
        if template is None:
            with bpy.data.libraries.load(str(ASSETS/'Models/Decals/Atlas2.blend'),link=False) as (src,dst):dst.objects=[asset]
            template=dst.objects[0].data.copy();template.name=key;bpy.data.objects.remove(dst.objects[0],do_unlink=True)
        mesh=template.copy();ps=[x.co for x in mesh.vertices];lo=Vector([min(p[i] for p in ps) for i in range(3)]);hi=Vector([max(p[i] for p in ps) for i in range(3)]);scale=width/(hi.x-lo.x);middle=(lo+hi)/2
        u,v=Vector(u).normalized(),Vector(v).normalized();centre=Vector(centre)
        for vertex in mesh.vertices:
            p=(vertex.co-middle)*scale;vertex.co=centre+u*p.x+v*p.y
        for i,m in enumerate(mesh.materials):mesh.materials[i]=self.native[m.name.split('.')[0]]
        obj=bpy.data.objects.new(self.name+' / native '+asset,mesh);self.col.objects.link(obj);obj['thermal_decal_support']=support.name;obj['source_asset']='SEUT Atlas2 '+asset
        return obj

    def label(self,support,text,centre,u=(1,0,0),v=(0,0,1),size=.10):
        """Readable markings on a real panel; keep text editable in the source."""
        u,v=Vector(u).normalized(),Vector(v).normalized();n=u.cross(v)
        data=bpy.data.curves.new('Thermal marking / '+text,'FONT');data.body=text
        data.size=size;data.align_x='CENTER';data.align_y='CENTER'
        material='PaintedMetal_VeryDark' if support.data.materials[0].name=='PaintedMetal_Colorable' else 'Metal_Dull'
        data.materials.append(self.native[material])
        obj=bpy.data.objects.new(self.name+' / marking '+text,data);self.col.objects.link(obj)
        obj.matrix_world=Matrix((u,v,n)).transposed().to_4x4();obj.location=centre
        obj['thermal_marking_support']=support.name
        return obj


def brayton(p):
    contract = runpy.run_path(str(ROOT/'assets/thermal_model_contract.py'))
    shaft_z = contract['TRAIN_SHAFT_Z']
    cx, tx, gx, bx = (contract['TRAIN_CENTRES'][k] for k in ('compressor','turbine','generator','cabinet'))
    p.base()
    for label,x,length,r in (('compressor',cx,2.0,1.35),('turbine',tx,2.75,1.85),('generator',gx,2.0,1.62)):
        if label=='generator':
            x=contract['generator_x'](x); length*=contract['TRAIN_GENERATOR_STRETCH']
        rear=contract['TRAIN_GENERATOR_REAR'] if label=='generator' else x+length/2
        p.cylinder(label+' casing',(x-length/2,0,shaft_z),(rear,0,shaft_z),r,'PaintedMetal_Darker',48)
        for sx in (x-length*.33,x+length*.33):
            p.saddle(label+' fitted cradle',sx,r,centre=shaft_z,width=.40)
            p.tube(label+' split casing band',((sx-.055,0,shaft_z),(sx+.055,0,shaft_z)),r+.06,'Metal_Dull',.08,48)
        for sign in (-1,1):
            if (label == 'compressor' and sign == 1) or (label == 'turbine' and sign == -1):continue
            sx=rear if sign==1 else x-length/2
            cover=p.cylinder(label+' bolted end cover',(sx-.035,0,shaft_z),(sx+.035,0,shaft_z),r*.96,'PaintedMetal_Colorable',48)
            for i in range(12):
                a=i*math.tau/12;p.bolt(label+' end cover stud',(sx+sign*.032,math.cos(a)*r*.83,shaft_z+math.sin(a)*r*.83),(sign,0,0),cover,.04)
    for a,b in ((tx+1.33,tx+1.83),):
        p.tube('split shaft coupling guard',((a,0,shaft_z),(b,0,shaft_z)),.36,'PaintedMetal_Colorable',.06)
    p.cylinder('turbine generator shaft',(tx-1.375,0,shaft_z),(contract['TRAIN_GENERATOR_REAR']+.20,0,shaft_z),.22,'Metal_Shiny')
    p.cylinder('independent compressor shaft',(cx-1.65,0,shaft_z),(cx+1.0,0,shaft_z),.18,'Metal_Shiny')
    p.cylinder('electric compressor motor',(cx-1.65,0,shaft_z),(cx-.95,0,shaft_z),.75,'PaintedMetal_Colorable',40)
    p.saddle('compressor motor cradle',cx-1.30,.75,centre=shaft_z,width=.42)
    terminal=p.box('compressor motor terminal',(cx-1.30,-.70,shaft_z),(.48,.35,.52),'PaintedMetal_Darker')
    p.label(terminal,'M',(cx-1.30,-.877,shaft_z),size=.16)
    scale=.7
    width,depth,height=(v*scale for v in (1.45,3.1,3.1))
    bottom=-p.size.z/2+.44; top=bottom+height
    cabinet_centre=Vector((bx,0,bottom+height/2))
    at=lambda offset: cabinet_centre+Vector(offset)*scale
    # The smaller enclosure bears directly on the foundation. Its forward
    # roof slope echoes the adjoining tapered pressure housings.
    section=[(-width/2,bottom),(width/2,bottom),(width/2,top-.08),
             (width/2-.08,top),(-width/2+.18,top),(-width/2,top-.25)]
    n=len(section)
    verts=[(bx+x,y,z) for y in (-depth/2,depth/2) for x,z in section]
    cabinet=p.mesh('generator switchgear',verts,[tuple(reversed(range(n))),tuple(range(n,2*n))]
        +[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],'PaintedMetal_Colorable')
    cabinet['thermal_cabinet_scale']=scale
    # Keep the half-round shaft cover as the final seat into the cabinet roof.
    profiles=[]
    for x,r,z in ((contract['TRAIN_GENERATOR_REAR']-.04,.62,shaft_z),(bx-.24,.44,shaft_z-.05)):
        section=[(-r,-.65),(r,-.65)]
        section += [(r*math.cos(i*math.pi/24),z+r*math.sin(i*math.pi/24)) for i in range(25)]
        profiles.extend((x,y,sz) for y,sz in section)
    n=len(section)
    hood=p.mesh('generator cabinet coupling hood',profiles,
        [tuple(reversed(range(n))),tuple(range(n,2*n))]
        +[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],'PaintedMetal_Colorable')
    hood['thermal_coupling_hood']=True
    hood['thermal_seated_on']=cabinet.name
    for face in hood.data.polygons:
        face.use_smooth=face.index>=4 and face.index<2+n-1
    cover=p.panel('supported switchgear door',at((0,-1.57,0)),Vector((1.2,.12,2.65))*scale)
    p.hazard(cover,at((0,-1.631,.65)),(1,0,0),(0,0,1),'Sign High Voltage',.28*scale)
    # The visibility pass routes the cable with tangent bends after the deck
    # and cabinet are final, before cutting support clearances.
    contract = runpy.run_path(str(ROOT/'assets/thermal_model_contract.py'))
    for port in contract['TRAIN_PORTS']:
        p.port(port['id'], port['position'], port['normal'], port['type'], port['hot_axis'])
    # Seated end-plenum piping follows the final hollow casings in the visibility stage.
    for x in (tx-.55,tx+.05,tx+.65):p.box('turbine inspection rib',(x,-1.65,1.55),(.30,.35,.7),'Metal_Dull',.018)
    for x in (gx-.80,gx-.40,gx,gx+.40,gx+.80):
        p.box('stator cooling jacket',(contract['generator_x'](x),0,shaft_z+1.55),(.12,1.2,.20),'Metal_Dull',.01)


def rejector(p):
    p.base()
    for x in (-3.2,3.2):
        p.cylinder('coolant vertical header',(x,.55,-2.75),(x,.55,2.75),.30)
        p.box('cooler corner support',(x,1.95,-.1),(.35,.35,6.5),'PaintedMetal_Colorable')
    for i in range(31):p.box('solid cooling fin',(0,.5,-2.5+i*.165),(6.0,2.4,.075),'Metal_Dull',.004)
    # A closed plenum carries both shrouds and directs airflow through the fins.
    face=p.box('fan mounting face',(0,-1.46,.4),(6.4,.16,5.5),'PaintedMetal_Darker')
    for x in (-1.68,1.68):
        cutter=p.cylinder('temporary fan aperture',(x,-1.8,.4),(x,-1.1,.4),1.42,sides=48)
        bpy.context.view_layer.objects.active=face
        mod=face.modifiers.new('Fan bore','BOOLEAN');mod.operation='DIFFERENCE';mod.object=cutter
        bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(cutter,do_unlink=True)
    uv(face)
    for x in (-3.16,3.16):p.box('plenum side return',(x,-1.05,.4),(.08,.82,5.5),'PaintedMetal_Darker')
    for z in (-2.31,3.11):p.box('plenum horizontal return',(0,-1.05,z),(6.4,.82,.08),'PaintedMetal_Darker')
    for x in (-3.0,3.0):
        for y in (-.5,1.5):p.box('cooler mounting leg',(x,y,-3.0),(.32,.32,1.1),'PaintedMetal_Colorable')
    p.label(face,'ATMOSPHERIC COOLER / KEEP CLEAR',(0,-1.542,2.53),size=.14)
    for x in (-1.68,1.68):
        p.tube('fan shroud',((x,-1.5,.4),(x,-2.30,.4)),1.53,'PaintedMetal_Colorable',.12,48)
        p.cylinder('fan motor',(x,-1.4,.4),(x,-2.05,.4),.31,'PaintedMetal_Darker')
        for a in (0,math.tau/3,2*math.tau/3):
            p.cylinder('rear motor mounting spider',(x,-1.43,.4),Vector((x,-1.43,.4))+Vector((math.cos(a),0,math.sin(a)))*1.48,.045,'Metal_Dull',8)
        # Real pitched solid blades; their axis/pivot are recorded for runtime.
        pivot=bpy.data.objects.new(p.name+' / fan pivot',None);p.col.objects.link(pivot);pivot.location=(x,-1.94,.4);pivot['runtime_axis']=(0,1,0)
        for j in range(8):
            a=j*math.tau/8;u=Vector((math.cos(a),0,math.sin(a)));t=Vector((-math.sin(a),0,math.cos(a)));centre=Vector((x,-1.94,.4))
            verts=[centre+u*r+t*w+Vector((0,y+w*.65,0)) for y in (-.035,.035) for r,w in ((.26,-.08),(1.32,-.17),(1.28,.22),(.28,.10))]
            blade=p.mesh('pitched fan blade',verts,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],'Metal_Shiny')
            for vertex in blade.data.vertices:vertex.co-=centre
            blade['fan_pivot']=pivot.name;blade.parent=pivot
        for radius in (.55,.95,1.35):p.tube('fan guard hoop',((x,-2.35,.4),(x,-2.31,.4)),radius,'Metal_Dull',.028,48)
        for j in range(8):
            a=j*math.tau/8;end=Vector((x,-2.33,.4))+Vector((math.cos(a),0,math.sin(a)))*1.48
            p.cylinder('fan guard spoke',(x,-2.33,.4),end,.022,'Metal_Dull',8)
    # Open exhaust guard: fan cooling has no vacuum emitter or utility circuit.
    for x in (-3.05,3.05):p.box('exhaust guard upright',(x,1.80,.15),(.13,.14,5.8),'PaintedMetal_Colorable')
    for z in (-2.6,2.9):p.box('exhaust guard crossrail',(0,1.80,z),(6.2,.14,.14),'PaintedMetal_Colorable')
    for z in range(13):p.box('open exhaust guard',(0,1.82,-2.4+z*.42),(6.1,.075,.045),'Metal_Dull',.006)
    p.port('CO2',(-3.75,1.25,0),(-1,0,0),'CO2_LP')
    for z in (-.46,.46):p.tube('coolant inlet stub',((-3.6,1.25,z),(-3.3,1.25,z),(-3.0,.55,z)),.29)


def upgraded(p):
    """Add the standard upgraded turbine controller before refinement."""
    brayton(p)
    c=runpy.run_path(str(ROOT/'assets/thermal_model_contract.py'))['TRAIN_CENTRES']
    cx,tx,gx=c['compressor'],c['turbine'],c['generator']
    # Production jackets follow the final hollow casings in the visibility
    # pass, so no upgrade ribs cross the inspection apertures.
    p.box('optimization controller mount',(cx,-1.05,-.45),(1.12,.60,.82),'PaintedMetal_Colorable')
    cover=p.panel('compressor optimization controller',(cx,-1.41,-.45),(1.0,.14,.72))
    p.label(cover,'OPT / III',(cx,-1.482,-.45),size=.11)
    p.col['upgrade_grade']=3
