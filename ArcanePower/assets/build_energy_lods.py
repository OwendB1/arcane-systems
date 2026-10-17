"""Native SEUT distance meshes, derived only after either main family is settled.

Keep glass seams and emissives exact; preserve connector silhouettes and UVs.
Reduce curved equipment tessellation and drop small hardware at distance.
"""
import importlib
import json
import runpy
from array import array
from pathlib import Path
import bpy

ROOT=Path(__file__).resolve().parents[1]
COLS=importlib.import_module('space-engineers-utilities.seut_collections')
CLEAN=runpy.run_path(str(ROOT/'assets/build_construction_stages.py'))['clean_mesh']


def triangles(mesh):return sum(len(p.vertices)-2 for p in mesh.polygons)


def normalize_uv(mesh):
    # Join matches UV layers by name. Native imports use Float2/map1 while
    # authored frames use UVMap; joining them directly fills missing UVs with 0.
    layer=next((uv for uv in mesh.uv_layers if uv.active_render),mesh.uv_layers.active)
    assert layer is not None,('Missing source UVs',mesh.name)
    values=array('f',[0])*(len(mesh.loops)*2)
    layer.data.foreach_get('uv',values)
    for uv in list(mesh.uv_layers):mesh.uv_layers.remove(uv)
    layer=mesh.uv_layers.new(name='UVMap',do_init=False)
    layer.data.foreach_set('uv',values);layer.active_render=True


def build_lods(scene, reference=None, batch=False):
    bpy.context.window.scene=scene;bpy.context.view_layer.update()
    cols=COLS.get_collections(scene);main=reference or cols['main'][0]
    meshes=[o for o in main.objects if o.type=='MESH']
    field=meshes and all(all(m and m.name.startswith(('ArcanePlasma','EnergyGlow','EnergyFill')) for m in o.data.materials) for o in meshes)
    if field or sum(triangles(o.data) for o in meshes)<1000:
        for col in list(cols['lod'] or []):
            if col.seut.ref_col==main:
                for obj in list(col.objects):bpy.data.objects.remove(obj,do_unlink=True)
                bpy.data.collections.remove(col)
        return {'lods':[],'reason':'Keep exact driven field silhouette' if field else 'Already small; keep exact main'}
    existing={}
    for col in cols['lod'] or []:
        if col.seut.ref_col!=main:continue
        if col.seut.type_index in (1,2) and col.seut.type_index not in existing:existing[col.seut.type_index]=col
        elif not col.objects:bpy.data.collections.remove(col)
    points=[o.matrix_world @ v.co for o in meshes for v in o.data.vertices]
    extent=max(max(p[i] for p in points)-min(p[i] for p in points) for i in range(3))
    distances=(75,150) if extent>3 else (35,90)
    report=[]
    for level,distance,ratio in ((1,distances[0],.55),(2,distances[1],.25)):
        col=existing.get(level) or COLS.create_seut_collection(scene,'lod',level,main)
        for obj in list(col.objects):bpy.data.objects.remove(obj,do_unlink=True)
        col.hide_viewport=False;col.hide_render=False
        reducible=[]
        for source in meshes:
            powered=any(m and any(t in m.name for t in ('Emissive','EnergyGlow','EnergyFill','EnergyStatus','ArcanePlasma','ClearChamber','Glass','ThermalHot','ThermalCold','ThermalStatus')) for m in source.data.materials)
            decal=source.get('texture_support') or source.get('fastener_body') or source.name.startswith(('Texture detail /','Marking /'))
            native_decal=source.get('source_asset') and all(m and m.name.startswith(('Atlas','TextAtlas','Paneling','Decals','Button')) for m in source.data.materials)
            if not powered and (decal or native_decal or max(source.dimensions)<(.12 if level==1 else .24)):continue
            obj=source.copy();obj.data=source.data.copy();obj.name='LOD%d / '%level+source.name
            normalize_uv(obj.data)
            col.objects.link(obj);obj.parent=None;obj.matrix_world=source.matrix_world.copy()
            obj['lod_source']=source.name;obj['lod_level']=level
            protected=powered or source.name.startswith(('Energy / chamber glazing','Curved chamber / pane'))
            # Small structural boxes retain their exact hard faces and chamfers.
            if not protected and triangles(obj.data)>96:
                if batch:
                    reducible.append(obj)
                    continue
                modifier=obj.modifiers.new('Distance tessellation','DECIMATE')
                modifier.ratio=ratio;modifier.use_collapse_triangulate=True
                bpy.context.view_layer.objects.active=obj
                bpy.ops.object.modifier_apply(modifier=modifier.name)
        if batch and reducible:
            # Native export copies are already in one coordinate space. Batch
            # the reducible pieces so each level needs one evaluated operation;
            # pressure glass, emitters and small hard faces remain exact.
            bpy.context.view_layer.update()
            obj=reducible[0]
            with bpy.context.temp_override(active_object=obj,object=obj,
                    selected_objects=reducible,selected_editable_objects=reducible):
                bpy.ops.object.join()
            modifier=obj.modifiers.new('Distance tessellation','DECIMATE')
            modifier.ratio=ratio;modifier.use_collapse_triangulate=True
            bpy.context.view_layer.objects.active=obj
            bpy.ops.object.modifier_apply(modifier=modifier.name)
        for obj in col.objects:
            if obj.type=='MESH' and not any(m and (m.seut.technique=='GLASS' or any(t in m.name for t in ('Emissive','EnergyGlow','EnergyFill','EnergyStatus','ArcanePlasma','ThermalHot','ThermalCold','ThermalStatus'))) for m in obj.data.materials):
                CLEAN(obj.data)
        col.seut.lod_distance=distance
        count=sum(triangles(o.data) for o in col.objects if o.type=='MESH')
        assert 0<count<sum(triangles(o.data) for o in meshes),(scene.name,level,count)
        report.append({'level':level,'distance_m':distance,'triangles':count})
        col.hide_render=True
    def hide(layer):
        if layer.collection.seut.col_type=='lod':layer.hide_viewport=True
        for child in layer.children:hide(child)
    hide(bpy.context.view_layer.layer_collection)
    scene['lod_source_revision']=3
    return {'main_triangles':sum(triangles(o.data) for o in meshes),'lods':report}


def main():
    original=bpy.context.scene
    energy='ArcanePower_EnergyCore' in bpy.data.scenes
    reports={s.name:build_lods(s) for s in list(bpy.data.scenes)
        if s.name.startswith('ArcanePower_Energy' if energy else 'ArcanePower_')}
    bpy.context.window.scene=original
    (ROOT/('validation/energy-lods.json' if energy else 'validation/prototype-lods.json')).write_text(json.dumps(reports,indent=2)+'\n')
    return reports


if __name__=='__main__':main()
