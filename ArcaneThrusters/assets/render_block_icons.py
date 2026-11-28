"""Render the main SEUT meshes of a production blend to the supplied PNG directory."""
import importlib
import sys
from pathlib import Path

import bpy
from mathutils import Vector

collections = importlib.import_module("space-engineers-utilities.seut_collections")


def render(source, output):
    bpy.context.window.scene = source
    bpy.context.view_layer.update()
    # Snapshot world poses while the source rig is active. Its neutral gimbal
    # meshes live under empties which do not belong in the icon scene.
    meshes = [(obj.data, obj.matrix_world.copy()) for obj in collections.get_collections(source)["main"][0].objects
              if obj.type == "MESH" and not obj.hide_render]
    studio = bpy.data.scenes.new("Arcane block icon")
    bpy.context.window.scene = studio
    studio.view_layers[0].name = "SEUT"
    studio.view_layers[0]["Paint Color"] = (.55, .55, .55)
    studio.view_layers[0]["UV Grid Overlay"] = 0.0
    points = []
    for mesh, pose in meshes:
        obj = bpy.data.objects.new(mesh.name, mesh)
        studio.collection.objects.link(obj)
        obj.matrix_world = pose
        points.extend(pose @ vertex.co for vertex in mesh.vertices)

    name = source.seut.subtypeId
    toward_camera = Vector((1.0, -1.45, .74))
    if "DrivePriority" in name:
        # See the duplex face and the pump deck from the pipefitter's side.
        toward_camera = Vector((1.35, 1.1, .8))
    elif "Tank" in name or "Charger" in name:
        toward_camera = Vector((1.05, -1.7, .9))
    rotation = (-toward_camera).to_track_quat("-Z", "Y")
    view = rotation.inverted()
    projected = [view @ p for p in points]
    bounds = [(min(p[i] for p in projected), max(p[i] for p in projected)) for i in range(3)]
    center = rotation @ Vector([(lo + hi) / 2 for lo, hi in bounds])
    span = max(hi - lo for lo, hi in bounds[:2])
    camera = bpy.data.objects.new("Icon camera", bpy.data.cameras.new("Icon camera"))
    studio.collection.objects.link(camera)
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = span * 1.09
    camera.location = center + toward_camera.normalized() * span * 3
    camera.rotation_euler = rotation.to_euler()
    studio.camera = camera
    for position, power in [((-.9, 1.2, 1.5), 55), ((1, .1, 1.2), 32), ((.4, 1, -1.1), 56)]:
        light = bpy.data.lights.new("Softbox", "AREA")
        light.energy, light.size = power * span**2, span
        obj = bpy.data.objects.new("Softbox", light)
        studio.collection.objects.link(obj)
        obj.location = center + rotation @ (Vector(position) * span)
        obj.rotation_euler = (center - obj.location).to_track_quat("-Z", "Y").to_euler()
    studio.world = bpy.data.worlds.new("Arcane icon studio")
    studio.world.use_nodes = True
    background = studio.world.node_tree.nodes["Background"]
    background.inputs["Color"].default_value = (.22, .25, .30, 1)
    background.inputs["Strength"].default_value = .8
    studio.render.engine = "CYCLES"
    studio.cycles.samples = 20
    studio.cycles.use_denoising = True
    studio.render.resolution_x = studio.render.resolution_y = 256
    studio.render.resolution_percentage = 100
    studio.render.film_transparent = True
    studio.render.image_settings.file_format = "PNG"
    studio.render.image_settings.color_mode = "RGBA"
    studio.render.filepath = str(output / (name + ".png"))
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    output = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
    for source in list(bpy.data.scenes):
        if source.seut.subtypeId.startswith("ArcaneThrusters_"):
            render(source, output)
