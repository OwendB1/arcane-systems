"""blender -b arcane-power-mockups-v01.blend -t 8 --python render_previews.py"""
import bpy
import sys
from pathlib import Path

out = Path(__file__).resolve().parent / 'previews'
only = next((arg.split('=', 1)[1] for arg in sys.argv if arg.startswith('--only=')), None)
for s in bpy.data.scenes:
    if s.name[:2] not in ['01', '02', '03', '04', '05']:
        continue
    if only and s.name[:2] != only:
        continue
    bpy.context.window.scene = s
    s.frame_set(115 if s.name.startswith('04') else 1)
    if '--animation' in sys.argv:
        if not s.name.startswith(('01', '04')):
            continue
        s.render.engine = 'BLENDER_WORKBENCH'
        s.display.shading.light = 'STUDIO'
        s.display.shading.color_type = 'MATERIAL'
        s.display.shading.show_shadows = True
        s.display.shading.show_cavity = True
        s.display.shading.cavity_type = 'BOTH'
        s.render.resolution_x, s.render.resolution_y = 1000, 625
        s.render.film_transparent = False
        for f in range(1, 241, 4):
            s.frame_set(f)
            s.render.filepath = str(out / ('frames-' + s.name[:2]) / f'{(f-1)//4:03}.png')
            bpy.ops.render.render(write_still=True, scene=s.name)
    else:
        s.render.filepath = str(out / (s.name[:2] + '.png'))
        bpy.ops.render.render(write_still=True, scene=s.name)
