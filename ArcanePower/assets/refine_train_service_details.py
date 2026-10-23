"""Fitted rear service panels and housing details for both turbine hands."""
import math
from pathlib import Path
import runpy

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]


def apply(p):
    detail = runpy.run_path(str(ROOT/'assets/refine_thermal_models.py'))
    visibility = runpy.run_path(str(ROOT/'assets/refine_thermal_visibility.py'))
    for obj in list(p.col.objects):
        if obj.get('thermal_rear_service_detail'):
            bpy.data.objects.remove(obj, do_unlink=True)
    cabinet = detail['named'](p, 'generator switchgear')[0]
    generator = detail['named'](p, 'generator casing')[0]
    compressor = detail['named'](p, 'compressor casing')[0]
    # Replace the small, isolated decals with fitted service assemblies.
    for obj in list(p.col.objects):
        if obj.get('thermal_decal_support') in (cabinet.name,generator.name,compressor.name):
            bpy.data.objects.remove(obj,do_unlink=True)
    before = set(p.col.objects)
    side = -1 if ' mirrored' in p.name else 1
    paint = 'PaintedMetal_Colorable' if p.name.endswith(' upgraded') else 'PaintedMetal_Darker'
    x = max((cabinet.matrix_world@v.co).x for v in cabinet.data.vertices)

    rear = p.panel('rear switchgear service frame',(x+.018,0,-1.0),(.044,1.89,1.82),(1,0,0))
    rear['thermal_seated_on'] = cabinet.name
    hatch = p.panel('rear switchgear access door',(x+.048,0,-.55),(.028,1.57,.65),(1,0,0))
    hatch['thermal_seated_on'] = rear.name
    p.label(hatch,'POWER / SERVICE',(x+.064,0,-.45),(0,1,0),(0,0,1),.085)
    for y in (-.58,.58):
        p.box('rear door hinge',(x+.076,y,-.55),(.035,.09,.28),'Metal_Dull',.002)
    for y in (-.43,.43):
        grille = p.panel('rear cooling grille',(x+.051,y,-1.42),(.035,.68,.69),(1,0,0))
        grille['thermal_seated_on'] = rear.name
        detail['mark'](p,grille,'Square Vent',(x+.070,y,-1.42),(0,1,0),(0,0,1),.47,'Atlas3')
    side_panel = p.panel('switchgear side access',(5.4,side*1.099,-.96),(.76,.036,1.70),(0,side,0))
    side_panel['thermal_seated_on'] = cabinet.name
    detail['mark'](p,side_panel,'Tech Panel',(5.4,side*1.118,-.78),(-side,0,0),(0,0,1),.43,'Atlas3')
    p.label(side_panel,'ISOLATE',(5.4,side*1.119,-1.42),(-side,0,0),(0,0,1),.065)

    end_cover=max(detail['named'](p,'generator bolted end cover'),key=lambda o:detail['centre'](o).x)
    rear_x=max((end_cover.matrix_world@v.co).x for v in end_cover.data.vertices)
    bearing=p.panel('generator rear bearing access',(rear_x+.014,0,.84),(.032,1.0,.40),(1,0,0))
    bearing['thermal_seated_on']=end_cover.name
    p.label(bearing,'BEARING / SERVICE',(rear_x+.032,0,.84),(0,1,0),(0,0,1),.073)

    def sector(label,x0,x1,radius,a0,a1,material):
        if side < 0:a0,a1=360-a1,360-a0
        obj=visibility['casing_sector'](p,label,x0,x1,radius-.006,radius+.034,a0,a1,material)
        obj.pop('thermal_upgrade_jacket',None)
        return obj

    def point(x,radius,angle):
        a=math.radians(angle)
        return Vector((x,-side*radius*math.sin(a),visibility['SHAFT_Z']+radius*math.cos(a)))

    for label,x0,x1,radius,a0,a1 in (
            ('compressor',-4.91,-4.43,1.35,240,268),
            ('turbine',.75,1.25,1.85,240,268),
            ('generator',3.40,4.23,1.62,260,320)):
        casing=detail['named'](p,label+' casing')[0]
        panel=sector(label+' rear inspection cover',x0,x1,radius,a0,a1,paint)
        panel['thermal_seated_on']=casing.name
        for xx in (x0+.07,x1-.07):
            for angle in (a0+5,a1-5):
                pos=point(xx,radius+.038,angle)
                normal=(pos-Vector((xx,0,visibility['SHAFT_Z']))).normalized()
                p.bolt(label+' rear cover captive stud',pos,normal,panel,.021)
        middle=(a0+a1)/2
        pos=point((x0+x1)/2,radius+.034,middle)
        normal=(pos-Vector((pos.x,0,visibility['SHAFT_Z']))).normalized()
        u=Vector((-side,0,0));v=normal.cross(u)
        detail['mark'](p,panel,'Tech Panel',pos,u,v,.26 if label!='generator' else .42,'Atlas3')
        if label=='generator':
            for xx in (3.48,4.15):
                rib=sector('generator rear cooling rib',xx-.025,xx+.025,radius+.033,268,312,'Metal_Dull')
                rib['thermal_seated_on']=panel.name

    # Two narrow webs stay outside both pressure bores on the reverse face.
    flange=next(o for o in p.col.objects if o.name.startswith(p.name+' / CO2 flange') and o.get('interface_type'))
    for xx in (-5.79,-4.21):
        web=p.box('manifold reverse stiffener',(xx,-side*2.350,-1.05),(.105,.040,1.28),'Metal_Dull',.003)
        web['thermal_seated_on']=flange.name
        for z in (-.50,-1.05,-1.60):
            p.bolt('manifold reverse stud',(xx,-side*2.326,z),(0,side,0),web,.024)
    for z,caption in ((-.31,'SUPPLY'),(-2.18,'RETURN')):
        p.label(flange,caption,(-5,-side*2.364,z),(-side,0,0),(0,0,1),.055)

    detail['mesh_markings'](p)
    for obj in set(p.col.objects)-before:
        obj['thermal_rear_service_detail']=1
        if obj.type=='MESH':obj['thermal_surface_revision']=detail['REVISION']
    p.scene['thermal_rear_service_revision']=1
    bpy.context.view_layer.update()
    return {'added':len(set(p.col.objects)-before)}
