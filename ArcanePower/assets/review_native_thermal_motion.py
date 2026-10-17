"""Disposable Blender review of actual MWM vertices under compiled runtime poses."""
import json
from pathlib import Path
import runpy
import bpy
from mathutils import Matrix,Quaternion,Vector

ROOT=Path(__file__).resolve().parents[1]
SCENE='Native manifold motion / runtime review'
AXES=Matrix(((-1,0,0,0),(0,0,1,0),(0,1,0,0),(0,0,0,1)))


def build():
    export=runpy.run_path(str(ROOT/'assets/export_thermal_models.py'))
    source=export['M']['scene_for']('Reactor housing')
    old=bpy.data.scenes.get(SCENE)
    if old:
        bpy.data.batch_remove(ids=list(old.objects))
        bpy.data.scenes.remove(old)
    scene=bpy.data.scenes.new(SCENE)
    scene.world=source.world
    moving={o for _,members,_ in export['subparts']('Reactor housing',export['M']['main_for']('Reactor housing')) for o in members}
    bpy.context.window.scene=source
    bpy.context.view_layer.update()
    for obj in export['M']['main_for']('Reactor housing').objects:
        if obj.type!='MESH' or obj in moving:continue
        copy=obj.copy();copy.animation_data_clear();copy.parent=None
        scene.collection.objects.link(copy);copy.matrix_world=obj.matrix_world.copy()
        copy.name='Native review static / '+obj.name
    data=json.loads((ROOT/'.cache/native-thermal-motion.json').read_text())
    for row in data['parts']:
        if row['model']!='Reactor housing':continue
        faces=[];materials=[]
        for slot,part in enumerate(row['parts']):
            indices=part['indices']
            faces.extend(tuple(indices[i:i+3]) for i in range(0,len(indices),3))
            materials.extend([slot]*(len(indices)//3))
        mesh=bpy.data.meshes.new('Native exported / '+row['name'])
        mesh.from_pydata([(-x,z,y) for x,y,z in row['positions']],[],faces)
        for part in row['parts']:
            material=bpy.data.materials.get(part['material'])
            assert material is not None,part['material']
            mesh.materials.append(material)
        uv=mesh.uv_layers.new(name='Native MWM UV')
        for face,slot in zip(mesh.polygons,materials):
            face.material_index=slot
            for loop in face.loop_indices:uv.data[loop].uv=row['uv'][mesh.loops[loop].vertex_index]
        obj=bpy.data.objects.new('Native runtime / '+row['name'],mesh)
        scene.collection.objects.link(obj)
        obj['native_motion_part']=row['name']
    bpy.context.window.scene=scene
    for area in bpy.context.screen.areas:
        if area.type=='VIEW_3D':
            space=area.spaces.active
            space.shading.type='MATERIAL';space.shading.studiolight_rotate_z=.5
            space.shading.studiolight_intensity=.8
            space.region_3d.view_rotation=Vector((.65,-2,.7)).to_track_quat('Z','Y')
            space.region_3d.view_distance=20
            space.region_3d.view_location=(0,0,-.5)
            space.lens=48
    return pose(0)


def pose(index):
    scene=bpy.data.scenes[SCENE]
    bpy.context.window.scene=scene
    data=json.loads((ROOT/'.cache/native-thermal-motion.json').read_text())
    rows={r['name']:r for r in data['parts'] if r['model']=='Reactor housing'}
    for obj in scene.objects:
        if obj.get('native_motion_part'):
            values=rows[obj['native_motion_part']]['poses'][index]
            native=Matrix([values[i:i+4] for i in range(0,16,4)]).transposed()
            obj.matrix_world=AXES@native@AXES
    scene['native_motion_sample']=index
    bpy.context.view_layer.update()
    return {'scene':SCENE,'sample':index,'deployment':index/46,'exported_moving_parts':20}
