"""Compile authored fuel FBXs/textures with the installed SE1 tools; refresh definitions."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont
from prepare_lab import ROOT, MOD, fuel_definitions
from texture_conversion import convert

setup = Path.home()/'.local/share/blender-se1-setup'
cache = Path.home()/'.cache/arcane-power/fuels/MWMBuilder'
shutil.copytree(setup/'assets/Tools/MWMBuilder', cache, dirs_exist_ok=True)
(cache/'MwmBuilder.exe.config').write_text(
    '<configuration><system.diagnostics><trace><listeners><clear />'
    '</listeners></trace></system.diagnostics></configuration>')
env = {**os.environ, 'WINEDEBUG': '-all', 'WINEPREFIX': str(setup/'wineprefix')}
win = lambda path: 'Z:'+str(path).replace('/', chr(92))


canister_only='--canister-only' in sys.argv
residuum_only='--residuum-only' in sys.argv
selected = 'ArcaneAetherResiduum' if residuum_only else 'ArcaneAetherCanister' if canister_only else None
if not canister_only:
    folders = [MOD/'Textures/Models/ArcanePower/Fuels']
    if not residuum_only:folders.append(MOD/'Textures/Voxels/ArcanePower')
    for folder in folders:
        for channel in ('cm', 'ng', 'add'):
            convert(folder/(('ArcaneResiduum*_' if residuum_only else '*_')+channel+'.tga'), folder,
                    linear=channel=='ng', voxel='Voxels' in folder.parts)
convert(ROOT/'assets/icons/fuels'/((selected or '*')+'.png'), MOD/'Textures/GUI/Icons/ArcanePower', icon=True)
models = MOD/'Models/Items/ArcanePower'
jobs = []
if not residuum_only:jobs.append((models, (selected or '*')+'.fbx'))
if not canister_only:jobs.append((ROOT/'.cache/residuum/models', 'ArcaneAetherResiduum.fbx'))
for sources,pattern in jobs:
    inputs=list(sources.glob(pattern))
    if not inputs:raise RuntimeError('Export Blender fuel sources first: '+str(sources/pattern))
    subprocess.run(['wine', str(cache/'MwmBuilder.exe'), '/f', '/s:'+win(sources),
                    '/m:'+pattern, '/o:'+win(sources), '/x:'+win(setup/'assets/Materials')],
                   cwd=cache, check=True, env=env)
    for source in inputs:
        output = source.with_suffix('.mwm')
        if not output.is_file() or output.stat().st_mtime < source.stat().st_mtime:
            raise RuntimeError('Missing or stale model: '+str(output))
        if sources != models:
            shutil.copy2(output, models/output.name)
            materials=ROOT/'assets/fuel-materials';materials.mkdir(exist_ok=True)
            shutil.copy2(source.with_suffix('.xml'),materials/(source.stem+'.xml'))
fuel_definitions()
if selected:
    print('Compiled '+selected+' model, icon and materials; definitions refreshed.')
    sys.exit(0)

# Review the actual model renders beside each matching mineral surface.
sheet = Image.new('RGB', (1280, 1120), '#141d29')
draw = ImageDraw.Draw(sheet)
font_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
font = ImageFont.truetype(font_path, 22)
small = ImageFont.truetype(font_path, 17)
draw.text((24, 18), 'ARCANE POWER / FUEL MATERIALS', font=font, fill='#e7edf7')
for col, title in enumerate(('RAW ORE', 'CONCENTRATE', 'FUEL CARTRIDGE', 'VOXEL SURFACE')):
    draw.text((col*320+24, 65), title, font=small, fill='#a8b5c6')
tiers = [
    ('Aether', 'Aetherite', 'ArcaneOre', 'ArcaneAetherConcentrate', 'ArcaneFuelI', '#36cbe9'),
    ('Helion', 'Helionite', 'ArcaneHelionOre', 'ArcaneHelionConcentrate', 'ArcaneFuelII', '#ffb43e'),
    ('Empyrean', 'Empyrite', 'ArcaneEmpyreanOre', 'ArcaneEmpyreanConcentrate', 'ArcaneFuelIII', '#bd79f8')]
for row, (name, ore_name, ore, concentrate, fuel, color) in enumerate(tiers):
    y = 108+row*332
    draw.line((20, y, 1260, y), fill='#334255', width=1)
    for col, subtype in enumerate((ore, concentrate, fuel)):
        with Image.open(ROOT/'assets/icons/fuels'/(subtype+'.png')) as source:
            icon = source.convert('RGBA').resize((284, 284), Image.Resampling.LANCZOS)
        sheet.paste(icon, (col*320+18, y+8), icon)
        label = (ore_name, name, name+' / '+('2.5 GW', '25 GW', '250 GW')[row])[col]
        draw.text((col*320+24, y+293), label, font=small, fill=color)
    with Image.open(MOD/'Textures/Voxels/ArcanePower'/('Arcane'+name+'_cm.tga')) as source:
        swatch = source.convert('RGB').resize((284, 284), Image.Resampling.LANCZOS)
    sheet.paste(swatch, (978, y+8))
    draw.text((984, y+293), name+' deposit', font=small, fill=color)
sheet.save(ROOT/'validation/fuel-assets.png')
print('Compiled empty canister assets; definitions refreshed.' if canister_only else
      'Compiled fuel item models/icons and three near/far voxel materials; definitions refreshed.')
