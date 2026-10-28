"""Export finished battery or prototype meshes without rebuilding derived art.

Run in an accepted production blend. EXPORT_NAMES can restrict a batch;
export_sources(names, isolate=True) is for disposable background processes. Native MWM
compilation and definition/cache-path wiring follow in tools/export_energy_main.py.
"""
import importlib
import json
from pathlib import Path
import runpy
import shutil

import bpy

ROOT = Path(__file__).resolve().parents[1]
LAB = runpy.run_path(str(ROOT/'tools/prepare_lab.py'))
THERMAL_SUBPARTS = Path(bpy.data.filepath).name == 'arcane-thermal-models.blend'
PROTOTYPE = THERMAL_SUBPARTS or Path(bpy.data.filepath).name == 'arcane-power-prototype.blend'
STAGING = ROOT/'src/Models/Cubes/large'/('.prototype-main-stage' if PROTOTYPE else '.energy-main-stage')
COLS = importlib.import_module('space-engineers-utilities.seut_collections')
EXPORT = importlib.import_module('space-engineers-utilities.export.seut_export_utils')


class Reporter:
    def report(self, kind, message):
        print(kind, message, flush=True)


def export_sources(names, isolate=False):
    assert not isolate or bpy.app.background, 'Isolated exports must never discard live authoring scenes'
    assert Path(bpy.data.filepath).name in ('arcane-energy-core.blend', 'arcane-power-prototype.blend', 'arcane-thermal-models.blend'), 'Export production, not the review assembly'
    if THERMAL_SUBPARTS:
        assert set(names) <= {'ArcanePower_BlastShield'+str(i) for i in range(1, 7)}, 'Thermal blocks use export_thermal_models.py'
        runpy.run_path(str(ROOT/'assets/audit_thermal_models.py'))['audit_blast_shields']()
        if bpy.app.background:
            # In this disposable export process, unrelated linked materials and
            # review instances make SEUT's global remapping needlessly costly.
            scenes = [bpy.data.scenes[name] for name in names]
            bpy.context.window.scene = scenes[0]
            keep = {obj for scene in scenes for obj in scene.objects}
            bpy.data.batch_remove(ids=[obj for obj in bpy.data.objects if obj not in keep])
            bpy.data.batch_remove(ids=[scene for scene in bpy.data.scenes if scene not in scenes])
            bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    if bpy.app.background:
        # SEUT popup menus crash background Blender; retain the full report in stdout.
        importlib.import_module('space-engineers-utilities.seut_errors').show_popup_report = lambda *args: print('SEUT', args, flush=True)
    for audit in (() if THERMAL_SUBPARTS else ('audit_reactor_exterior.py', 'audit_controller_details.py') if PROTOTYPE else ('audit_energy_geometry.py',)):
        runpy.run_path(str(ROOT/'assets'/audit))['main']()
    if isolate and not THERMAL_SUBPARTS:
        # Match the thermal exporter: isolate one reviewed family in a disposable
        # process, avoiding costly global linked-material remaps between models.
        scenes=[bpy.data.scenes[name] for name in names]
        for scene in scenes:
            for obj in scene.objects:
                if obj.type=='EMPTY' and 'file' in obj and obj.seut.linkedScene:
                    obj['file']=EXPORT.correct_for_export_type(scene,EXPORT.get_subpart_reference(obj,COLS.get_collections(scene)))
        bpy.context.window.scene=scenes[0]
        keep={obj for scene in scenes for obj in scene.objects}
        bpy.data.batch_remove(ids=[obj for obj in bpy.data.objects if obj not in keep])
        bpy.data.batch_remove(ids=[scene for scene in bpy.data.scenes if scene not in scenes])
        bpy.data.orphans_purge(do_local_ids=True,do_linked_ids=True,do_recursive=True)
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
        hkt = (LAB['COLLISIONS'] if target==ROOT/'src/Models/Cubes/large' else target)/(name+'.hkt')
        if name == 'ArcanePower_AdvancedContainmentController':
            hkt = LAB['COLLISIONS']/'ArcanePower_ContainmentController.hkt'
        has_collision = any(c.objects for c in COLS.get_collections(scene)['hkt'] or [])
        if has_collision and hkt.is_file():
            shutil.copy2(hkt, STAGING/(name+'.hkt'))
        accepted = LAB['model_source'](name) if target==ROOT/'src/Models/Cubes/large' else target/(name+'.mwm')
        assert accepted.is_file(), 'Missing accepted native model: '+name
        rows[name] = {
            'collections': [EXPORT.get_col_filename(c) for c in collections],
            'triangles': triangle_counts[name],
            'collection_triangles':triangle_counts,
            'authored_triangles':sum(len(p.vertices)-2 for o in main_col.objects if o.type == 'MESH' for p in o.data.polygons),
            'triangulation_adjustments':adjustments,
            'target': target.relative_to(ROOT/'src').as_posix(),
            'collision': hkt.relative_to(ROOT).as_posix() if has_collision and hkt.is_file() else None,
            'collision_model': accepted.relative_to(ROOT).as_posix(),
        }
        (STAGING/(name+'-source.json')).write_text(json.dumps(rows[name], indent=2)+'\n')
    return rows


def main(names):
    original=bpy.context.scene.name
    try:return export_sources(names)
    finally:
        if original in bpy.data.scenes:
            bpy.context.window.scene=bpy.data.scenes[original]
        bpy.context.view_layer.update()


if __name__ == '__main__':
    names = globals().get('EXPORT_NAMES') or (['ArcanePower_BlastShield'+str(i) for i in range(1, 7)] if THERMAL_SUBPARTS else [s.name for s in bpy.data.scenes if s.name.startswith('ArcanePower_' if PROTOTYPE else 'ArcanePower_Energy')])
    result = {'exported_sources': main(names), 'staging': str(STAGING)}
