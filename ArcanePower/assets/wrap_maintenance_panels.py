"""Seat native SEUT atlas decals onto the actual faceted drum armor."""
import bpy
import bmesh
import importlib
import json
import math
from pathlib import Path
from mathutils import Vector
from mathutils import Matrix
from mathutils.bvhtree import BVHTree

s=bpy.data.scenes['ArcanePower_ReactorPrototype']
bpy.context.window.scene=s
col=importlib.import_module('space-engineers-utilities.seut_collections').get_collections(s)['main'][0]
panels=[]
for o in col.objects:
    if o.type!='MESH' or not o.name.startswith('Drum segmented armor'):continue
    verts=[o.matrix_world@v.co for v in o.data.vertices]
    center=sum(verts,Vector())/len(verts)
    panels.append((math.atan2(center.y,center.x),o.name,BVHTree.FromPolygons(verts,[list(p.vertices) for p in o.data.polygons])))
decals=[o for o in col.objects if o.name.startswith('SEUT / Maintenance Box')]
# Recover the original four-vertex decal/UVs; do not preserve the earlier seam
# deformation. This checkpoint predates both maintenance-panel projection passes.
checkpoint=Path(__file__).resolve().parent/'arcane-power-before-deployment.blend'
with bpy.data.libraries.load(str(checkpoint),link=False) as (source,target):
    target.objects=[o.name for o in decals]
for decal,original in zip(decals,target.objects):
    assert original is not None,decal.name
    decal.data=original.data
    bpy.data.objects.remove(original,do_unlink=True)
results=[]
for o in decals:
    points=[o.matrix_world@v.co for v in o.data.vertices]
    center=sum(points,Vector())/len(points)
    angle=math.atan2(center.y,center.x)+math.pi/24
    # Leave both armor bays beside every cardinal conveyor/upgrade socket clear.
    if abs((angle+math.pi/4)%(math.pi/2)-math.pi/4)<math.radians(10):
        if bpy.context.view_layer.objects.active==o:bpy.context.view_layer.objects.active=None
        bpy.data.objects.remove(o,do_unlink=True)
        continue
    _,panel,surface=min(panels,key=lambda p:abs(math.atan2(math.sin(angle-p[0]),math.cos(angle-p[0]))))
    o.data.transform(o.matrix_world.inverted() @ Matrix.Rotation(math.pi/24,4,'Z') @ o.matrix_world)
    bm=bmesh.new();bm.from_mesh(o.data)
    bmesh.ops.subdivide_edges(bm,edges=list(bm.edges),cuts=11,use_grid_fill=True)
    bm.to_mesh(o.data);bm.free()
    inv=o.matrix_world.inverted()
    distances=[]
    for v in o.data.vertices:
        p=o.matrix_world@v.co
        radial=Vector((p.x,p.y,0)).normalized()
        origin=radial*6.4+Vector((0,0,p.z))
        hit,normal,index,distance=surface.ray_cast(origin,-radial,.8)
        assert hit is not None,(o.name,tuple(p))
        if normal.dot(radial)<0:normal=-normal
        seated=hit+normal*.0015
        distances.append((p-seated).length)
        v.co=inv@seated
    o.data.update()
    o['wrapped_to_drum']=True
    o['surface_clearance_m']=.0015
    o['armor_panel']=panel
    # Keep original native atlas UVs, alpha and material references.
    results.append({'name':o.name,'armor_panel':panel,'vertices':len(o.data.vertices),'maximum_reseat_m':max(distances)})
assert len(results)==16
s['maintenance_panels']='16 native atlas decals centred on individual intact armor panels; port-adjacent bays clear; 1.5mm surface offset'
path=Path(__file__).resolve().parents[1]/'validation/maintenance-panels.json'
path.write_text(json.dumps({'panels':results,'clearance_m':.0015,'scope':'Blender surface projection, native UVs retained'},indent=2))
bpy.context.view_layer.update()
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
print(s['maintenance_panels'])
