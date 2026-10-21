"""Cross-check delivered block definitions against authored and native contracts."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile
from PIL import Image, ImageStat
from check_block_catalog import check_catalog

ROOT=Path(__file__).resolve().parents[1]
MOD=ROOT/'src'


def main():
    models=json.loads((ROOT/'validation/thermal-models/models.json').read_text())
    report=json.loads((ROOT/'validation/thermal-models/native-export.json').read_text())
    tree=ET.parse(MOD/'Data/CubeBlocks/ArcanePower_Thermal.sbc')
    blocks={d.findtext('Id/SubtypeId'):d for d in tree.findall('CubeBlocks/Definition')}
    motion=json.loads((ROOT/'validation/thermal-models/native-motion.json').read_text())
    assert motion['status']=='passed' and motion['moving_parts']==24 and motion['failed_checks']==0,'Native moving meshes do not match authoring motion'
    assert motion['contract_sha256']==hashlib.sha256((ROOT/'assets/thermal-native-motion-contract.json').read_bytes()).hexdigest(),'Native motion contract changed after validation'
    assert motion['runtime_pose_sha256']==hashlib.sha256(b''.join((MOD/'Data/Scripts/ArcanePower'/name).read_bytes()
        for name in ('ThermalManifolds.cs','ThermalRotors.cs','ThermalModels.cs','ThermalPlant.cs'))).hexdigest(),'Runtime poses changed after native motion validation'
    for model in motion['models']:
        assert model['path']==blocks[model['subtype']].findtext('Model')
        assert model['sha256']==hashlib.sha256((MOD/model['path']).read_bytes()).hexdigest(),'Native moving model changed after validation'
    for path,digest in motion['native_mesh_sha256'].items():
        assert digest==hashlib.sha256((MOD/path).read_bytes()).hexdigest(),'Native moving mesh changed after motion validation'
    assert set(blocks)=={m['subtype'] for m in models.values()}
    assert report['status']=='passed' and report['blocks']==len(models) and report['construction_models']==3*len(models)
    highlights=report['inventory_highlights']
    assert set(highlights)=={'detector_conveyor_0','detector_conveyor_2','detector_conveyor_top','detector_conveyor_bottom'}
    assert len(highlights['detector_conveyor_top'])==4 and all(len(highlights[key])==1 for key in highlights if key!='detector_conveyor_top')
    category=ET.parse(MOD/'Data/ThermalCategories.sbc')
    items={n.text for n in category.findall('.//ItemIds/string')}
    files=[]
    for name,spec in models.items():
        d=blocks[spec['subtype']]
        expected='Reactor' if name=='Reactor housing' or name.startswith('Brayton train') else 'UpgradeModule'
        assert d.findtext('Id/TypeId')==expected,(name,'Wrong runtime owner')
        assert expected+'/'+spec['subtype'] in items
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
        for tag,suffix in (('Texture','ca'),('GlossTexture','ng')):
            value=definition.findtext(tag).replace('\\','/')
            assert value=='Textures/Models/ArcanePower/Thermal/UniformGlass_'+suffix+'.dds'
            assert value in packaged,('Missing uniform glass texture',value)
            with Image.open(MOD/value) as image:
                assert max(ImageStat.Stat(image).stddev)==0,('Nonuniform glass texture',value)
                if suffix=='ca':assert image.getextrema()==((0,0),(0,0),(0,0),(0,0))
    external=next(d for d in glass.findall('TransparentMaterials/TransparentMaterial') if d.findtext('Id/SubtypeId')=='ArcanePower_CoolantGlass')
    internal=next(d for d in glass.findall('TransparentMaterials/TransparentMaterial') if d.findtext('Id/SubtypeId')=='ArcanePower_InternalCoolantGlass')
    assert abs(float(external.findtext('Reflectivity'))-.45)<1e-5
    assert abs(float(internal.findtext('Reflectivity'))-.22)<1e-5
    restored=json.loads((ROOT/'validation/thermal-models/internal-pipes-preserved.json').read_text())
    assert restored['status']=='passed' and restored['geometry_transforms_and_material_assignments_match']
    result={'status':'passed','blocks':len(blocks),'construction_models':3*len(models),
            'lod_models':report['lod_models'],'validated_meshes':report['native_meshes'],
            'definitions_and_package_match':True,'co2_supply':'Integrated reactor commissioning',
            'runtime_scripts':len(scripts),'runtime_definitions':len(definitions),
            'archive_entries_verified':len(packaged),'code_and_definitions_packaged':True,
            'all_block_definitions':catalog['blocks'],'dedicated_thermal_icons':catalog['thermal_icons'],
            'native_import':True,'live_game_validation':'not_run'}
    result['uniform_native_glass_textures']=True
    result['internal_plumbing_preserved']=True
    result['main_reactor']='ArcanePower_Thermal_ReactorHousing'
    result['loadable_model_folder_matches_runtime_closure']=True
    result['exported_mesh_runtime_motion_verified']=True
    (ROOT/'validation/thermal-models/delivery-check.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
