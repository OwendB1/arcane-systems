"""Derive the hull installation from the finished shuttle engine in a separate SEUT file."""

import importlib
import math
import runpy
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ASSETS = Path(__file__).resolve().parent
drive = runpy.run_path(str(ASSETS / "build_shuttle_nozzle.py"))
cols = importlib.import_module("space-engineers-utilities.seut_collections")
NAME = drive["NAME"] + "_Hull"
PAINT, DARK, STEEL = drive["PAINT"], drive["DARK"], drive["STEEL"]


def casing(p, sectors):
    # The front cavity ends behind the injector. The independent rear pocket
    # ends behind the native conveyor. Both end faces share the four side skins.
    rings = []
    for y, radius, square in (
        (-0.03, 0.25, False),
        (-0.30, 0.34, False),
        (-1.17, 0.628, False),
        (-1.227, 0.636, False),
        (-1.25, 0.66, False),
        (-1.25, 0.75, True),
        (-1.16, 0.75, True),
        (-1.14, 0.722, True),
        (1.14, 0.722, True),
        (1.16, 0.75, True),
        (1.25, 0.75, True),
        (1.25, 0.174, True),
        (1.143, 0.174, True),
    ):
        ring = []
        for i in range(sectors):
            a = math.tau * i / sectors
            c, s = math.cos(a), math.sin(a)
            r = radius / max(abs(c), abs(s)) if square else radius
            ring.append((r * c, y, r * s))
        rings.append(ring)
    verts = [v for ring in rings for v in ring]
    # Triangle fans avoid collinear triangles across the square conveyor backing.
    verts.extend([(0, rings[0][0][1], 0), (0, rings[-1][0][1], 0)])
    faces = [
        (
            k * sectors + i,
            k * sectors + (i + 1) % sectors,
            (k + 1) * sectors + (i + 1) % sectors,
            (k + 1) * sectors + i,
        )
        for k in range(len(rings) - 1)
        for i in range(sectors)
    ]
    for offset, center in ((0, len(verts) - 2), ((len(rings) - 1) * sectors, len(verts) - 1)):
        faces.extend((offset + i, offset + (i + 1) % sectors, center) for i in range(sectors))
    skin = p.mesh("Pressure casing", verts, faces, PAINT)
    skin.data.materials.append(p.native[DARK])
    skin.data.materials.append(p.native[STEEL])
    for f in skin.data.polygons:
        band = f.index // sectors
        if band in (0, 1, 2, 7, 11, 12, 13):
            f.material_index = 1
        elif band == 3:
            f.material_index = 2

    for side in range(4):
        rot = Matrix.Rotation(side * math.pi / 2, 4, "Y")
        before = set(p.col.objects)
        for y in (-0.574, 0.574):
            p.box("Armor cassette", (0, y, 0.728), (1.412, 1.116, 0.036), PAINT, 0.042)
            if sectors >= 48:
                for x in (-0.608, 0.608):
                    for dy in (-0.46, 0.46):
                        p.cylinder("Flush fastener", (x, y + dy, 0.744), (x, y + dy, 0.75), 0.021, STEEL, 6)
        for obj in set(p.col.objects) - before:
            obj.matrix_world = rot @ obj.matrix_basis


def build():
    original = bpy.context.scene
    if (
        original.name != drive["NAME"]
        or Path(bpy.data.filepath).resolve() != ASSETS / "arcane-shuttle-nozzle.blend"
    ):
        raise RuntimeError("Open arcane-shuttle-nozzle.blend before building the hull variant")
    src = cols.get_collections(original)
    scene = bpy.data.scenes.new(NAME)
    bpy.context.window.scene = scene
    scene.unit_settings.system = "METRIC"
    scene.seut.sceneType = "mainScene"
    scene.seut.subtypeId = NAME
    scene.seut.mod_path = str(ASSETS.parent / "src")
    scene.seut.export_exportPath = str(ASSETS.parent / "src/Models/Cubes/small")
    scene.seut.export_sbc_type = "none"
    scene.seut.bBox_X, scene.seut.bBox_Y, scene.seut.bBox_Z = 3, 5, 3
    bpy.ops.scene.recreate_collections()
    scene.seut.gridScale = "small"
    dst = cols.get_collections(scene)
    p = drive["Parts"]()
    p.native = {key: bpy.data.materials[key] for key in (PAINT, DARK, STEEL)}
    keep = (
        " / Bell",
        "Rolled mouth",
        "Plasma field ring",
        "Emitter retainer",
        "Injector",
        "injector plate",
        "Small conveyor face",
    )
    for level, sectors in enumerate((64, 48, 32)):

        def collection(group):
            main = group["main"][0]
            if not level:
                return main
            return next(c for c in group["lod"] if c.seut.type_index == level and c.seut.ref_col == main)

        source = collection(src)
        p.col = collection(dst)
        p.name = f"Hull {level}"
        for obj in source.objects:
            if obj.type == "EMPTY" or any(label in obj.name for label in keep):
                p.col.objects.link(obj)
        casing(p, sectors)
        if level:
            p.col.seut.lod_distance = source.seut.lod_distance
            p.col.hide_render = True

    # Native dummies are shared with the exposed installation, at the same grid coordinates.
    def hide_lods(layer):
        if layer.collection.seut.col_type == "lod":
            layer.hide_viewport = True
        for child in layer.children:
            hide_lods(child)

    hide_lods(bpy.context.view_layer.layer_collection)
    bpy.data.scenes.remove(original)
    bpy.context.view_layer.update()
    main = dst["main"][0]
    points = [o.matrix_world @ v.co for o in main.objects if o.type == "MESH" for v in o.data.vertices]
    for i, half in enumerate((0.75, 1.25, 0.75)):
        assert abs(max(v[i] for v in points) - half) < 1e-4
        assert abs(min(v[i] for v in points) + half) < 1e-4
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            view = area.spaces.active
            view.region_3d.view_rotation = Vector((0.52, -1, 0.37)).to_track_quat("Z", "Y")
            view.region_3d.view_location = (0, 0, 0)
            view.region_3d.view_distance = 4.5
            view.overlay.show_overlays = False
    bpy.ops.wm.save_as_mainfile(filepath=str(ASSETS / "arcane-shuttle-hull.blend"), compress=True)


if __name__ == "__main__":
    build()
