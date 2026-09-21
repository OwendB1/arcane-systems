"""Grid-sized vent sections, crescent controllers and the inventory tile model."""
import ast,bpy,bmesh,importlib,json,math
from pathlib import Path
from mathutils import Matrix,Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1]
COLS=importlib.import_module('space-engineers-utilities.seut_collections')
reactor=bpy.data.scenes['ArcanePower_ReactorPrototype']
col=COLS.get_collections(reactor)['main'][0];root=next(o for o in col.objects if o.parent is None)
native={m.name:m for m in bpy.data.materials if m.library}
source=ast.parse((ROOT/'assets/build_deployable_chamber.py').read_text())
exec(compile(ast.Module(body=[n for n in source.body if isinstance(n,ast.FunctionDef) and n.name in ('mesh_object','prism','annulus')],type_ignores=[]),'chamber helpers','exec'))
backup=ROOT/'assets/arcane-power-before-external-hardware.blend'
if not backup.exists():bpy.ops.wm.save_as_mainfile(filepath=str(backup),copy=True)
collision_template=COLS.get_collections(reactor)['hkt'][0].objects[0]

def scene_parts(name,kind='mainScene'):
 s=bpy.data.scenes.get(name) or bpy.data.scenes.new(name)
 s.view_layers[0].name='SEUT';s.seut.sceneType=kind;s.seut.gridScale='large'
 s.seut.subtypeId=name;s.seut.mod_path=str(ROOT/'src');s.seut.export_sbc_type='none'
 s.seut.export_exportPath=str(ROOT/'src/Models/Cubes/large')
 cs=COLS.get_collections(s)
 def collection(key,label):
  if cs[key]:c=cs[key][0]
  else:
   c=bpy.data.collections.new(label+' ('+name+')')
   (s.collection if key=='seut' else wrapper).children.link(c)
   c.seut.scene=s;c.seut.col_type=key;c.seut.version=3
  return c
 wrapper=collection('seut','SEUT');main=collection('main','Main');hkt=collection('hkt','Collision - Main');hkt.seut.ref_col=main
 for c in (main,hkt):
  for o in list(c.objects):bpy.data.objects.remove(o,do_unlink=True)
 parent=bpy.data.objects.new(name+' root',None);main.objects.link(parent)
 return s,main,hkt,parent

def collision(mesh,target,parent):
 o=collision_template.copy();o.data=mesh.data.copy();o.name='Collision / '+mesh.name
 target.objects.link(o);o.parent=parent;o.matrix_basis=mesh.matrix_basis.copy()
 o.rigid_body.collision_shape='CONVEX_HULL'
 return o

def box(name,center,size,material,target,parent):
 x,y,z=size
 o=prism(name,[(-x/2,-y/2),(x/2,-y/2),(x/2,y/2),(-x/2,y/2)],-z/2,z/2,material,target,parent)
 o.data.transform(Matrix.Translation(Vector(center)));return o

def dummy(main,parent,name,position,source=None):
 o=bpy.data.objects.new(name,None);main.objects.link(o);o.parent=parent
 if source:o.matrix_basis=source.matrix_basis.copy()
 o.location=position;return o

for name,outlet in [('ArcanePower_VentDuct',False),('ArcanePower_VentOutlet',True)]:
 s,main,hkt,parent=scene_parts(name);bpy.context.window.scene=s
 # Eight outer panels tile an octagonal, grid-flush 7.5m square. The central
 # 3.72m bore is open in both render and static collision geometry.
 outline=[(-3.30,-3.75),(3.30,-3.75),(3.75,-3.30),(3.75,3.30),(3.30,3.75),(-3.30,3.75),(-3.75,3.30),(-3.75,-3.30)]
 for i in range(8):
  a=Vector(outline[i]);b=Vector(outline[(i+1)%8]);ai=a.normalized()*1.88;bi=b.normalized()*1.88
  angle0=math.atan2(a.y,a.x);angle1=math.atan2(b.y,b.x)
  while angle1<=angle0:angle1+=math.tau
  def inner_arc(radius):
   return [(radius*math.cos(angle1+(angle0-angle1)*j/32),radius*math.sin(angle1+(angle0-angle1)*j/32)) for j in range(33)]
  # The edge panels stop short of the hatch pocket. Corner columns surround it.
  lower=prism('Vent / lower frame %d'%i,[tuple(a),tuple(b)]+inner_arc(1.88),-1.25,.70,native['PaintedMetal_Darker'],main,parent)

  top=prism('Vent / flush rim %d'%i,[tuple(a),tuple(b)]+inner_arc(2.08),1.00,1.25,native['PaintedMetal_Darker'],main,parent)

  # Solid peripheral wall enclosing the retracting leaf pocket.
  wall=prism('Vent / pocket wall %d'%i,[tuple(a),tuple(b),tuple(b*.975),tuple(a*.975)],.70,1.0,native['Metal_Dull'],main,parent)

 for i in range(8):
  a=i*math.tau/8-math.pi/8;b=a+math.tau/8
  def outer(t):
   r=3.74/max(abs(math.cos(t)),abs(math.sin(t)))
   return (r*math.cos(t),r*math.sin(t))
  points=[(2.02*math.cos(a),2.02*math.sin(a)),outer(a),outer((a+b)/2),outer(b),(2.02*math.cos(b),2.02*math.sin(b))]
  temp=prism('Vent collision segment '+str(i),points,-1.25,1.25,native['Metal_Dull'],main,parent)
  collision(temp,hkt,parent);bpy.data.objects.remove(temp,do_unlink=True)
 annulus('Vent / inner liner',1.86,1.885,-1.25,.70,native['Metal_Dull'],main,parent)
 annulus('Vent / throat band',1.855,1.885,-.92,-.85,native['Emissive'],main,parent)
 annulus('Vent / upper seat',1.86,2.09,1.00,1.08,native['Metal_Dull'],main,parent)
 def pocket(cutter,parts):
  for obj in parts:
   mod=obj.modifiers.new('Recessed service hardware','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter
   bpy.context.view_layer.objects.active=obj;bpy.ops.object.modifier_apply(modifier=mod.name)
  bpy.data.objects.remove(cutter,do_unlink=True)
 rims=[o for o in main.objects if o.name.startswith('Vent / flush rim')]
 frames=[o for o in main.objects if o.name.startswith('Vent / lower frame')]
 for i in range(4):
  rot=Matrix.Rotation(i*math.pi/2,4,'Z')
  cut=box('Service pocket cutter',(0,-3.74,.05),(2.18,.18,1.18),native['Metal_Dull'],main,parent);cut.data.transform(rot);pocket(cut,frames)
  for label,center,size,mat in [('inset',(0,-3.696,.05),(2.1,.03,1.1),'PaintedMetal_VeryDark'),('status',(0,-3.720,.35),(1.5,.012,.07),'Emissive')]:
   o=box('Vent / '+label+' '+str(i),center,size,native[mat],main,parent);o.data.transform(rot)
  for j in range(5):
   o=box('Vent / grille %d %d'%(i,j),(-.8+.4*j,-3.725,-.07),(.16,.025,.5),native['Metal_Dull'],main,parent);o.data.transform(rot)
  for x in (-1.15,1.15):
   cut=box('Roof pocket cutter',(x,-2.85,1.25),(.88,.83,.06),native['Metal_Dull'],main,parent);cut.data.transform(rot);pocket(cut,rims)
   o=box('Vent / roof service inset',(x,-2.85,1.235),(.85,.80,.012),native['PaintedMetal_VeryDark'],main,parent);o.data.transform(rot)
   for dx in (-.30,.30):
    o=box('Vent / service latch',(x+dx,-2.85,1.244),(.09,.35,.006),native['Metal_Dull'],main,parent);o.data.transform(rot)
  for x in (2.6,):
   cut=box('Rail pocket cutter',(x,-2.55,1.25),(.22,.94,.06),native['Metal_Dull'],main,parent);cut.data.transform(rot);pocket(cut,rims)
   o=box('Vent / roof service rail', (x,-2.55,1.237),(.18,.90,.02),native['Metal_Dull'],main,parent);o.data.transform(rot)
 for direction,z in [('top',1.25),('bottom',-1.25)]:
  port=dummy(main,parent,'detector_conveyor_'+name+'_'+direction,(0,0,z),reactor.objects['detector_conveyor_'+direction])
  if direction=='top':top_port=port
 if outlet:
  for i in range(4):
   d=dummy(main,parent,'subpart_OutletHatch'+str(i+1),(0,0,1.08));d.rotation_euler.z=i*math.pi/2;d['file']='ArcanePower_VentHatch'
  top_port['highlight']=';'.join('subpart_OutletHatch'+str(i+1) for i in range(4))
 s['ap_envelope']='3x1x3 SE cells: 7.5x2.5x7.5 m; straight axial vent route'

# Fit the visual mating skirt to the actual reactor mesh at its installed
# grid position. Collision remains within the adjacent1x1x1 occupied cell.
verts=[];faces=[]
for obj in col.objects:
 if obj.type!='MESH' or obj.name.startswith(('SEUT /','Curved chamber','Integrated upgrade /','AP upgrade socket /')):continue
 offset=len(verts);verts.extend(obj.matrix_world@v.co for v in obj.data.vertices)
 faces.extend([offset+i for i in f.vertices] for f in obj.data.polygons)
reactor_surface=BVHTree.FromPolygons(verts,faces)
for name,advanced in [('ArcanePower_ContainmentController',False),('ArcanePower_AdvancedContainmentController',True)]:
 s,main,hkt,parent=scene_parts(name);bpy.context.window.scene=s
 # Compact piggyback pack:1.60m wide x1.00m high, versus the0.68m native port.
 # Its grid anchor remains unchanged; the visible pack hugs the mating face.
 def rounded_rect(w,h,c):
  return [(-w+c,-h),(w-c,-h),(w,-h+c),(w,h-c),(w-c,h),(-w+c,h),(-w,h-c),(-w,-h+c)]
 outer=rounded_rect(.80,.50,.065);front=rounded_rect(.74,.455,.055);socket=rounded_rect(.37,.37,.025)
 vertices=[]
 for x,z in outer:
  hit,_,_,_=reactor_surface.ray_cast(Vector((9,-x,z-2.33)),Vector((-1,0,0)),5)
  vertices.append((x,hit.x+.012-7.5 if hit is not None else -1.255,z))
 vertices.extend((x,-1.10,z) for x,z in outer)
 vertices.extend((x,-1.045,z) for x,z in front)
 vertices.extend((x,-1.245,z) for x,z in socket)
 vertices.extend((x,-1.155,z) for x,z in socket)
 faces=[]
 for start,end in [(0,8),(8,16),(24,0),(32,24)]:
  faces.extend((start+i,start+(i+1)%8,end+(i+1)%8,end+i) for i in range(8))
 faces.extend([tuple(range(16,24)),tuple(reversed(range(32,40)))])
 body=mesh_object('Power pack / curved socket shell',vertices,faces,native['PaintedMetal_Colorable'],main,parent)
 bm=bmesh.new();bm.from_mesh(body.data)
 if bm.calc_volume(signed=True)<0:bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
 bm.normal_update();bm.to_mesh(body.data);bm.free();body.data.update()
 body.data.materials.append(native['PaintedMetal_VeryDark'])
 # The front insert is a face of the shell, never coplanar overlay geometry.
 for face in body.data.polygons:
  if set(face.vertices)==set(range(16,24)):face.material_index=1
 hull=box('Power pack collision envelope',(0,-1.145,0),(1.60,.20,1.00),native['Metal_Dull'],main,parent)
 collision(hull,hkt,parent);bpy.data.objects.remove(hull,do_unlink=True)
 dummy(main,parent,'detector_upgrade_mating',(0,-1.15,0))
 # Two enclosed cell covers, small retaining clips and tier status bars give
 # the module the proportions of a replaceable battery cartridge.
 for x in (-.20,.20):
  box('Power pack / cell cover',(x,-1.020,-.08),(.30,.028,.49),native['PaintedMetal_Darker'],main,parent)
  box('Power pack / cell spine',(x,-1.001,-.08),(.055,.010,.40),native['Metal_Dull'],main,parent)
 for z in (-.42,.42):
  box('Power pack / retaining clip',(0,-1.044,z),(.19,.064,.085),native['Metal_Dull'],main,parent)
 for i in range(2 if advanced else 1):
  box('Power pack / fuel status',(0,-1.033,.32-i*.065),(.48,.014,.027),native['Emissive'],main,parent)
 for x in (-.23,0,.23):
  box('Power pack / lower vent',(x,-1.034,-.36),(.12,.010,.025),native['Metal_Dull'],main,parent)
 for x in (-.50,.50):
  for z in (-.35,.35):
   box('Power pack / fastener',(x,-1.034,z),(.035,.010,.035),native['Metal_Dull'],main,parent)
 # Raise art and its mating detector inside the existing grid cell.
 for collection in (main,hkt):
  for obj in collection.objects:
   if obj.type=='MESH':obj.data.transform(Matrix.Translation((0,0,.17)))
   elif obj.name.startswith('detector_upgrade'):obj.location.z=.17
 # Broaden face furniture as mesh data only; the cavity and all empties retain
 # their native dimensions. The case itself uses rounded target dimensions above.
 for obj in main.objects:
  if obj.type=='MESH' and obj.name.startswith(('Power pack / cell','Power pack / retaining','Power pack / fuel','Power pack / lower','Power pack / fastener')):
   obj.data.transform(Matrix.Diagonal((4/3,1,1,1)))
 s['ap_pack_vertical_offset_m']=.17
 s['ap_envelope']='1x1x1 native grid anchor; compact1.60x1.00m pack with curved mating back and socket recess'
 s['ap_grid_centre_distance_m']=7.5;s['ap_visible_projection_m']=.26
 s['ap_fit']='Piggyback power pack;12mm sampled back seam, cavity for native0.68m upgrade port'

s,main,hkt,parent=scene_parts('ArcanePower_ContainmentTile','item')
s.seut.export_exportPath=str(ROOT/'src/Models/Cubes/large')
source=COLS.get_collections(bpy.data.scenes['ArcanePower_Tile1'])['main'][0]
for o in source.objects:
 if o.type!='MESH':continue
 c=bpy.data.objects.new('Consumable / '+o.name,o.data.copy());main.objects.link(c);c.parent=parent
 if 'inset' in o.name:
  c.data.materials.clear();c.data.materials.append(native['BlueFrostedMetal'])
 else:collision(c,hkt,parent)
s['ap_item']='ArcaneContainmentTile: one craftable physical tile per shell facet'
# Display the new pieces as an authoring lineup; never exported or animated.
review=bpy.data.scenes.get('Arcane Power external hardware review') or bpy.data.scenes.new('Arcane Power external hardware review')
for o in list(review.objects):bpy.data.objects.remove(o,do_unlink=True)
for name,offset in [('ArcanePower_VentDuct',(-5,0,0)),('ArcanePower_VentOutlet',(5,0,0)),('ArcanePower_ContainmentController',(-3,-7,0)),('ArcanePower_AdvancedContainmentController',(1,-7,0)),('ArcanePower_ContainmentTile',(4,-7,0))]:
 src=bpy.data.scenes[name]
 for o in COLS.get_collections(src)['main'][0].objects:
  if o.type=='MESH':
   c=bpy.data.objects.new(name+' / '+o.name,o.data);review.collection.objects.link(c);c.matrix_world=Matrix.Translation(offset)@o.matrix_basis
  elif o.name.startswith('subpart_'):
   for mesh in COLS.get_collections(bpy.data.scenes[o['file']])['main'][0].objects:
    if mesh.type=='MESH':
     c=bpy.data.objects.new('Outlet door / '+mesh.name,mesh.data);review.collection.objects.link(c);c.matrix_world=Matrix.Translation(offset)@o.matrix_basis
review.world=reactor.world
bpy.context.window.scene=review
for a in bpy.context.screen.areas:
 if a.type=='VIEW_3D':
  a.spaces.active.overlay.show_overlays=False;a.spaces.active.shading.type='MATERIAL'
  r=a.spaces.active.region_3d;r.view_rotation=Vector((8,-13,12)).to_track_quat('Z','Y');r.view_location=(0,-2,0);r.view_distance=26
(ROOT/'assets/external-hardware.json').write_text(json.dumps({'vent_size_se':[3,1,3],'vent_meters':[7.5,2.5,7.5],'bore_radius_m':1.86,'outlet_leaf_drop_m':.30,'outlet_leaf_slide_xy_m':1.40,'controller_size_se':[1,1,1],'controller_mating_blender':[0,-1.15,.17],'controller_vertical_offset_m':.17,'controller_pack_width_height_m':[1.60,1.00],'controller_grid_centre_distance_m':7.5,'controller_skirt':'Mesh-sampled12mm mating seam; reduced depth within near-flush reactor socket surround; native anchors unchanged','controller_visible_projection_m':.26,'tile_model':'ArcanePower_ContainmentTile','route':'Straight, same-grid and aligned with reactor Up; at most16 sections'},indent=2)+'\n')
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
print('Created vent duct, synchronized outlet model, two compact power-pack controllers and physical containment tile')
