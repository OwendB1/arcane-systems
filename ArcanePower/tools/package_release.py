"""Prepare an unpublished runtime ZIP, checking native model/asset dependencies."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from prepare_lab import ROOT, MOD, GAME


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
    print(str(archive)+': '+str(len(entries))+' files, '+str(manifest['bytes'])+' bytes; dependencies resolved')


if __name__ == '__main__': main()
