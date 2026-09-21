"""Render the rounded SEUT detail study, including native interface closeups."""
import bpy
from pathlib import Path
from mathutils import Vector

s = bpy.data.scenes['08 Rounded reactor detail']
bpy.context.window.scene = s
out = Path(__file__).resolve().parent/'previews'
s.render.engine = 'CYCLES'
s.cycles.samples = 32


def shot(name, position, target, scale, frame=440):
    s.frame_set(frame)
    s.camera.location = position
    s.camera.rotation_euler = (Vector(target)-s.camera.location).to_track_quat('-Z', 'Y').to_euler()
    s.camera.data.ortho_scale = scale
    s.render.filepath = str(out/(name+'.png'))
    bpy.ops.render.render(write_still=True)


shot('detail-rounded', (6, -27, 15), (0, 0, 4.7), 20.5)
shot('detail-interfaces', (8, -17, 7), (1.4, -4.2, 2.05), 9)
shot('detail-parked', (6, -27, 18), (0, 0, 4.7), 20.5, 1)
