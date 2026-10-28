"""Fixed, single-face 1-deep x 2-high x 3-wide hull radiator. No export.

Reuses one face of the accepted radiator panel, preserving its meshes and UVs.
Four self-sealing edge unions join neighboring hull radiators. The rear lower
cell has the standard duplex pipe socket. All six sides have solid backing.
"""
import json
from pathlib import Path
import runpy
import bpy
import bmesh
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]


def build():
    m = runpy.run_path(str(ROOT/'assets/build_thermal_models.py'))
    source = m['main_for']('Radiator panel')
    bpy.context.window.scene = m['scene_for']('Radiator panel')
    bpy.context.view_layer.update()
    originals = []
    for obj in source.objects:
        if obj.type != 'MESH': continue
        label = obj.name.split(' / ', 1)[-1]
        centre = sum((obj.matrix_world@v.co for v in obj.data.vertices), Vector())/len(obj.data.vertices)
        if (obj.get('radiating_surface') and obj.get('surface_side') == -1
            or label.startswith('radiator panel substrate')
            or centre.y < 0 and label.startswith(('panel edge heat pipe','radiator tile retention shoe','tile retention screw'))):
            originals.append((obj, obj.matrix_world.copy()))
    assert sum(bool(o.get('radiating_surface')) for o,_ in originals) == 36
    p = m['Parts']('Hull radiator', existing=m['CONTRACT']['subtype']('Hull radiator') in bpy.data.scenes)
    for obj in list(p.col.objects): bpy.data.objects.remove(obj, do_unlink=True)
    p.ports = []
    # The monolithic backing closes all seams. Front tiles sit 20 mm below
    # the common armor plane; the casing reaches exact large-grid boundaries.
    backing = p.box('full block backing', (0, .08, 0), (7.5, 2.34, 5), 'PaintedMetal_Colorable', 0)
    backing['hull_radiator_collision'] = True
    copies = {}
    for obj, world in originals:
        copy = obj.copy(); copy.data = obj.data.copy(); copy.parent = None
        copy.animation_data_clear(); copy.name = obj.name.replace('Radiator panel / ', 'Hull radiator / ')
        p.col.objects.link(copy)
        copy.matrix_world = Matrix.Translation((0,-1.08,0))@world
        # Seat the existing proud edge hardware below the hull plane while
        # retaining the graphite tile thickness, UVs and front surface.
        if ' / panel edge heat pipe' in obj.name: copy.location.y += .04
        if ' / radiator tile retention shoe' in obj.name or ' / tile retention screw' in obj.name:
            copy.location.y += .075
        if obj.get('thermal_support'):
            point, axis = Vector(obj['support_point']), Vector(obj['support_axis'])
            if obj.get('thermal_support_space'):
                space = bpy.data.objects[obj['thermal_support_space']].matrix_world
                point, axis = space@point, space.to_3x3()@axis
                del copy['thermal_support_space']
            delta = copy.matrix_world@world.inverted()
            copy['support_point'] = tuple(delta@point)
            copy['support_axis'] = tuple(delta.to_3x3()@axis)
        copies[obj.name] = copy
    for obj in copies.values():
        for key in ('thermal_support','thermal_decal_support','thermal_marking_support'):
            if obj.get(key) in copies: obj[key] = copies[obj[key]].name
    for x in (-3.42,3.42):
        frame=p.box('flush side frame',(x,-1.17,0),(.66,.16,5),'PaintedMetal_Colorable',0)
        frame['hull_radiator_collision']=True
    for z in (-2.37,2.37):
        frame=p.box('flush end frame',(0,-1.17,z),(6.18,.16,.26),'PaintedMetal_Colorable',0)
        frame['hull_radiator_collision']=True
    for z in (-2.235,2.265):
        rail=p.box('panel retention rail',(0,-1.10,z),(6.40,.28,.14),'PaintedMetal_Darker')
        for x in (-2.9,-1.5,0,1.5,2.9):
            p.bolt('rail captive fastener',(x,-1.237,z),(0,-1,0),rail,.024)
    # Cut shallow socket pockets in the backing; their floors remain solid.
    cut = runpy.run_path(str(ROOT/'assets/build_pipe_rotor.py'))['cut']
    for port in m['CONTRACT']['HULL_RADIATOR_PORTS']:
        c,n,up = (Vector(port[k]) for k in ('position','normal','hot_axis'))
        u = up.cross(n)
        cutter=p.box('temporary union recess',(0,0,0),(1.98,1.98,.35),chamfer=0)
        cutter.matrix_world=Matrix((u,up,n)).transposed().to_4x4();cutter.location=c-n*.025
        cut(p,backing,cutter)
        p.port(port['id'], c, n, 'CO2', up)
        p.ports[-1].update({k:port[k] for k in ('self_sealing','hull_only') if k in port})
        for sign in (-1,1):
            centre=c+up*(sign*.46)
            p.cylinder('sealed union seat',centre-n*.23,centre-n*.19,.28,'PaintedMetal_VeryDark',48)
    label=p.box('service label plate',(2.5,1.231,1.25),(1.38,.032,.65),'PaintedMetal_Darker')
    p.label(label,'ARCANE / HULL RADIATOR',(2.5,1.249,1.34),(-1,0,0),(0,0,1),.067)
    p.label(label,'REAR H/C FEED / EDGES SELF SEAL',(2.5,1.249,1.13),(-1,0,0),(0,0,1),.046)
    refine=runpy.run_path(str(ROOT/'assets/refine_thermal_models.py'))
    refine['tighten_ports'](p);refine['mesh_markings'](p);refine['pressure_seal_fit'](p)
    # Retain every reused tile's original UVs. Only the new housing is mapped.
    for obj in p.col.objects:
        if obj.type=='MESH' and obj not in copies.values(): refine['cylindrical_uv'](obj,Vector((.17,.31)))
    p.finish();p.scene['thermal_phase']='textures'
    p.scene['thermal_detail_revision']=p.scene['thermal_texture_revision']=1
    p.scene['hull_radiator_revision']=1
    flow=runpy.run_path(str(ROOT/'assets/refine_thermal_flow.py'))
    data=json.loads((ROOT/'assets/thermal-flow-paths.json').read_text())
    data['models'][p.scene.name]=[flow['path_row']([Vector(port['position'])+Vector(port['hot_axis'])*sign*.46,
        (sign*.46,0,0)],'CO2',sign>0,i,.16,label=port['id'])
        for i,port in enumerate(p.ports) for sign in (-1,1)]
    (ROOT/'assets/thermal-flow-paths.json').write_text(json.dumps(data,indent=2)+'\n')
    return m['record']('Hull radiator')


def review():
    r=runpy.run_path(str(ROOT/'assets/review_thermal_models.py'))
    scene,p=r['fresh']('hull radiator array')
    for pos in ((0,0,0),(7.5,0,0),(0,0,5)):
        r['instance'](scene,'Hull radiator',pos)
    # Adjacent armor demonstrates the same exterior plane and one-cell depth.
    p.box('adjacent hull armor',(-5,0,0),(2.5,2.5,5),'PaintedMetal_Colorable',0)
    r['engineer'](p,(-5,-3))
    for obj in p.col.objects:
        if 'engineer' in obj.name:obj.location.z-=2.5
    return r['view'](scene.name,target=(2.2,0,1.7),direction=(.25,-1,.35),distance=23)


def audit():
    m=runpy.run_path(str(ROOT/'assets/build_thermal_models.py'))
    bpy.context.window.scene=m['scene_for']('Hull radiator');bpy.context.view_layer.update()
    col=m['main_for']('Hull radiator')
    ports=json.loads(col['ports']);assert len(ports)==5
    assert sum(p.get('hull_only',False) for p in ports)==4 and all(p['self_sealing'] for p in ports)
    tiles=[o for o in col.objects if o.get('radiating_surface')]
    assert len(tiles)==36 and all(o.get('surface_side')==-1 and o.parent is None for o in tiles)
    verts,faces=[],[];solids=0
    for obj in col.objects:
        if obj.type!='MESH':continue
        points=[obj.matrix_world@v.co for v in obj.data.vertices]
        assert all(abs(v.x)<=3.7501 and abs(v.y)<=1.2501 and abs(v.z)<=2.5001 for v in points),obj.name
        if obj in tiles:assert abs(min(v.y for v in points)+1.23)<1e-5,obj.name
        if obj.get('thermal_text') or obj.get('source_asset'):continue
        bm=bmesh.new();bm.from_mesh(obj.data)
        assert all(e.is_manifold for e in bm.edges) and bm.calc_volume()>0,obj.name
        bm.free();solids+=1
        offset=len(verts);verts.extend(points);faces.extend(tuple(offset+i for i in f.vertices) for f in obj.data.polygons)
    tree=BVHTree.FromPolygons(verts,faces);samples=0
    for axis,half in enumerate((3.75,1.25,2.5)):
        axes=[i for i in range(3) if i!=axis]
        for sign in (-1,1):
            n=Vector([sign if i==axis else 0 for i in range(3)])
            for a in range(-12,13):
                for b in range(-12,13):
                    origin=n*(half+.01)
                    origin[axes[0]]=a/12*((3.75,1.25,2.5)[axes[0]]-.05)
                    origin[axes[1]]=b/12*((3.75,1.25,2.5)[axes[1]]-.05)
                    assert tree.ray_cast(origin,-n,.5)[0] is not None,('Open casing',tuple(origin))
                    samples+=1
    return dict(solids=solids,hull_samples=samples,front_tiles=len(tiles),ports=5,cells_depth_height_width=(1,2,3),exported=False)
