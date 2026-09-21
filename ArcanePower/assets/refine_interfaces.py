"""Add glass and native, integer-cell controller interfaces to export scenes."""
import bpy
import importlib
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
get_cols=importlib.import_module('space-engineers-utilities.seut_collections').get_collections
main=bpy.data.scenes['ArcanePower_ReactorPrototype']
bpy.context.window.scene=main
cols=get_cols(main)
root=next(o for o in cols['main'][0].objects if o.parent is None)
native={m.name:m for m in bpy.data.materials if m.library}
helpers={'__file__':str(ROOT/'assets/mockups/build_mockups.py'),'__name__':'helpers'}
exec(compile(Path(helpers['__file__']).read_text(),helpers['__file__'],'exec'),helpers)
helpers['M']={'Hull':native['PaintedMetal_Colorable'],'Dark':native['PaintedMetal_VeryDark'],'Edge':native['Metal_Dull']}


def move(o,col):
    for c in list(o.users_collection):c.objects.unlink(o)
    col.objects.link(o)
    return o


def box(name,pos,size,col=cols['main'][0],parent=root,mat='Hull'):
    o=helpers['box'](name,pos,size,mat,parent)
    move(o,col)
    # Tiled UVs for new mechanical study geometry.
    uv=o.data.uv_layers.new(name='UVMap')
    for p in o.data.polygons:
        axes=[i for i in range(3) if i!=max(range(3),key=lambda i:abs(p.normal[i]))]
        for j in p.loop_indices:
            v=o.data.vertices[o.data.loops[j].vertex_index].co
            uv.data[j].uv=(v[axes[0]],v[axes[1]])
    return o


# Remove the visual-only boxes formerly mounted on arbitrary pillar positions.
for o in list(cols['main'][0].objects):
    original=bpy.data.scenes['08 Rounded reactor detail'].objects.get(o.name.rsplit('.',1)[0])
    # Export names can gain Blender suffixes; source parent membership is more reliable via prefix families.
    if o.name.startswith(('Controller armored casing','Controller front recess')):
        bpy.data.objects.remove(o,do_unlink=True)

# Four flat, two-sided game glass panes between the pillars, leaving the ring sweep clear.
for i in range(4):
    a=i*math.pi/2
    for inside in [False,True]:
        verts=[(-2.67,-2.97,2.92-6.25),(2.67,-2.97,2.92-6.25),
               (2.67,-2.97,8.92-6.25),(-2.67,-2.97,8.92-6.25)]
        mesh=bpy.data.meshes.new('Chamber glass')
        mesh.from_pydata(verts,[],[(3,2,1,0) if inside else (0,1,2,3)])
        mesh.materials.append(native['GlassInside' if inside else 'GlassOutside'])
        uv=mesh.uv_layers.new(name='UVMap')
        for j,co in enumerate([(0,0),(1,0),(1,1),(0,1)]):uv.data[j].uv=co
        o=bpy.data.objects.new('Chamber glass / '+('inside' if inside else 'outside'),mesh)
        cols['main'][0].objects.link(o);o.parent=root;o.rotation_euler.z=a
    for z in [2.87-6.25,8.96-6.25]:
        o=box('Glazing frame', (0,-2.97,z),(5.90,.14,.13),mat='Edge')
        # Rotate both position and orientation about the reactor axis.
        o.location.x=2.97*math.sin(a);o.location.y=-2.97*math.cos(a);o.rotation_euler.z=a

# Reactor ports: side X=+/-6.25, SE Y=-2.5, Z=0. Modules center on X=+/-7.5.
parts=bpy.app.driver_namespace['ap_parts']
for side in [-1,1]:
    box('Grid-aligned controller receiver', (side*5.57,0,-2.5),(1.36,2.48,2.48))
    p=parts['Upgrade Port LG'].copy();cols['main'][0].objects.link(p);p.parent=root
    p.name='Grid upgrade socket';p.location=(side*5,0,-2.5);p.rotation_euler=(0,side*math.pi/2,0);p.scale=(1,1,1)
    d=bpy.data.objects.new('detector_upgrade_'+str(side),None);cols['main'][0].objects.link(d);d.parent=root
    d.location=(side*6.15,0,-2.5)

module=bpy.data.scenes.new('ArcanePower_ContainmentController')
bpy.context.window.scene=module
bpy.ops.scene.recreate_collections()
module.seut.subtypeId=module.name;module.seut.mod_path=str(ROOT/'src');module.seut.export_sbc_type='none'
module.seut.export_deleteLooseFiles=False
mc=get_cols(module)
mr=box('Controller body',(0,0,0),(2.48,2.48,2.48),col=mc['main'][0],parent=None)
for side in [-1,1]:
    p=parts['Upgrade Port LG'].copy();mc['main'][0].objects.link(p);p.parent=mr
    p.name='Controller upgrade socket';p.location=(0,0,0);p.rotation_euler=(0,side*math.pi/2,0);p.scale=(1,1,1)
    d=bpy.data.objects.new('detector_upgrade_'+str(side),None);mc['main'][0].objects.link(d);d.parent=mr;d.location=(side*1.15,0,0)
for name,pos in [('Terminal LG',(-.45,-1.251,.35)),('Terminal Screen',(-.45,-1.258,.35))]:
    p=parts[name].copy();mc['main'][0].objects.link(p);p.parent=mr;p.location=pos;p.rotation_euler=(math.pi/2,0,0);p.scale=(1,1,1)
box('Controller front armor',(0,-1.18,0),(1.8,.12,1.9),col=mc['main'][0],parent=mr,mat='Dark')
collision=mr.copy();collision.data=mr.data.copy();collision.parent=None;collision.modifiers.clear();mc['hkt'][0].objects.link(collision)
bpy.app.driver_namespace['ap_export_scenes'].append(module)
bpy.context.window.scene=main
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
print('Added four glazed faces and grid-aligned module sockets; controller footprint 1x1x1 LG.')
