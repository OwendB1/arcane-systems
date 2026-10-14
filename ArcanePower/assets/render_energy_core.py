"""Render storage icons and construction previews from arcane-energy-core.blend."""
import bpy,importlib,math
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
COLS=importlib.import_module('space-engineers-utilities.seut_collections')
scenes=[s for s in bpy.data.scenes if s.name.startswith('ArcanePower_Energy') and s.name!='ArcanePower_EnergyRotor']
review=bpy.data.scenes.new('Energy review');review.render.engine='CYCLES';review.cycles.samples=24;review.cycles.use_denoising=True
review.render.resolution_x=review.render.resolution_y=512;review.render.resolution_percentage=100;review.render.film_transparent=True
review.render.image_settings.file_format='PNG';review.render.image_settings.color_mode='RGBA'
review.world=bpy.data.worlds.new('Energy studio');review.world.use_nodes=True
review.world.node_tree.nodes['Background'].inputs[0].default_value=(.15,.18,.23,1);review.world.node_tree.nodes['Background'].inputs[1].default_value=.7
cam=bpy.data.objects.new('Energy camera',bpy.data.cameras.new('Energy camera'));review.collection.objects.link(cam);cam.data.type='ORTHO';review.camera=cam
for pos in ((-8,-10,10),(8,5,10),(0,10,4)):
 data=bpy.data.lights.new('Studio light','AREA');data.energy=2200;data.size=8
 obj=bpy.data.objects.new('Studio light',data);review.collection.objects.link(obj);obj.location=pos;obj.rotation_euler=(-obj.location).to_track_quat('-Z','Y').to_euler()
folder=ROOT/'assets/icons/energy';folder.mkdir(parents=True,exist_ok=True)
previews=ROOT/'validation/energy';previews.mkdir(parents=True,exist_ok=True)
for source in scenes:
 bpy.context.window.scene=source;bpy.context.view_layer.update();cols=COLS.get_collections(source)
 core=source.name=='ArcanePower_EnergyCore'
 groups=[(cols['main'][0],folder/(source.name+'.png'))]
 groups += [(c,previews/(source.name+'_BS'+str(c.seut.type_index)+'.png')) for c in (cols['bs'] or []) if any(o.type=='MESH' for o in c.objects)]
 cam.location=(10,16,9) if core else (4,-7,4)
 cam.rotation_euler=(-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=11 if core else 3.8
 for col,path in groups:
  copies=[];collections=[col]
  if core and col==cols['main'][0]:collections.append(COLS.get_collections(bpy.data.scenes['ArcanePower_EnergyRotor'])['main'][0])
  for collection in collections:
   for mesh in collection.objects:
    if mesh.type!='MESH':continue
    obj=bpy.data.objects.new('Render mesh',mesh.data);review.collection.objects.link(obj);obj.matrix_world=mesh.matrix_world.copy();copies.append(obj)
  bpy.context.window.scene=review;review.render.filepath=str(path);bpy.ops.render.render(write_still=True)
  for obj in copies:bpy.data.objects.remove(obj,do_unlink=True)
 print('RENDERED',source.name,flush=True)
