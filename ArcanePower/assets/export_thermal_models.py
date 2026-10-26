"""Build reviewed native export scenes without changing accepted main geometry.

Moving parts are split into native subparts, preserving the C# coordinate contract.
Every block gets three unpowered weld stages; each mesh gets native distance LODs.
Run prepare(name) in live Blender, inspect derived scenes, then export(name).
For family rebuilds, use one disposable background process per reviewed main:
blender -b arcane-thermal-models.blend --python export_thermal_models.py -- --isolated MODEL
This keeps SEUT material remapping away from unrelated scenes and orphan meshes.
"""
import hashlib
import importlib
import json
import math
from pathlib import Path
import runpy
import shutil
from contextlib import nullcontext
import bpy
import bmesh
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT=Path(__file__).resolve().parents[1]
STAGING=ROOT/'src/Models/Cubes/large/.thermal-stage'
COLLISIONS=ROOT/'assets/collisions/Cubes/large'
M=runpy.run_path(str(ROOT/'assets/build_thermal_models.py'))
C=M['COLS']
LOD=runpy.run_path(str(ROOT/'assets/build_energy_lods.py'))
BUILD=runpy.run_path(str(ROOT/'assets/build_construction_stages.py'))
EXPORT=importlib.import_module('space-engineers-utilities.export.seut_export_utils')
OPS=importlib.import_module('space-engineers-utilities.export.seut_ot_export')
MANIFOLDS=json.loads((ROOT/'assets/thermal-manifold-runtime.json').read_text())
OUT=ROOT/'validation/thermal-models'


class Reporter:
    def report(self, kind, message):
        print(kind,message,flush=True)


def tris(col):
    return sum(len(f.vertices)-2 for o in col.objects if o.type=='MESH' for f in o.data.polygons)


def native_id(identifier):
    value='APT_'+identifier.removeprefix('ArcanePower_Thermal_').replace('Thermal_','').replace('Mirrored','Mir')+'_M'
    assert len(value)<=45,value
    return value


def scene(identifier, cells, subpart=False):
    key=native_id(identifier)
    previous=bpy.data.scenes.get(key)
    if previous:
        assert previous.get('thermal_export_only')
        owned=[c for c in bpy.data.collections if c.seut.scene==previous]
        for o in list(previous.objects): bpy.data.objects.remove(o,do_unlink=True)
        bpy.context.window.scene=M['scene_for']('Brayton train')
        bpy.data.scenes.remove(previous)
        for col in owned: bpy.data.collections.remove(col)
    s=bpy.data.scenes.new(key);bpy.context.window.scene=s
    s['thermal_export_only']=True
    s.unit_settings.system='METRIC';s.unit_settings.scale_length=1
    s.view_layers[0].name='SEUT'
    s.seut.sceneType='subpart' if subpart else 'mainScene'
    s.seut.gridScale='large';s.seut.subtypeId=key
    s.seut.mod_path=str(ROOT/'src');s.seut.export_exportPath=str(STAGING)
    s.seut.export_sbc_type='none';s.seut.linkSubpartInstances=False
    for axis,value in zip(('X','Y','Z'),cells):
        s.seut['bBox_'+axis]=value
    wrapper=bpy.data.collections.new('SEUT ('+key+')')
    s.collection.children.link(wrapper)
    wrapper.seut.scene=s;wrapper.seut.col_type='seut';wrapper.seut.version=3
    col=C.create_seut_collection(s,'main')
    root=bpy.data.objects.new(identifier+' export root',None);col.objects.link(root)
    root.empty_display_size=.1
    return s,col,root


def copy_mesh(source, col, root, transform=None, construction=False):
    obj=source.copy();obj.data=source.data.copy()
    obj.animation_data_clear();obj.parent=root;obj.matrix_parent_inverse=Matrix.Identity(4)
    obj.matrix_basis=Matrix.Identity(4)
    obj.data.transform((transform or Matrix.Identity(4))@source.matrix_world)
    obj['thermal_export_source']=source.name
    col.objects.link(obj)
    if construction:
        # No runtime emission or glazing in unwelded equipment.
        for i,mat in enumerate(obj.data.materials):
            if mat and (mat.seut.technique=='GLASS' or mat.name.startswith('Thermal')):
                obj.data.materials[i]=bpy.data.materials['Construction']
    return obj


def dummy(col, root, name, pose, file=None):
    obj=bpy.data.objects.new(name,None);col.objects.link(obj)
    obj.parent=root;obj.matrix_basis=pose;obj.empty_display_size=.1
    if file: obj['file']=file
    return obj


def subparts(name, source):
    groups=[]
    if name=='Reactor housing':
        for bay in MANIFOLDS['bays']:
            for part,group in (
                ('Carriage',bay['carriage']),('Intermediate',bay['intermediate_stage']),
                ('CoverMinus',bay['cover_slides'][0]),('CoverPlus',bay['cover_slides'][1])):
                objects=[o for o in source.objects if o.type=='MESH' and o.get('thermal_motion_group')==group
                         and not o.get('thermal_extending_connector')]
                groups.append(('Thermal_'+bay['id']+'_'+part,objects,Vector((0,0,0))))
            tails=[o for o in source.objects if o.get('thermal_extending_connector')==bay['id']]
            groups.append(('Thermal_'+bay['id']+'_ConnectorTail',tails,Vector((0,0,0))))
            vent=next(o for o in source.objects if o.get('native_subpart')=='Thermal_'+bay['id']+'_ChamberVent')
            groups.append((vent['native_subpart'],list(vent.children),Vector((0,0,0))))
    elif name.startswith('Brayton train') or name in ('Space radiator','Radiator panel'):
        for root in source.objects:
            if root.type=='EMPTY' and root.get('native_subpart'):
                groups.append((root['native_subpart'],list(root.children),root.matrix_world.translation.copy()))
    return groups


def structural(obj):
    if obj.get('thermal_support') or obj.get('thermal_decal_support') or obj.get('thermal_marking_support'):
        return False
    return not any(t in obj.name.lower() for t in ('stud','bolt','screw','label','indicator','status','decal'))


def stages(s, source_objects, name, root):
    meshes=[o for o in source_objects if o.type=='MESH']
    members={o.name:o for o in meshes}
    p=[o.matrix_world@v.co for o in meshes for v in o.data.vertices]
    low=Vector([min(v[i] for v in p)+.025 for i in range(3)])
    high=Vector([max(v[i] for v in p)-.025 for i in range(3)])
    def panel(o):
        # The block name "Radiator panel" must not classify its shafts and
        # pipe ribs as panel skins during intermediate construction.
        label=o.name.removeprefix(name+' / ').lower()
        return any(t in label for t in ('armor','panel','cover','casing','cladding','lid','drum segmented'))
    for level in (1,2,3):
        col=C.create_seut_collection(s,'bs',level)
        if name in M['CONTRACT']['BARE_PIPES']:
            # Weld the actual rings and tubes; a rectangular temporary cage
            # would restore the very silhouette this variant removes.
            for obj in meshes:
                fixture = any(m and m.name.startswith('Thermal') for m in obj.data.materials)
                if fixture or obj.get('thermal_decal_support'):
                    continue
                if level == 1 and not ('pressure lip' in obj.name or obj.get('thermal_external_pipe_clamp')):
                    continue
                if level == 2 and obj.get('thermal_support'):
                    continue
                copy_mesh(obj,col,root,construction=True)
            if tris(col)>8000:
                LOD['build_lods'](s,col,batch=True)
            col.hide_render=True
            continue
        frame=BUILD['Parts'](col)
        if name=='Reactor housing': BUILD['reactor_frame'](frame)
        else: BUILD['rectangular_frame'](frame,low,high,.065 if ' / ' in name else .12)
        frame.finish()
        if level>1:
            chosen={}
            def include(o,trail=None):
                if o in chosen:return chosen[o]
                trail=set() if trail is None else trail
                if o in trail:return False
                trail.add(o)
                owner=next((members[o[k]] for k in ('thermal_support','thermal_decal_support','thermal_marking_support','thermal_seated_on')
                            if o.get(k) in members),None)
                if owner: answer=include(owner,trail)
                elif not structural(o): answer=False
                # Opaque construction pipe bodies support the fitted clamps;
                # copy_mesh replaces their sight glass with Construction.
                elif o.get('thermal_internal_coolant') or o.get('thermal_external_pipe_style'): answer=True
                elif any(m and (m.seut.technique=='GLASS' or m.name.startswith('Thermal')) for m in o.data.materials):
                    answer=False
                elif panel(o): answer=level==3 and hashlib.sha256(o.name.encode()).digest()[0]%4!=0
                else: answer=True
                chosen[o]=answer
                return answer
            for o in meshes:
                if include(o):copy_mesh(o,col,root,construction=True)
        if tris(col)>8000:
            LOD['build_lods'](s,col,batch=True)
        col.hide_render=True
    def hide(layer):
        if layer.collection.seut.col_type in ('bs','lod'):layer.hide_viewport=True
        for child in layer.children:hide(child)
    hide(s.view_layers[0].layer_collection)


def collision(s, col, root):
    target=C.create_seut_collection(s,'hkt',ref_col=col)
    # Each hull follows one actual solid. Never enclose the whole machine in a
    # single box; the reactor keeps its accepted walkable chamber collision.
    meshes=[o for o in col.objects if o.type=='MESH' and structural(o)
            and not o.get('thermal_external_pipe_clamp')
            and not o.get('thermal_cable_bend_radius')]
    def volume(o):
        points=[o.matrix_world@v.co for v in o.data.vertices]
        dims=[max(v[i] for v in points)-min(v[i] for v in points) for i in range(3)]
        return math.prod(dims) if min(dims)>.045 else 0
    moving_radiator=s.seut.sceneType=='subpart' and '_RadiatorPanels_' in s.seut.subtypeId
    if moving_radiator:
        selected=[o for o in meshes if any(part in o.get('thermal_export_source','') for part in (
            ' / radiator panel substrate', ' / panel carrier beam',
            ' / radiator top rail', ' / side pipe metal rib'))]
        assert len(selected)==6, 'Missing rotating radiator face/frame collision sources'
    else:
        selected=sorted(meshes,key=volume,reverse=True)[:10]
    radiator = s.seut.subtypeId in ('APT_SpaceRadiator_M', 'APT_RadiatorPanel_M')
    extension = s.seut.subtypeId == 'APT_RadiatorPanel_M'
    if radiator and not extension:
        # The panels are subparts, so the static main otherwise has collision
        # only at the pedestal. Its rotation-invariant top dock must be aimable
        # when placing the first extension. Use the real axial collar, not a
        # broad invisible slab across the moving panel or its cooling rays.
        docks=[o for o in M['main_for']('Space radiator').objects
               if o.type=='MESH' and ' / stack axis collar' in o.name]
        assert len(docks)==1, 'Missing radiator stack docking collider source'
        selected=selected[:9]+docks  # SEUT supports at most ten hulls per model.
    template=next(o for o in bpy.data.objects if o.type=='MESH' and o.rigid_body)
    for source in selected:
        if volume(source)<=0:continue
        mesh=bpy.data.meshes.new('Thermal collision hull')
        bm=bmesh.new()
        points=[source.matrix_world@v.co for v in source.data.vertices]
        if radiator:
            # Leave 50 mm between adjoining collider faces, retaining the full
            # visual couplings and occupied grid cells. Convex margins must not
            # obstruct placement of the next block at a shared cell boundary.
            height=2.5 if extension else 3.75
            for point in points:
                point.z=min(point.z,height-.025)
                if extension:point.z=max(point.z,-height+.025)
        for point in points:bm.verts.new(point)
        bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.00001)
        bmesh.ops.convex_hull(bm,input=list(bm.verts),use_existing_faces=False)
        loose=[v for v in bm.verts if not v.link_faces]
        if loose:bmesh.ops.delete(bm,geom=loose,context='VERTS')
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
        bm.to_mesh(mesh);bm.free()
        obj=template.copy();obj.data=mesh;obj.parent=None;obj.matrix_world=Matrix.Identity(4)
        obj.name='Thermal collider / '+source.name;target.objects.link(obj)
        obj.rigid_body.collision_shape='CONVEX_HULL'
        obj.rigid_body.use_margin=True;obj.rigid_body.collision_margin=.01
    if moving_radiator:
        # Both faces must be reachable by native tools, while the actual
        # outward cooling rays must start clear of our own moving hulls.
        trees=[BVHTree.FromPolygons([v.co for v in o.data.vertices],
               [tuple(p.vertices) for p in o.data.polygons]) for o in target.objects]
        heights=(-1.02,.98) if 'APT_RadiatorPanel_' in s.seut.subtypeId else (1.6,3.6)
        for height in heights:
            for x in (-2.35,-1.55,-.85,.85,1.55,2.35):
                for sign in (-1,1):
                    direction=Vector((0,sign,0))
                    assert any(tree.ray_cast(Vector((x,sign*2,height)),-direction,4)[0] is not None
                               for tree in trees), ('Untargetable radiator face',s.name,x,height,sign)
                    assert not any(tree.ray_cast(Vector((x,sign*.26,height)),direction,250)[0] is not None
                                   for tree in trees), ('Radiator collision blocks own cooling ray',s.name)
    return target


def prepare(name):
    source_scene=M['scene_for'](name);bpy.context.window.scene=source_scene;bpy.context.view_layer.update()
    old_pose=None
    radiator_root=next((o for o in source_scene.objects if o.get('native_subpart')=='Thermal_RadiatorPanels'),None) if name in ('Space radiator','Radiator panel') else None
    radiator_angle=radiator_root.rotation_euler.z if radiator_root else 0
    if radiator_root:
        radiator_root.rotation_euler.z=0
        bpy.context.view_layer.update()
    if name=='Reactor housing':
        old_pose=source_scene['thermal_manifolds_deployment']
        runpy.run_path(str(ROOT/'assets/build_reactor_thermal_manifolds.py'))['pose'](0)
    source=M['main_for'](name)
    objects=list(source.objects)
    groups=subparts(name,source)
    assert len({part for part,_,_ in groups})==len(groups),'Duplicate native moving-part IDs'
    assert all(any(o.type=='MESH' for o in members) for _,members,_ in groups),'Empty native moving part'
    if name.startswith('Brayton train'):assert len(groups)==2
    if name=='Reactor housing':assert len(groups)==24
    matrices={o:o.matrix_world.copy() for o in objects}
    ident=M['CONTRACT']['subtype'](name);cells=M['CONTRACT']['SPECS'][name]
    generated=[]
    moving={o for _,members,_ in groups for o in members}
    try:
        for part,members,pivot in groups:
            native=ident+'_'+part
            s,col,root=scene(native,cells,True)
            for obj in members:
                # SEUT exports subpart vertices as (X,Z,-Y), while main
                # vertices and runtime poses use (-X,Z,Y). With our identity
                # native dummies, bake the missing half-turn into the mesh too.
                if obj.type=='MESH':copy_mesh(obj,col,root,Matrix.Rotation(math.pi,4,'Z')@Matrix.Translation(-pivot))
            s['thermal_mesh_frame']='reactor-local (-X,Z,Y)'
            bpy.context.view_layer.update()
            LOD['build_lods'](s,batch=True)
            if part=='Thermal_RadiatorPanels':collision(s,col,root)
            generated.append(s.name)
        s,col,root=scene(ident,cells)
        copies={}
        for obj in objects:
            if obj.type=='MESH' and obj not in moving:copies[obj]=copy_mesh(obj,col,root)
            elif obj.type=='EMPTY' and obj.name.startswith('Thermal reactor / '):
                native=obj.name.removeprefix('Thermal reactor / ')
                if native.startswith(('detector_','subpart_')):
                    target=dummy(col,root,native,matrices[obj],obj.get('file'))
                    copies[obj]=target
                    for k,v in obj.items():
                        if k not in ('_RNA_UI',):target[k]=v
        runpy.run_path(str(ROOT/'assets/highlight_inventory_hatches.py'))['remap_highlights'](copies,native=True)
        for part,members,pivot in groups:
            # SEUT's FBX empty axes otherwise import as a 180-degree Y turn.
            # Compensate the dummy and bake the same half-turn into its mesh.
            dummy(col,root,'subpart_'+part,Matrix.Translation(pivot)@Matrix.Rotation(math.pi,4,'Z'),native_id(ident+'_'+part))
        bpy.context.view_layer.update()
        assert tris(col)>0,('Empty native main',name)
        LOD['build_lods'](s,batch=True)
        stages(s,objects,name,root)
        if name!='Reactor housing':collision(s,col,root)
        generated.append(s.name)
        rows=json.loads((OUT/'native-source-scenes.json').read_text()) if (OUT/'native-source-scenes.json').exists() else {}
        rows[name]={'source':source_scene.name,'scenes':generated,'cells':cells,
                    'moving_parts':[g[0] for g in groups]}
        destination=OUT/'native-source-scenes.json'
        temporary=destination.with_suffix('.tmp')
        temporary.write_text(json.dumps(rows,indent=2)+'\n')
        temporary.replace(destination)
        s['thermal_derived_complete']=True
    finally:
        if old_pose is not None:runpy.run_path(str(ROOT/'assets/build_reactor_thermal_manifolds.py'))['pose'](old_pose)
        if radiator_root:
            bpy.context.window.scene=source_scene
            radiator_root.rotation_euler.z=radiator_angle
            bpy.context.view_layer.update()
    return rows[name]


def export(name, only_stems=None, preserve_collision=False):
    # Material and fitted-detail passes reuse accepted physics. Full initial
    # exports still build collision; a missing accepted HKT is a hard error.
    STAGING.mkdir(parents=True,exist_ok=True)
    rows=json.loads((OUT/'native-source-scenes.json').read_text())
    manifest=STAGING/'sources.json'
    records=json.loads(manifest.read_text()) if manifest.exists() else {}
    records={k:v for k,v in records.items() if v['block']!=name or (only_stems is not None and k not in only_stems)}
    area=next((a for a in bpy.context.screen.areas if a.type=='VIEW_3D'),None) if bpy.context.screen else None
    for key in rows[name]['scenes']:
        s=bpy.data.scenes[key];bpy.context.window.scene=s;bpy.context.view_layer.update()
        cols=C.get_collections(s)
        # The reactor's authored HKT collection holds only its four pillars.
        # Reuse the accepted combined housing/pillar inputs for main and stages.
        if preserve_collision and (cols['hkt'] or s.seut.sceneType=='mainScene'):
            for suffix in (('','_BS1','_BS2','_BS3') if s.seut.sceneType=='mainScene' else ('',)):
                filename=s.seut.subtypeId+suffix+'.hkt'
                shutil.copy2(COLLISIONS/'Thermal'/filename,STAGING/filename)
        if only_stems is not None and not any(EXPORT.get_col_filename(col) in only_stems
                for col in (cols['lod'] or [])+(cols['bs'] or [])+cols['main']):continue
        # SEUT edits all duplicate empty names globally; restore the authoring IDs.
        names={o:o.name for o in bpy.data.objects if o.type=='EMPTY'}
        transforms={o:(o.matrix_basis.copy(),o.empty_display_size) for o in names}
        try:
            with (bpy.context.temp_override(area=area,region=next(r for r in area.regions if r.type=='WINDOW')) if area else nullcontext()):
                for col in (cols['lod'] or [])+(cols['bs'] or [])+cols['main']:
                    if only_stems is not None and EXPORT.get_col_filename(col) not in only_stems:continue
                    modifiers=[]
                    try:
                        for obj in col.objects:
                            if obj.type=='MESH' and any(len(p.vertices)>3 for p in obj.data.polygons):
                                mod=obj.modifiers.new('Native export triangulation','TRIANGULATE');modifiers.append((obj,mod))
                        bpy.context.view_layer.update()
                        deps=bpy.context.evaluated_depsgraph_get()
                        evaluated=sum(len(p.vertices)-2 for obj in col.objects if obj.type=='MESH'
                                      for p in obj.evaluated_get(deps).data.polygons)
                        statuses=EXPORT.export_collection(Reporter(),bpy.context,col)
                        assert all('FINISHED' in status for status in statuses),(col.name,statuses)
                        stem=EXPORT.get_col_filename(col)
                        records[stem]={'block':name,'scene':key,'type':col.seut.col_type,
                                       'index':col.seut.type_index,'triangles':evaluated,'authored_triangles':tris(col),
                                       'reference':EXPORT.get_col_filename(col.seut.ref_col) if col.seut.ref_col else None,
                                       'distance':col.seut.lod_distance if col.seut.col_type=='lod' else None}
                    finally:
                        for obj,mod in modifiers:obj.modifiers.remove(mod)
                if cols['hkt'] and only_stems is None and not preserve_collision:
                    assert OPS.export_hkt(Reporter(),bpy.context)=={'FINISHED'}
        except BaseException:
            # SEUT's temporary material overrides also need undoing when an
            # export is interrupted, before the live scene is shown again.
            for mat in list(bpy.data.materials):
                if mat.override_library or (mat.use_nodes and mat.node_tree.nodes.get('EXPORT_DUMMY')):
                    EXPORT.revert_mat_after_export(Reporter(),bpy.context,mat)
            raise
        finally:
            changed=[o for o,n in names.items() if o.name!=n]
            for o in changed:o.name='Export restore / '+names[o]
            for o in changed:o.name=names[o]
            for o,(matrix,size) in transforms.items():
                o.matrix_basis=matrix;o.empty_display_size=size
        if name=='Reactor housing' and s.seut.sceneType=='mainScene' and only_stems is None and not preserve_collision:
            shutil.copy2(COLLISIONS/'Thermal'/(s.seut.subtypeId+'.hkt'),STAGING/(s.seut.subtypeId+'.hkt'))
        if s.seut.sceneType=='mainScene' and only_stems is None:
            assert (STAGING/(s.seut.subtypeId+'.hkt')).is_file(), 'Missing accepted block collision'
            for stage in (1,2,3):
                target=STAGING/(s.seut.subtypeId+'_BS'+str(stage)+'.hkt')
                if preserve_collision:assert target.is_file(), 'Missing accepted construction collision'
                else:shutil.copy2(STAGING/(s.seut.subtypeId+'.hkt'),target)
    manifest.write_text(json.dumps(records,indent=2)+'\n')
    return {'model':name,'exported_meshes':sum(r['block']==name for r in records.values()),'staging':str(STAGING)}


def export_isolated(name, staging=None, rebuild_collision=False):
    """Use the same native pipeline in a disposable background Blender process.

    SEUT temporarily remaps linked materials. Unrelated scenes and orphan meshes
    make that remap expensive; discard them only in this unsaved export process.
    Live authoring scenes and the full derived blend remain intact.
    """
    global STAGING
    assert not (name == 'Reactor housing' and rebuild_collision), 'Rebuild reactor physics with build_reactor_pillar_collision.py before exporting models'
    assert bpy.app.background, 'Isolation must never discard scenes in the live session'
    # SEUT's GUI error popup crashes background Blender before logging the
    # underlying error. Keep its reporting and cancellation, without the popup.
    errors=importlib.import_module('space-engineers-utilities.seut_errors')
    errors.show_popup_report=lambda context,title,text: print(title+': '+text,flush=True)
    assert Path(bpy.data.filepath)==M['FILE'], 'Start from the reviewed production mains'
    if staging is not None:STAGING=Path(staging).resolve()
    assert STAGING.is_relative_to(ROOT/'src'), 'SEUT staging must be inside the mod directory'
    source=M['scene_for'](name);bpy.context.window.scene=source
    keep=set(M['main_for'](name).objects)
    # Collision generation needs one native rigid-body template. Accepted HKT
    # files are reused by export(); this object is only a Blender-side template.
    keep.add(next(o for o in bpy.data.objects if o.type=='MESH' and o.rigid_body))
    bpy.data.batch_remove(ids=[o for o in bpy.data.objects if o not in keep])
    bpy.data.batch_remove(ids=[s for s in bpy.data.scenes if s!=source])
    prepare(name)
    bpy.data.orphans_purge(do_local_ids=True,do_linked_ids=True,do_recursive=True)
    # Newly added blocks build physics once. Later detail/LOD passes reuse the
    # accepted inputs just like the established thermal family.
    preserve=all((COLLISIONS/'Thermal'/(native_id(M['CONTRACT']['subtype'](name))+suffix+'.hkt')).is_file()
                 for suffix in ('','_BS1','_BS2','_BS3'))
    if name in ('Space radiator','Radiator panel'):
        preserve=preserve and (COLLISIONS/'Thermal'/(native_id(M['CONTRACT']['subtype'](name)+'_Thermal_RadiatorPanels')+'.hkt')).is_file()
    if rebuild_collision:preserve=False
    return export(name,preserve_collision=preserve)


if __name__=='__main__':
    import sys
    args=sys.argv[sys.argv.index('--')+1:]
    rebuild='--rebuild-collision' in args
    args=[a for a in args if a!='--rebuild-collision']
    assert args[0]=='--isolated' and len(args) in (2,3)
    print(export_isolated(args[1],args[2] if len(args)==3 else None,rebuild),flush=True)
