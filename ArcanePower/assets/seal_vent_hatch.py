"""Close the ejection leaves and hull outlet without changing their travel.

Run apply() in the visible prototype. The shared hatch seal also applies to
the reactor's copied hatch source in arcane-thermal-models.blend.
"""
import ast
import importlib
import math
from pathlib import Path

import bpy
import bmesh
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
COLS = importlib.import_module('space-engineers-utilities.seut_collections')


def apply():
    leaf_scene = bpy.data.scenes['ArcanePower_VentHatch']
    bpy.context.window.scene = leaf_scene
    col = COLS.get_collections(leaf_scene)['main'][0]
    root = next(o for o in col.objects if o.parent is None)
    helpers = ast.parse((ROOT/'assets/build_deployable_chamber.py').read_text())
    scope = dict(globals(), col=col, root=root)
    exec(compile(ast.Module(body=[n for n in helpers.body if isinstance(n, ast.FunctionDef)
        and n.name in ('mesh_object', 'prism', 'annulus')], type_ignores=[]), 'hatch primitives', 'exec'), scope)
    prism = scope['prism']
    material = next(m for m in bpy.data.materials if m.name == 'PaintedMetal_VeryDark' and m.library)
    for obj in list(col.objects):
        if obj.get('hatch_pressure_seal'):
            bpy.data.objects.remove(obj, do_unlink=True)
    # A recessed, full quadrant backs both radial seams. Its outer arc meets
    # the 128-sided throat exactly, while the original armor and markings stay.
    # It travels with the leaf: drop first, then slide into the roof pocket.
    outline = [(0, 0)]+[(1.86*math.cos(i*math.pi/64), 1.86*math.sin(i*math.pi/64)) for i in range(33)]
    seal = prism('Vent hatch / pressure seal', outline, .025, .135, material, col, root)
    seal['hatch_pressure_seal'] = True
    seal['lod_keep'] = True
    leaf_scene['hatch_seal_revision'] = 1

    outlet = bpy.data.scenes.get('ArcanePower_VentOutlet')
    if outlet:
        bpy.context.window.scene = outlet
        main = COLS.get_collections(outlet)['main'][0]
        parent = next(o for o in main.objects if o.parent is None)
        for obj in list(main.objects):
            if obj.get('vent_seat_collar'):
                bpy.data.objects.remove(obj, do_unlink=True)
        metal = next(m for m in bpy.data.materials if m.name == 'Metal_Dull' and m.library)
        collar = scope['annulus']('Vent / seat collar', 1.86, 2.09, 1.08, 1.24, metal, main, parent)
        collar['vent_seat_collar'] = True
        collar['lod_keep'] = True
        # Close the old 450 mm clipped corners so the outlet meets hull armor
        # along the whole cell boundary. Existing physics already spans them.
        for obj in list(main.objects):
            if obj.get('vent_hull_corner'):
                bpy.data.objects.remove(obj, do_unlink=True)
        armor = next(m for m in bpy.data.materials if m.name == 'PaintedMetal_Darker' and m.library)
        for i in range(4):
            rot = Matrix.Rotation(i*math.pi/2, 3, 'Z')
            points = [tuple((rot@Vector((x,y,0)))[:2]) for x,y in ((3.30,3.75),(3.75,3.30),(3.75,3.75))]
            obj = prism('Vent / hull corner '+str(i), points, -1.25, 1.25, armor, main, parent)
            obj['vent_hull_corner'] = True
            obj['lod_keep'] = True
        outlet['hatch_seal_revision'] = 1
    bpy.context.view_layer.update()
    return {'shared_leaf': leaf_scene.name, 'outlet': outlet.name if outlet else None}


def review(opening=0, level=0):
    """Temporary linked preview; remove before saving the production source."""
    name = 'Review / sealed vent hatch'
    scene = bpy.data.scenes.get(name)
    if scene:
        for obj in list(scene.objects): bpy.data.objects.remove(obj, do_unlink=True)
    else: scene = bpy.data.scenes.new(name)
    source = bpy.data.scenes['ArcanePower_VentOutlet']
    main = COLS.get_collections(source)['main'][0]
    leaf_cols = COLS.get_collections(bpy.data.scenes['ArcanePower_VentHatch'])
    leaf = leaf_cols['main'][0] if level == 0 else next(c for c in leaf_cols['lod'] if c.seut.type_index == level)
    scene.world = source.world
    bpy.context.window.scene = source
    bpy.context.view_layer.update()
    for obj in main.objects:
        if obj.type != 'MESH': continue
        copy = obj.copy(); scene.collection.objects.link(copy)
        copy.parent = None; copy.matrix_world = obj.matrix_world.copy()
    for dummy in (o for o in main.objects if o.name.startswith('subpart_OutletHatch')):
        pose = dummy.matrix_world.copy()
        pose.translation += Vector((0,0,-.30*min(opening/.3,1)))
        pose.translation += pose.to_3x3()@Vector((1.4,1.4,0))*max((opening-.3)/.7,0)
        for obj in leaf.objects:
            if obj.type != 'MESH': continue
            copy = obj.copy(); scene.collection.objects.link(copy)
            copy.parent = None; copy.matrix_world = pose@obj.matrix_world
    bpy.context.window.scene = scene
    bpy.context.view_layer.update()
    return scene.name


def audit():
    leaf = COLS.get_collections(bpy.data.scenes['ArcanePower_VentHatch'])['main'][0]
    seal = next(o for o in leaf.objects if o.get('hatch_pressure_seal'))
    bm = bmesh.new(); bm.from_mesh(seal.data)
    assert all(e.is_manifold and e.is_contiguous for e in bm.edges)
    assert bm.calc_volume(signed=True) > 0
    bm.free()
    name = review()
    vertices, faces = [], []
    for obj in bpy.data.scenes[name].objects:
        offset = len(vertices)
        vertices.extend(obj.matrix_world@v.co for v in obj.data.vertices)
        faces.extend(tuple(offset+i for i in face.vertices) for face in obj.data.polygons)
    tree = BVHTree.FromPolygons(vertices, faces)
    checks = 0
    # Include all four exact seam axes, the centre and the former hull corners.
    for x in range(-74,75):
        for y in range(-74,75):
            # Quarter-turn float matrices can leave sub-micron edge cracks.
            assert any(tree.ray_cast(Vector((x*.05+dx,y*.05+dy,1.4)),Vector((0,0,-1)),2.8)[0] is not None
                       for dx,dy in ((0,0),(1e-5,0),(-1e-5,0),(0,1e-5),(0,-1e-5))), ('Open outlet',x,y)
            checks += 1
    # The new gasket fits the existing drop-then-slide pocket at every pose.
    for step in range(101):
        t=step/100
        drop=.30*min(t/.3,1); slide=1.4*max((t-.3)/.7,0)
        points=[v.co+Vector((slide,slide,1.08-drop)) for v in seal.data.vertices]
        assert all(max(abs(p.x),abs(p.y)) < 3.65 for p in points)
        if slide > 0: assert max(p.z for p in points) < 1.0 and min(p.z for p in points) > .70
        checks += 1
    return {'status':'passed','closed_surface_and_motion_checks':checks}


if __name__ == '__main__':
    print(apply())
