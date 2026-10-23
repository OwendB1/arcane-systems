"""Actual grid-block assemblies and reproducible live-UI review evidence."""
import json
import math
from pathlib import Path
import runpy

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(str(ROOT/'assets/build_thermal_models.py'))
C = M['CONTRACT']
OUT = M['OUT']
OLD = runpy.run_path(str(ROOT/'assets/review_thermal_concepts.py'))


def view(scene, target=(0, 0, 0), direction=(1, -1, .65), distance=18, light_rotation=.5):
    assert -math.pi <= light_rotation <= math.pi, 'Studio light rotation is limited to +/- pi'
    row = OLD['view'](scene, target, direction, distance)
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            area.spaces.active.shading.studiolight_rotate_z = light_rotation
    row['light_rotation'] = light_rotation
    return row


def snapshot(filename):
    OLD['snapshot'].__globals__['OUT'] = OUT
    return OLD['snapshot'](filename)


def start_review(plan, label):
    """Let the live viewport settle between each view and its UI capture."""
    key = 'thermal_live_review'
    previous = bpy.app.driver_namespace.get(key)
    assert not previous or previous['status'] != 'running', 'A UI review is already running'
    state = {'status': 'running', 'index': 0, 'total': len(plan), 'phase': 'set'}
    bpy.app.driver_namespace[key] = state
    (OUT/(label+'-plan.json')).write_text(json.dumps(plan, indent=2)+'\n')

    def progress():
        (OUT/(label+'-progress.json')).write_text(json.dumps(state, indent=2)+'\n')

    def step():
        if state['index'] == len(plan):
            state['status'] = 'complete'
            progress()
            return None
        row = plan[state['index']]
        if state['phase'] == 'set':
            view(row['scene'], row['target'], row['direction'], row['distance'],
                 row.get('light_rotation', .5))
            if 'lens_mm' in row:
                for area in bpy.context.screen.areas:
                    if area.type == 'VIEW_3D':area.spaces.active.lens = row['lens_mm']
            if 'collection' in row:
                def visibility(layer):
                    if layer.collection.seut.col_type in ('main', 'bs', 'lod', 'hkt'):
                        layer.hide_viewport = layer.collection.name != row['collection']
                    for child in layer.children:visibility(child)
                visibility(bpy.context.view_layer.layer_collection)
            if 'frame' in row:
                bpy.context.scene.frame_set(row['frame'])
            state['phase'] = 'capture'
            progress()
            return 1.1
        snapshot(row['file'])
        state['index'] += 1
        state['phase'] = 'set'
        progress()
        return .05

    progress()
    bpy.app.timers.register(step, first_interval=.1)
    return {'review': label, 'views': len(plan)}


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
    name = C['PIPE_ALIASES'].get(name, name)
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
    # Matrix decomposition in Blender leaves ~1e-7 offsets at quarter turns.
    # These review sockets belong to the exact cardinal pipe lattice.
    def cardinal(v):
        assert all(abs(x-round(x)) < 1e-5 for x in v), ('Non-grid direction', obj.name, v)
        return [round(x) for x in v]
    return [dict(r, type=C['runtime_circuit'](obj['thermal_instance'], r['type']),
                 position=list(m@Vector(r['position'])),
                 normal=cardinal(m.to_3x3()@Vector(r['normal'])),
                 hot_axis=cardinal(m.to_3x3()@Vector(r['hot_axis'])))
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
    for row, bare in enumerate((False, True)):
        for col, shape in enumerate(C['PIPE_PORTS']):
            pos = (-20+7.5*col, 30+5*row, 1.25)
            instance(scene, 'PRIMARY / '+shape+(' bare' if bare else ''), pos)
            p.label(deck, ('BARE / ' if bare else 'MANIFOLD / ')+shape.upper(), (pos[0], pos[1]-1.8, .006), (1, 0, 0), (0, 1, 0), .15)
    return {'scene': scene.name, 'models': len(C['PLAYABLE'])}


def plant(environment='atmosphere', upgraded=False, room_loop=False):
    assert environment in ('atmosphere', 'space')
    runpy.run_path(str(ROOT/'assets/build_reactor_thermal_manifolds.py'))['pose'](1)
    scene, p = fresh('Reactor room loop' if room_loop else environment.title()+(' premium' if upgraded else ' starter'))
    suffix = ' upgraded' if upgraded else ''
    names = {'train': 'Brayton train'+suffix,
             'cooler': 'Atmospheric cooler' if environment == 'atmosphere' else 'Space radiator',
             'source': 'Reactor housing'}
    positions = {'train': (-10, 1.25, 2.5), 'cooler': (12.5, 11.25, 3.75),
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
        if port['id'] not in ('primary RA', 'primary RB'):
            cap_pos = Vector(outer['position'])+normal*1.25
            instance(scene, 'PRIMARY / End cap', cap_pos, rotation, 'Isolated '+port['id'])
            blocked |= C['occupied'](cap_pos, (1, 1, 1))
    edges = [(('source', 'primary RA'), ('train', 'CO2')),
             (('source', 'primary RB'), ('cooler', 'CO2'))]
    if room_loop:
        anchors = [((-27.5,-22.5,1.25), -math.pi/2), ((25,-22.5,1.25), 0),
                   ((25,20,1.25), math.pi/2), ((-12.5,20,1.25), math.pi)]
        for i,(pos,angle) in enumerate(anchors):
            key='room'+str(i+1)
            rotation=Matrix([[round(v) for v in row] for row in Matrix.Rotation(angle,3,'Z')])
            obj=instance(scene,'PRIMARY / Elbow',pos,rotation,key)
            bpy.context.view_layer.update()
            for port in ports(obj): sockets[key,port['id']]=port
            blocked |= C['occupied'](pos,(1,1,1))
        edges = [(('source','primary RA'),('room1','socket 1'))]+[
            (('room'+str(i),'socket 2'),('room'+str(i+1),'socket 1')) for i in range(1,4)]+[
            (('room4','socket 2'),('train','CO2'))]+edges[1:]
    routes = []
    for index, (a, b) in enumerate(edges):
        left, right = sockets[a], sockets[b]
        assert C['circuits_match'](left['type'], right['type'])
        try:
            reserved = {C['cell'](tuple(Vector(port['position'])+Vector(port['normal'])*1.25))
                        for pair in edges[index+1:] for key in pair for port in [sockets[key]]}
            steps = C['route'](left, right, blocked | reserved)
        except (ValueError, AssertionError) as error:
            raise ValueError('Route '+str(a)+' -> '+str(b)+': '+str(error)) from error
        for j, step in enumerate(steps):
            model = 'PRIMARY / '+step['shape']
            instance(scene, model, C['centre'](step['cell']), step['rotation'],
                     'Route '+str(index+1)+' / '+str(j+1)+' / '+model)
            blocked.add(tuple(step['cell']))
        routes.append({'from': list(a), 'to': list(b), 'circuit': left['type'], 'blocks': steps})
    floor(p, (-2.5, 0), (75, 60) if room_loop else (65, 50))
    scene['thermal_grid_routes'] = json.dumps(routes)
    scene['thermal_environment'] = environment
    scene['thermal_grade'] = 'premium' if upgraded else 'starter'
    path = OUT/('reactor-room-grid-bill.json' if room_loop else environment+('-premium' if upgraded else '-starter')+'-grid-bill.json')
    report = {'scene': scene.name, 'units': names, 'positions': positions, 'routes': routes,
              'pipe_blocks': sum(len(r['blocks']) for r in routes),
              'efficiency_note': 'Direct reactor-to-turbine loop; higher efficiencies require source temperature and train tier'}
    path.write_text(json.dumps(report, indent=2)+'\n')
    if room_loop or (environment == 'atmosphere' and not upgraded):
        bpy.context.view_layer.update()
        fixture = {'scene': scene.name, 'instances': [
            {'model': obj['thermal_instance'], 'matrix_blender': [list(row) for row in obj.matrix_world]}
            for obj in scene.objects if obj.get('thermal_instance')]}
        (ROOT.parent/'tests/fixtures'/('thermal-room-layout.json' if room_loop else 'thermal-starter-layout.json')).write_text(json.dumps(fixture, indent=2)+'\n')
    return {'scene': scene.name, 'pipe_blocks': report['pipe_blocks'], 'typed_routes': len(routes)}


def cooler_hull():
    """Full-size adjacent armor proves the cooler's flush hull fit."""
    scene,p=fresh('Integrated cooler / hull fit')
    instance(scene,'Atmospheric cooler',(0,0,3.75))
    for x in (-5,-2.5,0,2.5,5):
        for z in (-1.25,1.25,3.75,6.25,8.75):
            if abs(x)!=5 and z not in (-1.25,8.75):continue
            for y in (-1.25,1.25):
                p.box('neighbor armor',(x,y,z),(2.5,2.5,2.5),'PaintedMetal_Darker',.002)
    OLD['engineer'](p,(-7,-4))
    return {'scene':scene.name}


def bank():
    """Single-socket turbines branch from one shared duplex header."""
    scene, p = fresh('Grid parallel bank')
    branch_x = (-17.5, -2.5, 12.5)
    for i, x in enumerate((-15, 0, 15)):
        mirrored = i == 1
        instance(scene, 'Brayton train mirrored' if mirrored else 'Brayton train',
                 (x+2.5, -16.25 if mirrored else 1.25, 2.5))
    for i in range(-10, 9):
        x = i*2.5
        shape = 'Tee' if x in branch_x else 'Straight'
        rot = Matrix.Rotation(math.pi if x == -2.5 else 0, 3, 'Z')
        instance(scene, 'PRIMARY / '+shape, (x, -7.5, 1.25), rot)
    for x in branch_x:
        for y in (-10, -12.5) if x == -2.5 else (-5, -2.5):
            instance(scene, 'PRIMARY / Straight', (x, y, 1.25), Matrix.Rotation(math.pi/2, 3, 'Z'))
    for x, angle in ((-27.5, math.pi), (22.5, 0)):
        instance(scene, 'PRIMARY / End cap', (x, -7.5, 1.25), Matrix.Rotation(angle, 3, 'Z'))
    floor(p, (-2.5, -7.5), (62.5, 32.5))
    scene['bank_expected_ports_closed'] = True
    return {'scene': scene.name, 'trains': 3, 'pipe_blocks': 27}


def compact_trains():
    """All four 2×2×5 turbine variants beside an engineer and native grid cells."""
    scene,p=fresh('Compact turbines / size review')
    for name,y in (('Brayton train',1.25),('Brayton train upgraded',8.75),
                   ('Brayton train mirrored',16.25),('Brayton train mirrored upgraded',23.75)):
        instance(scene,name,(2.5,y,2.5))
    OLD['engineer'](p,(-5,-3))
    floor(p,(0,12.5),(15,35))
    return {'scene':scene.name,'cells_width_height_length':[2,2,5]}


if __name__ == '__main__':
    result = lineup()
