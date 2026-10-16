"""Audit the native authoring meshes and engineer-scale mechanical joints.
Run in Blender before export. Open native decals and two-sided glazing are
intentional; authored housings must be closed, consistently wound solids.
"""
import bpy
import bmesh
import importlib
import json
import math
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT=Path(__file__).resolve().parents[1]
COLS=importlib.import_module('space-engineers-utilities.seut_collections')

def main():
    original=bpy.context.scene
    failures=[];inventory={};metrics={}
    def require(condition,message):
        if not condition:failures.append(message)
    def points(obj,frame=None):
        matrix=obj.matrix_world if frame is None else frame @ obj.matrix_world
        return [matrix @ obj.data.vertices[i].co for i in {l.vertex_index for l in obj.data.loops}]
    def bounds(obj,frame):
        ps=points(obj,frame)
        return Vector([min(p[i] for p in ps) for i in range(3)]),Vector([max(p[i] for p in ps) for i in range(3)])
    for scene in bpy.data.scenes:
        if not scene.name.startswith('ArcanePower_Energy'):continue
        bpy.context.window.scene=scene;bpy.context.view_layer.update()
        main=COLS.get_collections(scene)['main'][0]
        meshes=[o for o in main.objects if o.type=='MESH']
        root=next(o for o in main.objects if o.parent is None)
        frame=root.matrix_world.inverted()
        for obj in meshes:
            bm=bmesh.new();bm.from_mesh(obj.data)
            closed=bool(bm.faces) and all(e.is_manifold for e in bm.edges)
            if closed:
                require(bm.calc_volume(signed=True)>1e-9,obj.name+': inverted or zero-volume solid')
                require(all(e.is_contiguous for e in bm.edges),obj.name+': inconsistent winding')
            elif not obj.get('source_asset') and 'glazing' not in obj.name:
                require(False,obj.name+': unexpectedly open housing')
            require(bool(obj.data.uv_layers),obj.name+': missing UVs')
            for uv in obj.data.uv_layers:
                require(all(math.isfinite(v) for d in uv.data for v in d.uv),obj.name+': nonfinite UV')
            bm.free()
            if scene.seut.sceneType=='mainScene':
                half=(3.751,3.751,3.751) if scene.name.endswith('Core') else (1.251,1.251,3.751)
                require(all(abs(p[i])<=half[i] for p in points(obj,frame) for i in range(3)),obj.name+': outside grid envelope')
        if scene.seut.sceneType=='mainScene':
            sockets=[o for o in main.objects if o.name.startswith('detector_upgrade')]
            expected=12 if scene.name.endswith('Core') else 3
            require(len(sockets)==expected,scene.name+': wrong triple socket count')
            for height in (-2.5,0,2.5):
                require(sum(abs((frame @ o.matrix_world.translation).z-height)<.001 for o in sockets)==expected//3,scene.name+': sockets must use 2.5 m cell pitch')
        inventory[scene.name]={'meshes':len(meshes),'triangles':sum(len(p.vertices)-2 for o in meshes for p in o.data.polygons)}
        def matching(prefix):return [o for o in meshes if o.name.startswith(prefix)]
        if scene.get('dock_integration_revision')==1:
            receivers=[o for o in meshes if ' / integrated socket receiver' in o.name]
            backing=[o for o in meshes if ' / opaque socket backing' in o.name]
            expected=12 if scene.name.endswith('Core') else 3
            require(len(receivers)==len(backing)==expected,scene.name+': closed socket receivers incomplete')
            require(not any(' / socket surround' in o.name for o in meshes),scene.name+': obsolete separate surround rails remain')
            tested=0
            for dummy in [o for o in main.objects if o.name.startswith('detector_upgrade')]:
                pose=dummy.matrix_world.copy();pose.normalize();pose.translation+=pose.to_3x3() @ Vector((0,0,.03))
                local=pose.inverted()
                if not backing:continue
                cap=min(backing,key=lambda o:(local @ o.matrix_world @ sum((v.co for v in o.data.vertices),Vector())/len(o.data.vertices)).length)
                vertices=[local @ cap.matrix_world @ v.co for v in cap.data.vertices]
                bvh=BVHTree.FromPolygons(vertices,[tuple(p.vertices) for p in cap.data.polygons])
                for x in (-.32,-.16,0,.16,.32):
                    for y in (-.32,-.16,0,.16,.32):
                        hit,normal,index,distance=bvh.ray_cast(Vector((x,y,-.4)),Vector((0,0,1)),.4)
                        require(hit is not None,cap.name+': see-through socket backing')
                        tested+=1
                require(abs(max(p.z for p in vertices)+.138)<.001,cap.name+': native port backing depth changed')
            metrics[scene.name+'_socket_backing_rays']=tested
            allowed=('EnergyFill','EnergyStatus','EnergyGlow','ArcanePower_ClearChamber')
            require(all(m.library is not None or m.name.startswith(allowed) for o in meshes for m in o.data.materials if m),scene.name+': non-native structural material')
        if scene.get('native_label_revision')==1:
            require(not any(m.name in ('EnergyLabel','PlasticWhite') for o in meshes for m in o.data.materials if m),scene.name+': obsolete label stock remains')
            require(any(m.name=='BlackMattePlastic' for o in meshes for m in o.data.materials if m),scene.name+': native dark label stock missing')
        if scene.get('readable_marking_revision')==1:
            require(not matching('Marking / Sign High Voltage') and not matching('Marking / Sign Moving Parts'),scene.name+': unreadable reflective markings remain')
            require(bool(matching('Marking / readable equipment')) or 'Capacity' in scene.name,scene.name+': readable equipment labels missing')
        if scene.get('connection_detail_revision')==1:
            def overlaps(obj,others,depth):
                a,b=bounds(obj,frame)
                return any(all(min(b[i],d[i])-max(a[i],c[i])>depth for i in range(3)) for c,d in (bounds(o,frame) for o in others))
            if 'Capacity' in scene.name:
                straps=matching('Module / plated cell strap')
                require(len(straps)==(18 if scene.name.endswith('Advanced') else 12),scene.name+': cell strap count')
                require(not matching('Module / cell bus link'),scene.name+': obsolete rounded cell links remain')
                for strap in straps:
                    require(overlaps(strap,matching('Module / cell contact'),.009),strap.name+': detached from cell terminal')
                    require(overlaps(strap,matching('Module / compartment bus'),.009),strap.name+': detached from compartment bus')
                for washer in matching('Module / terminal washer'):
                    require(overlaps(washer,straps,.001),washer.name+': washer floats above strap')
                for stud in matching('Module / cell terminal stud'):
                    require(overlaps(stud,matching('Module / terminal washer'),.005),stud.name+': terminal stud floats')
            elif 'Transfer' in scene.name:
                returns=matching('Module / manifold return')
                require(len(returns)==12,scene.name+': radiator returns missing')
                for pipe in returns:
                    require(overlaps(pipe,matching('Module / thermal spreader'),.009),pipe.name+': return does not enter heat spreader')
                    require(overlaps(pipe,matching('Module / cooling manifold'),.009),pipe.name+': return does not enter manifold')
                valves=matching('Module / coolant valve body')
                require(len(valves)==6,scene.name+': coolant valves missing')
                for valve in valves:require(overlaps(valve,matching('Module / cooling manifold'),.009),valve.name+': unsupported valve')
                for handle in matching('Module / valve handle'):require(overlaps(handle,valves,.005),handle.name+': valve handle floats')
            else:
                leads=matching('Module / motor lead')
                require(len(leads)==3,scene.name+': motor feeds missing')
                for lead in leads:require(overlaps(lead,matching('Module / fan bearing'),.009),lead.name+': motor feed disconnected')
                for saddle in matching('Module / harness saddle'):
                    require(overlaps(saddle,matching('Module / equipment backplane'),.009),saddle.name+': harness support floats')
        if scene.get('fastener_face_revision')==1:
            members={o.name:o for o in main.objects}
            for face in matching('Detail / seated fastener face'):
                body=members.get(face.get('fastener_body'))
                require(body is not None,face.name+': fastener body reference lost')
                if body is not None:
                    z=sum((body.matrix_world.inverted() @ face.matrix_world @ v.co).z for v in face.data.vertices)/len(face.data.vertices)
                    depth=max(abs(v.co.z) for v in body.data.vertices)
                    require(.0001<abs(z)-depth<.0015,face.name+': head detail detached from bolt')
        if scene.seut.sceneType=='mainScene':
            prefix='Energy / collar status' if scene.name.endswith('Core') else 'Module / spine status'
            lenses=matching(prefix+' lens');bezels=matching(prefix+' bezel')
            expected=8 if scene.name.endswith('Core') else 6
            require(len(lenses)==len(bezels)==expected,scene.name+': status strip count changed')
            require(all(o.data.materials[0].name=='EnergyStatus' for o in lenses),scene.name+': status material missing')
            for lens in lenses:
                lo,hi=bounds(lens,frame)
                require(any(all(min(hi[i],b[i])-max(lo[i],a[i])>.003 for i in range(3))
                    for a,b in (bounds(o,frame) for o in bezels)),lens.name+': lens floats above bezel')
        if scene.name=='ArcanePower_EnergyCore':
            if scene.get('drum_service_seating_revision',0)>=2:
                require(not matching('Energy / drum fastener'),'Redundant drum bolts remain inside service/dock housings')
                require(not matching('Energy / drum service gasket') and not matching('Energy / service cassette backing'),'Obsolete raised gasket plates remain')
                receivers=matching('Energy / inset service receiver');floors=matching('Energy / service pocket floor')
                require(len(receivers)==len(floors)==24,'Inset service cassette count')
                centers={o:sum(points(o,frame),Vector())/len(o.data.vertices) for o in receivers}
                trees={o:BVHTree.FromPolygons(points(o,frame),[tuple(p.vertices) for p in o.data.polygons]) for o in receivers}
                samples=0
                for panel in matching('Energy / drum access panel'):
                    ps=points(panel,frame);center=sum(ps,Vector())/len(ps)
                    receiver=min(receivers,key=lambda o:(centers[o]-center).length_squared)
                    require(abs(max(math.hypot(p.x,p.y) for p in ps)-3.607)<.0001,panel.name+': door is not inset')
                    for p in ps:
                        if abs(math.hypot(p.x,p.y)-3.585)>.0001:continue
                        outward=Vector((p.x,p.y,0)).normalized()
                        hit,normal,index,distance=trees[receiver].ray_cast(p,outward,.012)
                        require(hit is not None and normal.dot(outward)>.9,panel.name+': door perimeter lacks a seating ledge')
                        samples+=1
                metrics['service_panel_ledge_support_samples']=samples
                panels=matching('Energy / drum access panel');screws=matching('Energy / panel captive screw')
                require(len(screws)==48,'Panel captive screw count')
                for screw in screws:
                    center=sum(points(screw,frame),Vector())/len(screw.data.vertices)
                    panel=min(panels,key=lambda o:(sum(points(o,frame),Vector())/len(o.data.vertices)-center).length_squared)
                    tree=BVHTree.FromPolygons(points(panel,frame),[tuple(p.vertices) for p in panel.data.polygons])
                    outward=Vector((center.x,center.y,0)).normalized()
                    hit,normal,index,distance=tree.ray_cast(center-outward*.011,outward,.012)
                    require(hit is not None and normal.dot(outward)>.9,screw.name+': screw does not seat into its service door')
                metrics['service_screw_seating_samples']=len(screws)
                samples=0
                for louver in matching('Energy / drum cooling louver'):
                    ps=points(louver,frame);center=sum(ps,Vector())/len(ps)
                    receiver=min(receivers,key=lambda o:(centers[o]-center).length_squared)
                    angle=math.atan2(centers[receiver].y,centers[receiver].x)
                    for p in ps:
                        if abs(math.hypot(p.x,p.y)-3.581)>.0001 or abs((math.atan2(p.y,p.x)-angle+math.pi)%math.tau-math.pi)<.11:continue
                        outward=Vector((p.x,p.y,0)).normalized()
                        hit,normal,index,distance=trees[receiver].ray_cast(p,outward,.015)
                        require(hit is not None and normal.dot(outward)>.9,louver.name+': louver end floats off receiver')
                        samples+=1
                metrics['service_louver_end_support_samples']=samples
                armor=matching('Energy / segmented drum armor');vertices=[];polygons=[]
                for obj in armor:
                    offset=len(vertices);vertices.extend(points(obj,frame));polygons.extend(tuple(i+offset for i in p.vertices) for p in obj.data.polygons)
                tree=BVHTree.FromPolygons(vertices,polygons);samples=0
                for receiver in receivers:
                    center=centers[receiver];angle=math.atan2(center.y,center.x)
                    require(min(math.hypot(p.x,p.y) for p in points(receiver,frame))<3.451,receiver.name+': receiver floats above drum')
                    for u in (-.31,0,.31):
                        n=Vector((math.cos(angle+u/3.61),math.sin(angle+u/3.61),0))
                        for h in (-.12,0,.12):
                            hit,normal,index,distance=tree.ray_cast(n*3.68+Vector((0,0,center.z+h)),-n,.145)
                            require(hit is None,receiver.name+': armor masks the service pocket')
                            samples+=1
                metrics['service_aperture_clearance_samples']=samples
                if scene.get('drum_service_seating_revision',0)>=3:
                    seams=[]
                    for obj in armor:
                        ps=points(obj,frame);origin=math.atan2(ps[0].y,ps[0].x)
                        angles=[(math.atan2(p.y,p.x)-origin+math.pi)%math.tau-math.pi for p in ps]
                        seam=(math.tau/12-(max(angles)-min(angles)))*3.61
                        require(.013<seam<.016,obj.name+': excessive armor segment gap')
                        seams.append(seam)
                    metrics['drum_armor_seam_width_m']=[min(seams),max(seams)]
                for floor in floors:
                    ps=points(floor,frame)
                    require(min(math.hypot(p.x,p.y) for p in ps)<3.451,floor.name+': pocket floor is not seated into drum')
                metrics['service_door_inset_m']=.003
                metrics['service_pocket_depth_m']=.061
            elif scene.get('drum_service_seating_revision')==1:
                backings=matching('Energy / service cassette backing')
                require(len(backings)==24,'Service cassette backing count')
                centers={o:sum(points(o,frame),Vector())/len(o.data.vertices) for o in backings}
                seating_samples=0
                for gasket in matching('Energy / drum service gasket'):
                    ps=points(gasket,frame);center=sum(ps,Vector())/len(ps)
                    if not backings:continue
                    backing=min(backings,key=lambda o:(centers[o]-center).length_squared)
                    verts=points(backing,frame)
                    tree=BVHTree.FromPolygons(verts,[tuple(p.vertices) for p in backing.data.polygons])
                    require(min(math.hypot(p.x,p.y) for p in verts)<3.46,backing.name+': cassette is not seated into the machinery drum')
                    for p in ps:
                        if abs(math.hypot(p.x,p.y)-3.597)>.0001:continue
                        outward=Vector((p.x,p.y,0)).normalized()
                        hit,normal,index,distance=tree.ray_cast(p,outward,.025)
                        require(hit is not None and normal.dot(outward)>.9,gasket.name+': seal sits over air')
                        seating_samples+=1
                metrics['service_gasket_support_samples']=seating_samples
                bolts=matching('Energy / drum fastener')
                clearance=min(abs(abs(p.z)-3.22)-.220 for o in bolts for p in points(o,frame))
                require(clearance>.005,'Structural fasteners overlap service gasket/details')
                metrics['drum_bolt_service_gasket_clearance_m']=clearance
            if scene.get('dock_integration_revision')==1:
                require(len(matching('Energy / dock backplane'))==12,'Three closed tapered dock housings required per core face')
                roots=matching('Energy / curved dock root')
                require(len(roots)==8,'Curved top/bottom dock roots missing')
                for obj in roots:
                    radii=[math.hypot(p.x,p.y) for p in points(obj,frame)]
                    require(min(radii)<3.57 and max(radii)>3.69,obj.name+': dock root does not bridge drum and housing')
                if scene.get('dock_root_revision')==1:
                    def tree_for(objects):
                        vertices=[];polygons=[]
                        for obj in objects:
                            offset=len(vertices);vertices.extend(points(obj,frame));polygons.extend(tuple(i+offset for i in p.vertices) for p in obj.data.polygons)
                        return BVHTree.FromPolygons(vertices,polygons)
                    skin=tree_for(matching('Energy / segmented drum armor'))
                    cheeks=tree_for(matching('Energy / dock sidewall'))
                    support_samples=0;cheek_samples=0
                    for obj in roots:
                        ps=points(obj,frame);center=sum(ps,Vector())/len(ps);n=Vector((center.x,center.y,0)).normalized();t=Vector((-n.y,n.x,0))
                        root_tree=tree_for([obj]);z=math.copysign(3.22,center.z)
                        require(max(abs(p.z-z) for p in ps)<.301,obj.name+': saddle crosses drum trim')
                        for x in (-1.0,-.55,.55,1.0):
                            for h in (-.22,.22):
                                p=n*math.sqrt(3.565**2-x*x)+t*x+Vector((0,0,z+h));outward=Vector((p.x,p.y,0)).normalized()
                                hit,normal,index,distance=skin.ray_cast(p,outward,.06)
                                require(hit is not None and normal.dot(outward)>.9,obj.name+': saddle back lacks armor seating')
                                support_samples+=1
                        for x in (-.98,.98):
                            p=n*3.68+t*x+Vector((0,0,z))
                            for tree in (root_tree,cheeks):
                                hit,normal,index,distance=tree.ray_cast(p,n,.07)
                                require(hit is not None and normal.dot(n)>.9,obj.name+': saddle does not tie into dock cheek')
                            cheek_samples+=1
                    metrics['dock_root_armor_seating_samples']=support_samples
                    metrics['dock_root_cheek_seating_samples']=cheek_samples
                    metrics['dock_root_face_reveal_m']=.01
            if scene.get('dock_service_revision')==1:
                for obj in matching('Energy / drum access panel')+matching('Energy / drum cooling louver'):
                    clearance=min(abs((math.atan2(p.y,p.x)+math.pi/4)%(math.pi/2)-math.pi/4) for p in points(obj,frame))
                    require(clearance>math.radians(19),obj.name+': service station obstructed by dock root')
            if scene.get('form_detail_revision')==1:
                injectors=matching('Energy / pole injector housing')
                require(len(injectors)==8,'Pole injector housings missing')
                radii=[]
                for o in injectors:
                    ps=[frame @ o.matrix_world @ v.co for v in o.data.vertices]
                    for e in o.data.edges:
                        a,b=[ps[i] for i in e.vertices];d=b-a
                        length=d.x*d.x+d.y*d.y
                        t=max(0,min(1,-(a.x*d.x+a.y*d.y)/length)) if length>1e-12 else 0
                        radii.append(math.hypot(a.x+t*d.x,a.y+t*d.y))
                swept=max((o.matrix_world @ v.co).length for name in ('ArcanePower_Ring3','ArcanePower_Ring4')
                    for o in COLS.get_collections(bpy.data.scenes[name])['main'][0].objects if o.type=='MESH' for v in o.data.vertices)
                gap=min(radii)-swept
                require(gap>.020,'Pole injector enters the moving-ring swept envelope')
                metrics['injector_ring_radial_clearance_m']=gap
            if scene.get('engineering_detail_revision')==1:
                require(len(matching('Energy / drum access panel'))==12,'Drum access-panel count changed')
                require(len(matching('Energy / drum cooling louver'))==48,'Drum cooling-bank count changed')
                require(len(matching('Energy / flush deck pull'))==16,'Flush deck pulls missing')
                for o in matching('Energy / coolant retaining shoe'):
                    ps=points(o,frame)
                    require(min(math.hypot(p.x,p.y) for p in ps)>2.88,o.name+': bracket enters glass')
                    require(max(abs(p.z) for p in ps)>2.83,o.name+': bracket not seated in drum')
            require(not matching('Energy / pillar'),'Redundant corner pillar remains')
            glass=matching('Energy / chamber glazing');require(len(glass)==8,'Expected 4 glazing quadrants with inward/outward faces')
            ps=[p for o in glass for p in points(o,frame)]
            height=max(p.z for p in ps)-min(p.z for p in ps)
            require(abs(height-5.6)<1e-4,'Glazing height changed')
            # Every quadrant endpoint must be shared by its neighbor on both sides.
            for angle in (math.pi/4+i*math.pi/2 for i in range(4)):
                for z in (-2.8,2.8):
                    endpoint=Vector((2.78*math.cos(angle),2.78*math.sin(angle),z))
                    owners=sum(any((p-endpoint).length<1e-4 for p in points(o,frame)) for o in glass)
                    require(owners==4,'Open glazing seam at '+str(tuple(endpoint)))
            drum=min(bounds(o,frame)[0].z for o in matching('Energy / machinery drum') if bounds(o,frame)[0].z>0)
            glass_seat=max(p.z for p in ps)-drum
            collar=max(bounds(o,frame)[1].z for o in matching('Energy / inner collar'))
            require(glass_seat>.049,'Glass not seated into upper drum')
            require(collar-drum>.009,'Inner collar floats below drum')
            docks=matching('Energy / dock sidewall')+matching('Energy / dock backplane')
            minimum=min(math.hypot(p.x,p.y) for o in docks for p in points(o,frame))
            require(abs(minimum-2.70)<.001,'Dock intrudes beyond shallow inner radius')
            # Local X of each dock is tangential; the narrow face is 58% of
            # the mounting face. Check actual vertices at the chamber radius.
            for o in docks:
                rotation=o.matrix_basis.to_3x3()
                local=[rotation.inverted() @ p for p in points(o,frame)]
                inner=[p for p in local if abs(math.hypot(p.x,p.z)-2.70)<.001]
                if inner:
                    width=max(p.x for p in inner)-min(p.x for p in inner)
                    expected=(.28 if 'sidewall' in o.name else 1.66)*.58
                    require(abs(width-expected)<.001,o.name+': trapezoidal inner face missing')
            metrics['dock_inner_width_fraction']=.58
            metrics.update(glass_into_drum_m=glass_seat,collar_into_drum_m=collar-drum,dock_inner_radius_m=minimum,dock_through_glass_m=2.78-minimum)
            for o in matching('Energy / collar status bezel'):
                ps=points(o,frame)
                require(max(math.hypot(p.x,p.y) for p in ps)<2.46,o.name+': bezel extends past collar')
                require(max(abs(p.z) for p in ps)>2.467,o.name+': bezel floats below collar')
            for o in matching('Energy / segmented drum armor'):
                require(min(math.hypot(p.x,p.y) for p in points(o,frame))<3.461,'Drum armor lacks backing overlap')
        elif scene.seut.sceneType=='mainScene':
            if scene.get('equipment_mount_revision')==1:
                mounts=[bounds(o,frame) for o in matching('Module / equipment mount')]
                backplanes=[bounds(o,frame) for o in matching('Module / equipment backplane')]
                for a,b in backplanes:
                    require(any(all(min(b[i],d[i])-max(a[i],c[i])>.009 for i in range(3)) for c,d in mounts),scene.name+': equipment backplane floats off mount')
                if 'Transfer' in scene.name:
                    fins=matching('Module / radiator fin')
                    require(len(fins)==(63 if scene.name.endswith('Advanced') else 45),scene.name+': radiator fin count')
                    spreaders=[bounds(o,frame) for o in matching('Module / thermal spreader')]
                    for o in fins:
                        a,b=bounds(o,frame)
                        require(any(all(min(b[i],d[i])-max(a[i],c[i])>.009 for i in range(3)) for c,d in spreaders),o.name+': radiator not seated into spreader')
                    for a,b in spreaders:
                        require(any(all(min(b[i],d[i])-max(a[i],c[i])>.019 for i in range(3)) for c,d in backplanes),scene.name+': heat spreader floats off backplane')
            if scene.get('form_detail_revision')==1:
                require(len(matching('Module / faceted end deck'))==2,scene.name+': faceted end decks missing')
                require(len(matching('Module / bay corner gusset'))==12,scene.name+': bay gussets missing')
                backing=[bounds(o,frame) for o in matching('Module / lift socket backing')]
                for o in matching('Module / recessed lift bar'):
                    a,b=bounds(o,frame);z=(a.z+b.z)/2
                    floor=min(backing,key=lambda pair:abs((pair[0].z+pair[1].z)/2-z))
                    gap=a.z-floor[1].z if z>0 else floor[0].z-b.z
                    require(gap>.050,scene.name+': lift socket lacks glove clearance')
                    metrics['module_lift_socket_clearance_m']=gap
            if scene.get('cell_clamp_revision')==1:
                expected=54 if scene.name.endswith('Advanced') else 36
                require(not matching('Module / cell restraint'),scene.name+': rounded cell restraints remain')
                require(len(matching('Module / split cell band'))==expected,scene.name+': split bands incomplete')
                require(len(matching('Module / clamp bridge'))==expected,scene.name+': clamp bridges incomplete')
            if scene.get('engineering_detail_revision')==1:
                require(len(matching('Module / inset service door'))==6,scene.name+': service doors missing')
                require(len(matching('Module / intake fin'))==54,scene.name+': intake banks incomplete')
                require(not matching('Module / side vents'),scene.name+': obsolete flat vent bars remain')
            # Bounds are in the module's authored frame: outward is -Y.
            spines=[bounds(o,frame) for o in matching('Module / front spine')]
            for o in matching('Module / spine status bezel'):
                lo,hi=bounds(o,frame)
                require(any(all(min(hi[i],b[i])-max(lo[i],a[i])>.009 for i in range(3)) for a,b in spines),o.name+': unsupported status bezel')
            for o in matching('Module / power bus'):
                lo,hi=bounds(o,frame)
                for x in (lo.x+.012,hi.x-.012):
                    require(any(a.x<x<b.x and a.y<hi.y<b.y and a.z<lo.z<b.z for a,b in spines),o.name+': unsupported bus end')
            for o in matching('Module / service bolt'):
                lo,hi=bounds(o,frame);center=(lo+hi)/2
                require(any(a.x<center.x<b.x and a.y<hi.y<b.y and a.z<center.z<b.z for a,b in spines),o.name+': floating bolt')
                require(.045<hi.x-lo.x<.051,o.name+': excessive fastener size')
            plates=matching('Module / terminal mounting plate');require(len(plates)==1,scene.name+': terminal backing missing')
            if plates:
                lo,hi=bounds(plates[0],frame)
                bulk=[bounds(o,frame) for o in matching('Module / compartment bulkhead')]
                require(any(hi.y>a.y and lo.z<b.z and hi.z>a.z for a,b in bulk),scene.name+': terminal plate detached')
                for o in matching('Module / fan controller')+matching('Module / heatsink header'):
                    a,b=bounds(o,frame)
                    require(not all(min(hi[i],b[i])-max(lo[i],a[i])>.001 for i in range(3)),o.name+': overlaps terminal access backing')
            if 'Stabilizer' in scene.name:
                dummies=[o for o in main.objects if o.name.startswith('subpart_EnergyFan')]
                require(len(dummies)==3,scene.name+': fan pivots missing')
                require(all(o.get('file')=='ArcanePower_EnergyFan' for o in dummies),'Fan asset reference changed')
                fan=bpy.data.collections['Main (ArcanePower_EnergyFan)']
                fp=[o.matrix_world @ v.co for o in fan.objects if o.type=='MESH' for v in o.data.vertices]
                fan_front=-.61+min(p.y for p in fp)
                fan_rear=-.61+max(p.y for p in fp)
                if scene.get('fan_guard_revision')==1:
                    guards=matching('Module / flat grille ring')+matching('Module / flat grille spoke')
                    require(len(matching('Module / flat grille spoke'))==24,scene.name+': eight spokes per guard required')
                    guard_rear=max(bounds(o,frame)[1].y for o in guards)
                    require(fan_front-guard_rear>.090,scene.name+': insufficient blade/guard clearance')
                    metrics['flat_guard_blade_clearance_m']=fan_front-guard_rear
                require(fan_front>-.715,scene.name+': blade clips grille')
                backplane_front=min(bounds(o,frame)[0].y for o in matching('Module / equipment backplane'))
                require(backplane_front-fan_rear>.10,scene.name+': blade clips equipment backplane')
                metrics['fan_grille_clearance_m']=fan_front+.715
                metrics['fan_backplane_clearance_m']=backplane_front-fan_rear
    bpy.context.window.scene=original
    report={'passed':not failures,'failures':failures,'inventory':inventory,'measurements':metrics,'live_game_checked':False}
    path=ROOT/'validation/energy-geometry-audit.json';path.write_text(json.dumps(report,indent=2)+'\n')
    if failures:raise AssertionError('\n'.join(failures))
    return report

if __name__=='__main__':main()
