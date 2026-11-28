"""Make the vent family's base grey metal accept block paint and skins.

Run in assets/arcane-power-prototype.blend. Only the dominant Metal_Dull surfaces
switch to the native PaintedMetal_Colorable material (the reactor's paintable
finish); darker trim, hazard yellow, emissives and collision keep their own
materials. Covers main, LOD and construction-stage meshes.

The reactor roof reuses ArcanePower_VentHatch, which stays unpainted. The outlet
gets its own copy, ArcanePower_VentOutletHatch, and its four leaf dummies link to
that copy. Then export with assets/export_energy_main.py and
assets/export_construction_stages.py.
"""
import importlib
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
COLS = importlib.import_module('space-engineers-utilities.seut_collections')
REACTOR_HATCH, OUTLET_HATCH = 'ArcanePower_VentHatch', 'ArcanePower_VentOutletHatch'
SCENES = ('ArcanePower_VentDuct', 'ArcanePower_VentOutlet', OUTLET_HATCH)
SOURCE, TARGET = 'Metal_Dull', 'PaintedMetal_Colorable'


def rendered(scene):
    # Collision bodies carry no rendered material.
    return [obj for obj in scene.objects if obj.type == 'MESH'
            and not any(c.name.startswith('Collision') for c in obj.users_collection)]


def outlet_hatch():
    """Copy the reactor hatch scene once; the copy owns its meshes."""
    if OUTLET_HATCH in bpy.data.scenes:
        return bpy.data.scenes[OUTLET_HATCH]
    source = bpy.data.scenes[REACTOR_HATCH]
    before = set(bpy.data.scenes)
    bpy.context.window.scene = source
    bpy.ops.scene.new(type='FULL_COPY')
    scene = next(s for s in bpy.data.scenes if s not in before)
    scene.name = OUTLET_HATCH
    scene.seut.subtypeId = OUTLET_HATCH
    COLS.rename_collections(scene)
    cols = COLS.get_collections(scene)
    main = cols['main'][0]
    for col in cols['lod'] or []:
        assert col.seut.ref_col is main, ('LOD still references the reactor hatch', col.name)
    originals = {obj.data for obj in source.objects if obj.type == 'MESH'}
    for obj in scene.objects:
        if obj.type == 'MESH' and obj.data in originals:
            obj.data = obj.data.copy()
        # Keep the authored object names; only the Blender-unique suffix differs.
    return scene


def main(save=True):
    assert Path(bpy.data.filepath).name == 'arcane-power-prototype.blend', 'Run in the prototype production blend'
    checkpoint = ROOT/'assets/arcane-power-before-colorable-vents.blend'
    if save and not checkpoint.exists():
        bpy.ops.wm.save_as_mainfile(filepath=str(checkpoint), copy=True)
    source = bpy.data.materials[SOURCE]
    target = bpy.data.materials[TARGET]
    assert source.library and target.library, 'Expected linked native SEUT materials'
    hatch = outlet_hatch()
    outlet = bpy.data.scenes['ArcanePower_VentOutlet']
    leaves = [obj for obj in outlet.objects if obj.name.startswith('subpart_OutletHatch')]
    assert len(leaves) == 4
    for leaf in leaves:
        leaf['file'] = OUTLET_HATCH
        leaf.seut.linkedScene = hatch
    reactor_meshes = {obj.data for obj in rendered(bpy.data.scenes[REACTOR_HATCH])}
    meshes = set()
    for name in SCENES:
        for obj in rendered(bpy.data.scenes[name]):
            for slot in obj.material_slots:
                if slot.material != source:
                    continue
                assert slot.link != 'DATA' or obj.data not in reactor_meshes, ('Shared with reactor hatch', obj.name)
                if slot.link == 'DATA':
                    meshes.add(obj.data)
                slot.material = target
    remaining = [(scene, obj.name) for scene in SCENES for obj in rendered(bpy.data.scenes[scene])
                 if any(slot.material == source for slot in obj.material_slots)]
    assert not remaining, remaining
    painted = [obj.name for obj in rendered(bpy.data.scenes[REACTOR_HATCH])
               if any(slot.material == target for slot in obj.material_slots)]
    assert not painted, ('Reactor hatch must stay unpainted', painted)
    if save:
        bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/arcane-power-prototype.blend'))
    print('Colorable vent metal:', len(meshes), 'meshes; outlet hatch:', hatch.name)
    return len(meshes)


if __name__ == '__main__':
    main()
