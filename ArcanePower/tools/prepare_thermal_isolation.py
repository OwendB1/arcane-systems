"""Compile/install (with --compile) or validate native reactor shut-off valves."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from prepare_lab import ROOT, MOD, GAME
from package_release import resolve

SOURCE=ROOT/'assets/thermal-isolation.json'
STAGE=MOD/'Models/Cubes/large/.isolation-stage'
DEST=MOD/'Models/Cubes/large/Thermal/Isolation'
POSE=MOD/'Data/Scripts/ArcanePower/ThermalIsolation.cs'
REPORT=ROOT/'validation/thermal-models/isolation.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(compile_models=False):
    contract=json.loads(SOURCE.read_text())
    folder=STAGE if compile_models else DEST
    if compile_models:
        setup=Path.home()/'.local/share/blender-se1-setup'
        builder=Path.home()/'.cache/arcane-power/thermal/MWMBuilder'
        shutil.copytree(setup/'assets/Tools/MWMBuilder',builder,dirs_exist_ok=True)
        (builder/'MwmBuilder.exe.config').write_text('<configuration><system.diagnostics><trace><listeners><clear /></listeners></trace></system.diagnostics></configuration>')
        win=lambda path:'Z:'+str(path).replace('/',chr(92))
        for name in contract['models']:
            source=folder/(name+'.fbx')
            assert source.is_file(), 'Run the live Blender isolation export first'
            subprocess.run(['wine',str(builder/'MwmBuilder.exe'),'/f','/s:'+win(folder),'/m:'+source.name,
                '/o:'+win(folder),'/x:'+win(setup/'assets/Materials')],cwd=builder,check=True,
                env={**os.environ,'WINEDEBUG':'-all','WINEPREFIX':str(setup/'wineprefix')})
            assert source.with_suffix('.mwm').stat().st_mtime>=source.stat().st_mtime
    with tempfile.TemporaryDirectory(prefix='arcane-isolation-') as directory:
        work=Path(directory)
        built=subprocess.run(['dotnet','build',str(ROOT/'ArcanePower.csproj'),'--nologo','-o',str(work)],capture_output=True,text=True)
        if built.returncode:raise RuntimeError(built.stdout+built.stderr)
        exe=work/'IsolationProbe.exe'
        subprocess.run(['mcs','-out:'+str(exe),'-r:System.Web.Extensions','-r:/usr/lib/mono/4.5/Facades/netstandard.dll',
            '-r:'+str(work/'ArcanePower.dll'),*['-r:'+str(GAME/'Bin64'/(n+'.dll')) for n in ('VRage.Render','VRage.Math','VRage.Library')],
            str(ROOT/'tools/ThermalIsolationProbe.cs')],check=True)
        result=subprocess.check_output(['mono',str(exe),str(SOURCE),str(folder)],text=True,
            env={**os.environ,'MONO_PATH':str(work)+':'+str(GAME/'Bin64')})
        report=json.loads(result)
        for texture in report.pop('textures'):
            value=texture.replace('\\','/')
            assert resolve(MOD,value) or resolve(GAME/'Content',value), ('Missing valve texture',value)
    if compile_models:
        DEST.mkdir(parents=True,exist_ok=True)
        for name in contract['models']:shutil.copy2(folder/(name+'.mwm'),DEST/(name+'.mwm'))
    report.update(contract_sha256=digest(SOURCE),runtime_pose_sha256=digest(POSE),
        native_mesh_sha256={p.relative_to(MOD).as_posix():digest(p) for p in (DEST/(name+'.mwm') for name in contract['models'])},
        in_game_validation='not_run')
    REPORT.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return report


if __name__=='__main__':check('--compile' in sys.argv)
