"""Run in the authored Blender project, then tools/compile_construction_stages.py."""
import importlib
import json
import sys
from pathlib import Path
import bpy

sys.path.insert(0,str(Path(__file__).resolve().parent))
from build_construction_stages import NAMES, ENERGY

export = importlib.import_module('space-engineers-utilities.export.seut_export_utils')
collections = importlib.import_module('space-engineers-utilities.seut_collections')


class Reporter:
    def report(self, kind, message):
        print(kind, message)


def stage_layer(layer, collection):
    if layer.collection == collection:
        return layer
    for child in layer.children:
        found = stage_layer(child, collection)
        if found is not None:
            return found


def main(names=NAMES+ENERGY, output=None):
    if bpy.app.background:
        importlib.import_module('space-engineers-utilities.seut_errors').show_popup_report=lambda *args:print('SEUT',args,flush=True)
    area=next(a for a in bpy.context.screen.areas if a.type=='VIEW_3D');path=Path(output)/'construction-source.json' if output else None
    rows=json.loads(path.read_text()) if path and path.exists() else {}
    for name in names:
        if name not in bpy.data.scenes:continue
        scene=bpy.data.scenes[name];bpy.context.window.scene=scene;bpy.context.view_layer.update()
        previous=scene.seut.export_exportPath
        if output:scene.seut.export_exportPath=str(output)
        try:
            with bpy.context.temp_override(area=area,region=next(r for r in area.regions if r.type=='WINDOW')):
                for collection in collections.get_collections(scene)['bs']:
                    hidden=collection.hide_render;layer=stage_layer(bpy.context.view_layer.layer_collection,collection);hidden_viewport=layer.hide_viewport
                    layer.hide_viewport=False;collection.hide_render=False;bpy.context.view_layer.update()
                    try:statuses=export.export_collection(Reporter(),bpy.context,collection)
                    finally:collection.hide_render=hidden;layer.hide_viewport=hidden_viewport
                    if any('FINISHED' not in status for status in statuses):raise RuntimeError('Stage export failed: '+collection.name)
                    rows[export.get_col_filename(collection)]={'triangles':sum(len(p.vertices)-2 for o in collection.objects if o.type=='MESH' for p in o.data.polygons),'block':name,'stage':collection.seut.type_index}
        finally:scene.seut.export_exportPath=previous
    if path:path.write_text(json.dumps(rows,indent=2)+'\n')
    return rows


if __name__=='__main__':result=main(globals().get('EXPORT_NAMES',NAMES+ENERGY),globals().get('EXPORT_DIRECTORY'))
