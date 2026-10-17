"""Review-only moving tracers from authored paths and compiled C# route results.

Run install() in live Blender. No preview mesh belongs to a native main collection;
ThermalFlowVisuals.cs owns the actual depth-tested game billboards.
"""
import bisect
import json
import math
from pathlib import Path
import runpy
import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
R = runpy.run_path(str(ROOT/'assets/review_thermal_models.py'))
M = R['M']
PATHS = json.loads((ROOT/'assets/thermal-flow-paths.json').read_text())['models']


def material(label, color, liquid):
    name = 'REVIEW ONLY / '+label
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Emission Color'].default_value = (*color, 1)
    bsdf.inputs['Emission Strength'].default_value = .8
    bsdf.inputs['Roughness'].default_value = .6
    texture=mat.node_tree.nodes.get('Native particle') or mat.node_tree.nodes.new('ShaderNodeTexImage')
    texture.name='Native particle'
    native=Path.home()/'.local/share/Steam/steamapps/common/SpaceEngineers/Content/Textures/Particles'
    texture.image=bpy.data.images.load(str(native/('ProjectileTrailLine.dds' if liquid else 'Smoke_lit.dds')),check_existing=True)
    texture.image.pack()
    tint=mat.node_tree.nodes.get('Particle tint') or mat.node_tree.nodes.new('ShaderNodeMixRGB')
    tint.name='Particle tint';tint.blend_type='MULTIPLY'
    tint.inputs[0].default_value=1
    tint.inputs[1].default_value=(*color,1)
    mat.node_tree.links.new(texture.outputs['Color'],tint.inputs[2])
    mat.node_tree.links.new(tint.outputs[0],bsdf.inputs['Emission Color'])
    alpha=mat.node_tree.nodes.get('Particle alpha') or mat.node_tree.nodes.new('ShaderNodeMath')
    alpha.name='Particle alpha';alpha.operation='MULTIPLY';alpha.inputs[1].default_value=.45
    mat.node_tree.links.new(texture.outputs['Alpha'],alpha.inputs[0])
    mat.node_tree.links.new(alpha.outputs[0],bsdf.inputs['Alpha'])
    mat.surface_render_method='DITHERED'
    mat['review_only'] = True
    return mat


def sample(points, distances, at):
    i = min(len(points)-1, max(1, bisect.bisect_left(distances, at)))
    t = max(0, min(1, (at-distances[i-1])/(distances[i]-distances[i-1])))
    return points[i-1].lerp(points[i], t)


def draw(scene, rows, objects, frame):
    geometry = {key: ([], []) for key in objects}
    distance = (frame-1)/scene.render.fps*1.25
    space=next(a.spaces.active for a in bpy.context.screen.areas if a.type=='VIEW_3D')
    eye=space.region_3d.view_matrix.inverted().translation
    camera_up=space.region_3d.view_rotation@Vector((0,1,0))
    for row, pose, sign in rows:
        points = [Vector(v) for v in row['points']]
        distances = [0]
        for a,b in zip(points,points[1:]): distances.append(distances[-1]+(b-a).length)
        length = distances[-1]
        chamber = row['circuit'] == 'CHAMBER'
        liquid = row['circuit'] == 'PRIMARY'
        spacing = .125 if chamber else .75
        at = (distance*sign) % spacing
        vertices, faces = geometry[('hot' if row['hot'] else 'cold')+(' liquid' if liquid else ' gas')]
        while at < length:
            fade = min(1, at/min(.20,length*.25), (length-at)/min(.20,length*.25))
            if fade > .01:
                c = pose@sample(points, distances, at)
                d = pose.to_3x3()@(sample(points,distances,min(length,at+.16))-sample(points,distances,max(0,at-.04)))
                d.normalize()
                facing=(eye-c).normalized()
                across=d.cross(facing).normalized() if liquid else camera_up.cross(facing).normalized()
                up=d if liquid else facing.cross(across).normalized()
                radius = (.025+.065*at/length if chamber else min(.11,row['radius']*.52))
                if liquid: radius=min(.035,row['radius']*.18)
                radius *= fade
                half = .10*fade if liquid else radius
                start = len(vertices)
                along=up*half
                vertices += [c-along-across*radius,c+along-across*radius,c+along+across*radius,c-along+across*radius]
                faces.append(tuple(start+i for i in range(4)))
            at += spacing
    for key,obj in objects.items():
        vertices,faces = geometry[key]
        obj.data.clear_geometry()
        obj.data.from_pydata(vertices, [], faces)
        uv=obj.data.uv_layers.new(name='Native particle UV')
        for poly in obj.data.polygons:
            for index,corner in zip(poly.loop_indices,((0,0),(1,0),(1,1),(0,1))):
                uv.data[index].uv=corner
        obj.data.update()


def install():
    # The room's active sockets come from the compiled production route selector.
    states = json.loads((ROOT/'validation/thermal-models/flow-review-states.json').read_text())
    fixture = json.loads((ROOT.parent/'tests/fixtures/thermal-room-layout.json').read_text())
    room = bpy.data.scenes['Thermal production / Reactor room loop']
    chamber, _ = R['fresh']('Flow chamber')
    R['instance'](chamber, 'Reactor housing', (0,0,0))
    jobs = []
    for scene, entries, directions in (
        (chamber, [{'model':'Reactor housing','matrix_blender':Matrix.Identity(4)}], None),
        (room, fixture['instances'], {r['id']:r['ports'] for r in states['room']})):
        previous = [c for c in scene.collection.children if c.get('thermal_flow_preview')]
        for col in previous:
            for obj in list(col.objects): bpy.data.objects.remove(obj,do_unlink=True)
            bpy.data.collections.remove(col)
        col=bpy.data.collections.new(scene.name+' / flow preview')
        scene.collection.children.link(col)
        col['review_only']=col['thermal_flow_preview']=True
        rows=[]
        for ident,entry in enumerate(entries,1):
            model=M['CONTRACT']['subtype'](entry['model'])
            pose=Matrix(entry['matrix_blender'])
            ports=directions.get(ident,[]) if directions is not None else []
            for row in PATHS[model]:
                if row['internal']:
                    sign=1
                elif directions is None:
                    continue
                else:
                    port=ports[row['port']] if row['port'] < len(ports) else 0
                    sign=(1 if port==1 else -1 if port==2 else 0)*(1 if row['hot'] else -1)
                if sign: rows.append((row,pose,sign))
        objects={}
        for key,color in (('hot',(1.,.28,.045)),('cold',(.035,.56,.85))):
            for liquid in (False,True):
                label=key+(' liquid' if liquid else ' gas')
                mesh=bpy.data.meshes.new(scene.name+' '+label+' tracers')
                obj=bpy.data.objects.new(mesh.name,mesh);col.objects.link(obj)
                obj.data.materials.append(material(label,color,liquid));obj['review_only']=True
                objects[label]=obj
        scene.render.fps=24
        scene.frame_start,scene.frame_end=1,145
        jobs.append((scene,rows,objects))
    for handler in list(bpy.app.handlers.frame_change_post):
        if handler.__name__ == 'arcane_flow_frame': bpy.app.handlers.frame_change_post.remove(handler)
    def arcane_flow_frame(scene, depsgraph=None):
        for target,rows,objects in jobs:
            if target==scene: draw(scene,rows,objects,scene.frame_current)
    bpy.app.handlers.frame_change_post.append(arcane_flow_frame)
    bpy.app.driver_namespace['thermal_flow_preview_jobs']=jobs
    for scene,rows,objects in jobs:
        scene.frame_set(12)
        draw(scene,rows,objects,12)
    R['view'](chamber.name,(4.6,0,.1),(-1,-.25,.15),3)
    return {'scenes':[s.name for s,_,_ in jobs], 'paths':[len(rows) for _,rows,_ in jobs],
            'authority':'Compiled C# socket directions; Blender geometry is preview only'}


if __name__ == '__main__':
    result=install()
