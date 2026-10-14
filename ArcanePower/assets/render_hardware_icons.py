"""Render model icons; pass labels after Blender's -- to render selected icons."""
import bpy,importlib,sys
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
studio=[('Key',(3,-4,8),1800,7),('Fill',(-4,-2,3),950,6),('Rim',(3,5,5),2200,5)]
lights={}
for name,position,energy,size in studio:
 d=bpy.data.lights.new(name,'AREA');d.energy=energy;d.shape='DISK';d.size=size
 o=bpy.data.objects.new(name,d);scene.collection.objects.link(o);o.location=position;o.rotation_euler=(-o.location).to_track_quat('-Z','Y').to_euler()
 lights[name]=o
objects=[]
selected=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
for subtype,label in [('ArcanePower_ReactorPrototype','ArcaneReactor'),('ArcanePower_ContainmentTile','ArcaneContainmentTile'),('ArcanePower_ContainmentController','ArcaneContainmentController'),('ArcanePower_AdvancedContainmentController','ArcaneAdvancedContainmentController'),('ArcanePower_VentDuct','ArcaneVentDuct'),('ArcanePower_VentOutlet','ArcaneVentOutlet')]:
 if selected and label not in selected:continue
 for o in objects:bpy.data.objects.remove(o,do_unlink=True)
 objects=[]
 reactor=label=='ArcaneReactor'
 scene.cycles.samples=128 if reactor else 24
 scene.cycles.use_denoising=reactor
 camera.location=(0,-18,5) if reactor else (5,12,6) if 'Controller' in subtype else (8,-12,13)
 camera.rotation_euler=(-camera.location).to_track_quat('-Z','Y').to_euler()
 # Broad, balanced frontal lights reveal the chamber and lower housing without
 # the overhead hotspot used by the smaller hardware's three-quarter view.
 setup=[('Key',(-8,-10,7),2600,12),('Fill',(8,-10,7),2600,12),('Rim',(0,-10,-3),1600,10)] if reactor else studio
 for name,position,energy,size in setup:
  o=lights[name];o.location=position;o.rotation_euler=(-o.location).to_track_quat('-Z','Y').to_euler()
  o.data.energy=energy;o.data.size=size
 scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.25,.25,.25,1) if reactor else (.12,.14,.18,1)
 scene.world.node_tree.nodes['Background'].inputs[1].default_value=.8 if reactor else .6
 source=bpy.data.scenes[subtype]
 bpy.context.window.scene=source;bpy.context.view_layer.update()
 for mesh in COLS.get_collections(source)['main'][0].objects:
  if mesh.type=='MESH':
   o=bpy.data.objects.new(mesh.name+' icon',mesh.data);scene.collection.objects.link(o);o.matrix_world=mesh.matrix_world.copy();objects.append(o)
  elif mesh.name.startswith('subpart_'):
   for part in COLS.get_collections(bpy.data.scenes[mesh['file']])['main'][0].objects:
    if part.type=='MESH':
     o=bpy.data.objects.new(part.name+' icon',part.data);scene.collection.objects.link(o);o.matrix_world=mesh.matrix_world @ part.matrix_world;objects.append(o)
 bpy.context.window.scene=scene
 # Packs sit near their cell's mating face; frame the geometry, not the block origin.
 bpy.context.view_layer.update()
 corners=[o.matrix_world @ v.co for o in objects for v in o.data.vertices]
 center=Vector([(min(p[i] for p in corners)+max(p[i] for p in corners))/2 for i in range(3)])
 for o in objects:o.location-=center
 view=camera.rotation_euler.to_matrix().transposed()
 projected=[view @ (p-center) for p in corners]
 camera.data.ortho_scale=1.2*max(max(p[i] for p in projected)-min(p[i] for p in projected) for i in (0,1))
 folder=ROOT/'assets/icons';folder.mkdir(exist_ok=True)
 scene.render.filepath=str(folder/(label+'.png'))
 bpy.ops.render.render(write_still=True)
 print('Rendered',label,flush=True)
