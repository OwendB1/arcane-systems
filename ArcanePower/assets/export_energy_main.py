"""Export finished battery or prototype meshes without rebuilding derived art.

Run in arcane-energy-core.blend. EXPORT_NAMES can restrict a batch. Native MWM
compilation and definition/cache-path wiring follow in tools/export_energy_main.py.
"""
import importlib
import json
from pathlib import Path
import runpy
import shutil

import bpy

ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = Path(bpy.data.filepath).name == 'arcane-power-prototype.blend'
STAGING = ROOT/'src/Models/Cubes/large'/('.prototype-main-stage' if PROTOTYPE else '.energy-main-stage')
COLS = importlib.import_module('space-engineers-utilities.seut_collections')
EXPORT = importlib.import_module('space-engineers-utilities.export.seut_export_utils')


class Reporter:
    def report(self, kind, message):
        print(kind, message, flush=True)


def export_sources(names):
    assert Path(bpy.data.filepath).name in ('arcane-energy-core.blend', 'arcane-power-prototype.blend'), 'Export production, not the review assembly'
    if bpy.app.background:
        # SEUT popup menus crash background Blender; retain the full report in stdout.
        importlib.import_module('space-engineers-utilities.seut_errors').show_popup_report = lambda *args: print('SEUT', args, flush=True)
    for audit in (('audit_reactor_exterior.py', 'audit_controller_details.py') if PROTOTYPE else ('audit_energy_geometry.py',)):
        runpy.run_path(str(ROOT/'assets'/audit))['main']()
    STAGING.mkdir(parents=True, exist_ok=True)
    rows = {}
    area = next(a for a in bpy.context.screen.areas if a.type == 'VIEW_3D')
    for name in names:
        scene = bpy.data.scenes[name]
        bpy.context.window.scene = scene
        previous = scene.seut.export_exportPath, scene.seut.linkSubpartInstances
        target = Path(previous[0])
        target.relative_to(ROOT/'src')
        scene.seut.export_exportPath = str(STAGING)
        scene.seut.linkSubpartInstances = False
        bpy.context.view_layer.update()
        main_col = COLS.get_collections(scene)['main'][0]
        collections = [main_col] + [c for c in COLS.get_collections(scene)['lod'] or []
                                   if c.seut.ref_col == main_col and c.objects]
        triangle_counts={};adjustments=[]
        try:
            for collection in collections:
                # SEUT strips numeric suffixes by swapping names globally.
                # Keep those native names in FBX, then restore authoring IDs.
                empty_names={o:o.name for o in bpy.data.objects if o.type=='EMPTY'}
                empty_state={o:{key:tuple(getattr(o,key)) for key in ('location','rotation_euler','rotation_quaternion','rotation_axis_angle','scale')} for o in empty_names}
                empty_sizes={o:o.empty_display_size for o in empty_names}
                triangulators=[]
                shared_meshes=[]
                try:
                    # Blender's FBX cache can lose per-object material indices
                    # on linked native port copies. Export private mesh data,
                    # then restore the authored sharing exactly.
                    for obj in collection.objects:
                        if obj.type=='MESH' and obj.data.users>1:
                            shared_meshes.append((obj,obj.data));obj.data=obj.data.copy()
                    # Lock concave/boolean polygon tessellation to Blender's
                    # evaluated surface instead of MWMBuilder's FBX importer.
                    if PROTOTYPE:
                        for obj in collection.objects:
                            if obj.type=='MESH' and any(len(p.vertices)>3 for p in obj.data.polygons):
                                modifier=obj.modifiers.new('Export triangulation','TRIANGULATE')
                                triangulators.append((obj,modifier))
                    bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get();count=0
                    for obj in collection.objects:
                        if obj.type!='MESH':continue
                        evaluated=sum(len(p.vertices)-2 for p in obj.evaluated_get(deps).data.polygons)
                        authored=sum(len(p.vertices)-2 for p in obj.data.polygons)
                        count+=evaluated
                        if evaluated!=authored:adjustments.append({'object':obj.name,'authored_triangles':authored,'evaluated_triangles':evaluated})
                    triangle_counts[EXPORT.get_col_filename(collection)]=count
                    with bpy.context.temp_override(area=area, region=next(r for r in area.regions if r.type == 'WINDOW')):
                        statuses = EXPORT.export_collection(Reporter(), bpy.context, collection)
                finally:
                    for obj,modifier in triangulators:obj.modifiers.remove(modifier)
                    for obj,mesh in shared_meshes:
                        temporary=obj.data;obj.data=mesh
                        if temporary.users==0:bpy.data.meshes.remove(temporary)
                    renamed=[o for o,n in empty_names.items() if o.name!=n]
                    for o in renamed:o.name='AP export restore / '+empty_names[o]
                    for o in renamed:o.name=empty_names[o]
                    for o,properties in empty_state.items():
                        for key,value in properties.items():
                            if tuple(getattr(o,key))!=value:setattr(o,key,value)
                        o.empty_display_size=empty_sizes[o]
                assert all('FINISHED' in status for status in statuses), (name, statuses)
        finally:
            scene.seut.export_exportPath, scene.seut.linkSubpartInstances = previous
        hkt = target/(name+'.hkt')
        if name == 'ArcanePower_AdvancedContainmentController':
            hkt = target/'ArcanePower_ContainmentController.hkt'
        has_collision = any(c.objects for c in COLS.get_collections(scene)['hkt'] or [])
        if has_collision and hkt.is_file():
            shutil.copy2(hkt, STAGING/(name+'.hkt'))
        assert (target/(name+'.mwm')).is_file(), 'Missing accepted native model: '+name
        rows[name] = {
            'collections': [EXPORT.get_col_filename(c) for c in collections],
            'triangles': triangle_counts[name],
            'collection_triangles':triangle_counts,
            'authored_triangles':sum(len(p.vertices)-2 for o in main_col.objects if o.type == 'MESH' for p in o.data.polygons),
            'triangulation_adjustments':adjustments,
            'target': target.relative_to(ROOT/'src').as_posix(),
            'collision': hkt.relative_to(ROOT/'src').as_posix() if has_collision and hkt.is_file() else None,
            'collision_model': (target/(name+'.mwm')).relative_to(ROOT/'src').as_posix(),
        }
        (STAGING/(name+'-source.json')).write_text(json.dumps(rows[name], indent=2)+'\n')
    return rows


def main(names):
    original=bpy.context.scene
    try:return export_sources(names)
    finally:
        bpy.context.window.scene=original
        bpy.context.view_layer.update()


if __name__ == '__main__':
    names = globals().get('EXPORT_NAMES') or [s.name for s in bpy.data.scenes if s.name.startswith('ArcanePower_' if PROTOTYPE else 'ArcanePower_Energy')]
    result = {'exported_sources': main(names), 'staging': str(STAGING)}
