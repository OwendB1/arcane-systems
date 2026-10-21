"""Prepare an unpublished runtime ZIP, checking native model/asset dependencies."""
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from prepare_lab import ROOT, MOD, GAME, COLLISIONS, BASE_MODELS


def resolve(root, value):
    # SE asset paths are case insensitive, including on the Linux client.
    path = root
    for part in Path(value).parts:
        if part in ('.', '..') or not path.is_dir(): return None
        candidate = path/part
        if not candidate.exists():
            candidate = next((p for p in path.iterdir() if p.name.casefold() == part.casefold()), None)
        if candidate is None: return None
        path = candidate
    return path if path.is_file() else None


def prune_model_exports(runtime_files):
    """Keep only the resolved runtime closure in the loadable model folder."""
    folder=MOD/'Models/Cubes/large'
    unused=sorted(p for p in folder.rglob('*') if p.is_file() and p not in runtime_files)
    if not unused:return
    preserved=[]
    # Save exact physics and native interface baselines before deleting any
    # intermediate exports. Blends remain the geometry/material source.
    for path in unused:
        relative=path.relative_to(folder)
        destination=None
        if path.suffix=='.hkt' and relative.parent==Path('.'):
            destination=COLLISIONS/path.name
        elif path.suffix=='.hkt' and relative.parent==Path('.thermal-stage'):
            destination=COLLISIONS/'Thermal'/path.name
        elif relative.parent==Path('.') and path.suffix=='.mwm' and path.stem.startswith('ArcanePower_') and not re.search(r'_LOD\d|_r[0-9a-f]{12}|\.hkt$',path.stem):
            destination=BASE_MODELS/path.name
        elif relative==Path('ArcanePower_Plasma.xml'):
            destination=ROOT/'assets/definitions'/path.name
        elif relative==Path('.thermal-stage/sources.json'):
            destination=ROOT/'validation/thermal-models/native-export-sources.json'
            if destination.exists():
                # Incremental variant exports contain only their new rows.
                # Keep the prior source ledger when removing staging.
                rows=json.loads(destination.read_text())
                rows.update(json.loads(path.read_text()))
                path.write_text(json.dumps(rows,indent=2)+'\n')
        if destination:
            if destination.suffix=='.hkt' and destination.exists() and destination.read_bytes()!=path.read_bytes():
                raise RuntimeError('Export differs from accepted collision input: '+str(destination))
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,destination)
            sha=hashlib.sha256(path.read_bytes()).hexdigest()
            assert hashlib.sha256(destination.read_bytes()).hexdigest()==sha,('Authoring input copy failed',path)
            preserved.append({'path':destination.relative_to(ROOT).as_posix(),'sha256':sha,'bytes':destination.stat().st_size})
    removed_bytes=sum(p.stat().st_size for p in unused)
    for path in unused:path.unlink()
    for path in sorted((p for p in folder.rglob('*') if p.is_dir()),key=lambda p:len(p.parts),reverse=True):
        if not any(path.iterdir()):path.rmdir()
    report={'status':'passed','removed_files':len(unused),'removed_bytes':removed_bytes,
            'runtime_models_retained':sum(p.is_relative_to(folder) for p in runtime_files),
            'preserved_authoring_inputs':preserved}
    (ROOT/'validation/model-export-cleanup.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Pruned',len(unused),'unused model exports;',removed_bytes,'bytes removed from src')


def main():
    files = set(MOD.glob('Data/**/*.sbc')) | set(MOD.glob('Data/**/*.cs'))
    files.add(MOD/'metadata.mod')
    models = set()
    native = set()

    def asset(value):
        value = value.strip().replace('\\', '/')
        if not value or Path(value).suffix.lower() not in ('.mwm', '.dds', '.wav'):
            return
        path = resolve(MOD, value)
        if path:
            files.add(path)
            if path.suffix == '.mwm': models.add(path)
        elif resolve(GAME/'Content', value):
            native.add(value)
        else:
            raise FileNotFoundError('Unresolved runtime asset: '+value)

    for path in sorted(files):
        if path.suffix != '.sbc': continue
        for node in ET.parse(path).iter():
            asset(node.text or '')
            for value in node.attrib.values(): asset(value)
    game = GAME/'Bin64'
    with tempfile.TemporaryDirectory(prefix='arcane-package-') as tmp:
        exe = Path(tmp)/'Dependencies.exe'
        subprocess.run(['mcs', '-out:'+str(exe), '-r:/usr/lib/mono/4.5/Facades/netstandard.dll',
            *['-r:'+str(game/(name+'.dll')) for name in ('VRage.Render','VRage.Math','VRage.Library')],
            str(ROOT/'tools/ModelDependencies.cs')], check=True)
        result = subprocess.run(['mono', str(exe), *map(str, sorted(models))],
            capture_output=True, text=True, env={**os.environ, 'MONO_PATH':str(game)})
        if result.returncode: raise RuntimeError(result.stderr)
        for line in result.stdout.splitlines():
            kind, value = line.split('\t', 1)
            if kind == 'MODEL': files.add(Path(value))
            else: asset(value)
    entries = []
    output = ROOT/'.cache/release'
    output.mkdir(parents=True, exist_ok=True)
    version = (ROOT/'workshop/version.txt').read_text().strip()
    if ET.parse(MOD/'metadata.mod').findtext('ModVersion') != version:
        raise ValueError('Mod metadata and Workshop version must match')
    archive = output/('ArcanePower-'+version+'.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as package:
        for path in sorted(files):
            relative = path.relative_to(MOD).as_posix()
            data = path.read_bytes()
            package.writestr(relative, data)
            entries.append(dict(path=relative, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
    manifest = dict(version=version, published=False, archive=archive.name,
        sha256=hashlib.sha256(archive.read_bytes()).hexdigest(), bytes=archive.stat().st_size,
        files=entries, native_assets=sorted(native))
    (ROOT/'validation/release-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    prune_model_exports(files)
    print(str(archive)+': '+str(len(entries))+' files, '+str(manifest['bytes'])+' bytes; dependencies resolved')


if __name__ == '__main__': main()
