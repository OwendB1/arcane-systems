"""SE DDS conversion preserving packed alpha, including entirely zero channels.

The installed texconv treats all-zero legacy TGA alpha as missing/opaque.
PNG staging preserves metalness/gloss/paint masks independently of RGB.
CLI: python3 tools/texture_conversion.py path/to/material_cm.tga [...]
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from PIL import Image

SETUP = Path.home()/'.local/share/blender-se1-setup'
ENV = {**os.environ, 'WINEDEBUG': '-all', 'WINEPREFIX': str(SETUP/'wineprefix')}
win = lambda path: 'Z:'+str(path).replace('/', chr(92))


def convert(source, target, linear=False, icon=False, voxel=False):
    source, target = Path(source).resolve(), Path(target).resolve()
    files = sorted(source.parent.glob(source.name))
    if not files:
        raise FileNotFoundError(source)
    target.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='arcane-packed-textures-') as directory:
        staging = Path(directory)
        for path in files:
            with Image.open(path) as image:
                image.convert('RGBA').save(staging/(path.stem+'.png'))
        args = ['wine', str(SETUP/'staging/space-engineers-utilities/tools/texconv.exe'),
                '-nologo', '-y', '-ft', 'DDS', '-f', 'BC7_UNORM' if linear else 'BC7_UNORM_SRGB',
                '-o', win(target), '-pmalpha' if icon else '-sepalpha']
        if not linear:
            args.append('-sRGB')
        if voxel:
            args += ['-w', '2048', '-h', '2048']
        subprocess.run(args+[win(staging/'*.png')], check=True, env=ENV)
    for path in files:
        output = target/(path.stem+'.dds')
        uppercase = output.with_suffix('.DDS')
        if uppercase.exists():
            uppercase.replace(output)
        if not output.exists():
            raise RuntimeError('Missing DDS: '+str(output))
        if not icon:
            with Image.open(path) as original, Image.open(output) as compiled:
                if original.convert('RGBA').getchannel('A').getextrema() == (0, 0):
                    # BC7 can couple alpha to a shared endpoint bit (up to 4/255).
                    if compiled.getchannel('A').getextrema()[1] > 4:
                        raise RuntimeError('Packed zero alpha lost: '+str(output))


if __name__ == '__main__':
    for arg in sys.argv[1:]:
        source = Path(arg).resolve()
        convert(source, source.parent, linear=source.stem.endswith('_ng'))
