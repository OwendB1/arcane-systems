"""Validate the authored asteroid ores, dense concentrates and cumulative recipes."""
from pathlib import Path
from decimal import Decimal
import xml.etree.ElementTree as ET
import shutil
import tempfile

import prepare_lab

ROOT = Path(__file__).resolve().parents[1]
GAME = Path.home() / '.local/share/Steam/steamapps/common/SpaceEngineers'
item_definitions = ET.parse(ROOT / 'src/Data/PhysicalItems.sbc')
items = item_definitions.findall('PhysicalItems/PhysicalItem') + item_definitions.findall('Components/Component')
recipes = ET.parse(ROOT / 'src/Data/Blueprints.sbc').findall('Blueprints/Blueprint')
materials = ET.parse(ROOT / 'src/Data/VoxelMaterials_Arcane.sbc').findall('VoxelMaterials/VoxelMaterial')
weights = ET.parse(ROOT / 'src/Data/VoxelMaterials_ArcaneRarity.sbc').findall('VoxelMaterials/VoxelMaterial')


def keyed(nodes):
    result = {n.findtext('Id/SubtypeId'): n for n in nodes}
    assert len(result) == len(nodes), 'duplicate subtype'
    return result


items = keyed(items)
recipes = keyed(recipes)
materials = keyed(materials)
weights = keyed(weights)
classes = {n.get('BlueprintSubtypeId'): n.get('Class') for n in
           ET.parse(ROOT / 'src/Data/Blueprints.sbc').findall('BlueprintClassEntries/Entry')}
assert len(items) == 11 and len(recipes) == 7 and len(materials) == 3
canister = items['ArcaneAetherCanister']
assert canister.findtext('Id/TypeId') == 'Component'
assert Decimal(canister.findtext('Volume')) == 24
empty_inputs = {(n.get('TypeId'), n.get('SubtypeId')): Decimal(n.get('Amount')) for n in
                recipes['ArcaneAetherCanister'].findall('Prerequisites/Item')}
assert empty_inputs == {('Ingot', 'Iron'): 100, ('Ingot', 'Cobalt'): 40, ('Ingot', 'Silver'): 10,
                        ('Ingot', 'Platinum'): 5, ('Component', 'Superconductor'): 10,
                        ('Component', 'Computer'): 4, ('Component', 'MetalGrid'): 4}
assert recipes['ArcaneAetherCanister'].find('Result').attrib == {'TypeId': 'Component', 'SubtypeId': 'ArcaneAetherCanister', 'Amount': '1'}
assert classes['ArcaneAetherCanister'] == 'Components'
native = keyed(ET.parse(GAME / 'Content/Data/VoxelMaterials_asteroids.sbc').findall('VoxelMaterials/VoxelMaterial'))

# The native generator keeps at least one copy, then appends weight-1 copies.
# Uniform scaling preserves every pairwise vanilla weight ratio after its
# one-material-per-ore filtering; all custom weights are below any vanilla ore.
for subtype, node in weights.items():
    original = native[subtype]
    expected = 100 * max(1, int(original.findtext('AsteroidGeneratorSpawnProbabilityMultiplier', '1')))
    assert int(node.findtext('AsteroidGeneratorSpawnProbabilityMultiplier')) == expected
    for tree in (node, original):
        value = tree.find('AsteroidGeneratorSpawnProbabilityMultiplier')
        if value is not None:
            tree.remove(value)
        for child in tree.iter():
            child.text = (child.text or '').strip()
            child.tail = ''
    assert ET.tostring(node) == ET.tostring(original), 'vanilla properties changed: ' + subtype
assert weights

previous_fuel = None
previous_weight, previous_mining, previous_yield, previous_volume = float('inf'), float('inf'), float('inf'), float('inf')
for name, ore, fuel, concentrate, refining, preparing, expected_yield in (
        ('Aether', 'ArcaneOre', 'ArcaneFuelI', 'ArcaneAetherConcentrate', 'ArcaneAetherOreToConcentrate', 'ArcaneAetherFuel', Decimal('.001')),
        ('Helion', 'ArcaneHelionOre', 'ArcaneFuelII', 'ArcaneHelionConcentrate', 'ArcaneHelionOreToConcentrate', 'ArcaneHelionFuel', Decimal('.0001')),
        ('Empyrean', 'ArcaneEmpyreanOre', 'ArcaneFuelIII', 'ArcaneEmpyreanConcentrate', 'ArcaneEmpyreanOreToConcentrate', 'ArcaneEmpyreanFuel', Decimal('.00001'))):
    material = materials['Arcane' + name + 'Deposit']
    assert material.findtext('MinedOre') == ore
    assert material.findtext('IsRare') == material.findtext('CanBeHarvested') == material.findtext('SpawnsInAsteroids') == 'true'
    assert material.findtext('SpawnsFromMeteorites') == 'false'
    assert int(material.findtext('MinVersion')) == 3
    weight = int(material.findtext('AsteroidGeneratorSpawnProbabilityMultiplier'))
    mining = float(material.findtext('MinedOreRatio'))
    assert (weight,mining)=={'Aether':(20,.2),'Helion':(2,.03),'Empyrean':(1,.01)}[name]
    assert 0 < weight < previous_weight and weight < 100
    assert 0 < mining < previous_mining and mining < .3  # Uranium's mined-ore ratio.
    blueprint = recipes[refining]
    ingredients = blueprint.findall('Prerequisites/Item')
    assert len(ingredients) == 1 and ingredients[0].get('SubtypeId') == ore and ingredients[0].get('TypeId') == 'Ore'
    result = blueprint.find('Result')
    yield_ratio = Decimal(result.get('Amount')) / Decimal(ingredients[0].get('Amount'))
    assert yield_ratio == expected_yield and yield_ratio < previous_yield and yield_ratio < Decimal('.005')  # Platinum.
    assert result.get('SubtypeId') == concentrate and result.get('TypeId') == 'Ingot'
    assert Decimal(result.get('Amount')) >= Decimal('.000001')  # Fixed-point amount precision.
    assert classes[refining] == 'Ingots'
    assert classes[preparing] == 'Components'
    preparation = recipes[preparing]
    required = {item.get('SubtypeId'): Decimal(item.get('Amount')) for item in preparation.findall('Prerequisites/Item')}
    assert required == {concentrate: Decimal(10), previous_fuel or 'ArcaneAetherCanister': Decimal(1)}
    assert Decimal(preparation.findtext('BaseProductionTimeInSeconds')) == (100, 300, 900)[('Aether', 'Helion', 'Empyrean').index(name)]
    assert preparation.findtext('IgnoreEfficiencyMultiplier') == 'true', 'whole canister must survive assembler efficiency'
    assert preparation.find('Result').get('SubtypeId') == fuel
    assert preparation.find('Result').get('Amount') == '1'
    volume = Decimal(items[concentrate].findtext('Volume'))
    assert volume < previous_volume
    node = items[concentrate]
    assert node.findtext('Id/TypeId') == 'Ingot' and node.findtext('Mass') == '1'
    assert Decimal(node.findtext('Volume')) == volume
    for subtype in (concentrate, fuel):
        node = items[subtype]
        assert node.findtext('Id/TypeId') == 'Ingot'
        # Litres in SBC become m^3 in the engine. Stay at/above its volume quantum.
        assert volume / 1000 >= Decimal('.000001')
        assert Decimal(items[ore].findtext('Volume')) / volume >= 37
        assert name in node.findtext('DisplayName')
    rating = {'Aether': '2.5 GW', 'Helion': '25 GW', 'Empyrean': '250 GW'}[name]
    assert items[fuel].findtext('DisplayName') == name + ' Fuel Canister — ' + rating
    assert 'Rated reactor heat: ' + rating + '.' in items[fuel].findtext('Description')
    assert Decimal(items[fuel].findtext('Volume')) == 24
    assert 'Ideal full-load endurance: '+('2.5' if name=='Aether' else '10')+' minutes' in items[fuel].findtext('Description')
    assert tuple(Decimal(items[fuel].findtext('Size/' + axis)) for axis in 'XYZ') == (Decimal('.261'), Decimal('.438'), Decimal('.261'))
    assert Decimal(items[fuel].findtext('Mass')) == Decimal(canister.findtext('Mass')) + 10 * (1 + ('Aether', 'Helion', 'Empyrean').index(name))
    previous_fuel = fuel
    previous_weight, previous_mining, previous_yield, previous_volume = weight, mining, yield_ratio, volume
    print(f'{name}: weight {weight} vs vanilla >=100; mined ratio {mining:g}; refining {yield_ratio * 100}% ; {volume} L/kg')

# Every input/result resolves to a custom or native definition of the right type.
native_items = {(n.findtext('Id/TypeId'), n.findtext('Id/SubtypeId')) for path, query in
                [('PhysicalItems.sbc', 'PhysicalItems/PhysicalItem'), ('Components.sbc', 'Components/Component')]
                for n in ET.parse(GAME / 'Content/Data' / path).findall(query)}
for blueprint in recipes.values():
    for item in blueprint.findall('Prerequisites/Item') + [blueprint.find('Result')]:
        if item.get('SubtypeId') in items:
            assert items[item.get('SubtypeId')].findtext('Id/TypeId') == item.get('TypeId')
        else:
            assert (item.get('TypeId'), item.get('SubtypeId')) in native_items
print('PASS: rare ores, dense concentrates, exotic empty canister and 10-unit cumulative filling recipes')

# The authoring generator must preserve the shipped economy on regeneration.
with tempfile.TemporaryDirectory(prefix='arcane-fuel-recipes-') as directory:
    original_mod = prepare_lab.MOD
    prepare_lab.MOD = Path(directory)
    try:
        (prepare_lab.MOD / 'Data').mkdir()
        for name in ('PhysicalItems.sbc', 'ContainmentTiles.sbc'):
            shutil.copy2(original_mod / 'Data' / name, prepare_lab.MOD / 'Data' / name)
        prepare_lab.fuel_definitions()
        prepare_lab.containment_tiles()
        for name in ('PhysicalItems.sbc', 'Blueprints.sbc', 'ContainmentTiles.sbc', 'ContainmentTileBlueprints.sbc',
                     'VoxelMaterials_Arcane.sbc', 'VoxelMaterials_ArcaneRarity.sbc'):
            assert (prepare_lab.MOD / 'Data' / name).read_bytes() == (original_mod / 'Data' / name).read_bytes(), name
    finally:
        prepare_lab.MOD = original_mod
print('PASS: regeneration preserves canister, filling/upgrade recipes and exotic tile grades')

residuum = items['ArcaneAetherResiduum']
assert residuum.findtext('Id/TypeId') == 'Component'
assert Decimal(residuum.findtext('Mass')) == 1 and Decimal(residuum.findtext('Volume')) == Decimal('.001')
assert not any(b.find('Result').get('SubtypeId') == 'ArcaneAetherResiduum' for b in recipes.values())
thermal = ET.parse(ROOT/'src/Data/CubeBlocks/ArcanePower_Thermal.sbc').getroot()
upgrades = 0
for block in thermal.findall('CubeBlocks/Definition'):
    name = block.findtext('Id/SubtypeId')
    required = block.findall("Components/Component[@Subtype='ArcaneAetherResiduum']")
    if name.endswith('Upgraded'):
        upgrades += 1
        assert len(required)==1 and int(required[0].get('Count'))==(20 if 'BraytonTrain' in name else 10), name
        assert block.find('CriticalComponent').attrib=={'Subtype':'ArcaneAetherResiduum','Index':'0'}, name
    else:assert not required, name
assert upgrades==5
# Repeated catalog regeneration cannot duplicate or remove the progression gate.
import prepare_thermal_release as release
with tempfile.TemporaryDirectory(prefix='arcane-thermal-catalog-') as directory:
    original=release.MOD;release.MOD=Path(directory)
    try:
        release.write_catalog(thermal)
        release.write_catalog(ET.parse(release.MOD/'Data/CubeBlocks/ArcanePower_Thermal.sbc').getroot())
        assert (release.MOD/'Data/CubeBlocks/ArcanePower_Thermal.sbc').read_bytes()==(original/'Data/CubeBlocks/ArcanePower_Thermal.sbc').read_bytes()
        for name in ('ThermalCategories.sbc','CubeBlocks/ArcanePower_ThermalVariants.sbc'):
            assert (release.MOD/'Data'/name).read_bytes()==(original/'Data'/name).read_bytes(), name
    finally:release.MOD=original
print('PASS: uncraftable Residuum, five material-gated upgrades, idempotent block catalog')
