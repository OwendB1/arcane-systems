"""Live UI review and schematic plant assemblies, separate from export models."""
import json
import math
import runpy
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'validation/thermal-concepts'
BUILD=runpy.run_path(str(ROOT/'assets/build_thermal_concepts.py'))
Parts=BUILD['Parts']
DETAIL_VIEWS=[
    ('Brayton train','port',(-2.5,-3.79,1.25),(0,-1,.08)),
    ('Brayton train','cradle',(-1.35,1.7,-.6),(.15,1,.1)),
    ('Primary heater','cassette',(-1.55,-2.832,.7),(.08,-1,.1)),
    ('Primary heater','vessels',(1.25,1.9,.7),(.15,1,.1)),
    ('Recuperator','ports',(-3.75,-1.25,0),(-1,-.1,.08)),
    ('Recuperator','plate-bank',(-1.55,1.75,.6),(.1,1,.08)),
    ('Atmospheric cooler','fan',(1.68,-2.35,.4),(0,-1,.08)),
    ('Atmospheric cooler','exhaust',(1.3,1.84,.6),(0,1,.08)),
    ('Space radiator','tiles',(1.55,-.15,.3),(0,-1,.12)),
    ('Space radiator','rear tiles',(-1.55,.15,.3),(0,1,.12)),
    ('Space radiator','pump',(0,-.477,-2.85),(0,-1,.1)),
    ('Brayton train upgraded','hot end',(-1.9,-.752,2.14),(0,-1,.4)),
    ('Primary heater upgraded','hot end cassette',(1.55,2.92,.5),(0,1,.1)),
    ('Recuperator upgraded','manifold',(1.55,-2.06,.4),(0,-1,.1)),
    ('Duplex straight','west',(-1.25,0,0),(-1,-.2,.12)),
    ('Duplex straight','clamp',(.65,-.44,-.5),(.1,-1,.2)),
    ('Duplex elbow','bend',(0,.6,.46),(1,-1,.5)),
    ('Duplex elbow','north',(0,1.25,0),(.1,1,.12)),
    ('Brayton train','compressor motor',(-5.55,-.877,.45),(-.2,-1,.1)),
    ('Recuperator','bypass clearance',(3.3,.45,1.4),(1,.5,.4)),
    ('Duplex tee','branch bore',(0,1.25,0),(.1,1,.15)),
    ('Brayton train upgraded','controller',(-4.25,-1.482,-.45),(0,-1,.1)),
    ('Recuperator upgraded','rear manifold',(-1.55,2.06,.4),(0,1,.1)),
    ('Parallel train bank','HP header',(-2.5,-7.5,4.565),(1,1,.8)),
    ('Parallel train bank','LP header',(-2.5,7.5,4.565),(1,-1,.8)),
]


def tools_for(scene,col):
    p=object.__new__(Parts);p.name=scene.name;p.scene=scene;p.col=col
    p.native={m.name:m for m in bpy.data.materials if m.library}
    p.ports=[];p.support=[]
    return p


def view(scene,target=(0,0,0),direction=(1,-1,.65),distance=18):
    bpy.context.window.scene=bpy.data.scenes[scene]
    bpy.context.view_layer.update()
    for area in bpy.context.screen.areas:
        if area.type!='VIEW_3D':continue
        s=area.spaces.active;s.region_3d.view_location=target
        s.region_3d.view_rotation=Vector(direction).to_track_quat('Z','Y')
        s.region_3d.view_distance=distance;s.region_3d.view_perspective='PERSP'
        s.lens=48;s.overlay.show_overlays=False;s.shading.type='MATERIAL'
        s.shading.studio_light='studio.exr';s.shading.studiolight_rotate_z=.5
        s.shading.studiolight_intensity=.8;s.clip_start=.015;s.clip_end=500
        area.tag_redraw()
    return {'scene':scene,'target':list(target),'direction':list(direction),'distance_m':distance,'lens_mm':48}


def snapshot(filename):
    """Capture the settled live UI, called after a separate view-setting call."""
    area=next(a for a in bpy.context.screen.areas if a.type=='VIEW_3D')
    path=OUT/filename
    with bpy.context.temp_override(area=area):bpy.ops.screen.screenshot_area(filepath=str(path))
    s=area.spaces.active;r=s.region_3d;eye=r.view_matrix.inverted().translation
    row={'image':path.name,'scene':bpy.context.scene.name,'target':list(r.view_location),
         'eye':list(eye),'distance_m':(eye-r.view_location).length,'lens_mm':s.lens,
         'studio_light':s.shading.studio_light,'light_rotation':s.shading.studiolight_rotate_z,
         'light_intensity':s.shading.studiolight_intensity}
    manifest=OUT/'ui-reviews.json';rows=json.loads(manifest.read_text()) if manifest.exists() else {}
    rows[path.name]=row;manifest.write_text(json.dumps(rows,indent=2)+'\n')
    return row


def references():
    for label,filename in (('reactor','arcane-power-prototype.blend'),('battery','arcane-energy-core.blend')):
        key='Thermal reference / '+label
        rows=json.loads((OUT/(label+'-reference.json')).read_text())
        col=bpy.data.collections.get(key)
        if col and len(col.objects)==len(rows):continue
        if col:assert len(col.objects)==0,'Partial reference import needs inspection'
        else:col=bpy.data.collections.new(key)
        if label=='battery':
            names=list(dict.fromkeys(r['mesh'] for r in rows))
            with bpy.data.libraries.load(str(ROOT/'assets'/filename),link=False) as (src,dst):dst.meshes=names.copy()
            meshes=dict(zip(names,dst.meshes))
        for row in rows:
            data=meshes[row['mesh']] if label=='battery' else bpy.data.objects[row['object']].data
            obj=bpy.data.objects.new('Reference '+label+' / '+row['object'],data);col.objects.link(obj)
            obj.matrix_world=Matrix(row['matrix']);obj['reference_only']=True


def instance(scene,collection,label,location):
    obj=bpy.data.objects.new(label,None);scene.collection.objects.link(obj)
    obj.instance_type='COLLECTION';obj.instance_collection=bpy.data.collections[collection]
    obj.location=location;return obj


def engineer(p,xy=(0,0)):
    """Simple 1.9 m scale mannequin, explicitly a review guide."""
    x,y=xy
    p.box('engineer torso',(x,y,1.22),(.48,.27,.61),'PaintedMetal_Colorable',.025)
    p.box('engineer helmet',(x,y,1.745),(.28,.29,.31),'Metal_Dull',.035)
    for sign in (-1,1):
        p.box('engineer leg',(x+sign*.15,y,.45),(.20,.24,.90),'PaintedMetal_Darker')
        p.box('engineer arm',(x+sign*.33,y,1.19),(.14,.22,.62),'PaintedMetal_Darker')


def fresh(name):
    assert name not in bpy.data.scenes,'Review exists; do not duplicate it'
    scene=bpy.data.scenes.new(name);bpy.context.window.scene=scene
    scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
    col=bpy.data.collections.new(name+' / review geometry');scene.collection.children.link(col)
    col['review_only']=True
    return scene,tools_for(scene,col)


def port(model,ident,offset):
    col=bpy.data.collections['Thermal model / '+model]
    row=next(r for r in json.loads(col['ports']) if r['id']==ident)
    return dict(row,position=list(Vector(row['position'])+Vector(offset)))


def layout(environment="atmosphere", upgraded=False):
    """Port-correct schematic routing; final conduit block bill is not authored."""
    assert environment in ('atmosphere','space')
    references()
    scene,p=fresh('Thermal / '+environment.title()+(' upgraded' if upgraded else ' base'))
    train='Brayton train upgraded' if upgraded else 'Brayton train'
    hx='Recuperator upgraded' if upgraded else 'Recuperator'
    heater='Primary heater upgraded' if upgraded else 'Primary heater'
    cooler='Space radiator' if environment=='space' else 'Atmospheric cooler'
    positions={train:(-12.5,0,2.5),hx:(0,1.25,3.75),
               heater:(12.5,-7.5,3.75),cooler:(12.5,11.25,3.75)}
    for name,loc in positions.items():
        instance(scene,'Thermal model / '+name,'Plant / '+name,loc)
    instance(scene,'Thermal reference / reactor','Accepted reactor / reference',(-22.5,-15,3.75))
    instance(scene,'Thermal reference / battery','Accepted battery / reference',(-22.5,10,3.75))
    floor=p.box('review floor',(-2.5,0,-.15),(57.5,50,.30),'PaintedMetal_VeryDark')
    for x in range(-30,26,5):p.box('5 m floor grid',(x,0,.002),(.014,44,.003),'Metal_Dull',0)
    for y in range(-20,23,5):p.box('5 m floor grid',(-2.5,y,.002),(56,.014,.003),'Metal_Dull',0)
    # Deliberate interface proxy: production extraction seat still needs approval.
    proxy=p.box('proposed extraction head',(-15,-15,3.75),(2.5,2.3,2.3),'PaintedMetal_Colorable')
    p.box('extraction head support',(-15,-15,1.30),(1.1,1.6,2.6),'PaintedMetal_Darker')
    p.port('reactor extraction',(-13.75,-15,3.75),(1,0,0),'PRIMARY')
    p.label(proxy,'EXTRACTION HEAD / STUDY',(-15,-16.152,3.75),size=.10)
    proxy['unresolved_interface']='Extraction seat is proposed; no production reactor mesh changed'
    ports={}
    for name,loc in positions.items():
        for row in json.loads(bpy.data.collections['Thermal model / '+name]['ports']):
            ports[(name,row['id'])]=port(name,row['id'],loc)
    ports[('Reactor','extraction')]={'type':'PRIMARY','position':[-13.75,-15,3.75],'normal':[1,0,0],'hot_axis':[0,0,1]}
    edges=[]
    def route(a,b,xy):
        left,right=ports[a],ports[b];assert left['type']==right['type']
        path=[Vector(left['position'])]+[Vector((x,y,3.75)) for x,y in xy]+[Vector(right['position'])]
        assert (path[1]-path[0]).normalized().dot(Vector(left['normal']))>.999
        assert (path[-2]-path[-1]).normalized().dot(Vector(right['normal']))>.999
        for sign in (-1,1):p.tube(left['type']+' schematic '+('H' if sign>0 else 'C'),[q+Vector((0,0,sign*.46)) for q in path],.355,'PaintedMetal_Darker',.075)
        # Routes are concept plumbing; floor posts show a plausible load path.
        for point in path[1:-1]:
            p.box('route saddle stand',(point.x,point.y,1.40),(.28,.85,2.8),'PaintedMetal_Colorable')
            p.box('route saddle head',(point.x,point.y,2.88),(.55,1.02,.18),'Metal_Dull')
        edges.append({'from':list(a),'to':list(b),'type':left['type'],'path':[list(q) for q in path],'up_axis':[0,0,1]})
    route((train,'CO2 leg -1'),(hx,'high-pressure -1'),[(-15,-5),(-5,-5),(-5,0)])
    route((train,'CO2 leg 1'),(hx,'low-pressure -1'),[(-15,5),(-5,5),(-5,2.5)])
    route((hx,'high-pressure 1'),(heater,'CO2'),[(17.5,0),(17.5,-12.5),(12.5,-12.5)])
    route((hx,'low-pressure 1'),(cooler,'CO2'),[(7.5,2.5),(7.5,12.5)])
    route(('Reactor','extraction'),(heater,'primary'),[(7.5,-15),(7.5,-7.5)])
    for text,centre in (('SCO2 TRAIN',(-12.5,-7.5,.007)),('HEATER',(12.5,-16,.007)),('RECUPERATOR',(0,-3.5,.007)),(cooler.upper(),(12.5,19,.007)),('REACTOR / REFERENCE',(-22.5,-23,.007)),('BATTERY / REFERENCE',(-22.5,16,.007))):
        p.label(floor,text,centre,(1,0,0),(0,1,0),.38)
    engineer(p,(-8.5,-2.5));engineer(p,(8,-9))
    p.label(floor,environment.upper()+(' / HOT END 65% CEILING' if upgraded else ' / BRAYTON 40% BASE'),(-3,-23,.007),(1,0,0),(0,1,0),.50)
    scene['thermal_connections']=json.dumps(edges);scene['study_not_export']=True
    scene['environment']=environment;scene['upgrade_grade']=3 if upgraded else 0
    (OUT/(environment+('-upgraded' if upgraded else '-base')+'-layout.json')).write_text(json.dumps(edges,indent=2)+'\n')
    return {'scene':scene.name,'connections':len(edges),'production_meshes_edited':False}


def lineup():
    scene,p=fresh('Thermal / Component lineup')
    floor=p.box('lineup floor',(0,2.5,-.15),(62.5,42.5,.30),'PaintedMetal_VeryDark')
    placements={'Brayton train':(-17.5,-10,2.5),'Brayton train upgraded':(0,-10,2.5),
                'Primary heater':(-22.5,5,3.75),'Primary heater upgraded':(-10,5,3.75),
                'Recuperator':(2.5,6.25,3.75),'Recuperator upgraded':(15,6.25,3.75),
                'Atmospheric cooler':(-12.5,18.75,3.75),'Space radiator':(0,18.75,3.75),
                'Duplex straight':(22.5,-10,1.25),'Duplex elbow':(22.5,-2.5,1.25),'Duplex tee':(22.5,17.5,1.25)}
    for name,loc in placements.items():
        instance(scene,'Thermal model / '+name,'Study / '+name,loc)
        p.label(floor,name.upper(),(loc[0],loc[1]-5.5,.007),(1,0,0),(0,1,0),.30)
    engineer(p,(-7,-10))
    for x in (-1.25,1.25):p.box('2.5 m cell edge',(x,-10,1.25),(.025,.025,2.5),'Metal_Dull',0)
    p.box('2.5 m cell top',(0,-10,2.5),(2.5,.025,.025),'Metal_Dull',0)
    p.label(floor,'1.9 M ENGINEER / 2.5 M CELL',(0,-12,.007),(1,0,0),(0,1,0),.20)
    scene['study_not_export']=True
    return {'scene':scene.name,'models':len(placements)}


def cooling_comparison():
    scene,p=fresh('Thermal / Cooling comparison')
    floor=p.box('cooling review floor',(0,0,-.15),(22.5,12.5,.30),'PaintedMetal_VeryDark')
    for name,x in (('Atmospheric cooler',-5),('Space radiator',5)):
        instance(scene,'Thermal model / '+name,'Cooling / '+name,(x,0,3.75))
        p.label(floor,name.upper(),(x,-4.5,.007),(1,0,0),(0,1,0),.26)
    engineer(p,(0,-2))
    scene['study_not_export']=True
    return {'scene':scene.name,'models':2}


def parallel_bank():
    """Three trains with shared HP/LP headers: two duty, one automatic standby."""
    scene,p=fresh('Thermal / Parallel train bank')
    floor=p.box('bank review floor',(0,0,-.15),(55,25,.30),'PaintedMetal_VeryDark')
    branches=[]
    for index,x in enumerate((-15,0,15)):
        instance(scene,'Thermal model / Brayton train','Bank / train '+str(index+1),(x,0,2.5))
        text='STANDBY / AUTO FAILOVER' if index==2 else 'DUTY / 100 MWTH'
        p.label(floor,text,(x,-5,.007),(1,0,0),(0,1,0),.30)
        for sign in (-1,1):branches.append({'port':[x-2.5,sign*3.75,3.75],'header':[x-2.5,sign*7.5,3.75],'type':'CO2_HP' if sign<0 else 'CO2_LP'})
    for sign,kind in ((-1,'CO2_HP'),(1,'CO2_LP')):
        y=sign*7.5
        p.port(kind+' west',(-23.75,y,3.75),(-1,0,0),kind)
        p.port(kind+' east',(23.75,y,3.75),(1,0,0),kind)
        for z in (3.29,4.21):
            p.branch_pipe(kind+' shared header',(-23.75,y,z),(23.75,y,z),
                          [((x-2.5,y,z),(x-2.5,sign*3.75,z)) for x in (-15,0,15)])
        for x in (-23,-17.5,-10,-2.5,5,12.5,20,23):
            p.box('header load post',(x,y,1.44),(.30,.70,2.88),'PaintedMetal_Colorable')
            p.box('header saddle',(x,y,2.91),(.70,1.0,.18),'Metal_Dull')
        p.label(floor,kind+' / CONNECT TO RECOVERY BANK',(0,sign*10,.007),(1,0,0),(0,1,0),.28)
    engineer(p,(-7,-3))
    p.label(floor,'MODULAR GENERATION / 2 DUTY + 1 SPARE',(0,-11.5,.007),(1,0,0),(0,1,0),.35)
    scene['train_bank_branches']=json.dumps(branches);scene['study_not_export']=True
    return {'scene':scene.name,'trains':3,'duty':2,'standby':1,'external_ports':len(p.ports)}
