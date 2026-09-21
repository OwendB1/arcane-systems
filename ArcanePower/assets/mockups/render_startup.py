"""Render v02 startup stills or a sampled motion sequence from the saved blend."""
import bpy
import sys
from pathlib import Path

s = bpy.data.scenes['06 Tile assembly startup']
bpy.context.window.scene = s
out = Path(__file__).resolve().parent / 'previews'
if '--animation' in sys.argv:
    s.render.engine = 'BLENDER_WORKBENCH'
    s.display.shading.color_type = 'MATERIAL'
    s.display.shading.light = 'STUDIO'
    s.display.shading.show_shadows = True
    s.display.shading.show_cavity = True
    s.render.resolution_x, s.render.resolution_y = 960, 720
    for i, frame in enumerate(range(1, 481, 4)):
        s.frame_set(frame)
        s.render.filepath = str(out / 'frames-startup' / f'{i:03}.png')
        bpy.ops.render.render(write_still=True)
else:
    for frame, name in [(1, 'startup-parked'), (120, 'startup-raised'),
                        (279, 'startup-40-tiles'), (450, 'startup-running')]:
        s.frame_set(frame)
        s.render.filepath = str(out / (name+'.png'))
        bpy.ops.render.render(write_still=True)
