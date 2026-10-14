"""Recompile plasma with fresh texture/model cache keys after a material export."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid
import xml.etree.ElementTree as ET

from prepare_lab import MOD, refresh_reactor_model
from texture_conversion import SETUP, ENV, win


def main(refresh_cache=False):
    # Explicit refresh also changes paths when the asset bytes are unchanged.
    cache_key = uuid.uuid4().bytes if refresh_cache else b''
    textures = MOD/'Textures/Models/ArcanePower'
    # Preserve the selected original dark DDS packing. Re-converting the PNGs
    # here would silently replace it with the rejected nonmetallic glow variant.
    maps = sorted(textures.glob('ArcanePlasma_*.dds'))
    digest = hashlib.sha256(cache_key+b''.join(p.name.encode()+p.read_bytes() for p in maps)).hexdigest()[:12]
    revision = textures/('plasma_'+digest)
    revision.mkdir(exist_ok=True)
    for source in maps:
        shutil.copy2(source, revision/source.name)

    models = MOD/'Models/Cubes/large'
    name = 'ArcanePower_Plasma'
    tree = ET.parse(models/(name+'.xml'))
    for parameter in tree.findall('Material/Parameter'):
        if parameter.get('Name').endswith('Texture'):
            filename = parameter.text.replace('\\', '/').split('/')[-1]
            parameter.text = (revision/filename).relative_to(MOD).as_posix()
    # Stage compilation so a failed compiler cannot replace the working model.
    with tempfile.TemporaryDirectory(prefix='arcane-plasma-') as directory:
        staging = Path(directory)/'Models/Cubes/large'
        staging.mkdir(parents=True)
        builder = Path(directory)/'MWMBuilder'
        shutil.copytree(SETUP/'assets/Tools/MWMBuilder', builder)
        (builder/'MwmBuilder.exe.config').write_text(
            '<configuration><system.diagnostics><trace><listeners><clear />'
            '</listeners></trace></system.diagnostics></configuration>')
        for suffix in ('.fbx', '.hkt'):
            shutil.copy2(models/(name+suffix), staging/(name+suffix))
        tree.write(staging/(name+'.xml'), encoding='utf-8', xml_declaration=True)
        subprocess.run(['wine', str(builder/'MwmBuilder.exe'), '/f', '/s:'+win(staging),
                        '/m:'+name+'.fbx', '/o:'+win(staging),
                        '/x:'+win(SETUP/'assets/Materials')], cwd=builder, env=ENV, check=True)
        output = staging/(name+'.mwm')
        if not output.is_file():
            raise RuntimeError('Plasma model compilation produced no MWM')
        shutil.copy2(output, models/output.name)
        shutil.copy2(staging/(name+'.xml'), models/(name+'.xml'))
    print('Plasma textures:', revision.relative_to(MOD))
    print('Reactor model:', refresh_reactor_model())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh-cache', action='store_true',
                        help='Force fresh model and plasma texture paths even without asset changes')
    main(parser.parse_args().refresh_cache)
