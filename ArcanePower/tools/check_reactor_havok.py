"""Load delivered collision with the installed game's native Havok and cast contacts.

Linux authoring check: requires Mono compiler and the existing SEUT Wine prefix.
"""
from pathlib import Path
import hashlib
import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
game = Path.home()/'.local/share/Steam/steamapps/common/SpaceEngineers/Bin64'
model = ROOT/'src'/ET.parse(ROOT/'src/Data/CubeBlocks/ArcanePower_ReactorPrototype.sbc').findtext('CubeBlocks/Definition/Model')
canonical = ROOT/'src/Models/Cubes/large/ArcanePower_ReactorPrototype.mwm'
hkt = canonical.with_suffix('.hkt')
assert model.read_bytes() == canonical.read_bytes()
assert hashlib.sha256(model.read_bytes()).hexdigest()[:12] in model.stem
with tempfile.TemporaryDirectory(prefix='arcane-native-collision-') as directory:
    exe=Path(directory)/'Probe.exe'
    subprocess.run(['mcs','-platform:x64','-out:'+str(exe),'-r:/usr/lib/mono/4.5/Facades/netstandard.dll',
                    *['-r:'+str(game/(name+'.dll')) for name in ('HavokWrapper','VRage.Library','VRage.Math')],
                    str(ROOT/'tools/ReactorCollisionProbe.cs')],check=True)
    win=lambda path:'Z:'+str(path).replace('/',chr(92))
    subprocess.run(['wine',str(exe),win(game),win(hkt)],check=True,
                   env={**os.environ,'WINEPREFIX':str(Path.home()/'.local/share/blender-se1-setup/wineprefix'),'WINEDEBUG':'-all'})
print('PASS: referenced model matches the corrected export and has a fresh content-hash cache key')
