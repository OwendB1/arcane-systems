"""SE-style weld frames, exposed equipment and partial armor.
Run in either Arcane .blend; changes only construction collections.
Also reused by the Energy Core authoring script.
"""
import importlib
import json
import math
import re
from pathlib import Path
import bpy
import bmesh
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
COLS = importlib.import_module('space-engineers-utilities.seut_collections')
NAMES = ('ArcanePower_ReactorPrototype', 'ArcanePower_ContainmentController',
         'ArcanePower_AdvancedContainmentController', 'ArcanePower_VentDuct', 'ArcanePower_VentOutlet')
ENERGY = ('ArcanePower_EnergyCore', 'ArcanePower_EnergyCapacity', 'ArcanePower_EnergyCapacityAdvanced',
          'ArcanePower_EnergyTransfer', 'ArcanePower_EnergyTransferAdvanced',
          'ArcanePower_EnergyStabilizer', 'ArcanePower_EnergyStabilizerAdvanced')


def clean_mesh(mesh):
    bm = bmesh.new(); bm.from_mesh(mesh)
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    collapsed = [f for f in bm.faces if f.calc_area() < 1e-7]
    if collapsed: bmesh.ops.delete(bm, geom=collapsed, context='FACES_ONLY')
    bm.normal_update()
    uv = bm.loops.layers.uv.verify()
    for face in bm.faces:
        a, b, c = [loop[uv].uv.copy() for loop in face.loops]
        if abs((b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x)) > 1e-10: continue
        axes = [i for i in range(3) if i != max(range(3), key=lambda i: abs(face.normal[i]))]
        for loop in face.loops: loop[uv].uv = tuple(loop.vert.co[i]*.4 for i in axes)
    bm.to_mesh(mesh); bm.free(); mesh.update()


class Parts:
    """Batch construction pieces by material rather than thousands of objects."""
    def __init__(self, collection):
        self.collection, self.data = collection, {}

    def prism(self, points, a, b, material='Construction'):
        a, b = Vector(a), Vector(b)
        rotation = (b-a).to_track_quat('Z', 'Y').to_matrix()
        verts, faces = self.data.setdefault(material, ([], []))
        start, count = len(verts), len(points)
        verts.extend(a + rotation @ Vector((x, y, z))
                     for z in (0, (b-a).length) for x, y in points)
        faces.extend([tuple(start+i for i in reversed(range(count))),
                      tuple(start+count+i for i in range(count))])
        faces.extend((start+i, start+(i+1)%count, start+(i+1)%count+count, start+i+count)
                     for i in range(count))

    def beam(self, a, b, width, material='Construction', channel=True):
        h, t = width/2, width*.18
        # Open C-section with a web and two flanges, like native weld frames.
        points = [(-h,-h),(h,-h),(h,-h+t),(-h+t,-h+t),
                  (-h+t,h-t),(h,h-t),(h,h),(-h,h)] if channel else [(-h,-h),(h,-h),(h,h),(-h,h)]
        self.prism(points, a, b, material)

    def box(self, center, size, material='Construction'):
        x, y, z = size
        self.prism([(-x/2,-y/2),(x/2,-y/2),(x/2,y/2),(-x/2,y/2)],
                   Vector(center)-Vector((0,0,z/2)), Vector(center)+Vector((0,0,z/2)), material)

    def pipe(self, a, b, radius, material='Metal_Dull', sides=12):
        self.prism([(radius*math.cos(i*math.tau/sides), radius*math.sin(i*math.tau/sides))
                    for i in range(sides)], a, b, material)

    def ring(self, radius, z, width, count=16):
        points = [(radius*math.cos(i*math.tau/count), radius*math.sin(i*math.tau/count), z)
                  for i in range(count)]
        for a, b in zip(points, points[1:]+points[:1]): self.beam(a, b, width)

    def finish(self):
        for name, (verts, faces) in self.data.items():
            mesh = bpy.data.meshes.new('Build / '+name)
            mesh.from_pydata(verts, [], faces)
            mesh.materials.append(next(m for m in bpy.data.materials if m.name == name and m.library))
            clean_mesh(mesh)
            obj = bpy.data.objects.new('Build / welded '+name, mesh)
            self.collection.objects.link(obj)


def rectangular_frame(p, low, high, width, front=-1):
    low, high = Vector(low), Vector(high)
    for axis in range(3):
        other = [i for i in range(3) if i != axis]
        for u in (0,1):
            for v in (0,1):
                a, b = low.copy(), low.copy(); b[axis] = high[axis]
                for i, value in zip(other, (u,v)): a[i] = b[i] = high[i] if value else low[i]
                p.beam(a, b, width)
    # Diagonal webs leave the equipment face accessible.
    for x in (low.x, high.x):
        p.beam((x,low.y,low.z),(x,high.y,high.z),width*.7)
    y = high.y if front < 0 else low.y
    middle = (low.x+high.x)/2
    p.beam((low.x,y,low.z),(middle,y,high.z),width*.75)
    p.beam((middle,y,high.z),(high.x,y,low.z),width*.75)
    y = low.y if front < 0 else high.y
    for x, sx in ((low.x,1),(high.x,-1)):
        for z, sz in ((low.z,1),(high.z,-1)):
            reach = min((high.x-low.x)*.20, (high.z-low.z)*.20)
            p.beam((x+sx*reach,y,z),(x,y,z+sz*reach),width*.9)
            p.box((x+sx*width*.4,y,z+sz*width*.4),(width*1.5,width*.38,width*1.5))


def reactor_frame(p):
    for z in (-3.55,-1.5,3.04,3.55): p.ring(5.95,z,.26,24)
    for z in (-3.55,-1.5,3.55): p.ring(2.15,z,.20,16)
    for i in range(12):
        a, b = i*math.tau/12, (i+1)*math.tau/12
        xy = lambda r,t,z: (r*math.cos(t),r*math.sin(t),z)
        p.beam(xy(5.95,a,-3.55),xy(5.95,a,-1.5),.24)
        p.beam(xy(5.95,a,-3.55),xy(5.95,b,-1.5),.17)
        p.beam(xy(5.95,a,3.04),xy(5.95,a,3.55),.22)
        for z in (-3.55,-1.5,3.55): p.beam(xy(2.15,a,z),xy(5.95,a,z),.20)
    for i in range(4):
        a = math.pi/4+i*math.pi/2
        x,y = 5.0*math.cos(a),5.0*math.sin(a)
        p.beam((x,y,-1.5),(x,y,3.55),.38)
        for z in (-1.4,2.95): p.box((x,y,z),(.7,.7,.13))
        p.beam((x,y,2.0),(x*.68,y*.68,3.55),.23)


def vent_frame(p):
    outline = [(-3.15,-3.58),(3.15,-3.58),(3.58,-3.15),(3.58,3.15),
               (3.15,3.58),(-3.15,3.58),(-3.58,3.15),(-3.58,-3.15)]
    for z in (-1.1,1.1):
        for a,b in zip(outline,outline[1:]+outline[:1]): p.beam((*a,z),(*b,z),.23)
        p.ring(2.03,z,.19,16)
    for i,(x,y) in enumerate(outline):
        p.beam((x,y,-1.1),(x,y,1.1),.22)
        a = math.atan2(y,x)
        for z in (-1.1,1.1):
            p.beam((x,y,z),(2.03*math.cos(a),2.03*math.sin(a),z),.19)
        if i%2 == 0:
            end=outline[(i+1)%8]; mid=((x+end[0])/2,(y+end[1])/2)
            p.beam((x,y,-1.1),(*mid,1.1),.16)
            p.beam((*mid,1.1),(*end,-1.1),.16)


def reactor_equipment(p):
    for i in range(8):
        a=i*math.tau/8; x,y=4.65*math.cos(a),4.65*math.sin(a)
        p.pipe((x,y,-3.3),(x,y,-1.65),.32)
        for z in (-3.1,-2.4,-1.8): p.pipe((x,y,z-.06),(x,y,z+.06),.38,'Construction')
        p.beam((x*.75,y*.75,-3.25),(x*.75,y*.75,-1.7),.16,'Metal_Shiny',False)
        for z in (-3.18,-1.8): p.pipe((x*.75,y*.75,z),(x,y,z),.065)


def controller_equipment(p, advanced):
    for x in (-.43,0,.43) if advanced else (-.34,.34):
        p.box((x,-1.26,.16),(.34,.12,.68),'PaintedMetal_VeryDark')
        p.pipe((x,-1.12,-.10),(x,-1.12,.43),.105)
        for z in (-.03,.33): p.box((x,-1.08,z),(.26,.045,.045))
        p.pipe((x,-1.12,.45),(x,-1.12,.55),.033,'Metal_Shiny')
    p.box((0,-1.19,-.20),(1.48,.07,.075),'Metal_Shiny')
    p.box((0,-1.23,.52),(1.48,.12,.05))
    p.pipe((-.60,-1.13,.54),(.60,-1.13,.54),.025)


def energy_equipment(p, name):
    if name == ENERGY[0]:
        for i in range(8):
            a=i*math.tau/8; x,y=2.65*math.cos(a),2.65*math.sin(a)
            p.pipe((x,y,-3.15),(x,y,-2.40),.24)
            p.box((x,y,-2.8),(.55,.55,.10))
        for x in (-2.65,2.65):
            for y in (-2.65,2.65):
                p.pipe((x*.92,y*.92,-2.85),(x*.92,y*.92,2.85),.10,'Metal_Shiny')
                for z in (-2.6,0,2.6): p.box((x*.92,y*.92,z),(.35,.35,.12))
        p.ring(1.1,-2.75,.18)
        for z in (-1,1):
            for i in range(4):
                a=i*math.tau/4
                p.beam((2.1*math.cos(a),2.1*math.sin(a),z*2.79),
                       (2.65*math.cos(a),2.65*math.sin(a),z*3.43),.16)
        return
    p.box((0,0,-.95),(1.92,1.55,.12))
    if 'Capacity' in name:
        advanced=name.endswith('Advanced')
        for x in (-.58,0,.58) if advanced else (-.46,.46):
            radius=.25 if advanced else .34
            p.pipe((x,0,-.86),(x,0,.86),radius,'Metal_Dull',16)
            p.pipe((x,0,-.92),(x,0,-.80),radius*.6)
            for z in (-.68,0,.68): p.pipe((x,0,z-.05),(x,0,z+.05),radius+.04,'Construction',16)
            for z in (-.93,.93):
                p.pipe((x,0,z*.91),(x,0,z),.055,'Metal_Shiny')
                p.pipe((x,0,z),(x,-.5,z),.055,'Metal_Shiny')
        for z in (-.93,.93): p.box((0,-.5,z),(1.75,.13,.12),'Metal_Shiny')
    elif 'Transfer' in name:
        for x in (-.45,.45):
            p.box((x,0,0),(.5,.62,1.65),'PaintedMetal_VeryDark')
            for z in (-.65,-.43,-.21,.01,.23,.45,.67): p.box((x,-.02,z),(.65,.75,.08),'Metal_Dull')
        p.box((0,-.53,-.75),(1.6,.12,.17),'Metal_Shiny')
        p.box((0,.50,.78),(1.6,.12,.17),'Metal_Shiny')
    else:
        for i in range(16):
            a,b=i*math.tau/16,(i+1)*math.tau/16
            p.beam((.64*math.cos(a),0,.64*math.sin(a)),(.64*math.cos(b),0,.64*math.sin(b)),.20,'Metal_Shiny',False)
        for x in (-.66,.66): p.beam((x,0,-.9),(x,0,.9),.12)
        p.box((0,-.13,-.86),(1.7,.72,.22),'PaintedMetal_VeryDark')
        for x in (-.6,-.3,0,.3,.6): p.box((x,-.53,-.85),(.14,.12,.14),'Metal_Dull')
    p.box((0,.82,0),(1.82,.07,1.86),'PaintedMetal_VeryDark')
    for x in (-.73,0,.73): p.pipe((x,.65,-.84),(x,.65,.84),.035)


def service_opening(point):
    """Contiguous service bays keep panels and their fittings together."""
    angle=math.atan2(point.y,point.x)
    return -1.50 < angle < -.30 or 1.65 < angle < 2.30


def copy_part(source, collection, cut=None):
    mesh=bpy.data.meshes.new_from_object(source.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    if cut:
        bm=bmesh.new(); bm.from_mesh(mesh)
        bmesh.ops.triangulate(bm,faces=[f for f in bm.faces if len(f.verts)>4])
        remove=[f for f in bm.faces if cut(source.matrix_world @ f.calc_center_median())]
        if remove: bmesh.ops.delete(bm,geom=remove,context='FACES')
        bm.to_mesh(mesh); bm.free()
    if not mesh.polygons:
        bpy.data.meshes.remove(mesh); return
    raw=next(m for m in bpy.data.materials if m.library and m.name=='Construction')
    for i, material in enumerate(mesh.materials):
        if material and any(s in material.name for s in ('Emissive','ArcanePlasma','EnergyGlow','EnergyFill')): mesh.materials[i]=raw
    clean_mesh(mesh)
    obj=bpy.data.objects.new('Build / '+source.name,mesh)
    collection.objects.link(obj); obj.matrix_world=source.matrix_world.copy()


def installed_parts(name, meshes, collection, stage):
    if stage == 1: return
    for obj in meshes:
        n=obj.name
        center=obj.matrix_world @ (sum((Vector(v) for v in obj.bound_box),Vector())/8)
        cut=None
        if name == NAMES[0]:
            internals=n.startswith(('Structural','Spine bolted','Coolant riser','Pipe ',
                'Integrated support','AP dispenser / guide rail','Injector','AP floor / fixed','AP floor / solid central','Base upgrade / native socket'))
            if stage==2 and not internals: continue
            if n.startswith(('Curved chamber / pane','Spine status','AP floor / fuel','AP dispenser / fuel','AP vent / ceiling fuel')): continue
            if not internals:
                if n.startswith(('Lower machinery drum','Circular upper armored housing','Cap central service hatch','AP vent / bell backing')): cut=service_opening
                elif service_opening(center): continue
        elif 'Controller' in name:
            if n.startswith('Power pack / fuel status'): continue
            if n.startswith('Power pack / curved socket shell'):
                continue  # Separate sheets below leave a clean, rectangular service opening.
            elif stage==2:
                if not n.startswith('Power pack / retaining clip'): continue
            elif center.x > .02 and -.17 < center.z < .48: continue
        elif 'Vent' in name:
            if n.startswith(('Vent / status','VentTube / status')): continue
            internals=n.startswith(('Vent / inner liner','Vent / throat band','Vent / upper seat','VentTube /'))
            if stage==2 and not internals: continue
            if stage==3 and not internals:
                if n.startswith(('Vent / lower frame','Vent / flush rim','Vent / pocket wall')):
                    side=int(re.search(r' (\d+)',n).group(1))
                    if side in (0,1,6): continue
                elif center.y < -1.9 or center.x < -2.7: continue
        elif name==ENERGY[0]:
            if n.startswith(('Energy / pillar','Energy / frame rail','Energy / fill indicator')): continue
            if n.startswith('Energy / octagonal housing'):
                if stage==2: continue
                cut=service_opening
            elif obj.get('build_stage',3)>stage: continue
        else:
            # Replace the solid main chassis with separate partial sheets.
            if stage==2 and not n.startswith('Module / connector'): continue
            if stage==3 and not n.startswith(('Module / connector','Module / cell window','Module / transfer heatsink','Module / field vane')): continue
            if stage==3 and not n.startswith('Module / connector') and center.x > -.15: continue
        copy_part(obj,collection,cut=cut)


def build_stages(scene):
    bpy.context.window.scene=scene; bpy.context.view_layer.update()
    cols=COLS.get_collections(scene)
    meshes=sorted((o for o in cols['main'][0].objects if o.type=='MESH'),key=lambda o:o.name)
    existing={}
    for col in list(cols['bs'] or []):
        if col.seut.type_index in existing: bpy.data.collections.remove(col)
        else: existing[col.seut.type_index]=col
    report=[]
    for stage in range(1,4):
        collection=existing.get(stage)
        if collection is None:
            collection=bpy.data.collections.new('BS%d (%s)'%(stage,scene.name)); cols['seut'][0].children.link(collection)
            collection.seut.scene=scene; collection.seut.col_type='bs'; collection.seut.type_index=stage; collection.seut.version=3
        for obj in list(collection.objects): bpy.data.objects.remove(obj,do_unlink=True)
        p=Parts(collection); name=scene.name
        if name==NAMES[0]:
            reactor_frame(p)
            if stage>1: reactor_equipment(p)
        elif 'Vent' in name:
            vent_frame(p)
            if stage>1:
                for x in (-2.65,2.65):
                    p.pipe((x,-2.4,-.65),(x,2.4,-.65),.10)
                    for y in (-2.3,2.3): p.box((x,y,-.25),(.75,.7,.7),'Metal_Dull')
                if 'Outlet' in name:
                    for x in (-2.7,2.7): p.pipe((x,-1.5,.5),(x,1.5,.5),.19,'Metal_Shiny')
        elif 'Controller' in name:
            rectangular_frame(p,(-.755,-1.32,-.285),(.755,-1.045,.625),.055,front=1)
            if stage>1: controller_equipment(p,'Advanced' in name)
            if stage==3:
                p.box((-.38,-1.06,.17),(.72,.05,.88),'PaintedMetal_Darker')
                for z in (-.285,.625): p.box((0,-1.19,z),(1.50,.26,.065),'PaintedMetal_Colorable')
                p.box((-.755,-1.19,.17),(.055,.26,.88),'PaintedMetal_Colorable')
        elif name==ENERGY[0]:
            for z in (-3.43,3.43):
                p.ring(3.46,z,.24,8); p.ring(2.18,z,.18,16)
                for i in range(8):
                    a=i*math.tau/8
                    p.beam((2.18*math.cos(a),2.18*math.sin(a),z),(3.46*math.cos(a),3.46*math.sin(a),z),.18)
            rectangular_frame(p,(-2.65,-2.65,-3.43),(2.65,2.65,3.43),.30,front=1)
            if stage>1: energy_equipment(p,name)
        else:
            rectangular_frame(p,(-1.02,-1.02,-1.02),(1.02,1.02,1.02),.17)
            if stage>1: energy_equipment(p,name)
            if stage==3:
                for pos,size in (((-.57,-1.04,0),(1.03,.10,1.98)),((0,0,1.045),(1.98,1.98,.09)),((1.045,.33,0),(.09,1.32,1.98))):
                    p.box(pos,size,'PaintedMetal_Colorable')
                p.box((-.57,-1.10,.83),(.8,.025,.06),'Metal_Dull')
                p.box((-.57,-1.10,-.83),(.8,.025,.06),'Metal_Dull')
        p.finish(); installed_parts(name,meshes,collection,stage)
        if name==ENERGY[0] and stage==3 and 'ArcanePower_EnergyRotor' in bpy.data.scenes:
            rotor=COLS.get_collections(bpy.data.scenes['ArcanePower_EnergyRotor'])['main'][0]
            for obj in rotor.objects:
                if obj.type=='MESH': copy_part(obj,collection)
        report.append({'stage':stage,'meshes':sum(o.type=='MESH' for o in collection.objects),
                       'triangles':sum(len(p.vertices)-2 for o in collection.objects if o.type=='MESH' for p in o.data.polygons)})
        collection.hide_render=True
    scene.seut.export_sbc_type='none'; scene.seut.export_deleteLooseFiles=False
    def hide_stages(layer):
        if layer.collection.seut.col_type=='bs': layer.hide_viewport=True
        for child in layer.children: hide_stages(child)
    hide_stages(scene.view_layers[0].layer_collection)
    return report


def main():
    report={s.name:build_stages(s) for s in bpy.data.scenes if s.name in NAMES+ENERGY}
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
    path=ROOT/'validation'/('energy-construction-source.json' if any(n in ENERGY for n in report) else 'construction-stages.json')
    path.write_text(json.dumps({'style':'SE channel frames, diagonal webs, exposed equipment, partial cladding',
                               'source':report,'exported':False,'live_game_checked':False},indent=2)+'\n')
    print(json.dumps(report),flush=True)


if __name__=='__main__': main()
