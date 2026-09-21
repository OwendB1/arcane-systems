"""Restore lost packed alpha in local SEUT preview TIFs from installed vanilla DDS.

Input: JSON {Blender image name: resolved texture path}. Backs up every replaced
RGB TIF outside the repository. No game textures are distributed with this tool.
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path
from PIL import Image

assets = Path.home()/'.local/share/blender-se1-setup/assets'
game = Path.home()/'.local/share/Steam/steamapps/common/SpaceEngineers/Content'
backup = Path.home()/'.cache/arcane-power/seut-texture-backups'
native = {str(p.relative_to(game)).lower(): p for p in (game/'Textures').rglob('*') if p.suffix.lower() == '.dds'}
report = []
for path in set(json.loads(Path(sys.argv[1]).read_text()).values()):
    target = Path(path).resolve()
    relative = target.relative_to(assets)
    source = native.get(str(relative.with_suffix('.dds')).lower())
    if source is None:
        report.append({'texture': str(relative), 'status': 'no native counterpart'})
        continue
    with Image.open(target) as old, Image.open(source) as original:
        if 'A' in old.getbands() or 'A' not in original.getbands():
            report.append({'texture': str(relative), 'status': 'no lost alpha'})
            continue
        digest = hashlib.sha256(target.read_bytes()).hexdigest()[:12]
        saved = backup/relative.with_name(target.stem+'_'+digest+target.suffix)
        saved.parent.mkdir(parents=True, exist_ok=True)
        if not saved.exists():
            shutil.copy2(target, saved)
        original.convert('RGBA').save(target, compression='tiff_lzw')
        report.append({'texture': str(relative), 'status': 'restored RGBA from native DDS', 'backup': str(saved)})
print(json.dumps(report, indent=2))
