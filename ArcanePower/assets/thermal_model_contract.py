"""Large-grid model and duplex-interface contract; no Blender dependency.

Blender: X length, Y width, Z up. SEUT FBX: (-X, Z, Y).
Review lattice: cell centres (2.5*i, 2.5*j, 1.25+2.5*k).
"""
import heapq
import itertools
import math

CELL = 2.5
CIRCUITS = ('PRIMARY', 'CO2_HP', 'CO2_LP')
# Accepted external manifold positions. Internal flow changes must not move these sockets.
TRAIN_PORTS = [
    {'id': 'CO2 leg -1', 'type': 'CO2_HP', 'position': [-2.5, -3.75, 1.25],
     'normal': [0., -1., 0.], 'hot_axis': [0., 0., 1.]},
    {'id': 'CO2 leg 1', 'type': 'CO2_LP', 'position': [-2.5, 3.75, 1.25],
     'normal': [0., 1., 0.], 'hot_axis': [0., 0., 1.]},
]
MACHINES = {
    'Brayton train': (5, 3, 2),
    'Brayton train upgraded': (5, 3, 2),
    'Primary heater': (3, 3, 3),
    'Primary heater upgraded': (3, 3, 3),
    'Recuperator': (3, 2, 3),
    'Recuperator upgraded': (3, 2, 3),
    'Atmospheric cooler': (3, 2, 3),
    'Space radiator': (3, 2, 3),
    'Reactor housing': (5, 5, 3),
}
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
    assert len(ROTATIONS) == 24 and len(SPECS) == 31
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
