"""Seat the fixed dispensers into the ceiling and curved glass retainer.

Only Main receives surrounds. Original dispensers, glass and roof seats stay put.
"""
import bpy
import bmesh
import importlib
import math
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
PREFIX='Reactor exterior / dispenser '


def main():
    scene=bpy.data.scenes['ArcanePower_ReactorPrototype']
    if scene.get('dispenser_mount_revision')==1:return {'already_applied':True}
    bpy.context.window.scene=scene;bpy.context.view_layer.update()
    col=importlib.import_module('space-engineers-utilities.seut_collections').get_collections(scene)['main'][0]
    root=next(o for o in col.objects if o.parent is None)
    native={m.name:m for m in bpy.data.materials if m.library}
    checkpoint=ROOT/'assets/arcane-power-before-dispenser-surrounds.blend'
    if not checkpoint.exists():bpy.ops.wm.save_as_mainfile(filepath=str(checkpoint),copy=True)

    def mesh_object(label,vertices,faces,material):
        mesh=bpy.data.meshes.new(label);mesh.from_pydata(vertices,[],faces)
        bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free();mesh.update()
        mesh.materials.append(native[material]);uv=mesh.uv_layers.new(name='UVMap')
        for face in mesh.polygons:
            axes=[i for i in range(3) if i!=max(range(3),key=lambda a:abs(face.normal[a]))]
            for index in face.loop_indices:
                p=mesh.vertices[mesh.loops[index].vertex_index].co;uv.data[index].uv=(p[axes[0]]*.4,p[axes[1]]*.4)
        obj=bpy.data.objects.new(PREFIX+label,mesh);col.objects.link(obj);obj.parent=root
        return obj

    def curved_rail(label,angle,start,end,inner,outer,bottom,top):
        count=max(2,math.ceil((end-start)*64));vertices=[]
        for i in range(count+1):
            a=angle+start+(end-start)*i/count
            vertices.extend((r*math.cos(a),r*math.sin(a),z) for r,z in ((inner,bottom),(outer,bottom),(outer,top),(inner,top)))
        faces=[(4*i+j,4*i+(j+1)%4,4*(i+1)+(j+1)%4,4*(i+1)+j) for i in range(count) for j in range(4)]
        faces.extend(((3,2,1,0),tuple(4*count+j for j in range(4))))
        return mesh_object(label,vertices,faces,'Metal_Dull')

    for i in range(4):
        angle=-math.pi/4+i*math.pi/2;n=Vector((math.cos(angle),math.sin(angle),0));t=Vector((-n.y,n.x,0))
        # Pitched cheeks overlap the cradle edge, leaving the entire mouth and
        # guide rails open. Their tops penetrate the solid ceiling by 52 mm.
        profile=[(4.13,2.61),(4.73,2.015),(5.045,2.24),(5.045,2.94),(4.37,2.94)]
        for sign in (-1,1):
            vertices=[tuple(n*r+t*(sign*x)+Vector((0,0,z))) for x in (.495,.610) for r,z in profile]
            count=len(profile);faces=[tuple(reversed(range(count))),tuple(range(count,count*2))]
            faces.extend((j,(j+1)%count,(j+1)%count+count,j+count) for j in range(count))
            mesh_object('pitched cheek',vertices,faces,'PaintedMetal_Colorable')
        # A four-sided curved escutcheon masks the glass penetration. It meets
        # the existing seal and stays below the accepted upper pillar seat.
        curved_rail('ceiling flange',angle,-.138,.138,4.86,5.075,2.785,2.925)
        curved_rail('lower glass sill',angle,-.138,.138,4.90,5.06,2.045,2.135)
        for sign in (-1,1):
            low,high=sorted((sign*.119,sign*.138))
            curved_rail('glass side retainer',angle,low,high,4.90,5.06,2.125,2.805)
    scene['dispenser_mount_revision']=1
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/arcane-power-prototype.blend'))
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/arcane-power-exterior-work-in-progress.blend'),copy=True)
    return {'dispenser_surrounds':4,'original_dispensers_moved':False,'roof_seats_changed':False}


if __name__=='__main__':result=main()
