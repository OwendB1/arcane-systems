"""Combine the reactor platforms, glass and four SEUT-exported pillar hulls.

Usage: python3 tools/build_reactor_pillar_collision.py PILLAR_EXPORT.hkt
Native contact/capsule checks must pass before replacing the thermal build inputs.
The original housing-only collision remains unchanged for reproducible rebuilds.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

from prepare_lab import ROOT, GAME, MOD, save


def build(pillars):
    base = ROOT/'assets/collisions/Cubes/large/ArcanePower_ReactorPrototype.hkt'
    target = base.parent/'Thermal'
    before = hashlib.sha256(base.read_bytes()).hexdigest()
    env = {**os.environ,'WINEPREFIX':str(Path.home()/'.local/share/blender-se1-setup/wineprefix'),'WINEDEBUG':'-all'}
    win = lambda path:'Z:'+str(path).replace('/',chr(92))
    with tempfile.TemporaryDirectory(prefix='arcane-pillar-collision-') as directory:
        work = Path(directory)
        exe = work/'Probe.exe'
        subprocess.run(['mcs','-platform:x64','-out:'+str(exe),'-r:/usr/lib/mono/4.5/Facades/netstandard.dll',
                        *['-r:'+str(GAME/'Bin64'/(name+'.dll')) for name in ('HavokWrapper','VRage.Library','VRage.Math')],
                        str(ROOT/'tools/ReactorCollisionProbe.cs')],check=True)
        combined = work/'combined.hkt'
        subprocess.run(['wine',str(exe),win(GAME/'Bin64'),'--merge',win(base),win(pillars),win(combined)],env=env,check=True)
        subprocess.run(['wine',str(exe),win(GAME/'Bin64'),win(combined)],env=env,check=True)
        assert hashlib.sha256(base.read_bytes()).hexdigest() == before
        for suffix in ('','_BS1','_BS2','_BS3'):
            shutil.copy2(combined,target/('APT_ReactorHousing_M'+suffix+'.hkt'))
        saved_pillars = target/'APT_ReactorHousing_Pillars.hkt'
        if pillars.resolve() != saved_pillars.resolve():
            shutil.copy2(pillars,saved_pillars)
    print('Installed validated pillar collision for reactor main and all three construction stages')


def install():
    """Replace only native collision tags; preserve every authored render payload."""
    definition = MOD/'Data/CubeBlocks/ArcanePower_Thermal.sbc'
    tree = ET.parse(definition)
    reactor = next(b for b in tree.findall('CubeBlocks/Definition')
                   if b.findtext('Id/SubtypeId') == 'ArcanePower_Thermal_ReactorHousing')
    models = [reactor.find('Model'), *reactor.findall('BuildProgressModels/Model')]
    old = (MOD/reactor.findtext('Model')).parent
    report_path = ROOT/'validation/thermal-models/native-export.json'
    report = json.loads(report_path.read_text())
    native_env = {**os.environ, 'MONO_PATH': str(GAME/'Bin64')}
    with tempfile.TemporaryDirectory(prefix='arcane-reactor-model-') as directory:
        work = Path(directory)
        bundle = work/'models'
        shutil.copytree(old, bundle)
        probe = work/'ModelProbe.exe'
        subprocess.run(['mcs', '-out:'+str(probe), '-r:/usr/lib/mono/4.5/Facades/netstandard.dll',
                        *['-r:'+str(GAME/'Bin64'/(name+'.dll')) for name in ('VRage.Render','VRage.Math','VRage.Library')],
                        str(ROOT/'tools/EnergyModelProbe.cs')], check=True)
        for node in models:
            path = MOD/(node.text if node.tag == 'Model' and not node.attrib else node.get('File'))
            assert path.parent == old, 'Reactor main and stages must share their native bundle'
            collision = ROOT/'assets/collisions/Cubes/large/Thermal'/(path.stem+'.hkt')
            target = bundle/path.name
            subprocess.run(['mono', str(probe), '--set-collision', str(path), str(target), str(collision)],
                           env=native_env, check=True)
            row = report['native_models'][path.stem]
            subprocess.run(['mono', str(probe), str(target), str(row['triangles']), str(collision), str(path)],
                           env=native_env, check=True, stdout=subprocess.DEVNULL)
            row['sha256'] = hashlib.sha256(target.read_bytes()).hexdigest()
        stamp = hashlib.sha256(b''.join(p.name.encode()+p.read_bytes() for p in sorted(bundle.iterdir()))).hexdigest()[:12]
        revision = old.parent/('thermal_'+stamp)
        if revision.exists():
            assert {p.name:p.read_bytes() for p in revision.iterdir()} == {p.name:p.read_bytes() for p in bundle.iterdir()}
        else:
            shutil.copytree(bundle, revision)
        for node in models:
            if node.attrib:
                node.set('File', (revision/Path(node.get('File')).name).relative_to(MOD).as_posix())
            else:
                node.text = (revision/Path(node.text).name).relative_to(MOD).as_posix()
        save(tree.getroot(), definition)
        report['revision'] = revision.relative_to(MOD).as_posix()
        report['physics'] = 'Ten flat reactor hulls: unchanged deck/roof and four pillars, four convex glass quadrants; SE model and grid shape counts agree'
        report['game_reloaded'] = False
        report_path.write_text(json.dumps(report, indent=2)+'\n')
    print('Installed collision-only reactor revision', revision.name)


if __name__ == '__main__':
    assert len(sys.argv) in (2,3) and (len(sys.argv) == 2 or sys.argv[2] == '--install'), 'Supply the pillar-only HKT, optionally followed by --install'
    build(Path(sys.argv[1]).resolve())
    if '--install' in sys.argv:
        install()
