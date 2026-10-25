"""Run production fuel/mode interlocks and circuit dispatch with recording SE doubles."""
from pathlib import Path
import os
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'ArcanePower/src/Data/Scripts/ArcanePower'
GAME = Path.home() / '.local/share/Steam/steamapps/common/SpaceEngineers/Bin64'


def member(file, signature):
    source = (SRC / file).read_text()
    start = source.index(signature)
    end = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end] + '\n'


members = ''.join(member(file, signature) for file, signatures in {
    'Reactor.Fuel.cs': ['private bool HasUsableFuel()', 'private void RefreshFuelCapacity()',
                       'private double FuelUnitsPerMinute()', 'private void UpdateFuel()',
                       'private void RecoverResiduum()', 'private void ExportResiduum('],
    'Reactor.Safety.cs': ['private bool IsIntactController(', 'internal bool HasAdvancedController()',
                         'private bool HasIntactControllers()'],
    'Reactor.Power.cs': ['private bool CanPrepareContainment', 'internal bool NeedsStorageSupport',
                        'private float ContainmentMW', 'private double ReserveCapacityMJ'],
    'Reactor.Motion.cs': ['private void BeginShutdown()', 'private void BeginDismantling()',
                         'private void RestoreMotionState(', 'internal static bool Valid('],
    'Reactor.Thermal.cs': ['internal bool ThermalInitialized', 'private bool ThermalFuelModeReady',
                          'internal double ThermalHeatMW', 'internal double ThermalHotC', 'private bool ThermalNeedsPowerSupport',
                          'internal bool ThermalCanRun', 'private float ElectricalRatingMW',
                          'private bool ThermalCold', 'private bool ThermalManifoldPower',
                          'internal string ThermalModeTransitionHint', 'internal void RequestThermalMode(',
                          'private void UpdateThermalMode()', 'internal void ProduceThermal(',
                          'private void RefreshThermalCapacity()', 'internal void StopForLoopLoss()',
                          'private void ThermalEnabledChanged(', 'internal void CheckLoopSafety()',
                          'private void InitializeThermalRuntime()'],
}.items() for signature in signatures)
# Engine interface replacement only; all predicates and state changes are shipped code.
members = members.replace('VRage.Game.ModAPI.IMyCubeBlock', 'Block').replace('VRage.Game.ModAPI.IMyInventory', 'Inventory')
members = members.replace('VRage.Game.ModAPI.Ingame.MyItemType', 'MyItemType')
fuel = (SRC / 'Reactor.Fuel.cs').read_text()
members += fuel[fuel.index('        private static readonly string[] Fuels'):fuel.index('        private MyReactor nativeReactor;')]
motion = (SRC / 'Reactor.Motion.cs').read_text()
state = motion[motion.index('    public enum CorePhase'):motion.index('    public sealed partial class Reactor')]
state = re.sub(r'\[Proto(?:Contract|Member\([^]]+\))\]', '', state)
session = (SRC / 'VentSession.cs').read_text()
start = session.index('thermalMode.Enabled = ') + len('thermalMode.Enabled = ')
gate = session[start:session.index('};', start) + 1]
fixture = (ROOT / 'tests/reactor-fuel-modes.cs').read_text()
fixture = fixture.replace('// PRODUCTION_MEMBERS', members).replace('// PRODUCTION_STATE', state)
fixture = fixture.replace('/* TERMINAL_GATE */', gate)
fixture = fixture.replace('// PRODUCTION_LOOPS', ''.join(member('ThermalSession.Loops.cs', signature)
    for signature in ('private void AdvanceLoops(', 'private static double DrainLoop('))
    + member('ThermalSession.cs', 'private static void InvalidateCircuits('))
with tempfile.TemporaryDirectory(prefix='arcane-fuel-modes-') as folder:
    path = Path(folder) / 'check.cs'
    path.write_text(fixture)
    exe = path.with_suffix('.exe')
    subprocess.run(['mcs', '-warn:0', '-langversion:6', '-out:' + str(exe),
                    '-r:/usr/lib/mono/4.5/Facades/netstandard.dll', '-r:' + str(GAME / 'VRage.Library.dll'), '-r:' + str(GAME / 'VRage.Math.dll'),
                    str(path), str(SRC / 'ThermalPlant.cs'), str(SRC / 'ThermalLoops.cs'), str(SRC / 'ThermalNetwork.cs')], check=True)
    subprocess.run(['mono', str(exe)], env={**os.environ, 'MONO_PATH': str(GAME)}, check=True)
