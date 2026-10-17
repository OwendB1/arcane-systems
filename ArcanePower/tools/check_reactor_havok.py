"""Load delivered collision with the installed game's native Havok and cast contacts.

Linux authoring check: requires Mono compiler and the existing SEUT Wine prefix.
"""
from pathlib import Path
import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
game = Path.home()/'.local/share/Steam/steamapps/common/SpaceEngineers/Bin64'
reactor = next(block for block in ET.parse(ROOT/'src/Data/CubeBlocks/ArcanePower_Thermal.sbc').findall('CubeBlocks/Definition')
               if block.findtext('Id/SubtypeId')=='ArcanePower_Thermal_ReactorHousing')
model = ROOT/'src'/reactor.findtext('Model')
hkt = ROOT/'assets/collisions/Cubes/large/ArcanePower_ReactorPrototype.hkt'
with tempfile.TemporaryDirectory(prefix='arcane-native-collision-') as directory:
    exe=Path(directory)/'Probe.exe'
    model_probe=Path(directory)/'ModelProbe.exe'
    subprocess.run(['mcs','-out:'+str(model_probe),'-r:/usr/lib/mono/4.5/Facades/netstandard.dll',
                    *['-r:'+str(game/(name+'.dll')) for name in ('VRage.Render','VRage.Math','VRage.Library')],
                    str(ROOT/'tools/EnergyModelProbe.cs')],check=True)
    embedded=Path(directory)/'embedded.hkt'
    subprocess.run(['mono',str(model_probe),'--collision',str(model),str(embedded)],check=True,
                   env={**os.environ,'MONO_PATH':str(game)})
    assert embedded.read_bytes()==hkt.read_bytes(),'Delivered reactor collision differs from accepted physics'
    subprocess.run(['mcs','-platform:x64','-out:'+str(exe),'-r:/usr/lib/mono/4.5/Facades/netstandard.dll',
                    *['-r:'+str(game/(name+'.dll')) for name in ('HavokWrapper','VRage.Library','VRage.Math')],
                    str(ROOT/'tools/ReactorCollisionProbe.cs')],check=True)
    win=lambda path:'Z:'+str(path).replace('/',chr(92))
    subprocess.run(['wine',str(exe),win(game),win(hkt)],check=True,
                   env={**os.environ,'WINEPREFIX':str(Path.home()/'.local/share/blender-se1-setup/wineprefix'),'WINEDEBUG':'-all'})
print('PASS: delivered reactor embeds the accepted collision and passes native Havok contacts')
