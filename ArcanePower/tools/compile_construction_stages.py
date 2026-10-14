"""Compile the SEUT-exported construction FBXs with the installed SE1 toolchain."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

from prepare_lab import BUILD_BLOCKS, MOD, refresh_build_stages
from prepare_energy_core import BLOCKS as ENERGY_BLOCKS, main as refresh_energy

setup = Path.home()/'.local/share/blender-se1-setup'
cache = Path.home()/'.cache/arcane-power/build-stages/MWMBuilder'
shutil.copytree(setup/'assets/Tools/MWMBuilder', cache, dirs_exist_ok=True)
# Wine's default .NET trace listener fails while formatting MWMBuilder output.
(cache/'MwmBuilder.exe.config').write_text(
    '<configuration><system.diagnostics><trace><listeners><clear />'
    '</listeners></trace></system.diagnostics></configuration>')
folder = MOD/'Models/Cubes/large'
win = lambda path: 'Z:'+str(path).replace('/',chr(92))
blocks = ENERGY_BLOCKS if '--energy' in sys.argv else BUILD_BLOCKS
for name in blocks:
    collision = folder/(name+'.hkt')
    if name == 'ArcanePower_AdvancedContainmentController':
        collision = folder/'ArcanePower_ContainmentController.hkt'
    for stage in range(1,4):
        stem = folder/(name+'_BS'+str(stage))
        if not stem.with_suffix('.fbx').is_file() or not stem.with_suffix('.xml').is_file():
            raise FileNotFoundError('Export stage FBX and XML first: '+str(stem))
        # Native SEUT fallback: each build stage uses the finished block's hull.
        shutil.copyfile(collision,stem.with_suffix('.hkt'))
    subprocess.run(['wine',str(cache/'MwmBuilder.exe'),'/f','/s:'+win(folder),
                    '/m:'+name+'_BS?.fbx','/o:'+win(folder),'/x:'+win(setup/'assets/Materials')],
                   cwd=cache,check=True,env={**os.environ,'WINEDEBUG':'-all',
                   'WINEPREFIX':str(setup/'wineprefix')})
    for stage in range(1,4):
        output=folder/(name+'_BS'+str(stage)+'.mwm')
        if not output.is_file() or output.stat().st_mtime < output.with_suffix('.fbx').stat().st_mtime:
            raise RuntimeError('Missing or stale compiled stage: '+str(output))
if '--energy' in sys.argv: refresh_energy()
else: refresh_build_stages()
print('Compiled and connected '+str(len(blocks)*3)+' construction stages')
