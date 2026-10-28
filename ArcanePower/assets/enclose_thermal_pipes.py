"""Close the manifold pipe skins without changing their duplex interfaces.

Run apply(name) in the production Blender file. Bare variants keep the same
plumbing and omit these skins when derived by build_thermal_models.
"""
import runpy
from pathlib import Path

import bpy
import bmesh
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(str(ROOT/'assets/build_thermal_models.py'))


def apply(name):
    assert ' / ' in name and name not in M['CONTRACT']['BARE_PIPES']
    p = M['Parts'](name, existing=True)
    for obj in list(p.col.objects):
        if obj.get('thermal_pipe_casing'):
            bpy.data.objects.remove(obj, do_unlink=True)
    # Six overlapping solid skins meet at the cell boundary. Socket apertures
    # overlap the existing flange by 30 mm, including the offset reactor inlet.
    for axis in range(3):
        for sign in (-1, 1):
            normal = Vector(tuple(sign if i == axis else 0 for i in range(3)))
            size = [2.5]*3
            size[axis] = .10
            skin = p.box('enclosed pipe casing '+str(axis)+' '+str(sign),
                         normal*1.20, size, 'PaintedMetal_Colorable', .002)
            skin['thermal_pipe_casing'] = True
            for port in p.ports:
                if Vector(port['normal']).dot(normal) < .99:
                    continue
                opening = [1.98]*3
                opening[axis] = .4
                cutter = p.box('temporary casing aperture',
                               Vector(port['position'])-normal*.05, opening, chamfer=0)
                bpy.context.view_layer.objects.active = skin
                modifier = skin.modifiers.new('Sealed flange aperture', 'BOOLEAN')
                modifier.operation, modifier.solver, modifier.object = 'DIFFERENCE', 'EXACT', cutter
                bpy.ops.object.modifier_apply(modifier=modifier.name)
                bpy.data.objects.remove(cutter, do_unlink=True)
            M['BUILD']['uv'](skin)
    # Side-mounted lamps would be hidden by the new skins. Seat the same lamps
    # on each existing flange, below the grid face, retaining native materials.
    for port in p.ports:
        c, n, up = (Vector(port[k]) for k in ('position', 'normal', 'hot_axis'))
        across = up.cross(n)
        for label, inset in (('status bezel', .0185), ('status lens', .007)):
            obj = next(o for o in p.col.objects if o.name == name+' / '+port['id']+' '+label)
            obj.matrix_world = Matrix((across, up, n)).transposed().to_4x4()
            obj.location = c+across*.78-n*inset
    p.scene['thermal_enclosed_revision'] = 1
    bpy.context.view_layer.update()
    audit(p)
    return M['record'](name)


def audit(p):
    """Check real solids and sample every casing face outside the fluid bores."""
    skins = [o for o in p.col.objects if o.get('thermal_pipe_casing')]
    assert len(skins) == 6, (p.name, 'Missing casing face')
    vertices, faces = [], []
    for obj in p.col.objects:
        if obj.type != 'MESH':
            continue
        if obj in skins:
            bm = bmesh.new(); bm.from_mesh(obj.data)
            assert all(e.is_manifold and e.is_contiguous for e in bm.edges), obj.name
            assert bm.calc_volume(signed=True) > 0, obj.name
            bm.free()
            assert obj.data.uv_layers.active, obj.name
        offset = len(vertices)
        vertices.extend(obj.matrix_world@v.co for v in obj.data.vertices)
        faces.extend(tuple(offset+i for i in face.vertices) for face in obj.data.polygons)
    tree = BVHTree.FromPolygons(vertices, faces)
    for axis in range(3):
        tangents = [i for i in range(3) if i != axis]
        for sign in (-1, 1):
            n = Vector(tuple(sign if i == axis else 0 for i in range(3)))
            for a in range(-12, 13):
                for b in range(-12, 13):
                    point = n*1.26
                    point[tangents[0]], point[tangents[1]] = a*.1, b*.1
                    if any(Vector(port['normal']).dot(n) > .99 and any(
                        (point-(Vector(port['position'])+Vector(port['hot_axis'])*hot*.46)).cross(n).length < .29
                        for hot in (-1, 1)) for port in p.ports):
                        continue
                    assert tree.ray_cast(point, -n, .16)[0] is not None, (p.name, 'Open casing', tuple(point))


if __name__ == '__main__':
    for name in M['CONTRACT']['PLAYABLE']:
        if ' / ' in name and name not in M['CONTRACT']['BARE_PIPES']:
            apply(name)
