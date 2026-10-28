"""Large-grid model and duplex-interface contract; no Blender dependency.

Blender: X length, Y width, Z up. SEUT FBX: (-X, Z, Y).
Review lattice: cell centres (2.5*i, 2.5*j, 1.25+2.5*k).
"""
import heapq
import itertools
import math

CELL = 2.5
TRAIN_SHAFT_Z = -.10
TRAIN_CENTRES = {"compressor": -4.40, "turbine": 1.00, "generator": 3.70, "cabinet": 5.40}
# Lengthen the complete generator from its fixed turbine-facing seat.
TRAIN_GENERATOR_REAR = 4.94
TRAIN_GENERATOR_STRETCH = (TRAIN_GENERATOR_REAR-(TRAIN_CENTRES['generator']-1))/2


def generator_x(x):
    front = TRAIN_CENTRES['generator']-1
    return front+(x-front)*TRAIN_GENERATOR_STRETCH
CIRCUITS = ('PRIMARY', 'CO2_HP', 'CO2_LP')
# Compact train interfaces. Standard duplex bores remain unscaled; side sockets fit the 5×2×2 envelope.
TRAIN_PORTS = [
    {'id': 'CO2', 'type': 'CO2', 'position': [-5.0, -2.5, -1.25],
     'normal': [0., -1., 0.], 'hot_axis': [0., 0., 1.]},
]
MACHINES = {
    'Brayton train': (5, 2, 2),
    'Brayton train upgraded': (5, 2, 2),
    'Brayton train mirrored': (5, 2, 2),
    'Brayton train mirrored upgraded': (5, 2, 2),
    'Primary heater': (3, 3, 3),
    'Primary heater upgraded': (3, 3, 3),
    'Recuperator': (3, 2, 3),
    'Recuperator upgraded': (3, 2, 3),
    'Atmospheric cooler': (3, 2, 3),
    'Space radiator': (1, 1, 1),
    'Radiator panel': (3, 3, 2),
    'Hull radiator': (3, 1, 2),
    'Pipe rotor': (1, 1, 1),
    'Pipe rotor head': (1, 1, 1),
    'Reactor housing': (5, 5, 3),
}
PIPE_ROTORS = {'Pipe rotor': 'MotorAdvancedStator', 'Pipe rotor head': 'MotorAdvancedRotor'}
# Native MyMotorStator constrains the head BLOCK ORIGIN to electric_motor;
# the wheel dummy and initial placement offset do not offset the live hinge.
PIPE_ROTOR_HEAD_CENTRE = 2.70
PIPE_ROTOR_DISPLACEMENT = (-.10, .10)
PIPE_ROTOR_CUFF_BOTTOM = -1.85
HULL_RADIATOR_PORTS = [
    dict(id='Rear H C', type='CO2', position=(0, 1.25, -1.25), normal=(0, 1, 0),
         hot_axis=(0, 0, 1), self_sealing=True),
] + [dict(id=label, type='CO2', position=p, normal=n, hot_axis=(0, -1, 0),
          hull_only=True, self_sealing=True) for label, p, n in (
    ('Left edge', (-3.75, 0, 0), (-1, 0, 0)), ('Right edge', (3.75, 0, 0), (1, 0, 0)),
    ('Top edge', (0, 0, 2.5), (0, 0, 1)), ('Bottom edge', (0, 0, -2.5), (0, 0, -1)))]
HULL_RADIATOR_SAMPLES = [(x, -1.28, z) for x in (-2.725, -1.975, -1.225, -.475, .475, 1.225, 1.975, 2.725)
                        for z in (-1.52, -.52, .48, 1.48)]
# (face normal, positive/H offset direction). Negative is C, never swapped.
PIPE_PORTS = {
    'Straight': (((-1, 0, 0), (0, 0, 1)), ((1, 0, 0), (0, 0, 1))),
    'Elbow': (((-1, 0, 0), (0, 0, 1)), ((0, 1, 0), (0, 0, 1))),
    'Riser': (((-1, 0, 0), (0, 0, 1)), ((0, 0, 1), (-1, 0, 0))),
    'Tee': (((-1, 0, 0), (0, 0, 1)), ((1, 0, 0), (0, 0, 1)), ((0, 1, 0), (0, 0, 1))),
    'Cross': (((-1, 0, 0), (0, 0, 1)), ((1, 0, 0), (0, 0, 1)),
              ((0, -1, 0), (0, 0, 1)), ((0, 1, 0), (0, 0, 1))),
    'Roll adapter': (((-1, 0, 0), (0, 0, 1)), ((1, 0, 0), (0, 1, 0))),
    'End cap': (((-1, 0, 0), (0, 0, 1)),),
}
SPECS = dict(MACHINES)
SPECS.update({c+' / '+shape: (1, 1, 1) for c in CIRCUITS for shape in PIPE_PORTS})
SPECS['PRIMARY / Reactor adapter'] = (1, 1, 1)
BARE_PIPES = {name + ' bare': name for name in SPECS if ' / ' in name}
SPECS.update({name: SPECS[base] for name, base in BARE_PIPES.items()})
# Keep authored rebuild sources and saved-world IDs. PRIMARY supplies the single
# public pipe family; HP/LP IDs are hidden aliases using those same assets.
RETIRED = {'Primary heater', 'Primary heater upgraded', 'Recuperator', 'Recuperator upgraded'}
PIPE_ALIASES = {name: 'PRIMARY / '+name.split(' / ')[1] for name in SPECS
                if name.startswith(('CO2_HP / ', 'CO2_LP / '))}
# Gameplay variants reuse the accepted base geometry, weld stages and LODs.
COOLER_UPGRADES = {name+' upgraded': name for name in ('Atmospheric cooler', 'Space radiator', 'Radiator panel', 'Hull radiator')}
RUNTIME = {name: cells for name, cells in SPECS.items() if name not in RETIRED}
RUNTIME.update({name: SPECS[base] for name, base in COOLER_UPGRADES.items()})
PLAYABLE = {name: cells for name, cells in RUNTIME.items() if name not in PIPE_ALIASES}


def runtime_models(authored):
    models = {name: dict(spec) for name, spec in authored.items() if name in RUNTIME}
    for name, base in COOLER_UPGRADES.items():
        models[name] = dict(authored[base], subtype=subtype(name), geometry_source=base)
    return models


def runtime_circuit(name, circuit):
    return circuit if circuit == 'CHAMBER' else 'CO2'


def circuits_match(a, b):
    return True  # All external sockets carry the same H/C duplex pair.


def train_ports(name):
    return [dict(p, position=[p['position'][0], -p['position'][1], p['position'][2]],
                 normal=[p['normal'][0], -p['normal'][1], p['normal'][2]])
            for p in TRAIN_PORTS] if 'mirrored' in name else TRAIN_PORTS


def subtype(name):
    return 'ArcanePower_Thermal_' + ''.join(c for c in name.title().replace('Co2', 'CO2') if c.isalnum())


def add(a, b):
    return tuple(x+y for x, y in zip(a, b))


def neg(a):
    return tuple(-x for x in a)


def rotate(matrix, vector):
    return tuple(sum(row[i]*vector[i] for i in range(3)) for row in matrix)


def rotations():
    result = []
    for perm in itertools.permutations(range(3)):
        for signs in itertools.product((-1, 1), repeat=3):
            m = tuple(tuple(signs[i] if j == perm[i] else 0 for j in range(3)) for i in range(3))
            a, b, c = m
            det = a[0]*(b[1]*c[2]-b[2]*c[1])-a[1]*(b[0]*c[2]-b[2]*c[0])+a[2]*(b[0]*c[1]-b[1]*c[0])
            if det == 1:
                result.append(m)
    return result


ROTATIONS = rotations()


def cell(point):
    f = (point[0]/CELL, point[1]/CELL, (point[2]-CELL/2)/CELL)
    assert all(abs(x-round(x)) < 1e-5 for x in f), ('Off-grid centre', point)
    return tuple(round(x) for x in f)


def centre(index):
    return (index[0]*CELL, index[1]*CELL, index[2]*CELL+CELL/2)


def occupied(position, size):
    low = tuple(position[i]-(size[i]-1)*CELL/2 for i in range(3))
    first = cell(low)
    return {add(first, index) for index in itertools.product(*(range(s) for s in size))}


def route(start, end, blocked):
    """A* over real 1-cell duplex pieces, including roll and vertical bends.

    State includes channel orientation. Occupied machine/pipe cells are forbidden;
    neighbouring pipes meet by matching both face normals and H offset vectors.
    """
    options = {}
    for shape in ('Straight', 'Elbow', 'Riser', 'Roll adapter'):
        for m in ROTATIONS:
            ports = [(rotate(m, n), rotate(m, up)) for n, up in PIPE_PORTS[shape]]
            for i in (0, 1):
                n, up = ports[i]
                out_n, out_up = ports[1-i]
                key = (n, up)
                item = (shape, m, out_n, out_up)
                if item not in options.setdefault(key, []):
                    options[key].append(item)
    sn, su = tuple(start['normal']), tuple(start['hot_axis'])
    en, eu = tuple(end['normal']), tuple(end['hot_axis'])
    first = cell(add(start['position'], tuple(x*CELL/2 for x in sn)))
    last = cell(add(end['position'], tuple(x*CELL/2 for x in en)))
    assert first not in blocked and last not in blocked, ('Blocked socket', first, last)
    initial = (first, neg(sn), su)
    serial = itertools.count()
    queue = [(0, next(serial), initial)]
    cost = {initial: 0}
    prev = {}
    bound = tuple((min(first[i], last[i])-12, max(first[i], last[i])+12) for i in range(3))
    while queue:
        _, _, state = heapq.heappop(queue)
        here, incoming, up = state
        for shape, m, out_n, out_up in options[(incoming, up)]:
            step = {'shape': shape, 'rotation': m, 'cell': here}
            if here == last and out_n == neg(en) and out_up == eu:
                steps = [step]
                while state != initial:
                    state, entry = prev[state]
                    steps.append(entry)
                steps.reverse()
                # A shortest route must not put two differently oriented pieces in one cell.
                assert len({tuple(x['cell']) for x in steps}) == len(steps)
                return steps
            nxt = add(here, out_n)
            if nxt in blocked or any(not lo <= v <= hi for v, (lo, hi) in zip(nxt, bound)):
                continue
            next_state = (nxt, neg(out_n), out_up)
            new = cost[state] + 1 + (.04 if shape != 'Straight' else 0)
            if new >= cost.get(next_state, math.inf):
                continue
            cost[next_state] = new
            prev[next_state] = state, step
            h = sum(abs(a-b) for a, b in zip(nxt, last))
            heapq.heappush(queue, (new+h, next(serial), next_state))
    raise ValueError('No channel-correct grid route between sockets')


def self_check():
    assert len(ROTATIONS) == 24 and len(SPECS) == len(MACHINES) + 2*len(BARE_PIPES)
    assert len(BARE_PIPES) == 22
    assert len(PLAYABLE) == 27 and len(PIPE_ALIASES) == 28
    assert all(target in PLAYABLE and SPECS[name] == SPECS[target] for name, target in PIPE_ALIASES.items())
    assert all(SPECS[name] == SPECS[base] == (1, 1, 1) for name, base in BARE_PIPES.items())
    assert len({subtype(n) for n in SPECS}) == len(SPECS)
    for name, size in SPECS.items():
        pos = tuple((s % 2 == 0)*1.25 for s in size[:2]) + (size[2]*1.25,)
        assert len(occupied(pos, size)) == math.prod(size), name
    for target, normal, up in (((8.75, 0, 1.25), (-1, 0, 0), (0, 0, 1)),
                               ((5, 0, 7.5), (0, 0, -1), (1, 0, 0)),
                               ((8.75, 2.5, 6.25), (-1, 0, 0), (0, 1, 0))):
        start = {'position': (1.25, 0, 1.25), 'normal': (1, 0, 0), 'hot_axis': (0, 0, 1)}
        end = {'position': target, 'normal': normal, 'hot_axis': up}
        steps = route(start, end, set())
        old = start
        for step in steps:
            at = centre(step['cell'])
            ports = [{'position': add(at, tuple(x*1.25 for x in rotate(step['rotation'], n))),
                      'normal': rotate(step['rotation'], n), 'hot_axis': rotate(step['rotation'], u)}
                     for n, u in PIPE_PORTS[step['shape']]]
            match = [p for p in ports if p['position'] == old['position'] and p['normal'] == neg(old['normal']) and p['hot_axis'] == old['hot_axis']]
            assert len(match) == 1
            old = next(p for p in ports if p is not match[0])
        assert old['position'] == tuple(end['position']) and old['normal'] == neg(normal) and old['hot_axis'] == up
    return {'models': len(SPECS), 'rotations': len(ROTATIONS), 'route_cases': 3}


if __name__ == '__main__':
    print(self_check())


def circuit_type(name):
    """PRIMARY is the reactor-side label for the direct high-pressure loop."""
    return "CO2_HP" if name == "PRIMARY" else name
