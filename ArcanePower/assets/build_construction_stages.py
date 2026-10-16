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
from mathutils.bvhtree import BVHTree

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
        x,y = 5.6*math.cos(a),5.6*math.sin(a)
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


def energy_equipment(p, name):
    if name == ENERGY[0]:
        for i in range(8):
            a=i*math.tau/8; x,y=2.65*math.cos(a),2.65*math.sin(a)
            # Fit hidden equipment inside the finished drum, seated on its
            # spoke lattice instead of protruding into the clean chamber.
            p.pipe((x,y,-3.46),(x,y,-2.85),.24)
            p.box((x,y,-3.49),(.55,.55,.10))
        p.ring(1.1,-2.75,.18)
        for i in range(4):
            a=i*math.pi/2;x,y=1.1*math.cos(a),1.1*math.sin(a)
            p.beam((x,y,-3.52),(x,y,-2.75),.12)


def energy_frame(p,name):
    if name==ENERGY[0]:
        for z in (-3.60,3.60):
            for radius,width in ((3.46,.24),(2.18,.18),(1.10,.18)):p.ring(radius,z,width,24)
            for i in range(8):
                a=i*math.tau/8;n=Vector((math.cos(a),math.sin(a),0))
                p.beam(n*1.10+Vector((0,0,z)),n*3.46+Vector((0,0,z)),.18)
            sign=math.copysign(1,z);p.ring(2.35,sign*2.61,.14,24)
            for i in range(4):
                a=math.pi/4+i*math.pi/2;n=Vector((math.cos(a),math.sin(a),0))
                p.beam(n*2.18+Vector((0,0,z)),n*2.35+Vector((0,0,sign*2.61)),.14)
            for i in range(4):
                for side in (-1,1):
                    a=i*math.pi/2+side*.60;n=Vector((math.cos(a),math.sin(a),0))
                    p.beam(n*2.18+Vector((0,0,z)),n*2.86+Vector((0,0,sign*2.73)),.13)
        for i in range(4):
            a=i*math.pi/2;n=Vector((math.cos(a),math.sin(a),0));t=Vector((-n.y,n.x,0))
            def dock(x,z,r=3.44):return n*r+t*x+Vector((0,0,z))
            for x in (-.98,.98):p.beam(dock(x,-3.60),dock(x,3.60),.20)
            for z in (-3.40,-1.15,1.15,3.40):p.beam(dock(-.98,z),dock(.98,z),.18)
            for z in (-2.5,0,2.5):
                for x in (-.73,.73):p.beam(dock(x,z-.73,3.52),dock(x,z+.73,3.52),.12)
                for dz in (-.73,.73):
                    p.beam(dock(-.73,z+dz,3.52),dock(.73,z+dz,3.52),.12)
                    for sign in (-1,1):p.beam(dock(sign*.98,z+dz),dock(sign*.73,z+dz,3.52),.12)
        return
    # The current module has four posts at (+/- .96, +/- .78), and three
    # full-size native receivers on the curved mating side. No old backplanes.
    rectangular_frame(p,(-.96,-.78,-3.47),(.96,.78,3.47),.17)
    for z in (-1.15,1.15):
        for y in (-.78,.78):p.beam((-.96,y,z),(.96,y,z),.14)
    for z in (-2.5,0,2.5):
        for x in (-.73,.73):p.beam((x,1.03,z-.73),(x,1.03,z+.73),.12)
        for dz in (-.73,.73):
            p.beam((-.73,1.03,z+dz),(.73,1.03,z+dz),.12)
            for sign in (-1,1):p.beam((sign*.96,.78,z+dz),(sign*.73,1.03,z+dz),.12)


def service_opening(point):
    """Contiguous service bays keep panels and their fittings together."""
    angle=math.atan2(point.y,point.x)
    return -1.50 < angle < -.30 or 1.65 < angle < 2.30


def copy_part(source, collection, cut=None):
    # Applied main meshes can be copied directly. Evaluating the full scene
    # after every linked fitting makes detailed construction batches quadratic.
    mesh=(bpy.data.meshes.new_from_object(source.evaluated_get(bpy.context.evaluated_depsgraph_get()))
          if source.modifiers else source.data.copy())
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
        if material and any(s in material.name for s in ('Emissive','ArcanePlasma','EnergyGlow','EnergyFill','EnergyStatus')): mesh.materials[i]=raw
    clean_mesh(mesh)
    obj=bpy.data.objects.new('Build / '+source.name,mesh)
    collection.objects.link(obj); obj.matrix_world=source.matrix_world.copy()
    obj['source_object']=source.name
    return obj


def installed_energy_parts(name,meshes,collection,stage):
    """Install current assemblies atomically, including their small fittings."""
    if stage==1:return
    root=next(o for o in meshes[0].users_collection[0].objects if o.parent is None)
    authored=root.matrix_world.inverted()
    centers={o:authored @ o.matrix_world @ (sum((Vector(v) for v in o.bound_box),Vector())/8) for o in meshes}
    members={o.name:o for o in meshes};core=name==ENERGY[0]
    def matching(prefixes):return [o for o in meshes if o.name.startswith(prefixes)]
    def nearest(obj,prefixes):
        candidates=matching(prefixes)
        return min(candidates,key=lambda o:(centers[o]-centers[obj]).length_squared) if candidates else obj
    owners={}
    for obj in meshes:
        n=obj.name;owner=obj
        if obj.get('fastener_body') in members:owner=members[obj['fastener_body']]
        elif core:
            if n.startswith(('Energy / deck pull','Energy / flush deck pull','Energy / deck captive screw')):owner=nearest(obj,'Energy / radial service lid')
            elif n.startswith(('Energy / hatch seal','Energy / hatch bolt')):owner=nearest(obj,'Energy / central service hatch')
            elif n.startswith(('Energy / panel captive screw','Energy / panel pull','Marking / safety label backing','Marking / readable equipment')):owner=nearest(obj,'Energy / drum access panel')
            elif n.startswith(('Energy / drum cooling louver','Energy / service pocket floor')):owner=nearest(obj,'Energy / inset service receiver')
            elif n.startswith('Energy / recessed cooling slot'):owner=nearest(obj,'Energy / deck panel')
        else:
            if n.startswith(('Module / service pocket backing','Module / inset service door','Module / cooling pocket backing','Module / intake fin','Module / cooling screw boss','Module / cooling bank screw')):owner=nearest(obj,'Module / side armor')
            elif n.startswith(('Module / door captive screw','Module / service pull','Service / ')):owner=nearest(obj,'Module / inset service door')
            elif n.startswith(('Module / faceted end deck','Module / lift socket backing','Module / lift anchor foot','Module / recessed lift bar','Module / end load rib','Module / end deck screw','Module / end status bezel','Module / end bezel screw')):owner=nearest(obj,'Module / armored endcap')
            elif n.startswith(('Module / engraved ID tab','Marking / safety label backing')):owner=nearest(obj,('Module / armored endcap','Module / side armor'))
            elif n.startswith('Marking / equipment code'):owner=nearest(obj,'Module / engraved ID tab')
            elif n.startswith(('Marking / Sign Battery','Marking / readable equipment')):owner=nearest(obj,'Marking / safety label backing')
            elif n.startswith(('Module / spine status bezel','Module / service bolt','Module / bay corner gusset','Module / gusset captive screw')):owner=nearest(obj,'Module / front spine')
        owners[obj]=owner
    equipment=('Module / cassette retention rail','Module / cell clamp saddle','Module / cassette clamp bolt',
        'Module / split cell band','Module / clamp bridge','Module / split clamp bolt','Module / plated cell strap','Module / terminal washer','Module / cell terminal stud',
        'Module / power bus','Module / heatsink header','Module / cooling manifold','Module / manifold hex union','Module / manifold clamp','Module / bus insulator','Module / bus terminal',
        'Module / radiator fin','Module / heat exchanger mount bolt','Module / manifold return','Module / return hex union','Module / coolant valve body','Module / valve handle',
        'Module / fan carrier','Module / fan hub','Module / fan controller','Module / fan cable trunk','Module / controller cable','Module / controller return','Module / motor lead','Module / harness saddle',
        'Energy / coolant retaining shoe','Energy / coolant shoe screw','Energy / pole injector housing','Energy / pole injector nozzle','Energy / pole injector screw','Energy / injector coil feed')
    chosen={}
    def include(obj):
        if obj in chosen:return chosen[obj]
        n=obj.name;phase=obj.get('build_stage',3)
        if phase>3 or n.startswith(('Module / frame','Energy / machinery drum')):chosen[obj]=False
        elif owners[obj]!=obj:chosen[obj]=include(owners[obj])
        elif phase<=2 or n.startswith(equipment):chosen[obj]=True
        elif stage==2:chosen[obj]=False
        elif not core and n.startswith('Module / side armor'):chosen[obj]=centers[obj].x>0
        elif not core and n.startswith('Module / armored endcap'):chosen[obj]=centers[obj].z>0
        elif core and math.hypot(centers[obj].x,centers[obj].y)>2.45 and abs(centers[obj].z)>2.8:
            sector=int(((math.atan2(centers[obj].y,centers[obj].x)%math.tau)+.00001)/(math.tau/12))%12
            chosen[obj]=sector not in (3,8,9)
        else:chosen[obj]=True
        return chosen[obj]
    for obj in meshes:
        if not include(obj):continue
        # Cooling slots over intentionally absent roof panels wait for the
        # finished drum. Other assemblies retain their actual closed solids.
        if core and obj.name.startswith('Energy / recessed cooling slot'):
            a,b=centers[obj],centers[owners[obj]]
            if abs((math.atan2(a.y,a.x)-math.atan2(b.y,b.x)+math.pi)%math.tau-math.pi)>.20:continue
        copy=copy_part(obj,collection)
        if copy:copy['source_owner']=owners[obj].name


def installed_parts(name, meshes, collection, stage):
    if stage == 1: return
    if name in ENERGY:
        installed_energy_parts(name,meshes,collection,stage)
        return
    if name==NAMES[0] or 'Controller' in name:
        installed_current_prototype(name,meshes,collection,stage)
        return
    for obj in meshes:
        n=obj.name
        center=obj.matrix_world @ (sum((Vector(v) for v in obj.bound_box),Vector())/8)
        cut=None
        if 'Vent' in name:
            if n.startswith(('Vent / status','VentTube / status')): continue
            internals=n.startswith(('Vent / inner liner','Vent / throat band','Vent / upper seat','VentTube /'))
            if stage==2 and not internals: continue
            if stage==3 and not internals:
                if n.startswith(('Vent / lower frame','Vent / flush rim','Vent / pocket wall')):
                    side=int(re.search(r' (\d+)',n).group(1))
                    if side in (0,1,6): continue
                elif center.y < -1.9 or center.x < -2.7: continue
        copy_part(obj,collection,cut=cut)


def installed_current_prototype(name,meshes,collection,stage):
    """Use current mounted assemblies; fittings follow their actual support."""
    members={o.name:o for o in meshes};core=name==NAMES[0]
    centers={o:o.matrix_world @ (sum((Vector(v) for v in o.bound_box),Vector())/8) for o in meshes}
    def nearest(obj,prefixes):
        candidates=[o for o in meshes if o.name.startswith(prefixes)]
        return min(candidates,key=lambda o:(centers[o]-centers[obj]).length_squared) if candidates else obj
    owners={}
    for obj in meshes:
        n=obj.name;owner=obj
        for key in ('texture_support','fastener_body','support'):
            if obj.get(key) in members:owner=members[obj[key]];break
        if owner==obj and core:
            if n.startswith('Reactor exterior /') and any(t in n for t in ('door','louver','pocket','hinge','equipment number','pull','captive screw','native screw face','divider','mullion')):
                owner=nearest(obj,'Reactor exterior / service receiver')
            elif n.startswith('Reactor exterior /') and any(t in n for t in ('pillar','side cover','inner cover','cooling vane')) and 'jacket' not in n:
                owner=nearest(obj,'Reactor exterior / chamfered pillar jacket')
            elif n.startswith('AP dispenser /') and 'corner cradle' not in n:
                owner=nearest(obj,'AP dispenser / corner cradle')
        elif owner==obj and not core and n.startswith('Controller detail /'):
            if any(t in n for t in ('cassette pull','cassette release','cassette pressed')):owner=nearest(obj,'Controller detail / broad service cassette')
            elif any(t in n for t in ('fin saddle','cartridge heat','bus terminal')):owner=nearest(obj,'Controller detail / paired power cartridge')
            elif any(t in n for t in ('status lamp seat','tier number')):owner=nearest(obj,'Controller detail / status carrier')
        owners[obj]=owner
    chosen={}
    def include(obj):
        if obj in chosen:return chosen[obj]
        n=obj.name;p=centers[obj]
        powered=any(m and any(t in m.name for t in ('Emissive','ArcanePlasma','ClearChamber','EnergyGlow','EnergyFill','EnergyStatus')) for m in obj.data.materials)
        if powered or n.startswith(('Curved chamber / pane','Spine status','AP floor / fuel','AP floor / island fuel','AP dispenser / fuel','AP vent / ceiling fuel')):answer=False
        elif owners[obj]!=obj:answer=include(owners[obj])
        elif core:
            structural=n.startswith(('Coolant riser','Pipe coupling','Injector','AP floor / fixed','AP floor / solid central','Base upgrade / native socket','AP upgrade socket / integrated','Reactor exterior / chamfered pillar jacket','Reactor exterior / fitted','AP dispenser / corner cradle'))
            if stage==2:answer=structural
            else:answer=structural or not service_opening(p)
        else:
            # Equipment is attached to the weld frame before the casing closes.
            equipment=n.startswith(('Controller detail / lower retention','Controller detail / retention rail','Controller detail / broad service','Controller detail / paired power','Controller detail / connected power','Controller detail / power bus','Controller detail / bus spine'))
            answer=equipment if stage==2 else p.x<.55 or n.startswith('Power pack / curved socket shell')
        chosen[obj]=answer;return answer
    for obj in meshes:
        if not include(obj):continue
        cut=None
        if core and obj.name.startswith(('Lower machinery drum','Circular upper armored housing','Cap central service hatch','AP vent / bell backing')):cut=service_opening
        elif not core and obj.name.startswith('Power pack / curved socket shell'):cut=lambda p:p.x>.55 and p.y>-1.28
        copy=copy_part(obj,collection,cut)
        if copy:copy['source_owner']=owners[obj].name
    # Do not install a decal or screw on a face removed for a service opening.
    copies={o.get('source_object'):o for o in collection.objects if o.get('source_object')}
    for obj in list(collection.objects):
        source=members.get(obj.get('source_object'))
        if not source:continue
        missing=owners[source]!=source and owners[source].name not in copies
        if source.get('texture_support') and not missing:
            support=copies[source['texture_support']]
            tree=BVHTree.FromPolygons([support.matrix_world @ v.co for v in support.data.vertices],[tuple(p.vertices) for p in support.data.polygons])
            normal=(obj.matrix_world.to_3x3() @ obj.data.polygons[0].normal).normalized()
            missing=any(tree.ray_cast(obj.matrix_world @ v.co,-normal,.008)[0] is None for v in obj.data.vertices)
        if missing:bpy.data.objects.remove(obj,do_unlink=True)


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
            # Current cassettes seat at Y=-1.070. Weld rails reach their backs
            # and tie into both side frames before the finished casing exists.
            for z in (-.06,.31):
                p.beam((-.755,-1.09,z),(.755,-1.09,z),.045)
                for x in (-.755,.755):p.beam((x,-1.32,z),(x,-1.045,z),.045)
        elif name in ENERGY:
            energy_frame(p,name)
            if stage>1: energy_equipment(p,name)
        p.finish()
        if name in ENERGY:
            # Respect the energy author's root orientation when rebuilding from
            # the saved .blend as well as during initial procedural authoring.
            root=next(o for o in cols['main'][0].objects if o.parent is None)
            for obj in collection.objects:obj.matrix_world=root.matrix_world @ obj.matrix_world
        installed_parts(name,meshes,collection,stage)
        if name in ENERGY and stage>=2:
            for dummy in cols['main'][0].objects:
                if not (dummy.name.startswith('subpart_EnergyFan') or stage==3 and dummy.name.startswith('subpart_EnergyRing')):continue
                subpart=bpy.data.scenes.get(dummy.get('file',''))
                if subpart is None:raise ValueError('Missing construction subpart: '+dummy.name)
                pose=dummy.matrix_world.copy()
                bpy.context.window.scene=subpart;bpy.context.view_layer.update()
                for obj in COLS.get_collections(subpart)['main'][0].objects:
                    if obj.type=='MESH':
                        copy=copy_part(obj,collection)
                        if copy:
                            copy.matrix_world=pose @ obj.matrix_world
                            copy['source_owner']=dummy.name;copy['construction_static_subpart']=subpart.name
                bpy.context.window.scene=scene;bpy.context.view_layer.update()
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
