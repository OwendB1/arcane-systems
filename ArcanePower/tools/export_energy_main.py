"""Compile and connect SEUT main exports; preserve existing derived art.

First run assets/export_energy_main.py in production Blender through MCP.
Use --prototype for the reactor, controllers, vents, subparts and tablet.
Add --update to install only the prototype models exported into staging.
"""
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as E

from prepare_lab import ROOT, MOD, GAME, COLLISIONS, model_source, refresh_reactor_model, save
from prepare_energy_core import BLOCKS, refresh_models
from package_release import resolve


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def settings(path):
    root = E.parse(path).getroot()
    for node in root.iter():
        if node.text and node.text.strip().lower().endswith('.mwm'):
            node.text = re.sub(r'_r[0-9a-f]{12}(?=\.mwm$)','',Path(node.text.strip().replace(chr(92), '/')).name)
        for key,value in node.attrib.items():
            if value.lower().endswith('.mwm'):
                node.set(key, re.sub(r'_r[0-9a-f]{12}(?=\.mwm$)','',Path(value.replace(chr(92), '/')).name))
    E.indent(root)
    return E.tostring(root)


def main(prototype=False, update=False):
    assert prototype or not update, 'Incremental mode is for prototype exports'
    folder = MOD/'Models/Cubes/large'
    label = 'prototype' if prototype else 'energy'
    staging = folder/('.'+label+'-main-stage')
    names = sorted(p.name.removesuffix('-source.json') for p in staging.glob('*-source.json')) if prototype else ['ArcanePower_EnergyFan', 'ArcanePower_EnergyRotor'] + list(BLOCKS)
    if prototype:
        assert names, 'No prototype source exports'
        if not update:assert len(names)==23, 'Incomplete prototype source export'
    specs = {name: json.loads((staging/(name+'-source.json')).read_text()) for name in names}
    stems = [stem for spec in specs.values() for stem in spec['collections']]
    setup = Path.home()/'.local/share/blender-se1-setup'
    cache = Path.home()/('.cache/arcane-power/'+label+'-main/MWMBuilder')
    shutil.copytree(setup/'assets/Tools/MWMBuilder', cache, dirs_exist_ok=True)
    (cache/'MwmBuilder.exe.config').write_text('<configuration><system.diagnostics><trace><listeners><clear /></listeners></trace></system.diagnostics></configuration>')
    win = lambda path: 'Z:'+str(path).replace('/', chr(92))
    env = {**os.environ, 'WINEDEBUG': '-all', 'WINEPREFIX': str(setup/'wineprefix')}
    log = ROOT/('validation/'+label+'-main-native-export.log')
    game = GAME/'Bin64'
    probe_env = {**os.environ, 'MONO_PATH': str(game)}
    accepted = {}
    # Some older assets keep physics only inside their MWM. Extract the exact
    # accepted bytes instead of regenerating collision from Blender.
    if prototype:
        exe=staging/'EnergyModelProbe.exe'
        subprocess.run(['mcs','-out:'+str(exe),'-r:/usr/lib/mono/4.5/Facades/netstandard.dll',
                        *['-r:'+str(game/(n+'.dll')) for n in ('VRage.Render','VRage.Math','VRage.Library')],
                        str(ROOT/'tools/EnergyModelProbe.cs')],check=True)
        for name in names:
            target=model_source(name) if specs[name]['target']=='Models/Cubes/large' else ROOT/specs[name]['collision_model']
            path=staging/(name+'-accepted.hkt')
            subprocess.run(['mono',str(exe),'--collision',str(target),str(path)],check=True,env=probe_env)
            accepted[name]=path
            collision=staging/(name+'.hkt')
            if path.stat().st_size:shutil.copy2(path,collision)
            else:collision.unlink(missing_ok=True)
        # Keep the reviewed plasma texture revision and its original dark DDS.
        if 'ArcanePower_Plasma' in names:
            shutil.copy2(ROOT/'assets/definitions/ArcanePower_Plasma.xml',staging/'ArcanePower_Plasma.xml')
    def compile(pattern):
        with log.open('a') as output:
            subprocess.run(['wine',str(cache/'MwmBuilder.exe'),'/f','/s:'+win(staging),
                            '/m:'+pattern,'/o:'+win(staging),'/x:'+win(setup/'assets/Materials')],
                           check=True,cwd=cache,env=env,stdout=output,stderr=subprocess.STDOUT)
    log.write_text('')
    lod_stems=sorted(set(stems)-set(names))
    if lod_stems:compile('ArcanePower_*_LOD?.fbx')
    # Native LOD paths are mod-root relative (MyLODDescriptor), unlike subparts.
    # Immutable filenames prevent cached LODs surviving a fresh parent export.
    lod_variants={};lod_paths={}
    for name,spec in specs.items():
        for stem in spec['collections']:
            if stem==name:continue
            source=staging/(stem+'.mwm');assert source.is_file(),'Missing native LOD: '+stem
            variant=source.with_stem(stem+'_r'+digest(source)[:12]);shutil.copy2(source,variant)
            lod_variants[stem]=variant;lod_paths[stem]=(Path(spec['target'])/variant.name).as_posix()
        path=staging/(name+'.xml');tree=E.parse(path)
        for node in tree.findall('LOD/Model'):
            stem=re.sub(r'_r[0-9a-f]{12}$','',Path(node.text.replace(chr(92),'/')).stem)
            assert stem in spec['collections'] and stem!=name,'Unexported LOD: '+str(node.text)
            node.text=lod_paths[stem]
        save(tree.getroot(),path)
        compile(name+'.fbx')
    for stem in stems:
        path = staging/(stem+'.mwm')
        assert path.is_file() and path.stat().st_mtime >= (staging/(stem+'.fbx')).stat().st_mtime, 'Missing/stale native export: '+stem

    rows = {}
    with tempfile.TemporaryDirectory(prefix='arcane-energy-export-probes-') as directory:
        probes = {}
        for name in ('EnergyModelProbe', 'EnergySocketProbe'):
            exe = Path(directory)/(name+'.exe')
            subprocess.run(['mcs', '-out:'+str(exe), '-r:/usr/lib/mono/4.5/Facades/netstandard.dll',
                            *['-r:'+str(game/(n+'.dll')) for n in ('VRage.Render', 'VRage.Math', 'VRage.Library')],
                            str(ROOT/'tools'/(name+'.cs'))], check=True)
            probes[name] = exe
        for name in names:
            path = staging/(name+'.mwm')
            references=[lod_paths[s] for s in specs[name]['collections'] if s!=name]
            if references:
                fixed=path.with_suffix('.relinked.mwm')
                subprocess.run(['mono',str(probes['EnergyModelProbe']),'--lod-paths',str(path),str(fixed),*references],check=True,env=probe_env)
                fixed.replace(path)
            args = ['mono', str(probes['EnergyModelProbe']), str(path), str(specs[name]['triangles'])]
            if prototype: args.extend((str(accepted[name]),str(model_source(name) if specs[name]['target']=='Models/Cubes/large' else ROOT/specs[name]['collision_model'])))
            elif name in BLOCKS: args.append(str(COLLISIONS/(name+'.hkt')))
            output = subprocess.check_output(args, env=probe_env, text=True)
            lines = [line.split('\t') for line in output.splitlines()]
            textures = sorted({line[1].replace(chr(92), '/') for line in lines if line[0] == 'TEXTURE'})
            subparts = sorted({line[1] for line in lines if line[0] == 'SUBPART'})
            for texture in textures:
                assert resolve(MOD, texture) or resolve(GAME/'Content', texture), 'Missing texture: '+texture
            for subpart in subparts:
                assert (staging/(subpart+'.mwm')).is_file() or model_source(subpart).is_file(), 'Missing subpart: '+subpart
            lods=[]
            for line in lines:
                if line[0]!='LOD':continue
                reference=line[1].replace(chr(92),'/')
                stem=next((s for s in specs[name]['collections'] if lod_paths.get(s)==reference),None)
                assert stem is not None,'Unexpected/staging LOD reference: '+reference
                variant=lod_variants[stem];expected=specs[name]['collection_triangles'][stem]
                probe=subprocess.check_output(['mono',str(probes['EnergyModelProbe']),str(variant),str(expected)],env=probe_env,text=True)
                lod_lines=[row.split('\t') for row in probe.splitlines()]
                assert not any(row[0] in ('SUBPART','LOD') for row in lod_lines),'Unexpected nested LOD interface: '+stem
                for row in lod_lines:
                    if row[0]=='TEXTURE':assert resolve(MOD,row[1].replace(chr(92),'/')) or resolve(GAME/'Content',row[1].replace(chr(92),'/')),'Missing LOD texture: '+row[1]
                lods.append({'path':reference,'triangles':expected,'distance_m':float(line[2]),'sha256':digest(variant),'native_import_passed':True})
            assert len(lods)==len(specs[name]['collections'])-1,'Missing compiled LOD descriptor: '+name
            if name in BLOCKS and not prototype:
                subprocess.run(['mono', str(probes['EnergySocketProbe']), str(path)], check=True, env=probe_env)
            if name in BLOCKS and not prototype:
                highlights=subprocess.check_output(['mono',str(probes['EnergyModelProbe']),'--highlights',str(path)],env=probe_env,text=True)
                assert 'HIGHLIGHT\tdetector_terminal\t' in highlights, 'Missing native terminal highlight: '+name
                if name=='ArcanePower_EnergyCore':
                    assert 'HIGHLIGHT\tdetector_terminal_control\tEnergy / control terminal_section' in highlights, 'Missing dedicated core terminal highlight'
            rows[name] = {'triangles': specs[name]['triangles'], 'sha256': digest(path),
                          'materials': sorted({line[1] for line in lines if line[0] == 'MATERIAL'}),
                          'textures': textures, 'subparts': subparts, 'native_import_passed': True,
                          'target':specs[name].get('target','Models/Cubes/large'),'lods':lods}
            if prototype:rows[name]['native_interfaces_unchanged']=True
            print('Validated', name, flush=True)

    definitions = MOD/'Data/CubeBlocks/ArcanePower_EnergyCore.sbc'
    definition_files=list((MOD/'Data').rglob('*.sbc')) if prototype else [definitions]
    original_settings = {p:settings(p) for p in definition_files}
    legacy = MOD/'Data/CubeBlocks/ArcanePower_EnergyCoreLegacy.sbc'
    legacy_hash = digest(legacy)
    derived = {p: digest(p) for p in folder.glob('*_BS*.mwm')}
    collision_hashes={p:digest(p) for p in (ROOT/'assets/collisions').rglob('*.hkt')}
    backup = ROOT/('validation/'+label+'-export-backup')
    backup.mkdir(exist_ok=True)
    for path in definition_files:
        saved=backup/path.relative_to(MOD);saved.parent.mkdir(parents=True,exist_ok=True)
        if not saved.exists():shutil.copy2(path,saved)
    for name,spec in specs.items():
        for stem in spec['collections']:
            for ext in ('.fbx', '.xml', '.mwm'):
                source = staging/(stem+ext)
                target = MOD/spec.get('target','Models/Cubes/large')/source.name
                saved=backup/target.relative_to(MOD);saved.parent.mkdir(parents=True,exist_ok=True)
                if target.exists() and not saved.exists(): shutil.copy2(target, saved)
                shutil.copy2(source, target)
    for stem,source in lod_variants.items():
        target=MOD/lod_paths[stem]
        if target.exists():assert digest(target)==digest(source),'Immutable LOD cache key collision'
        else:shutil.copy2(source,target)
    if prototype:
        revision=folder if update else (MOD/refresh_reactor_model()).parent
        delivered={}
        for name,spec in specs.items():
            if spec['target']=='Models/Cubes/large' and not update:delivered[name]=revision/(name+'.mwm')
            else:
                source=MOD/spec['target']/(name+'.mwm')
                target=source.with_stem(name+'_r'+digest(source)[:12]);shutil.copy2(source,target)
                delivered[name]=target
        for path in definition_files:
            tree=E.parse(path);changed=False
            for node in tree.iter('Model'):
                stem=re.sub(r'_r[0-9a-f]{12}$','',Path((node.text or '').strip().replace(chr(92),'/')).stem)
                if stem in delivered:
                    value=delivered[stem].relative_to(MOD).as_posix()
                    if node.text!=value:node.text=value;changed=True
            if changed:save(tree.getroot(),path)
    else:
        revision = refresh_models()
        delivered={name:revision/(name+'.mwm') for name in names}
    if prototype:
        from prepare_thermal_release import refresh_shared_subparts
        refresh_shared_subparts({name+'.mwm':staging/(name+'.mwm') for name in names})
    assert all(settings(p)==value for p,value in original_settings.items()), 'Non-model definition settings changed'
    assert digest(legacy) == legacy_hash, 'Legacy definitions changed'
    assert all(digest(p) == value for p, value in derived.items()), 'Build-stage models changed'
    assert all(digest(p)==value for p,value in collision_hashes.items()), 'Accepted collision files changed'
    for name in names:
        assert digest(delivered[name]) == rows[name]['sha256'], 'Packaged model differs from validated export'
        rows[name]['delivered']=delivered[name].relative_to(MOD).as_posix()
        for lod in rows[name]['lods']:assert digest(MOD/lod['path'])==lod['sha256'],'Delivered LOD differs from validated model'
    link = Path.home()/'.config/SpaceEngineers/Mods/ArcanePower-Prototype'
    assert link.resolve() == MOD.resolve(), 'Local mod no longer points to source'
    report = {'passed': True, 'revision': revision.relative_to(MOD).as_posix(), 'models': rows,
              'non_model_settings_unchanged': True, 'legacy_definitions_unchanged': True,
              'build_stages_unchanged': True, 'collision_bytes_unchanged': True,
              'local_mod': str(link), 'game_reloaded': False, 'workshop_published': False}
    (ROOT/('validation/'+label+'-main-export.json')).write_text(json.dumps(report, indent=2)+'\n')
    print('Connected validated native models:', report['revision'], flush=True)
    return report


if __name__ == '__main__': main('--prototype' in sys.argv, '--update' in sys.argv)
