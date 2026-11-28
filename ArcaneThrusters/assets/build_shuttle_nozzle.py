"""Build the standalone shuttle engine in a fresh SEUT-enabled Blender session."""

import importlib
import math
import runpy
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ASSETS = Path(__file__).resolve().parent
POWER = ASSETS.parents[1] / "ArcanePower/assets"
SEUT = Path.home() / ".local/share/blender-se1-setup/assets"
Parts = runpy.run_path(str(POWER / "thermal_parts.py"))["Parts"]
NAME = "ArcaneThrusters_DualModeThrusterSG"
STEEL, DARK, CAST = "Metal_Dull", "PaintedMetal_VeryDark", "PaintedMetal_Darker"
PAINT = "PaintedMetal_Colorable"
# Profiles run from the ship mount (-X) to the lip (+X). Face vanilla SE forward on export.
TO_BLOCK = Matrix.Rotation(-math.pi / 2, 4, "Z")


def shell(p, name, profile, mat, sides=64):
    """Revolve a closed cross section; smooth the circumference, preserve profile edges."""
    verts = [
        (x, r * math.cos(i * math.tau / sides), r * math.sin(i * math.tau / sides))
        for x, r in profile
        for i in range(sides)
    ]
    faces = [
        (
            j * sides + i,
            j * sides + (i + 1) % sides,
            ((j + 1) % len(profile)) * sides + (i + 1) % sides,
            ((j + 1) % len(profile)) * sides + i,
        )
        for j in range(len(profile))
        for i in range(sides)
    ]
    obj = p.mesh(name, verts, faces, mat)
    for f in obj.data.polygons:
        f.use_smooth = True
    for edge in obj.data.edges:
        a, b = edge.vertices
        edge.use_edge_sharp = a // sides == b // sides
    return obj


def pipe(p, name, points, radius, mat, sides=20):
    """Round the visible bends of a cast duct between its flange seats."""
    points = list(map(Vector, points))
    path = [points[0]]
    for prev, corner, after in zip(points, points[1:], points[2:]):
        cut = min((prev - corner).length, (after - corner).length) * 0.42
        a = corner + (prev - corner).normalized() * cut
        b = corner + (after - corner).normalized() * cut
        for i in range(7):
            t = i / 6
            path.append((1 - t) ** 2 * a + 2 * t * (1 - t) * corner + t * t * b)
    return p.tube(name, path + [points[-1]], radius, mat, radius * 0.22, sides)


def mount_pad(p, y, z):
    # A clipped four-corner pad with a genuine bolt bore and a countersunk entry.
    sides = 24
    verts = []
    for x, radius, square in (
        (-1.25, 0.084, True),
        (-1.164, 0.084, True),
        (-1.164, 0.032, False),
        (-1.237, 0.032, False),
        (-1.25, 0.043, False),
    ):
        for j in range(sides):
            a = math.tau * j / sides
            c, sn = math.cos(a), math.sin(a)
            r = min(radius / max(abs(c), abs(sn)), radius * 1.23) if square else radius
            verts.append((x, y + r * c, z + r * sn))
    faces = [
        (
            i * sides + j,
            i * sides + (j + 1) % sides,
            ((i + 1) % 5) * sides + (j + 1) % sides,
            ((i + 1) % 5) * sides + j,
        )
        for i in range(5)
        for j in range(sides)
    ]
    p.mesh("Mount lug", verts, faces, PAINT)


def service_hardware(p):
    # Bracketed electrical box with heat fins, plugs and a small retaining strap.
    for j in range(5):
        p.box("Controller fin", (-0.713 + j * 0.033, -0.246, -0.247), (0.014, 0.029, 0.101), STEEL, 0.004)
    for x in (-0.692, -0.601):
        p.cylinder("Cable gland", (x, -0.158, -0.301), (x, -0.158, -0.339), 0.027, STEEL, 6)
        pipe(
            p,
            "Controller lead",
            [
                (x, -0.158, -0.328),
                (x, -0.158, -0.379),
                (x + 0.037, -0.18, -0.40),
                (x + 0.115, -0.205, -0.38),
                (x + 0.14, -0.196, -0.21),
            ],
            0.012,
            "RubberDry",
            12,
        )
    p.box("Pipe bracket", (-0.54, -0.24, 0.306), (0.062, 0.117, 0.046), CAST, 0.006)
    p.cylinder("Bracket pin", (-0.54, -0.277, 0.322), (-0.54, -0.277, 0.347), 0.018, STEEL, 6)
    # A split clamp only where the pipe has a straight run to seat it.
    p.cylinder("Transfer duct ferrule", (-0.337, -0.395, 0.198), (-0.31, -0.395, 0.198), 0.085, STEEL, 32)
    for sign in (-1, 1):
        p.box("Clevis ear", (-0.438, sign * 0.191, -0.23), (0.092, 0.041, 0.077), PAINT, 0.009)
        p.cylinder(
            "Clevis pin", (-0.438, sign * 0.157, -0.23), (-0.438, sign * 0.223, -0.23), 0.021, STEEL, 16
        )


def pierced_plate(p, name, outline, holes, origin, along, up, thickness, material):
    """Extrude the actual bores and both faces from the same constrained triangulation."""
    from mathutils.geometry import delaunay_2d_cdt

    points, loops, edges = [], [], []
    for boundary in [outline] + holes:
        first = len(points)
        points.extend(map(Vector, boundary))
        loop = list(range(first, len(points)))
        loops.append(loop)
        edges.extend(zip(loop, loop[1:] + loop[:1]))
    verts, _, triangles, _, _, regions = delaunay_2d_cdt(points, edges, loops, 1, 1e-7)
    assert len(verts) == len(points)
    base, along, up = Vector(origin), Vector(along), Vector(up)
    normal = along.cross(up).normalized()
    n = len(verts)
    solid = [base + along * v.x + up * v.y + normal * h for h in (0, thickness) for v in verts]
    caps = [tuple(f) for f, region in zip(triangles, regions) if set(region) == {0}]
    faces = caps + [tuple(i + n for i in f) for f in caps]
    faces.extend((a, b, b + n, a + n) for a, b in edges)
    return p.mesh(name, solid, faces, material)


def circle(cx, cy, r, count):
    return [
        (cx + r * math.cos(j * math.tau / count), cy + r * math.sin(j * math.tau / count))
        for j in range(count)
    ]


def suspension_link(p, y, z):
    # Tapered forging with a bored bearing eye at each end and visible pin shoulders.
    outer = Vector((-1.187, y * 0.342, z * 0.342))
    inner = Vector((-0.915, y * 0.138, z * 0.138))
    along = (inner - outer).normalized()
    side = Vector((0, -z, y)).normalized()
    up = side.cross(along)
    length = (outer - inner).length
    outline = [
        (0.058 * math.cos(a), 0.058 * math.sin(a))
        for a in (math.pi / 2 + i * math.pi / 12 for i in range(13))
    ]
    outline += [
        (length + 0.075 * math.cos(a), 0.075 * math.sin(a))
        for a in (-math.pi / 2 + i * math.pi / 12 for i in range(13))
    ]
    pierced_plate(
        p,
        "Forged suspension link",
        outline,
        [circle(0, 0, 0.026, 16), circle(length, 0, 0.034, 16)],
        outer - side * 0.027,
        along,
        up,
        0.054,
        CAST,
    )
    for center, radius in ((outer, 0.024), (inner, 0.032)):
        p.cylinder("Pivot pin", center - side * 0.054, center + side * 0.054, radius, STEEL, 20)
        p.cylinder("Pivot pin keeper", center + side * 0.042, center + side * 0.060, radius * 1.30, STEEL, 12)
    # The pivot ears land on the casting; their open gap clears the link.
    for sign in (-1, 1):
        a = inner + side * (sign * 0.046)
        p.cylinder("Pivot ear", a - side * 0.014, a + side * 0.014, 0.065, PAINT, 20)


def pump(p, level=None):
    # A lobed cover on an asymmetric scroll casting with a tangential discharge.
    cx, cy = -0.598, -0.362
    levels = [
        (0.065, 0.112, 0),
        (0.088, 0.151, 0),
        (0.135, 0.171, 0),
        (0.225, 0.170, 0),
        (0.247, 0.158, 0),
        (0.255, 0.158, 0.010),
        (0.27, 0.158, 0.010),
        (0.275, 0.140, 0),
        (0.30, 0.128, 0),
        (0.314, 0.101, 0),
        (0.318, 0.059, 0),
    ]
    sides = 64 if level is None else (48, 32, 16)[level]
    verts = []
    for z, r, lobe in levels:
        for j in range(sides):
            t = j * math.tau / sides
            rr = r * (1 + 0.14 * math.cos(t + 0.49)) + lobe * (0.5 + 0.5 * math.cos(8 * t))
            verts.append((cx + rr * math.cos(t), cy + rr * math.sin(t), z))
    faces = [
        (k * sides + j, k * sides + (j + 1) % sides, (k + 1) * sides + (j + 1) % sides, (k + 1) * sides + j)
        for k in range(len(levels) - 1)
        for j in range(sides)
    ]
    faces += [tuple(reversed(range(sides))), tuple(range(len(verts) - sides, len(verts)))]
    casing = p.mesh("Offset scroll casting", verts, faces, "ShuttleCastAlloy")
    casing.data.materials.append(p.native[STEEL])
    for face in casing.data.polygons[:-2]:
        band = face.index // sides
        face.use_smooth = True
        if band in (4, 6):
            face.material_index = 1
    for e in casing.data.edges:
        a, b = e.vertices
        e.use_edge_sharp = a // sides == b // sides
    if level is not None:
        # Stepped drive end and split casing behind the asymmetric scroll.
        drum = shell(
            p,
            "Turbine bearing case",
            [
                (-0.158, 0.071),
                (-0.155, 0.107),
                (-0.134, 0.111),
                (-0.130, 0.095),
                (-0.086, 0.100),
                (-0.079, 0.126),
                (-0.043, 0.132),
                (-0.038, 0.145),
                (-0.015, 0.145),
                (-0.011, 0.128),
                (0.063, 0.130),
                (0.086, 0.111),
                (0.086, 0.067),
            ],
            "ShuttleCastAlloy",
            sides,
        )
        drum.rotation_euler.y = -math.pi / 2
        drum.location = (cx, cy, 0)
        p.cylinder("Turbine end cap", (cx, cy, -0.170), (cx, cy, -0.150), 0.086, STEEL, sides)
        if level < 2:
            for dx, dy in circle(0, 0, 0.118, 8):
                p.cylinder(
                    "Turbine tie rod", (cx + dx, cy + dy, -0.059), (cx + dx, cy + dy, 0.081), 0.012, STEEL, 10
                )
    for j in range(0, 8, 2 if level == 2 else 1):
        t = j * math.tau / 8
        rr = 0.154 * (1 + 0.14 * math.cos(t + 0.49))
        x, y = cx + rr * math.cos(t), cy + rr * math.sin(t)
        p.cylinder("Cover washer", (x, y, 0.265), (x, y, 0.276), 0.017, DARK, 16)
        p.cylinder("Cover bolt", (x, y, 0.275), (x, y, 0.287), 0.012, STEEL, 6)
    # Raised curved webs follow the domed cover and taper into both bosses.
    for j in range(0 if level == 2 else 4):
        a = math.tau * j / 4 + 0.32
        verts = []
        for rr, angle, base, top, half in (
            (0.058, a, 0.311, 0.325, 0.012),
            (0.082, a + 0.10, 0.310, 0.330, 0.014),
            (0.112, a + 0.21, 0.296, 0.318, 0.013),
            (0.140, a + 0.29, 0.270, 0.297, 0.010),
            (0.154, a + 0.32, 0.264, 0.275, 0.008),
        ):
            for side, h in ((-half, base), (half, base), (half * 0.6, top), (-half * 0.6, top)):
                verts.append(
                    (
                        cx + rr * math.cos(angle) - side * math.sin(angle),
                        cy + rr * math.sin(angle) + side * math.cos(angle),
                        h,
                    )
                )
        faces = [(0, 1, 2, 3), (16, 17, 18, 19)] + [
            (4 * i + k, 4 * i + (k + 1) % 4, 4 * i + 4 + (k + 1) % 4, 4 * i + 4 + k)
            for i in range(4)
            for k in range(4)
        ]
        p.mesh("Cast cover web", verts, faces, "ShuttleCastAlloy")
    p.cylinder("Pump inspection boss", (cx, cy, 0.313), (cx, cy, 0.327), 0.062, STEEL, 32)
    p.cylinder("Inspection plug", (cx, cy, 0.325), (cx, cy, 0.348), 0.047, DARK, 6)
    outlet = p.cylinder("Pump outlet", (-0.495, -0.395, 0.198), (-0.322, -0.395, 0.198), 0.095, CAST)
    outlet["lod_keep"] = True
    for x in (-0.421, -0.39):
        p.cylinder("Union shoulder", (x - 0.009, -0.395, 0.198), (x + 0.009, -0.395, 0.198), 0.105, STEEL, 32)
    p.cylinder("Outlet union", (-0.386, -0.395, 0.198), (-0.349, -0.395, 0.198), 0.1, DARK, 12)


def injector(p):
    wells = [(0, 0, 0.054)] + [(y, z, 0.042) for y, z in circle(0, 0, 0.142, 6)]
    pierced_plate(
        p,
        "Recessed injector plate",
        # The retaining ring overlaps the face, with a proud outer shoulder.
        circle(0, 0, 0.225, 48),
        [circle(y, z, r, 16) for y, z, r in wells],
        (0.07, 0, 0),
        (0, 1, 0),
        (0, 0, 1),
        0.045,
        STEEL,
    )
    p.cylinder("Injector cavity backing", (0.036, 0, 0), (0.044, 0, 0), 0.231, DARK, 48)
    # A raised rolled rim around the wells leaves their dark sidewalls exposed.
    for y, z, r in wells:
        rim = shell(
            p,
            "Injector well rim",
            [(0.113, r + 0.008), (0.121, r + 0.008), (0.125, r + 0.004), (0.122, r), (0.113, r)],
            CAST,
            24,
        )
        rim.location = (0, y, z)
    shell(
        p,
        "Injector retaining ring",
        [(0.108, 0.21), (0.108, 0.234), (0.13, 0.234), (0.135, 0.224), (0.13, 0.21)],
        DARK,
        48,
    )


def control_manifold(p):
    # A stepped valve casting on the side opposite the main scroll. The machined
    # pad spans two flats, with a keyed plug at one end and an elbow at the other.
    outline = [
        (-0.78, 0.10),
        (-0.77, 0.19),
        (-0.72, 0.245),
        (-0.53, 0.245),
        (-0.485, 0.203),
        (-0.485, 0.126),
        (-0.54, 0.09),
        (-0.72, 0.09),
    ]
    n = len(outline)
    verts = [(x, y, z) for z in (0.135, 0.295) for x, y in outline]
    faces = [tuple(range(n)), tuple(range(n, 2 * n))] + [
        (j, (j + 1) % n, (j + 1) % n + n, j + n) for j in range(n)
    ]
    p.mesh("Control manifold casting", verts, faces, "ShuttleCastAlloy")
    for x in (-0.694, -0.561):
        p.cylinder("Valve boss", (x, 0.176, 0.287), (x, 0.176, 0.324), 0.066, CAST, 32)
        p.cylinder("Valve cover lip", (x, 0.176, 0.32), (x, 0.176, 0.339), 0.069, STEEL, 32)
    p.cylinder("Keyed plug", (-0.694, 0.176, 0.335), (-0.694, 0.176, 0.37), 0.045, DARK, 6)
    p.box("Plug key", (-0.694, 0.176, 0.368), (0.051, 0.013, 0.014), STEEL, 0.003)
    p.cylinder("Elbow adaptor", (-0.561, 0.176, 0.335), (-0.561, 0.176, 0.376), 0.044, STEEL, 6)
    pipe(
        p,
        "Valve crossover",
        [
            (-0.561, 0.176, 0.358),
            (-0.561, 0.176, 0.432),
            (-0.512, 0.166, 0.458),
            (-0.41, 0.110, 0.455),
            (-0.345, 0.071, 0.422),
            (-0.307, 0.035, 0.335),
            (-0.307, 0.035, 0.276),
        ],
        0.023,
        STEEL,
        16,
    )
    p.cylinder("Crossover gland", (-0.307, 0.035, 0.286), (-0.307, 0.035, 0.321), 0.041, CAST, 6)
    for x in (-0.73, -0.526):
        p.cylinder("Valve flange screw", (x, 0.22, 0.289), (x, 0.22, 0.308), 0.012, DARK, 6)


def clamp_latch(p):
    # Split lugs and a transverse draw pin are readable from the main service view.
    for y in (-0.062, 0.062):
        p.box("Clamp latch ear", (-0.343, y, 0.320), (0.079, 0.047, 0.076), CAST, 0.012)
        p.cylinder("Latch barrel", (-0.343, y - 0.024, 0.356), (-0.343, y + 0.024, 0.356), 0.028, STEEL, 20)
    p.cylinder("Clamp draw pin", (-0.343, -0.108, 0.356), (-0.343, 0.095, 0.356), 0.014, STEEL, 16)
    p.cylinder("Latch nut", (-0.343, -0.107, 0.356), (-0.343, -0.09, 0.356), 0.025, DARK, 6)


def machinery(p):
    # Raised square conveyor on a four-foot spider. The open bays show the inlet casting.
    p.box("Inlet mounting boss", (-1.132, 0, 0), (0.104, 0.43, 0.43), CAST)
    for y, z in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        mount_pad(p, y * 0.342, z * 0.342)
        suspension_link(p, y, z)
    p.cylinder("Inlet casting", (-1.13, 0, 0), (-0.84, 0, 0), 0.187, STEEL)
    p.cylinder("Inlet collar", (-0.97, 0, 0), (-0.90, 0, 0), 0.225, DARK)
    shell(
        p,
        "Head casting",
        [
            (-0.87, 0.168),
            (-0.866, 0.237),
            (-0.822, 0.269),
            (-0.791, 0.268),
            (-0.765, 0.245),
            (-0.621, 0.236),
            (-0.571, 0.276),
            (-0.53, 0.276),
            (-0.53, 0.168),
        ],
        "ShuttleCastAlloy",
    )
    for j in range(6):
        a = j * math.tau / 6
        # Tapered longitudinal webs seated between the two flange shoulders.
        y, z = math.cos(a), math.sin(a)
        pts = [
            (-0.803, 0.245),
            (-0.792, 0.271),
            (-0.748, 0.29),
            (-0.626, 0.273),
            (-0.577, 0.269),
            (-0.589, 0.236),
        ]
        verts = [(x, y * r - z * d, z * r + y * d) for d in (-0.016, 0.016) for x, r in pts]
        n = len(pts)
        p.mesh(
            "Head casting rib",
            verts,
            [tuple(range(n)), tuple(range(n, 2 * n))]
            + [(i, (i + 1) % n, (i + 1) % n + n, i + n) for i in range(n)],
            CAST,
        )
    for x in (-0.834, -0.535):
        p.cylinder("Head flange", (x - 0.023, 0, 0), (x + 0.023, 0, 0), 0.311, STEEL, 48)
        for j in range(10):
            y, z = 0.287 * math.cos(j * math.tau / 10), 0.287 * math.sin(j * math.tau / 10)
            p.cylinder("Flange fastener", (x + 0.017, y, z), (x + 0.035, y, z), 0.018, DARK, 6)
    shell(
        p,
        "Chamber jacket",
        [
            (-0.534, 0.23),
            (-0.526, 0.277),
            (-0.467, 0.298),
            (-0.396, 0.301),
            (-0.328, 0.293),
            (-0.232, 0.275),
            (-0.109, 0.265),
            (-0.069, 0.278),
            (-0.024, 0.284),
            (-0.014, 0.252),
            (-0.014, 0.23),
        ],
        CAST,
    )
    control_manifold(p)
    clamp_latch(p)
    for x in (-0.405, -0.34):
        p.cylinder("Chamber band", (x - 0.02, 0, 0), (x + 0.02, 0, 0), 0.321, STEEL, 48)
    # Different housings and routes give the engine a distinct service face.
    p.cylinder("Pump carrier", (-0.55, 0.04, 0.03), (-0.55, -0.402, 0.22), 0.116, CAST)
    pump(p)
    pipe(
        p,
        "Main transfer duct",
        [
            (-0.35, -0.395, 0.198),
            (-0.24, -0.416, 0.213),
            (-0.15, -0.478, 0.172),
            (0.05, -0.420, -0.11),
            (0.12, -0.332, -0.177),
            (0.12, -0.207, -0.148),
        ],
        0.080,
        DARK,
        28,
    )
    p.cylinder("Duct seat", (0.12, -0.297, -0.154), (0.12, -0.208, -0.154), 0.101, STEEL)
    # Polished line bridges the service side and terminates in the small instrument block.
    p.box("Instrument block", (-0.60, -0.204, 0.246), (0.10, 0.075, 0.085), PAINT, 0.009)
    pipe(
        p,
        "Instrument return",
        [
            (-0.60, -0.20, 0.266),
            (-0.60, -0.20, 0.326),
            (-0.54, -0.22, 0.353),
            (-0.38, -0.22, 0.353),
            (-0.302, -0.275, 0.296),
            (-0.302, -0.363, 0.246),
            (-0.34, -0.39, 0.224),
        ],
        0.022,
        STEEL,
        14,
    )
    p.cylinder("Return housing", (-0.61, 0.23, -0.105), (-0.35, 0.23, -0.105), 0.127, STEEL)
    pipe(
        p,
        "Return duct",
        [
            (-0.38, 0.23, -0.105),
            (-0.25, 0.305, -0.138),
            (-0.075, 0.334, -0.134),
            (0.07, 0.285, -0.061),
            (0.085, 0.198, -0.04),
        ],
        0.062,
        CAST,
    )
    p.box("Controller housing", (-0.646, -0.14, -0.241), (0.209, 0.174, 0.136), PAINT, 0.02)
    p.box("Controller cover", (-0.645, -0.217, -0.249), (0.173, 0.044, 0.115), CAST, 0.009)
    for i in range(2):
        y = -0.14 - 0.032 * i
        pipe(
            p,
            "Harness conduit",
            [
                (-0.97, y, 0.04),
                (-0.91, y - 0.10, 0.057),
                (-0.785, y - 0.148, 0.056),
                (-0.72, y - 0.146, -0.16),
                (-0.65, y - 0.055, -0.23),
            ],
            0.014,
            STEEL,
            12,
        )
    for s in (-1, 1):
        p.cylinder("Actuator body", (-1.175, s * 0.34, -0.34), (-0.83, s * 0.309, -0.26), 0.047, CAST, 24)
        p.cylinder("Actuator rod", (-0.846, s * 0.309, -0.26), (-0.43, s * 0.183, -0.225), 0.023, STEEL, 16)
    shell(
        p,
        "Throat casting",
        [
            (-0.052, 0.242),
            (-0.048, 0.305),
            (0.019, 0.318),
            (0.094, 0.25),
            (0.158, 0.239),
            (0.235, 0.279),
            (0.241, 0.253),
            (0.15, 0.215),
        ],
        CAST,
    )
    injector(p)


def nozzle(p, sides=80):
    outside = [
        (0.177, 0.242),
        (0.23, 0.268),
        (0.325, 0.312),
        (0.46, 0.379),
        (0.62, 0.449),
        (0.80, 0.512),
        (0.98, 0.563),
        (1.12, 0.595),
        (1.218, 0.612),
    ]
    inside = [(x, r - 0.026) for x, r in outside]
    bell = shell(p, "Bell", outside + list(reversed(inside)), "ShuttleBellAlloy", sides)
    # Unwrap around the engine axis. Each cap has a narrow strip outside the skin UVs.
    uv = bell.data.uv_layers.active
    for face in bell.data.polygons:
        rings = {v // sides for v in face.vertices}
        angles = [(-(v % sides) / sides) % 1 for v in face.vertices]
        wrap = max(angles) - min(angles) > 0.5
        for li, u in zip(face.loop_indices, angles):
            v = bell.data.loops[li].vertex_index
            ring = v // sides
            x = bell.data.vertices[v].co.x
            t = (x - outside[0][0]) / (outside[-1][0] - outside[0][0])
            if rings == {8, 9}:
                row = 598 if ring == 8 else 604
            elif rings == {0, 17}:
                row = 8 if ring == 0 else 2
            else:
                row = 8 + 590 * t if ring < 9 else 617 + 398 * t
            uv.data[li].uv = (u + 1 if wrap and u < 0.5 else u, 1 - row / 1024)
    # Keep the seam and thin mouth intact through the generic distance pass.
    bell["lod_keep"] = True
    # Smooth adjacent stations on the uninterrupted skins, keeping the ends sharp.
    for edge in bell.data.edges:
        a, b = edge.vertices
        if a // sides == b // sides and a // sides not in (0, 8, 9, 17):
            edge.use_edge_sharp = False
    shell(
        p,
        "Bell attachment flange",
        [(0.27, 0.275), (0.27, 0.315), (0.284, 0.33), (0.309, 0.33), (0.323, 0.313), (0.323, 0.297)],
        STEEL,
        sides,
    )
    shell(
        p,
        "Rolled mouth",
        [(1.198, 0.58), (1.201, 0.615), (1.217, 0.621), (1.231, 0.615), (1.231, 0.581), (1.216, 0.577)],
        STEEL,
        sides,
    )
    # Visible down the bore. One independently named emitter for the two future modes.
    shell(
        p,
        "Plasma field ring",
        [(0.829, 0.503), (0.833, 0.475), (0.852, 0.469), (0.861, 0.476), (0.864, 0.511)],
        "ArcanePlasmaBell",
        sides,
    )
    for x, r in ((0.816, 0.474), (0.868, 0.493)):
        shell(
            p,
            "Emitter retainer",
            [(x, r + 0.025), (x, r), (x + 0.011, r), (x + 0.011, r + 0.025)],
            STEEL,
            sides,
        )


def build():
    if bpy.data.filepath or list(bpy.data.scenes.keys()) != ["Scene"]:
        raise RuntimeError("Start the nozzle builder in a fresh Blender file")
    stock = bpy.context.scene
    scene = bpy.data.scenes.new(NAME)
    bpy.context.window.scene = scene
    scene.unit_settings.system = "METRIC"
    scene.seut.sceneType = "mainScene"
    scene.seut.subtypeId = NAME
    scene.seut.mod_path = str(ASSETS.parent / "src")
    scene.seut.export_sbc_type = "none"
    scene.seut.export_exportPath = str(ASSETS.parent / "src/Models/Cubes/small")
    scene.seut.bBox_X, scene.seut.bBox_Y, scene.seut.bBox_Z = 3, 5, 3
    bpy.ops.scene.recreate_collections()
    scene.seut.gridScale = "small"
    p = Parts()
    p.name = "Shuttle engine"
    p.col = importlib.import_module("space-engineers-utilities.seut_collections").get_collections(scene)[
        "main"
    ][0]
    names = [PAINT, DARK, CAST, STEEL, "RubberDry"]
    with bpy.data.libraries.load(str(SEUT / "Materials/Materials.blend"), link=True) as (_, lib):
        lib.materials = names.copy()
    p.native = dict(zip(names, lib.materials))
    with bpy.data.libraries.load(str(POWER / "arcane-energy-core.blend")) as (_, lib):
        lib.materials = ["EnergyStatus"]
    field = lib.materials[0]
    field.name = "ArcanePlasmaBell"
    p.native[field.name] = field
    for name in ("CM", "NG", "ADD"):
        node = field.node_tree.nodes[name]
        img = bpy.data.images.load(
            str(
                ASSETS.parent
                / "src/Textures/Models/ArcaneThrusters"
                / ("EnergyField_" + name.lower() + ".dds")
            ),
            check_existing=True,
        )
        img.colorspace_settings.name = node.image.colorspace_settings.name
        node.image = img
    for name, filename in (
        ("ShuttleBellAlloy", "ShuttleBell"),
        ("ShuttleCastAlloy", "ShuttleCasting"),
    ):
        alloy = p.native[STEEL].copy()
        alloy.name = name
        p.native[name] = alloy
        for channel in ("CM", "NG"):
            node = alloy.node_tree.nodes[channel]
            path = ASSETS / "Textures/Models/ArcaneThrusters" / (filename + "_" + channel.lower() + ".dds")
            image = bpy.data.images.load(str(path))
            image.alpha_mode = "CHANNEL_PACKED"
            image.colorspace_settings.name = node.image.colorspace_settings.name
            node.image = image
    machinery(p)
    service_hardware(p)
    body = set(p.col.objects)
    nozzle(p)
    bell_objects = set(p.col.objects) - body
    with bpy.data.libraries.load(str(SEUT / "Models/Common.blend")) as (_, lib):
        lib.objects = ["Conveyor SG"]
    socket = lib.objects[0]
    p.col.objects.link(socket)
    socket.name = "Shuttle engine / Small conveyor face"
    socket["lod_keep"] = True
    pose = Matrix.Rotation(-math.pi / 2, 4, "Y")
    pose.translation = (-1, 0, 0)
    socket.matrix_world = pose
    dummy = bpy.data.objects.new("detector_conveyor_small_inlet", None)
    p.col.objects.link(dummy)
    dummy.matrix_world = pose @ Matrix.Rotation(math.pi / 2, 4, "Z")
    dummy.location.x = -1.25
    dummy.empty_display_size = 0.085
    bpy.context.view_layer.update()
    for obj in list(p.col.objects):
        obj.matrix_world = TO_BLOCK @ obj.matrix_world
    flame = bpy.data.objects.new("thruster_flame_01", None)
    p.col.objects.link(flame)
    # SEUT's identity empty points aft after MWM conversion. Flip it to SE forward.
    flame.rotation_euler.z = math.pi
    flame.location = (0, -1.231, 0)
    flame.scale = (1.14,) * 3
    flame.empty_display_size = 0.12
    bpy.context.view_layer.update()
    for obj in p.col.objects:
        if obj.type == "MESH":
            assert obj.data.uv_layers, obj.name
            for v in obj.data.vertices:
                assert all(
                    abs(a) <= b + 0.0001 for a, b in zip(obj.matrix_world @ v.co, (0.75, 1.25, 0.75))
                ), obj.name
    lods = runpy.run_path(str(POWER / "build_energy_lods.py"))
    report = lods["build_lods"](scene, p.col)
    # Rebuild the circular sections with uniform sectors so a decimator cannot
    # deform the lip, cut through the bore, or smear the stencil across the UV seam.
    main = p.col
    cols = importlib.import_module("space-engineers-utilities.seut_collections").get_collections(scene)
    for level, sectors in ((1, 40), (2, 24)):
        col = next(c for c in cols["lod"] if c.seut.type_index == level and c.seut.ref_col == main)
        for obj in list(col.objects):
            source = main.objects.get(obj.get("lod_source", ""))
            if source is None:
                continue
            if source == socket:
                # The native conveyor has a live bevel. Triangulating its control cage
                # before evaluating that bevel creates slivers on the copied LOD port.
                obj.data = socket.data
                continue
            omit = ["Controller lead", "Harness conduit"]
            if level == 2:
                omit += ["Instrument return", "Cable gland", "Bracket pin"]
            if source in bell_objects or any(label in source.name for label in omit):
                bpy.data.objects.remove(obj, do_unlink=True)
        p.col = col
        p.name = f"LOD{level} / Shuttle engine"
        existing = set(col.objects)
        nozzle(p, sectors)
        if level == 2:
            for y, z in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
                p.box("Mount lug", (-1.207, y * 0.342, z * 0.342), (0.086, 0.168, 0.168), PAINT, 0.015)
        for obj in set(col.objects) - existing:
            obj.matrix_world = TO_BLOCK @ obj.matrix_basis
        report["lods"][level - 1]["triangles"] = sum(lods["triangles"](o.data) for o in col.objects)
    assert report["main_triangles"] > report["lods"][0]["triangles"] > report["lods"][1]["triangles"]
    print("Shuttle drive detail levels", report)
    bpy.data.scenes.remove(stock)
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            view = area.spaces.active
            view.overlay.show_overlays = False
            view.shading.type = "MATERIAL"
            view.shading.studio_light = "studio.exr"
            view.shading.studiolight_intensity = 1.1
            view.shading.studiolight_rotate_z = 0.5
            # Frame the engine mount-up as in the reference. The block axis stays SE forward.
            direction = Vector((-0.5, -0.23, 0.90)).normalized()
            right = Vector((0, 1, 0)).cross(direction).normalized()
            view.region_3d.view_rotation = (
                Matrix((right, direction.cross(right), direction)).transposed().to_quaternion()
            )
            view.region_3d.view_location = (0, 0, 0)
            view.region_3d.view_perspective = "PERSP"
            view.region_3d.view_distance = 4.8
            view.lens = 42
            view.clip_start = 0.012
    bpy.ops.wm.save_as_mainfile(filepath=str(ASSETS / "arcane-shuttle-nozzle.blend"), compress=True)


if __name__ == "__main__":
    build()
