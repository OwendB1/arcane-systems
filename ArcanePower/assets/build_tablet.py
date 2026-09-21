"""Arcane handheld telemetry tablet; original geometry with SEUT native materials."""
import bpy, importlib, math
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
COLS=importlib.import_module('space-engineers-utilities.seut_collections')
old=bpy.context.window.scene
native={m.name:m for m in bpy.data.materials if m.library}
template=next(o for o in bpy.data.objects if o.type=='MESH' and o.rigid_body)
s=bpy.data.scenes.get('ArcanePower_Tablet')
if s: raise RuntimeError('Tablet scene already exists; edit rather than duplicate it')
s=bpy.data.scenes.new('ArcanePower_Tablet'); bpy.context.window.scene=s
s.seut.sceneType='item'; s.seut.subtypeId='ArcanePower_Tablet'; s.seut.mod_path=str(ROOT/'src')
bpy.ops.scene.recreate_collections()
s.seut.export_sbc_type='none'; s.seut.export_deleteLooseFiles=False
main=COLS.get_collections(s)['main'][0]
root=bpy.data.objects.new('Tablet / root',None); main.objects.link(root)
# Blender X=width, Z=height, -Y=screen/front (SEUT exports to game +Z).
def box(name,center,size,material,bevel=.002):
    bpy.ops.mesh.primitive_cube_add(size=1,location=center)
    o=bpy.context.object; o.name=name; o.dimensions=size
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    for col in list(o.users_collection): col.objects.unlink(o)
    main.objects.link(o); o.parent=root; o.data.materials.append(native[material])
    if bevel:
        m=o.modifiers.new('Machined rounded edges','BEVEL'); m.width=bevel; m.segments=3
        bpy.ops.object.modifier_apply(modifier=m.name)
        m=o.modifiers.new('Weighted normals','WEIGHTED_NORMAL'); bpy.ops.object.modifier_apply(modifier=m.name)
    return o
box('Tablet / armored chassis',(0,0,0),(.36,.045,.26),'PaintedMetal_Colorable',.012)
box('Tablet / back inset',(0,.023,0),(.29,.009,.20),'PaintedMetal_Darker',.008)
box('Tablet / screen recess',(0,-.024,.009),(.294,.009,.202),'PaintedMetal_VeryDark',.009)
box('Tablet / glass display',(0,-.030,.012),(.270,.003,.174),'PaintedMetal_VeryDark',.004)
for side in (-1,1):
    box('Tablet / rubber hand grip '+str(side),(side*.164,-.004,0),(.025,.049,.185),'PaintedMetal_VeryDark',.006)
    for z in (-.063,-.042,-.021,0,.021,.042,.063):
        box('Tablet / grip rib',(side*.165,-.030,z),(.024,.003,.006),'Metal_Dull',.001)
    for z in (-.112,.112):
        box('Tablet / corner fastener',(side*.143,-.025,z),(.009,.004,.009),'Metal_Shiny',.002)
box('Tablet / cyan status rail',(0,-.032,.108),(.226,.003,.003),'Emissive',.001)
for x in (-.042,0,.042):
    box('Tablet / physical function key',(x,-.026,-.102),(.027,.010,.013),'Metal_Dull',.003)
    box('Tablet / key legend',(x,-.032,-.102),(.008,.001,.002),'Emissive',0)
# Static device graphic: brand/antenna icon, not misleading baked live readings.
for x in (-.093,-.031,.031,.093):
    box('Tablet / screen card',(x,-.032,.056),(.052,.001,.046),'PaintedMetal_Darker',.003)
    box('Tablet / screen card accent',(x,-.033,.074),(.039,.001,.002),'Emissive',0)
for z,width in ((.009,.224),(-.017,.182),(-.043,.203),(-.069,.224)):
    box('Tablet / diagnostic trace',(-(.224-width)/2,-.033,z),(width,.001,.002),'Emissive',0)
# Collider encloses only the device. This is an item, no block mount/detector empties.
cols=COLS.get_collections(s)
hc=cols['hkt'][0] if cols['hkt'] else bpy.data.collections.new('Collision - Main ('+s.name+')')
if not cols['hkt']:
    cols['seut'][0].children.link(hc); hc.seut.scene=s; hc.seut.col_type='hkt'; hc.seut.version=3; hc.seut.ref_col=main
c=template.copy(); c.data=bpy.data.meshes.new('Tablet collision'); c.name='Collision / tablet'
verts=[(x,y,z) for z in (-.13,.13) for y in (-.034,.028) for x in (-.18,.18)]
c.data.from_pydata(verts,[],[(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)])
c.data.uv_layers.new(name='UVMap'); c.data.materials.append(native['Metal_Dull']); hc.objects.link(c); c.parent=root; c.matrix_basis.identity(); c.rigid_body.collision_shape='CONVEX_HULL'
# Review camera/light rigs are outside the export collection.
review=bpy.data.collections.new('Tablet review'); s.collection.children.link(review)
def light(name,position,power,size):
    data=bpy.data.lights.new(name,'AREA'); data.energy=power; data.shape='DISK'; data.size=size
    obj=bpy.data.objects.new(name,data); review.objects.link(obj); obj.location=position; obj.rotation_euler=(-obj.location).to_track_quat('-Z','Y').to_euler()
light('Tablet key',(.1,-.7,.8),55,.7); light('Tablet rim',(-.6,.1,.5),65,.5)
data=bpy.data.cameras.new('Tablet camera'); cam=bpy.data.objects.new('Tablet camera',data); review.objects.link(cam)
cam.location=(.31,-.76,.36); cam.rotation_euler=(-cam.location).to_track_quat('-Z','Y').to_euler(); data.type='ORTHO'; data.ortho_scale=.48; s.camera=cam
s.render.engine='CYCLES'; s.cycles.samples=32; s.render.resolution_x=1024; s.render.resolution_y=768; s.render.resolution_percentage=100
s.world=bpy.data.worlds.new('Tablet studio'); s.world.use_nodes=True; s.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.06,.08,.11,1); s.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.4
# Physical collider hidden only for rendering.
c.hide_render=True; c.hide_set(True)
for area in bpy.context.screen.areas:
    if area.type=='VIEW_3D':
        area.spaces.active.region_3d.view_distance=.65; area.spaces.active.region_3d.view_location=(0,0,0)
        area.spaces.active.region_3d.view_rotation=cam.rotation_euler.to_quaternion()
        area.spaces.active.shading.type='MATERIAL'
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/arcane-power-prototype.blend'))
print('Saved handheld tablet scene:',len(main.objects),'objects; item export:',s.seut.export_exportPath)
