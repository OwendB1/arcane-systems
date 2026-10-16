"""Actual grid-block assemblies and reproducible live-UI review evidence."""
import json
from pathlib import Path
import runpy

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(str(ROOT/'assets/build_thermal_models.py'))
C = M['CONTRACT']
OUT = M['OUT']
OLD = runpy.run_path(str(ROOT/'assets/review_thermal_concepts.py'))


def view(scene, target=(0, 0, 0), direction=(1, -1, .65), distance=18):
    return OLD['view'](scene, target, direction, distance)


def snapshot(filename):
    OLD['snapshot'].__globals__['OUT'] = OUT
    return OLD['snapshot'](filename)


def fresh(label):
    name = 'Thermal production / '+label
    old = bpy.data.scenes.get(name)
    if old:
        assert old.get('review_only'), 'Only generated review scenes may be refreshed'
        bpy.context.window.scene = M['scene_for']('Brayton train')
        owned = list(old.collection.children)
        for obj in list(old.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.scenes.remove(old)
        for col in owned:
            bpy.data.collections.remove(col)
    scene = bpy.data.scenes.new(name)
    bpy.context.window.scene = scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1
    col = bpy.data.collections.new(name+' / guides')
    scene.collection.children.link(col)
    col['review_only'] = True
    p = object.__new__(M['Parts'])
    p.name, p.scene, p.col = name, scene, col
    p.ports, p.support = [], []
    p.native = {m.name: m for m in bpy.data.materials if m.library}
    scene['review_only'] = True
    return scene, p


def instance(scene, name, position, rotation=None, label=None):
    col = M['main_for'](name)
    obj = bpy.data.objects.new(label or name, None)
    scene.collection.objects.link(obj)
    obj.instance_type, obj.instance_collection = 'COLLECTION', col
    obj.matrix_world = Matrix(rotation).to_4x4() if rotation else Matrix.Identity(4)
    obj.location = position
    obj['thermal_instance'] = name
    return obj


def ports(obj):
    m = obj.matrix_world
    return [dict(r, position=list(m@Vector(r['position'])),
                 normal=list(m.to_3x3()@Vector(r['normal'])),
                 hot_axis=list(m.to_3x3()@Vector(r['hot_axis'])))
            for r in json.loads(obj.instance_collection['ports'])]


def floor(p, centre, size):
    x, y = centre
    w, d = size
    deck = p.box('review deck', (x, y, -.15), (w, d, .30), 'PaintedMetal_VeryDark')
    for gx in range(round(x-w/2+1), round(x+w/2), 5):
        p.box('5 m grid', (gx, y, .002), (.012, d, .003), 'Metal_Dull', 0)
    for gy in range(round(y-d/2+1), round(y+d/2), 5):
        p.box('5 m grid', (x, gy, .002), (w, .012, .003), 'Metal_Dull', 0)
    OLD['engineer'](p, (x, y-d/2+3))
    for dx in (-1.25, 1.25):
        p.box('2.5 m cell upright', (x+dx, y-d/2+3, 1.25), (.02, .02, 2.5), 'Metal_Dull', 0)
    p.box('2.5 m cell cap', (x, y-d/2+3, 2.5), (2.5, .02, .02), 'Metal_Dull', 0)
    return deck


def lineup():
    scene, p = fresh('Main model lineup')
    deck = floor(p, (0, 9), (65, 65))
    positions = {'Brayton train': (-20, -10, 2.5), 'Brayton train upgraded': (0, -10, 2.5),
                 'Primary heater': (-22.5, 5, 3.75), 'Primary heater upgraded': (-10, 5, 3.75),
                 'Recuperator': (2.5, 6.25, 3.75), 'Recuperator upgraded': (15, 6.25, 3.75),
                 'Atmospheric cooler': (-20, 18.75, 3.75), 'Space radiator': (-7.5, 18.75, 3.75),
                 'Reactor housing': (12.5, 22.5, 3.75),
                 'PRIMARY / Reactor adapter': (22.5, 20, 1.25)}
    for name, pos in positions.items():
        instance(scene, name, pos)
        p.label(deck, name.upper(), (pos[0], pos[1]-5, .006), (1, 0, 0), (0, 1, 0), .24)
    for row, circuit in enumerate(C['CIRCUITS']):
        for col, shape in enumerate(C['PIPE_PORTS']):
            pos = (-20+7.5*col, 30+5*row, 1.25)
            instance(scene, circuit+' / '+shape, pos)
            p.label(deck, circuit+' / '+shape.upper(), (pos[0], pos[1]-1.8, .006), (1, 0, 0), (0, 1, 0), .15)
    return {'scene': scene.name, 'models': len(C['SPECS'])}


def plant(environment='atmosphere', upgraded=False):
    assert environment in ('atmosphere', 'space')
    runpy.run_path(str(ROOT/'assets/build_reactor_thermal_manifolds.py'))['pose'](1)
    scene, p = fresh(environment.title()+(' premium' if upgraded else ' starter'))
    suffix = ' upgraded' if upgraded else ''
    names = {'train': 'Brayton train'+suffix, 'recovery': 'Recuperator'+suffix,
             'heater': 'Primary heater'+suffix,
             'cooler': 'Atmospheric cooler' if environment == 'atmosphere' else 'Space radiator',
             'source': 'Reactor housing'}
    positions = {'train': (-12.5, 0, 2.5), 'recovery': (0, 1.25, 3.75),
                 'heater': (12.5, -7.5, 3.75), 'cooler': (12.5, 11.25, 3.75),
                 'source': (-25, -12.5, 3.75)}
    units, sockets, blocked = {}, {}, set()
    for key, name in names.items():
        obj = instance(scene, name, positions[key], label='Plant / '+key)
        units[key] = obj
        bpy.context.view_layer.update()
        for port in ports(obj):
            sockets[key, port['id']] = port
        blocked |= C['occupied'](positions[key], C['SPECS'][name])
    # Transition from the original curved armor's native band elevation to
    # the 2.5 m pipe lattice. All four transition blocks are real bill items.
    for port in ports(units['source']):
        normal = Vector(port['normal'])
        pos = Vector(port['position'])+normal*1.25-Vector((0, 0, .17))
        rotation = Matrix.Identity(3) if normal.x > 0 else Matrix.Rotation(3.141592653589793, 3, 'Z')
        adapter = instance(scene, 'PRIMARY / Reactor adapter', pos, rotation, 'Transition '+port['id'])
        bpy.context.view_layer.update()
        outer = next(r for r in ports(adapter) if r['id'] == 'socket 2')
        sockets['source', port['id']] = outer
        blocked |= C['occupied'](pos, (1, 1, 1))
        if port['id'] != 'primary RA':
            cap_pos = Vector(outer['position'])+normal*1.25
            instance(scene, 'PRIMARY / End cap', cap_pos, rotation, 'Isolated '+port['id'])
            blocked |= C['occupied'](cap_pos, (1, 1, 1))
    edges = [(('source', 'primary RA'), ('heater', 'primary')),
             (('heater', 'CO2'), ('recovery', 'high-pressure 1')),
             (('recovery', 'high-pressure -1'), ('train', 'CO2 leg -1')),
             (('train', 'CO2 leg 1'), ('recovery', 'low-pressure -1')),
             (('recovery', 'low-pressure 1'), ('cooler', 'CO2'))]
    routes = []
    for index, (a, b) in enumerate(edges):
        left, right = sockets[a], sockets[b]
        assert left['type'] == right['type']
        steps = C['route'](left, right, blocked)
        for j, step in enumerate(steps):
            model = left['type']+' / '+step['shape']
            instance(scene, model, C['centre'](step['cell']), step['rotation'],
                     'Route '+str(index+1)+' / '+str(j+1)+' / '+model)
            blocked.add(tuple(step['cell']))
        routes.append({'from': list(a), 'to': list(b), 'circuit': left['type'], 'blocks': steps})
    floor(p, (-2.5, 0), (65, 50))
    scene['thermal_grid_routes'] = json.dumps(routes)
    scene['thermal_environment'] = environment
    scene['thermal_grade'] = 'premium' if upgraded else 'starter'
    path = OUT/(environment+('-premium' if upgraded else '-starter')+'-grid-bill.json')
    report = {'scene': scene.name, 'units': names, 'positions': positions, 'routes': routes,
              'pipe_blocks': sum(len(r['blocks']) for r in routes),
              'efficiency_note': 'Hardware/topology view; premium efficiency also requires extra recovery capacity'}
    path.write_text(json.dumps(report, indent=2)+'\n')
    return {'scene': scene.name, 'pipe_blocks': report['pipe_blocks'], 'typed_routes': len(routes)}


def bank():
    """Three machines, two typed headers built exclusively from 1-cell parts."""
    scene, p = fresh('Grid parallel bank')
    used = set()
    for x in (-15, 0, 15):
        obj = instance(scene, 'Brayton train', (x, 0, 2.5))
        used |= C['occupied'](obj.location, C['SPECS']['Brayton train'])
    for sign, circuit in ((-1, 'CO2_HP'), (1, 'CO2_LP')):
        # Header y=±7.5; at branches a tee faces the adjacent machine.
        for i in range(-10, 9):
            x = i*2.5
            shape = 'Tee' if x in (-17.5, -2.5, 12.5) else 'Straight'
            rot = Matrix.Rotation(3.141592653589793 if sign > 0 else 0, 3, 'Z')
            # Tee's default north branch must face inward.
            obj = instance(scene, circuit+' / '+shape, (x, sign*7.5, 3.75), rot)
            obj['bank_header'] = circuit
        for x in (-17.5, -2.5, 12.5):
            obj = instance(scene, circuit+' / Straight', (x, sign*5, 3.75), Matrix.Rotation(3.141592653589793/2, 3, 'Z'))
            obj['bank_branch'] = circuit
        for x, angle in ((-27.5, 3.141592653589793), (22.5, 0)):
            instance(scene, circuit+' / End cap', (x, sign*7.5, 3.75), Matrix.Rotation(angle, 3, 'Z'))
    floor(p, (-2.5, 0), (62.5, 27.5))
    scene['bank_expected_ports_closed'] = True
    return {'scene': scene.name, 'trains': 3, 'pipe_blocks': 48}


if __name__ == '__main__':
    result = lineup()
