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


def witness_uv(obj):
    # The uniform indicator map needs enough UV area for MWM half precision,
    # including the sub-millimetre chamfers on these tiny witness strips.
    layer=obj.data.uv_layers.active.data
    lo=Vector([min(d.uv[i] for d in layer) for i in (0,1)])
    scale=.8/max(max(d.uv[i] for d in layer)-lo[i] for i in (0,1))
    for d in layer:d.uv=(d.uv-lo)*scale+Vector((.05,.05))


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
        if ident.endswith('Seat'):
            # 55 cm bore, fitted inside the accepted 71 cm pipe jacket.
            p.tube('steel valve seat',[(0,.010,0),(0,.055,0)],.308,'Metal_Dull',.031,40)
            p.tube('pressure gasket',[(0,.006,0),(0,.010,0)],.292,'PaintedMetal_VeryDark',.015,40)
            for side in (-1,1):
                p.box('shaft bearing',(0,.025,side*.297),(.070,.052,.034),'Metal_Shiny',.003)
            E['dummy'](col,root,'subpart_Gate',Matrix.Identity(4),NAMES[1])
        else:
            disc=p.cylinder('pressure blade',(0,-.006,0),(0,.006,0),.278,'Metal_Shiny',40)
            p.cylinder('blade spindle',(0,0,-.297),(0,0,.297),.015,'Metal_Dull',12)
            for side in (-1,1):
                p.box('blade stiffening rib',(side*.105,-.014,0),(.040,.016,.390),'Metal_Dull',.003)
                witness_uv(p.box('closure witness',(side*.105,-.023,0),(.018,.003,.065),'ThermalStatus',.001))
        for obj in col.objects:
            if obj.type=='MESH':obj.parent=root
        scenes.append(scene)
    save()
    return {'source':str(SOURCE),'triangles':{s.name:E['tris'](E['C'].get_collections(s)['main'][0]) for s in scenes}}


def save():
    bpy.data.libraries.write(str(SOURCE),{bpy.data.scenes[n] for n in NAMES},path_remap='RELATIVE',fake_user=True,compress=True)


def export():
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
    (ROOT/'assets/thermal-isolation.json').write_text(json.dumps({'models':rows,'radius':.278,'bore_offset':.46,'recess':.30,
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
