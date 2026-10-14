"""Author/export three-cell pillar storage and its three construction stages.
Run with the prototype .blend open; saves a separate energy-core .blend.
"""
import bpy, importlib, math, shutil, sys
from pathlib import Path
from mathutils import Matrix, Vector

ROOT=Path(__file__).resolve().parents[1]
COLS=importlib.import_module('space-engineers-utilities.seut_collections')
native={m.name:m for m in bpy.data.materials if m.library}
collision_template=next(o for o in bpy.data.objects if o.type=='MESH' and o.rigid_body)
materials=dict(native)
materials['GlassInside']=materials['GlassOutside']=bpy.data.materials['ArcanePower_ClearChamber']
for name in ['EnergyGlow']+['EnergyFill'+str(i) for i in range(1,5)]:
    material=native['Emissive'].copy();material.name=name;materials[name]=material
names=['ArcanePower_EnergyCore','ArcanePower_EnergyCapacity','ArcanePower_EnergyCapacityAdvanced',
       'ArcanePower_EnergyTransfer','ArcanePower_EnergyTransferAdvanced',
       'ArcanePower_EnergyStabilizer','ArcanePower_EnergyStabilizerAdvanced']
created=[]
# Use the exact same SEUT library part as the reactor; its mouth is 0.6804 m.
with bpy.data.libraries.load(str(Path.home()/'.local/share/blender-se1-setup/assets/Models/Common.blend'),link=False) as (source,target):
    target.objects=['Upgrade Port LG','Terminal LG','Terminal Screen']
parts=dict(zip(('Upgrade Port LG','Terminal LG','Terminal Screen'),target.objects))

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
        m=obj.modifiers.new('Machined edges','BEVEL');m.width=bevel;m.segments=2
        bpy.ops.object.modifier_apply(modifier=m.name)
        m=obj.modifiers.new('Normals','WEIGHTED_NORMAL');bpy.ops.object.modifier_apply(modifier=m.name)
    return finish(obj,name,mat,main,parent,stage)

def cylinder(name,pos,radius,depth,mat,main,parent,vertices=32,stage=2):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=radius,depth=depth,location=pos)
    return finish(bpy.context.object,name,mat,main,parent,stage)

def collision(cols,parent,pos,size):
    x,y,z=[v/2 for v in size]
    mesh=bpy.data.meshes.new('Energy collision')
    mesh.from_pydata([(pos[0]+a*x,pos[1]+b*y,pos[2]+c*z) for c in (-1,1) for b in (-1,1) for a in (-1,1)],[],
                    [(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)])
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
    build_stages(s)

def arc(name,radius,thickness,z,depth,start,end,mat,main,parent,stage=3):
    """Closed annular panel; segmented drums leave real maintenance seams."""
    steps=max(4,int(abs(end-start)*24));verts=[];faces=[]
    for i in range(steps+1):
        angle=start+(end-start)*i/steps
        for r,h in ((radius-thickness,z-depth/2),(radius,z-depth/2),(radius,z+depth/2),(radius-thickness,z+depth/2)):
            verts.append((r*math.cos(angle),r*math.sin(angle),h))
    for i in range(steps):
        for j in range(4):faces.append((4*i+j,4*i+(j+1)%4,4*(i+1)+(j+1)%4,4*(i+1)+j))
    faces += [(3,2,1,0),tuple(4*steps+j for j in range(4))]
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
    for face in mesh.polygons:face.use_smooth=mat.startswith('Glass') or (face.index<steps*4 and face.index%4 in (1,3))
    return obj

def ring(name,r,z,wire,mat,main,parent,stage=2):
    bpy.ops.mesh.primitive_torus_add(major_segments=64,minor_segments=8,major_radius=r,minor_radius=wire,location=(0,0,z))
    obj=finish(bpy.context.object,name,mat,main,parent,stage)
    for f in obj.data.polygons:f.use_smooth=True
    return obj

def native_part(key,name,pose,main,parent,stage=2):
    mesh=parts[key].data.copy();mesh.transform(pose)
    for i,mat in enumerate(mesh.materials):mesh.materials[i]=native.get(mat.name.split('.')[0],mat)
    obj=bpy.data.objects.new(name,mesh);main.objects.link(obj);obj.parent=parent
    obj['source_asset']='SEUT Common.blend / '+key;obj['build_stage']=stage
    return obj

def socket(label,center,normal,main,parent):
    # The native asset faces +Z and its lip lies at Z=1.2497. Preserve scale/UVs.
    rotation=Vector(normal).to_track_quat('Z','Y').to_matrix().to_4x4()
    pose=Matrix.Translation(center) @ rotation
    native_part('Upgrade Port LG',label+' / native upgrade port',pose @ Matrix.Translation((0,0,-1.25)),main,parent)
    # A recessed adapter made of four chamfered rails, leaving the port open.
    for x,y,w,h in ((0,-.56,1.45,.36),(0,.56,1.45,.36),(-.56,0,.36,.76),(.56,0,.36,.76)):
        obj=box(label+' / socket surround',(x,y,-.10),(w,h,.19),'PaintedMetal_Colorable',main,parent,2,.055)
        obj.matrix_world=pose @ obj.matrix_world
    for x in (-.56,.56):
        for y in (-.56,.56):
            obj=cylinder(label+' / captive bolt',(x,y,-.025),.045,.025,'Metal_Shiny',main,parent,8,3)
            obj.matrix_world=pose @ obj.matrix_world
    dummy=bpy.data.objects.new('detector_upgrade_'+label.replace(' / ','_').replace(' ','_'),None)
    main.objects.link(dummy);dummy.parent=parent
    dummy.matrix_world=pose @ Matrix.Translation((0,0,-.03));dummy.scale=(.7,.7,.08)
    dummy['purpose']='Native SE upgrade socket; preserve the whole-cell mating face'

def terminal(pos,normal,main,parent,label):
    rotation=Vector(normal).to_track_quat('Z','Y').to_matrix().to_4x4()
    pose=Matrix.Translation(pos) @ rotation
    for key in ('Terminal LG','Terminal Screen'):native_part(key,label+' / '+key,pose,main,parent,4)
    dummy=bpy.data.objects.new('detector_terminal',None);main.objects.link(dummy);dummy.parent=parent
    dummy.matrix_world=pose;dummy.scale=(.25,.50,.08)

s,cols,parent=scene(names[0]);main=cols['main'][0]
# Reactor-family chamber: rounded machinery drums, armor segments, machined lips,
# four structural spines and curved glazing around the restrained central field.
for x in (-2.65,2.65):
    for y in (-2.65,2.65):
        box('Energy / pillar',(x,y,0),(.42,.42,6.9),'Metal_Dull',main,parent,1,.08)
        collision(cols,parent,(x,y,0),(.42,.42,6.9))
        for z in (-2.55,2.55):
            box('Energy / spine shoulder',(x,y,z),(.72,.72,.8),'PaintedMetal_Colorable',main,parent,3,.16)
        for z in (-1.5,1.5):
            box('Energy / spine clamp',(x,y,z),(.53,.53,.13),'Metal_Shiny',main,parent,2,.03)
for z in (-3.22,3.22):
    cylinder('Energy / machinery drum',(0,0,z),3.48,.88,'PaintedMetal_Darker',main,parent,96,2)
    for i in range(12):
        a=i*math.tau/12
        arc('Energy / segmented drum armor',3.61,.13,z,.68,a+.025,a+math.tau/12-.025,'PaintedMetal_Colorable',main,parent)
        for dz in (-.22,.22):
            obj=cylinder('Energy / drum fastener',(0,0,0),.047,.035,'Metal_Shiny',main,parent,8,3)
            obj.location=(3.615*math.cos(a+.10),3.615*math.sin(a+.10),z+dz)
            obj.rotation_euler=Vector((math.cos(a+.10),math.sin(a+.10),0)).to_track_quat('Z','Y').to_euler()
    for dz in (-.46,.46):ring('Energy / machined perimeter',3.46,z+dz,.06,'Metal_Shiny',main,parent,3)
    cylinder('Energy / inner collar',(0,0,z-math.copysign(.68,z)),2.46,.30,'PaintedMetal_Darker',main,parent,64,2)
    ring('Energy / containment seat',2.45,z-math.copysign(.68,z),.07,'Metal_Shiny',main,parent)
    for r in (1.10,1.55,2.05):ring('Energy / induction winding',r,z-math.copysign(.80,z),.065,'Metal_Dull',main,parent)
    # The broad drum collision remains the existing accepted footprint.
    collision(cols,parent,(0,0,3.45 if z>0 else -3.45),(6.8,6.8,.5))
    for i in range(8):
        a=i*math.tau/8
        obj=box('Energy / radial service lid',(2.80*math.cos(a),2.80*math.sin(a),z+(.48 if z>0 else -.48)),(.65,.84,.07),'PaintedMetal_Darker',main,parent,3,.08)
        obj.rotation_euler.z=a
for i in range(4):
    a=i*math.pi/2
    # Native two-sided glass, with narrow open seams beneath the structural ribs.
    for mat in ('GlassOutside','GlassInside'):
        arc('Energy / chamber glazing',2.78,.008,0,4.60,a-.57,a+.57,mat,main,parent,4)
    for z in (-2.35,2.35):arc('Energy / glazing retainer',2.85,.12,z,.12,a-.60,a+.60,'Metal_Dull',main,parent)
    for side in (-1,1):
        angle=a+side*.60
        cylinder('Energy / coolant riser',(2.86*math.cos(angle),2.86*math.sin(angle),0),.075,4.7,'Metal_Shiny',main,parent,16,2)
# All four pillars stand upright. Old compact subtypes retain their saved definitions.
for label,center,normal in [('capacity left',(-3.75,0,0),(-1,0,0)),('capacity right',(3.75,0,0),(1,0,0)),('transfer',(0,-3.75,0),(0,-1,0)),('stabilizer',(0,3.75,0),(0,1,0))]:
    if normal[2]==0:
        # A narrow service spine carries the socket; the surrounding chamber stays glazed.
        pose=Matrix.Translation(center) @ Vector(normal).to_track_quat('Z','Y').to_matrix().to_4x4()
        for x in (-.58,.58):
            obj=box('Energy / socket support',(x,0,-.44),(.19,5.75,.20),'Metal_Dull',main,parent,2,.04)
            obj.matrix_world=pose @ obj.matrix_world
        obj=box('Energy / socket backing',(0,0,-.40),(1.55,1.65,.48),'PaintedMetal_Darker',main,parent,2,.12)
        obj.matrix_world=pose @ obj.matrix_world
    socket('Energy / '+label,center,normal,main,parent)
# The roof service console stays accessible with all four pillars mounted.
console_before=set(main.objects)
box('Energy / service console',(0,3.47,-3.20),(2.15,.31,.70),'PaintedMetal_VeryDark',main,parent,3,.09)
for i in range(1,5):box('Energy / fill indicator',(-.82+.36*(i-1),3.64,-3.19),(.24,.035,.12),'EnergyFill'+str(i),main,parent,4,.02)
terminal((.76,3.64,-3.17),(0,1,0),main,parent,'Energy')
console_pose=Matrix.Translation((0,-1.5,.09)) @ Matrix.Rotation(math.pi/2,4,'X')
for obj in set(main.objects)-console_before:obj.matrix_world=console_pose @ obj.matrix_world
dummy=bpy.data.objects.new('subpart_EnergyRotor',None);main.objects.link(dummy);dummy.parent=parent;dummy['file']='ArcanePower_EnergyRotor'

def pillar_cap(name,z,depth,main,parent,stage=3):
    # Rounded outer face and a concave inner face follow the chamber's curvature.
    # The complete pillar still occupies a full 1x3x1 grid volume.
    profile=[(1.15*math.cos(a),-.03+1.15*math.sin(a)) for a in [math.pi+i*math.pi/16 for i in range(17)]]
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
    # One unscaled SE port at the center, with full-height passive retaining rails.
    socket('Module / connector',(0,1.25,0),(0,1,0),main,parent)
    for z in (-2.3,0,2.3):
        back=arc('Module / curved saddle',3.75,.12,z,2.12,-math.pi/2-.305,-math.pi/2+.305,'PaintedMetal_Darker',main,parent,2)
        back.location.y=4.70
        for x in (-1.01,1.01):
            box('Module / side armor',(x,.12,z),(.22,1.84,1.96),'PaintedMetal_Colorable',main,parent,3,.09)
            for dz in (-.48,0,.48):box('Module / side vents',(x*1.12,.05,z+dz),(.025,1.22,.065),'PaintedMetal_VeryDark',main,parent,3,.015)
        box('Module / equipment backplane',(0,-.35,z),(1.8,.12,1.90),'PaintedMetal_VeryDark',main,parent,2,.06)
        for dz in (-1.02,1.02):
            box('Module / service crossrail',(0,-.84,z+dz),(1.90,.14,.12),'Metal_Dull',main,parent,3,.04)
        if 'Capacity' in name:
            for x in ((-.50,0,.50) if advanced else (-.39,.39)):
                radius=.18 if advanced else .25
                cylinder('Module / storage cell',(x,-.70,z),radius,1.75,'Metal_Shiny',main,parent,24,2)
                for dz in (-.72,0,.72):
                    obj=ring('Module / cell restraint',radius+.01,z+dz,.035,'PaintedMetal_Darker',main,parent)
                    obj.location.x=x;obj.location.y=-.70
        elif 'Transfer' in name:
            for x in (-.67,-.45,-.22,0,.22,.45,.67):
                box('Module / transfer heatsink',(x,-.77,z),(.075,.32,1.75),'Metal_Dull',main,parent,2,.025)
            for dz in ((-.60,0,.60) if advanced else (-.55,.55)):
                box('Module / power bus',(0,-.96,z+dz),(1.70,.06,.08),'Metal_Shiny',main,parent,3,.02)
        else:
            for radius in ((.27,.45,.63) if advanced else (.35,.61)):
                obj=ring('Module / field winding',radius,0,.055,'Metal_Shiny',main,parent)
                obj.rotation_euler.x=math.pi/2;obj.location.y=-.77;obj.location.z=z
            obj=cylinder('Module / field hub',(0,-.80,z),.18,.16,'PaintedMetal_Darker',main,parent,32,2)
            obj.rotation_euler.x=math.pi/2
            for x in (-.75,.75):box('Module / field vane',(x,-.80,z),(.12,.13,1.75),'Metal_Dull',main,parent,3,.025)
        for x in (-.91,.91):
            box('Module / front spine',(x,-.72,z),(.15,.23,1.97),'PaintedMetal_Colorable',main,parent,3,.05)
            for dz in (-.96,.96):
                obj=cylinder('Module / service bolt',(x,-.93,z+dz),.045,.03,'Metal_Shiny',main,parent,8,3);obj.rotation_euler.x=math.pi/2
    if 'Capacity' in name:
        for i in range(1,5):box('Module / fill',(-.57+.38*(i-1),-1.17,-3.47),(.24,.035,.075),'EnergyFill'+str(i),main,parent,4,.012)
    for x in ((-.22,.22) if advanced else (0,)):
        box('Module / tier lamp',(x,-1.17,3.47),(.26,.035,.065),'Emissive',main,parent,4,.01)
    collision(cols,parent,(0,0,0),(2.35,2.4,7.4))
    terminal((.0,-1.00,-1.15),(0,-1,0),main,parent,'Module')

s,cols,parent=scene('ArcanePower_EnergyRotor',True);main=cols['main'][0]
bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=16,radius=1.15)
orb=finish(bpy.context.object,'Energy / stored field','EnergyGlow',main,parent)
for p in orb.data.polygons:p.use_smooth=True
for tilt in (-.5,.5):
    bpy.ops.mesh.primitive_torus_add(major_segments=48,minor_segments=8,major_radius=2.0,minor_radius=.055)
    obj=bpy.context.object;obj.rotation_euler=(tilt,.2,0)
    finish(obj,'Energy / orbit','Metal_Shiny',main,parent)

for block_scene in created[:-1]:
    stages(block_scene,COLS.get_collections(block_scene),None)
    # SEUT mainScene exports Blender (-X, Z, Y). Rotate the authored assembly
    # so its module connector becomes SE Forward (-Z), and core transfer is rear.
    # Rotate parent roots once; independent build-stage meshes follow as well.
    for obj in block_scene.objects:
        if obj.parent is None:
            obj.matrix_world=Matrix.Rotation(math.pi,4,'Z') @ obj.matrix_world

# Save only the new asset family, preserving the reactor authoring file.
bpy.context.window.scene=created[0]
for old in list(bpy.data.scenes):
    if old not in created:bpy.data.scenes.remove(old)
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/arcane-energy-core.blend'))
setup=Path.home()/'.local/share/blender-se1-setup'
cache=Path.home()/'.cache/arcane-power/energy/MWMBuilder';shutil.copytree(setup/'assets/Tools/MWMBuilder',cache,dirs_exist_ok=True)
(cache/'MwmBuilder.exe.config').write_text('<configuration><system.diagnostics><trace><listeners><clear /></listeners></trace></system.diagnostics></configuration>')
bpy.context.preferences.addons['space-engineers-utilities'].preferences.mwmb_path=str(cache/'MwmBuilder.exe')
importlib.import_module('space-engineers-utilities.seut_errors').show_popup_report=lambda c,t,x:print(t,x,flush=True)
area=next(a for a in bpy.context.screen.areas if a.type=='VIEW_3D')
# Referenced rotor first, then each block with native stages and collision.
for s in created[-1:]+created[:-1]:
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
