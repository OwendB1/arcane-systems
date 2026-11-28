"""Prepare collision and weld stages in disposable copies of both engine mains."""

import importlib
import math
import runpy
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

ASSETS = Path(__file__).resolve().parent
engine = runpy.run_path(str(ASSETS / "build_shuttle_nozzle.py"))
export = runpy.run_path(str(ASSETS / "export_plasma_tanks.py"))
collections = export["collections"]


def large_stages_and_collision(scene, cols, parts, material):
    half = scene.seut.bBox_Y * 1.25
    hull = scene.name.endswith("_Hull")
    main = cols["main"][0]
    for level in (1, 2, 3):
        parts.col = next(c for c in cols["bs"] if c.seut.type_index == level)
        if hull:
            for x in (-3.45, 3.45):
                for z in (-3.45, 3.45):
                    parts.box("Case rail", (x, 0, z), (0.24, 2 * half - 0.18, 0.24), "Construction")
            for y in (-half + 0.16, 0, half - 0.16):
                for s in (-1, 1):
                    parts.box("Frame span", (0, y, s * 3.45), (7.08, 0.23, 0.24), "Construction")
                    parts.box("Frame post", (s * 3.45, y, 0), (0.24, 0.23, 6.68), "Construction")
        for obj in main.objects:
            if obj.type != "MESH" or obj.get("weld_stage", 3) > level:
                continue
            part = obj.copy()
            part.data = obj.data.copy()
            part.data.materials.clear()
            part.data.materials.append(material)
            parts.col.objects.link(part)
    parts.col = cols["hkt"][0]
    if hull:
        parts.box("Pressure casing", (0, 0, 0), (7.5, 2 * half, 7.5), "Construction", 0)
    else:
        # On the triple mounts, keep the open spaces between the three banks
        # traversable. Each bank has one convex piece for machinery and one for its bell.
        stations = [o.matrix_world.translation for o in main.objects if o.name.startswith("thruster_flame")]
        groups = {}
        for obj in main.objects:
            if obj.type != "MESH":
                continue
            part = obj.name.split(" / ")[-1].split(".")[0]
            if part in ("Aft thrust plate", "Thrust stay", "Bell"):
                parts.col.objects.link(obj.copy())
                continue
            if part in ("Upper inlet chest", "Lower inlet chest", "Duplex inlet seat", "Hydrogen collector"):
                parts.col.objects.link(obj.copy())
                continue
            if obj.get("weld_stage", 3) != 3 and part not in (
                "Chamber casting",
                "Inlet distribution body",
                "Exchanger casting",
                "Pump inlet boss",
                "Hydrogen header runner",
                "Pump inlet neck",
            ):
                continue
            bank = 0
            if len(stations) > 1:
                center = obj.matrix_world @ ((Vector(obj.bound_box[0]) + Vector(obj.bound_box[6])) / 2)
                bank = min(
                    range(len(stations)),
                    key=lambda i: (stations[i].x - center.x) ** 2 + (stations[i].z - center.z) ** 2,
                )
            groups.setdefault(bank, []).extend(obj.matrix_world @ v.co for v in obj.data.vertices)
        for bank, points in groups.items():
            bm = bmesh.new()
            vertices = [bm.verts.new(point) for point in points]
            bmesh.ops.convex_hull(bm, input=vertices)
            bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
            mesh = bpy.data.meshes.new(f"Machinery collision {bank + 1}")
            bm.to_mesh(mesh)
            bm.free()
            parts.col.objects.link(bpy.data.objects.new(mesh.name, mesh))


def export_gimbals(scene, cols, controls, members, output):
    # Build a native scene for each joint with the matching authored distance meshes.
    for control in controls.objects:
        number, axis = control.name.split(" / ")
        joint = axis + number.split()[-1]
        name = scene.name + "_" + joint
        source = members[control]
        pivot = control.matrix_world.translation.copy()
        sub = bpy.data.scenes.new(name)
        bpy.context.window.scene = sub
        sub.view_layers[0].name = "SEUT"
        sub.unit_settings.system = "METRIC"
        sub.seut.sceneType = "subpart"
        sub.seut.gridScale = "large"
        sub.seut.subtypeId = name
        sub.seut.mod_path = scene.seut.mod_path
        sub.seut.export_exportPath = str(output)
        sub.seut.export_deleteLooseFiles = False
        wrapper = bpy.data.collections.new("SEUT (" + name + ")")
        sub.collection.children.link(wrapper)
        wrapper.seut.scene = sub
        wrapper.seut.col_type = "seut"
        wrapper.seut.version = 3
        main = collections.create_seut_collection(sub, "main")
        flip = Matrix.Rotation(math.pi, 4, "Z")
        for col in cols["main"] + [c for c in cols["lod"] if c.objects]:
            level = col.seut.type_index
            target = main
            if col.seut.col_type == "lod":
                target = collections.create_seut_collection(sub, "lod", level, ref_col=main)
                target.seut.lod_distance = col.seut.lod_distance
            objects = [o for o in col.objects if o in source]
            assert objects, (name, col.name)
            for obj in objects:
                pose = obj.matrix_world.copy()
                col.objects.unlink(obj)
                target.objects.link(obj)
                obj.matrix_world = flip @ Matrix.Translation(-pivot) @ pose
        export["export_collections"](sub, output, collision=False)
        bpy.context.window.scene = scene
        dummy = bpy.data.objects.new("subpart_" + joint, None)
        cols["main"][0].objects.link(dummy)
        dummy.matrix_world = Matrix.Translation(pivot) @ flip
        dummy["file"] = name
        bpy.context.view_layer.update()


def build(scene, output):
    bpy.context.window.scene = scene
    scene.seut.mod_path = str(output.parents[2])
    scene.seut.export_exportPath = str(output)
    scene.seut.export_deleteLooseFiles = False
    output.mkdir(parents=True, exist_ok=True)
    cols = collections.get_collections(scene)
    main = cols["main"][0]
    hull = scene.name.endswith("_Hull")
    with bpy.data.libraries.load(str(engine["SEUT"] / "Materials/Materials.blend"), link=True) as (_, lib):
        lib.materials = ["Construction"]
    mat = lib.materials[0]
    parts = engine["Parts"]()
    parts.native = {"Construction": mat}
    parts.name = "Frame"
    if scene.seut.gridScale == "large":
        # Bake the neutral authoring rig in the disposable export. SE's static
        # thruster keeps its native flame markers and fixed grid direction.
        controls = scene.collection.children.get("Nozzle steering - Blender controls")
        if controls:
            for ctrl in controls.objects:
                ctrl.rotation_euler = (0, 0, 0)
            bpy.context.view_layer.update()
            pivots = set(controls.objects)
            members = {c: {o for o in c.children if o.type == "MESH"} for c in pivots}
            for obj in list(scene.objects):
                if obj.parent in pivots and obj.name not in controls.objects:
                    pose = obj.matrix_world.copy()
                    obj.parent = None
                    obj.matrix_world = pose
            bpy.context.view_layer.update()
        large_stages_and_collision(scene, cols, parts, mat)
        if controls:
            export_gimbals(scene, cols, controls, members, output)
        export["export_collections"](scene, output)
        return
    # Stages expose the mounting structure first, then the bell and pipework.
    for level in (1, 2, 3):
        parts.col = next(c for c in cols["bs"] if c.seut.type_index == level)
        if hull:
            for x in (-0.70, 0.70):
                for z in (-0.70, 0.70):
                    parts.box("Longeron", (x, 0, z), (0.085, 2.50, 0.085), "Construction")
            for y in (-1.2, 0, 1.2):
                for s in (-1, 1):
                    parts.box("Cross member", (0, y, s * 0.69), (1.44, 0.082, 0.09), "Construction")
                    parts.box("Side post", (s * 0.69, y, 0), (0.089, 0.085, 1.36), "Construction")
        for obj in main.objects:
            if obj.type != "MESH":
                continue
            name = obj.name
            early = any(
                s in name for s in ("Mount lug", "suspension link", "Pivot", "Inlet casting", "Head casting")
            )
            middle = any(s in name for s in (" / Bell", "Chamber jacket", "Pump carrier", "Rolled mouth"))
            late = any(
                s in name
                for s in (
                    "scroll casting",
                    "Control manifold",
                    "transfer duct",
                    "Injector",
                    "conveyor face",
                    "Armor cassette",
                )
            )
            if early or (level >= 2 and middle) or (level == 3 and late):
                part = obj.copy()
                part.data = obj.data.copy()
                part.data.materials.clear()
                part.data.materials.append(mat)
                parts.col.objects.link(part)
        assert len(parts.col.objects) > 0
    parts.col = cols["hkt"][0]
    if hull:
        parts.box("Case collision", (0, 0, 0), (1.5, 2.5, 1.5), "Construction", 0)
    else:
        # Several narrow convex pieces leave clearance beside the exposed assembly.
        parts.box("Mount collision", (0, 1.112, 0), (0.82, 0.276, 0.82), "Construction")
        parts.cylinder("Head collision", (0, 0.23, 0), (0, 1.02, 0), 0.307, "Construction", 12)
        parts.cylinder("Bell collision", (0, -1.23, 0), (0, -0.60, 0), 0.57, "Construction", 16)
        parts.cylinder("Throat collision", (0, -0.64, 0), (0, 0.27, 0), 0.32, "Construction", 12)
        parts.box("Pump collision", (-0.34, 0.50, 0.17), (0.32, 0.49, 0.34), "Construction")
    export["export_collections"](scene, output)


if __name__ == "__main__":
    assert bpy.app.background
    errors = importlib.import_module("space-engineers-utilities.seut_errors")
    errors.show_popup_report = lambda context, title, message: print(title, message, flush=True)
    build(bpy.context.scene, Path(sys.argv[-1]) / "Models/Cubes" / bpy.context.scene.seut.gridScale)
