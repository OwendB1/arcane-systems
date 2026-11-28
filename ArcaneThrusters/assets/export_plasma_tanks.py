"""Export in a disposable Blender process using the accepted tank mains and Power LOD tools."""
import importlib
import json
import runpy
import sys
from pathlib import Path

import bpy

ASSETS = Path(__file__).resolve().parents[2] / "ArcanePower/assets"
build_lods = runpy.run_path(str(ASSETS / "build_energy_lods.py"))["build_lods"]
stages = runpy.run_path(str(ASSETS / "build_construction_stages.py"))
collections = importlib.import_module("space-engineers-utilities.seut_collections")
export = importlib.import_module("space-engineers-utilities.export.seut_export_utils")
ops = importlib.import_module("space-engineers-utilities.export.seut_ot_export")


def export_tank(scene, output):
    bpy.context.window.scene = scene
    bpy.context.view_layer.update()
    output.mkdir(parents=True, exist_ok=True)
    scene.seut.mod_path = str(output.parents[2])
    scene.seut.export_exportPath = str(output)
    scene.seut.export_deleteLooseFiles = False
    cols = collections.get_collections(scene)
    main = cols["main"][0]
    meshes = [o for o in main.objects if o.type == 'MESH']
    # Export text as real triangles and give each port its own FBX material table.
    for obj in main.objects:
        if obj.type == 'FONT':
            bpy.context.view_layer.objects.active = obj
            with bpy.context.temp_override(selected_editable_objects=[obj], selected_objects=[obj]):
                bpy.ops.object.convert(target='MESH')
            stages["clean_mesh"](obj.data)
        if obj.type == 'MESH' and obj.data.users > 1:
            obj.data = obj.data.copy()
    hulls = cols["hkt"][0] if cols["hkt"] else collections.create_seut_collection(scene, "hkt", ref_col=main)
    for obj in meshes:
        if any(s in obj.name for s in ("Pressure vessel", "Mounting skid", "Conveyor bulkhead", "Exchanger bulkhead", "Service box")):
            hull = obj.copy()
            hull.name = "Hull / " + obj.name
            hulls.objects.link(hull)
    assert len(hulls.objects) == 6
    build_lods(scene, main)
    for index in (1, 2, 3):
        col = next((c for c in cols['bs'] or [] if c.seut.type_index == index), None)
        if col is None:
            col = collections.create_seut_collection(scene, "bs", index)
        for obj in meshes:
            structure = any(s in obj.name for s in ("Mounting skid", "Cast saddle", "Conveyor bulkhead", "Exchanger bulkhead"))
            vessel = any(s in obj.name for s in ("Pressure vessel", "Field winding", "Field supply bus"))
            if structure or (index >= 2 and vessel) or (index == 3 and "Segmented armor" in obj.name):
                part = obj.copy()
                part.data = obj.data.copy()
                part.data.materials.clear()
                part.data.materials.append(bpy.data.materials["Construction"])
                col.objects.link(part)

    export_collections(scene, output)


def export_collections(scene, output, collision=True):
    cols = collections.get_collections(scene)
    def show(layer):
        layer.hide_viewport = False
        for child in layer.children:
            show(child)
    show(bpy.context.view_layer.layer_collection)
    counts = {}
    for col in cols["main"] + (cols["bs"] or []) + (cols["lod"] or []):
        if not col.objects:
            continue
        col.hide_render = col.hide_viewport = False
        for obj in col.objects:
            if obj.type == 'MESH':
                obj.modifiers.new("Export triangulation", "TRIANGULATE")
        bpy.context.view_layer.update()
        deps = bpy.context.evaluated_depsgraph_get()
        counts[export.get_col_filename(col)] = sum(len(p.vertices)-2 for o in col.objects if o.type == 'MESH'
                                                    for p in o.evaluated_get(deps).data.polygons)
        statuses = export.export_collection(export.STDOUT_OPERATOR, bpy.context, col)
        assert all('FINISHED' in status for status in statuses), col.name
    if collision:
        assert ops.export_hkt(export.STDOUT_OPERATOR, bpy.context) == {'FINISHED'}
        hkt = output / (scene.name + ".hkt")
        assert hkt.stat().st_size > 0
    (output / (scene.name + "-counts.json")).write_text(json.dumps(counts))


if __name__ == "__main__":
    assert bpy.app.background
    errors = importlib.import_module("space-engineers-utilities.seut_errors")
    errors.show_popup_report = lambda context, title, message: print(title, message, flush=True)
    output = Path(sys.argv[sys.argv.index('--')+1])
    scene = bpy.data.scenes[sys.argv[-1]]
    native = Path.home() / ".local/share/blender-se1-setup/assets/Materials/Materials.blend"
    with bpy.data.libraries.load(str(native), link=True) as (_, target):
        target.materials = ["Construction"]
    export_tank(scene, output / "Models/Cubes" / scene.seut.gridScale)
