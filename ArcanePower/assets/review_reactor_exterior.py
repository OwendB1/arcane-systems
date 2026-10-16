"""Repeatable live-viewport review at measured surface distances, in metres."""
import bpy
import json
import math
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'validation/reactor-exterior-loop-01'


def main(names=None):
    scene=bpy.data.scenes['ArcanePower_ReactorPrototype'];bpy.context.window.scene=scene;bpy.context.view_layer.update()
    area=next(a for a in bpy.context.screen.areas if a.type=='VIEW_3D');space=area.spaces.active
    n=Vector((math.sqrt(.5),-math.sqrt(.5),0));t=Vector((-n.y,n.x,0));up=Vector((0,0,1))
    views={
        'status-front':(n*6.094+up*1.031,n+t*.22),
        'status-side':(n*6.094+up*1.031,n*.65+t),
        'foot-front':(n*6.105-up*1.15,n+t*.30+up*.45),
        'foot-side':(n*5.70+t*.82-up*1.15,t+n*.30+up*.50),
        'foot-chamber':(n*5.09-up*1.20,-n+t*.25+up*.40),
        'roof-seat-front':(n*6.15+up*2.86,n+t*.40-up*.35),
        'roof-seat-chamber':(n*4.99+up*2.87,-n+t*.40-up*.45),
        'pillar-side':(n*5.40+t*.802+up*.80,t+n*.40),
        'pillar-chamber':(n*5.098+up*.80,-n+t*.20),
        'band-front':(n*6.125+up*3.365,n+t*.25+up*.15),
        'band-side':(n*6.125+up*3.365,n*.65+t+up*.15),
        'dispenser-front':(n*4.3916+up*2.3316,-n+t*.30-up*.55),
        'dispenser-side':(n*4.60+t*.610+up*2.50,t+n*.35-up*.20),
        'roof-texture':(Vector((math.cos(math.pi/16),math.sin(math.pi/16),0))*3.65+up*3.748,Vector((.10,0,1))),
        'drum-texture':(Vector((math.cos(-math.pi/8),math.sin(-math.pi/8),0))*6.14-up*1.9,Vector((math.cos(-math.pi/8),math.sin(-math.pi/8),.2))),
    }
    path=FOLDER/'distance-review.json';report=json.loads(path.read_text()) if path.exists() else {'views':{}}
    space.overlay.show_overlays=False;space.shading.type='MATERIAL'
    space.shading.use_scene_world=False;space.shading.use_scene_lights=False
    space.shading.studio_light='studio.exr';space.shading.studiolight_rotate_z=.5;space.shading.studiolight_intensity=.8;space.lens=48
    scene.render.resolution_x=1400;scene.render.resolution_y=1000;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
    for name in names or views:
        target,direction=views[name];records=[]
        for distance in (1.8,2.4,3.0):
            rv=space.region_3d;rv.view_rotation=direction.to_track_quat('Z','Y');rv.view_location=target;rv.view_distance=distance;rv.view_perspective='PERSP';rv.update()
            eye=rv.view_matrix.inverted().translation
            measured=(eye-target).length
            assert abs(measured-distance)<.0001,(name,distance,measured)
            image=FOLDER/(name+'-'+str(distance)+'m.png');scene.render.filepath=str(image)
            with bpy.context.temp_override(area=area,region=next(r for r in area.regions if r.type=='WINDOW')):bpy.ops.render.opengl(write_still=True,view_context=True)
            records.append({'target':list(target),'eye':list(eye),'distance_m':measured,'lens_mm':48,'image':image.name})
        report['views'][name]=records
    report['lighting']={'studio':'studio.exr','rotation_z':.5,'intensity':.8}
    report['geometry_report']='geometry.json';report['live_game_checked']=False
    path.write_text(json.dumps(report,indent=2)+'\n')
    return {'reviewed_views':list(names or views),'distances_m':[1.8,2.4,3.0],'report':str(path)}


if __name__=='__main__':result=main(globals().get('REVIEW_VIEWS'))
