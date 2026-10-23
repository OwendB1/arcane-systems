"""Hull-integrated atmospheric cooler, edited and reviewed in live Blender."""
import json
import math
from pathlib import Path
import runpy
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
NAME='Atmospheric cooler'


def cut(p, target, cutter):
    bpy.context.view_layer.objects.active=target
    mod=target.modifiers.new('Seated opening','BOOLEAN')
    mod.operation='DIFFERENCE';mod.object=cutter
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter,do_unlink=True)


def apply():
    m=runpy.run_path(str(ROOT/'assets/build_thermal_models.py'))
    detail=runpy.run_path(str(ROOT/'assets/refine_thermal_models.py'))
    flow=runpy.run_path(str(ROOT/'assets/refine_thermal_flow.py'))
    p=m['Parts'](NAME,existing=m['CONTRACT']['subtype'](NAME) in bpy.data.scenes)
    for obj in list(p.col.objects):bpy.data.objects.remove(obj,do_unlink=True)
    p.ports=[]
    p.col.pop('thermal_seal_fit_revision',None)
    # Reuse the established native fan meshes, guards, fasteners and fin stack.
    m['BUILD']['rejector'](p)
    detail['cooler'](p)
    fan_labels=('fan shroud','fan motor','rear motor mounting spider','fan pivot',
                'pitched fan blade','fan guard','guard captive screw','fan rotor nose')
    delta=Vector((0,-.65,-.4))
    for obj in list(p.col.objects):
        label=obj.name.removeprefix(NAME+' / ')
        fan=any(label.startswith(t) for t in fan_labels)
        if not fan and not label.startswith(('solid cooling fin','coolant vertical header')):
            bpy.data.objects.remove(obj,do_unlink=True);continue
        if fan:
            obj['cooler_exhaust_part']=True
            if not obj.parent:obj.location+=delta
            if obj.get('support_point'):obj['support_point']=list(Vector(obj['support_point'])+delta)
            if obj.get('pipe_path'):
                obj['pipe_path']=json.dumps([list(Vector(v)+delta) for v in json.loads(obj['pipe_path'])])
    p.ports=[]
    # Full occupied-cell silhouette: all four hull edges meet adjacent armor.
    front=p.box('flush exhaust bulkhead',(0,-2.41,0),(7.5,.18,7.5),'PaintedMetal_Colorable',0)
    front['thermal_bore_axis']=1
    for x in (-1.68,1.68):
        cut(p,front,p.cylinder('temporary fan bore',(x,-2.7,0),(x,-2.1,0),1.42,sides=48))
    for x in (-3.66,3.66):
        p.box('flush hull side',(x,.09,0),(.18,4.82,7.5),'PaintedMetal_Colorable',0)
    for z in (-3.66,3.66):
        p.box('flush hull end',(0,.09,z),(7.14,4.82,.18),'PaintedMetal_Colorable',0)
    rear=p.box('rear service bulkhead',(0,2.39,0),(7.14,.18,7.14),'PaintedMetal_Darker',.002)
    rear['thermal_bore_axis']=1
    for z in (-.46,.46):
        cut(p,rear,p.cylinder('temporary rear bore',(0,2.1,z),(0,2.7,z),.38,sides=48))
    # Air returns from recessed exterior louvers, so sides/back can be enclosed.
    for z in (-2.7,2.7):
        cut(p,front,p.box('temporary intake opening',(0,-2.41,z),(6.2,.6,.94),chamfer=0))
        p.box('intake shadow backing',(0,-2.12,z),(6.2,.06,.94),'PaintedMetal_VeryDark',0)
        for i in range(7):
            blade=p.box('recessed intake louver',(0,-2.28,z+(i-3)*.13),(6.16,.055,.13),'Metal_Dull',.002)
            blade.rotation_euler.x=math.radians(25)
    for x in (-2.5,2.5):
        door=p.panel('rear service cover',(x,2.484,0),(1.45,.012,4.9),(0,1,0))
        p.label(door,'COIL SERVICE',(x,2.492,1.9),(-1,0,0),(0,0,1),.12)
    p.label(front,'EXHAUST / KEEP 2.5 m CLEAR',(0,-2.501,1.95),size=.14)
    p.label(front,'ATMOSPHERIC COOLER',(0,-2.501,-1.95),size=.13)
    p.port('CO2',(0,2.5,0),(0,1,0),'CO2_LP',(0,0,1))
    detail['tighten_ports'](p)
    flow['materials'](p)
    flow['indicators'](p)
    detail['pressure_seal_fit'](p)
    for hot in (False,True):
        z=.46 if hot else -.46
        p.tube('rear coolant inlet stub',[(0,2.35,z),(0,1.7,z),(3.2 if hot else -3.2,.55,z)],.29,'Metal_Dull',.045,40)
    # Sample positions are authored beside the fan faces, then axis-converted
    # by the existing runtime contract generator. They clear guard fasteners.
    samples=[]
    for x in (-1.68,1.68):
        samples.append([x,-3.08,0])
        for i in range(8):
            a=i*math.tau/8
            samples.append([x+1.05*math.cos(a),-3.08,1.05*math.sin(a)])
    p.col['air_exhaust_samples']=json.dumps(samples)
    for obj in list(p.col.objects):
        if obj.type=='MESH':
            m['BUILD']['uv'](obj)
            detail['cylindrical_uv'](obj,Vector((.17,.31)))
        elif obj.type=='FONT':
            if obj.data.body=='CO2 / LP':obj.location=(0,2.488,.92)
            obj['thermal_text']=obj.data.body
            obj['thermal_decal_support']=obj['thermal_marking_support']
            bpy.ops.object.select_all(action='DESELECT');obj.select_set(True)
            bpy.context.view_layer.objects.active=obj;bpy.ops.object.convert(target='MESH')
            m['BUILD']['uv'](bpy.context.object)
    p.finish()
    p.scene['cooler_integrated_revision']=1
    p.scene['thermal_detail_revision']=p.scene['thermal_texture_revision']=1
    p.scene['thermal_phase']='textures'
    data=json.loads((ROOT/'assets/thermal-flow-paths.json').read_text())
    data['models'][p.scene.name]=[flow['path_row']([(0,2.5,s*.46),(0,1.7,s*.46)],'CO2_LP',s>0,0,.16,label='rear cooler union') for s in (-1,1)]
    (ROOT/'assets/thermal-flow-paths.json').write_text(json.dumps(data,indent=2)+'\n')
    return m['record'](NAME)


if __name__=='__main__':result=apply()
