"""Geometry/seating proof for the main reactor exterior; no game-runtime claim."""
import bpy,bmesh,importlib,json,math,runpy
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT=Path(__file__).resolve().parents[1]
PREFIX='Reactor exterior / '


def main():
    scene=bpy.data.scenes['ArcanePower_ReactorPrototype'];bpy.context.window.scene=scene;bpy.context.view_layer.update()
    col=importlib.import_module('space-engineers-utilities.seut_collections').get_collections(scene)['main'][0]
    meshes=[o for o in col.objects if o.type=='MESH'];new=[o for o in meshes if o.name.startswith(PREFIX)]
    baseline=json.loads((ROOT/'validation/reactor-exterior-loop-01/source.json').read_text())['protected_objects']
    fingerprint=runpy.run_path(str(ROOT/'assets/refine_reactor_exterior.py'))['fingerprint']
    failures=[];measurements={}
    def require(ok,message):
        if not ok:failures.append(message)
    for name,sha in baseline.items():require(name in bpy.data.objects and fingerprint(bpy.data.objects[name])==sha,'Protected object changed: '+name)
    def points(o):return [o.matrix_world @ v.co for v in o.data.vertices]
    trees={}
    def tree(o):
        if o not in trees:trees[o]=BVHTree.FromPolygons(points(o),[tuple(p.vertices) for p in o.data.polygons])
        return trees[o]
    for obj in new:
        bm=bmesh.new();bm.from_mesh(obj.data)
        if not obj.get('source_asset'):
            require(all(e.is_manifold and e.is_contiguous for e in bm.edges),obj.name+': open or inconsistently wound solid')
            require(bm.calc_volume(signed=True)>1e-9,obj.name+': inverted or zero-volume solid')
        bm.free()
        require(bool(obj.data.uv_layers),obj.name+': missing UVs')
        require(all(math.isfinite(x) for uv in obj.data.uv_layers for d in uv.data for x in d.uv),obj.name+': nonfinite UV')
        require(all(m is not None and m.library is not None for m in obj.data.materials),obj.name+': structural material is not native')
        require(all(abs(p.x)<=6.2501 and abs(p.y)<=6.2501 and abs(p.z)<=3.7501 for p in points(obj)),obj.name+': outside 5x3x5 envelope')
        require(all(m.type!='BEVEL' or m.segments==1 for m in obj.modifiers),obj.name+': rounded structural fillet')
    screws=[o for o in new if 'support' in o and 'screw' in o.name];vane_samples=0
    for obj in screws:
        support=bpy.data.objects.get(obj['support']);require(support is not None,obj.name+': lost support reference')
        if support:
            n=(obj.matrix_world.to_3x3() @ Vector((0,0,1))).normalized();origin=obj.matrix_world.translation-n*.003
            hit,normal,index,distance=tree(support).ray_cast(origin,n,.020)
            require(hit is not None and normal.dot(n)>.9,obj.name+': screw floats above its panel or flange')
    for obj in new:
        if 'fastener_body' in obj:require(obj['fastener_body'] in col.objects,obj.name+': lost fastener body')
        if 'support' not in obj or 'screw' in obj.name:continue
        support=bpy.data.objects.get(obj['support'])
        if not support:require(False,obj.name+': lost vane support');continue
        n=(support.matrix_world.to_3x3() @ Vector((0,0,1))).normalized()
        for x in (min(v.co.x for v in obj.data.vertices)+.004,max(v.co.x for v in obj.data.vertices)-.004):
            p=obj.matrix_world @ Vector((x,0,0));hit,normal,index,distance=tree(support).ray_cast(p,n,.055)
            require(hit is not None and normal.dot(n)>.9,obj.name+': unsupported louver end');vane_samples+=1
    jackets=[o for o in new if o.name.startswith(PREFIX+'chamfered pillar jacket')]
    require(len(jackets)==4,'Four bulkier pillar jackets required')
    for obj in jackets:
        n=(obj.matrix_world.to_3x3() @ Vector((0,0,1))).normalized();t=Vector((-n.y,n.x,0));ps=points(obj)
        require(abs(max(p.dot(n) for p in ps)-6.10)<.001,obj.name+': outward face not seated near housing rim')
        require(abs(max(p.dot(t) for p in ps)-min(p.dot(t) for p in ps)-1.60)<.001,obj.name+': pillar width changed')
    status_samples=0
    emitters=[o for o in meshes if o.name.startswith('Spine status emitter')]
    require(len(emitters)==4 and scene.get('pillar_status_revision')==1,'Four recessed status lamps required')
    for emitter in emitters:
        backing=bpy.data.objects.get(emitter.get('status_backing',''))
        jacket=bpy.data.objects.get(backing.get('status_jacket','')) if backing else None
        require(backing is not None and jacket is not None,emitter.name+': status mounting references missing')
        if not backing or not jacket:continue
        n=(jacket.matrix_world.to_3x3() @ Vector((0,0,1))).normalized();t=Vector((-n.y,n.x,0))
        for obj,front in ((jacket,6.10),(backing,6.081),(emitter,6.094)):
            require(abs(max(p.dot(n) for p in points(obj))-front)<.0001,obj.name+': wrong status layer depth')
        for x in (-.040,0,.040):
            for z in (.65,1.03,1.40):
                origin=n*6.20+t*x+Vector((0,0,z))
                require(tree(jacket).ray_cast(origin,-n,.11)[0] is None,emitter.name+': jacket masks luminous face')
                hit,normal,index,distance=tree(emitter).ray_cast(origin,-n,.15)
                require(hit is not None and abs(hit.dot(n)-6.094)<.0001,emitter.name+': luminous face occluded or misplaced')
                hit,normal,index,distance=tree(backing).ray_cast(origin,-n,.16)
                require(hit is not None and abs(hit.dot(n)-6.081)<.0001,emitter.name+': backing not behind luminous face')
                status_samples+=1
    require(sum(o.name.startswith(PREFIX+'fitted curved pillar foot') for o in new)==4,'Fitted pillar feet missing')
    require(scene.get('pillar_foot_revision')==3,'Inset stepped pillar feet missing')
    feet=[o for o in new if o.name.startswith(PREFIX+'fitted curved pillar foot')]
    foot_radius=max(math.hypot(p.x,p.y) for o in feet for p in points(o))
    require(foot_radius<=6.1551,'Pillar foot projects beyond its supported collar footprint')
    require(sum(o.name.startswith(PREFIX+'fitted pillar roof seat') for o in new)==4,'Fitted upper pillar seats missing')
    require(not any(o.name.startswith(('Upper radial bracket','Integrated support / curved pillar saddle')) for o in meshes),'Superseded saddles/brackets remain')
    require(all(scene.get('pillar_surface_revision_'+str(i))==1 for i in range(4)),'Not all pillar faces refined')
    require(sum(o.name.startswith(PREFIX+'continuous cooling rib') for o in new)==4,'Continuous cooling belt missing')
    # Sample the full circular belt between ribs: armor must not mask the plenum.
    upper=next(o for o in meshes if o.name.startswith('Circular upper armored housing'));belt_samples=0
    for i in range(128):
        a=(i+.5)*math.tau/128;n=Vector((math.cos(a),math.sin(a),0))
        hit,normal,index,distance=tree(upper).ray_cast(n*6.30+Vector((0,0,3.23)),-n,.34)
        require(hit is None,'Upper armor masks continuous cooling belt');belt_samples+=1
    # The new pillar casing and seats must stay outside each dispensing mouth.
    openings=0
    for i in range(4):
        a=-math.pi/4+i*math.pi/2;n=Vector((math.cos(a),math.sin(a),0));t=Vector((-n.y,n.x,0))
        for z in (2.15,2.30,2.45):
            for x in (-.15,0,.15):
                p=n*3.9+t*x+Vector((0,0,z))
                for obj in jackets+[o for o in new if o.name.startswith(PREFIX+'fitted pillar roof seat')]:
                    require(tree(obj).ray_cast(p,n,.8)[0] is None,'New pillar armor blocks dispenser opening')
                openings+=1
    surrounds=[o for o in new if o.name.startswith(PREFIX+'dispenser ')]
    require(len(surrounds)==24 and scene.get('dispenser_mount_revision')==1,'Four complete dispenser surrounds required')
    launch_samples=0;mount_samples=0;toe_samples=0
    for i in range(4):
        a=-math.pi/4+i*math.pi/2;n=Vector((math.cos(a),math.sin(a),0));t=Vector((-n.y,n.x,0));up=Vector((0,0,1))
        normal=(-n-up).normalized();pitch=normal.cross(t)
        # Sample across the launch aperture along the actual 45-degree path,
        # not just horizontally through its centre.
        for x in (-.30,0,.30):
            for y in (-.22,0,.22):
                p=n*4.48+up*2.42+t*x+pitch*y+normal*.24
                for obj in surrounds:require(tree(obj).ray_cast(p,normal,2.0)[0] is None,'Dispenser surround obstructs launch path')
                launch_samples+=1
        # Both ends of each new cheek must seat into the original cradle and
        # solid ceiling. The curved rails straddle the glass, closing its seam.
        for x in (-.53,.53):
            p=n*4.6+t*x+up*2.80
            require(tree(upper).ray_cast(p,up,.12)[0] is not None,'Dispenser ceiling mount lacks solid roof backing');mount_samples+=1
        collar=next(o for o in meshes if o.name.startswith('Machined perimeter collar') and min(p.z for p in points(o))>-2)
        for x in (-.50,.50):
            p=n*6.10+t*x+up*(-1.35)
            require(tree(collar).ray_cast(p,-up,.05)[0] is not None,'Pillar foot lacks drum collar support');mount_samples+=1
        for x in (-.82,-.60,-.30,0,.30,.60,.82):
            p=n*math.sqrt(6.155**2-x*x)+t*x+up*(-1.35)
            hit,normal,index,distance=tree(collar).ray_cast(p,-up,.05)
            require(hit is not None and normal.z>.9,'Pillar foot toe overhangs perimeter collar');toe_samples+=1
    measurements.update(dispenser_launch_clearance_samples=launch_samples,roof_and_foot_support_samples=mount_samples,foot_toe_support_samples=toe_samples,foot_max_radius_m=foot_radius)
    measurements.update(status_layer_samples=status_samples,status_backing_recess_m=.019,status_emitter_recess_m=.006,captive_screws_seated=len(screws),louver_end_support_samples=vane_samples,continuous_belt_clearance_samples=belt_samples,dispenser_opening_samples=openings,pillar_width_m=1.60,pillar_outward_face_m=6.10,pillar_outset_m=.50)
    report={'passed':not failures,'failures':failures,'main_meshes':len(meshes),'triangles':sum(len(p.vertices)-2 for o in meshes for p in o.data.polygons),'new_meshes':len(new),'protected_objects_unchanged':len(baseline),'dispensers_unchanged':sum(name.startswith('AP dispenser /') for name in baseline),'measurements':measurements,'live_game_checked':False}
    (ROOT/'validation/reactor-exterior-loop-01/geometry.json').write_text(json.dumps(report,indent=2)+'\n')
    if failures:raise AssertionError('\n'.join(failures))
    return report


if __name__=='__main__':result=main()
