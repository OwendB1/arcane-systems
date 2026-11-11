"""Verify reversed pipe channels, routing, generated runtime and menu delivery."""
import json
import math
from pathlib import Path
import runpy
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def check():
    c = runpy.run_path(str(ROOT/'assets/thermal_model_contract.py'))
    c['self_check']()
    models = json.loads((ROOT/'validation/thermal-models/models.json').read_text())
    flows = json.loads((ROOT/'assets/thermal-flow-paths.json').read_text())['models']
    blocks = {b.findtext('Id/SubtypeId'): b for b in ET.parse(
        ROOT/'src/Data/CubeBlocks/ArcanePower_Thermal.sbc').findall('CubeBlocks/Definition')}
    groups = ET.parse(ROOT/'src/Data/CubeBlocks/ArcanePower_ThermalVariants.sbc')
    members = [b.get('Subtype') for b in groups.findall('.//Blocks/Block')]
    checked = 0
    for name, base in c['REVERSED_PIPES'].items():
        for suffix in ('', ' bare'):
            current = models[name+suffix]
            ident = current['subtype']
            expected = c['PIPE_PORTS'][name.split(' / ')[1]]
            assert current['ports'] == models[name]['ports']
            for port, (normal, up) in zip(current['ports'], expected):
                assert port['normal'] == list(normal) and port['hot_axis'] == list(up)
                assert port['position'] == [v*1.25 for v in normal]
            paths = flows[ident]
            assert len(paths) == 2 and {p['hot'] for p in paths} == {False, True}
            assert sorted(len(p['points']) for p in paths) == sorted(len(p['points']) for p in flows[c['subtype'](base)])
            lengths = {}
            for path in paths:
                lengths[path['hot']] = sum(math.dist(a, b) for a, b in zip(path['points'], path['points'][1:]))
                for rotation in c['ROTATIONS']:
                    endpoints = [c['rotate'](rotation, path['points'][i]) for i in (0, -1)]
                    for port in current['ports']:
                        sign = 1 if path['hot'] else -1
                        socket = c['rotate'](rotation, [a+sign*.46*b for a, b in zip(port['position'], port['hot_axis'])])
                        assert min(math.dist(socket, endpoint) for endpoint in endpoints) < .057, (name, 'Flow misses socket')
            if 'Riser' in name:
                assert lengths[True] > lengths[False]+1, 'Hot channel must use the outer arc'
            else:
                assert abs(lengths[True]-lengths[False]) < 1e-5
                for path in paths:
                    original = next(p for p in flows[c['subtype'](base)] if p['hot'] == path['hot'])
                    reflected = [[x, -y, z] for x, y, z in original['points']]
                    assert path['points'] in (reflected, reflected[::-1]), 'Elbow must turn the opposite way'
            block = blocks[ident]
            assert block.findtext('Public') == 'true' and members.count(ident) == 1
            assert block.findtext('IsAirTight') == str(not suffix).lower()
            for value in [block.findtext('Model'), block.findtext('Icon')]+[
                    s.get('File') for s in block.findall('BuildProgressModels/Model')]:
                assert (ROOT/'src'/value).is_file(), value
            checked += 1
    # An outer-hot bend must be routable directly, without an extra roll adapter.
    start = dict(position=(-1.25, 0, 1.25), normal=(1, 0, 0), hot_axis=(0, 0, -1))
    end = dict(position=(0, 0, 2.5), normal=(0, 0, -1), hot_axis=(1, 0, 0))
    route = c['route'](start, end, set())
    assert len(route) == 1 and route[0]['shape'] == 'Riser reversed'
    generator = runpy.run_path(str(ROOT/'tools/build_thermal_runtime_contract.py'))
    assert generator['generate']() == generator['TARGET'].read_text()
    assert generator['generate_flow']() == generator['TARGET'].with_name('ThermalFlowModels.cs').read_text()
    return dict(status='passed', variants=checked, orientations=24, direct_outer_hot_route=True)


if __name__ == '__main__':
    print(json.dumps(check()))
