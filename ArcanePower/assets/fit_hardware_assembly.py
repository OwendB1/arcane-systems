"""Seat hardware at native grid centres and remove layered vent/roof surfaces."""
import ast,bpy,bmesh,importlib,json,math
from pathlib import Path
from mathutils import Matrix,Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1]
COLS=importlib.import_module('space-engineers-utilities.seut_collections')
s=bpy.data.scenes['ArcanePower_ReactorPrototype'];bpy.context.window.scene=s
col=COLS.get_collections(s)['main'][0];root=next(o for o in col.objects if o.parent is None)
native={m.name:m for m in bpy.data.materials if m.library}
source=ast.parse((ROOT/'assets/build_deployable_chamber.py').read_text())
exec(compile(ast.Module(body=[n for n in source.body if isinstance(n,ast.FunctionDef) and n.name in ('mesh_object','prism','annulus')],type_ignores=[]),'chamber helpers','exec'))

def cut(obj,cutter):
 mod=obj.modifiers.new('Separate lining and roof surfaces','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter
 bpy.context.view_layer.objects.active=obj;bpy.ops.object.modifier_apply(modifier=mod.name)

if not s.get('ap_lining_relief_v1'):
 housing=next(o for o in col.objects if o.name.startswith('Circular upper armored housing'))
 # The existing barrel shared its inner face with the original housing bore.
 # Widen only the backing, leaving the visible liner's 1.86m bore unchanged.
 for radius,z0,z1 in [(1.935,2.86,3.80),(2.055,3.525,3.80)]:
  cutter=prism('Liner relief cutter',[(radius*math.cos(i*math.tau/128),radius*math.sin(i*math.tau/128)) for i in range(128)],z0,z1,native['Metal_Dull'])
  cut(housing,cutter);bpy.data.objects.remove(cutter,do_unlink=True)
 # Roof panels were only2mm above an uninterrupted backing face. Give each
 # removable panel an actual seat so the backing cannot show through it.
 for panel in [o for o in col.objects if o.name.startswith('Cap removable sector')]:
  cutter=panel.copy();cutter.data=panel.data.copy();col.objects.link(cutter)
  cutter.data.transform(Matrix.Translation((0,0,.003)));cut(housing,cutter)
  bpy.data.objects.remove(cutter,do_unlink=True)
 s['ap_lining_relief_v1']=True
 s['ap_surface_relief']='Roof panel seats and separate barrel/hatch backing; visible bore remains1.86m'

# Centre the native ports on the side armor: Z=-2.33 is the midpoint of
# its[-3.07,-1.59]m extent. Grid block centres remain unchanged.
for obj in col.objects:
 if obj.name.startswith('Base upgrade / native socket'):
  centre=(min(v.co.z for v in obj.data.vertices)+max(v.co.z for v in obj.data.vertices))/2
  obj.data.transform(Matrix.Translation((0,0,-2.33-centre)))
 elif obj.name.startswith('detector_upgrade'):obj.location.z=-2.33

# Replace the old adapter mound with a proper open receiver around each pack.
# The visible rim stops25mm behind the pack's dark face; native sockets stay.
for obj in list(col.objects):
 if obj.name.startswith(('Integrated upgrade / curved socket surround','AP upgrade socket /')):
  bpy.data.objects.remove(obj,do_unlink=True)
# Close the portion of the former low aperture exposed below the raised bay.
# Trim against existing armor so this is infill rather than a layered decal.
for side in (-1,1):
 angle=0 if side>0 else math.pi
 extent=math.asin(.80/6.159)
 patch=annulus('AP upgrade socket / lower armor infill '+str(side),6.03,6.158,-3.07,-2.94,native['PaintedMetal_Colorable'],start=angle-extent,end=angle+extent,segments=24)
 for armor in [o for o in col.objects if o.name.startswith('Drum segmented armor')]:
  points=[v.co for v in armor.data.vertices]
  if max(v.x*side for v in points)>5.8 and min(v.y for v in points)<.81 and max(v.y for v in points)>-.81:cut(patch,armor)

verts=[];polys=[]
for obj in col.objects:
 if obj.type!='MESH' or obj.name.startswith(('SEUT /','Curved chamber')):continue
 offset=len(verts);verts.extend(obj.matrix_world@v.co for v in obj.data.vertices)
 polys.extend([offset+i for i in face.vertices] for face in obj.data.polygons)
surface=BVHTree.FromPolygons(verts,polys)
def socket_outline(w,h,c):
 return [(-w+c,-h),(w-c,-h),(w,-h+c),(w,h-c),(w-c,h),(-w+c,h),(-w,h-c),(-w,-h+c)]
for side in (-1,1):
 vertices=[]
 for u,z in socket_outline(1.15,.65,.095):
  hit,_,_,_=surface.ray_cast(Vector((side*8,u,z-2.33)),Vector((-side,0,0)),4)
  radial=abs(hit.x)-.004 if hit is not None else math.sqrt(6.13**2-u*u)
  vertices.append((side*radial,u,z-2.33))
 for width,height,corner,radial in [(1.00,.59,.085,6.43),(.82,.515,.06,6.43),(.83,.52,.065,6.20)]:
  vertices.extend((side*radial,u,z-2.33) for u,z in socket_outline(width,height,corner))
 faces=[]
 for start,end in [(0,8),(8,16),(16,24),(24,0)]:
  faces.extend((start+i,start+(i+1)%8,end+(i+1)%8,end+i) for i in range(8))
 obj=mesh_object('AP upgrade socket / integrated receiver '+str(side),vertices,faces,native['PaintedMetal_Colorable'])
 bm=bmesh.new();bm.from_mesh(obj.data)
 if bm.calc_volume(signed=True)<0:bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
 bm.normal_update();bm.to_mesh(obj.data);bm.free();obj.data.update()
 obj.data.materials.append(native['Metal_Dull'])
 for face in obj.data.polygons:
  if all(16<=i<32 for i in face.vertices):face.material_index=1
 obj['pack_face_clearance_m']=.025
s['ap_upgrade_socket']='Curved manifold receiver; outer lip at+/-6.43m,25mm behind pack face; native0.68m port retained'

name='AP mounted hardware (not exported)'
c=bpy.data.collections.get(name)
if c:
 for o in list(c.objects):bpy.data.objects.remove(o,do_unlink=True)
else:c=bpy.data.collections.new(name);s.collection.children.link(c)

def instance(label,scene,transform):
 o=bpy.data.objects.new(label,None);c.objects.link(o)
 o.instance_type='COLLECTION';o.instance_collection=COLS.get_collections(bpy.data.scenes[scene])['main'][0]
 o.matrix_world=transform;o['preview_only']=True;return o

placements=[]
for sign,scene in [(1,'ArcanePower_AdvancedContainmentController'),(-1,'ArcanePower_ContainmentController')]:
 transform=Matrix.Translation((sign*7.5,0,-2.5))@Matrix.Rotation(-sign*math.pi/2,4,'Z')
 instance('Mounted / '+scene,scene,transform)
 placements.append({'model':scene,'centre_blender_m':[sign*7.5,0,-2.5],'rotation_z_radians':-sign*math.pi/2})
instance('Mounted / straight vent duct','ArcanePower_VentDuct',Matrix.Translation((0,0,5)))
instance('Mounted / terminal vent outlet','ArcanePower_VentOutlet',Matrix.Translation((0,0,7.5)))
# Collection instances do not resolve exported subpart dummies automatically.
for i in range(4):
 instance('Mounted / outlet leaf '+str(i+1),'ArcanePower_VentHatch',Matrix.Translation((0,0,8.58))@Matrix.Rotation(i*math.pi/2,4,'Z'))
s['ap_mounted_hardware']='Non-exported source collection instances; controller centres +/-7.5,0,-2.5; duct Z5,outletZ7.5'
for a in bpy.context.screen.areas:
 if a.type=='VIEW_3D':
  a.spaces.active.overlay.show_overlays=False;a.spaces.active.shading.type='MATERIAL'
  r=a.spaces.active.region_3d;r.view_rotation=Vector((12,-18,12)).to_track_quat('Z','Y');r.view_location=(0,0,1.5);r.view_distance=27
(ROOT/'validation/mounted-hardware.json').write_text(json.dumps({'controllers':placements,'duct_centre_blender_m':[0,0,5],'outlet_centre_blender_m':[0,0,7.5],'collection':name,'source_instances':True,'socket_lip_radius_axis_m':6.43,'pack_face_radius_axis_m':6.455,'socket_face_setback_m':.025,'pack_width_m':1.6,'socket_widest_width_m':2.3,'socket_lip_outer_width_m':2.0,'pack_and_port_centre_z_m':-2.33,'pack_local_z_offset_m':.17,'white_panel_z_extent_m':[-3.07,-1.59],'socket_top_bottom_margin_m':.09,'surface_fixes':['Recessed external vent service panels/rails','Barrel backing clearance','Roof panel seats'],'scope':'Blender authoring and mounted inspection; no game calls'},indent=2)+'\n')
bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
print(s['ap_mounted_hardware'])
