"""Check definitions, menu entries, model references and DDS icons for every block."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from PIL import Image
from package_release import resolve
from prepare_lab import ROOT, MOD


def check_catalog():
    manifest = json.loads((ROOT/'validation/release-manifest.json').read_text())
    packaged = {entry['path']: entry for entry in manifest['files']}
    blocks, menu, rows = {}, set(), []
    for path in sorted((MOD/'Data').rglob('*.sbc')):
        tree = ET.parse(path)
        menu.update(n.text for n in tree.findall('.//CategoryClasses/Category/ItemIds/string'))
        for block in tree.findall('CubeBlocks/Definition'):
            ident = block.findtext('Id/TypeId')+'/'+block.findtext('Id/SubtypeId')
            assert ident not in blocks, ('Duplicate block definition', ident)
            blocks[ident] = (path, block)
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
            assert ident in menu, ('Block absent from build menu', ident)
            assert block.findtext('GuiVisible', 'true').lower() == 'true', ident
            assert block.findtext('AvailableInSurvival', 'true').lower() == 'true', ident
            assert len(stages) == 3, ('Missing weld stages', ident)
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
            expected = 'Textures/GUI/Icons/ArcanePower/Thermal/'+ident.split('/')[1]+'.dds'
            assert len(icons) == 1 and icons[0].text == expected, ('Thermal icon is a placeholder', ident)
        rows.append({'id': ident, 'public': public, 'definition': path.relative_to(MOD).as_posix(),
                     'icon': icons[0].text, 'construction_stages': len(stages)})
    assert menu <= set(blocks), ('Dangling menu entries', menu-set(blocks))
    assert 'Reactor/ArcanePower_ReactorPrototype' not in blocks, 'Legacy reactor must remain an authoring asset'
    main = blocks['Reactor/ArcanePower_Thermal_ReactorHousing'][1]
    assert main.findtext('DisplayName') == 'Arcane Reactor'
    assert sum(b.findtext('DisplayName') == 'Arcane Reactor' for _, b in blocks.values()) == 1
    thermal = [row for row in rows if '/ArcanePower_Thermal_' in row['id']]
    assert len(thermal) == 31
    assert len({packaged[row['icon']]['sha256'] for row in thermal}) == len(thermal), 'Thermal icons must be distinct'
    result = {'status': 'passed', 'blocks': len(rows), 'public_blocks': sum(row['public'] for row in rows),
              'hidden_blocks': sum(not row['public'] for row in rows), 'thermal_icons': len(thermal),
              'menu_entries': len(menu), 'all_icons_and_definitions_packaged': True, 'catalog': rows}
    (ROOT/'validation/block-catalog.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    result = check_catalog()
    print(json.dumps({key: value for key, value in result.items() if key != 'catalog'}, indent=2))
