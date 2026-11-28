"""Build the two tank mains from a fresh Blender session with Arcane Power's SEUT setup."""
import importlib
import math
import runpy
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

MOD = Path(__file__).resolve().parents[1]
POWER = MOD.parent / "ArcanePower" / "assets"
SEUT = Path.home() / ".local/share/blender-se1-setup/assets"
Parts = runpy.run_path(str(POWER / "thermal_parts.py"))["Parts"]
collections = importlib.import_module("space-engineers-utilities.seut_collections")
PAINT = "PaintedMetal_Colorable"
DARK = "PaintedMetal_VeryDark"
STEEL = "Metal_Dull"


def jacket(p, label, left, right, radius, angle, span, mat):
    """A solid curved shield with clipped corners over the cylindrical vessel."""
    verts = []
    segments = 14
    for i in range(segments + 1):
        t = i / segments
        theta = math.radians(angle + span * (t - .5))
        clip = radius * .10 * max(0, 1 - min(t, 1 - t) * segments / 2)
        for x, r in ((left + clip, radius), (right - clip, radius),
                     (right - clip, radius * .94), (left + clip, radius * .94)):
            verts.append((x, r * math.cos(theta), r * math.sin(theta)))
    faces = [(3, 2, 1, 0), tuple(range(4 * segments, 4 * segments + 4))]
    for i in range(segments):
        for j in range(4):
            a = 4 * i + j
            b = 4 * i + (j + 1) % 4
            faces.append((a, b, b + 4, a + 4))
    shell = p.mesh(label, verts, faces, mat)
    for face in shell.data.polygons:
        # Smooth only the curved skins. Keep their cut ends and lips crisp.
        indices = {v % 4 for v in face.vertices}
        face.use_smooth = indices in ({0, 1}, {2, 3})
    return shell


def end_plate(p, sign, half, width, socket, depth):
    """Chamfered end bulkhead with a square pocket sized to the native conveyor mesh."""
    radius = width * .48
    corner = radius * .25
    outline = [(radius, radius-corner), (radius-corner, radius), (-radius+corner, radius),
               (-radius, radius-corner), (-radius, -radius+corner), (-radius+corner, -radius),
               (radius-corner, -radius), (radius, -radius+corner)]
    verts = []
    for x, scale, opening in ((half-.012, 1, False), (half-depth, .94, False),
                               (half-depth, 1, True), (half-.012, 1, True)):
        for y, z in outline:
            if opening:
                # Two points per corner leave four straight jambs and a tiny corner bevel.
                y = math.copysign(socket if abs(y) == radius else socket-.003, y)
                z = math.copysign(socket if abs(z) == radius else socket-.003, z)
            verts.append((sign*x, y*scale, z*scale))
    faces = [(i*8+j, i*8+(j+1)%8, ((i+1)%4)*8+(j+1)%8, ((i+1)%4)*8+j)
             for i in range(4) for j in range(8)]
    p.mesh("Conveyor bulkhead", verts, faces, PAINT)


def tank(grid, cells, native, port, charger=False):
    small = grid == "small"
    tag = "SG" if small else "LG"
    cell = .5 if small else 2.5
    length, width, height = (n*cell for n in cells)
    half = length/2
    radius = width*.39
    name = "ArcaneThrusters_RecoveryChargerLG" if charger else "ArcaneThrusters_PlasmaTank" + tag
    scene = bpy.data.scenes.new(name)
    bpy.context.window.scene = scene
    scene.unit_settings.system = 'METRIC'
    scene.seut.sceneType = 'mainScene'
    scene.seut.subtypeId = name
    scene.seut.mod_path = str(MOD / "src")
    scene.seut.export_sbc_type = 'none'
    scene.seut.export_exportPath = str(MOD / "src/Models/Cubes" / grid)
    scene.seut.bBox_X, scene.seut.bBox_Y, scene.seut.bBox_Z = cells
    bpy.ops.scene.recreate_collections()
    scene.seut.gridScale = grid
    p = Parts()
    p.name, p.col, p.native = tag, collections.get_collections(scene)['main'][0], native
    p.support, p.ports = [], []

    # Leave room at each end for the original SE conveyor, including its recessed back.
    depth = .16 if small else .34
    socket = .17 if small else .68
    end = half - depth
    p.cylinder("Pressure vessel", (-end,0,0), (end,0,0), radius, DARK, 64)
    for sign in (-1, 1):
        if charger and sign < 0:
            p.port("Recovery duplex", (-half, 0, 0), (-1, 0, 0), "H / C")
            p.box("Exchanger bulkhead", (-half+.23,0,0), (.18,2.12,2.12), DARK)
            continue
        end_plate(p, sign, half, width, socket-.002, depth)
        pose = Matrix.Rotation(sign*math.pi/2, 4, 'Y')
        pose.translation = (sign*(half-cell/2), 0, 0)
        face = port.copy()
        face.name = tag + " / Conveyor face " + str(sign)
        p.col.objects.link(face)
        face.matrix_world = pose
        # Cap the native open-backed part below its deepest surface.
        p.box("Receiver back", (sign*(half-(.086 if small else .30)),0,0),
              (.026, socket*2.05, socket*2.05), DARK)
        prefix = "detector_conveyor_small_" if small else "detector_conveyor_"
        dummy = bpy.data.objects.new(prefix + ("right" if sign > 0 else "left"), None)
        p.col.objects.link(dummy)
        # Quarter-turn in the port plane. Local +Z still points out of the tank.
        dummy.matrix_world = pose @ Matrix.Rotation(math.pi/2, 4, 'Z')
        dummy.location.x = sign*half
        dummy.empty_display_size = socket*.44
        for y in (-1, 1):
            for z in (-1, 1):
                p.cylinder("End plate stud", (sign*(half-.021), y*width*.35, z*width*.35),
                           (sign*(half-.003), y*width*.35, z*width*.35), width*.018, STEEL, 6)

    bays = 2 if small else 3
    extent = end - width*.06
    stops = [-extent + 2*extent*i/bays for i in range(bays+1)]
    for i, x in enumerate(stops):
        band = width*.095
        p.cylinder("Field winding", (x-band/2,0,0), (x+band/2,0,0), radius*1.115,
                   "PaintedMetal_Darker", 48)
        for sign in (-1, 1):
            c = x + sign*band*.39
            p.cylinder("Retaining hoop", (c-.015*width,0,0),(c+.015*width,0,0),
                       radius*1.14, STEEL, 48)
        p.cylinder("Field monitor band", (x-.009*width,0,0),(x+.009*width,0,0),
                   radius*1.118, "EnergyStatus", 48)
        # The cast yoke follows the lower half of this collar down to the skid.
        points = [(-radius*1.16,-height*.46),(radius*1.16,-height*.46),
                  (radius*1.16,-radius*.25)]
        for j in range(25):
            a = math.pi*j/24
            points.append((radius*1.10*math.cos(a), -radius*1.10*math.sin(a)))
        points.append((-radius*1.16,-radius*.25))
        n = len(points)
        verts = [(x+dx,y,z) for dx in (-band*.46,band*.46) for y,z in points]
        p.mesh("Cast saddle", verts, [tuple(range(n)),tuple(range(n,2*n))]+
               [(j,(j+1)%n,(j+1)%n+n,j+n) for j in range(n)], PAINT)
        if i == bays:
            break
        margin = band*.52
        if charger and i < 2:
            for j in range(9):
                fin_x = x + margin + (stops[i+1]-x-2*margin) * j / 8
                p.cylinder("Exchanger lamination", (fin_x-.035,0,0), (fin_x+.035,0,0),
                           radius*1.09, STEEL if j % 3 == 0 else PAINT, 32)
            continue
        for angle in (0,90,180,270):
            jacket(p, "Segmented armor", x+margin, stops[i+1]-margin,
                   radius*1.054, angle, 77, PAINT)
    for sign in (-1,1):
        p.box("Mounting skid", (0,sign*width*.37,-height*.465),
              (length*.985,width*.22,height*.07), "PaintedMetal_Darker", width*.025)
        # The field supply line runs in the gap between the top and side jackets.
        y = sign*radius*.764
        z = radius*.764
        p.cylinder("Field supply bus", (-extent,y,z),(extent,y,z),radius*.045,STEEL,16)
    # A plated field-service enclosure fitted across one bay on the service side.
    center = (stops[0]+stops[1])/2
    panel_width = min(width*.67,(stops[1]-stops[0])*.76)
    p.box("Service box", (center,-radius*.99,0), (panel_width,width*.17,width*.31), DARK)
    front = -radius*.99-width*.085
    panel = p.box("Service cover", (center,front,0),(panel_width*.98,width*.022,width*.30), PAINT)
    face = front-width*.011
    p.label(panel, "RECOVERY" if charger else "PLASMA", (center,face-.001,width*.051),size=width*.071)
    for i in range(4):
        p.box("Status lens", (center+(i-1.5)*panel_width*.135,face-.003,-width*.042),
              (panel_width*.105,.007,width*.019),"EnergyStatus",.002)
    bpy.context.view_layer.update()
    for obj in p.col.objects:
        if obj.type != 'MESH':
            continue
        assert obj.data.uv_layers, obj.name
        for vertex in obj.data.vertices:
            pt = obj.matrix_world @ vertex.co
            assert all(abs(v) <= limit/2+.0001 for v,limit in zip(pt,(length,width,height))), obj.name
    return scene


def build(charger=False):
    if bpy.data.filepath or list(bpy.data.scenes.keys()) != ["Scene"]:
        raise RuntimeError("Start the tank builder in a fresh Blender file")
    stock = bpy.context.scene
    names = [PAINT,DARK,STEEL,"PaintedMetal_Darker"]
    if charger: names.append("Metal_Shiny")
    with bpy.data.libraries.load(str(SEUT / "Materials/Materials.blend"),link=True) as (_, dst):
        dst.materials = names.copy()
    native = dict(zip(names, dst.materials))
    with bpy.data.libraries.load(str(POWER / "arcane-energy-core.blend")) as (_, dst):
        dst.materials = ["EnergyStatus"]
    native["EnergyStatus"] = dst.materials[0]
    with bpy.data.libraries.load(str(SEUT / "Models/Common.blend")) as (_, dst):
        dst.objects = ["Conveyor LG","Conveyor SG"]
    large, small = dst.objects
    carrier = tank("large", (3,1,1), native, large, charger)
    if not charger:
        tank("small", (5,3,3), native, small)
    bpy.context.window.scene = carrier
    bpy.data.scenes.remove(stock)
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            view = area.spaces.active
            view.region_3d.view_perspective = 'PERSP'
            view.region_3d.view_rotation = Vector((.67,-1,.46)).to_track_quat('Z','Y')
            view.region_3d.view_distance = 10.5
            view.region_3d.view_location = (0,0,0)
            view.lens = 48
            view.clip_start = .015
            view.overlay.show_overlays = False
            view.shading.type = 'MATERIAL'
            view.shading.studio_light = 'studio.exr'
            view.shading.studiolight_rotate_z = .5
            view.shading.studiolight_intensity = .8
    file = "arcane-recovery-charger.blend" if charger else "arcane-plasma-tanks.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(MOD / "assets" / file),compress=True)


if __name__ == "__main__":
    build("--charger" in sys.argv)
