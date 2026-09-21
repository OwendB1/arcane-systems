"""Neutral SEUT material preview; keep vanilla material references for export.

If packed alpha was lost in installed TIF previews, generate a manifest and run
tools/repair_seut_preview_textures.py first. That restores native DDS channels.
"""
import bpy
import importlib
import json
from pathlib import Path
from mathutils import Vector

s = bpy.data.scenes['ArcanePower_ReactorPrototype']
bpy.context.window.scene = s
col = importlib.import_module('space-engineers-utilities.seut_collections').get_collections(s)['main'][0]
materials = {m for o in col.objects if o.type == 'MESH' for m in o.data.materials if m and m.library}
paths = {}
for material in materials:
    if not material.node_tree:
        continue
    group = material.node_tree.nodes.get('SEUT_NODE_GROUP')
    if group and material.seut.technique not in ['GLASS', 'HOLO', 'SHIELD']:
        # Repair preview-only damage from SEUT's active-material callbacks.
        group.inputs['TM Switch'].default_value = 0
        # Alpha blending sorts entire objects against the chamber panes and can
        # hide opaque supports behind glass. Use the native solid preview mode.
        material.surface_render_method = 'DITHERED'
    for node in material.node_tree.nodes:
        if node.type == 'TEX_IMAGE' and node.image:
            paths[node.image.name] = bpy.path.abspath(node.image.filepath, library=node.image.library)
            node.image.reload()
manifest = Path.home()/'.cache/arcane-power/preview-textures.json'
manifest.parent.mkdir(parents=True, exist_ok=True)
manifest.write_text(json.dumps(paths, indent=2))
s.seut.paint_color = (.8, .8, .8)
s.view_settings.view_transform = 'AgX'
s.view_settings.exposure = 0
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        space = area.spaces.active
        space.shading.type = 'MATERIAL'
        space.shading.studio_light = 'studio.exr'
        space.shading.studiolight_rotate_z = .5
        space.shading.studiolight_intensity = .8
        space.shading.use_scene_world = False
        space.overlay.show_overlays = False
        space.region_3d.view_distance = 25
        space.region_3d.view_location = (0, 0, 0)
        space.region_3d.view_rotation = Vector((11, -15, 12)).to_track_quat('Z', 'Y')
        space.region_3d.view_perspective = 'PERSP'
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
print('SEUT preview ready; native texture manifest:', manifest)
