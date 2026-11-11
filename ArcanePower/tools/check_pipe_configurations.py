"""Check routed duplex geometry, orientation coverage and delivered scroll groups."""
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
    groups = {g.find('Id').get('Subtype'): [b.get('Subtype') for b in g.findall('Blocks/Block')]
              for g in ET.parse(ROOT/'src/Data/CubeBlocks/ArcanePower_ThermalVariants.sbc').findall('.//BlockVariantGroup')}

    def signature(shape):
        return min(tuple(sorted((c['rotate'](r, n), c['rotate'](r, h)) for n, h in c['PIPE_PORTS'][shape]))
                   for r in c['ROTATIONS'])

    straight = ('Straight', 'Roll adapter', 'Roll adapter reversed', 'Crossover')
    assert len({signature(s) for s in straight}) == 4, 'All four straight roll states must be distinct'
    bends = ('Elbow', 'Riser', 'Riser reversed') + tuple(s for s in c['ROUTED_PIPES'] if s.startswith('Elbow'))
    assert len({signature(s) for s in bends}) == 7, 'Rolled bends must add four distinct orientations'
    measurements = {}
    for shape in c['ROUTED_PIPES']:
        paths = c['routed_paths'](shape)
        # Fixed full-size outer walls need positive clearance at every sample.
        gap = min(math.dist(a, b) for a in paths[0] for b in paths[1]) - 2*.355
        assert gap > .06, (shape, 'channels too close', gap)
        radii = []
        for path in paths:
            for a, b, d in zip(path, path[1:], path[2:]):
                u = [b[i]-a[i] for i in range(3)]; v = [d[i]-b[i] for i in range(3)]
                cross = [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]]
                area2 = math.sqrt(sum(x*x for x in cross))
                if area2 > 1e-12:
                    radii.append(math.dist(a,b)*math.dist(b,d)*math.dist(a,d)/(2*area2))
        radius = min(radii)
        assert radius > .39, (shape, 'inner wall folds', radius)
        measurements[shape] = {'channel_clearance_m': round(gap, 4), 'minimum_bend_radius_m': round(radius, 4)}
        for suffix in ('', ' bare'):
            name = 'PRIMARY / '+shape+suffix
            model = models[name]; ident = c['subtype'](name)
            expected = c['PIPE_PORTS'][shape]
            assert len(model['ports']) == 2
            for port, (normal, hot) in zip(model['ports'], expected):
                assert port['normal'] == list(normal) and port['hot_axis'] == list(hot)
                assert port['position'] == [1.25*v for v in normal]
            flow = flows[ident]
            assert len(flow) == 2 and {p['hot'] for p in flow} == {False, True}
            for path in flow:
                sign = 1 if path['hot'] else -1
                for rotation in c['ROTATIONS']:
                    ends = [c['rotate'](rotation, path['points'][i]) for i in (0,-1)]
                    for port in model['ports']:
                        mouth = c['rotate'](rotation, [p+sign*.46*h-.056*n for p,h,n in
                            zip(port['position'],port['hot_axis'],port['normal'])])
                        assert min(math.dist(mouth,end) for end in ends) < 1e-5, (name, 'wrong H/C endpoint')
            group = 'ArcanePower_Thermal_'+('BarePipes' if suffix else 'ManifoldPipes')
            assert groups[group].count(ident) == 1 and sum(g.count(ident) for g in groups.values()) == 1
            block = blocks[ident]
            assert block.findtext('Public') == 'true'
            assert block.findtext('IsAirTight') == str(not suffix).lower()
            assert all(block.find('Size').get(axis) == '1' for axis in ('x','y','z'))
            for value in [block.findtext('Model'),block.findtext('Icon')]+[
                    m.get('File') for m in block.findall('BuildProgressModels/Model')]:
                assert (ROOT/'src'/value).is_file(), value
    generator = runpy.run_path(str(ROOT/'tools/build_thermal_runtime_contract.py'))
    assert generator['generate']() == generator['TARGET'].read_text()
    assert generator['generate_flow']() == generator['TARGET'].with_name('ThermalFlowModels.cs').read_text()
    return {'status':'passed','new_variants':12,'orientations':24,'straight_roll_states':4,
            'distinct_bend_states':7,'geometry':measurements}


if __name__ == '__main__':
    print(json.dumps(check(), indent=2))
