"""Editable thermal-plant concepts; never exports or changes production assets.

Run prepare() in the accepted reactor file, then build(name) in bounded live
Blender calls. Model coordinates are X length, Y width, Z up, in metres.
"""
import hashlib
import json
import math
import runpy
from pathlib import Path

import bpy
import bmesh
from mathutils import Matrix, Vector

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'validation/thermal-concepts'
FILE=ROOT/'assets/arcane-thermal-concepts.blend'
ASSETS=Path.home()/'.local/share/blender-se1-setup/assets'
SPECS={
    'Brayton train':(5,3,2),'Primary heater':(3,3,3),
    'Recuperator':(3,2,3),'Atmospheric cooler':(3,2,3),
    'Space radiator':(3,2,3),'Brayton train upgraded':(5,3,2),
    'Primary heater upgraded':(3,3,3),'Recuperator upgraded':(3,2,3),
    'Duplex straight':(1,1,1),'Duplex elbow':(1,1,1),'Duplex tee':(1,1,1),
}


def prepare():
    assert Path(bpy.data.filepath).name=='arcane-power-prototype.blend'
    OUT.mkdir(exist_ok=True)
    refs={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (
        ROOT/'assets/arcane-power-prototype.blend',ROOT/'assets/arcane-energy-core.blend')}
    s=bpy.data.scenes['ArcanePower_ReactorPrototype'];bpy.context.window.scene=s;bpy.context.view_layer.update()
    import importlib
    col=importlib.import_module('space-engineers-utilities.seut_collections').get_collections(s)['main'][0]
    rows=[{'object':o.name,'mesh':o.data.name,'matrix':[list(r) for r in o.matrix_world]} for o in col.objects if o.type=='MESH']
    (OUT/'reactor-reference.json').write_text(json.dumps(rows))
    (OUT/'protected-production.json').write_text(json.dumps(refs,indent=2)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(FILE))
    return {'file':str(FILE),'models':SPECS,'production_files_preserved':True}


def uv(obj):
    layer=obj.data.uv_layers.active or obj.data.uv_layers.new(name='UVMap')
    shift=hashlib.sha256(obj.name.encode()).digest()
    for face in obj.data.polygons:
        axes=[i for i in range(3) if i!=max(range(3),key=lambda j:abs(face.normal[j]))]
        for i in face.loop_indices:
            p=obj.data.vertices[obj.data.loops[i].vertex_index].co
            layer.data[i].uv=(p[axes[0]]*.8+shift[0]/255,p[axes[1]]*.8+shift[1]/255)


class Parts:
    def __init__(self,name):
        assert Path(bpy.data.filepath)==FILE,'Work in the separate concept file'
        self.name=name;self.size=Vector(SPECS[name])*2.5
        scene_name='Thermal / '+name
        assert scene_name not in bpy.data.scenes,'Use the existing concept; do not duplicate a build'
        self.scene=bpy.data.scenes.new(scene_name);bpy.context.window.scene=self.scene
        self.scene.unit_settings.system='METRIC';self.scene.unit_settings.scale_length=1
        self.col=bpy.data.collections.new('Thermal model / '+name);self.scene.collection.children.link(self.col)
        self.col['thermal_concept']=name;self.col['grid_cells']=SPECS[name]
        self.native={m.name:m for m in bpy.data.materials if m.library}
        self.ports=[];self.support=[]

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
        points=[(-r-.2,floor),(r+.2,floor),(r+.2,centre),(r,centre)]
        points.extend((r*math.cos(i*math.pi/20),centre-r*math.sin(i*math.pi/20)) for i in range(1,21));points.append((-r-.2,centre))
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
        """Readable markings on a real panel; keep text editable in the study."""
        u,v=Vector(u).normalized(),Vector(v).normalized();n=u.cross(v)
        data=bpy.data.curves.new('Thermal marking / '+text,'FONT');data.body=text
        data.size=size;data.align_x='CENTER';data.align_y='CENTER'
        material='PaintedMetal_VeryDark' if support.data.materials[0].name=='PaintedMetal_Colorable' else 'Metal_Dull'
        data.materials.append(self.native[material])
        obj=bpy.data.objects.new(self.name+' / marking '+text,data);self.col.objects.link(obj)
        obj.matrix_world=Matrix((u,v,n)).transposed().to_4x4();obj.location=centre
        obj['thermal_marking_support']=support.name
        return obj

    def finish(self):
        self.col['ports']=json.dumps(self.ports);self.scene['thermal_concept']=self.name
        return {'model':self.name,'cells':SPECS[self.name],'meshes':sum(o.type=='MESH' for o in self.col.objects),'ports':self.ports}


def brayton(p):
    p.base()
    for label,x,length,r in (('compressor',-4.25,2.0,1.35),('turbine',-1.35,2.75,1.85),('generator',2.05,3.25,1.62)):
        p.cylinder(label+' casing',(x-length/2,0,.45),(x+length/2,0,.45),r,'PaintedMetal_Darker',48)
        for sx in (x-length*.33,x+length*.33):
            p.saddle(label+' fitted cradle',sx,r)
            p.tube(label+' split casing band',((sx-.055,0,.45),(sx+.055,0,.45)),r+.06,'Metal_Dull',.08,48)
        for sign in (-1,1):
            sx=x+sign*length/2
            cover=p.cylinder(label+' bolted end cover',(sx-.035,0,.45),(sx+.035,0,.45),r*.96,'PaintedMetal_Colorable',48)
            for i in range(12):
                a=i*math.tau/12;p.bolt(label+' end cover stud',(sx+sign*.032,math.cos(a)*r*.83,.45+math.sin(a)*r*.83),(sign,0,0),cover,.04)
    for a,b in ((-.02,.48),):
        p.tube('split shaft coupling guard',((a,0,.45),(b,0,.45)),.36,'PaintedMetal_Colorable',.06)
    p.cylinder('turbine generator shaft',(-2.725,0,.45),(4.25,0,.45),.22,'Metal_Shiny')
    p.cylinder('independent compressor shaft',(-5.9,0,.45),(-3.25,0,.45),.18,'Metal_Shiny')
    p.cylinder('electric compressor motor',(-5.9,0,.45),(-5.2,0,.45),.75,'PaintedMetal_Colorable',40)
    p.saddle('compressor motor cradle',-5.55,.75,width=.42)
    terminal=p.box('compressor motor terminal',(-5.55,-.70,.45),(.48,.35,.52),'PaintedMetal_Darker')
    p.label(terminal,'M',(-5.55,-.877,.45),size=.16)
    p.tube('compressor supply conduit',((4.4,-2.5,-1.98),(-5.55,-2.5,-1.98),(-5.55,-2.5,.45),(-5.55,-.72,.45)),.09,'PaintedMetal_VeryDark',.025,16)
    for x in (4.05,4.75):
        p.box('switchgear pedestal',(x,0,-2.0),(.50,2.4,.4),'PaintedMetal_Colorable')
    p.box('generator switchgear',(4.4,0,-.30),(2.0,3.1,3.1),'PaintedMetal_Colorable')
    cover=p.panel('supported switchgear door',(4.4,-1.57,-.3),(1.7,.12,2.65))
    p.hazard(cover,(4.4,-1.631,.35),(1,0,0),(0,0,1),'Sign High Voltage',.28)
    # Supported electrical trunk terminates in the generator cabinet.
    p.box('bus trunk',(2.9,-1.55,-1.6),(2.0,.32,.38),'Metal_Shiny')
    for x in (2.1,3.5):p.box('bus pedestal',(x,-1.55,-2.03),(.35,.5,.5),'PaintedMetal_VeryDark')
    contract = runpy.run_path(str(ROOT/'assets/thermal_model_contract.py'))
    for port in contract['TRAIN_PORTS']:
        p.port(port['id'], port['position'], port['normal'], port['type'], port['hot_axis'])
    # Seated end-plenum piping follows the final hollow casings in the visibility stage.
    for x in (-1.9,-1.3,-.7):p.box('turbine inspection rib',(x,-1.65,1.55),(.30,.35,.7),'Metal_Dull',.018)
    for x in (1.05,1.55,2.05,2.55,3.05):
        p.box('stator cooling jacket',(x,0,2.0),(.12,1.2,.20),'Metal_Dull',.01)


def heater(p):
    p.base()
    for x in (-2.6,2.6):
        for y in (-2.6,2.6):p.box('exchanger corner post',(x,y,-.1),(.48,.48,6.5),'PaintedMetal_Colorable')
    for z in (-2.65,2.65):p.box('exchanger end plate',(0,0,z),(5.8,5.8,.38),'PaintedMetal_Colorable')
    for x in (-1.25,1.25):
        for y in (-1.25,1.25):
            p.cylinder('isolated exchanger vessel',(x,y,-2.55),(x,y,2.55),.75,'PaintedMetal_Darker',40)
            for z in (-1.9,0,1.9):p.tube('pressure vessel band',((x,y,z-.075),(x,y,z+.075)),.82,'Metal_Dull',.09)
    p.port('primary',(-3.75,0,0),(-1,0,0),'PRIMARY')
    p.port('CO2',(0,-3.75,0),(0,-1,0),'CO2_HP')
    for sign in (-1,1):
        z=sign*.46
        p.tube('primary distribution',((-3.6,0,z),(-1.25,0,z),(1.25,0,z)),.29)
        for x in (-1.25,1.25):p.tube('primary vessel branches',((x,-1.25,z),(x,1.25,z)),.24)
        # Separate CO2 headers approach the vessels at different elevations.
        p.tube('CO2 distribution',((0,-3.6,z),(0,-3.05,z),(0,-2.15,sign*1.5),(0,1.25,sign*1.5)),.29)
        for y in (-1.25,1.25):p.tube('CO2 vessel branches',((-1.25,y,sign*1.5),(1.25,y,sign*1.5)),.24)
    for x in (-1.55,1.55):
        for z in (-2.2,2.1):p.box('cassette backing rail',(x,-2.53,z),(2.1,.32,.18),'Metal_Dull')
        panel=p.panel('front service cassette',(x,-2.73,-.05),(1.90,.20,4.6))
        p.hazard(panel,(x,-2.832,1.35),(1,0,0),(0,0,1),'Sign High Pressure',.32)
        p.box('cassette pull',(x,-2.90,-.8),(.55,.16,.09),'Metal_Shiny',.012)
        p.label(panel,'HX / '+('A' if x<0 else 'B'),(x,-2.832,.65),size=.14)


def recuperator(p):
    p.base()
    for x in (-3.2,3.2):
        for y in (-2.0,2.0):p.box('counterflow frame post',(x,y,-.05),(.35,.35,6.6),'PaintedMetal_Colorable')
    for x in (-1.55,1.55):
        for z in (-2.6,2.6):p.box('plate bank end clamp',(x,0,z),(2.85,3.7,.30),'PaintedMetal_Darker')
        for i in range(26):p.box('counterflow plate',(x,0,-2.4+i*.192),(2.65,3.5,.095),'Metal_Dull',.006)
        for y in (-1.87,1.87):p.cylinder('stack tie rod',(x,y,-2.8),(x,y,2.8),.075,'Metal_Shiny',12)
    for sign in (-1,1):
        p.port('high-pressure '+str(sign),(sign*3.75,-1.25,0),(sign,0,0),'CO2_HP')
        p.port('low-pressure '+str(sign),(sign*3.75,1.25,0),(sign,0,0),'CO2_LP')
        for y in (-1.25,1.25):
            working=-.46 if y<0 else .46
            p.tube('working leg manifold',((sign*3.6,y,working),(sign*2.5,y,working)),.29)
    for y,z in ((-1.25,-.46),(1.25,.46)):
        p.tube('plate bank working bridge',((-.45,y,z),(.45,y,z)),.24,'Metal_Dull',.045)
    # HP hot feed and LP cold return bypass the exchange banks, separately.
    for y,z in ((-1.25,.46),(1.25,-.46)):
        bypass_y=math.copysign(.45,y)
        p.tube('insulated non-working bypass',((-3.6,y,z),(-3.3,y,z),(-3.3,bypass_y,z),(-3.3,bypass_y,3.05),(3.3,bypass_y,3.05),(3.3,bypass_y,z),(3.3,y,z),(3.6,y,z)),.29,'PaintedMetal_VeryDark')
    for y in (-2.04,2.04):
        rail=p.box('bank identifier rail',(0,y,2.1),(6.1,.12,.35),'PaintedMetal_Darker')
        p.label(rail,'RECUPERATOR / COUNTERFLOW',(0,y+math.copysign(.062,y),2.1),(math.copysign(-1,y),0,0),(0,0,1),.13)


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


def radiator(p):
    """Two-sided framed radiation panels with exposed tiles and pump service."""
    p.base()
    for x in (-1.55,1.55):
        p.box('radiator load post',(x,0,-2.975),(.38,.55,.80),'PaintedMetal_Colorable')
        p.box('radiator panel substrate',(x,0,.25),(2.78,.16,5.75),'Metal_Dull',.018)
        for sign in (-1,1):
            for column in range(3):
                for row in range(9):
                    tile=p.box('high emissivity radiator tile',(x+(column-1)*.89,sign*.115,-2.30+row*.635),(.86,.07,.60),'PaintedMetal_VeryDark',.009)
                    tile['radiating_surface']=True;tile['surface_side']=sign
            for dx in (-1.40,1.40):p.box('panel edge heat pipe',(x+dx,sign*.10,.25),(.07,.20,5.9),'Metal_Dull',.012)
    for x in (-3.05,3.05):
        p.cylinder('radiator vertical header',(x,0,-2.8),(x,0,3.2),.17,'Metal_Dull',24)
    for z in (-2.55,3.12):p.cylinder('radiator distribution header',(-3.05,0,z),(3.05,0,z),.14,'Metal_Dull',24)
    rail=p.box('radiator top rail',(0,0,3.38),(6.4,.45,.25),'PaintedMetal_Colorable')
    for sign in (-1,1):p.label(rail,'SPACE RADIATOR / CLEAR SKY',(0,sign*.227,3.38),(-sign,0,0),(0,0,1),.105)
    p.port('CO2',(-3.75,1.25,0),(-1,0,0),'CO2_LP')
    for z in (-.46,.46):p.tube('radiator inlet stub',((-3.6,1.25,z),(-3.3,1.25,z),(-3.05,0,z)),.29)
    cabinet=p.panel('radiator pump service',(0,-.30,-2.85),(1.15,.35,.65))
    p.label(cabinet,'PUMP', (0,-.477,-2.85),size=.10)
    p.box('pump cabinet mount',(0,-.30,-3.22),(1.25,.55,.22),'PaintedMetal_Colorable')


def upgraded(p,base):
    """Maximum-grade equipment shares the accepted base envelope and port poses."""
    base(p)
    if base is brayton:
        for x in (-1.9,-.8):
            box=p.box('high temperature turbine cassette',(x,0,2.14),(.70,1.5,.42),'PaintedMetal_Colorable')
            p.label(box,'HT', (x,-.752,2.26),size=.12)
        for x in (1.05,2.05,3.05):p.box('upgraded stator fin',(x,-1.50,.45),(.30,.30,1.1),'Metal_Dull')
        p.box('optimization controller mount',(-4.25,-1.05,-.45),(1.12,.60,.82),'PaintedMetal_Colorable')
        cover=p.panel('compressor optimization controller',(-4.25,-1.41,-.45),(1.0,.14,.72))
        p.label(cover,'OPT / III',(-4.25,-1.482,-.45),size=.11)
    elif base is heater:
        for x in (-1.55,1.55):
            panel=p.panel('exotic hot end service cassette',(x,2.73,.5),(1.9,.20,2.8),(0,1,0))
            p.label(panel,'HT / 1200 C',(x,2.832,1.65),(-1,0,0),(0,0,1),.12)
            for z in (-.3,.1,.5,.9,1.3):p.box('hot end reinforcement',(x,2.85,z),(1.5,.12,.075),'Metal_Dull')
            for z in (-.6,1.6):p.box('rear cassette seat',(x,2.53,z),(2.1,.32,.18),'Metal_Dull')
    else:
        for y in (-1.94,1.94):
            for x in (-1.55,1.55):
                panel=p.panel('precision exchange manifold',(x,y,.4),(1.4,.20,2.8),(0,math.copysign(1,y),0))
                for z in (-.7,1.5):p.box('manifold backing bridge',(x,y-math.copysign(.12,y),z),(1.55,.30,.18),'Metal_Dull')
                for z in (-.5,0,.5,1):p.box('manifold heat bridge',(x,y+math.copysign(.12,y),z),(1.1,.08,.08),'Metal_Dull')
                p.label(panel,'HX / III',(x,y+math.copysign(.102,y),1.5),(-math.copysign(1,y),0,0),(0,0,1),.10)
    p.col['upgrade_grade']=3


def conduit(p,elbow=False):
    if elbow:
        path=[(-1.25,0,0),(-.6,0,0)]+[(-.6+.6*math.cos(a),.6+.6*math.sin(a),0) for a in [-math.pi/2+i*math.pi/24 for i in range(1,13)]]+[(0,1.25,0)]
        p.port('west',(-1.25,0,0),(-1,0,0));p.port('north',(0,1.25,0),(0,1,0))
    else:
        path=[(-1.25,0,0),(1.25,0,0)];p.port('west',path[0],(-1,0,0));p.port('east',path[1],(1,0,0))
    for sign in (-1,1):
        p.tube('insulated '+('hot supply' if sign>0 else 'cold return'),[Vector(x)+Vector((0,0,sign*.46)) for x in path],.355,'PaintedMetal_Darker',.075)
    for x in (-.70,.65) if not elbow else (-.7,):
        for z in (-.46,.46):p.tube('insulation clamp',((x-.06,0,z),(x+.06,0,z)),.405,'Metal_Dull',.055)
        foot=p.box('conduit stand',(x,0,-1.10),(.28,1.12,.22),'PaintedMetal_Colorable',.02)
        for y in (-.44,.44):p.box('clamp stand web',(x,y,-.06),(.20,.14,1.85),'PaintedMetal_Colorable',.012)


def tee(p):
    p.port('west',(-1.25,0,0),(-1,0,0));p.port('east',(1.25,0,0),(1,0,0));p.port('north',(0,1.25,0),(0,1,0))
    for z in (-.46,.46):p.branch_pipe('hollow tee channel',(-1.25,0,z),(1.25,0,z),[((0,0,z),(0,1.25,z))])
    for x in (-.6,.6):
        for z in (-.46,.46):p.tube('tee insulation clamp',((x-.06,0,z),(x+.06,0,z)),.405,'Metal_Dull',.055)
        p.box('tee mounting foot',(x,0,-1.10),(.28,1.12,.22),'PaintedMetal_Colorable')
        for y in (-.44,.44):p.box('tee mounting web',(x,y,-.06),(.20,.14,1.85),'PaintedMetal_Colorable')


def build(name,rebuild=False):
    instances=[]
    if rebuild:
        scene=bpy.data.scenes['Thermal / '+name];col=bpy.data.collections['Thermal model / '+name]
        assert col.get('thermal_concept')==name
        instances=[o for o in bpy.data.objects if o.instance_collection==col]
        bpy.context.window.scene=bpy.data.scenes['ArcanePower_ReactorPrototype']
        for obj in list(col.objects):bpy.data.objects.remove(obj,do_unlink=True)
        bpy.data.scenes.remove(scene);bpy.data.collections.remove(col)
    p=Parts(name)
    {'Brayton train':brayton,'Primary heater':heater,'Recuperator':recuperator,
     'Atmospheric cooler':rejector,'Space radiator':radiator,
     'Brayton train upgraded':lambda p:upgraded(p,brayton),
     'Primary heater upgraded':lambda p:upgraded(p,heater),
     'Recuperator upgraded':lambda p:upgraded(p,recuperator),
     'Duplex straight':lambda p:conduit(p),'Duplex elbow':lambda p:conduit(p,True),'Duplex tee':tee}[name](p)
    bpy.context.view_layer.update();report=p.finish()
    for obj in instances:obj.instance_collection=p.col
    path=OUT/'models.json';rows=json.loads(path.read_text()) if path.exists() else {};rows[name]=report;path.write_text(json.dumps(rows,indent=2)+'\n')
    return report


if __name__=='__main__':result=build(globals()['MODEL_NAME'])
