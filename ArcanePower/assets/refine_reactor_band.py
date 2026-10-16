"""Continuous upper cooling belt and outboard pillars; dispensers stay fixed."""
import bpy
import bmesh
import importlib
import math
from pathlib import Path
from mathutils import Matrix, Vector

ROOT=Path(__file__).resolve().parents[1]
PREFIX='Reactor exterior / '


def main():
    scene=bpy.data.scenes['ArcanePower_ReactorPrototype']
    if scene.get('exterior_band_revision')==1:return {'already_applied':True}
    bpy.context.window.scene=scene;bpy.context.view_layer.update()
    col=importlib.import_module('space-engineers-utilities.seut_collections').get_collections(scene)['main'][0]
    root=next(o for o in col.objects if o.parent is None)
    native={m.name:m for m in bpy.data.materials if m.library}
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/arcane-power-before-continuous-band.blend'),copy=True)

    def mesh_object(label,vertices,faces,material):
        mesh=bpy.data.meshes.new(label);mesh.from_pydata(vertices,[],faces);mesh.update()
        bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
        mesh.materials.append(native[material]);uv=mesh.uv_layers.new(name='UVMap')
        for face in mesh.polygons:
            axes=[i for i in range(3) if i!=max(range(3),key=lambda a:abs(face.normal[a]))]
            for index in face.loop_indices:
                p=mesh.vertices[mesh.loops[index].vertex_index].co;uv.data[index].uv=(p[axes[0]]*.4,p[axes[1]]*.4)
        obj=bpy.data.objects.new(PREFIX+label,mesh);col.objects.link(obj);obj.parent=root
        return obj

    def annulus(label,inner,outer,z,height,material):
        count=128;vertices=[];faces=[]
        for i in range(count):
            a=i*math.tau/count
            for r,h in ((inner,z-height/2),(outer,z-height/2),(outer,z+height/2),(inner,z+height/2)):
                vertices.append((r*math.cos(a),r*math.sin(a),h))
        for i in range(count):
            for j in range(4):faces.append((4*i+j,4*i+(j+1)%4,4*((i+1)%count)+(j+1)%4,4*((i+1)%count)+j))
        obj=mesh_object(label,vertices,faces,material)
        for face in obj.data.polygons:
            if face.index%4 not in (1,3):continue
            face.use_smooth=True
            for index in face.loop_indices:
                vertex=obj.data.loops[index].vertex_index;i=vertex//4
                u=i/count
                if face.index//4==count-1 and i==0:u=1
                uv=obj.data.uv_layers.active.data[index];uv.uv=(u*math.tau*outer*.4,obj.data.vertices[vertex].co.z*.4)
        return obj

    # Remove the first pass's separate upper-band cassettes, including their
    # lettering and screws, without disturbing the roof's inspection hatches.
    for obj in list(col.objects):
        if obj.type!='MESH' or not obj.name.startswith(PREFIX):continue
        center=sum((obj.matrix_world @ v.co for v in obj.data.vertices),Vector())/len(obj.data.vertices)
        if 2.95<center.z<3.51 and math.hypot(center.x,center.y)>5.9:bpy.data.objects.remove(obj,do_unlink=True)
    upper=next(o for o in col.objects if o.name.startswith('Circular upper armored housing'))
    cutter=annulus('temporary belt recess',5.930,6.36,3.23,.510,'PaintedMetal_Colorable')
    if upper.data.users>1:upper.data=upper.data.copy()
    mod=upper.modifiers.new('Continuous cooling belt recess','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter
    bpy.context.view_layer.objects.active=upper;bpy.context.view_layer.update();bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter,do_unlink=True)
    annulus('continuous cooling plenum',5.900,6.000,3.23,.520,'PaintedMetal_VeryDark')
    for h in (-.265,.265):annulus('cooling belt edge rail',6.015,6.160,3.23+h,.050,'Metal_Dull')
    for h in (-.135,-.045,.045,.135):annulus('continuous cooling rib',5.990,6.125,3.23+h,.027,'Metal_Dull')

    # Move the jackets, service equipment and pipe runs together. The existing
    # four dispenser assemblies, glass and ring mechanisms are not translated.
    moved=[]
    for obj in col.objects:
        if obj.type!='MESH':continue
        original=obj.name.startswith(('Coolant riser pipe','Pipe coupling','Spine status emitter','SEUT / Tech Panel'))
        attached=obj.name.startswith(PREFIX)
        if not (original or attached):continue
        center=sum((obj.matrix_world @ v.co for v in obj.data.vertices),Vector())/len(obj.data.vertices)
        if not (-1.30<center.z<2.85 and 4.8<math.hypot(center.x,center.y)<5.85):continue
        angle=min((-math.pi/4+i*math.pi/2 for i in range(4)),key=lambda a:abs((math.atan2(center.y,center.x)-a+math.pi)%math.tau-math.pi))
        delta=Vector((math.cos(angle),math.sin(angle),0))*.50
        obj.matrix_basis=Matrix.Translation(delta) @ obj.matrix_basis;moved.append(obj.name)

    def outline(width,inner,outer,corner):
        w=width/2;c=corner
        return [(-w+c,inner),(w-c,inner),(w,inner+c),(w,outer-c),(w-c,outer),(-w+c,outer),(-w,outer-c),(-w,inner+c)]

    def bridge(angle,label,lower,upper,z0,z1):
        n=Vector((math.cos(angle),math.sin(angle),0));t=Vector((-n.y,n.x,0))
        vertices=[tuple(t*x+n*r+Vector((0,0,z))) for loop,z in ((lower,z0),(upper,z1)) for x,r in loop]
        faces=[tuple(reversed(range(8))),tuple(range(8,16))]+[(i,(i+1)%8,(i+1)%8+8,i+8) for i in range(8)]
        return mesh_object(label,vertices,faces,'PaintedMetal_Colorable')

    for i in range(4):
        angle=-math.pi/4+i*math.pi/2
        bridge(angle,'outboard pillar foot',outline(1.80,4.74,6.14,.10),outline(1.62,5.03,6.09,.075),-1.43,-.94)
        bridge(angle,'pillar roof bridge',outline(1.80,4.73,6.15,.10),outline(1.62,4.98,6.10,.075),2.68,2.94)
        bridge(angle,'continuous belt clamp',outline(.120,5.97,6.15,.018),outline(.120,5.97,6.15,.018),2.95,3.51)
    scene['exterior_band_revision']=1
    scene['pillar_outset_m']=.50
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/arcane-power-prototype.blend'))
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/arcane-power-exterior-work-in-progress.blend'),copy=True)
    return {'continuous_cooling_ribs':4,'outboard_pillar_offset_m':.50,'translated_parts':len(moved),'dispensers_moved':False,'saved':bpy.data.filepath}


if __name__=='__main__':result=main()
