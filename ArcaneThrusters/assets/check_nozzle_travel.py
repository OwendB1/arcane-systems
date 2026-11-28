"""Sample yaw and pitch stops in a disposable copy of an exposed large-grid engine."""

import importlib
import math
from itertools import combinations, product

import bpy
from mathutils.bvhtree import BVHTree


def surface(objects):
    vertices, faces = [], []
    for obj in objects:
        offset = len(vertices)
        vertices.extend(obj.matrix_world @ v.co for v in obj.data.vertices)
        faces.extend(tuple(offset + i for i in face.vertices) for face in obj.data.polygons)
    return BVHTree.FromPolygons(vertices, faces)


def check(scene):
    cols = importlib.import_module("space-engineers-utilities.seut_collections").get_collections(scene)
    main = cols["main"][0]
    triple = scene.seut.subtypeId in ("ArcaneThrusters_DrivePriorityLG", "ArcaneThrusters_VacuumLG")
    count = 3 if triple else 1
    travel = 1.5 if triple else 2.0
    cells = (scene.seut.bBox_X, scene.seut.bBox_Y, scene.seut.bBox_Z)
    assert cells == (3, 2 if scene.seut.subtypeId == "ArcaneThrusters_AtmosphericLG" else 3, 3)
    half_size = tuple(n * 1.25 for n in cells)
    meshes = [o for o in main.objects if o.type == "MESH"]
    fixed = [o for o in meshes if o.parent is None]
    stationary = surface(fixed)
    pumps = surface(
        [
            o
            for o in fixed
            if any(
                word in o.name.lower()
                for word in (
                    "pump",
                    "scroll",
                    "discharge",
                    "outlet",
                    "union",
                    "cover web",
                    "turbine",
                    "inspection",
                )
            )
        ]
    )
    controls = [
        (scene.objects[f"Nozzle {i:02} / Yaw"], scene.objects[f"Nozzle {i:02} / Pitch"])
        for i in range(1, count + 1)
    ]
    axes = {
        (i, j): (controls[j][0].location - controls[i][0].location).normalized()
        for i, j in combinations(range(count), 2)
    }
    intervals = {(k, pair): [] for pair in axes for k in pair}
    clearance = min(half_size)
    for i, (yaw, pitch) in enumerate(controls):
        moving = [o for o in meshes if o.parent in (pitch, yaw)]
        bells = [o for o in moving if " / Bell" in o.name or "Rolled mouth" in o.name]
        flame = main.objects[f"thruster_flame_{i + 1:02}"]
        assert bells and flame.parent == pitch and pitch.parent == yaw
        neutral = flame.matrix_world.translation.copy()
        for a, b in product((-travel, 0, travel), repeat=2):
            yaw.rotation_euler.z, pitch.rotation_euler.x = map(math.radians, (a, b))
            bpy.context.view_layer.update()
            if a or b:
                assert (flame.matrix_world.translation - neutral).length > 0.045, "Detached exhaust"
            assert not surface(bells).overlap(stationary), (i, a, b, "bell contacts fixed hardware")
            assert not surface(moving).overlap(pumps), (i, a, b, "gimbal contacts pump")
            points = [o.matrix_world @ v.co for o in moving for v in o.data.vertices]
            clearance = min(clearance, *(half_size[k] - abs(pt[k]) for pt in points for k in range(3)))
            for pair, axis in axes.items():
                if i in pair:
                    projections = [axis.dot(pt) for pt in points]
                    intervals[i, pair].append((min(projections), max(projections)))
        yaw.rotation_euler.z = pitch.rotation_euler.x = 0
        bpy.context.view_layer.update()
    assert clearance > 0, "Steering exceeds the grid envelope"
    print(f"{scene.name}: minimum sampled grid clearance {clearance:.3f} m")
    for pair in axes:
        i, j = pair
        gap = min(lo for lo, _ in intervals[j, pair]) - max(hi for _, hi in intervals[i, pair])
        assert gap > 0, (i, j, "neighboring nozzles can touch")
        print(f"Nozzles {i + 1}/{j + 1}: minimum projected separation {gap:.3f} m")


if __name__ == "__main__":
    assert bpy.app.background, "Use a background Blender process for the pose check"
    check(bpy.context.scene)
