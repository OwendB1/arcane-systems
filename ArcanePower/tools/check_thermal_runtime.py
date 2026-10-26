"""Exercise the compiled production runtime with native math and authored layout."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
GAME = Path.home() / '.local/share/Steam/steamapps/common/SpaceEngineers/Bin64'


def fixture(filename, method, bare=False):
    models = json.loads((ROOT / 'ArcanePower/validation/thermal-models/models.json').read_text())
    layout = json.loads((ROOT / 'tests/fixtures'/filename).read_text())
    # Blender column vectors -> native SE row vectors, A=(-X,Z,Y).
    basis = ((-1, 0, 0), (0, 0, 1), (0, 1, 0))
    rows = ['using System.Collections.Generic;', 'using ArcanePower;', 'using VRageMath;',
            'public static partial class ThermalRuntimeChecks {',
            'static List<ThermalEndpoint> '+method+'() { return new List<ThermalEndpoint> {']
    for ident, entry in enumerate(layout['instances'], 1):
        model=entry['model']
        if bare and model+' bare' in models:model+=' bare'
        matrix = entry['matrix_blender']
        rotation = [[sum(basis[i][a] * matrix[a][b] * basis[j][b] for a in range(3) for b in range(3))
                     for j in range(3)] for i in range(3)]
        at = [sum(basis[i][a] * matrix[a][3] for a in range(3)) for i in range(3)]
        native = [rotation[j][i] if i < 3 and j < 3 else at[j] if i == 3 and j < 3 else 1 if i == j else 0
                  for i in range(4) for j in range(4)]
        values = ','.join(format(round(value, 6), '.6g') + 'f' for value in native)
        rows.append(f'Node({ident}, "{models[model]["subtype"]}", new Matrix({values})),')
    rows += ['}; } }']
    return '\n'.join(rows)


def main():
    subprocess.run(['python3', str(ROOT / 'ArcanePower/tools/build_thermal_runtime_contract.py'), '--check'], check=True)
    with tempfile.TemporaryDirectory(prefix='arcane-thermal-check-') as directory:
        work = Path(directory)
        output = work / 'mod'
        # compile_mod.py owns the full compatibility/whitelist analyzer gate.
        result = subprocess.run(['dotnet', 'build', str(ROOT / 'ArcanePower/ArcanePower.csproj'),
                                 '--nologo', '-p:RunAnalyzersDuringBuild=false', '-o', str(output)], capture_output=True, text=True)
        if result.returncode:
            print(result.stdout, result.stderr)
            raise SystemExit(result.returncode)
        (work / 'Layout.cs').write_text(fixture('thermal-starter-layout.json', 'Layout'))
        (work / 'BareLayout.cs').write_text(fixture('thermal-starter-layout.json', 'BareLayout', bare=True))
        (work / 'RoomLayout.cs').write_text(fixture('thermal-room-layout.json', 'RoomLayout'))
        exe = work / 'checks.exe'
        subprocess.run(['mcs', '-langversion:6', '-out:' + str(exe),
                        '-r:/usr/lib/mono/4.5/Facades/netstandard.dll', '-r:' + str(output / 'ArcanePower.dll'),
                        '-r:' + str(GAME / 'VRage.Math.dll'), '-r:' + str(GAME / 'VRage.Library.dll'),
                        '-r:' + str(GAME / 'ProtoBuf.Net.dll'), '-r:' + str(GAME / 'ProtoBuf.Net.Core.dll'),
                        str(ROOT / 'tests/thermal-runtime.cs'), str(work / 'Layout.cs'), str(work / 'BareLayout.cs'), str(work / 'RoomLayout.cs')], check=True)
        result = subprocess.run(['mono', str(exe), str(ROOT / 'ArcanePower/validation/thermal-models/flow-review-states.json')], capture_output=True, text=True,
                                env={**os.environ, 'MONO_PATH': str(output) + ':' + str(GAME)})
        print(result.stdout, end='')
        if result.returncode:
            print(result.stderr, end='')
            raise SystemExit(result.returncode)
        report = dict(status='passed', scope='Compiled production kernel with native math; no live SE world',
                      runtime_contracts=55, authored_starter_blocks=len(json.loads((ROOT / 'tests/fixtures/thermal-starter-layout.json').read_text())['instances']), manifold_samples=47,
                      authored_room_blocks=len(json.loads((ROOT / 'tests/fixtures/thermal-room-layout.json').read_text())['instances']),
                      conservation_hours_per_efficiency=1, efficiencies=[.20, .40, .78],
                      cooling_checks='Per-circuit adequate/half/zero rejection, early recovery, hottest-circuit critical threshold, paid-energy conservation, idempotent migration, reload and idle credit',
                      bank_checks='Four independent manifold circuits at fixed 25% heat allocations; unchanged tier efficiency, immediate availability, sealed topology, isolated failure and last-loop trip',
                      rotor_checks='Linear load targets, no-demand idle, coastdown, reload/copy identity, invalid inputs, phase integration and native pivots',
                      flow_checks='Starter and room routing, opposed H/C, capped spurs, standby branches, equal parallel routes, split/facing/roll faults, path sampling and state validation',
                      construction_checks='Authored build, incomplete/detached blocks, open/facing/roll/crowded joints, 24 placement orientations, missing turbine/cooling and unchanged runtime authority',
                      isolation_checks='Removed/damaged/split/misrolled/crowded/open-cap circuits; cross-linked manifolds, extra turbines, fixed surviving allocations, immediate repair, legacy charge/pressure XML snapshots and valve timing',
                      integration_checks='Unique multiplayer channels, compatible game logic for every authored subtype, interchangeable bare/framed pipes and registered runtime sessions',
                      checks=result.stdout.strip(), native_delivery_report='thermal-models/delivery-check.json',
                      in_game_validation='not_run')
        (ROOT / 'ArcanePower/validation/thermal-runtime.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
