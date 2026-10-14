"""Finalize the existing vent models in the current prototype via Blender MCP.

Preserves the fitted art, conveyor ports and outlet leaf dummies. Run this, then
export VentDuct, VentOutlet and VentHatch using SEUT with SBC generation disabled.
"""
import importlib
from pathlib import Path

import bpy
from mathutils import Matrix

ROOT = Path(__file__).resolve().parents[1]
collections = importlib.import_module('space-engineers-utilities.seut_collections')
backup = Path.home() / '.cache/arcane-power/vent/before.blend'
backup.parent.mkdir(parents=True, exist_ok=True)
if not backup.exists():
    bpy.ops.wm.save_as_mainfile(filepath=str(backup), copy=True)

for name in ('ArcanePower_VentDuct', 'ArcanePower_VentOutlet'):
    scene = bpy.data.scenes[name]
    bpy.context.window.scene = scene
    cols = collections.get_collections(scene)
    collision = cols['hkt'][0]
    collision.hide_viewport = False
    bpy.context.view_layer.update()
    assert len(collision.objects) == 8
    for obj in collision.objects:
        # Native Havok must receive positioned shapes, independent of rigid-body
        # transforms. Do not recopy the reactor's now-solid platform colliders.
        world = obj.matrix_world.copy()
        obj.data = obj.data.copy()
        obj.data.transform(world)
        obj.parent = None
        obj.matrix_world = Matrix.Identity(4)
        obj.rigid_body.collision_shape = 'CONVEX_HULL'
        obj.rigid_body.use_margin = True
        obj.rigid_body.collision_margin = .01
    collision.seut.hkt_file = ''
    scene.seut.export_sbc_type = 'none'
    scene.seut.export_deleteLooseFiles = False
    scene['ap_required_installation'] = 'Reactor > 1-15 aligned VentDuct blocks > VentOutlet; fully built, same grid'
    scene['ap_collision_revision'] = 'baked-eight-sector-open-bore-v1'

bpy.data.scenes['ArcanePower_ReactorPrototype']['ap_required_installation'] = (
    'Two controllers and centered roof stack: 1-15 VentDuct blocks followed by VentOutlet')
bpy.data.scenes['ArcanePower_VentHatch'].seut.export_sbc_type = 'none'
bpy.data.scenes['ArcanePower_VentHatch'].seut.export_deleteLooseFiles = False
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / 'assets/arcane-power-prototype.blend'))
print('Vent models prepared: existing native ports, four outlet leaves, eight baked hulls per section')
