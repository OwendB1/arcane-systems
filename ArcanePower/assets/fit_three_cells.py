"""Fit the reactor to 5x3x5 SE cells without scaling its native interfaces."""
import bpy
import math
import importlib
from mathutils import Vector

s=bpy.data.scenes['ArcanePower_ReactorPrototype']
bpy.context.window.scene=s
assert not s.get('three_cells_applied'), 'Already fitted; rebuild export scenes before repeating'
cols=importlib.import_module('space-engineers-utilities.seut_collections').get_collections(s)
root=next(o for o in cols['main'][0].objects if o.parent is None)


def height(z):
    if z<=2.5:return z
    if z<=8.9:return 2.5+(z-2.5)*3.65/6.4
    return 6.15+(z-8.9)*1.35/1.55


# Original root-local geometry used the 5-cell center at z=6.25.
# Keep the entire base and conveyor inserts at native scale; compress only above it.
for o in cols['main'][0].objects:
    if o.type=='MESH':
        # Grid receiver collars stay a full cell high at the middle cell center.
        if o.name.startswith('Grid-aligned controller receiver'):
            o.location.z=0
            continue
        if o.name.startswith('Grid upgrade socket'):
            o.location.z=0
            continue
        # Most meshes are already baked into root coordinates; frame/glass objects carry transforms.
        o.data=o.data.copy()
        matrix=o.matrix_local.copy()
        for v in o.data.vertices:
            p=matrix@v.co
            p.z=height(p.z+6.25)-3.75
            v.co=p
        o.matrix_basis.identity()
    elif o.type=='EMPTY' and o!=root:
        if o.name.startswith('detector_upgrade'):
            o.location.z=0
        else:
            o.location.z=height(o.location.z+6.25)-3.75

# Simple faceted plasma placeholder; four-at-a-time assembly remains a later engine test.
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2,radius=.85,location=(0,0,.575))
core=bpy.context.object;core.name='Prototype faceted plasma';core.parent=root
for c in list(core.users_collection):c.objects.unlink(core)
cols['main'][0].objects.link(core)
core.data.materials.append(next(m for m in bpy.data.materials if m.name=='Emissive' and m.library))
core.data.uv_layers.new(name='UVMap')

# Stay within the ten rigid-body export limit, with glass walls now blocking passage.
for o in list(cols['hkt'][0].objects):bpy.data.objects.remove(o,do_unlink=True)


def collision(pos,size,angle=0,cylinder=False):
    if cylinder:
        bpy.ops.mesh.primitive_cylinder_add(vertices=32,radius=size[0],depth=size[2],location=pos)
    else:
        bpy.ops.mesh.primitive_cube_add(size=1,location=pos)
    o=bpy.context.object;o.name='Prototype collision'
    if not cylinder:o.scale=size
    o.rotation_euler.z=angle
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    for c in list(o.users_collection):c.objects.unlink(o)
    cols['hkt'][0].objects.link(o)


collision((0,0,-3.50),(5.40,5.40,.5),cylinder=True)
collision((0,0,3.30),(4.5,4.5,.90),cylinder=True)
for i in range(4):
    a=i*math.pi/2
    collision((4.75*math.cos(a),4.75*math.sin(a),-2.25),(2.8,8.5,2),a)
    collision((2.97*math.cos(a),2.97*math.sin(a),.6),(.12,6.0,3.7),a)
s.seut.bBox_X=5;s.seut.bBox_Y=5;s.seut.bBox_Z=3
s['three_cells_applied']=True
s['game_size_xyz']='5,3,5'
s['native_interface_centers']='Conveyors Y=-2.5; upgrade sockets Y=0; modules at X=+/-7.5'
bpy.context.view_layer.update()
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
print('Fitted to SE Size=(5,3,5), native interfaces retained; top collision plane +3.75m.')
