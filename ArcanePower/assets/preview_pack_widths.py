"""Non-exported mounted-hardware width comparison; no source empties are scaled."""
import bpy,importlib,math
from pathlib import Path
from mathutils import Matrix,Vector
ROOT=Path(__file__).resolve().parents[1]
cols=importlib.import_module('space-engineers-utilities.seut_collections')
reactor=bpy.data.scenes['ArcanePower_ReactorPrototype']
source=bpy.data.scenes['ArcanePower_AdvancedContainmentController']
s=bpy.data.scenes.get('AP pack width comparison (not exported)') or bpy.data.scenes.new('AP pack width comparison (not exported)')
for obj in list(s.objects):bpy.data.objects.remove(obj,do_unlink=True)
s.world=reactor.world
ink=bpy.data.materials.get('AP comparison ink') or bpy.data.materials.new('AP comparison ink')
ink.diffuse_color=(.82,.90,1,1);ink.use_nodes=True
nt=ink.node_tree;nt.nodes.clear();out=nt.nodes.new('ShaderNodeOutputMaterial');em=nt.nodes.new('ShaderNodeEmission');em.inputs['Color'].default_value=(.82,.90,1,1);nt.links.new(em.outputs[0],out.inputs['Surface'])
def text(label,position,size=.13):
 curve=bpy.data.curves.new(label,'FONT');curve.body=label;curve.size=size;curve.align_x='CENTER';curve.materials.append(ink)
 obj=bpy.data.objects.new(label,curve);s.collection.objects.link(obj);obj.location=position;obj.rotation_euler.x=math.pi/2

def line(label,points):
 curve=bpy.data.curves.new(label,'CURVE');curve.dimensions='3D';curve.bevel_depth=.006;curve.bevel_resolution=1;curve.materials.append(ink)
 poly=curve.splines.new('POLY');poly.points.add(len(points)-1)
 for p,co in zip(poly.points,points):p.co=(*co,1)
 obj=bpy.data.objects.new(label,curve);s.collection.objects.link(obj)

socket=next(o for o in cols.get_collections(reactor)['main'][0].objects if o.name=='AP upgrade socket / integrated receiver 1')
world_to_module=(Matrix.Translation((7.5,0,-2.5))@Matrix.Rotation(-math.pi/2,4,'Z')).inverted()
for offset,width,socket_width in [(-2.0,1.6,2.3),(2.0,2.0,3.0)]:
 factor=width/1.6
 transform=Matrix.Translation((offset,-1.1,-.17))@Matrix.Rotation(math.pi,4,'Z')
 for original in cols.get_collections(source)['main'][0].objects:
  if original.type!='MESH':continue
  obj=bpy.data.objects.new(str(width)+'m / '+original.name,original.data.copy());s.collection.objects.link(obj)
  for v in obj.data.vertices:
   # The shell's connector cavity is vertices24..39; its dimensions stay fixed.
   if not original.name.startswith('Power pack / curved socket shell') or v.index<24:v.co.x*=factor
  obj.matrix_world=transform@original.matrix_basis
 obj=bpy.data.objects.new(str(width)+'m / socket surround',socket.data.copy());s.collection.objects.link(obj)
 obj.data.transform(world_to_module@socket.matrix_world)
 for v in obj.data.vertices:
  v.co.x*=socket_width/2.3 if v.index<8 else factor
 obj.matrix_world=transform
 # All figures measure the pack case, not the broader receiver behind it.
 text(('A' if width==1.6 else 'B')+'  /  '+format(width,'.1f')+' m PACK',(offset,-.5,1.12),.19)
 text('Socket surround: '+format(socket_width,'.1f')+' m',(offset,-.5,.88),.115)
 y=-.48;z=-.83
 line('Pack width',[(offset-width/2,y,z),(offset+width/2,y,z)])
 for x in (offset-width/2,offset+width/2):line('Width extension',[(x,y,-.54),(x,y,-.90)])
 text(format(width,'.2f')+' m',(offset,y,-1.07),.16)
 x=offset+socket_width/2+.20
 line('Pack height',[(x,y,-.5),(x,y,.5)])
 for z in (-.5,.5):line('Height tick',[(x-.06,y,z),(x+.06,y,z)])
 text('1.00 m',(x+.27,y,-.04),.12)
text('Same height, depth and native upgrade connection',(0,-.5,-1.5),.13)
s['preview_only']=True;s['comparison']='A:1.6x1.0m pack,2.3m socket; B:2.0x1.0m pack,3.0m socket. Rough width studies; no source edits or empty instances.'
bpy.context.window.scene=s
for a in bpy.context.screen.areas:
 if a.type=='VIEW_3D':
  a.spaces.active.overlay.show_overlays=False;a.spaces.active.shading.type='MATERIAL'
  r=a.spaces.active.region_3d;r.view_rotation=Vector((0,-1,0)).to_track_quat('Z','Y');r.view_perspective='ORTHO';r.view_location=(.30,0,-.1);r.view_distance=6.8
bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
print(s['comparison'])
