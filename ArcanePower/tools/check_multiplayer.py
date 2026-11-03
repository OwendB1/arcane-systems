"""Run production transport/packet handlers with native protobuf and engine doubles.

Builds the mod, then exercises authenticated server/client delivery on a queued
game thread. This does not run a dedicated server, Havok or a live SE connection.
"""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'ArcanePower/src/Data/Scripts/ArcanePower'
GAME = Path.home() / '.local/share/Steam/steamapps/common/SpaceEngineers/Bin64'


def member(filename, signature):
    source = (SRC / filename).read_text()
    start = source.index(signature)
    end = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end].replace('private ', 'internal ', 1)


def main():
    subprocess.run(['dotnet', 'build', str(ROOT / 'ArcanePower/ArcanePower.csproj'),
                    '--nologo', '-p:RunAnalyzersDuringBuild=false'], check=True)
    fixture = (ROOT / 'tests/power-multiplayer.cs').read_text()
    network = (SRC / 'PowerNetwork.cs').read_text()
    network = network[network.index('namespace ArcanePower'):].replace('namespace ArcanePower', 'namespace Acceptance')
    replacements = {
        'NETWORK': network,
        'REACTOR': '\n'.join(member(f, s) for f, s in [
            ('Reactor.Motion.cs', 'internal static bool Valid('),
            ('Reactor.Tiles.cs', 'private static bool ValidTileGrades('),
            ('Reactor.Thermal.cs', 'internal bool ManifoldRigReady'),
            ('Reactor.Motion.cs', 'internal void ReceiveState(')]),
        'VENT': '\n'.join(member('VentSession.cs', s) for s in [
            'internal static void SendCommand(', 'private static void Apply(', 'private void Receive(']),
        'ENERGY_CORE': '\n'.join(member(f, s) for f, s in [
            ('EnergyCore.Gameplay.cs', 'internal void ReceiveGameplay('),
            ('EnergyCore.Replication.cs', 'internal bool CanReceiveBank('),
            ('EnergyCore.Replication.cs', 'internal void ReceiveBank(')]),
        'ENERGY': '\n'.join(member('EnergySession.cs', s) for s in [
            'private static void Send(', 'private static void Apply(', 'private static EnergyPacket Snapshot(', 'private void Receive(']),
        'HAZARDS': '\n'.join(member('CoreHazards.cs', s) for s in [
            'private void Broadcast(', 'private void SendSnapshot(', 'private void ApplySnapshot(', 'private void Receive(']),
    }
    for name, value in replacements.items():
        fixture = fixture.replace('// ' + name + '_PRODUCTION', value)
    with tempfile.TemporaryDirectory(prefix='arcane-multiplayer-') as directory:
        work = Path(directory)
        path = work / 'Checks.cs'
        path.write_text(fixture)
        output = ROOT / 'ArcanePower/bin/Debug/net48'
        exe = work / 'Checks.exe'
        subprocess.run(['mcs', '-warn:0', '-langversion:6', '-out:' + str(exe),
                        '-r:/usr/lib/mono/4.5/Facades/netstandard.dll', '-r:' + str(output / 'ArcanePower.dll'),
                        *['-r:' + str(GAME / name) for name in ('VRage.Math.dll', 'VRage.Library.dll', 'ProtoBuf.Net.dll', 'ProtoBuf.Net.Core.dll')],
                        str(path)], check=True)
        subprocess.run(['mono', str(exe)], check=True,
                       env={**os.environ, 'MONO_PATH': str(output) + ':' + str(GAME)})


if __name__ == '__main__':
    main()
