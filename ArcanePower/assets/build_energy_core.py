"""Author/export compact modular storage and its three construction stages.
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
for name in ['EnergyGlow']+['EnergyFill'+str(i) for i in range(1,5)]:
    material=native['Emissive'].copy();material.name=name;materials[name]=material
names=['ArcanePower_EnergyCore','ArcanePower_EnergyCapacity','ArcanePower_EnergyCapacityAdvanced',
       'ArcanePower_EnergyTransfer','ArcanePower_EnergyTransferAdvanced',
       'ArcanePower_EnergyStabilizer','ArcanePower_EnergyStabilizerAdvanced']
created=[]

def scene(name, subpart=False):
    s=bpy.data.scenes.new(name);bpy.context.window.scene=s
    s.seut.sceneType='subpart' if subpart else 'mainScene'
    s.seut.subtypeId=name;s.seut.gridScale='large';s.seut.mod_path=str(ROOT/'src')
    bpy.ops.scene.recreate_collections()
    s.seut.export_sbc_type='none';s.seut.export_deleteLooseFiles=False
    s.seut.export_exportPath=str(ROOT/'src/Models/Cubes/large')
    s.seut.bBox_X=s.seut.bBox_Y=s.seut.bBox_Z=3 if name==names[0] else 1
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

s,cols,parent=scene(names[0]);main=cols['main'][0]
# Four posts and rim rails form the first build stage.
for x in (-2.65,2.65):
    for y in (-2.65,2.65):
        box('Energy / pillar',(x,y,0),(.42,.42,6.9),'Metal_Dull',main,parent,1)
        collision(cols,parent,(x,y,0),(.42,.42,6.9))
for z in (-3.45,3.45):
    for x in (-2.65,2.65):box('Energy / frame rail',(x,0,z),(.18,5.5,.18),'Metal_Dull',main,parent,1)
    for y in (-2.65,2.65):box('Energy / frame rail',(0,y,z),(5.5,.18,.18),'Metal_Dull',main,parent,1)
    cylinder('Energy / octagonal housing',(0,0,z),3.65,.5,'PaintedMetal_Colorable',main,parent,8,3)
    cylinder('Energy / inner collar',(0,0,z*.81),2.3,.32,'PaintedMetal_Darker',main,parent,48,2)
    collision(cols,parent,(0,0,z),(6.8,6.8,.5))
for x in (-1,1):
    box('Energy / side capacity port',(x*3.64,0,0),(.20,1.5,1.5),'PaintedMetal_Darker',main,parent,2)
    for y in (-.48,.48):box('Energy / side bus',(x*3.52,y,0),(.12,.12,5.3),'Metal_Shiny',main,parent,2)
box('Energy / rear transfer port',(0,-3.64,0),(1.5,.20,1.5),'PaintedMetal_Darker',main,parent,2)
box('Energy / top stabilizer port',(0,0,3.66),(1.5,1.5,.12),'PaintedMetal_Darker',main,parent,3)
for z in (-3.3,3.3):
    for x in (-2,-1,0,1,2):box('Energy / panel seam',(x,3.35,z),(.045,.06,.3),'Metal_Dull',main,parent,3)
for i in range(1,5):box('Energy / fill indicator',(-.9+.6*(i-1),3.58,-3.1),(.4,.06,.17),'EnergyFill'+str(i),main,parent,4)
terminal=bpy.data.objects.new('detector_terminal',None);main.objects.link(terminal);terminal.parent=parent;terminal.location=(0,3.62,-2.95);terminal.scale=(1,.1,.4)
dummy=bpy.data.objects.new('subpart_EnergyRotor',None);main.objects.link(dummy);dummy.parent=parent;dummy['file']='ArcanePower_EnergyRotor'
stages(s,cols,parent)

for name in names[1:]:
    s,cols,parent=scene(name);main=cols['main'][0]
    advanced=name.endswith('Advanced')
    for x in (-1.08,1.08):
        for y in (-1.08,1.08):box('Module / frame',(x,y,0),(.12,.12,2.3),'Metal_Dull',main,parent,1)
    for z in (-1.1,1.1):
        for x in (-1.08,1.08):box('Module / rail',(x,0,z),(.12,2.2,.12),'Metal_Dull',main,parent,1)
        for y in (-1.08,1.08):box('Module / rail',(0,y,z),(2.2,.12,.12),'Metal_Dull',main,parent,1)
    box('Module / chassis',(0,0,0),(2.18,1.7,2.18),'PaintedMetal_Darker',main,parent,2,.07)
    box('Module / connector',(0,1.16,0),(1.45,.16,1.45),'Metal_Shiny',main,parent,2)
    box('Module / service face',(0,-1.04,0),(2.2,.16,2.2),'PaintedMetal_Colorable',main,parent,3,.06)
    if 'Capacity' in name:
        for x in (-.55,.55):
            cylinder('Module / storage cell',(x,-.1,0),.36,1.8,'Metal_Shiny',main,parent,24,2)
            box('Module / cell window',(x,-1.14,0),(.35,.04,1.5),'PaintedMetal_VeryDark',main,parent,3)
        for i in range(1,5):box('Module / fill',(-.75+.5*(i-1),-1.17,-.85),(.3,.05,.08),'EnergyFill'+str(i),main,parent,4)
    elif 'Transfer' in name:
        for x in (-.7,-.35,0,.35,.7):box('Module / transfer heatsink',(x,-1.17,0),(.12,.14,1.65),'Metal_Dull',main,parent,3)
    else:
        for z in (-.55,0,.55):box('Module / field vane',(0,-1.18,z),(1.65,.12,.15),'Metal_Shiny',main,parent,3)
    for x in ((-.65,.65) if advanced else (0,)):
        box('Module / tier lamp',(x,-1.2,.9),(.35,.035,.075),'Emissive',main,parent,4)
    collision(cols,parent,(0,0,0),(2.35,2.4,2.35))
    detector=bpy.data.objects.new('detector_terminal',None);main.objects.link(detector);detector.parent=parent;detector.location=(0,-1.21,0);detector.scale=(.8,.04,.8)
    stages(s,cols,parent)

s,cols,parent=scene('ArcanePower_EnergyRotor',True);main=cols['main'][0]
bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=16,radius=.85)
orb=finish(bpy.context.object,'Energy / stored field','EnergyGlow',main,parent)
for p in orb.data.polygons:p.use_smooth=True
for tilt in (-.5,.5):
    bpy.ops.mesh.primitive_torus_add(major_segments=48,minor_segments=8,major_radius=1.6,minor_radius=.055)
    obj=bpy.context.object;obj.rotation_euler=(tilt,.2,0)
    finish(obj,'Energy / orbit','Metal_Shiny',main,parent)

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
    with bpy.context.temp_override(area=area,region=next(r for r in area.regions if r.type=='WINDOW')):
        result=bpy.ops.scene.export()
        if 'FINISHED' not in result:raise RuntimeError('Energy export failed: '+s.name)
    print('EXPORTED',s.name,flush=True)
print('Saved/exported compact storage family and construction stages',flush=True)
