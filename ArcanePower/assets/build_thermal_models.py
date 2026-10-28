"""Production thermal main models, built in bounded calls in live Blender.

Reuses the reviewed machine builders and native SEUT materials. The concept and
accepted reactor/battery files remain separate. Existing mains progress through
base, geometry and textures; bare pipe variants derive from the finished mains.
No LOD/build-stage work here.
"""
import hashlib
import importlib
import json
import math
from pathlib import Path
import runpy

import bpy
import bmesh
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'validation/thermal-models'
FILE = ROOT/'assets/arcane-thermal-models.blend'
BUILD = runpy.run_path(str(ROOT/'assets/thermal_parts.py'))
CONTRACT = runpy.run_path(str(ROOT/'assets/thermal_model_contract.py'))
SPECS = CONTRACT['SPECS']
COLS = importlib.import_module('space-engineers-utilities.seut_collections')


def prepare():
    assert Path(bpy.data.filepath).name == 'arcane-thermal-concepts.blend'
    assert not FILE.exists(), 'Production file exists; inspect it before rebuilding'
    OUT.mkdir(parents=True, exist_ok=True)
    protected = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (
        ROOT/'assets/arcane-thermal-concepts.blend',
        ROOT/'assets/arcane-power-prototype.blend', ROOT/'assets/arcane-energy-core.blend')}
    (OUT/'protected-sources.json').write_text(json.dumps(protected, indent=2)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(FILE))
    return {'file': str(FILE), 'models': len(SPECS), 'contract': CONTRACT['self_check']()}


def scene_for(name):
    return bpy.data.scenes[CONTRACT['subtype'](name)]


def main_for(name):
    return COLS.get_collections(scene_for(name))['main'][0]


class Parts(BUILD['Parts']):
    def __init__(self, name, existing=False):
        assert Path(bpy.data.filepath) == FILE, 'Use the separate production thermal source'
        self.name = name
        self.size = Vector(SPECS[name])*2.5
        self.native = {m.name: m for m in bpy.data.materials if m.library}
        self.support = []
        if existing:
            self.scene = scene_for(name)
            bpy.context.window.scene = self.scene
            self.col = main_for(name)
            self.ports = json.loads(self.col['ports'])
            return
        ident = CONTRACT['subtype'](name)
        assert ident not in bpy.data.scenes, 'Existing main model; refine it instead'
        self.scene = bpy.data.scenes.new(ident)
        bpy.context.window.scene = self.scene
        self.scene.unit_settings.system = 'METRIC'
        self.scene.unit_settings.scale_length = 1
        self.scene.view_layers[0].name = 'SEUT'
        self.scene.seut.sceneType = 'mainScene'
        self.scene.seut.gridScale = 'large'
        self.scene.seut.subtypeId = ident
        self.scene.seut.mod_path = str(ROOT/'src')
        self.scene.seut.export_sbc_type = 'none'
        self.scene.seut.export_exportPath = str(ROOT/'src/Models/Cubes/large/Thermal')
        self.scene.seut.bBox_X, self.scene.seut.bBox_Y, self.scene.seut.bBox_Z = SPECS[name]
        wrapper = bpy.data.collections.new('SEUT ('+ident+')')
        self.scene.collection.children.link(wrapper)
        wrapper.seut.scene = self.scene
        wrapper.seut.col_type = 'seut'
        wrapper.seut.version = 3
        self.col = bpy.data.collections.new('Main ('+ident+')')
        wrapper.children.link(self.col)
        self.col.seut.scene = self.scene
        self.col.seut.col_type = 'main'
        self.col.seut.version = 3
        self.col['thermal_model'] = name
        self.col['grid_cells'] = SPECS[name]
        collision = bpy.data.collections.new('Collision - Main ('+ident+')')
        wrapper.children.link(collision)
        collision.seut.scene = self.scene
        collision.seut.col_type = 'hkt'
        collision.seut.version = 3
        collision.seut.ref_col = self.col
        self.ports = []

    def box(self, label, p, size, mat='PaintedMetal_Darker', chamfer=.025):
        # The concept helper's broad edge breaks read as roundovers at game
        # scale. Production housings have a narrow, flat machining chamfer.
        width = chamfer if self.name == 'Reactor housing' else min(chamfer, .003, min(size)*.04)
        obj = super().box(label, p, size, mat, width)
        if self.name != 'Reactor housing':
            obj['thermal_chamfer_m'] = width
            obj['thermal_chamfer_segments'] = 1 if width else 0
            for face in obj.data.polygons:
                face.use_smooth = False
        return obj

    def cylinder(self, label, a, b, radius, mat='Metal_Dull', sides=32):
        obj = super().cylinder(label, a, b, radius, mat, sides)
        if self.name != 'Reactor housing' and sides <= 8:
            for face in obj.data.polygons:
                face.use_smooth = False
            obj['thermal_faceted_hardware'] = True
        return obj

    def tube(self, label, path, radius, mat='Metal_Dull', wall=.045, sides=24):
        """Parallel-transport rings avoid the old vertical-frame discontinuity."""
        path = [Vector(p) for p in path]
        assert len(path) >= 2 and 0 < wall < radius
        # Hold a straight collar at either end of routed machine stubs. A
        # bisected bend ring otherwise intrudes into the nominal socket neck.
        if len(path) > 2:
            if (path[1]-path[0]).length > .18:
                path.insert(1, path[0]+(path[1]-path[0]).normalized()*.10)
            if (path[-2]-path[-1]).length > .18:
                path.insert(-1, path[-1]+(path[-2]-path[-1]).normalized()*.10)
        tangents = [(path[min(i+1, len(path)-1)]-path[max(i-1, 0)]).normalized() for i in range(len(path))]
        u = Vector((0, 0, 1)) if abs(tangents[0].z) < .95 else Vector((0, 1, 0))
        u = (u-tangents[0]*u.dot(tangents[0])).normalized()
        verts, distances = [], [0.]
        for i, p in enumerate(path):
            if i:
                u = tangents[i-1].rotation_difference(tangents[i]) @ u
                distances.append(distances[-1]+(p-path[i-1]).length)
            v = tangents[i].cross(u)
            for r in (radius, radius-wall):
                verts.extend(p+r*(u*math.cos(j*math.tau/sides)+v*math.sin(j*math.tau/sides)) for j in range(sides))
        faces = []
        for k in range(len(path)-1):
            for ring in (0, 1):
                a, b = (k*2+ring)*sides, ((k+1)*2+ring)*sides
                faces.extend((a+j, a+(j+1)%sides, b+(j+1)%sides, b+j) for j in range(sides))
        for k in (0, len(path)-1):
            a = k*sides*2
            faces.extend((a+j, a+(j+1)%sides, a+sides+(j+1)%sides, a+sides+j) for j in range(sides))
        obj = self.mesh(label, verts, faces, mat)
        uv = obj.data.uv_layers.active
        for f in obj.data.polygons:
            indices = [obj.data.loops[i].vertex_index for i in f.loop_indices]
            js = [i % sides for i in indices]
            seam = max(js)-min(js) > sides/2
            cap = len({i//(sides*2) for i in indices}) == 1
            for li, idx, j in zip(f.loop_indices, indices, js):
                k, ring = divmod(idx//sides, 2)
                angle = (j+sides if seam and j == 0 else j)/sides
                if cap:
                    uv.data[li].uv = (.8*(radius-ring*wall)*math.cos(angle*math.tau),
                                     .8*(radius-ring*wall)*math.sin(angle*math.tau))
                else:
                    uv.data[li].uv = (distances[k]*.8, angle*math.tau*(radius-ring*wall)*.8)
            f.use_smooth = not cap
        obj['uv_method'] = 'metric cylindrical transport; 0.8 tiles/m'
        obj['pipe_path'] = json.dumps([list(p) for p in path])
        obj['pipe_radius'] = radius
        return obj

    def port(self, label, p, n, kind='PRIMARY', up=(0, 0, 1)):
        plate = super().port(label, p, n, kind, up)
        # Sleeve covers the neck behind the machined face, retaining both bores.
        for sign in (-1, 1):
            c = Vector(p)+Vector(up)*(.46*sign)
            self.tube(label+' neck sleeve', (c-Vector(n)*.23, c-Vector(n)*.065), .355, 'Metal_Dull', .08)
        plate['interface_type'] = kind
        return plate

    def finish(self):
        self.col['ports'] = json.dumps(self.ports)
        self.scene['thermal_model'] = self.name
        self.scene['thermal_phase'] = 'base'
        self.scene['se_definition_size'] = (SPECS[self.name][0], SPECS[self.name][2], SPECS[self.name][1])
        self.scene['seut_axis_map'] = 'Blender (X,Y,Z) -> SEUT FBX (-X,Z,Y)'
        self.scene['thermal_version'] = 1
        bpy.context.view_layer.update()
        return record(self.name)


def record(name):
    s, col = scene_for(name), main_for(name)
    row = {'subtype': s.name, 'cells_blender': SPECS[name], 'cells_se': list(s['se_definition_size']),
           'metres_blender': [v*2.5 for v in SPECS[name]], 'phase': s['thermal_phase'],
           'meshes': sum(o.type == 'MESH' for o in col.objects),
           'triangles': sum(len(f.vertices)-2 for o in col.objects if o.type == 'MESH' for f in o.data.polygons),
           'ports': json.loads(col['ports'])}
    if s.get('thermal_visibility_revision'):
        row['visibility_revision'] = s['thermal_visibility_revision']
        row['transparent_pressure_tubes'] = sum(bool(o.get('thermal_pressure_glass')) for o in col.objects)
        row['rotors'] = [{'subpart': o['native_subpart'], 'pivot_blender': list(o.location)}
                         for o in col.objects if o.type == 'EMPTY' and o.get('native_subpart')]
    if s.get('thermal_flow_revision'):
        row['flow_revision'] = s['thermal_flow_revision']
    if s.get('thermal_variant_of'):
        row['variant_of'] = s['thermal_variant_of']
        row['style'] = 'bare'
    if col.get('air_exhaust_samples'):
        row['air_exhaust_samples'] = json.loads(col['air_exhaust_samples'])
    path = OUT/'models.json'
    rows = json.loads(path.read_text()) if path.exists() else {}
    rows[name] = row
    path.write_text(json.dumps(rows, indent=2)+'\n')
    return row


def pipe_base(p, circuit, shape):
    for i, (n, up) in enumerate(CONTRACT['PIPE_PORTS'][shape]):
        p.port('socket '+str(i+1), Vector(n)*1.25, n, circuit, up)
    paths = []
    if shape in ('Straight', 'Roll adapter', 'End cap'):
        for sign in (-1, 1):
            if shape == 'Roll adapter':
                path = []
                for i in range(49):
                    t = i/48
                    ramp = max(0, min(1, (t-.14)/.72))
                    angle = math.pi/2*(ramp*ramp*(3-2*ramp))
                    path.append((-1.25+2.5*t, sign*.46*math.sin(angle), sign*.46*math.cos(angle)))
            else:
                path = [(-1.25, 0, sign*.46), (.72 if shape == 'End cap' else 1.25, 0, sign*.46)]
            paths.append(path)
    elif shape in ('Elbow', 'Riser'):
        for sign in (-1, 1):
            if shape == 'Elbow':
                path = [(-1.25, 0, sign*.46), (-.6, 0, sign*.46)]
                path += [(-.6+.6*math.sin(a), .6-.6*math.cos(a), sign*.46) for a in (i*math.pi/40 for i in range(1, 21))]
                path.append((0, 1.25, sign*.46))
            else:
                path = [(-1.25, 0, sign*.46), (-1, 0, sign*.46)]
                path += [(-1+(1-sign*.46)*math.sin(a), 0, 1-(1-sign*.46)*math.cos(a)) for a in (i*math.pi/64 for i in range(1, 33))]
                path.append((-sign*.46, 0, 1.25))
            paths.append(path)
    else:
        for sign in (-1, 1):
            branches = [((0, 0, sign*.46), (0, 1.25, sign*.46))]
            if shape == 'Cross':
                branches.append(((0, 0, sign*.46), (0, -1.25, sign*.46)))
            p.branch_pipe('connected '+('H' if sign > 0 else 'C')+' manifold', (-1.25, 0, sign*.46), (1.25, 0, sign*.46), branches)
    for sign, path in zip((-1, 1), paths):
        p.tube('insulated '+('H' if sign > 0 else 'C')+' channel', path, .355, 'PaintedMetal_Darker', .075, 32)
        if shape == 'End cap':
            p.cylinder('blind pressure closure', (.70, 0, sign*.46), (.80, 0, sign*.46), .355, 'PaintedMetal_Colorable')
    pipe_frame(p)
    p.col['circuit'] = circuit
    p.col['pipe_shape'] = shape


def pipe_frame(p):
    # Corner load cage clears all bores, including the vertical/rolled ports.
    p.box('pipe base mounting shoe', (0, 0, -1.18), (2.24, 2.24, .14), 'PaintedMetal_Colorable', .025)
    for x in (-.96, .96):
        for y in (-.96, .96):
            p.box('pipe cage upright', (x, y, -.06), (.14, .14, 2.10), 'PaintedMetal_Colorable', .014)
    # Top edges stop below the riser's face flange.
    for x in (-.96, .96):
        p.box('pipe cage upper rail', (x, 0, 1.025), (.14, 2.06, .07), 'Metal_Dull', .012)
    for port in p.ports:
        n, up = Vector(port['normal']), Vector(port['hot_axis'])
        u = up.cross(n)
        for a in (-1, 1):
            for b in (-1, 1):
                p.box('flange load gusset', Vector(port['position'])-n*.25+u*(a*.79)+up*(b*.79), (.30, .30, .30), 'Metal_Dull', .018)


def build_base(name):
    if name == 'Hull radiator':
        return runpy.run_path(str(ROOT/'assets/build_hull_radiator.py'))['build']()
    if name in CONTRACT['PIPE_ROTORS']:
        return runpy.run_path(str(ROOT/'assets/build_pipe_rotor.py'))['build'](name)
    if name not in CONTRACT['RUNTIME']:
        raise ValueError('No current block builder for '+name)
    if 'mirrored' in name:
        return runpy.run_path(str(ROOT/'assets/build_mirrored_train.py'))['build'](name)
    if name == 'Atmospheric cooler':
        return runpy.run_path(str(ROOT/'assets/build_integrated_cooler.py'))['apply']()
    if name == 'Radiator panel':
        return runpy.run_path(str(ROOT/'assets/build_tracking_radiator.py'))['extension']()
    if name in CONTRACT['BARE_PIPES']:
        return build_bare_pipe(name)
    p = Parts(name)
    if name == 'Space radiator':
        p.finish()
        return runpy.run_path(str(ROOT/'assets/build_tracking_radiator.py'))['apply']()
    if name == 'Reactor housing':
        runpy.run_path(str(ROOT/'assets/build_reactor_thermal_manifolds.py'))['build'](p)
    elif name == 'PRIMARY / Reactor adapter':
        # The original reactor/controller band is 170 mm above the cell centre.
        # Only this inlet is offset; its outlet uses the standard pipe lattice.
        p.port('socket 2', (1.25, 0, 0), (1, 0, 0), 'PRIMARY')
        p.port('reactor inlet', (-1.25, 0, .17), (-1, 0, 0), 'PRIMARY')
        p.ports[-1]['cell_offset'] = [0, 0, .17]
        p.ports[-1]['reactor_transition'] = True
        for sign in (-1, 1):
            path = [(-1.25, 0, sign*.46+.17), (-.80, 0, sign*.46+.17),
                    (.80, 0, sign*.46), (1.25, 0, sign*.46)]
            p.tube('reactor transition '+str(sign), path, .355, 'PaintedMetal_Darker', .075, 32)
        pipe_frame(p)
        p.col['circuit'] = 'PRIMARY'
        p.col['pipe_shape'] = 'Reactor adapter'
    elif ' / ' in name:
        pipe_base(p, *name.split(' / '))
    else:
        if name.endswith(' upgraded'):
            BUILD['upgraded'](p)
        else:
            BUILD['brayton'](p)
    row = p.finish()
    if name == 'Reactor housing':
        runpy.run_path(str(ROOT/'assets/refine_thermal_flow.py'))['apply'](name)
        row = record(name)
    return row


def build_bare_pipe(name):
    """Derive pipe-only blocks from accepted mains without editing shared art.

    Circular pressure fittings, glass, UVs, port frames and flow paths stay
    identical. Remove the mounting cage and plate-dependent details together,
    so bolts, decals and status panels cannot float where their backing was.
    """
    base = CONTRACT['BARE_PIPES'][name]
    source = main_for(base)
    source_scene = scene_for(base)
    assert source_scene['thermal_phase'] == 'textures', 'Derive bare pipes from finished mains'
    p = Parts(name)
    for key, value in source.items():
        if key != 'seut':
            p.col[key] = value
    p.col['thermal_model'] = name
    p.col['thermal_variant_of'] = base
    p.ports = json.loads(source['ports'])
    owners = ('thermal_support', 'thermal_decal_support', 'thermal_marking_support',
              'thermal_seated_on', 'thermal_support_space')
    removed = {o.name for o in source.objects if o.get('interface_type') or o.get('thermal_pipe_casing') or any(
        term in o.name.lower() for term in ('pipe cage', 'pipe base mounting shoe',
                                           'flange load web', 'flange load gusset',
                                           'status bezel', 'status lens'))}
    while True:
        dependents = {o.name for o in source.objects if any(o.get(k) in removed for k in owners)}
        if dependents <= removed:
            break
        removed |= dependents
    copies = {}
    for old in source.objects:
        if old.name in removed:
            continue
        obj = old.copy()
        if old.data:
            obj.data = old.data.copy()
        obj.animation_data_clear()
        obj.name = name + ' / ' + old.name.removeprefix(base + ' / ')
        p.col.objects.link(obj)
        copies[old] = obj
    renamed = {old.name: obj.name for old, obj in copies.items()}
    for old, obj in copies.items():
        pose = old.matrix_world.copy()
        obj.parent = copies.get(old.parent)
        obj.matrix_world = pose
        for key in owners:
            if obj.get(key):
                assert obj[key] in renamed, (name, 'Unsupported retained detail', old.name, obj[key])
                obj[key] = renamed[obj[key]]
    p.finish()
    for key, value in source_scene.items():
        if key.startswith('thermal_') and key not in ('thermal_model', 'thermal_enclosed_revision'):
            p.scene[key] = value
    p.scene['thermal_variant_of'] = base
    p.scene['thermal_bare_revision'] = 1
    bpy.context.view_layer.update()
    flows = ROOT / 'assets/thermal-flow-paths.json'
    data = json.loads(flows.read_text())
    data['models'][CONTRACT['subtype'](name)] = data['models'][CONTRACT['subtype'](base)]
    flows.write_text(json.dumps(data, indent=2) + '\n')
    return record(name)


def rebuild_base(name):
    if name not in CONTRACT['RUNTIME']:
        raise ValueError('No current block builder for '+name)
    if name == 'Atmospheric cooler':
        return runpy.run_path(str(ROOT/'assets/build_integrated_cooler.py'))['apply']()
    scene, col = scene_for(name), main_for(name)
    assert scene.get('thermal_model') == name and scene['thermal_phase'] in ('base', 'geometry', 'textures')
    phase = scene['thermal_phase']
    users = [o for o in bpy.data.objects if o.instance_collection == col]
    collections = list(scene.collection.children_recursive)
    bpy.context.window.scene = bpy.data.scenes['Thermal production / Main model lineup']
    for obj in list(scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.scenes.remove(scene)
    for collection in reversed(collections):
        bpy.data.collections.remove(collection)
    row = build_base(name)
    for obj in users:
        obj.instance_collection = main_for(name)
    if phase != 'base' and name not in CONTRACT['BARE_PIPES'] and 'mirrored' not in name:
        refine = runpy.run_path(str(ROOT/'assets/refine_thermal_models.py'))
        row = refine['geometry'](name)
        if phase == 'textures':
            row = refine['textures'](name)
    return row


def checkpoint(label):
    path = ROOT/'assets'/('arcane-thermal-'+label+'.blend')
    assert not path.exists(), 'Checkpoint already exists'
    bpy.ops.wm.save_as_mainfile(filepath=str(path), copy=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(FILE))
    return {'checkpoint': str(path)}


if __name__ == '__main__':
    result = build_base(globals()['MODEL_NAME'])
