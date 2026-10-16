"""Compile native construction models; validate battery stages before delivery."""
import os
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from prepare_lab import BUILD_BLOCKS, MOD, ROOT, GAME, refresh_build_stages
from prepare_energy_core import BLOCKS as ENERGY_BLOCKS, refresh_models
from export_energy_main import digest, settings
from package_release import resolve


def compile_models(blocks,folder):
    setup=Path.home()/'.local/share/blender-se1-setup'
    cache=Path.home()/'.cache/arcane-power/build-stages/MWMBuilder'
    shutil.copytree(setup/'assets/Tools/MWMBuilder',cache,dirs_exist_ok=True)
    # Wine's default .NET trace listener fails while formatting compiler output.
    (cache/'MwmBuilder.exe.config').write_text('<configuration><system.diagnostics><trace><listeners><clear /></listeners></trace></system.diagnostics></configuration>')
    canonical=MOD/'Models/Cubes/large';win=lambda path:'Z:'+str(path).replace('/',chr(92))
    for name in blocks:
        collision=canonical/(('ArcanePower_ContainmentController' if name=='ArcanePower_AdvancedContainmentController' else name)+'.hkt')
        for stage in range(1,4):
            stem=folder/(name+'_BS'+str(stage))
            if not stem.with_suffix('.fbx').is_file() or not stem.with_suffix('.xml').is_file():raise FileNotFoundError('Export stage FBX and XML first: '+str(stem))
            shutil.copyfile(collision,stem.with_suffix('.hkt'))
        subprocess.run(['wine',str(cache/'MwmBuilder.exe'),'/f','/s:'+win(folder),'/m:'+name+'_BS?.fbx','/o:'+win(folder),'/x:'+win(setup/'assets/Materials')],cwd=cache,check=True,env={**os.environ,'WINEDEBUG':'-all','WINEPREFIX':str(setup/'wineprefix')})
        for stage in range(1,4):
            output=folder/(name+'_BS'+str(stage)+'.mwm')
            if not output.is_file() or output.stat().st_mtime<max(output.with_suffix(ext).stat().st_mtime for ext in ('.fbx','.xml')):raise RuntimeError('Missing or stale compiled stage: '+str(output))


def install_stages(staging,blocks,energy=True):
    """Validate the complete requested stage batch before connecting it."""
    folder=MOD/'Models/Cubes/large';specs=json.loads((staging/'construction-source.json').read_text())
    expected={name+'_BS'+str(stage) for name in blocks for stage in range(1,4)}
    assert set(specs)==expected,'Incomplete construction export batch'
    rows={};game=GAME/'Bin64';env={**os.environ,'MONO_PATH':str(game)}
    with tempfile.TemporaryDirectory(prefix='arcane-construction-probes-') as directory:
        probes={}
        for name in ('EnergyModelProbe','ConstructionModelProbe'):
            exe=Path(directory)/(name+'.exe')
            subprocess.run(['mcs','-out:'+str(exe),'-r:/usr/lib/mono/4.5/Facades/netstandard.dll',*['-r:'+str(game/(n+'.dll')) for n in ('VRage.Render','VRage.Math','VRage.Library')],str(ROOT/'tools'/(name+'.cs'))],check=True)
            probes[name]=exe
        for stem,spec in specs.items():
            path=staging/(stem+'.mwm');collision=folder/(('ArcanePower_ContainmentController' if spec['block']=='ArcanePower_AdvancedContainmentController' else spec['block'])+'.hkt')
            output=subprocess.check_output(['mono',str(probes['EnergyModelProbe']),str(path),str(spec['triangles']),str(collision)],env=env,text=True)
            lines=[line.split('\t') for line in output.splitlines()]
            materials=sorted({line[1] for line in lines if line[0]=='MATERIAL'})
            textures=sorted({line[1].replace(chr(92),'/') for line in lines if line[0]=='TEXTURE'})
            assert not any(line[0] in ('SUBPART','LOD') for line in lines),'Unfinished stage references moving/derived models: '+stem
            assert 'Construction' in materials and not any(any(token in m for token in ('Emissive','EnergyGlow','EnergyFill','EnergyStatus','ClearChamber')) for m in materials),'Powered or glazed stage: '+stem
            for texture in textures:assert resolve(MOD,texture) or resolve(GAME/'Content',texture),'Missing stage texture: '+texture
            subprocess.run(['mono',str(probes['ConstructionModelProbe']),str(path),str(collision),str(folder/(spec['block']+'.mwm'))],check=True,env=env)
            rows[stem]={**spec,'sha256':digest(path),'bytes':path.stat().st_size,'materials':materials,'textures':textures,'native_import_passed':True}
    definition_paths=[MOD/'Data/CubeBlocks/ArcanePower_EnergyCore.sbc'] if energy else [MOD/'Data/CubeBlocks'/n for n in set(BUILD_BLOCKS[b] for b in blocks)]
    before_settings={p:settings(p) for p in definition_paths}
    legacy=MOD/'Data/CubeBlocks/ArcanePower_EnergyCoreLegacy.sbc';legacy_hash=digest(legacy)
    finished={p:digest(p) for p in folder.glob('*.mwm') if '_BS' not in p.stem}
    collision_hashes={p:digest(p) for p in folder.glob('*.hkt') if '_BS' not in p.stem}
    report_folder=ROOT/('validation/energy-construction-update' if energy else 'validation/reactor-texture-lod-loop')
    backup=report_folder/'export-backup';backup.mkdir(exist_ok=True)
    for p in definition_paths:shutil.copy2(p,backup/p.name)
    for stem in expected:
        for ext in ('.fbx','.xml','.hkt','.mwm'):
            source=staging/(stem+ext);target=folder/source.name
            if target.exists() and not (backup/target.name).exists():shutil.copy2(target,backup/target.name)
            shutil.copy2(source,target)
    if energy:revision=refresh_models()
    else:refresh_build_stages();revision=folder
    assert all(settings(p)==value for p,value in before_settings.items()),'Non-model block settings changed'
    assert digest(legacy)==legacy_hash,'Legacy definitions changed'
    assert all(digest(p)==sha for p,sha in finished.items()),'Finished model changed'
    assert all(digest(p)==sha for p,sha in collision_hashes.items()),'Accepted collision changed'
    for stem,row in rows.items():
        if energy:delivered=revision/(stem+'.mwm')
        else:
            from prepare_lab import model_revision
            delivered=MOD/model_revision(stem)
        assert digest(delivered)==row['sha256'],'Delivered stage differs from validated model'
        row['delivered']=delivered.relative_to(MOD).as_posix()
    link=Path.home()/'.config/SpaceEngineers/Mods/ArcanePower-Prototype'
    assert link.resolve()==MOD.resolve(),'Local mod link changed'
    report={'passed':True,'revision':revision.relative_to(MOD).as_posix(),'models':rows,'finished_models_unchanged':True,'collision_bytes_unchanged':True,'non_model_settings_unchanged':True,'legacy_definitions_unchanged':True,'local_mod':str(link),'game_reloaded':False,'workshop_published':False}
    (report_folder/('native-export.json' if energy else 'native-construction-export.json')).write_text(json.dumps(report,indent=2)+'\n')
    if energy:
        path=ROOT/'validation/energy-construction-source.json';source=json.loads(path.read_text());source.update(exported=True,native_model_import_passed=True,revision=report['revision']);path.write_text(json.dumps(source,indent=2)+'\n')
    print('Validated and connected '+str(len(rows))+' construction stages:',report['revision'])
    return report


def main():
    energy='--energy' in sys.argv;folder=MOD/'Models/Cubes/large'
    if energy:folder=folder/'.energy-construction-stage'
    prototype='--prototype' in sys.argv
    if prototype:folder=folder/'.prototype-construction-stage'
    blocks=ENERGY_BLOCKS if energy else list(BUILD_BLOCKS)[:3] if prototype else BUILD_BLOCKS
    compile_models(blocks,folder)
    if energy or prototype:return install_stages(folder,blocks,energy)
    refresh_build_stages()
    print('Compiled and connected '+str(len(blocks)*3)+' construction stages')


if __name__=='__main__':main()
