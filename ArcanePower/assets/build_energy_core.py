"""Author/export three-cell pillar storage and its three construction stages.
Run with the prototype .blend open; saves a separate energy-core .blend.
"""
import bpy, bmesh, importlib, json, math, runpy, shutil, subprocess, sys
from pathlib import Path
from mathutils import Matrix, Vector

ROOT=Path(__file__).resolve().parents[1]
COLS=importlib.import_module('space-engineers-utilities.seut_collections')
native={m.name:m for m in bpy.data.materials if m.library}
collision_template=next(o for o in bpy.data.objects if o.type=='MESH' and o.rigid_body)
materials=dict(native)
materials['GlassInside']=materials['GlassOutside']=bpy.data.materials['ArcanePower_ClearChamber']
runpy.run_path(str(ROOT/'assets/tune_chamber_glass.py'))['apply']()
for name in ['EnergyGlow']+['EnergyFill'+str(i) for i in range(1,5)]:
    material=native['Emissive'].copy();material.name=name;materials[name]=material
# The field needs a continuous luminous surface, not the patterned lamp atlas.
# Use the same packed channels/export path as the existing plasma material.
texture_folder=ROOT/'src/Textures/Models/ArcanePower/Energy'
texture_folder.mkdir(parents=True,exist_ok=True)
texture_paths=[]
for node,suffix,rgba in [('CM','cm',(1,1,1,0)),('NG','ng',(.5,.5,1,.12)),('ADD','add',(1,1,0,0))]:
    img=bpy.data.images.new('EnergyField_'+suffix,width=16,height=16,alpha=True)
    if suffix!='cm':img.colorspace_settings.name='Non-Color'
    img.alpha_mode='CHANNEL_PACKED';img.pixels.foreach_set(list(rgba)*256)
    img.filepath_raw=str(texture_folder/('EnergyField_'+suffix+'.png'));img.file_format='PNG';img.save()
    materials['EnergyGlow'].node_tree.nodes[node].image=img;texture_paths.append(img.filepath_raw)
subprocess.run(['python3',str(ROOT/'tools/texture_conversion.py'),*texture_paths],check=True)
def emissive_preview(material,color,strength):
    # SE applies color in C#. Tint a private preview group without changing the
    # packed textures or native exporter nodes shared by the accepted reactor.
    node=material.node_tree.nodes['SEUT_NODE_GROUP']
    node.node_tree=node.node_tree.copy()
    group=node.node_tree
    group.links.new(group.nodes['Group Input'].outputs['Color Override'],group.nodes['Principled BSDF'].inputs['Emission Color'])
    node.inputs['Color Override'].default_value=color
    node.inputs['Color Override Alpha'].default_value=1
    node.inputs['Emission Strength'].default_value=strength

emissive_preview(materials['EnergyGlow'],(.035,.12,.65,1),.55)
# Continuous native packed emissive, independently controlled from the field.
materials['EnergyStatus']=materials['EnergyGlow'].copy();materials['EnergyStatus'].name='EnergyStatus'
emissive_preview(materials['EnergyStatus'],(.035,.35,.65,1),.7)

def label_material():
    """Native matte dark stock for white SEUT glyphs; preserve the native maps."""
    material=bpy.data.materials.get('BlackMattePlastic')
    if material is None:
        with bpy.data.libraries.load(str(Path.home()/'.local/share/blender-se1-setup/assets/Materials/Materials.blend'),link=True) as (source,target):
            target.materials=['BlackMattePlastic']
        material=target.materials[0]
    materials['EnergyLabel']=material
    return material

label_material()
names=['ArcanePower_EnergyCore','ArcanePower_EnergyCapacity','ArcanePower_EnergyCapacityAdvanced',
       'ArcanePower_EnergyTransfer','ArcanePower_EnergyTransferAdvanced',
       'ArcanePower_EnergyStabilizer','ArcanePower_EnergyStabilizerAdvanced']
created=[]
stage_reports={}
# Use the exact same SEUT library part as the reactor; its mouth is 0.6804 m.
with bpy.data.libraries.load(str(Path.home()/'.local/share/blender-se1-setup/assets/Models/Common.blend'),link=False) as (source,target):
    target.objects=['Upgrade Port LG','Terminal LG','Terminal Screen']
parts=dict(zip(('Upgrade Port LG','Terminal LG','Terminal Screen'),target.objects))
for part in parts.values():part['source_library']='Common.blend'
for library,keys in [('Decals/Atlas3.blend',('Tech Panel','Maintenance Box','Wire Vent','Tiedown Handle','Large Screw')),
                     ('Decals/ButtonsAtlas.blend',('Combined Panel','Button Emergency Stop')),
                     ('Decals/Atlas2.blend',('Sign Battery','Sign High Voltage','Sign Moving Parts')),
                     ('Decals/TextAtlas.blend',('C','T','S','P','W','R','F','A','N','1','2','3'))]:
    with bpy.data.libraries.load(str(Path.home()/'.local/share/blender-se1-setup/assets/Models'/library),link=False) as (source,target):
        target.objects=list(keys)
    parts.update(zip(keys,target.objects))
    for part in target.objects:part['source_library']=library

def scene(name, subpart=False):
    s=bpy.data.scenes.new(name);bpy.context.window.scene=s
    s.seut.sceneType='subpart' if subpart else 'mainScene'
    s.seut.subtypeId=name;s.seut.gridScale='large';s.seut.mod_path=str(ROOT/'src')
    bpy.ops.scene.recreate_collections()
    s.seut.export_sbc_type='none';s.seut.export_deleteLooseFiles=False
    s.seut.export_exportPath=str(ROOT/'src/Models/Cubes/large')
    s.seut.bBox_X=s.seut.bBox_Y=3 if name==names[0] else 1
    s.seut.bBox_Z=1 if subpart else 3
    cols=COLS.get_collections(s)
    parent=bpy.data.objects.new(name+' root',None);cols['main'][0].objects.link(parent)
    created.append(s)
    return s,cols,parent

def finish(obj,name,mat,main,parent,stage=2):
    obj.name=name;obj['build_stage']=stage
    for c in list(obj.users_collection):c.objects.unlink(obj)
    main.objects.link(obj);obj.parent=parent
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True)
    bpy.context.view_layer.objects.active=obj
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    obj.data.materials.append(materials[mat])
    # Stable box projection on the final geometry; native tiled industrial maps.
    uv=obj.data.uv_layers.get('UVMap') or obj.data.uv_layers.new(name='UVMap')
    for face in obj.data.polygons:
        axes=[i for i in range(3) if i!=max(range(3),key=lambda a:abs(face.normal[a]))]
        for loop in face.loop_indices:
            p=obj.data.vertices[obj.data.loops[loop].vertex_index].co
            uv.data[loop].uv=(p[axes[0]]*.4,p[axes[1]]*.4)
    return obj

def box(name,pos,size,mat,main,parent,stage=2,bevel=.025):
    bpy.ops.mesh.primitive_cube_add(size=1,location=pos)
    obj=bpy.context.object;obj.dimensions=size
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if bevel:
        m=obj.modifiers.new('Machined edges','BEVEL');m.width=bevel
        m.segments=1  # Structural edges use a flat chamfer, never a rounded fillet.
        bpy.ops.object.modifier_apply(modifier=m.name)
        m=obj.modifiers.new('Normals','WEIGHTED_NORMAL');bpy.ops.object.modifier_apply(modifier=m.name)
    return finish(obj,name,mat,main,parent,stage)

def cylinder(name,pos,radius,depth,mat,main,parent,vertices=32,stage=2):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=radius,depth=depth,location=pos)
    obj=finish(bpy.context.object,name,mat,main,parent,stage)
    uv=obj.data.uv_layers['UVMap']
    for face in obj.data.polygons:
        if abs(face.normal.z)>.5:continue
        face.use_smooth=True
        center=math.atan2(face.center.y,face.center.x)
        for index in face.loop_indices:
            p=obj.data.vertices[obj.data.loops[index].vertex_index].co
            angle=center+(math.atan2(p.y,p.x)-center+math.pi)%math.tau-math.pi
            uv.data[index].uv=(angle*radius*.4,p.z*.4)
    return obj

def status_strip(name,pose,main,parent):
    """40 mm lens in a chamfered bezel; local +Z faces away from its backing."""
    bezel=box(name+' bezel',(0,0,0),(.072,.82,.032),'PaintedMetal_VeryDark',main,parent,3,.008)
    lens=box(name+' lens',(0,0,.017),(.040,.74,.012),'EnergyStatus',main,parent,4,.004)
    for obj in (bezel,lens):obj.matrix_basis=pose @ obj.matrix_basis
    return bezel,lens

def pipe(name,start,end,radius,mat,main,parent,stage=2):
    start,end=Vector(start),Vector(end)
    obj=cylinder(name,(start+end)/2,radius,(end-start).length,mat,main,parent,16,stage)
    obj.rotation_euler=(end-start).to_track_quat('Z','Y').to_euler()
    return obj

def collision(cols,parent,pos=None,size=None,points=None):
    mesh=bpy.data.meshes.new('Energy collision')
    if points is None:
        x,y,z=[v/2 for v in size]
        mesh.from_pydata([(pos[0]+a*x,pos[1]+b*y,pos[2]+c*z) for c in (-1,1) for b in (-1,1) for a in (-1,1)],[],
                        [(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)])
    else:
        mesh.from_pydata(points,[],[])
        bm=bmesh.new();bm.from_mesh(mesh)
        hull=bmesh.ops.convex_hull(bm,input=list(bm.verts),use_existing_faces=False)
        unused=set(hull['geom_unused'])|set(hull['geom_interior'])
        if unused:bmesh.ops.delete(bm,geom=list(unused),context='VERTS')
        bm.to_mesh(mesh);bm.free()
    # SEUT also sends the collision FBX through MwmBuilder's wildcard pass.
    # Give it valid UVs even though that extra collision MWM is never shipped.
    uv=mesh.uv_layers.new(name='UVMap')
    for polygon in mesh.polygons:
        for index,point in zip(polygon.loop_indices,((0,0),(1,0),(1,1),(0,1))):uv.data[index].uv=point
    mesh.materials.append(native['Metal_Dull'])
    obj=collision_template.copy();obj.data=mesh;obj.name='Energy collision'
    if not cols['hkt']:
        col=bpy.data.collections.new('Collision - Main ('+bpy.context.scene.name+')');cols['seut'][0].children.link(col)
        col.seut.scene=bpy.context.scene;col.seut.col_type='hkt';col.seut.ref_col=cols['main'][0];col.seut.version=3
    else:col=cols['hkt'][0]
    col.objects.link(obj);obj.parent=parent;obj.matrix_basis=Matrix.Identity(4)
    obj.rigid_body.collision_shape='CONVEX_HULL';obj.hide_render=True

def stages(s,cols,parent):
    sys.path.insert(0,str(ROOT/'assets'))
    from build_construction_stages import build_stages
    stage_reports[s.name]=build_stages(s)

def arc(name,radius,thickness,z,depth,start,end,mat,main,parent,stage=3,segments=None):
    """Closed annular panel; segmented drums leave real maintenance seams."""
    steps=max(4,int(abs(end-start)*24) if segments is None else segments);verts=[];faces=[]
    for i in range(steps+1):
        angle=start+(end-start)*i/steps
        for r,h in ((radius-thickness,z-depth/2),(radius,z-depth/2),(radius,z+depth/2),(radius-thickness,z+depth/2)):
            verts.append((r*math.cos(angle),r*math.sin(angle),h))
    for i in range(steps):
        for j in range(4):faces.append((4*i+j,4*i+(j+1)%4,4*(i+1)+(j+1)%4,4*(i+1)+j))
    faces += [(3,2,1,0),tuple(4*steps+j for j in range(4))]
    # The sweep above follows its cross-section clockwise. Reverse every face:
    # inward outer walls previously exposed backs coincident with the drum.
    faces=[tuple(reversed(face)) for face in faces]
    if mat.startswith('Glass'):
        faces=[faces[i*4+1] for i in range(steps)]
        if mat=='GlassInside':faces=[tuple(reversed(face)) for face in faces]
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update()
    obj=bpy.data.objects.new(name,mesh);main.objects.link(obj)
    finish(obj,name,mat,main,parent,stage)
    if mat.startswith('Glass'):
        uv=mesh.uv_layers['UVMap']
        for loop in mesh.loops:
            index=loop.vertex_index
            uv.data[loop.index].uv=((index//4)/steps, 1 if index%4 in (2,3) else 0)
    else:
        uv=mesh.uv_layers['UVMap']
        for face in mesh.polygons:
            if face.index>=steps*4 or face.index%4 not in (1,3):continue
            for index in face.loop_indices:
                vertex=mesh.loops[index].vertex_index
                angle=start+(end-start)*(vertex//4)/steps
                p=mesh.vertices[vertex].co
                uv.data[index].uv=(angle*radius*.4,p.z*.4)
    for face in mesh.polygons:face.use_smooth=mat.startswith('Glass') or (face.index<steps*4 and face.index%4 in (1,3))
    return obj

def dock_housing(name,x,width,y,height,outer,main,parent):
    """Trapezoidal housing: full-width mounting face, narrow chamber face."""
    xs=[x-width/2+width*i/8 for i in range(9)]
    low,high=y-height/2,y+height/2
    ys=sorted(set([low,high]+[h for h in (-2.82,-2.50,2.50,2.82) if low<h<high]))
    vertices=[];faces=[];nx=len(xs);ny=len(ys);count=nx*ny
    for side in (0,1):
        for h in ys:
            # Recede the inner edge of upper/lower backplanes to open the view.
            inner_h=y+(h-y)*.78 if width>1 else h
            height=h if side else inner_h
            radius=2.70+.68*min(1,max(0,(abs(height)-2.50)/.32))
            for t in xs:
                tangent=t if side else t*.58
                vertices.append((tangent,height,outer if side else math.sqrt(radius*radius-tangent*tangent)-3.75))
    for j in range(ny-1):
        for i in range(nx-1):
            a=j*nx+i;b=a+1;c=b+nx;d=a+nx
            faces.extend([(a,d,c,b),(a+count,b+count,c+count,d+count)])
    border=list(range(nx))+[j*nx+nx-1 for j in range(1,ny)]+list(range(count-2,count-nx-1,-1))+[j*nx for j in range(ny-2,0,-1)]
    for a,b in zip(border,border[1:]+border[:1]):faces.append((a,b,b+count,a+count))
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(vertices,[],faces);mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
    obj=bpy.data.objects.new(name,mesh);main.objects.link(obj)
    return finish(obj,name,'PaintedMetal_Darker',main,parent,2)


def dock_crossmember(y,main,parent):
    obj=box('Energy / docking crossmember',(0,y,-.15),(1.66,.18,.26),'Metal_Dull',main,parent,2,.012)
    # Follow the sloping cheeks: 10 mm front reveal, >20 mm rear clearance.
    for v in obj.data.vertices:
        depth=(.13-v.co.z)/.26
        rear_width=1.10 if abs(y)>3 else 1.46
        v.co.x*=1-depth*(1-rear_width/1.66)
    obj.data.update()
    return obj


def fan_rotor(main,parent):
    """Six solid pitched blades; Blender -Y exports as native local Z."""
    before=set(main.objects)
    cylinder('Fan / rotor hub',(0,0,0),.15,.10,'Metal_Shiny',main,parent,32,2)
    profile=[(.12,-.05),(.43,-.15),(.55,-.09),(.55,.06),(.18,.10)]
    for i in range(6):
        # A pitched plate has visible thickness at engineer inspection distance.
        vertices=[(x,y,y*.38+h) for h in (-.012,.012) for x,y in profile]
        n=len(profile);faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]
        faces += [(j,(j+1)%n,(j+1)%n+n,j+n) for j in range(n)]
        mesh=bpy.data.meshes.new('Fan blade');mesh.from_pydata(vertices,[],faces);mesh.update()
        obj=bpy.data.objects.new('Fan / pitched blade',mesh);main.objects.link(obj)
        finish(obj,obj.name,'Metal_Dull',main,parent,2)
        obj.rotation_euler.z=i*math.tau/6
    for obj in set(main.objects)-before:
        obj.matrix_basis=Matrix.Rotation(math.pi/2,4,'X') @ obj.matrix_basis
    bpy.context.view_layer.update()


def ring(name,r,z,wire,mat,main,parent,stage=2):
    bpy.ops.mesh.primitive_torus_add(major_segments=64,minor_segments=8,major_radius=r,minor_radius=wire,location=(0,0,z))
    obj=finish(bpy.context.object,name,mat,main,parent,stage)
    for f in obj.data.polygons:f.use_smooth=True
    return obj

def native_part(key,name,pose,main,parent,stage=2):
    mesh=parts[key].data.copy();mesh.transform(pose)
    for i,mat in enumerate(mesh.materials):mesh.materials[i]=native.get(mat.name.split('.')[0],mat)
    obj=bpy.data.objects.new(name,mesh);main.objects.link(obj);obj.parent=parent
    obj['source_asset']='SEUT '+parts[key].get('source_library','Common.blend')+' / '+key;obj['build_stage']=stage
    return obj

def detail(key,pos,normal,main,parent,scale=1,angle=0):
    pose=Matrix.Translation(pos) @ Vector(normal).to_track_quat('Z','Y').to_matrix().to_4x4()
    return native_part(key,'Service / '+key,pose @ Matrix.Rotation(angle,4,'Z') @ Matrix.Scale(scale,4),main,parent,3)

def recess(target,pos,size,main,parent):
    cutter=box('Temporary service pocket',pos,size,'Metal_Dull',main,parent,bevel=.025)
    bpy.context.view_layer.update()
    modifier=target.modifiers.new('Recessed service hardware','BOOLEAN');modifier.operation='DIFFERENCE';modifier.solver='EXACT';modifier.object=cutter
    bpy.context.view_layer.objects.active=target;bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.data.objects.remove(cutter,do_unlink=True)

def bolt(pos,normal,main,parent):
    # Use the reactor's correctly mapped screw rather than a plain cylinder cap.
    detail('Large Screw',pos,normal,main,parent,.34)

def socket(label,center,normal,main,parent):
    # The native asset faces +Z and its lip lies at Z=1.2497. Preserve scale/UVs.
    rotation=Vector(normal).to_track_quat('Z','Y').to_matrix().to_4x4()
    pose=Matrix.Translation(center) @ rotation
    native_part('Upgrade Port LG',label+' / native upgrade port',pose @ Matrix.Translation((0,0,-1.25)),main,parent)
    socket_receiver(label,pose,main,parent)
    for x in (-.56,.56):
        for y in (-.56,.56):
            obj=cylinder(label+' / captive bolt',(x,y,-.025),.045,.025,'Metal_Shiny',main,parent,8,3)
            obj.matrix_world=pose @ obj.matrix_world
    dummy=bpy.data.objects.new('detector_upgrade_'+label.replace(' / ','_').replace(' ','_'),None)
    main.objects.link(dummy);dummy.parent=parent
    dummy.matrix_world=pose @ Matrix.Translation((0,0,-.03));dummy.scale=(.7,.7,.08)
    dummy['purpose']='Native SE upgrade socket; preserve the whole-cell mating face'

def socket_receiver(label,pose,main,parent):
    """Single clipped receiver and opaque rear closure around the native port."""
    def outline(w,c):return [(-w+c,-w),(w-c,-w),(w,-w+c),(w,w-c),(w-c,w),(-w+c,w),(-w,w-c),(-w,-w+c)]
    outer=outline(.73,.11);inner=outline(.355,.015)
    vertices=[(x,y,z) for z in (-.195,-.030) for loop in (outer,inner) for x,y in loop]
    faces=[]
    for i in range(8):
        j=(i+1)%8
        faces.extend([(i,j,8+j,8+i),(16+i,24+i,24+j,16+j),
                      (i,16+i,16+j,j),(8+i,8+j,24+j,24+i)])
    mesh=bpy.data.meshes.new('Closed native socket receiver');mesh.from_pydata(vertices,[],faces);mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
    obj=bpy.data.objects.new(label+' / integrated socket receiver',mesh);main.objects.link(obj)
    finish(obj,obj.name,'PaintedMetal_Colorable',main,parent,2);obj.matrix_basis=pose
    cap=box(label+' / opaque socket backing',(0,0,-.168),(.78,.78,.060),'PaintedMetal_Darker',main,parent,2,.012)
    cap.matrix_basis=pose @ cap.matrix_basis
    return obj,cap

def dock_root_fairing(normal,sign,main,parent):
    """Chamfered saddle: cylindrical seating face to the straight dock cheeks."""
    n=Vector(normal);t=Vector((-n.y,n.x,0))
    columns=17;rows=4;count=columns*rows;vertices=[];faces=[]
    for front,w,h,c in ((False,1.24,.30,.050),(True,1.08,.21,.040)):
        for height,width in ((-h,w-c),(-h+c,w),(h-c,w),(h,w-c)):
            for i in range(columns):
                x=-width+2*width*i/(columns-1);r=3.720 if front else math.sqrt(3.565**2-x*x)
                vertices.append(tuple(t*x+n*r+Vector((0,0,sign*3.22+height))))
    for offset in (0,count):
        for j in range(rows-1):
            for i in range(columns-1):
                a=offset+j*columns+i;faces.append((a,a+1,a+columns+1,a+columns))
    border=list(range(columns))+[j*columns+columns-1 for j in range(1,rows)]+list(range(count-2,count-columns-1,-1))+[j*columns for j in range(rows-2,0,-1)]
    faces.extend((a,b,b+count,a+count) for a,b in zip(border,border[1:]+border[:1]))
    mesh=bpy.data.meshes.new('Dock curved root fairing');mesh.from_pydata(vertices,[],faces);mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
    obj=bpy.data.objects.new('Energy / curved dock root',mesh);main.objects.link(obj)
    finish(obj,obj.name,'PaintedMetal_Colorable',main,parent,2);mesh.materials.append(materials['PaintedMetal_Darker'])
    for face in mesh.polygons:
        if (rows-1)*(columns-1)<=face.index<2*(rows-1)*(columns-1):face.material_index=1
    return obj

def dock_root_details(s,main,parent):
    if not s.name.endswith('Core') or s.get('dock_root_revision')==1:return
    bpy.context.window.scene=s;bpy.context.view_layer.update()
    for obj in [o for o in main.objects if o.name.startswith('Energy / curved dock root')]:bpy.data.objects.remove(obj,do_unlink=True)
    for normal in ((-1,0,0),(1,0,0),(0,-1,0),(0,1,0)):
        for sign in (-1,1):dock_root_fairing(normal,sign,main,parent)
    s['dock_root_revision']=1

def dock_integration_details(s,main,parent):
    """Repair existing main-model receivers without changing native port geometry."""
    if s.get('dock_integration_revision')==1:return
    bpy.context.window.scene=s;bpy.context.view_layer.update()
    for old in [o for o in list(main.objects) if any(k in o.name for k in (' / socket surround',' / integrated socket receiver',' / opaque socket backing'))]:bpy.data.objects.remove(old,do_unlink=True)
    for dummy in [o for o in main.objects if o.name.startswith('detector_upgrade')]:
        pose=dummy.matrix_basis.copy();pose.normalize();pose.translation+=pose.to_3x3() @ Vector((0,0,.03))
        socket_receiver('Energy' if s.name.endswith('Core') else 'Module',pose,main,parent)
    if s.name.endswith('Core'):
        for old in [o for o in list(main.objects) if o.name.startswith('Energy / dock backplane')]:bpy.data.objects.remove(old,do_unlink=True)
        for normal in ((-1,0,0),(1,0,0),(0,-1,0),(0,1,0)):
            pose=Matrix.Translation(Vector(normal)*3.75) @ Vector(normal).to_track_quat('Z','Y').to_matrix().to_4x4()
            for h in (-2.5,0,2.5):
                back=dock_housing('Energy / dock backplane',0,1.66,h,1.66,-.08,main,parent)
                recess(back,(0,h,-.12),(.74,.74,.24),main,parent);back.matrix_basis=pose @ back.matrix_basis
            for sign in (-1,1):dock_root_fairing(normal,sign,main,parent)
        s['dock_root_revision']=1
    for o in main.objects:
        if o.type=='MESH':
            for i,mat in enumerate(o.data.materials):
                if mat and mat.name=='EnergyLabel':o.data.materials[i]=materials['EnergyLabel']
    s['dock_integration_revision']=1

def dock_service_clearance(s,main,parent):
    """Keep drum maintenance stations clear of the four integrated dock roots."""
    if not s.name.endswith('Core') or s.get('dock_service_revision')==1:return
    doors=(30,60,135,210,240,315);vents=(45,116.5,153.5,225,296.5,333.5)
    rotations={i:Matrix.Rotation(math.radians((doors if i%2==0 else vents)[i//2])-(i*math.tau/12+.30),4,'Z') for i in range(12)}
    moved={}
    prefixes=('Energy / drum service gasket','Energy / drum access panel','Energy / drum cooling louver',
              'Energy / panel captive screw','Energy / panel pull','Marking / safety label backing','Marking / readable equipment')
    for obj in [o for o in main.objects if o.type=='MESH' and o.name.startswith(prefixes)]:
        center=sum((obj.matrix_basis @ v.co for v in obj.data.vertices),Vector())/len(obj.data.vertices)
        angle=math.atan2(center.y,center.x)
        station=min(range(12),key=lambda i:abs((angle-i*math.tau/12-.30+math.pi)%math.tau-math.pi))
        obj.matrix_basis=rotations[station] @ obj.matrix_basis;moved[obj.name]=rotations[station]
    for face in [o for o in main.objects if o.name.startswith('Detail / seated fastener face')]:
        rotation=moved.get(face.get('fastener_body'))
        if rotation is not None:face.matrix_basis=rotation @ face.matrix_basis
    s['dock_service_revision']=1

def native_label_details(s,main,parent):
    """Use the native dark stock after restoring the native glyph channels."""
    if s.get('native_label_revision')==1:return
    for obj in main.objects:
        if obj.type!='MESH':continue
        for i,mat in enumerate(obj.data.materials):
            if mat and mat.name in ('EnergyLabel','PlasticWhite'):obj.data.materials[i]=materials['EnergyLabel']
    s['native_label_revision']=1

def drum_service_seating(s,main,parent):
    """Inset both drums' service cassettes; keep screws on removable panels."""
    revision=s.get('drum_service_seating_revision',0)
    if not s.name.endswith('Core') or revision>=3:return
    bpy.context.window.scene=s;bpy.context.view_layer.update()
    stations=[]
    for gasket in [o for o in main.objects if o.name.startswith('Energy / drum service gasket' if revision<2 else 'Energy / inset service receiver')]:
        center=sum((gasket.matrix_basis @ v.co for v in gasket.data.vertices),Vector())/len(gasket.data.vertices)
        stations.append((math.atan2(center.y,center.x),center.z))
    assert len(stations)==24,'Expected both drums\' service stations'
    bolts={o.name for o in main.objects if o.name.startswith('Energy / drum fastener')}
    for obj in list(main.objects):
        if obj.name in bolts or obj.get('fastener_body') in bolts or obj.name.startswith(('Energy / drum service gasket','Energy / service cassette backing','Energy / inset service receiver','Energy / service pocket floor')):
            bpy.data.objects.remove(obj,do_unlink=True)

    def mesh_object(name,vertices,faces,material):
        mesh=bpy.data.meshes.new(name);mesh.from_pydata(vertices,[],faces);mesh.update()
        bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
        obj=bpy.data.objects.new(name,mesh);main.objects.link(obj)
        return finish(obj,name,material,main,parent,3)

    def outline(w,h,c):
        corners=[(-w+c,-h),(w-c,-h),(w,-h+c),(w,h-c),(w-c,h),(-w+c,h),(-w,h-c),(-w,-h+c)]
        return [(a[0]+(b[0]-a[0])*j/count,a[1]+(b[1]-a[1])*j/count)
                for i,(a,b) in enumerate(zip(corners,corners[1:]+corners[:1]))
                for count in [8 if i in (0,4) else 1] for j in range(count)]

    def point(angle,z,x,h,r):return (r*math.cos(angle+x/3.61),r*math.sin(angle+x/3.61),z+h)

    # The former 180 mm open segment gaps made cassettes bridge empty space.
    # Rebuild the skin with 14 mm seams before cutting the service apertures.
    for obj in [o for o in main.objects if o.name.startswith('Energy / segmented drum armor')]:bpy.data.objects.remove(obj,do_unlink=True)
    armor=[arc('Energy / segmented drum armor',3.61,.15,z,.68,i*math.tau/12+.002,(i+1)*math.tau/12-.002,'PaintedMetal_Colorable',main,parent)
           for z in (-3.22,3.22) for i in range(12)]
    for angle,z in stations:
        # Closed stepped receiver: a nearly flush painted rim, a real seating
        # ledge under the door/louver ends, and a floor sunk into the drum.
        outer=outline(.487,.225,.020);mouth=outline(.424,.188,.014);ledge=outline(.375,.155,.010)
        loops=[(3.611,outer),(3.611,mouth),(3.590,mouth),(3.590,ledge),(3.450,ledge),(3.450,outer)]
        vertices=[point(angle,z,x,h,r) for r,loop in loops for x,h in loop];count=len(outer)
        faces=[(k*count+i,k*count+(i+1)%count,((k+1)%len(loops))*count+(i+1)%count,((k+1)%len(loops))*count+i)
               for k in range(len(loops)) for i in range(count)]
        rim=mesh_object('Energy / inset service receiver',vertices,faces,'PaintedMetal_Colorable')
        for face in rim.data.polygons:
            face.use_smooth=face.index//count in (0,2)
        arc('Energy / service pocket floor',3.550,.100,z,.450,angle-.135,angle+.135,'PaintedMetal_VeryDark',main,parent,3,8)

        # Cut the actual armor, including stations which bridge an armor seam.
        vertices=[];faces=[];columns=12;rows=4;layer=columns*rows
        for r in (3.440,3.700):
            for h,w in ((-.188,.410),(-.174,.424),(.174,.424),(.188,.410)):
                vertices.extend(point(angle,z,-w+2*w*i/(columns-1),h,r) for i in range(columns))
        for offset in (0,layer):
            for j in range(rows-1):
                for i in range(columns-1):
                    a=offset+j*columns+i;faces.append((a,a+1,a+1+columns,a+columns))
        boundary=list(range(columns))+[j*columns+columns-1 for j in range(1,rows)]+list(range(layer-2,layer-columns-1,-1))+[j*columns for j in range(rows-2,0,-1)]
        faces.extend((a,b,b+layer,a+layer) for a,b in zip(boundary,boundary[1:]+boundary[:1]))
        cutter=mesh_object('Temporary service aperture',vertices,faces,'PaintedMetal_Colorable')
        for obj in armor:
            ps=[obj.matrix_basis @ v.co for v in obj.data.vertices]
            center=sum(ps,Vector())/len(ps)
            if abs(center.z-z)>.1 or abs((math.atan2(center.y,center.x)-angle+math.pi)%math.tau-math.pi)>.42:continue
            modifier=obj.modifiers.new('Inset service aperture','BOOLEAN');modifier.operation='DIFFERENCE';modifier.solver='EXACT';modifier.object=cutter
            bpy.context.view_layer.objects.active=obj;bpy.context.view_layer.update();bpy.ops.object.modifier_apply(modifier=modifier.name)
        bpy.data.objects.remove(cutter,do_unlink=True)

    # Keep native screw faces, pulls and lettering registered to their doors.
    moves={}
    prefixes=('Energy / panel captive screw','Energy / panel pull','Marking / safety label backing','Marking / readable equipment')
    for obj in [o for o in main.objects if revision<2 and o.type=='MESH' and o.name.startswith(prefixes)]:
        center=sum((obj.matrix_basis @ v.co for v in obj.data.vertices),Vector())/len(obj.data.vertices)
        angle,z=min(stations,key=lambda a:abs(a[1]-center.z)+abs((math.atan2(center.y,center.x)-a[0]+math.pi)%math.tau-math.pi))
        delta=Vector((-.022*math.cos(angle),-.022*math.sin(angle),0))
        obj.matrix_basis=Matrix.Translation(delta) @ obj.matrix_basis;moves[obj.name]=delta
    for face in [o for o in main.objects if o.name.startswith('Detail / seated fastener face')]:
        if face.get('fastener_body') in moves:face.matrix_basis=Matrix.Translation(moves[face['fastener_body']]) @ face.matrix_basis
    for obj in [o for o in main.objects if revision<2 and o.name.startswith(('Energy / drum access panel','Energy / drum cooling louver'))]:
        obj.data=obj.data.copy();inverse=obj.matrix_basis.inverted();shift=.022 if 'access panel' in obj.name else .032
        for vertex in obj.data.vertices:
            p=obj.matrix_basis @ vertex.co;r=math.hypot(p.x,p.y);p.x*=1-shift/r;p.y*=1-shift/r;vertex.co=inverse @ p
        obj.data.update()
    s['drum_service_seating_revision']=3

def terminal(pos,normal,main,parent,label):
    rotation=Vector(normal).to_track_quat('Z','Y').to_matrix().to_4x4()
    pose=Matrix.Translation(pos) @ rotation
    body=native_part('Terminal LG',label+' / Terminal LG',pose,main,parent,4)
    native_part('Terminal Screen',label+' / Terminal Screen',pose,main,parent,4)
    dummy=bpy.data.objects.new('detector_terminal',None);main.objects.link(dummy);dummy.parent=parent
    dummy.matrix_world=pose;dummy.scale=(.25,.50,.08)
    runpy.run_path(str(ROOT/'assets/build_control_access.py'))['highlight_terminal'](dummy,body)

def main_details(s,main,parent):
    """Engineer-scale service assemblies; finished meshes only."""
    if s.get('engineering_detail_revision')==1:return
    bpy.context.window.scene=s;bpy.context.view_layer.update()
    advanced=s.name.endswith('Advanced')
    def pose(pos,normal):
        n=Vector(normal);x=Vector((-n.y,n.x,0)) if abs(n.z)<.5 else Vector((1,0,0))
        m=Matrix((x,n.cross(x),n)).transposed().to_4x4();m.translation=pos
        return m
    def block(name,frame,position,size,material='PaintedMetal_Darker',chamfer=.006,stage=3):
        o=box(name,position,size,material,main,parent,stage,chamfer);o.matrix_basis=frame @ o.matrix_basis
        return o
    def screw(name,frame,position,radius=.022):
        o=cylinder(name,position,radius,.020,'Metal_Shiny',main,parent,8,3);o.matrix_basis=frame @ o.matrix_basis
        return o
    def cut(target,frame,size,depth):
        cutter=block('Temporary engineering pocket',frame,(0,0,depth),size,'Metal_Dull',.012)
        old=target.data
        if old.users>1:target.data=old.copy()
        bpy.context.view_layer.update()
        modifier=target.modifiers.new('Chamfered engineering recess','BOOLEAN');modifier.operation='DIFFERENCE';modifier.solver='EXACT';modifier.object=cutter
        bpy.context.view_layer.objects.active=target;bpy.ops.object.modifier_apply(modifier=modifier.name)
        for o in list(bpy.data.objects):
            if o.data==old:o.data=target.data
        bpy.data.objects.remove(cutter,do_unlink=True)
        if old.users==0:bpy.data.meshes.remove(old)
    def handle(name,frame,center):
        x,y,z=center
        for dx in (-.105,.105):block(name+' foot',frame,(x+dx,y,z),(.030,.055,.046),'Metal_Dull',.004)
        block(name+' grip',frame,(x,y,z+.0215),(.24,.040,.018),'Metal_Shiny',.004)
    def decal(key,frame,position,scale):
        native_part(key,'Service / '+key,frame @ Matrix.Translation(position) @ Matrix.Scale(scale,4),main,parent,3)
    if s.name=='ArcanePower_EnergyCore':
        for z in (-3.22,3.22):
            for i in range(12):
                a=i*math.tau/12
                # Curved backing follows the existing armor; every layer overlaps
                # its support while the visible panel seams remain open.
                arc('Energy / drum service gasket',3.617,.020,z,.44,a+.16,a+.44,'PaintedMetal_VeryDark',main,parent,3)
                if i%2==0:
                    arc('Energy / drum access panel',3.629,.022,z,.36,a+.185,a+.415,'PaintedMetal_Darker',main,parent,3)
                    for da in (.205,.395):
                        f=pose((3.633*math.cos(a+da),3.633*math.sin(a+da),z),(math.cos(a+da),math.sin(a+da),0))
                        for h in (-.115,.115):screw('Energy / panel captive screw',f,(0,h,0))
                    f=pose((3.629*math.cos(a+.30),3.629*math.sin(a+.30),z),(math.cos(a+.30),math.sin(a+.30),0))
                    handle('Energy / panel pull',f,(0,0,.013))
                else:
                    for h in (-.135,-.045,.045,.135):
                        arc('Energy / drum cooling louver',3.638,.025,z+h,.028,a+.185,a+.415,'Metal_Dull',main,parent,3)
            # Flush pull pockets and small captive screws on the radial deck lids.
            for lid in [o for o in list(main.objects) if o.name.startswith('Energy / radial service lid') and math.copysign(1,o.location.z)==math.copysign(1,z)]:
                sign=math.copysign(1,z);a=lid.rotation_euler.z
                f=Matrix.Translation(lid.location) @ Matrix.Rotation(a,4,'Z')
                if sign<0:f=f @ Matrix.Rotation(math.pi,4,'X')
                f=f @ Matrix.Translation((0,0,.035))
                cut(lid,f,(.31,.36,.055),-.018)
                block('Energy / deck pull recess',f,(0,0,-.039),(.28,.33,.012),'PaintedMetal_VeryDark',.008)
                for x in (-.11,.11):block('Energy / deck pull foot',f,(x,0,-.021),(.025,.045,.027),'Metal_Dull',.003)
                block('Energy / flush deck pull',f,(0,0,-.008),(.245,.040,.012),'Metal_Shiny',.003)
                for x in (-.245,.245):
                    for y in (-.32,.32):
                        # 14 mm total height fits under the 3.75 m block plane.
                        o=cylinder('Energy / deck captive screw',(x,y,.004),.020,.014,'Metal_Shiny',main,parent,8,3);o.matrix_basis=f @ o.matrix_basis
        # Outboard shoes tie risers into the drums without entering the glazing.
        for riser in [o for o in list(main.objects) if o.name.startswith('Energy / coolant riser')]:
            n=Vector((riser.location.x,riser.location.y,0)).normalized()
            for z in (-2.73,2.73):
                f=pose((n.x*2.94,n.y*2.94,z),n)
                block('Energy / coolant retaining shoe',f,(0,0,0),(.19,.22,.10),'Metal_Dull',.008)
                for y in (-.065,.065):screw('Energy / coolant shoe screw',f,(0,y,.055),.016)
        s['engineering_detail_revision']=1
        return
    # Replace three flat vent bars with an actual recessed cooling bank.
    for old in [o for o in list(main.objects) if o.name.startswith('Module / side vents')]:
        mesh=old.data
        for o in [o for o in list(bpy.data.objects) if o.data==mesh]:bpy.data.objects.remove(o,do_unlink=True)
        if mesh.users==0:bpy.data.meshes.remove(mesh)
    for armor in [o for o in list(main.objects) if o.name.startswith('Module / side armor')]:
        sign=math.copysign(1,armor.location.x);z=armor.location.z
        f=pose((sign*1.12,.10,z+.22),(sign,0,0))
        cut(armor,f,(.88,1.08,.10),-.035)
        block('Module / service pocket backing',f,(0,0,-.078),(.86,1.06,.018),'PaintedMetal_VeryDark',.012)
        block('Module / inset service door',f,(0,0,-.041),(.80,.99,.050),'PaintedMetal_Darker',.018)
        for x in (-.32,.32):
            for y in (-.40,.40):screw('Module / door captive screw',f,(x,y,-.009),.018)
        handle('Module / service pull',f,(.12,-.23,0))
        decal('Tech Panel' if 'Transfer' in s.name else 'Maintenance Box',f,(-.17,.16,-.014),.42)
        vent=pose((sign*1.12,.12,z-.75),(sign,0,0))
        cut(armor,vent,(1.22,.32,.085),-.0275)
        block('Module / cooling pocket backing',vent,(0,0,-.062),(1.20,.30,.014),'PaintedMetal_VeryDark',.008)
        for i in range(9):
            block('Module / intake fin',vent,(-.52+i*.13,0,-.030),(.034,.25,.065),'Metal_Dull',.004)
        for x in (-.56,.56):
            block('Module / cooling screw boss',vent,(x,0,-.025),(.07,.07,.066),'PaintedMetal_Darker',.004)
            screw('Module / cooling bank screw',vent,(x,0,.014),.016)
    for z in (-2.3,0,2.3):
        if 'Capacity' in s.name:
            for h in (-.66,.66):
                block('Module / cassette retention rail',Matrix.Identity(4),(0,-.99,z+h),(1.64,.08,.085),'PaintedMetal_Darker',.008)
                for x in ((-.50,0,.50) if advanced else (-.39,.39)):
                    block('Module / cell clamp saddle',Matrix.Identity(4),(x,-.93,z+h),(.16,.20,.10),'Metal_Dull',.008)
                    f=pose((x,-1.0325,z+h),(0,-1,0));screw('Module / cassette clamp bolt',f,(0,0,0),.020)
        elif 'Transfer' in s.name:
            for h in (-.78,.78):block('Module / heatsink header',Matrix.Identity(4),(0,-.77,z+h),(1.60,.40,.08),'PaintedMetal_Darker',.008)
            for x in (-.74,.74):
                pipe('Module / cooling manifold',(x,-.83,z-.80),(x,-.83,z+.80),.035,'Metal_Shiny',main,parent,3)
                for h in (-.69,.69):cylinder('Module / manifold hex union',(x,-.83,z+h),.055,.09,'Metal_Dull',main,parent,6,3)
                block('Module / manifold clamp',Matrix.Identity(4),(x,-.86,z),(.14,.12,.19),'PaintedMetal_Darker',.008)
            for h in ((-.60,0,.60) if advanced else (-.55,.55)):
                for x in (-.58,.58):
                    block('Module / bus insulator',Matrix.Identity(4),(x,-.93,z+h),(.16,.12,.18),'PaintedMetal_VeryDark',.008)
                    block('Module / bus terminal lug',Matrix.Identity(4),(x,-1.0025,z+h),(.10,.035,.10),'Metal_Shiny',.006)
                    screw('Module / bus terminal bolt',pose((x,-1.025,z+h),(0,-1,0)),(0,0,0),.020)
        else:
            # Flat-sided carrier plate, with a true circular intake opening.
            f=pose((0,-.81,z),(0,-1,0))
            carrier=block('Module / fan carrier',f,(0,0,0),(1.56,1.56,.10),'PaintedMetal_Darker',.075)
            cutter=cylinder('Temporary intake bore',(0,0,0),.69,.30,'Metal_Dull',main,parent,48,3);cutter.matrix_basis=f
            bpy.context.view_layer.update();modifier=carrier.modifiers.new('Fan intake bore','BOOLEAN');modifier.operation='DIFFERENCE';modifier.solver='EXACT';modifier.object=cutter
            bpy.context.view_layer.objects.active=carrier;bpy.ops.object.modifier_apply(modifier=modifier.name);bpy.data.objects.remove(cutter,do_unlink=True)
            for x in (-.62,.62):
                for y in (-.62,.62):screw('Module / fan carrier screw',f,(x,y,.057),.024)
            cap=cylinder('Module / fan hub cap',(0,0,0),.12,.018,'Metal_Dull',main,parent,8,3);cap.matrix_basis=pose((0,-.886,z),(0,-1,0))
            for i in range(3):
                a=i*math.tau/3;screw('Module / fan hub screw',pose((0,-.898,z),(0,-1,0)),(.07*math.cos(a),.07*math.sin(a),0),.010)
            if abs(z)<.01:
                # One common driver above the center fan leaves terminal access clear.
                block('Module / fan controller',Matrix.Identity(4),(0,-.89,.885),(.52 if advanced else .32,.20,.18),'PaintedMetal_VeryDark',.012)
                block('Module / fan controller lamp',Matrix.Identity(4),(.12 if advanced else .06,-.995,.885),(.06,.018,.026),'EnergyStatus',.003,4)
    s['engineering_detail_revision']=1

def profile_solid(name,outline,depth,mat,main,parent,pose,stage=3):
    """Extruded clipped profile; hard faces, no rounded structural corners."""
    n=len(outline)
    vertices=[(x,y,z) for z in (-depth/2,depth/2) for x,y in outline]
    faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]
    faces.extend((i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n))
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(vertices,[],faces);mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
    o=bpy.data.objects.new(name,mesh);main.objects.link(o);finish(o,name,mat,main,parent,stage);o.matrix_basis=pose
    return o


def refinement_details(s,main,parent):
    """Second main-only loop: layered forms, real joints, equipment identity."""
    if s.get('form_detail_revision')==1:return
    bpy.context.window.scene=s;bpy.context.view_layer.update()
    def frame(pos,normal):
        n=Vector(normal);x=Vector((-n.y,n.x,0)) if abs(n.z)<.5 else Vector((1,0,0))
        m=Matrix((x,n.cross(x),n)).transposed().to_4x4();m.translation=pos
        return m
    def block(name,f,pos,size,mat='PaintedMetal_Darker',chamfer=.006,stage=3):
        o=box(name,pos,size,mat,main,parent,stage,chamfer);o.matrix_basis=f @ o.matrix_basis
        return o
    def screw(name,f,pos,radius=.016):
        o=cylinder(name,pos,radius,.018,'Metal_Shiny',main,parent,8,3);o.matrix_basis=f @ o.matrix_basis
        return o
    def print_asset(key,f,pos,scale=1):
        vs=parts[key].data.vertices
        lo=Vector([min(v.co[i] for v in vs) for i in range(3)]);hi=Vector([max(v.co[i] for v in vs) for i in range(3)])
        center=(lo+hi)*scale/2+Vector(pos)
        block('Marking / safety label backing',f,(center.x,center.y,pos[2]-.002),((hi.x-lo.x)*scale+.018,(hi.y-lo.y)*scale+.018,.004),'EnergyLabel',.001)
        return native_part(key,'Marking / '+key,f @ Matrix.Translation(Vector(pos)+Vector((0,0,.0015))) @ Matrix.Scale(scale,4),main,parent,3)
    def text(code,f,pos,height=.075):
        # Preserve native glyph UVs; normalize height, not character aspect ratio.
        widths=[]
        for key in code:
            vs=parts[key].data.vertices
            widths.append((max(v.co.x for v in vs)-min(v.co.x for v in vs))*height/(max(v.co.y for v in vs)-min(v.co.y for v in vs)))
        width=sum(widths)+.018*(len(code)-1)
        block('Module / engraved ID tab',f,(pos[0]+width/2,pos[1],pos[2]-.002),(width+.035,height+.040,.008),'EnergyLabel',.002)
        cursor=pos[0]
        for key in code:
            mesh=parts[key].data
            lo=Vector([min(v.co[i] for v in mesh.vertices) for i in range(3)]);hi=Vector([max(v.co[i] for v in mesh.vertices) for i in range(3)])
            scale=height/(hi.y-lo.y)
            p=Matrix.Translation((cursor-lo.x*scale,pos[1]-(hi.y+lo.y)*scale/2,pos[2]+.0035)) @ Matrix.Scale(scale,4)
            native_part(key,'Marking / equipment code',f @ p,main,parent,3)
            cursor+=(hi.x-lo.x)*scale+.018
    def pocket(targets,f,size,offset):
        cutter=block('Temporary lift socket cutter',f,offset,size,'Metal_Dull',.012)
        bpy.context.view_layer.update()
        for target in targets:
            old=target.data
            if old.users>1:target.data=old.copy()
            m=target.modifiers.new('Recessed lift socket','BOOLEAN');m.operation='DIFFERENCE';m.solver='EXACT';m.object=cutter
            bpy.context.view_layer.objects.active=target;bpy.ops.object.modifier_apply(modifier=m.name)
            for user in list(bpy.data.objects):
                if user.data==old:user.data=target.data
            if old.users==0:bpy.data.meshes.remove(old)
        bpy.data.objects.remove(cutter,do_unlink=True)
    def relocate(o,local_delta):
        # Review transforms are refreshed separately by sync_energy_review.py.
        o.location+=Vector(local_delta);bpy.context.view_layer.update()
    if s.name=='ArcanePower_EnergyCore':
        for sign in (-1,1):
            for i in range(4):
                a=math.pi/4+i*math.pi/2
                radial=Vector((math.cos(a),math.sin(a),0));normal=Vector((0,0,-sign))
                f=Matrix((radial,normal.cross(radial),normal)).transposed().to_4x4();f.translation=radial*1.86+Vector((0,0,sign*2.405))
                outline=[(-.10,-.175),(-.065,-.21),(.065,-.21),(.10,-.175),(.10,.175),(.065,.21),(-.065,.21),(-.10,.175)]
                profile_solid('Energy / pole injector housing',outline,.16,'PaintedMetal_Darker',main,parent,f)
                nozzle=cylinder('Energy / pole injector nozzle',(0,0,.09),.065,.045,'Metal_Dull',main,parent,8,3);nozzle.matrix_basis=f @ nozzle.matrix_basis
                emitter=cylinder('Energy / pole injector emitter',(0,0,.114),.038,.010,'EnergyStatus',main,parent,16,4);emitter.matrix_basis=f @ emitter.matrix_basis
                for y in (-.135,.135):screw('Energy / pole injector screw',f,(0,y,.084),.013)
                pipe('Energy / injector coil feed',radial*1.94+Vector((0,0,sign*2.405)),radial*2.05+Vector((0,0,sign*2.405)),.020,'Metal_Shiny',main,parent,3)
        for z in (-3.22,3.22):
            for i in range(0,12,2):
                a=i*math.tau/12+.227
                f=frame((3.631*math.cos(a),3.631*math.sin(a),z),(math.cos(a),math.sin(a),0))
                print_asset('Sign High Voltage',f,(0,0,0),.65)
        s['form_detail_revision']=1
        return
    advanced=s.name.endswith('Advanced');capacity='Capacity' in s.name;transfer='Transfer' in s.name
    letter='C' if capacity else 'T' if transfer else 'S'
    sign_key='Sign Battery' if capacity else 'Sign High Voltage' if transfer else 'Sign Moving Parts'
    for cap in [o for o in list(main.objects) if o.name.startswith('Module / armored endcap')]:
        sign=math.copysign(1,sum(v.co.z for v in cap.data.vertices)/len(cap.data.vertices))
        # The endcap mesh stores its height in vertices, unlike ordinary boxes.
        f=frame((0,-.06,sign*3.70),(0,0,sign))
        outline=[(-.85,-.53),(-.70,-.68),(.70,-.68),(.85,-.53),(.85,.53),(.70,.68),(-.70,.68),(-.85,.53)]
        cover=profile_solid('Module / faceted end deck',outline,.028,'PaintedMetal_Darker',main,parent,f)
        pocket((cap,cover),f,(.58,.38,.10),(0,0,-.025))
        block('Module / lift socket backing',f,(0,0,-.070),(.555,.355,.020),'PaintedMetal_VeryDark',.008)
        for x in (-.20,.20):block('Module / lift anchor foot',f,(x,0,-.030),(.035,.10,.085),'Metal_Dull',.004)
        block('Module / recessed lift bar',f,(0,0,.005),(.435,.065,.020),'Metal_Shiny',.004)
        for x in (-.66,.66):
            block('Module / end load rib',f,(x,0,.018),(.055,1.0,.022),'Metal_Dull',.005)
        for x in (-.54,.54):
            for y in (-.52,.52):screw('Module / end deck screw',f,(x,y,.020),.018)
        # Bolted front bezel has enough depth for the lamps to be seated.
        front=frame((0,-1.1875,sign*3.47),(0,-1,0))
        block('Module / end status bezel',front,(0,0,0),(1.58,.28,.035),'PaintedMetal_VeryDark',.015)
        for x in (-.70,.70):
            for y in (-.07,.07):screw('Module / end bezel screw',front,(x,y,.0225),.014)
        if sign>0:
            print_asset(sign_key,front,(-.55,0,.019),.85 if capacity else .52 if transfer else .34)
            text(letter+('2' if advanced else '1'),front,(.47,0,.019),.075)
        elif not capacity:
            text('PWR' if transfer else 'FAN',front,(-.16,0,.019),.085)
    for o in list(main.objects):
        if o.name.startswith(('Module / tier lamp','Module / fill')):relocate(o,(0,-.0425,0))
    for z in (-2.3,0,2.3):
        for sx in (-1,1):
            for sz in (-1,1):
                f=frame((sx*.90,-.944,z+sz*1.02),(0,-1,0))
                outline=[(0,-sz*.22),(0,-sz*.012),(-sx*.012,0),(-sx*.22,0),(-sx*.22,-sz*.025),(-sx*.025,-sz*.22)]
                profile_solid('Module / bay corner gusset',outline,.060,'Metal_Dull',main,parent,f)
                screw('Module / gusset captive screw',f,(-sx*.058,-sz*.058,.035),.014)
    for armor in [o for o in main.objects if o.name.startswith('Module / side armor')]:
        sx=math.copysign(1,armor.location.x);bay=armor.location.z
        f=frame((sx*1.12,.10,bay+.22),(sx,0,0))
        print_asset(sign_key,f,(.18,.16,-.014),1.05 if capacity else .67 if transfer else .40)
        text(str(int(round(bay/2.3))+2),f,(-.25,-.23,-.014),.10)
    s['form_detail_revision']=1

def cell_clamp_details(s,main,parent):
    """Replace toroidal retainers with split, bolted, flat-section metal bands."""
    if 'Capacity' not in s.name or s.get('cell_clamp_revision')==1:return
    bpy.context.window.scene=s;bpy.context.view_layer.update()
    for old in [o for o in list(main.objects) if o.name.startswith('Module / cell restraint')]:
        mesh=old.data
        for o in [o for o in list(bpy.data.objects) if o.data==mesh]:bpy.data.objects.remove(o,do_unlink=True)
        if mesh.users==0:bpy.data.meshes.remove(mesh)
    advanced=s.name.endswith('Advanced');radius=.18 if advanced else .25
    for bay in (-2.3,0,2.3):
        for x in ((-.50,0,.50) if advanced else (-.39,.39)):
            for h in (-.72,0,.72):
                for start in (-math.pi/2,math.pi/2):
                    band=arc('Module / split cell band',radius+.035,.040,bay+h,.045,start+.035,start+math.pi-.035,'Metal_Dull',main,parent,3,segments=12)
                    band.location=(x,-.70,0)
                for side in (-1,1):
                    y=-.70+side*(radius+.020)
                    box('Module / clamp bridge',(x,y,bay+h),(.13,.060,.090),'PaintedMetal_Darker',main,parent,3,.006)
                    bolt=cylinder('Module / split clamp bolt',(x,-.70+side*(radius+.054),bay+h),.014,.018,'Metal_Shiny',main,parent,8,3)
                    bolt.rotation_euler.x=math.pi/2
    s['cell_clamp_revision']=1

def fan_guard_details(s,main,parent):
    """Engineer-scale flat grille rings and spokes, separate from rotating blades."""
    if 'Stabilizer' not in s.name or s.get('fan_guard_revision')==1:return
    bpy.context.window.scene=s;bpy.context.view_layer.update()
    for old in [o for o in list(main.objects) if o.name.startswith(('Module / field winding','Module / grille support'))]:
        mesh=old.data
        for o in [o for o in list(bpy.data.objects) if o.data==mesh]:bpy.data.objects.remove(o,do_unlink=True)
        if mesh.users==0:bpy.data.meshes.remove(mesh)
    for bay in (-2.3,0,2.3):
        for radius in ((.27,.45,.63) if s.name.endswith('Advanced') else (.35,.61)):
            vertices=[];faces=[];segments=48
            for i in range(segments):
                angle=i*math.tau/segments
                for r,y in ((radius-.011,-.783),(radius+.011,-.783),(radius+.011,-.757),(radius-.011,-.757)):
                    vertices.append((r*math.cos(angle),y,bay+r*math.sin(angle)))
            for i in range(segments):
                for j in range(4):faces.append((4*i+j,4*i+(j+1)%4,4*((i+1)%segments)+(j+1)%4,4*((i+1)%segments)+j))
            mesh=bpy.data.meshes.new('Module / flat grille ring');mesh.from_pydata(vertices,[],faces);mesh.update()
            bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
            o=bpy.data.objects.new('Module / flat grille ring',mesh);main.objects.link(o);finish(o,o.name,'Metal_Dull',main,parent,3)
        for i in range(8):
            a=i*math.tau/8
            o=box('Module / flat grille spoke',(.445*math.cos(a),-.77,bay+.445*math.sin(a)),(.55,.034,.014),'Metal_Dull',main,parent,3,.003)
            o.rotation_euler.y=-a
    s['fan_guard_revision']=1

def fastener_face_details(s,main,parent):
    """Native normal-mapped captive screw faces seated on existing 3D heads."""
    bpy.context.window.scene=s;bpy.context.view_layer.update()
    prefixes=('Module / split clamp bolt','Module / gusset captive screw',
              'Module / cell terminal stud',
              'Module / service bolt','Module / cassette clamp bolt','Module / bus terminal bolt',
              'Module / cooling bank screw','Module / fan hub screw','Module / connector / captive bolt',
              'Module / connector lower / captive bolt','Module / connector upper / captive bolt',
              'Energy / drum fastener','Energy / coolant shoe screw','Energy / pole injector screw',
              'Energy / capacity left / captive bolt','Energy / capacity right / captive bolt',
              'Energy / transfer / captive bolt','Energy / stabilizer / captive bolt',
              'Module / end deck screw','Module / end bezel screw','Module / fan carrier screw','Module / heat exchanger mount bolt',
              'Module / door captive screw','Energy / panel captive screw','Energy / deck captive screw')
    template=parts['Large Screw'].data
    native_width=max(v.co.x for v in template.vertices)-min(v.co.x for v in template.vertices)
    decorated={o.get('fastener_body') for o in main.objects if o.name.startswith('Detail / seated fastener face')}
    for body in [o for o in list(main.objects) if o.type=='MESH' and o.name.startswith(prefixes)]:
        if body.name in decorated:continue
        radius=max(abs(v.co.x) for v in body.data.vertices)
        depth=max(v.co.z for v in body.data.vertices)
        reverse=body.name.startswith('Module / split clamp bolt') and body.location.y>-.70
        axis=Vector((0,0,-1 if reverse else 1))
        normal=body.matrix_basis.to_3x3() @ axis
        point=body.matrix_basis @ Vector((0,0,(-depth-.0005) if reverse else (depth+.0005)))
        pose=Matrix.Translation(point) @ normal.to_track_quat('Z','Y').to_matrix().to_4x4() @ Matrix.Scale(radius*2*.82/native_width,4)
        face=native_part('Large Screw','Detail / seated fastener face',pose,main,parent,3)
        face['fastener_body']=body.name
    s['fastener_face_revision']=1

def equipment_mount_details(s,main,parent):
    """Close the backplane-to-rail joint and mount transfer fins to a heat spreader."""
    if s.name=='ArcanePower_EnergyCore' or s.get('equipment_mount_revision')==1:return
    bpy.context.window.scene=s;bpy.context.view_layer.update()
    for old in [o for o in list(main.objects) if o.name.startswith('Module / equipment backplane')]:
        new=box('Temporary seated backplane',(0,-.35,old.location.z),(1.80,.16,1.90),'PaintedMetal_VeryDark',main,parent,2,.020)
        previous=old.data
        for user in [u for u in list(bpy.data.objects) if u.data==previous]:user.data=new.data
        bpy.data.objects.remove(new,do_unlink=True)
        if previous.users==0:bpy.data.meshes.remove(previous)
    if 'Transfer' in s.name:
        for old in [o for o in list(main.objects) if o.name.startswith('Module / transfer heatsink')]:
            previous=old.data
            for user in [u for u in list(bpy.data.objects) if u.data==previous]:bpy.data.objects.remove(user,do_unlink=True)
            if previous.users==0:bpy.data.meshes.remove(previous)
        advanced=s.name.endswith('Advanced');count=21 if advanced else 15;pitch=1.40/(count-1)
        for bay in (-2.3,0,2.3):
            box('Module / thermal spreader',(0,-.49,bay),(1.56,.18,1.80),'Metal_Dull',main,parent,2,.012)
            for i in range(count):
                box('Module / radiator fin',(-.70+i*pitch,-.76,bay),(.020 if advanced else .024,.38,1.72),'Metal_Dull',main,parent,3,.003)
            for x in (-.73,.73):
                for h in (-.78,.78):
                    o=cylinder('Module / heat exchanger mount bolt',(x,-.974,bay+h),.018,.018,'Metal_Shiny',main,parent,8,3);o.rotation_euler.x=math.pi/2
    s['equipment_mount_revision']=1

def connection_details(s,main,parent):
    """Finish actual cell, cooling and motor connections at engineer scale."""
    if s.name.endswith('Core') or s.get('connection_detail_revision')==1:return
    bpy.context.window.scene=s;bpy.context.view_layer.update()
    advanced=s.name.endswith('Advanced')
    if 'Capacity' in s.name:
        for old in [o for o in list(main.objects) if o.name.startswith('Module / cell bus link')]:
            bpy.data.objects.remove(old,do_unlink=True)
        for bay in (-2.3,0,2.3):
            for x in ((-.50,0,.50) if advanced else (-.39,.39)):
                for sign in (-1,1):
                    box('Module / plated cell strap',(x,-.32,bay+sign*.915),(.10,.82,.040),'Metal_Shiny',main,parent,3,.004)
                    cylinder('Module / terminal washer',(x,-.70,bay+sign*.939),.058,.012,'Metal_Dull',main,parent,8,3)
                    stud=cylinder('Module / cell terminal stud',(x,-.70,bay+sign*.947),.033,.020,'Metal_Shiny',main,parent,8,3)
                    if sign<0:stud.rotation_euler.x=math.pi
    elif 'Transfer' in s.name:
        for bay in (-2.3,0,2.3):
            for x in (-.74,.74):
                for sign in (-1,1):
                    pipe('Module / manifold return',(x,-.83,bay+sign*.69),(x,-.55,bay+sign*.69),.023,'Metal_Shiny',main,parent,3)
                    union=cylinder('Module / return hex union',(x,-.585,bay+sign*.69),.043,.07,'Metal_Dull',main,parent,6,3)
                    union.rotation_euler.x=math.pi/2
                valve=cylinder('Module / coolant valve body',(x,-.895,bay+.27),.047,.16,'Metal_Dull',main,parent,6,3)
                valve.rotation_euler.x=math.pi/2
                box('Module / valve handle',(x,-.980,bay+.27),(.12,.026,.028),'PaintedMetal_Darker',main,parent,3,.004)
    else:
        pipe('Module / fan cable trunk',(.80,-.45,-2.3),(.80,-.45,2.3),.014,'PaintedMetal_VeryDark',main,parent,3)
        pipe('Module / controller cable',(.23 if advanced else .13,-.89,.885),(.80,-.89,.885),.014,'PaintedMetal_VeryDark',main,parent,3)
        pipe('Module / controller return',(.80,-.89,.885),(.80,-.45,.885),.014,'PaintedMetal_VeryDark',main,parent,3)
        for bay in (-2.3,0,2.3):
            pipe('Module / motor lead',(.80,-.45,bay),(.11,-.45,bay),.014,'PaintedMetal_VeryDark',main,parent,3)
            box('Module / harness saddle',(.80,-.445,bay),(.07,.055,.10),'Metal_Dull',main,parent,3,.004)
    s['connection_detail_revision']=1

def surface_clearances(s,main,parent):
    """Seat adjoining parts at distinct depths without moving native sockets.

    Also applies to an existing main scene; derived geometry is rebuilt afterward.
    Coordinates below are in the authored root frame, before the SE orientation.
    """
    if s.get('surface_clearance_revision')==1:return
    bpy.context.window.scene=s;bpy.context.view_layer.update()
    meshes=[o for o in main.objects if o.type=='MESH']
    def matching(prefix):return [o for o in meshes if o.name.startswith(prefix)]
    def reshape(obj,change):
        obj.data=obj.data.copy()
        inverse=obj.matrix_basis.inverted()
        for vertex in obj.data.vertices:
            p=obj.matrix_basis @ vertex.co
            change(p)
            vertex.co=inverse @ p
        obj.data.update()
    def local_scale(obj,axis,factor):
        obj.data=obj.data.copy()
        for vertex in obj.data.vertices:vertex.co[axis]*=factor
        obj.data.update()
    def move(obj,delta):
        obj.location+=Vector(delta)
        for face in meshes:
            if face.get('fastener_body')==obj.name:face.location+=Vector(delta)
    if s.name.endswith('Core'):
        for obj in matching('Energy / curved dock root'):
            ps=[obj.matrix_basis @ v.co for v in obj.data.vertices]
            center=sum(ps,Vector())/len(ps);n=Vector((center.x,center.y,0)).normalized()
            def recess_face(p):
                if p.dot(n)>3.719:p-=n*.015
            reshape(obj,recess_face)
        stations=[]
        for obj in matching('Energy / inset service receiver'):
            ps=[obj.matrix_basis @ v.co for v in obj.data.vertices]
            center=sum(ps,Vector())/len(ps)
            stations.append((math.atan2(center.y,center.x),center.z))
        for obj in matching('Energy / segmented drum armor'):
            ps=[obj.matrix_basis @ v.co for v in obj.data.vertices]
            anchor=math.atan2(ps[0].y,ps[0].x)
            angles=[anchor+(math.atan2(p.y,p.x)-anchor+math.pi)%math.tau-math.pi for p in ps]
            low,high=min(angles),max(angles)
            def open_aperture(p):
                r=math.hypot(p.x,p.y);angle=math.atan2(p.y,p.x)
                for a,z in stations:
                    x=((angle-a+math.pi)%math.tau-math.pi)*3.61;h=p.z-z
                    if abs(x)<.425 and abs(h)<.189:
                        angle=a+x*(.430/.424)/3.61
                        angle=anchor+(angle-anchor+math.pi)%math.tau-math.pi
                        angle=max(low,min(high,angle))
                        p.x=r*math.cos(angle);p.y=r*math.sin(angle);p.z=z+h*(.193/.188)
                        break
            reshape(obj,open_aperture)
        for obj in matching('Energy / service pocket floor'):
            ps=[obj.matrix_basis @ v.co for v in obj.data.vertices]
            center=sum(ps,Vector())/len(ps);a=math.atan2(center.y,center.x)
            def inset_floor(p):
                r=math.hypot(p.x,p.y);angle=a+((math.atan2(p.y,p.x)-a+math.pi)%math.tau-math.pi)*.94
                if r<3.451:r-=.005
                p.x=r*math.cos(angle);p.y=r*math.sin(angle);p.z=center.z+(p.z-center.z)*.94
            reshape(obj,inset_floor)
        for obj in matching('Energy / panel pull grip'):local_scale(obj,0,.93)
    else:
        for obj in matching('Module / perimeter trim'):
            local_scale(obj,0,.99);local_scale(obj,1,.99)
        for obj in matching('Module / front spine'):local_scale(obj,2,2.12/2.14)
        for obj in matching('Module / service crossrail'):move(obj,(0,.008,0))
        for obj in matching('Module / armored endcap'):
            def widen_lift_pocket(p):
                if abs(p.x)<.301 and abs(p.y+.06)<.201 and abs(p.z)>3.60:
                    p.x*=.296/.29;p.y=-.06+(p.y+.06)*(.196/.19)
            reshape(obj,widen_lift_pocket)
        for obj in matching('Module / cell clamp saddle')+matching('Module / cassette clamp bolt'):move(obj,(0,-.006,0))
        for obj in matching('Module / recessed lift bar'):local_scale(obj,0,.96)
        for obj in matching('Module / service pull grip'):local_scale(obj,0,.93)
        for obj in matching('Module / radiator fin'):
            def seat_fin(p):
                if p.y>-.58:p.y=-.56+(p.y+.57)
            reshape(obj,seat_fin)
        for obj in matching('Module / return hex union'):local_scale(obj,2,.086/.07)
    s['surface_clearance_revision']=1


def readable_equipment_markings(s,main,parent):
    """Use matte-backed native text where chrome-like safety decals disappear."""
    if s.get('readable_marking_revision')==1:return
    for old in [o for o in list(main.objects) if o.name.startswith(('Marking / Sign High Voltage','Marking / Sign Moving Parts'))]:
        code='PWR' if 'High Voltage' in old.name else 'FAN'
        points=[old.matrix_basis @ v.co for v in old.data.vertices]
        n=old.matrix_basis.to_3x3() @ old.data.polygons[0].normal
        x=Vector((-n.y,n.x,0)).normalized();y=n.cross(x)
        frame=Matrix((x,y,n)).transposed().to_4x4();frame.translation=sum(points,Vector())/len(points)
        width=max(p.dot(x) for p in points)-min(p.dot(x) for p in points)
        height=max(p.dot(y) for p in points)-min(p.dot(y) for p in points)
        glyphs=[]
        for key in code:
            vs=parts[key].data.vertices
            lo=Vector([min(v.co[i] for v in vs) for i in range(3)]);hi=Vector([max(v.co[i] for v in vs) for i in range(3)])
            glyphs.append((key,lo,hi,(hi.x-lo.x)/(hi.y-lo.y)))
        h=min(height*.72,width/(sum(g[3] for g in glyphs)+.36))
        cursor=-h*(sum(g[3] for g in glyphs)+.36)/2
        for key,lo,hi,ratio in glyphs:
            scale=h/(hi.y-lo.y)
            pose=frame @ Matrix.Translation((cursor-lo.x*scale,-(lo.y+hi.y)*scale/2,-lo.z*scale)) @ Matrix.Scale(scale,4)
            native_part(key,'Marking / readable equipment',pose,main,parent,3)
            cursor+=ratio*h+.18*h
        bpy.data.objects.remove(old,do_unlink=True)
    s['readable_marking_revision']=1

s,cols,parent=scene(names[0]);main=cols['main'][0]
# Reactor-family chamber: rounded machinery drums, armor segments, machined lips
# and curved glazing around the restrained central field.
for z in (-3.22,3.22):
    cylinder('Energy / machinery drum',(0,0,z),3.48,.94,'PaintedMetal_Darker',main,parent,96,2)
    for i in range(12):
        a=i*math.tau/12
        arc('Energy / segmented drum armor',3.61,.15,z,.68,a+.002,a+math.tau/12-.002,'PaintedMetal_Colorable',main,parent)
    # Short straight strips on the chamber-facing collar, seated 8 mm into it.
    for i in range(4):
        a=math.pi/4+i*math.pi/2
        normal=Vector((0,0,-math.copysign(1,z)))
        radial=Vector((math.cos(a),math.sin(a),0))
        pose=Matrix((radial,normal.cross(radial),normal)).transposed().to_4x4()
        pose.translation=(2.21*math.cos(a),2.21*math.sin(a),math.copysign(2.452,z))
        status_strip('Energy / collar status',pose,main,parent)
    for dz in (-.46,.46):ring('Energy / machined perimeter',3.46,z+dz,.06,'Metal_Shiny',main,parent,3)
    cylinder('Energy / inner collar',(0,0,z-math.copysign(.61,z)),2.46,.30,'PaintedMetal_Darker',main,parent,64,2)
    ring('Energy / containment seat',2.45,z-math.copysign(.68,z),.07,'Metal_Shiny',main,parent)
    for r in (1.10,1.55,2.05):ring('Energy / induction winding',r,z-math.copysign(.80,z),.065,'Metal_Dull',main,parent)
    # The broad drum collision remains the existing accepted footprint.
    collision(cols,parent,(0,0,3.45 if z>0 else -3.45),(6.8,6.8,.5))
    for i in range(8):
        a=i*math.tau/8
        obj=box('Energy / radial service lid',(2.80*math.cos(a),2.80*math.sin(a),z+(.48 if z>0 else -.48)),(.65,.84,.07),'PaintedMetal_Darker',main,parent,3,.08)
        obj.rotation_euler.z=a
# Flush service deck: concentric panel seams, cooling slots and a bolted hatch.
for sign in (-1,1):
    z=sign*3.70
    cylinder('Energy / central service hatch',(0,0,z),1.06,.055,'PaintedMetal_VeryDark',main,parent,64,3)
    ring('Energy / hatch seal',1.07,z,.026,'Metal_Shiny',main,parent,3)
    for i in range(12):
        a=i*math.tau/12
        cylinder('Energy / hatch bolt',(.94*math.cos(a),.94*math.sin(a),z+sign*.03),.035,.025,'Metal_Shiny',main,parent,8,3)
        if sign>0 and 1<=i<=4:continue  # Keep the native service console clear.
        arc('Energy / deck panel',2.55,1.28,z,.035,a+.035,a+math.tau/12-.035,'PaintedMetal_Darker',main,parent)
        for r in (2.03,2.17,2.31):
            arc('Energy / recessed cooling slot',r,.055,z+sign*.025,.015,a+.10,a+math.tau/12-.10,'PaintedMetal_VeryDark',main,parent)
for i in range(4):
    a=i*math.pi/2
    # Four adjoining quadrants close the two-sided glass around the chamber.
    for mat in ('GlassOutside','GlassInside'):
        arc('Energy / chamber glazing',2.78,.008,0,5.60,a-math.pi/4,a+math.pi/4,mat,main,parent,4)
    for z in (-2.79,2.79):arc('Energy / glazing retainer',2.85,.12,z,.12,a-math.pi/4,a+math.pi/4,'Metal_Dull',main,parent)
    for side in (-1,1):
        angle=a+side*.60
        cylinder('Energy / coolant riser',(2.86*math.cos(angle),2.86*math.sin(angle),0),.075,5.60,'Metal_Shiny',main,parent,16,2)
# All four pillars stand upright. Old compact subtypes retain their saved definitions.
for label,center,normal in [('capacity left',(-3.75,0,0),(-1,0,0)),('capacity right',(3.75,0,0),(1,0,0)),('transfer',(0,-3.75,0),(0,-1,0)),('stabilizer',(0,3.75,0),(0,1,0))]:
    # The inner wall follows radius 2.70: an 80 mm intrusion through the glass.
    # Its mating plane stays 20 mm inside the cell face; the native port is unscaled.
    pose=Matrix.Translation(center) @ Vector(normal).to_track_quat('Z','Y').to_matrix().to_4x4()
    dock_before=set(main.objects)
    for x in (-.98,.98):
        dock_housing('Energy / dock sidewall',x,.28,0,7.0,-.02,main,parent)
    for y in (-2.08,2.08):
        back=dock_housing('Energy / dock backplane',0,1.66,y,2.48,-.08,main,parent)
        recess(back,(0,math.copysign(2.5,y),-.12),(.74,.74,.24),main,parent)
    # Small recessed pads seat each native surround into the tapered cheeks.
    for h in (-2.5,0,2.5):
        for x in (-.75,.75):
            for dy in (-.56,.56):
                box('Energy / dock mating pad',(x,h+dy,-.10),(.24,.16,.12),'Metal_Dull',main,parent,2,.008)
    for y in (-3.40,-1.15,1.15,3.40):
        dock_crossmember(y,main,parent)
    for obj in set(main.objects)-dock_before:
        obj.matrix_world=pose @ obj.matrix_world
    bpy.context.view_layer.update()
    hull_parts=[o for o in set(main.objects)-dock_before if o.name.startswith(('Energy / dock sidewall','Energy / dock backplane'))]
    collision(cols,parent,points=[o.matrix_world @ v.co for o in hull_parts for v in o.data.vertices])
    for h,suffix in ((-2.5,' lower'),(0,''),(2.5,' upper')):
        socket('Energy / '+label+suffix,Vector(center)+Vector((0,0,h)),normal,main,parent)
# The roof service console stays accessible with all four pillars mounted.
console_before=set(main.objects)
box('Energy / service console',(0,3.47,-3.20),(2.15,.31,.70),'PaintedMetal_VeryDark',main,parent,3,.09)
for i in range(1,5):box('Energy / fill indicator',(-.82+.36*(i-1),3.64,-3.19),(.24,.035,.12),'EnergyFill'+str(i),main,parent,4,.02)
terminal((.76,3.64,-3.17),(0,1,0),main,parent,'Energy')
console_pose=Matrix.Translation((0,-1.5,.09)) @ Matrix.Rotation(math.pi/2,4,'X')
for obj in set(main.objects)-console_before:obj.matrix_world=console_pose @ obj.matrix_world
dummy=bpy.data.objects.new('subpart_EnergyRotor',None);main.objects.link(dummy);dummy.parent=parent;dummy['file']='ArcanePower_EnergyRotor'
for i,source in enumerate(('ArcanePower_Ring3','ArcanePower_Ring4'),1):
    dummy=bpy.data.objects.new('subpart_EnergyRing'+str(i),None)
    main.objects.link(dummy);dummy.parent=parent;dummy['file']=source

def pillar_cap(name,z,depth,main,parent,stage=3):
    # Flat outer faces and clipped corners; the inner face follows the chamber.
    # The complete pillar still occupies a full 1x3x1 grid volume.
    profile=[(-1.15,-.88),(-.85,-1.18),(.85,-1.18),(1.15,-.88)]
    profile += [(x,.95+3.75-math.sqrt(3.75**2-x*x)) for x in [1.15-i*2.30/16 for i in range(17)]]
    count=len(profile);verts=[(x,y,h) for h in (z-depth/2,z+depth/2) for x,y in profile]
    faces=[tuple(reversed(range(count))),tuple(range(count,count*2))]
    faces += [(i,(i+1)%count,(i+1)%count+count,i+count) for i in range(count)]
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update()
    obj=bpy.data.objects.new(name,mesh);main.objects.link(obj)
    return finish(obj,name,'PaintedMetal_Colorable',main,parent,stage)

for name in names[1:]:
    s,cols,parent=scene(name);main=cols['main'][0]
    advanced=name.endswith('Advanced')
    for x in (-.96,.96):
        for y in (-.78,.78):box('Module / frame',(x,y,0),(.17,.17,6.95),'Metal_Dull',main,parent,1,.04)
    for z in (-3.47,3.47):
        pillar_cap('Module / armored endcap',z,.45,main,parent)
        pillar_cap('Module / perimeter trim',z*.94,.10,main,parent,2)
    for x in (-.94,.94):
        cylinder('Module / coolant spine',(x,.70,0),.065,6.60,'Metal_Shiny',main,parent,16,2)
    # Full-height backing and inter-bay bulkheads remove the hollow gap behind
    # the equipment. Pads mate with the core's dock across the grid-face seam.
    for x in (-.97,.97):
        box('Module / rear retaining rail',(x,1.17,0),(.20,.12,6.76),'Metal_Dull',main,parent,2,.025)
    for z in (-3.25,-1.15,1.15,3.25):
        box('Module / compartment bulkhead',(0,.18,z),(1.94,1.98,.18),'PaintedMetal_Darker',main,parent,2,.035)
    for x in (-.48,.48):
        box('Module / vertical power bus',(x,.42,0),(.16,.22,6.48),'Metal_Shiny',main,parent,2,.035)
    # One native connector per occupied grid cell; never scale the port asset.
    for h,suffix in ((-2.5,' lower'),(0,''),(2.5,' upper')):
        socket('Module / connector'+suffix,(0,1.25,h),(0,1,0),main,parent)
    for z in (-2.3,0,2.3):
        back=arc('Module / curved saddle',3.75,.12,z,2.12,-math.pi/2-.305,-math.pi/2+.305,'PaintedMetal_Darker',main,parent,2)
        back.location.y=4.70
        if z:
            plate=box('Module / mating backplate',(0,1.15,z),(1.78,.16,2.20),'PaintedMetal_Darker',main,parent,2,.045)
            recess(plate,(0,1.15,math.copysign(2.5,z)),(.74,.36,.74),main,parent)
        else:
            # Keep the native connector mouth open in the middle compartment.
            for x in (-.77,.77):box('Module / port backplate',(x,1.15,0),(.24,.16,1.80),'PaintedMetal_Darker',main,parent,2,.035)
            for h in (-.99,.99):box('Module / port backplate',(0,1.15,h),(1.78,.16,.22),'PaintedMetal_Darker',main,parent,2,.035)
        for x in (-.75,.75):
            box('Module / equipment mount',(x,.34,z),(.20,1.24,1.74),'Metal_Dull',main,parent,2,.035)
        for dz in (-.84,.84):
            box('Module / compartment bus',(0,-.02,z+dz),(1.66,.76,.14),'Metal_Shiny',main,parent,2,.035)
        for x in (-1.01,1.01):
            box('Module / side armor',(x,.12,z),(.22,1.84,2.14),'PaintedMetal_Colorable',main,parent,3,.025)
            for dz in (-.48,0,.48):box('Module / side vents',(x*1.12,.05,z+dz),(.025,1.22,.065),'PaintedMetal_VeryDark',main,parent,3,.015)
        box('Module / equipment backplane',(0,-.35,z),(1.8,.16,1.90),'PaintedMetal_VeryDark',main,parent,2,.02)
        for dz in (-1.02,1.02):
            box('Module / service crossrail',(0,-.92,z+dz),(1.90,.10,.12),'Metal_Dull',main,parent,3,.012)
        if 'Capacity' in name:
            for x in ((-.50,0,.50) if advanced else (-.39,.39)):
                radius=.18 if advanced else .25
                cylinder('Module / storage cell',(x,-.70,z),radius,1.75,'Metal_Shiny',main,parent,24,2)
                for dz in (-.88,.88):
                    cylinder('Module / cell contact',(x,-.70,z+dz),radius*.68,.09,'PaintedMetal_VeryDark',main,parent,16,2)
                    pipe('Module / cell bus link',(x,-.70,z+dz),(x,.12,z+dz),.055,'Metal_Shiny',main,parent)
                for dz in (-.72,0,.72):
                    obj=ring('Module / cell restraint',radius+.01,z+dz,.035,'PaintedMetal_Darker',main,parent)
                    obj.location.x=x;obj.location.y=-.70
        elif 'Transfer' in name:
            for x in (-.67,-.45,-.22,0,.22,.45,.67):
                box('Module / transfer heatsink',(x,-.77,z),(.075,.32,1.75),'Metal_Dull',main,parent,2,.025)
            for dz in ((-.60,0,.60) if advanced else (-.55,.55)):
                box('Module / power bus',(0,-.97,z+dz),(1.78,.06,.08),'Metal_Shiny',main,parent,3,.008)
        else:
            obj=cylinder('Module / fan bearing',(0,-.51,z),.13,.22,'Metal_Dull',main,parent,24,2);obj.rotation_euler.x=math.pi/2
            for angle in (0,math.pi/2,math.pi,3*math.pi/2):
                pipe('Module / grille support',(.14*math.cos(angle),-.77,z+.14*math.sin(angle)),(.68*math.cos(angle),-.77,z+.68*math.sin(angle)),.018,'Metal_Dull',main,parent,2)
            dummy=bpy.data.objects.new('subpart_EnergyFan'+str(int(round(z/2.3))+2),None);main.objects.link(dummy);dummy.parent=parent
            dummy['file']='ArcanePower_EnergyFan';dummy.location=(0,-.61,z)
            for radius in ((.27,.45,.63) if advanced else (.35,.61)):
                obj=ring('Module / field winding',radius,0,.055,'Metal_Shiny',main,parent)
                obj.rotation_euler.x=math.pi/2;obj.location.y=-.77;obj.location.z=z
            obj=cylinder('Module / field hub',(0,-.80,z),.18,.16,'PaintedMetal_Darker',main,parent,32,2)
            obj.rotation_euler.x=math.pi/2
            for x in (-.75,.75):box('Module / field vane',(x,-.80,z),(.12,.13,1.75),'Metal_Dull',main,parent,3,.025)
        for x in (-.91,.91):
            box('Module / front spine',(x,-.78,z),(.16,.38,2.14),'PaintedMetal_Colorable',main,parent,3,.012)
            pose=Matrix.Translation((x,-.974,z)) @ Matrix.Rotation(math.pi/2,4,'X')
            status_strip('Module / spine status',pose,main,parent)
            for dz in (-1.02,1.02):
                obj=cylinder('Module / service bolt',(x,-.9775,z+dz),.025,.025,'Metal_Shiny',main,parent,8,3);obj.rotation_euler.x=math.pi/2
    if 'Capacity' in name:
        for i in range(1,5):box('Module / fill',(-.57+.38*(i-1),-1.17,-3.47),(.24,.035,.075),'EnergyFill'+str(i),main,parent,4,.012)
    for x in ((-.22,.22) if advanced else (0,)):
        box('Module / tier lamp',(x,-1.17,3.47),(.26,.035,.065),'EnergyStatus',main,parent,4,.01)
    collision(cols,parent,(0,0,0),(2.35,2.4,7.4))
    box('Module / terminal mounting plate',(0,-.88,-1.15),(.42,.22,.58),'PaintedMetal_Darker',main,parent,3,.012)
    terminal((.0,-1.00,-1.15),(0,-1,0),main,parent,'Module')

s,cols,parent=scene('ArcanePower_EnergyRotor',True);main=cols['main'][0]
bpy.ops.mesh.primitive_uv_sphere_add(segments=64,ring_count=32,radius=1.15)
orb=finish(bpy.context.object,'Energy / stored field','EnergyGlow',main,parent)
for p in orb.data.polygons:p.use_smooth=True

s,cols,parent=scene('ArcanePower_EnergyFan',True);fan_rotor(cols['main'][0],parent)

for block_scene in [s for s in created if s.seut.sceneType=='mainScene']:
    block_cols=COLS.get_collections(block_scene);main=block_cols['main'][0]
    main_details(block_scene,main,next(o for o in main.objects if o.parent is None))
    refinement_details(block_scene,main,next(o for o in main.objects if o.parent is None))
    cell_clamp_details(block_scene,main,next(o for o in main.objects if o.parent is None))
    fan_guard_details(block_scene,main,next(o for o in main.objects if o.parent is None))
    equipment_mount_details(block_scene,main,next(o for o in main.objects if o.parent is None))
    connection_details(block_scene,main,next(o for o in main.objects if o.parent is None))
    readable_equipment_markings(block_scene,main,next(o for o in main.objects if o.parent is None))
    dock_integration_details(block_scene,main,next(o for o in main.objects if o.parent is None))
    dock_root_details(block_scene,main,next(o for o in main.objects if o.parent is None))
    dock_service_clearance(block_scene,main,next(o for o in main.objects if o.parent is None))
    native_label_details(block_scene,main,next(o for o in main.objects if o.parent is None))
    drum_service_seating(block_scene,main,next(o for o in main.objects if o.parent is None))
    fastener_face_details(block_scene,main,next(o for o in main.objects if o.parent is None))
    surface_clearances(block_scene,main,next(o for o in main.objects if o.parent is None))
    if block_scene.name=='ArcanePower_EnergyCore':
        runpy.run_path(str(ROOT/'assets/build_control_access.py'))['apply_energy'](block_scene)
    stages(block_scene,COLS.get_collections(block_scene),None)
    # SEUT mainScene exports Blender (-X, Z, Y). Rotate the authored assembly
    # so its module connector becomes SE Forward (-Z), and core transfer is rear.
    # Rotate parent roots once; independent build-stage meshes follow as well.
    for obj in block_scene.objects:
        if obj.parent is None:
            obj.matrix_world=Matrix.Rotation(math.pi,4,'Z') @ obj.matrix_world

from audit_energy_geometry import main as audit_geometry
import runpy
runpy.run_path(str(ROOT/'assets/detail_native_textures.py'))['main']()
audit_geometry()

# Save only the new asset family, preserving the reactor authoring file.
(ROOT/'validation/energy-construction-source.json').write_text(json.dumps({
    'style':'SE channel frames, diagonal webs, exposed equipment, partial cladding',
    'source':stage_reports,'exported':False,'live_game_checked':False},indent=2)+'\n')
bpy.context.window.scene=created[0]
for old in list(bpy.data.scenes):
    if old not in created and old.name not in ('ArcanePower_Ring3','ArcanePower_Ring4'):bpy.data.scenes.remove(old)
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/arcane-energy-core.blend'))
setup=Path.home()/'.local/share/blender-se1-setup'
cache=Path.home()/'.cache/arcane-power/energy/MWMBuilder';shutil.copytree(setup/'assets/Tools/MWMBuilder',cache,dirs_exist_ok=True)
(cache/'MwmBuilder.exe.config').write_text('<configuration><system.diagnostics><trace><listeners><clear /></listeners></trace></system.diagnostics></configuration>')
bpy.context.preferences.addons['space-engineers-utilities'].preferences.mwmb_path=str(cache/'MwmBuilder.exe')
importlib.import_module('space-engineers-utilities.seut_errors').show_popup_report=lambda c,t,x:print(t,x,flush=True)
area=next(a for a in bpy.context.screen.areas if a.type=='VIEW_3D')
# Referenced rotor first, then each block with native stages and collision.
for s in [s for s in created if s.seut.sceneType=='subpart']+[s for s in created if s.seut.sceneType=='mainScene']:
    bpy.context.window.scene=s
    # SEUT only propagates the main hull if no stale stage HKT files exist.
    for stage in range(1,4):
        (ROOT/'src/Models/Cubes/large'/(s.name+'_BS'+str(stage)+'.hkt')).unlink(missing_ok=True)
    # Hidden stage collections can evaluate as the main mesh in Blender 5.
    # Keep them visible during FBX evaluation, as export_construction_stages does.
    def show_stages(layer):
        if layer.collection.seut.col_type=='bs':
            layer.hide_viewport=False;layer.collection.hide_render=False
        for child in layer.children:show_stages(child)
    show_stages(bpy.context.view_layer.layer_collection)
    bpy.context.view_layer.update()
    with bpy.context.temp_override(area=area,region=next(r for r in area.regions if r.type=='WINDOW')):
        result=bpy.ops.scene.export()
        if 'FINISHED' not in result:raise RuntimeError('Energy export failed: '+s.name)
    (ROOT/'src/Models/Cubes/large'/(s.name+'.hkt.mwm')).unlink(missing_ok=True)
    print('EXPORTED',s.name,flush=True)
print('Saved/exported three-cell storage family and construction stages',flush=True)
