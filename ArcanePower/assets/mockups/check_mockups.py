"""Run inside the saved Blender file to check tiers, motion, and chamber clearance."""
import bpy
import json
from mathutils import Vector
from pathlib import Path

report = {'status': 'passed', 'checks': []}
original = bpy.context.window.scene
for name in ['01 Gyroscopic reactors', '02 Column reactors']:
    s = bpy.data.scenes[name]
    bpy.context.window.scene = s
    roots = [o for o in s.objects if 'ring_count' in o]
    assert sorted(o['ring_count'] for o in roots) == [2, 3, 4]
    initial = {}
    for frame in [1, 61, 121, 181]:
        s.frame_set(frame)
        s.view_layers[0].update()
        for root in roots:
            rotors = [o for o in root.children_recursive if '/ animated rotor' in o.name]
            assert len(rotors) == root['ring_count']
            assert len([o for o in root.children_recursive if o.name.startswith('Containment controller')]) == root['ring_count']
            for rotor in rotors:
                assert rotor.animation_data and rotor.animation_data.action
                if frame == 1:
                    initial[rotor.name] = rotor.matrix_world.copy()
                else:
                    assert rotor.matrix_world != initial[rotor.name], rotor.name + ' is not moving'
                for mesh in rotor.children:
                    if mesh.type != 'MESH':
                        continue
                    to_local = root.matrix_world.inverted() @ mesh.matrix_world
                    zs = [(to_local @ v.co).z for v in mesh.data.vertices]
                    assert min(zs) > 2.27, (mesh.name, frame, min(zs), 'pedestal collision')
                    assert max(zs) < 8.0, (mesh.name, frame, max(zs), 'upper cap collision')
    s.frame_set(1)
    report['checks'].append(name + ': 2/3/4 rings/controllers, animated transforms, vertical clearance at 4 poses')

s = bpy.data.scenes['04 Vent states']
bpy.context.window.scene = s
plume = next(o for o in s.objects if o.name.startswith('Discharge preview'))
for frame, expected in [(1, .001), (115, 1), (240, .001)]:
    s.frame_set(frame)
    assert abs(plume.scale.x - expected) < .0001
s.frame_set(115)
report['checks'].append('Vent sequence: discharge hidden/open/hidden at start, flow, end')
small = next(o for o in bpy.data.scenes['05 Scale study'].objects if 'ring_count' in o and o.scale.x < .7)
assert not any(o.name.startswith('Scale reference') for o in small.children)
report['checks'].append('Compact scale study does not shrink the human reference')
bpy.context.window.scene = original
report['limitations'] = 'Geometric pose checks only; no exhaustive mesh collision, game export, particle, or runtime verification.'
Path(__file__).with_name('validation.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
