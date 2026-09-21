"""Remove obsolete trunk boxes after the widened round housing has been built."""
import bpy
import importlib

s = bpy.data.scenes['ArcanePower_ReactorPrototype']
assert s.get('housings_widened'), 'Widen the housing before removing its old trunk boxes'
bpy.context.window.scene = s
col = importlib.import_module('space-engineers-utilities.seut_collections').get_collections(s)['main'][0]
removed = []
for obj in list(col.objects):
    if obj.name.startswith('Radial conveyor trunk'):
        removed.append(obj.name)
        bpy.data.objects.remove(obj, do_unlink=True)
    elif obj.name.startswith('Base upgrade / adapter plate') and not obj.get('seated_in_round_hull'):
        # Leave the front/native port fixed; extend only the rear into the curved
        # shell so the thin surrounding plate cannot float at its outer corners.
        for vertex in obj.data.vertices:
            if vertex.co.y > 0:
                vertex.co.y *= 2
        obj['seated_in_round_hull'] = True
s['radial_trunks_removed'] = True
bpy.context.view_layer.update()
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
print('Removed obsolete radial trunks:', removed)
