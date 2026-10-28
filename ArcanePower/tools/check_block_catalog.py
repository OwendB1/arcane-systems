"""Check definitions, menu entries, model references and DDS icons for every block."""
import hashlib
import json
import runpy
from pathlib import Path
import xml.etree.ElementTree as ET

from PIL import Image
from package_release import resolve
from prepare_lab import ROOT, MOD


def check_catalog():
    contract=runpy.run_path(str(ROOT/'assets/thermal_model_contract.py'))
    aliases={contract['subtype'](name):contract['subtype'](target) for name,target in contract['PIPE_ALIASES'].items()}
    manifest = json.loads((ROOT/'validation/release-manifest.json').read_text())
    packaged = {entry['path']: entry for entry in manifest['files']}
    blocks, menu, rows = {}, set(), []
    for path in sorted((MOD/'Data').rglob('*.sbc')):
        tree = ET.parse(path)
        menu.update(n.text for n in tree.findall('.//CategoryClasses/Category/ItemIds/string'))
        if tree.find('CategoryClasses') is not None or tree.find('BlockVariantGroups') is not None:
            relative=path.relative_to(MOD).as_posix()
            assert relative in packaged and packaged[relative]['sha256']==hashlib.sha256(path.read_bytes()).hexdigest(), ('Stale or missing menu definitions',relative)
        for block in tree.findall('CubeBlocks/Definition'):
            ident = block.findtext('Id/TypeId')+'/'+block.findtext('Id/SubtypeId')
            assert ident not in blocks, ('Duplicate block definition', ident)
            blocks[ident] = (path, block)
    assert menu <= set(blocks), ('Dangling menu entries', menu-set(blocks))
    variants={};grouped=set()
    for path in sorted((MOD/'Data').rglob('*.sbc')):
        for group in ET.parse(path).findall('BlockVariantGroups/BlockVariantGroup'):
            ident=group.find('Id').get('Subtype')
            assert ident not in variants, ('Duplicate variant group',ident)
            members=[n.get('Type').removeprefix('MyObjectBuilder_')+'/'+n.get('Subtype') for n in group.findall('Blocks/Block')]
            assert members and len(members)==len(set(members)) and set(members)<=set(blocks), ('Invalid variant members',ident)
            assert not grouped.intersection(members), ('Block belongs to multiple scroll groups',ident)
            assert menu.intersection(members)=={members[0]}, ('Only the primary scroll entry belongs in the tab',ident)
            assert group.findtext('DisplayName') and group.findtext('Description'), ('Missing group text',ident)
            icon=group.findtext('Icon')
            assert icon in packaged and packaged[icon]['sha256']==hashlib.sha256((MOD/icon).read_bytes()).hexdigest(), ('Missing group icon',ident)
            grouped.update(members)
            variants[ident]=members
    reachable=menu|grouped
    for ident, (path, block) in blocks.items():
        public = block.findtext('Public', 'true').lower() == 'true'
        assert block.findtext('DisplayName') and block.findtext('BlockPairName'), ident
        assert block.findtext('CubeSize') in ('Large', 'Small'), ident
        assert all(int(block.find('Size').get(axis)) > 0 for axis in ('x', 'y', 'z')), ident
        components = block.findall('Components/Component')
        assert components and all(int(c.get('Count')) > 0 for c in components), ident
        critical = block.find('CriticalComponent')
        assert critical is not None, ('Missing critical component', ident)
        assert 0 <= int(critical.get('Index')) < sum(c.get('Subtype') == critical.get('Subtype') for c in components), ident
        stages = block.findall('BuildProgressModels/Model')
        if public:
            assert ident in reachable, ('Block absent from build menu and scroll groups', ident)
            assert block.findtext('GuiVisible', 'true').lower() == 'true', ident
            assert block.findtext('AvailableInSurvival', 'true').lower() == 'true', ident
            assert len(stages) == 3, ('Missing weld stages', ident)
        else:
            assert ident not in reachable, ('Hidden block exposed in build menu',ident)
        if stages:
            assert [float(s.get('BuildPercentUpperBound')) for s in stages] == [.33, .67, 1], ident
        icons = block.findall('Icon') + block.findall('Icons/Icon')
        assert icons and all(n.text for n in icons), ('Missing block icon', ident)
        references = [path.relative_to(MOD).as_posix(), block.findtext('Model')]
        references += [s.get('File') for s in stages] + [n.text for n in icons]
        for value in references:
            asset = resolve(MOD, value.replace('\\', '/'))
            assert asset is not None, ('Unresolved block asset', ident, value)
            relative = asset.relative_to(MOD).as_posix()
            assert relative in packaged, ('Block asset not packaged', ident, relative)
            assert packaged[relative]['sha256'] == hashlib.sha256(asset.read_bytes()).hexdigest(), ('Stale block asset', ident, relative)
        for icon in icons:
            asset = resolve(MOD, icon.text.replace('\\', '/'))
            with Image.open(asset) as image:
                assert image.format == 'DDS' and image.width == image.height, ('Invalid inventory DDS', ident)
                assert image.width >= 128 and image.width & (image.width-1) == 0, ident
                alpha = image.convert('RGBA').getchannel('A')
                assert alpha.getbbox() is not None and alpha.getextrema()[0] < 255, ('Blank or opaque icon', ident)
        if '/ArcanePower_Thermal_' in ident:
            subtype=ident.split('/')[1]
            expected = 'Textures/GUI/Icons/ArcanePower/Thermal/'+aliases.get(subtype,subtype)+'.dds'
            assert len(icons) == 1 and icons[0].text == expected, ('Thermal icon is a placeholder', ident)
        rows.append({'id': ident, 'public': public, 'definition': path.relative_to(MOD).as_posix(),
                     'icon': icons[0].text, 'construction_stages': len(stages)})
    assert 'Reactor/ArcanePower_ReactorPrototype' not in blocks, 'Legacy reactor must remain an authoring asset'
    main = blocks['Reactor/ArcanePower_Thermal_ReactorHousing'][1]
    assert main.findtext('DisplayName') == 'Arcane Reactor'
    assert sum(b.findtext('DisplayName') == 'Arcane Reactor' for _, b in blocks.values()) == 1
    thermal = [row for row in rows if '/ArcanePower_Thermal_' in row['id']]
    models = json.loads((ROOT/'validation/thermal-models/models.json').read_text())
    playable=contract['PLAYABLE']
    models={name:spec for name,spec in contract['runtime_models'](models).items() if name in playable}
    assert len(thermal) == len(contract['RUNTIME'])
    public_thermal=[row for row in thermal if row['public']]
    assert len(public_thermal) == len(models)
    for alias,target in aliases.items():
        ident='UpgradeModule/'+alias
        assert ident not in menu and ident not in grouped, ('Legacy pipe visible in menu',ident)
        block=blocks[ident][1]
        canonical=blocks['UpgradeModule/'+target][1]
        assert block.findtext('Public')=='false' and block.findtext('GuiVisible')=='false'
        assert block.findtext('AvailableInSurvival')=='true', 'Legacy projections must remain weldable'
        for child in canonical:
            if child.tag in ('Id','BlockPairName','Public','GuiVisible'):continue
            # Appending GuiVisible changes the preceding element's indentation,
            # even though its gameplay value remains identical.
            actual=block.find(child.tag)
            assert actual is not None and ET.canonicalize(ET.tostring(actual),strip_text=True)==ET.canonicalize(ET.tostring(child),strip_text=True), ('Alias differs from shared block',alias,child.tag)
        assert not (MOD/'Textures/GUI/Icons/ArcanePower/Thermal'/(alias+'.dds')).exists(), 'Unused legacy DDS remains in src'
    bare={model['subtype'] for model in models.values() if model.get('variant_of')}
    for key,subtypes in (('BarePipes',bare),('ManifoldPipes',{name.removesuffix('Bare') for name in bare})):
        assert set(variants['ArcanePower_Thermal_'+key])=={'UpgradeModule/'+name for name in subtypes}, ('Wrong pipe scroll group',key)
    expected_groups={
        'Energy_BatteryUpgrades': [('BatteryBlock' if name.startswith('Capacity') else 'UpgradeModule')+'/ArcanePower_Energy'+name+'_Pillar'
                                 for name in ('Capacity','CapacityAdvanced','Transfer','TransferAdvanced','Stabilizer','StabilizerAdvanced')],
        'Power_Controllers': ['UpgradeModule/ArcanePower_'+name for name in ('ContainmentController','AdvancedContainmentController')],
        'Power_Vents': ['Conveyor/ArcanePower_Vent'+name for name in ('Duct','Outlet')],
        'Thermal_Cooling': ['UpgradeModule/ArcanePower_Thermal_'+name for name in ('SpaceRadiator','SpaceRadiatorUpgraded',
                            'RadiatorPanel','RadiatorPanelUpgraded','HullRadiator','HullRadiatorUpgraded','AtmosphericCooler','AtmosphericCoolerUpgraded')],
        'Thermal_PipeRotors': ['MotorAdvancedStator/ArcanePower_Thermal_PipeRotor','MotorAdvancedRotor/ArcanePower_Thermal_PipeRotorHead'],
        'Thermal_Turbines': ['Reactor/ArcanePower_Thermal_BraytonTrain'+suffix for suffix in ('','Upgraded','Mirrored','MirroredUpgraded')],
    }
    for key,members in expected_groups.items():
        assert variants['ArcanePower_'+key]==members, ('Wrong scroll group membership or primary',key)
    assert len(variants)==8 and len(menu)==10, 'Expected eight scroll groups plus the reactor and energy core'
    assert menu-grouped=={'Reactor/ArcanePower_Thermal_ReactorHousing','BatteryBlock/ArcanePower_EnergyCore_Pillar'}
    assert len({packaged[row['icon']]['sha256'] for row in public_thermal}) == len(public_thermal), 'Public thermal icons must be distinct'
    result = {'status': 'passed', 'blocks': len(rows), 'public_blocks': sum(row['public'] for row in rows),
              'hidden_blocks': sum(not row['public'] for row in rows), 'thermal_icons': len(public_thermal),
              'pipe_compatibility_aliases':len(aliases),
              'menu_entries': len(menu), 'scroll_groups':len(variants), 'all_icons_and_definitions_packaged': True, 'catalog': rows}
    (ROOT/'validation/block-catalog.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    result = check_catalog()
    print(json.dumps({key: value for key, value in result.items() if key != 'catalog'}, indent=2))
