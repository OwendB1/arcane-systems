"""Compile mod sources with SE1's compatibility imports and the project's MDK analyzers.

SE's MyScriptManager.UpdateCompatibility prepends these imports to every mod source.
A plain SDK build alone cannot catch the resulting namespace collisions. This is
compilation only: it does not load a world, run regression suites or deploy files.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
# Installed game source: MyScriptManager.COMPATIBILITY_USINGS (SE1).
IMPORTS = (
    'VRage', 'VRage.Game.Components', 'VRage.ObjectBuilders', 'VRage.ModAPI',
    'VRage.Game.ModAPI', 'Sandbox.Common.ObjectBuilders', 'VRage.Game',
    'Sandbox.ModAPI', 'VRage.Game.ModAPI.Interfaces', 'SpaceEngineers.Game.ModAPI',
)

def main():
    with tempfile.TemporaryDirectory(prefix='arcane-power-compile-') as directory:
        target = Path(directory)
        shutil.copy2(ROOT / 'ArcanePower.csproj', target / 'ArcanePower.csproj')
        local = ROOT / 'ArcanePower.mdk.local.ini'
        if local.exists():
            shutil.copy2(local, target / local.name)
        for source in (ROOT / 'src/Data/Scripts').rglob('*.cs'):
            text = source.read_text(encoding='utf-8-sig')
            # Equivalent import set without duplicate-using warnings.
            header = ''.join('using ' + name + ';\n' for name in IMPORTS
                             if ('using ' + name + ';') not in text.split('namespace', 1)[0])
            output = target / source.relative_to(ROOT)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(header + '#line 1 "' + str(source) + '"\n' + text)
        return subprocess.call(['dotnet', 'build', str(target / 'ArcanePower.csproj'),
                                '--nologo', '-p:RunAnalyzersDuringBuild=true'])

if __name__ == '__main__':
    raise SystemExit(main())
