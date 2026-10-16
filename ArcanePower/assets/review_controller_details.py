"""Matched controller views at 1.8, 2.4 and 3 m, plus installed fit checks."""
import bpy
import importlib
import json
import math
from pathlib import Path
from mathutils import Matrix,Vector

ROOT=Path(__file__).resolve().parents[1]
NAMES=('ArcanePower_ContainmentController','ArcanePower_AdvancedContainmentController')


def main():
    folder=ROOT/'validation/controller-detail-loop-01';report={'views':{},'live_game_checked':False}
    area=next(a for a in bpy.context.screen.areas if a.type=='VIEW_3D');space=area.spaces.active
    space.overlay.show_overlays=False;space.shading.type='MATERIAL';space.shading.use_scene_world=False;space.shading.use_scene_lights=False
    space.shading.studio_light='studio.exr';space.shading.studiolight_intensity=.8;space.lens=48
    cols=importlib.import_module('space-engineers-utilities.seut_collections')

    def capture(scene,label,target,direction,distances,rotation):
        bpy.context.window.scene=scene;bpy.context.view_layer.update();space.shading.studiolight_rotate_z=rotation
        scene.render.resolution_x=1400;scene.render.resolution_y=1000;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
        records=[]
        for distance in distances:
            rv=space.region_3d;rv.view_rotation=Vector(direction).to_track_quat('Z','Y');rv.view_location=target;rv.view_distance=distance;rv.view_perspective='PERSP';rv.update()
            eye=rv.view_matrix.inverted().translation;measured=(eye-Vector(target)).length
            assert abs(measured-distance)<.0001,(label,distance,measured)
            path=folder/(label+'-'+str(distance)+'m.png');scene.render.filepath=str(path)
            with bpy.context.temp_override(area=area,region=next(r for r in area.regions if r.type=='WINDOW')):bpy.ops.render.opengl(write_still=True,view_context=True)
            records.append({'image':path.name,'distance_m':measured,'target':list(target),'eye':list(eye),'lens_mm':48,'studio_rotation':rotation})
        report['views'][label]=records

    reactor=bpy.data.scenes['ArcanePower_ReactorPrototype']
    for name in NAMES:
        scene=bpy.data.scenes[name];tier='advanced' if 'Advanced' in name else 'standard'
        for view,target,direction in (
                ('front',(0,-1.045,.17),(.25,1,.20)),
                ('side',(.8,-1.245,.17),(1,.65,.25)),
                ('top',(0,-1.215,.67),(.3,.5,1))):
            capture(scene,tier+'-'+view,target,direction,(1.8,2.4,3.0),.5-math.pi)
        bpy.context.window.scene=reactor;bpy.context.view_layer.update()
        installed=next(o for o in reactor.objects if o.instance_collection and o.instance_collection.name==cols.get_collections(scene)['main'][0].name)
        hidden=installed.hide_get();installed.hide_set(False)
        try:
            target=installed.matrix_world @ Vector((0,-1.045,.17));direction=installed.matrix_world.to_3x3() @ Vector((.15,1,.12))
            capture(reactor,tier+'-mounted',target,direction,(1.8,2.4,3.0),.5)
        finally:installed.hide_set(hidden)

    # A side-by-side review scene contains collection instances, not movable
    # copies of production mesh data. Also refresh the older authoring lineup.
    comparison=bpy.data.scenes.get('Controller / detail review') or bpy.data.scenes.new('Controller / detail review')
    for o in list(comparison.objects):
        if o.name.startswith('Controller comparison / '):bpy.data.objects.remove(o,do_unlink=True)
    comparison.world=reactor.world;comparison.seut.paint_color=reactor.seut.paint_color[:]
    lineup=bpy.data.scenes.get('Arcane Power external hardware review')
    for name,x in zip(NAMES,(1.05,-1.05)):
        source=bpy.data.scenes[name];col=cols.get_collections(source)['main'][0]
        obj=bpy.data.objects.new('Controller comparison / '+name,None);comparison.collection.objects.link(obj);obj.instance_type='COLLECTION';obj.instance_collection=col;obj.location.x=x
        if lineup:
            for o in list(lineup.objects):
                if o.name.startswith(name+' / '):bpy.data.objects.remove(o,do_unlink=True)
            offset=(-3,-7,0) if name==NAMES[0] else (1,-7,0)
            for o in col.objects:
                if o.type!='MESH':continue
                copy=bpy.data.objects.new(name+' / '+o.name,o.data);lineup.collection.objects.link(copy);copy.matrix_world=Matrix.Translation(offset) @ o.matrix_world
    capture(comparison,'comparison',(0,-1.045,.17),(.25,1,.20),(3.0,),.5-math.pi)
    report['lighting']={'studio':'studio.exr','intensity':.8}
    (folder/'distance-review.json').write_text(json.dumps(report,indent=2)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/arcane-power-prototype.blend'))
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/arcane-power-exterior-work-in-progress.blend'),copy=True)
    return {'views':len(report['views']),'images':sum(len(v) for v in report['views'].values()),'report':str(folder/'distance-review.json')}


if __name__=='__main__':result=main()
