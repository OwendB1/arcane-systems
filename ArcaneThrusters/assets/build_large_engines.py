"""Build one large-grid engine from a fresh SEUT Blender session. See README for arguments."""

import importlib
import math
import runpy
import sys
from itertools import pairwise
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ASSETS = Path(__file__).resolve().parent
drive = runpy.run_path(str(ASSETS / "build_shuttle_nozzle.py"))
collections = importlib.import_module("space-engineers-utilities.seut_collections")
PAINT, DARK, STEEL, CAST = (
    drive["PAINT"],
    drive["DARK"],
    drive["STEEL"],
    "ShuttleCastAlloy",
)
ROTATE = drive["TO_BLOCK"]


def square(y, z, radius, clip=0):
    if not clip:
        return [
            (y - radius, z - radius),
            (y + radius, z - radius),
            (y + radius, z + radius),
            (y - radius, z + radius),
        ]
    return [
        (y + a, z + b)
        for a, b in (
            (-radius + clip, -radius),
            (radius - clip, -radius),
            (radius, -radius + clip),
            (radius, radius - clip),
            (radius - clip, radius),
            (-radius + clip, radius),
            (-radius, radius - clip),
            (-radius, -radius + clip),
        )
    ]


def plate(p, name, outline, holes, x, depth, material):
    return drive["pierced_plate"](p, name, outline, holes, (x, 0, 0), (0, 1, 0), (0, 0, 1), depth, material)


def shell_at(p, name, stations, y, z, material, sectors):
    obj = drive["shell"](p, name, stations, material, sectors)
    obj.location = (0, y, z)
    return obj


def fit_bell(p, y, z, lip, radial, mouth_radial, length, level):
    sectors = (80, 48, 24)[level]
    start = lip - 1.231 * length
    old = set(p.col.objects)
    drive["nozzle"](p, sectors)
    if mouth_radial != radial:
        # Shape the skirt downstream of its clamping flange. Apply the same
        # contour to the liner, field ring and rolled lip so their seats follow it.
        for part in set(p.col.objects) - old:
            for vertex in part.data.vertices:
                t = min(1.0, max(0.0, (vertex.co.x - 0.325) / (1.198 - 0.325)))
                flare = 1 + (mouth_radial / radial - 1) * t * (2 - t)
                vertex.co.y *= flare
                vertex.co.z *= flare
    if level == 0:
        drive["injector"](p)
    else:
        p.cylinder("Injector face", (0.075, 0, 0), (0.106, 0, 0), 0.232, STEEL, 24)
        for cy, cz in [(0, 0)] + drive["circle"](0, 0, 0.142, 6):
            p.cylinder("Injector recess", (0.105, cy, cz), (0.110, cy, cz), 0.04, DARK, 12)
    fit = Matrix.Translation((start, y, z)) @ Matrix.Diagonal(Vector((length, radial, radial, 1)))
    moving = set(p.col.objects) - old
    for obj in moving:
        obj.matrix_world = fit @ obj.matrix_basis
        obj["weld_stage"] = 2
    return moving


def turbopump(p, center, scale, roll, level):
    """Fit the shuttle's complete scroll, cover, turbine and outlet as one assembly."""
    old = set(p.col.objects)
    drive["pump"](p, level)
    fit = (
        Matrix.Translation(center)
        @ Matrix.Rotation(roll, 4, "X")
        @ Matrix.Scale(scale, 4)
        @ Matrix.Translation((0.598, 0.362, -0.198))
    )
    for obj in set(p.col.objects) - old:
        obj.matrix_world = fit @ obj.matrix_basis
    return fit @ Vector((-0.322, -0.395, 0.198))


def pump_mounts(p, root, bells, triple, level):
    """Keep each scroll and its short discharge elbow on the fixed side of the joint."""
    sides = (32, 24, 16)[level]
    if triple:
        for y, z in bells:
            # Each branch ends in its own flanged casting, leaving a clear sightline
            # between the three pump stations and their gimbals.
            shell_at(
                p,
                "Branch pump housing",
                [
                    (root - 1.56, 0.39),
                    (root - 1.55, 0.53),
                    (root - 1.47, 0.55),
                    (root - 1.37, 0.48),
                    (root - 0.96, 0.48),
                    (root - 0.83, 0.57),
                    (root - 0.60, 0.57),
                    (root - 0.51, 0.50),
                    (root - 0.51, 0.38),
                ],
                y,
                z,
                CAST,
                sides,
            )
            shell_at(
                p,
                "Pump station flange",
                [
                    (root - 1.50, 0.50),
                    (root - 1.50, 0.61),
                    (root - 1.42, 0.61),
                    (root - 1.40, 0.50),
                ],
                y,
                z,
                STEEL,
                sides,
            )
            if level < 2:
                for dy, dz in drive["circle"](0, 0, 0.554, 8):
                    p.cylinder(
                        "Station flange bolt",
                        (root - 1.46, y + dy, z + dz),
                        (root - 1.38, y + dy, z + dz),
                        0.040,
                        DARK,
                        6,
                    )
    for y, z in bells:
        # The three service faces point into different gaps in the cluster.
        directions = (
            [Vector((-z, y)).normalized()]
            if triple
            else [Vector((-1, 0.20)).normalized(), Vector((1, 0.20)).normalized()]
        )
        for side in directions:
            spacing, scale = (1.14, 2.7) if triple else (1.73, 3.6)
            axis = Vector((0, side.x, side.y))
            seat = Vector((root - (1.45 if triple else 1.82), y, z))
            center = seat + axis * spacing
            p.cylinder(
                "Pump mounting neck",
                seat + axis * 0.33,
                center,
                scale * 0.098,
                CAST,
                sides,
            )
            p.cylinder(
                "Pump mounting flange",
                center - axis * 0.29,
                center - axis * 0.19,
                scale * 0.125,
                STEEL,
                sides,
            )
            outlet = turbopump(p, center, scale, math.atan2(-side.x, side.y), level)
            target = Vector((root - 0.86, y, z)) + axis * (0.48 if triple else 1.28)
            if triple:
                # Sweep the return in one plane with enough radius for both pipe walls.
                bend = (outlet - target).dot(axis) / 2
                path = [
                    (bend * math.sin(t), bend * (math.cos(t) - 1), 0)
                    for t in (math.pi * i / 12 for i in range(13))
                ]
                path.append((target.x - outlet.x, -2 * bend, 0))
                elbow = p.tube("Pump discharge elbow", path, scale * 0.065, CAST, 0.04, sides)
                elbow.location = outlet
                elbow.rotation_euler.x = math.atan2(axis.z, axis.y)
            else:
                corner = outlet + Vector((0.18, 0, 0))
                drive["pipe"](
                    p,
                    "Pump discharge elbow",
                    [outlet, corner, corner - axis * 0.18, target],
                    scale * 0.065,
                    CAST,
                    sides,
                )
            p.cylinder(
                "Discharge union",
                outlet - Vector((0.08, 0, 0)),
                outlet + Vector((0.06, 0, 0)),
                scale * 0.087,
                STEEL,
                12,
            )


def gimbal(p, root, y, z, triple, length, radial, level):
    """Build a fixed fork, a yaw cradle and a hollow pitch knuckle on intersecting axes."""
    r = 0.60 if triple else 1.18
    n = (48, 32, 24)[level]
    pivot = Vector((root + 0.02, y, z))
    along = Vector((1, 0, 0))
    pitch_axis = Vector((0, 1, 0))
    yaw_axis = Vector((0, 0, 1))
    # The fork cheeks have machined pin bores. Their feet land on the fixed collar.
    cheek = [(-0.64 * r, -0.25 * r), (0, -0.25 * r)]
    cheek.extend(
        (0.25 * r * math.cos(a), 0.25 * r * math.sin(a))
        for a in [-math.pi / 2 + j * math.pi / 12 for j in range(1, 13)]
    )
    cheek.append((-0.64 * r, 0.25 * r))
    for sign in (-1, 1):
        foot = pivot - along * 0.49 * r + yaw_axis * sign * r * 1.10
        p.box("Fork foot", foot, (0.43 * r, 0.54 * r, 0.77 * r), CAST, 0.06 * r)
        base = pivot + yaw_axis * (sign * 1.48 * r - 0.10 * r)
        drive["pierced_plate"](
            p,
            "Gimbal fork cheek",
            cheek,
            [drive["circle"](0, 0, 0.135 * r, 16)],
            base,
            along,
            pitch_axis,
            0.20 * r,
            PAINT,
        )
        p.cylinder(
            "Yaw trunnion",
            pivot + yaw_axis * sign * 1.25 * r,
            pivot + yaw_axis * sign * 1.61 * r,
            0.131 * r,
            STEEL,
            n,
        )
    # The drive housing stays on the fork. Its round gearbox sits over the yaw pin.
    top = pivot + yaw_axis * (1.64 * r)
    p.cylinder(
        "Yaw reduction gear",
        top - yaw_axis * 0.07 * r,
        top + yaw_axis * 0.17 * r,
        0.30 * r,
        CAST,
        n,
    )
    p.cylinder(
        "Servo cover",
        top + yaw_axis * 0.15 * r,
        top + yaw_axis * 0.20 * r,
        0.23 * r,
        STEEL,
        n,
    )
    motor = top + yaw_axis * 0.045 * r
    p.cylinder(
        "Gimbal servo motor",
        motor - along * 0.70 * r,
        motor - along * 0.16 * r,
        0.155 * r,
        DARK,
        n,
    )
    for t in (0.63, 0.51, 0.38, 0.23):
        p.cylinder(
            "Servo case rib",
            motor - along * (t + 0.023) * r,
            motor - along * (t - 0.023) * r,
            0.176 * r,
            CAST,
            n,
        )
    p.box(
        "Servo terminal",
        motor - along * 0.52 * r + yaw_axis * 0.16 * r,
        (0.21 * r, 0.17 * r, 0.12 * r),
        PAINT,
        0.018 * r,
    )
    old = set(p.col.objects)
    shell_at(
        p,
        "Gimbal yaw cradle",
        [
            (root - 0.095 * r, 1.18 * r),
            (root - 0.13 * r, 1.26 * r),
            (root - 0.08 * r, 1.36 * r),
            (root + 0.12 * r, 1.36 * r),
            (root + 0.16 * r, 1.27 * r),
            (root + 0.10 * r, 1.18 * r),
        ],
        y,
        z,
        CAST,
        n,
    )
    for sign in (-1, 1):
        ctr = pivot + pitch_axis * (sign * 1.29 * r)
        p.cylinder(
            "Pitch bearing housing",
            ctr - pitch_axis * 0.22 * r,
            ctr + pitch_axis * 0.22 * r,
            0.265 * r,
            PAINT,
            n,
        )
        end = ctr + pitch_axis * (sign * 0.245 * r)
        p.cylinder(
            "Pitch bearing cap",
            end - pitch_axis * sign * 0.08 * r,
            end,
            0.21 * r,
            STEEL,
            n,
        )
        if level < 2:
            for dx, dz in drive["circle"](0, 0, 0.158 * r, 6):
                off = Vector((dx, 0, dz))
                p.cylinder(
                    "Bearing cap screw",
                    end + off - pitch_axis * sign * 0.01 * r,
                    end + off + pitch_axis * sign * 0.033 * r,
                    0.031 * r,
                    DARK,
                    6,
                )
    yaw = set(p.col.objects) - old
    old = set(p.col.objects)
    # Size the injector socket from the bell tooling. Its shoulder covers the
    # 0.234-radius retainer and steps into the bell wall just past its first ring.
    shell_at(
        p,
        "Swivel throat",
        [
            (root - 0.20 * r, 0.88 * r),
            (root - 0.16 * r, 0.97 * r),
            (root, 0.995 * r),
            (root + 0.032 * length, 0.252 * radial),
            (root + 0.160 * length, 0.252 * radial),
            (root + 0.177 * length, 0.256 * radial),
            (root + 0.185 * length, 0.256 * radial),
            (root + 0.185 * length, 0.230 * radial),
            (root + 0.165 * length, 0.210 * radial),
            (root - 0.20 * r, 0.82 * r),
        ],
        y,
        z,
        STEEL,
        n,
    )
    for sign in (-1, 1):
        p.cylinder(
            "Pitch trunnion",
            pivot + pitch_axis * sign * 0.92 * r,
            pivot + pitch_axis * sign * 1.33 * r,
            0.14 * r,
            STEEL,
            n,
        )
    return yaw, set(p.col.objects) - old


def rig_gimbals(scene, root, bells, joints, triple):
    controls = bpy.data.collections.new("Nozzle steering - Blender controls")
    scene.collection.children.link(controls)
    degrees = 1.5 if triple else 2.0
    for i, ((y, z), (cradle, nozzle)) in enumerate(zip(bells, joints), 1):
        pivot = ROTATE @ Vector((root + 0.02, y, z))
        parent = None
        for label, axis, parts in (("Yaw", 2, cradle), ("Pitch", 0, nozzle)):
            ctrl = bpy.data.objects.new(f"Nozzle {i:02} / {label}", None)
            controls.objects.link(ctrl)
            ctrl.parent = parent
            ctrl.location = pivot if parent is None else (0, 0, 0)
            ctrl.empty_display_type = "ARROWS"
            ctrl.empty_display_size = 0.54 if triple else 1.0
            ctrl.lock_location = ctrl.lock_scale = (True, True, True)
            ctrl.lock_rotation = [j != axis for j in range(3)]
            limit = ctrl.constraints.new("LIMIT_ROTATION")
            limit.name = f"{label} travel ±{degrees}°"
            limit.owner_space = "LOCAL"
            limit.use_transform_limit = True
            for j, key in enumerate("xyz"):
                setattr(limit, "use_limit_" + key, True)
                travel = math.radians(degrees) if j == axis else 0
                setattr(limit, "min_" + key, -travel)
                setattr(limit, "max_" + key, travel)
            bpy.context.view_layer.update()
            for obj in parts:
                obj.parent = ctrl
                obj.matrix_parent_inverse = ctrl.matrix_world.inverted()
            parent = ctrl
    bpy.context.view_layer.update()


def ship_distributor(p, half, root, level):
    sectors = (48, 32, 20)[level]
    core_start, core_end, radius = -half + 0.55, root - 0.41, 1.32
    p.cylinder(
        "Inlet distribution body",
        (core_start, 0, 0),
        (core_end, 0, 0),
        radius,
        CAST,
        sectors,
    )
    for x in (core_start + 0.13, core_end - 0.22):
        shell_at(
            p,
            "Machined coupling",
            [
                (x - 0.11, radius - 0.02),
                (x - 0.11, radius + 0.12),
                (x - 0.055, radius + 0.21),
                (x + 0.09, radius + 0.21),
                (x + 0.12, radius - 0.02),
            ],
            0,
            0,
            STEEL,
            sectors,
        )
    for i in range(8):
        a = i * math.tau / 8
        y, z = math.cos(a), math.sin(a)
        rail = p.box(
            "Distributor rib",
            ((core_start + core_end) / 2, y * radius, z * radius),
            (core_end - core_start - 0.30, 0.23, 0.21),
            DARK,
            0.04,
        )
        rail.rotation_euler.x = a


def thermal_exchangers(p, half, root, bells, level):
    # A shallow two-tier casting feeds the lower pair and the upper engine at the bulkhead.
    rear = -half + 0.24
    p.box("Lower inlet chest", (rear + 0.20, 0, -1.04), (0.40, 5.78, 2.60), CAST, 0.14)
    p.box("Upper inlet chest", (rear + 0.18, 0, 0.99), (0.36, 2.18, 3.78), CAST, 0.13)
    p.box("Duplex inlet seat", (rear + 0.18, 2.44, 0.17), (0.36, 1.11, 1.31), STEEL, 0.10)
    for y, z in bells:
        seat = rear + (0.33 if z > 0 else 0.37)
        end = root - 1.44
        # A short, finned socket bolts the pump housing straight to the manifold face.
        stations = [
            (seat, 0.93, 0.26),
            (seat + 0.09, 0.93, 0.26),
            (seat + 0.15, 0.65, 0.29),
            (end - 0.33, 0.65, 0.29),
            (end - 0.12, 0.53, 0.26),
            (end, 0.49, 0.26),
        ]
        assert all(a[0] < b[0] for a, b in pairwise(stations))
        verts = [(x, a, b) for x, width, clip in stations for a, b in square(y, z, width, clip)]
        faces = [
            (8 * j + i, 8 * j + (i + 1) % 8, 8 * (j + 1) + (i + 1) % 8, 8 * (j + 1) + i)
            for j in range(len(stations) - 1)
            for i in range(8)
        ]
        faces += [tuple(reversed(range(8))), tuple(range(len(verts) - 8, len(verts)))]
        p.mesh("Exchanger casting", verts, faces, CAST)
        # Use the free flats beside the scroll for the removable finned covers.
        for side in (-1, 1):
            normal = Vector((0, 0, side) if z > 0 else (0, side, 0))
            rotation = math.pi / 2 if z > 0 else 0.0
            start, stop = seat + 0.18, end - 0.36
            center = Vector(((start + stop) / 2, y, z))
            cover = p.box(
                "Exchanger cover", center + normal * 0.66, (stop - start + 0.10, 0.10, 0.67), DARK, 0.03
            )
            cover.rotation_euler.x = rotation
            count = (5, 4, 3)[level]
            for j in range(count):
                x = start + j * (stop - start) / (count - 1)
                fin = p.box(
                    "Exchanger fin", Vector((x, y, z)) + normal * 0.74, (0.04, 0.13, 0.61), STEEL, 0.016
                )
                fin.rotation_euler.x = rotation
        if level < 2:
            for sy in (-1, 1):
                for sz in (-1, 1):
                    dy, dz = y + sy * 0.75, z + sz * 0.75
                    p.cylinder(
                        "Exchanger foot bolt",
                        (seat + 0.07, dy, dz),
                        (seat + 0.135, dy, dz),
                        0.081,
                        STEEL,
                        6,
                    )


def hydrogen_manifold(p, half, root, bells, level):
    """The central conveyor feeds a squat collector with three pump takeoffs."""
    rear = -half + 0.25
    sides = (36, 24, 16)[level]
    p.cylinder("Hydrogen collector", (rear - 0.01, 0, 0), (rear + 0.68, 0, 0), 1.04, CAST, sides)
    for y, z in bells:
        axis = Vector((0, y, z)).normalized()
        start = Vector((rear + 0.36, 0, 0))
        elbow = Vector((rear + 0.36, y, z))
        p.cylinder("Hydrogen header runner", start + axis * 0.85, elbow, 0.32, CAST, sides)
        p.cylinder("Runner union", elbow - axis * 0.66, elbow - axis * 0.52, 0.40, STEEL, sides)
        end = root - 1.49
        p.cylinder("Pump inlet boss", (rear - 0.03, y, z), (rear + 0.65, y, z), 0.55, CAST, sides)
        p.cylinder("Pump inlet neck", (rear + 0.59, y, z), (end, y, z), 0.41, DARK, sides)
        p.cylinder("Pump inlet flange", (end - 0.10, y, z), (end + 0.01, y, z), 0.57, STEEL, sides)


def machinery(p, family, half, bells, root, level):
    sectors = (48, 32, 20)[level]
    if family == "vacuum":
        hydrogen_manifold(p, half, root, bells, level)
    elif family == "thermal":
        thermal_exchangers(p, half, root, bells, level)
    else:
        ship_distributor(p, half, root, level)
    for y, z in bells:
        r = 0.58 if len(bells) == 3 else 1.16
        shell_at(
            p,
            "Chamber casting",
            [
                (root - 0.59, r * 0.86),
                (root - 0.53, r),
                (root - 0.23, r),
                (root - 0.15, r * 0.94),
                (root - 0.15, r * 0.82),
                (root - 0.59, r * 0.78),
            ],
            y,
            z,
            CAST,
            sectors,
        )
        shell_at(
            p,
            "Chamber clamp",
            [
                (root - 0.26, r - 0.02),
                (root - 0.27, r + 0.13),
                (root - 0.12, r + 0.13),
                (root - 0.08, r - 0.02),
            ],
            y,
            z,
            STEEL,
            sectors,
        )
        if level < 2:
            for dy, dz in drive["circle"](0, 0, r + 0.07, 8):
                p.cylinder(
                    "Clamp stud",
                    (root - 0.16, y + dy, z + dz),
                    (root - 0.095, y + dy, z + dz),
                    0.057,
                    DARK,
                    6,
                )


def back(p, half, family, hull, level, port, bells):
    thermal = family == "thermal"
    start = -half
    edge = 3.75 if hull else 3.55
    holes = [square(0, 0, 0.68)]
    if thermal:
        holes.append(square(2.5, 0, 0.98, 0.08))
    if family == "vacuum":
        # Solid clean-out covers sit inside these recesses, flush with the mounting plane.
        holes.extend(drive["circle"](y, z, 0.56, (32, 24, 16)[level]) for y, z in bells)
    elif not hull:
        for sign in (-1, 1):
            holes.extend(square(y, sign * 2.13, 0.62, 0.26) for y in (-1.85, 1.85))
    plate(
        p,
        "Aft thrust plate",
        square(0, 0, edge, 0 if hull else 0.58),
        holes,
        start,
        0.25,
        PAINT,
    )
    p.box("Conveyor recess backing", (start + 0.32, 0, 0), (0.16, 1.55, 1.55), DARK)
    pose = Matrix.Rotation(-math.pi / 2, 4, "Y")
    pose.translation = (start + 1.25, 0, 0)
    face = port.copy()
    p.col.objects.link(face)
    face.name = p.name + " / Large conveyor face"
    face.matrix_world = pose
    if thermal:
        p.port("Drive duplex", (start, 2.5, 0), (-1, 0, 0), "PRIMARY")
        for sign in (-1, 1):
            p.cylinder(
                "Duplex bore backing",
                (start + 0.22, 2.5, sign * 0.46),
                (start + 0.34, 2.5, sign * 0.46),
                0.31,
                DARK,
                24,
            )
    if family == "vacuum":
        for y, z in bells:
            sides = (32, 24, 16)[level]
            p.cylinder("Inspection cover seat", (start + 0.08, y, z), (start + 0.27, y, z), 0.57, DARK, sides)
            p.cylinder("Hydrogen clean-out cover", (start + 0.045, y, z), (start + 0.09, y, z), 0.49, CAST, sides)
            if level < 2:
                for dy, dz in drive["circle"](0, 0, 0.37, 6):
                    p.cylinder("Clean-out screw", (start + 0.012, y + dy, z + dz),
                               (start + 0.051, y + dy, z + dz), 0.052, STEEL, 6)
    if hull or len(bells) == 3:
        return
    for sy in (-1, 1):
        for sz in (-1, 1):
            y, z = sy * 2.75, sz * 2.75
            p.box("Thrust shoe", (start + 0.27, y, z), (0.27, 0.64, 0.64), CAST, 0.085)
            end = (start + 2.06, sy * 0.91, sz * 0.91)
            p.cylinder(
                "Thrust stay",
                (start + 0.33, y, z),
                end,
                0.205,
                PAINT,
                (16, 12, 8)[level],
            )
            if level < 2:
                top = Vector((start + 0.33, y, z))
                axis = Vector(end) - top
                p.cylinder(
                    "Forged stay sleeve",
                    top + 0.06 * axis,
                    top + 0.59 * axis,
                    0.265,
                    CAST,
                    20,
                )
                for t in (0.10, 0.54):
                    p.cylinder(
                        "Sleeve locking band",
                        top + t * axis,
                        top + (t + 0.036) * axis,
                        0.29,
                        STEEL,
                        16,
                    )
            p.cylinder(
                "Shoe pin",
                (start + 0.18, y - 0.37, z),
                (start + 0.18, y + 0.37, z),
                0.135,
                STEEL,
                16,
            )


def casing(p, half, bells, lip, radial, level):
    radius = radial * 0.621
    sectors = (80, 48, 24)[level]
    holes = [drive["circle"](y, z, radius + 0.13, sectors) for y, z in bells]
    plate(
        p,
        "Armored nozzle surround",
        square(0, 0, 3.75),
        holes,
        half - 0.26,
        0.215,
        PAINT,
    )
    for y, z in bells:
        # Chamfer the aperture into a lining that overlaps the outside of the rolled mouth.
        shell_at(
            p,
            "Recess bezel",
            [
                (half, radius + 0.135),
                (half - 0.025, radius + 0.08),
                (lip + 0.03, radius - 0.015),
                (lip - 0.10, radius - 0.03),
                (lip - 0.12, radius + 0.11),
                (half - 0.035, radius + 0.17),
            ],
            y,
            z,
            STEEL,
            sectors,
        )
    # Four replaceable, slotted heat shields key the exhaust face to the rim.
    for sy in (-1, 1):
        for sz in (-1, 1):
            y, z = sy * 3.05, sz * 3.12
            outline = [
                (y + sy * a, z + sz * b)
                for a, b in (
                    (-0.55, -0.27),
                    (-0.32, -0.48),
                    (0.50, -0.48),
                    (0.55, -0.40),
                    (0.55, 0.48),
                    (-0.55, 0.48),
                )
            ]
            slots = []
            for dy in (-0.245, 0, 0.245):
                slots.append(
                    [
                        (y + sy * (dy + a), z + sz * b)
                        for a, b in (
                            (-0.08, -0.17),
                            (-0.04, -0.25),
                            (0.08, -0.25),
                            (0.08, 0.19),
                            (0.04, 0.25),
                            (-0.08, 0.25),
                        )
                    ]
                )
            plate(p, "Slotted heat shield", outline, slots, half - 0.046, 0.037, CAST)
            for dy in (-0.42, 0.42):
                p.cylinder(
                    "Captive shield pin",
                    (half - 0.013, y + dy, z + sz * 0.36),
                    (half, y + dy, z + sz * 0.36),
                    0.065,
                    STEEL,
                    8,
                )
    count = 4 if half > 4 else 3
    span = (2 * half - 0.50) / count
    for side in range(4):
        rot = Matrix.Rotation(side * math.pi / 2, 4, "X")
        old = set(p.col.objects)
        p.box(
            "Side pressure skin",
            (0, 0, 3.59),
            (2 * half - 0.36, 7.46, 0.27),
            DARK,
            0.016,
        )
        for j in range(count):
            x = -half + 0.25 + (j + 0.5) * span
            for sign in (-1, 1):
                y = sign * 1.865
                p.box(
                    "Removable armor panel",
                    (x, y, 3.712),
                    (span - 0.045, 3.69, 0.068),
                    PAINT,
                    0.05,
                )
                if level == 0:
                    for dx in (-1, 1):
                        # Captive slots sit in small dark seats on the panel face.
                        p.box(
                            "Latch seat",
                            (x + dx * (span * 0.5 - 0.21), y, 3.747),
                            (0.18, 0.37, 0.006),
                            DARK,
                            0,
                        )
        for obj in set(p.col.objects) - old:
            obj.matrix_world = rot @ obj.matrix_basis


def build(family, mount):
    if family not in ("main", "thermal", "vacuum", "atmospheric") or mount not in ("open", "hull"):
        raise ValueError("Expected main|thermal|vacuum|atmospheric and open|hull")
    if bpy.data.filepath or list(bpy.data.scenes.keys()) != ["Scene"]:
        raise RuntimeError("Build from a fresh Blender scene")
    stock = bpy.context.scene
    triple = family in ("thermal", "vacuum")
    hull = mount == "hull"
    subtype = {"main": "DualModeThrusterLG", "thermal": "DrivePriorityLG", "vacuum": "VacuumLG", "atmospheric": "AtmosphericLG"}[family]
    name = "ArcaneThrusters_" + subtype + ("_Hull" if hull else "")
    half = 5.0 if triple and hull else 3.75
    radial, length = (2.43, 2.65) if triple else (4.52, 3.38)
    if family == "atmospheric":
        # Keep the single engine's pump deck at the same mount-relative station.
        half, length = 2.5, 3.38 - 2.5 / 1.231
    lip = half - 0.18
    bells = [(0, 1.75), (-1.73, -1.16), (1.73, -1.16)] if triple else [(0, 0)]
    mouth_radial = 3.08 if family == "atmospheric" else radial
    if triple and not hull:
        length, mouth_radial = 3.64, 2.69
        bells = [(0, 1.925), (-1.87, -1.35), (1.87, -1.35)]
    root = lip - 1.231 * length
    scene = bpy.data.scenes.new(name)
    bpy.context.window.scene = scene
    scene.unit_settings.system = "METRIC"
    scene.seut.sceneType = "mainScene"
    scene.seut.subtypeId = name
    scene.seut.mod_path = str(ASSETS.parent / "src")
    scene.seut.export_exportPath = str(ASSETS.parent / "src/Models/Cubes/large")
    scene.seut.export_sbc_type = "none"
    scene.seut.bBox_X, scene.seut.bBox_Y, scene.seut.bBox_Z = 3, int(half * 2 / 2.5), 3
    bpy.ops.scene.recreate_collections()
    scene.seut.gridScale = "large"
    cols = collections.get_collections(scene)
    p = drive["Parts"]()
    names = [PAINT, DARK, STEEL, "PaintedMetal_Darker", "Metal_Shiny"]
    with bpy.data.libraries.load(str(drive["SEUT"] / "Materials/Materials.blend"), link=True) as (_, lib):
        lib.materials = names.copy()
    p.native = dict(zip(names, lib.materials))
    with bpy.data.libraries.load(str(ASSETS / "arcane-shuttle-nozzle.blend")) as (
        _,
        lib,
    ):
        lib.materials = ["ArcanePlasmaBell", "ShuttleBellAlloy", CAST]
    p.native.update({m.name: m for m in lib.materials})
    with bpy.data.libraries.load(str(drive["SEUT"] / "Models/Common.blend")) as (
        _,
        lib,
    ):
        lib.objects = ["Conveyor LG"]
    port = lib.objects[0]
    main = cols["main"][0]
    joints = [([], []) for _ in bells]
    for level in range(3):
        p.col = (
            main
            if level == 0
            else next(c for c in cols["lod"] if c.seut.ref_col == main and c.seut.type_index == level)
        )
        p.name = f"{family} {mount} L{level}"
        p.support, p.ports = [], []
        back(p, half, family, hull, level, port, bells)
        for obj in p.col.objects:
            obj["weld_stage"] = 1
        for i, (y, z) in enumerate(bells):
            moving = fit_bell(p, y, z, lip, radial, mouth_radial, length, level)
            if not hull:
                yaw, pitch = gimbal(p, root, y, z, triple, length, radial, level)
                joints[i][0].extend(yaw)
                joints[i][1].extend(moving | pitch)
        if hull:
            casing(p, half, bells, lip, mouth_radial, level)
            if family == "vacuum":
                hydrogen_manifold(p, half, root, bells, level)
        else:
            machinery(p, family, half, bells, root, level)
            pump_mounts(p, root, bells, triple, level)
        bpy.context.view_layer.update()
        for obj in list(p.col.objects):
            if obj.type == "FONT":
                if obj.data.body == "PRIMARY":
                    bpy.data.objects.remove(obj, do_unlink=True)
                    continue
                mesh = bpy.data.meshes.new_from_object(
                    obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
                )
                text = bpy.data.objects.new(obj.name + " mesh", mesh)
                p.col.objects.link(text)
                text.matrix_world = obj.matrix_world.copy()
                bpy.data.objects.remove(obj, do_unlink=True)
                obj = text
            if obj.type == "EMPTY" and level:
                bpy.data.objects.remove(obj, do_unlink=True)
                continue
            if any(
                part in obj.name
                for part in (
                    "Inlet distribution body",
                    "Chamber casting",
                    "Exchanger casting",
                    "Hydrogen header runner",
                    "Pump inlet neck",
                )
            ):
                obj["weld_stage"] = 2
            if any(label in obj.name for label in ("inlet chest", "Duplex inlet seat", "Hydrogen collector", "Pump inlet boss")):
                obj["weld_stage"] = 1
            if "Side pressure skin" in obj.name or (
                "Removable armor panel" in obj.name and obj.location.z > 3
            ):
                obj["weld_stage"] = 4  # Upper armor closes at full integrity.
            obj.matrix_world = ROTATE @ obj.matrix_world
        if level:
            p.col.seut.lod_distance = (100, 260)[level - 1]
            p.col.hide_render = True
    pose = ROTATE @ Matrix.Rotation(-math.pi / 2, 4, "Y") @ Matrix.Rotation(math.pi / 2, 4, "Z")
    pose.translation = (0, half, 0)
    port_dummy = bpy.data.objects.new("detector_conveyor_inlet", None)
    main.objects.link(port_dummy)
    port_dummy.matrix_world = pose
    for i, (y, z) in enumerate(bells, 1):
        flame = bpy.data.objects.new(f"thruster_flame_{i:02}", None)
        main.objects.link(flame)
        flame.rotation_euler.z = math.pi
        flame.location = (y, -lip, z)
        flame.scale = (1.14 * mouth_radial,) * 3
        flame.empty_display_size = 0.12
        joints[i - 1][1].append(flame)
    bpy.context.view_layer.update()
    points = [
        obj.matrix_world @ v.co for obj in main.objects if obj.type == "MESH" for v in obj.data.vertices
    ]
    for axis, r in enumerate((3.75, half, 3.75)):
        lo, hi = min(v[axis] for v in points), max(v[axis] for v in points)
        assert lo >= -r - 0.0001 and hi <= r + 0.0001, (axis, lo, hi)
        if hull:
            assert abs(lo + r) < 0.0001 and abs(hi - r) < 0.0001

    if not hull:
        rig_gimbals(scene, root, bells, joints, triple)

    def hide_lods(layer):
        if layer.collection.seut.col_type == "lod":
            layer.hide_viewport = True
        for child in layer.children:
            hide_lods(child)

    hide_lods(bpy.context.view_layer.layer_collection)
    bpy.data.scenes.remove(stock)
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            v = area.spaces.active
            v.overlay.show_overlays = False
            v.shading.type = "MATERIAL"
            v.shading.studio_light = "studio.exr"
            v.shading.studiolight_intensity = 1.15
            v.shading.studiolight_rotate_z = 0.55
            v.region_3d.view_rotation = Vector((-0.76, -1, 0.47)).to_track_quat("Z", "Y")
            v.region_3d.view_location = (0, 0, 0)
            v.region_3d.view_distance = 18 if triple else 17
            v.lens = 40
    bpy.ops.wm.save_as_mainfile(filepath=str(ASSETS / f"arcane-{family}-lg-{mount}.blend"), compress=True)


if __name__ == "__main__":
    build(*sys.argv[sys.argv.index("--") + 1 :])
