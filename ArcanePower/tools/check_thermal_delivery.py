"""Cross-check delivered block definitions against authored and native contracts."""
import hashlib
import json
import runpy
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile
from PIL import Image, ImageStat
from check_block_catalog import check_catalog
from check_reactor_roof import check as check_roof

ROOT=Path(__file__).resolve().parents[1]
MOD=ROOT/'src'


def main():
    check_roof()
    models=json.loads((ROOT/'validation/thermal-models/models.json').read_text())
    contract=runpy.run_path(str(ROOT/'assets/thermal_model_contract.py'))
    playable=contract['PLAYABLE']
    authored={name:spec for name,spec in models.items() if name in playable}
    models={name:spec for name,spec in contract['runtime_models'](models).items() if name in playable}
    report=json.loads((ROOT/'validation/thermal-models/native-export.json').read_text())
    tree=ET.parse(MOD/'Data/CubeBlocks/ArcanePower_Thermal.sbc')
    blocks={d.findtext('Id/SubtypeId'):d for d in tree.findall('CubeBlocks/Definition')}
    motion=json.loads((ROOT/'validation/thermal-models/native-motion.json').read_text())
    assert motion['status']=='passed' and motion['moving_parts']==34 and motion['failed_checks']==0,'Native moving meshes do not match authoring motion'
    assert motion['contract_sha256']==hashlib.sha256((ROOT/'assets/thermal-native-motion-contract.json').read_bytes()).hexdigest(),'Native motion contract changed after validation'
    assert motion['runtime_pose_sha256']==hashlib.sha256(b''.join((MOD/'Data/Scripts/ArcanePower'/name).read_bytes()
        for name in ('ThermalManifolds.cs','ThermalRotors.cs','ThermalRadiators.cs','ThermalModels.cs','ThermalPlant.cs'))).hexdigest(),'Runtime poses changed after native motion validation'
    for model in motion['models']:
        assert model['path']==blocks[model['subtype']].findtext('Model')
        assert model['sha256']==hashlib.sha256((MOD/model['path']).read_bytes()).hexdigest(),'Native moving model changed after validation'
    for path,digest in motion['native_mesh_sha256'].items():
        assert digest==hashlib.sha256((MOD/path).read_bytes()).hexdigest(),'Native moving mesh changed after motion validation'
    isolation=json.loads((ROOT/'validation/thermal-models/isolation.json').read_text())
    assert isolation['status']=='passed' and isolation['checks']>0, 'Valve native motion is unverified'
    assert isolation['contract_sha256']==hashlib.sha256((ROOT/'assets/thermal-isolation.json').read_bytes()).hexdigest()
    assert isolation['runtime_pose_sha256']==hashlib.sha256((MOD/'Data/Scripts/ArcanePower/ThermalIsolation.cs').read_bytes()).hexdigest()
    for path,digest in isolation['native_mesh_sha256'].items():
        assert digest==hashlib.sha256((MOD/path).read_bytes()).hexdigest(), 'Valve mesh changed after native validation'
    assert set(blocks)=={contract['subtype'](name) for name in contract['RUNTIME']}
    assert report['status']=='passed' and report['blocks']==len(authored) and report['construction_models']==3*len(authored)
    highlights=report['inventory_highlights']
    assert set(highlights)=={'detector_conveyor_0','detector_conveyor_2','detector_conveyor_top','detector_conveyor_bottom'}
    assert len(highlights['detector_conveyor_top'])==4 and all(len(highlights[key])==1 for key in highlights if key!='detector_conveyor_top')
    panels=report['control_panel_highlights']
    assert set(panels)=={'detector_terminal_control','detector_terminal_control_opposite'}
    for suffix,label in (('', 'control terminal_section'),('_opposite','control opposite terminal_section')):
        panel=panels['detector_terminal_control'+suffix]
        assert len(panel)==1 and label in panel[0], 'Missing dedicated reactor control-panel highlight'
    category=ET.parse(MOD/'Data/ThermalCategories.sbc')
    items={n.text for n in category.findall('.//ItemIds/string')}
    reachable=set(items)
    for group in ET.parse(MOD/'Data/CubeBlocks/ArcanePower_ThermalVariants.sbc').findall('BlockVariantGroups/BlockVariantGroup'):
        members=[n.get('Type').removeprefix('MyObjectBuilder_')+'/'+n.get('Subtype') for n in group.findall('Blocks/Block')]
        assert items.intersection(members)=={members[0]}, 'Scroll group must have exactly one menu entry'
        reachable.update(members)
    assert len(items)==6 and len(reachable)==len(playable), 'Expected reactor plus five thermal scroll groups'
    files=[]
    for name,spec in models.items():
        d=blocks[spec['subtype']]
        expected=contract['PIPE_ROTORS'].get(name, 'Reactor' if name=='Reactor housing' or name.startswith('Brayton train') else 'UpgradeModule')
        assert d.findtext('Id/TypeId')==expected,(name,'Wrong runtime owner')
        assert expected+'/'+spec['subtype'] in reachable
        assert [int(d.find('Size').get(k)) for k in ('x','y','z')]==spec['cells_se']
        assert d.findtext('Public')=='true' and d.findtext('AvailableInSurvival')=='true'
        assert d.findtext('CubeSize')=='Large'
        if expected=='Reactor':assert len(d.find('FuelInfos'))==0,'Native fuel must not bypass paid heat'
        if expected=='UpgradeModule':assert len(d.find('Upgrades'))==0,'Thermal pipes must not grant containment upgrades'
        assert all(int(c.get('Count'))>0 for c in d.findall('Components/Component'))
        critical=d.find('CriticalComponent').get('Subtype')
        assert critical in {c.get('Subtype') for c in d.findall('Components/Component')}
        stages=d.findall('BuildProgressModels/Model')
        assert len(stages)==3
        assert [float(s.get('BuildPercentUpperBound')) for s in stages]==[.33,.67,1]
        if name in contract['COOLER_UPGRADES']:
            base=blocks[models[contract['COOLER_UPGRADES'][name]]['subtype']]
            assert d.findtext('Model')==base.findtext('Model'), 'Tier variant must reuse validated geometry'
            assert [s.attrib for s in stages]==[s.attrib for s in base.findall('BuildProgressModels/Model')]
        paths=[d.findtext('Model')]+[s.get('File') for s in stages]
        for value in paths:
            path=MOD/value
            assert path.is_file(),value
            entry=report['native_models'][path.stem]
            assert hashlib.sha256(path.read_bytes()).hexdigest()==entry['sha256'],('Changed validated asset',value)
            if path==MOD/paths[0]:
                assert len(entry['lods'])==2 or entry['triangles']<1000,('Missing distance meshes',name)
            files.append(value)
    # The package must contain the exact inspected model closure, not just sources.
    manifest=json.loads((ROOT/'validation/release-manifest.json').read_text())
    packaged={r['path']:r for r in manifest['files']}
    model_folder=MOD/'Models/Cubes/large'
    actual_models={p.relative_to(MOD).as_posix() for p in model_folder.rglob('*') if p.is_file()}
    assert actual_models=={p for p in packaged if p.startswith('Models/Cubes/large/')},'Unused or missing loadable model exports'
    assert set(files)<=set(packaged),'Release omitted a thermal main/weld model'
    assert set(isolation['native_mesh_sha256'])<=set(packaged),'Release omitted animated isolation valves'
    for path in files:
        assert packaged[path]['sha256']==hashlib.sha256((MOD/path).read_bytes()).hexdigest()
    # A model-only manifest check misses omitted scripts and stale ZIP contents.
    scripts={p.relative_to(MOD).as_posix() for p in MOD.glob('Data/**/*.cs')}
    definitions={p.relative_to(MOD).as_posix() for p in MOD.glob('Data/**/*.sbc')}
    assert scripts|definitions <= set(packaged),'Release omitted runtime code or definitions'
    archive=ROOT/'.cache/release'/manifest['archive']
    assert archive.stat().st_size==manifest['bytes']
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==manifest['sha256'],'Release ZIP hash mismatch'
    with zipfile.ZipFile(archive) as package:
        names=package.namelist()
        assert len(names)==len(set(names)) and set(names)==set(packaged),'ZIP and manifest entries differ'
        for path,entry in packaged.items():
            data=package.read(path)  # Also verifies the member CRC.
            digest=hashlib.sha256(data).hexdigest()
            assert len(data)==entry['bytes'] and digest==entry['sha256'],('Changed ZIP entry',path)
            assert (MOD/path).is_file() and hashlib.sha256((MOD/path).read_bytes()).hexdigest()==digest,('Stale ZIP entry',path)
    catalog=check_catalog()
    glass=ET.parse(MOD/'Data/TransparentMaterials.sbc')
    for name in ('ArcanePower_ClearChamber','ArcanePower_CoolantGlass','ArcanePower_InternalCoolantGlass'):
        definition=next(d for d in glass.findall('TransparentMaterials/TransparentMaterial')
                        if d.findtext('Id/SubtypeId')==name)
        # Zero CA removes dirt, so ColorAdd supplies the visible body/opacity.
        # Color.W has no effect here. Keep the tint premultiplied and avoid
        # the old high-reflection, almost invisible pressure-wall finish.
        opacity=float(definition.findtext('ColorAdd/W'))
        assert .20<=opacity<=.45,('Glass body too transparent or opaque',name)
        assert all(0<float(definition.findtext('ColorAdd/'+axis))<=opacity for axis in 'XYZ')
        assert 0<float(definition.findtext('Reflectivity'))<=.30,('Mirror-like glass reflection',name)
        for tag,suffix in (('Texture','ca'),('GlossTexture','ng')):
            value=definition.findtext(tag).replace('\\','/')
            assert value=='Textures/Models/ArcanePower/Thermal/UniformGlass_'+suffix+'.dds'
            assert value in packaged,('Missing uniform glass texture',value)
            with Image.open(MOD/value) as image:
                assert max(ImageStat.Stat(image).stddev)==0,('Nonuniform glass texture',value)
                if suffix=='ca':assert image.getextrema()==((0,0),(0,0),(0,0),(0,0))
    restored=json.loads((ROOT/'validation/thermal-models/internal-pipes-preserved.json').read_text())
    assert restored['status']=='passed' and restored['pillar_geometry_transforms_uvs_and_materials_match']
    assert restored['pillar_pipes']==8 and restored['pillar_objects']==48
    assert restored['chamber_pipe_bodies_removed']==16 and restored['chamber_pipe_clamps_removed']==48
    assert restored['floor_vents']==4
    result={'status':'passed','blocks':len(models),'compatibility_aliases':len(contract['PIPE_ALIASES']),
            'authored_model_families':len(authored),'construction_models':3*len(authored),
            'lod_models':report['lod_models'],'validated_meshes':report['native_meshes'],
            'definitions_and_package_match':True,'co2_supply':'Automatic reactor supply; powered startup/cooldown circulation',
            'runtime_scripts':len(scripts),'runtime_definitions':len(definitions),
            'archive_entries_verified':len(packaged),'code_and_definitions_packaged':True,
            'all_block_definitions':catalog['blocks'],'dedicated_thermal_icons':catalog['thermal_icons'],
            'native_import':True,'live_game_validation':'not_run'}
    result['uniform_native_glass_textures']=True
    result['internal_plumbing_preserved']=True
    result['main_reactor']='ArcanePower_Thermal_ReactorHousing'
    result['loadable_model_folder_matches_runtime_closure']=True
    result['exported_mesh_runtime_motion_verified']=True
    result['isolation_valve_native_checks']=isolation['checks']
    (ROOT/'validation/thermal-models/delivery-check.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
