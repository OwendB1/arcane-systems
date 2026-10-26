"""Native reactor shut-off valves, reviewed in the live thermal scene.

The normal block meshes/collisions are unchanged. Runtime attaches these tiny
native subparts at the reactor's duplex mouths. Blender + SEUT owns the source/export.
"""
import json
import math
import runpy
from pathlib import Path
import bpy
from mathutils import Matrix, Vector

ROOT=Path(__file__).resolve().parents[1]
E=runpy.run_path(str(ROOT/'assets/export_thermal_models.py'))
M=E['M']
STAGE=ROOT/'src/Models/Cubes/large/.isolation-stage'
SOURCE=ROOT/'assets/arcane-thermal-isolation.blend'
NAMES=('ArcaneIsolationSeat','ArcaneIsolationGate')
BORE_RADIUS=.230  # Reactor sliding stem: R265 with a 35 mm wall, 40 sides.
DISC_RADIUS=.2055


def small_part_uv(obj):
    # Tiny rib and indicator chamfers need enough UV area for MWM half precision.
    # Preserve projection proportions while increasing their texture density.
    layer=obj.data.uv_layers.active.data
    lo=Vector([min(d.uv[i] for d in layer) for i in (0,1)])
    scale=.8/max(max(d.uv[i] for d in layer)-lo[i] for i in (0,1))
    for d in layer:d.uv=(d.uv-lo)*scale+Vector((.05,.05))


def geometry(p, ident):
    """Complete mechanism inside the reactor bore, including shaft bearings."""
    if ident.endswith('Seat'):
        p.tube('steel valve seat',[(0,.010,0),(0,.045,0)],.227,'Metal_Dull',.020,40)
        p.tube('pressure gasket',[(0,.006,0),(0,.010,0)],.219,'PaintedMetal_VeryDark',.012,40)
        for side in (-1,1):
            p.box('shaft bearing',(0,.017,side*.218),(.040,.036,.018),'Metal_Shiny',.002)
    else:
        p.cylinder('pressure blade',(0,-.005,0),(0,.005,0),DISC_RADIUS,'Metal_Shiny',40)
        p.cylinder('blade spindle',(0,0,-.218),(0,0,.218),.012,'Metal_Dull',12)
        for side in (-1,1):
            small_part_uv(p.box('blade stiffening rib',(side*.080,-.011,0),(.030,.012,.280),'Metal_Dull',.002))
            small_part_uv(p.box('closure witness',(side*.080,-.018,0),(.014,.002,.045),'ThermalStatus',.0007))


def refit():
    """Update only the existing valve source scenes; keep native roots/dummies."""
    for ident in NAMES:
        scene=bpy.data.scenes[ident];bpy.context.window.scene=scene;bpy.context.view_layer.update()
        col=E['C'].get_collections(scene)['main'][0]
        meshes=[o for o in col.objects if o.type=='MESH']
        root=meshes[0].parent
        assert root is not None and all(o.parent==root for o in meshes)
        for obj in meshes:bpy.data.objects.remove(obj,do_unlink=True)
        p=object.__new__(M['Parts']);p.name=ident;p.col=col;p.scene=scene;p.support=[]
        p.native={m.name:m for m in bpy.data.materials}
        geometry(p,ident)
        for obj in col.objects:
            if obj.type=='MESH':obj.parent=root
    return audit_bore()


def audit_bore():
    """Fit evaluated geometry inside the actual faceted ID at every 5 degrees."""
    col=M['main_for']('Reactor housing')
    stem=next(o for o in col.objects if 'LA sliding H primary stem' in o.name)
    path=list(map(Vector,json.loads(stem['pipe_path'])));axis=(path[-1]-path[0]).normalized()
    radii=[]
    bpy.context.window.scene=M['scene_for']('Reactor housing');bpy.context.view_layer.update()
    for vertex in stem.data.vertices:
        d=stem.matrix_world@vertex.co-path[0];radii.append((d-axis*d.dot(axis)).length)
    assert abs(min(radii)-BORE_RADIUS)<1e-5, 'Reactor bore changed; remeasure the valve fit'
    limit=BORE_RADIUS*math.cos(math.pi/40)
    maximum=0
    for ident in NAMES:
        bpy.context.window.scene=bpy.data.scenes[ident];bpy.context.view_layer.update()
        deps=bpy.context.evaluated_depsgraph_get()
        for obj in E['C'].get_collections(bpy.context.scene)['main'][0].objects:
            if obj.type!='MESH':continue
            for degrees in (range(0,91,5) if ident.endswith('Gate') else (0,)):
                turn=Matrix.Rotation(math.radians(degrees),4,'Z')
                for vertex in obj.evaluated_get(deps).data.vertices:
                    v=turn@obj.matrix_world@vertex.co
                    radial=math.hypot(v.x,v.z);maximum=max(maximum,radial)
                    assert radial<limit-.001, (obj.name,degrees,'Valve crosses inner pressure wall',radial)
                    if ident.endswith('Gate') and 'spindle' not in obj.name:
                        assert radial<.207*math.cos(math.pi/40), (obj.name,'Blade sweeps through its seat')
    return {'bore_diameter_m':2*BORE_RADIUS,'disc_diameter_m':2*DISC_RADIUS,
            'minimum_wall_clearance_m':limit-maximum,'motion_samples':19}


def build():
    assert Path(bpy.data.filepath)==M['FILE'], 'Load accepted thermal materials first'
    scenes=[]
    for ident in NAMES:
        assert bpy.data.scenes.get(ident) is None, 'Inspect the existing valve source before rebuilding'
        scene,col,root=E['scene'](ident,(1,1,1),True)
        scene.name=ident;scene.seut.subtypeId=ident
        scene.seut.export_exportPath=str(STAGE)
        p=object.__new__(M['Parts']);p.name=ident;p.col=col;p.scene=scene;p.support=[]
        p.native={m.name:m for m in bpy.data.materials}
        geometry(p,ident)
        if ident.endswith('Seat'):E['dummy'](col,root,'subpart_Gate',Matrix.Identity(4),NAMES[1])
        for obj in col.objects:
            if obj.type=='MESH':obj.parent=root
        scenes.append(scene)
    save()
    return {'source':str(SOURCE),'triangles':{s.name:E['tris'](E['C'].get_collections(s)['main'][0]) for s in scenes}}


def save():
    bpy.data.libraries.write(str(SOURCE),{bpy.data.scenes[n] for n in NAMES},path_remap='RELATIVE',fake_user=True,compress=True)


def export():
    audit_bore()
    STAGE.mkdir(parents=True,exist_ok=True)
    previous=bpy.context.window.scene
    names={o:o.name for o in bpy.data.objects if o.type=='EMPTY'}
    transforms={o:(o.matrix_basis.copy(),o.empty_display_size) for o in names}
    rows={}
    try:
        for name in NAMES:
            s=bpy.data.scenes[name];bpy.context.window.scene=s;bpy.context.view_layer.update()
            col=E['C'].get_collections(s)['main'][0]
            modifiers=[]
            try:
                for obj in col.objects:
                    if obj.type=='MESH':modifiers.append((obj,obj.modifiers.new('Native triangulation','TRIANGULATE')))
                statuses=E['EXPORT'].export_collection(E['Reporter'](),bpy.context,col)
                assert all('FINISHED' in status for status in statuses),statuses
                assert E['EXPORT'].get_col_filename(col)==name
                rows[name]={'triangles':E['tris'](col)}
            finally:
                for obj,mod in modifiers:obj.modifiers.remove(mod)
    finally:
        for mat in list(bpy.data.materials):
            if mat.override_library or (mat.use_nodes and mat.node_tree.nodes.get('EXPORT_DUMMY')):
                E['EXPORT'].revert_mat_after_export(E['Reporter'](),bpy.context,mat)
        changed=[o for o,n in names.items() if o.name!=n]
        for o in changed:o.name='Export restore / '+names[o]
        for o in changed:o.name=names[o]
        for o,(matrix,size) in transforms.items():o.matrix_basis=matrix;o.empty_display_size=size
        bpy.context.window.scene=previous
    contract(rows)
    return {'staging':str(STAGE),'models':rows}


def contract(rows):
    """Sample authored meshes at the four reactor mounts, independently of C#."""
    basis=Matrix(((1,0,0,0),(0,0,1,0),(0,-1,0,0),(0,0,0,1)))
    native=Matrix(((-1,0,0,0),(0,0,1,0),(0,1,0,0),(0,0,0,1)))
    meshes={}
    previous=bpy.context.window.scene
    try:
        for name in NAMES:
            s=bpy.data.scenes[name];bpy.context.window.scene=s;bpy.context.view_layer.update()
            deps=bpy.context.evaluated_depsgraph_get()
            meshes[name]=[basis@o.matrix_world@v.co for o in E['C'].get_collections(s)['main'][0].objects
                          if o.type=='MESH' for v in o.evaluated_get(deps).data.vertices]
        samples=[]
        models=M['CONTRACT']['runtime_models'](json.loads((ROOT/'validation/thermal-models/models.json').read_text()))
        spec=models['Reactor housing']
        col=M['main_for']('Reactor housing')
        for index,port in enumerate(json.loads(col['ports'])):
            n=Vector(port['normal']);hot=Vector(port['hot_axis'])
            right=hot.cross(n).normalized()
            for side in (-1,1):
                pose=Matrix((right,hot,n)).transposed().to_4x4()
                pose.translation=Vector(port['position'])-n*.30+hot*(side*.46)
                for name,points in meshes.items():
                    for opening in ((0,.25,.5,.75,1) if name.endswith('Gate') else (0,)):
                        turn=Matrix.Rotation(opening*math.pi/2,4,'Y') if name.endswith('Gate') else Matrix.Identity(4)
                        ps=[native@pose@turn@p for p in points]
                        samples.append({'subtype':spec['subtype'],'port':index,'side':side,'model':name,'opening':opening,
                                        'bounds':[[fn(p[i] for p in ps) for i in range(3)] for fn in (min,max)]})
    finally:bpy.context.window.scene=previous
    (ROOT/'assets/thermal-isolation.json').write_text(json.dumps({'models':rows,'radius':DISC_RADIUS,
        'bore_radius':BORE_RADIUS,'bore_sides':40,'bore_offset':.46,'recess':.30,
        'samples':samples},indent=2)+'\n')


def preview(opening=0):
    """Fresh linked review copies. Never save this assembly over production art."""
    name='Thermal isolation review'
    previous=bpy.data.scenes.get(name)
    if previous:
        for obj in list(previous.objects):bpy.data.objects.remove(obj,do_unlink=True)
        bpy.data.scenes.remove(previous)
    scene=bpy.data.scenes.new(name);scene['review_only']=True
    scene.view_layers[0].name='SEUT'
    scene.view_layers[0]['Paint Color']=(.55,.55,.55);scene.view_layers[0]['UV Grid Overlay']=0.0
    source=M['scene_for']('Reactor housing');bpy.context.window.scene=source;bpy.context.view_layer.update()
    col=M['main_for']('Reactor housing')
    for obj in col.objects:
        if obj.type!='MESH':continue
        copy=obj.copy();copy.parent=None;copy.animation_data_clear();scene.collection.objects.link(copy);copy.matrix_world=obj.matrix_world.copy()
    # Blender -> canonical native conversion, matching SEUT subpart export.
    basis=Matrix(((1,0,0,0),(0,0,1,0),(0,-1,0,0),(0,0,0,1)))
    for port in json.loads(col['ports']):
        n=Vector(port['normal']);hot=Vector(port['hot_axis'])
        right=hot.cross(n).normalized()
        for sign in (-1,1):
            pose=Matrix((right,hot,n)).transposed().to_4x4()
            pose.translation=Vector(port['position'])-n*.30+hot*(sign*.46)
            for part in NAMES:
                part_scene=bpy.data.scenes[part];bpy.context.window.scene=part_scene;bpy.context.view_layer.update()
                for obj in E['C'].get_collections(part_scene)['main'][0].objects:
                    if obj.type!='MESH':continue
                    copy=obj.copy();copy.parent=None;copy.animation_data_clear();scene.collection.objects.link(copy)
                    turn=Matrix.Rotation(opening*math.pi/2,4,'Y') if part.endswith('Gate') else Matrix.Identity(4)
                    copy.matrix_world=pose@turn@basis@obj.matrix_world
                    copy['isolation_preview']=True
    bpy.context.window.scene=scene;bpy.context.view_layer.update()
    view=runpy.run_path(str(ROOT/'assets/review_thermal_models.py'))['view']
    return view(scene.name,(-1.15,0,.1),(-1,-.3,.2),2.4)


if __name__=='__main__':
    import sys
    if '--export' in sys.argv:print(export())
    else:print(build());print(preview())
