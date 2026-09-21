"""Check the authored AE assembly without building a Blender animation preview."""
import bpy
import bmesh
import importlib
import json
import math
from pathlib import Path
from mathutils import Matrix, Vector

ROOT=Path(__file__).resolve().parents[1]
d=json.loads((ROOT/'assets/deployment.json').read_text())
cols=importlib.import_module('space-engineers-utilities.seut_collections')
s=bpy.data.scenes['ArcanePower_ReactorPrototype']
main=cols.get_collections(s)['main'][0]
dummies={o.name[8:]:o for o in main.objects if o.name.startswith('subpart_')}
assert len(dummies)==89,len(dummies)
assert len(d['tiles'])==80
assert len(set(t['model'] for t in d['tiles']))==2
for batch in range(20):
    assert sorted(t['dispenser'] for t in d['tiles'] if t['batch']==batch)==[0,1,2,3]
for f in d['feeders']:
    assert abs(Vector(f['normal']).length-1)<1e-6
    assert abs(f['normal'][2]+math.sqrt(.5))<1e-6

ring_bounds=[]
for ring in d['rings']:
    c=cols.get_collections(bpy.data.scenes['ArcanePower_'+ring['name']])['main'][0]
    vertices=[o.matrix_world@v.co for o in c.objects if o.type=='MESH' for v in o.data.vertices]
    inside=min(v.length for v in vertices)
    outside=max(v.length for v in vertices)
    assert inside >= ring['inner']-1e-5
    assert outside <= ring['sweep_radius']+1e-5
    assert d['center'][2]-outside > -1.225
    assert d['center'][2]+outside < 2.81
    assert outside < 1.82 # Fully raised/parked hoops clear the floor aperture.
    ring_bounds.append((inside,outside))
gaps=[ring_bounds[i+1][0]-ring_bounds[i][1] for i in range(3)]
assert min(gaps)>.10
assert ring_bounds[0][0] > d['field_radius']+.027

for name in d['subpart_scenes']:
    scene=bpy.data.scenes[name]
    assert scene.seut.export_sbc_type=='none'
    for o in cols.get_collections(scene)['main'][0].objects:
        if o.type!='MESH':continue
        bm=bmesh.new();bm.from_mesh(o.data)
        assert all(e.is_manifold for e in bm.edges),o.name
        assert bm.calc_volume(signed=True)>0,o.name
        bm.free()

max_field_radius=0
for tile in d['tiles']:
    scene=bpy.data.scenes[tile['model']]
    rotation=Matrix(tile['rotation'])
    for o in cols.get_collections(scene)['main'][0].objects:
        if o.type!='MESH':continue
        for vertex in o.data.vertices:
            final=rotation@vertex.co+Vector(tile['final'])
            max_field_radius=max(max_field_radius,(final-Vector(d['center'])).length)
            assert (final-Vector(d['center'])).length<.92
    assert tile['staging'][2]>.575+.052+.30
    assert Vector(tile['start']).length<5.5
    for point in ['start','exit','staging','final']:
        assert abs(tile[point][0])<4.95 and abs(tile[point][1])<4.95
        assert -1.2<tile[point][2]<2.81

source=(ROOT/'src/Data/Animation/main.bsl').read_text()
assert source.count(' as Subpart(')==89
assert 'api.stopdelays()' in source and 'api.stoploop("Spin")' in source
assert source.count('.setvisible(true)')==81
assert source.count('.spin(')==4
assert source.count('.rotate(')==84
report={'status':'passed','scope':'Offline authored geometry and generated BSL contract; game motion untested',
        'subparts':89,'rings':4,'leaves':4,'tiles':80,'tile_models':2,'batches':20,'batch_size':4,
        'tile_thickness_m':d['tile_thickness'],'field_outer_radius_m':max_field_radius,
        'ring_sweep_bounds_m':ring_bounds,'minimum_inter_ring_gap_m':min(gaps),
        'floor_clearance_m':d['center'][2]-ring_bounds[-1][1]+1.225,
        'all_orientations_ring_clearance':'Disjoint radial shells, invariant under any rotation about their common centre',
        'limitations':['Flight-path housing checks are bounds only; no exhaustive mesh collision test.',
                       'Does not prove BSL parsing, SE dummy rotations, actual timing, save/load or multiplayer.']}
(ROOT/'validation/deployment.json').write_text(json.dumps(report,indent=2))
print('PASS:89subparts,80solidtiles,20quartets,four45-degreefeeders;all-angle ring gap',min(gaps),'floor clearance',report['floor_clearance_m'])
