# Reactor restart persistence

World saves and save-and-exit capture reactor state inside the block's registered
`MyModStorageComponent`. `MotionState` preserves startup/cooldown/dismantle/vent
phase and progress, deployed rings and both gyro phases, heat/load/ramp, selected
fuel and signed fractional consumption remainder, installed tiles/wear/replacement progress,
emergency reserve, ejection handoff and damage flags, and critical status/countdown.
The native inventory is saved by SE. Critical/ejected core records also retain
their existing server-owned world-storage ledger.

The snapshot now explicitly includes the reactor's on/off flag. Running reactors
resume running; interrupted sequences continue from their saved progress. Manually
switched-off reactors and completed vent cycles remain off. Old saves without the
new optional flag retain the native saved Enabled value. A copied/projected block
with a different entity ID cannot inherit installed tiles, reserve or active cycles.
This does not skip the normal cooldown/dismantling sequence when a player switches
the reactor off and back on during play.

## Save timing

SE's `MySession.Save` captures its checkpoint, then sector/grid object builders,
then invokes session `SaveData`. Saving block storage only in `SaveData` is too
late for that sector snapshot. `VentSession.GetObjectBuilder` now flushes all
initialized reactor states during the checkpoint step, before grid serialization.
Periodic/state-transition saves and the existing SaveData/Close fallback remain.
A guard prevents a pre-initialization save from overwriting the loaded state.

This is normal save persistence, not crash journaling: closing without saving or
losing the process restores the last completed world save. No offline fuel burn,
cooling or wall-clock detonation advancement is introduced.

## Restore timing

The native upgrade block reconnects on its 100-frame update. Previously,
`CheckContainment` could disable the reactor before those upgrades existed, and
the first power request returned zero because the controller had no preceding
distribution interval. Either path could turn a restored running state into a
shutdown.

A bounded 120-simulation-frame initialization period now holds the restored pose
and suppresses those startup-only shutdown checks. Generation stays suppressed
until the final two frames, when capacity and controller demand are primed. Fuel
accounting runs during those priming frames; a new sink's first empty interval is
not mistaken for a sustained outage. After initialization, normal hardware, fuel,
power and reserve rules apply. Missing modules or actual power loss still stop the
reactor. A committed critical core's existing hazard timer is not reset or paused
by this initialization period.

The dashboard identifies this short phase as **Reconnecting containment**. Saved
fuel emissives/poses remain available during initialization. The running world is
not hot-reloaded by copying scripts to the local mod directory.

## Native source evidence and delivery

- `Sandbox.Game/.../World/MySession.cs`: checkpoint → sector → SaveData ordering;
  `SaveSessionComponentObjectBuilders` invokes each session GetObjectBuilder.
- `SpaceEngineers.Game/.../Blocks/MyUpgradeModule.cs`: deferred connection refresh
  in UpdateBeforeSimulation100 after grid registration.
- `ContainmentController.Request`: reports the previously distributed interval.
- `EntityComponents.sbc`: registers the existing ArcanePowerMotionState GUID.
- `VRage.Library/VRage/MyFixedPoint.cs`: double conversion rounds inventory
  amounts to the nearest millionth, rather than truncating them.

## Fuel rounding restore failure (2026-10-09)

The Prototype Lab save contained an enabled, running reactor with
`FuelDebt=-2.288216908615642E-07`. A rounded-up native fuel withdrawal leaves a
small negative remainder: credit to carry into subsequent ticks. The validator
required a nonnegative value, silently rejecting the entire motion snapshot and
replacing it with defaults. That also rejected running-state network updates
whenever they carried a negative remainder.

Validation now permits credit down to half the native inventory quantum, with
`1e-12` tolerance for double arithmetic. Consumption and the saved credit remain
unchanged; clamping credit to zero would accumulate excess consumption. Larger
negative values, NaN, infinities and remainders at or above one remain invalid.
Invalid snapshots for the same entity now produce a restore diagnostic; copied
entities still cannot inherit the original reactor's state.

Offline verification:

- `tools/check_reload_retraction.py` uses the affected world's complete motion
  XML in `tools/fixtures/reactor-running-rounding.xml`. It verifies enabled/running
  restore, all saved fields unchanged, connection initialization, manual-off
  preservation, validation boundaries, diagnostics and copied-entity rejection.
  Existing reload/interlock and teardown checks also pass. Engine interactions
  use doubles; this does not simulate actual power distribution after loading.
- `tools/check_controller_tiers.py` now uses the installed native `MyFixedPoint`
  instead of the incorrect floor-based test double. It verifies every snapshot
  and accumulated fuel accounting over 300,000 ticks across five loads and all
  controller tiers, including 150 XML round trips with negative credit and a
  protobuf round trip. Existing fuel/controller checks also pass.
- `tools/compile_mod.py` passes against installed SE assemblies and the MDK
  whitelist with zero warnings or errors.

A fresh in-game world reload remains to be verified. The running game must reload
the mod scripts to apply this fix. No live world files were modified.
