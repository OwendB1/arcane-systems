"""Matched live viewport comparisons, preserving production scene visibility."""
import importlib
import json
from pathlib import Path
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'validation/reactor-texture-lod-loop'
COLS=importlib.import_module('space-engineers-utilities.seut_collections')


def main(names,stages=True):
    original=bpy.context.scene;rows=[]
    area=next(a for a in bpy.context.screen.areas if a.type=='VIEW_3D');space=area.spaces.active
    rv=space.region_3d;original_view=(rv.view_rotation.copy(),rv.view_location.copy(),rv.view_distance,rv.view_perspective)
    space.overlay.show_overlays=False;space.shading.type='MATERIAL';space.shading.use_scene_world=False;space.shading.use_scene_lights=False
    space.shading.studio_light='studio.exr';space.shading.studiolight_rotate_z=.5;space.shading.studiolight_intensity=.8;space.lens=48
    for name in names:
        scene=bpy.data.scenes[name];bpy.context.window.scene=scene;bpy.context.view_layer.update();cs=COLS.get_collections(scene);main=cs['main'][0]
        layers=[]
        def walk(layer):
            layers.append((layer,layer.hide_viewport))
            for child in layer.children:walk(child)
        walk(bpy.context.view_layer.layer_collection)
        hidden={o:o.hide_get() for o in scene.objects};render={c:c.hide_render for cols in cs.values() if cols for c in cols}
        ps=[o.matrix_world @ v.co for o in main.objects if o.type=='MESH' for v in o.data.vertices]
        lo=Vector([min(p[i] for p in ps) for i in range(3)]);hi=Vector([max(p[i] for p in ps) for i in range(3)]);center=(lo+hi)/2;extent=max(hi-lo)
        direction=Vector((.45,1,.35)) if 'Controller' in name else Vector((.6,-1,.65))
        if 'Energy' in name:
            root=next(o for o in main.objects if o.parent is None)
            direction=root.matrix_world.to_3x3() @ direction
        def show(col):
            for layer,_ in layers:
                kind=layer.collection.seut.col_type
                if kind in ('bs','lod','hkt'):layer.hide_viewport=layer.collection!=col
                elif kind=='main':layer.hide_viewport=False
            for c in render:c.hide_render=c.seut.col_type in ('hkt','lod','bs') and c!=col
            for obj in scene.objects:
                if obj.type=='MESH':obj.hide_set(obj.name not in col.objects)
                elif obj.type=='EMPTY':obj.hide_set(obj.name not in main.objects or col.seut.col_type=='bs')
        def capture(col,label,distance):
            show(col);rv=space.region_3d;rv.view_rotation=direction.to_track_quat('Z','Y');rv.view_location=center;rv.view_distance=distance;rv.view_perspective='PERSP';rv.update()
            scene.render.resolution_x=1200;scene.render.resolution_y=900;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
            path=FOLDER/(name+'-'+label+'.png');scene.render.filepath=str(path)
            with bpy.context.temp_override(area=area,region=next(r for r in area.regions if r.type=='WINDOW')):bpy.ops.render.opengl(write_still=True,view_context=True)
            rows.append({'scene':name,'collection':col.name,'distance_m':distance,'lens_mm':48,'image':path.name})
        try:
            capture(main,'main',extent*1.8)
            if stages:
                for col in sorted(cs.get('bs') or [],key=lambda c:c.seut.type_index):
                    if col.objects:capture(col,'BS'+str(col.seut.type_index),extent*1.8)
            previous=main
            for col in sorted((c for c in cs.get('lod') or [] if c.seut.ref_col==main and c.objects),key=lambda c:c.seut.type_index):
                distance=col.seut.lod_distance
                capture(previous,'before-LOD'+str(col.seut.type_index),distance)
                capture(col,'LOD'+str(col.seut.type_index),distance)
                previous=col
        finally:
            for layer,value in layers:layer.hide_viewport=value
            for obj,value in hidden.items():obj.hide_set(value)
            for col,value in render.items():col.hide_render=value
    bpy.context.window.scene=original
    rv.view_rotation,rv.view_location,rv.view_distance,rv.view_perspective=original_view;rv.update();area.tag_redraw()
    path=FOLDER/'derived-review.json';data=json.loads(path.read_text()) if path.exists() else {}
    for name in names:data[name]=[r for r in rows if r['scene']==name]
    path.write_text(json.dumps(data,indent=2)+'\n')
    return {'images':len(rows),'scenes':names}


if __name__=='__main__':result=main(globals()['REVIEW_NAMES'])
