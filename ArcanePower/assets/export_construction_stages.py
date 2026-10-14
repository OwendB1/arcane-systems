"""Run in the authored Blender project, then tools/compile_construction_stages.py."""
import importlib
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


area = next(a for a in bpy.context.screen.areas if a.type == 'VIEW_3D')
for name in NAMES+ENERGY:
    if name not in bpy.data.scenes: continue
    scene = bpy.data.scenes[name]
    bpy.context.window.scene = scene
    with bpy.context.temp_override(area=area, region=next(r for r in area.regions if r.type == 'WINDOW')):
        for collection in collections.get_collections(scene)['bs']:
            hidden = collection.hide_render
            layer = stage_layer(bpy.context.view_layer.layer_collection, collection)
            hidden_viewport = layer.hide_viewport
            layer.hide_viewport = False
            collection.hide_render = False
            try:
                result = export.export_collection(Reporter(), bpy.context, collection)
            finally:
                collection.hide_render = hidden
                layer.hide_viewport = hidden_viewport
            if any('FINISHED' not in status for status in result):
                raise RuntimeError('Stage export failed: '+collection.name)
