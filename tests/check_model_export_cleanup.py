"""Pruning preserves runtime closure and rebuild inputs, including on copy failure."""
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ArcanePower/tools'))
import package_release as package


with tempfile.TemporaryDirectory(prefix='arcane-cleanup-check-') as directory:
    root=Path(directory)
    mod=root/'src'
    folder=mod/'Models/Cubes/large'
    folder.mkdir(parents=True)
    (root/'validation/thermal-models').mkdir(parents=True)
    baseline=root/'assets/native-baselines/Cubes/large'
    collisions=root/'assets/collisions/Cubes/large'
    originals={
        'Thermal/current/main.mwm':b'current parent',
        'Thermal/LOD/lod_r0123456789ab.mwm':b'referenced distance mesh',
        'old/main.mwm':b'obsolete export',
        'ArcanePower_ReactorPrototype.mwm':b'accepted interface baseline',
        'ArcanePower_ReactorPrototype.hkt':b'accepted collision',
        '.thermal-stage/APT_Reactor_M.hkt':b'accepted thermal collision',
        '.thermal-stage/sources.json':b'{}',
        '.thermal-stage/APT_Reactor_M.fbx':b'temporary geometry',
        'ArcanePower_Plasma.xml':b'<Model/>',
    }
    for name,data in originals.items():
        path=folder/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(data)
    blend=root/'assets/production.blend'
    blend.parent.mkdir(parents=True,exist_ok=True)
    blend.write_bytes(b'production source')
    keep={folder/name for name in list(originals)[:2]}
    with patch.multiple(package,ROOT=root,MOD=mod,BASE_MODELS=baseline,COLLISIONS=collisions):
        with patch.object(package.shutil,'copy2',side_effect=OSError('archive unavailable')):
            try:package.prune_model_exports(keep)
            except OSError:pass
            else:raise AssertionError('Archive failure must abort pruning')
        assert all((folder/name).read_bytes()==data for name,data in originals.items())
        package.prune_model_exports(keep)
        assert {p for p in folder.rglob('*') if p.is_file()}==keep
        assert (baseline/'ArcanePower_ReactorPrototype.mwm').read_bytes()==originals['ArcanePower_ReactorPrototype.mwm']
        assert (collisions/'ArcanePower_ReactorPrototype.hkt').read_bytes()==originals['ArcanePower_ReactorPrototype.hkt']
        assert (collisions/'Thermal/APT_Reactor_M.hkt').read_bytes()==originals['.thermal-stage/APT_Reactor_M.hkt']
        assert (root/'validation/thermal-models/native-export-sources.json').read_bytes()==b'{}'
        assert (root/'assets/definitions/ArcanePower_Plasma.xml').read_bytes()==b'<Model/>'
        package.prune_model_exports(keep)
        assert blend.read_bytes()==b'production source'
        assert all(path.read_bytes()==originals[path.relative_to(folder).as_posix()] for path in keep)
        changed=folder/'ArcanePower_ReactorPrototype.hkt'
        changed.write_bytes(b'unaccepted physics')
        obsolete=folder/'obsolete.fbx'
        obsolete.write_bytes(b'keep until inputs are safe')
        try:package.prune_model_exports(keep)
        except RuntimeError:pass
        else:raise AssertionError('Cleanup must never replace accepted physics')
        assert obsolete.exists() and changed.exists()
        assert (collisions/changed.name).read_bytes()==originals[changed.name]
print('PASS: runtime closure, rebuild inputs, idempotence, archive failure and collision-change safety')
