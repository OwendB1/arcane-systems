"""Verify the roof relief survives native packing in the shipped main and both LODs."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from prepare_lab import ROOT, MOD, GAME


def check(paths=None):
    if paths is None:
        blocks = ET.parse(MOD / 'Data/CubeBlocks/ArcanePower_Thermal.sbc')
        model = next(b.findtext('Model') for b in blocks.findall('CubeBlocks/Definition')
                     if b.findtext('Id/SubtypeId') == 'ArcanePower_Thermal_ReactorHousing')
        report = json.loads((ROOT / 'validation/thermal-models/native-export.json').read_text())
        lods = report['native_models'][Path(model).stem]['lods']
        paths = [MOD / path for path in [model, *lods]]
    assert len(paths) == 3, 'Main and both reactor distance meshes must be checked'
    with tempfile.TemporaryDirectory(prefix='arcane-roof-') as folder:
        exe = Path(folder) / 'RoofProbe.exe'
        subprocess.run(['mcs', '-out:' + str(exe), '-r:/usr/lib/mono/4.5/Facades/netstandard.dll',
                        *['-r:' + str(GAME / 'Bin64' / (name + '.dll'))
                          for name in ('VRage.Render', 'VRage.Math', 'VRage.Library')],
                        str(ROOT / 'tools/ReactorRoofProbe.cs')], check=True)
        subprocess.run(['mono', str(exe), *map(str, paths)],
                       env={**os.environ, 'MONO_PATH': str(GAME / 'Bin64')}, check=True)


if __name__ == '__main__':
    check()
