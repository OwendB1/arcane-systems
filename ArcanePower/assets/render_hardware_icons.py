"""Render inventory/build-menu icons directly from the authored models."""
import bpy,importlib
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
COLS=importlib.import_module('space-engineers-utilities.seut_collections')
scene=bpy.data.scenes.new('Hardware icon render')
bpy.context.window.scene=scene
scene.render.engine='CYCLES';scene.cycles.samples=24
scene.render.resolution_x=512;scene.render.resolution_y=512;scene.render.resolution_percentage=100
scene.render.film_transparent=True;scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA'
scene.world=bpy.data.worlds.new('Icon studio');scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.12,.14,.18,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.6
camera=bpy.data.objects.new('Icon camera',bpy.data.cameras.new('Icon camera'));scene.collection.objects.link(camera);scene.camera=camera
camera.data.type='ORTHO';camera.location=(8,-12,13);camera.rotation_euler=(-camera.location).to_track_quat('-Z','Y').to_euler()
for name,position,energy,size in [('Key',(3,-4,8),1800,7),('Fill',(-4,-2,3),950,6),('Rim',(3,5,5),2200,5)]:
 d=bpy.data.lights.new(name,'AREA');d.energy=energy;d.shape='DISK';d.size=size
 o=bpy.data.objects.new(name,d);scene.collection.objects.link(o);o.location=position;o.rotation_euler=(-o.location).to_track_quat('-Z','Y').to_euler()
objects=[]
for subtype,label in [('ArcanePower_ContainmentTile','ArcaneContainmentTile'),('ArcanePower_ContainmentController','ArcaneContainmentController'),('ArcanePower_AdvancedContainmentController','ArcaneAdvancedContainmentController'),('ArcanePower_VentDuct','ArcaneVentDuct'),('ArcanePower_VentOutlet','ArcaneVentOutlet')]:
 for o in objects:bpy.data.objects.remove(o,do_unlink=True)
 objects=[]
 camera.location=(5,12,6) if 'Controller' in subtype else (8,-12,13)
 camera.rotation_euler=(-camera.location).to_track_quat('-Z','Y').to_euler()
 for mesh in COLS.get_collections(bpy.data.scenes[subtype])['main'][0].objects:
  if mesh.type=='MESH':
   o=bpy.data.objects.new(mesh.name+' icon',mesh.data);scene.collection.objects.link(o);o.matrix_world=mesh.matrix_world.copy();objects.append(o)
  elif mesh.name.startswith('subpart_'):
   for part in COLS.get_collections(bpy.data.scenes[mesh['file']])['main'][0].objects:
    if part.type=='MESH':
     o=bpy.data.objects.new(part.name+' icon',part.data);scene.collection.objects.link(o);o.matrix_world=mesh.matrix_world @ part.matrix_world;objects.append(o)
 # Packs sit near their cell's mating face; frame the geometry, not the block origin.
 bpy.context.view_layer.update()
 corners=[o.matrix_world @ Vector(p) for o in objects for p in o.bound_box]
 center=Vector([(min(p[i] for p in corners)+max(p[i] for p in corners))/2 for i in range(3)])
 for o in objects:o.location-=center
 view=camera.rotation_euler.to_matrix().transposed()
 projected=[view @ (p-center) for p in corners]
 camera.data.ortho_scale=1.2*max(max(p[i] for p in projected)-min(p[i] for p in projected) for i in (0,1))
 folder=ROOT/'assets/icons';folder.mkdir(exist_ok=True)
 scene.render.filepath=str(folder/(label+'.png'))
 bpy.ops.render.render(write_still=True)
 print('Rendered',label,flush=True)
