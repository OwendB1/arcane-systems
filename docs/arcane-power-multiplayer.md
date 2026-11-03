# Arcane Power multiplayer compatibility

Implementation checklist from the multiplayer audit, 3 November 2026. Work in
order; mark each item complete with its verification, then reread the next item.
The server owns gameplay, persistence and physical hazards. Clients consume
measurements and animate presentation. Listen hosts run both roles.

- [x] 1. Fix hazard removal synchronization. Use a nonempty snapshot envelope
  which explicitly clears the client when the final hazard disappears.
- [x] 2. Replicate complete reactor display telemetry: fuel, tiles, Residuum,
  controller count/capacity and advanced-controller readiness. HUD/LCD/tablet
  reads must not depend on inventory UI context or local attachment discovery.
- [x] 3. Prevent clients from overwriting authoritative power telemetry. Keep
  necessary local native sink mirroring separate from server measurements.
- [x] 4. Remove dedicated-server cosmetic work: radiator subpart transforms and
  flow smoothing/scrolling. Preserve tracking/exposure and collision suppression.
- [x] 5. Separate authoritative mechanism timing and model contracts from client
  animation, preserving startup, maintenance, cooldown and physical ejection.
- [x] 6. Replicate energy-bank membership, policy/allocation and emergency results;
  clients consume server decisions instead of independently calculating them.
- [x] 7. Add recipient relevance filtering and consistent request throttling;
  avoid repeatedly sending immutable hazard shell geometry.
- [x] 8. Harden snapshot lifecycle and transport: sequences, bounded validation,
  game-thread handling, freshness, retry and send-failure handling.
- [x] 9. Fix listen-server command identity handling for host input versus native
  timer/PB actions, retaining authenticated remote-player authorization.
- [x] 10. Add multiplayer acceptance coverage, then run the complete available
  test suite. Cover server/client roles, late join/reconnect/streaming, ownership,
  automation, save/reload during venting and final-hazard removal. Record which
  checks use engine doubles and which have been exercised in a live world.

## Verification log

1. Hazard snapshots now use a versioned envelope, preserving explicit empty state.
   Focused meltdown/ejection suite: 2,383 checks passed.

2. Added validated reactor telemetry to motion snapshots and routed client supply,
   controller and readiness displays through it. Appearance/status checks passed.

3. Client sinks mirror confirmed demand without rewriting input, demand or reserve.
   Focused client power/replicated supply regression passed.

4. Dedicated servers skip radiator transforms and flow smoothing/scrolling.
   Radiator collision suppression remains active, including recreated subparts.
   Focused role/collision regression passed.

5. Visual transforms now live in Reactor.Visuals.cs. Heat simulation is server-only;
   shared scalar clocks and physical pose sampling preserve gameplay/ejection.
   Manifold readiness caches native model metadata without rendered subpart checks.
   Focused meltdown/ejection suite: 2,383 checks passed.

6. Energy snapshots now carry membership, active modules, native allocations,
   policy, emergency state and aggregate flow. Clients no longer rediscover bank
   policy or allocations. Energy policy suite passed; allocation regression added.

7. Shared PowerNetwork transport filters recipients by SyncDistance and throttles
   per-player/channel/entity snapshot requests. Hazard snapshots are batched,
   atomically assembled, and send shell geometry only on first observation or
   explicit resync. A normal compiled build is the focused verification.

8. Added bounded/validated sequenced snapshots, atomic hazard batch assembly,
   game-thread exception handling and transport send diagnostics. Stale reactor,
   energy, thermal and hazard replicas pause/clear presentation and request resync.
   Compiled build and focused energy checks passed; full packet tests follow in 10.

9. Native action callbacks have a server-local trusted path; host UI input keeps
   its access check and remote packets always validate sender identity. The flag
   is absent from wire contracts. Game-compatible MDK analyzer build passed.

10. Added `tools/check_multiplayer.py` and `tests/power-multiplayer.cs`, compiling
    the production transport, receiver and command bodies against recording
    engine doubles and the installed game's protobuf/math libraries. Also
    extended client telemetry, allocation, timeout and dedicated-render tests.
    Updated older fixtures to include their current runtime dependencies.

## Final test results

The final implementation passed all 23 runtime/contract suites, all 45 JavaScript
tests, the game-compatible MDK analyzer build (zero warnings/errors), native
model-motion checks and the rebuilt release delivery check. The broader Python
pass also exercised definition, audio, asset, construction and native collision
checks. Two pre-existing failures remain in unchanged inputs, listed below.

| Check | Result |
| --- | --- |
| New multiplayer transport/handler acceptance | 130 checks passed |
| Thermal runtime/topology/conservation | 1,407,974 checks passed |
| Reactor fuel/mode/controller integration | 152,405 checks passed |
| Cooling integrity and isolation | 3,715 checks passed |
| Meltdown, ejection, save/reload and shield testing | 2,383 checks passed |
| Radiator client/server motion and collision ownership | 192 checks passed |
| Exported native mesh motion | 1,820 checks; 60 meshes; no failures |
| Energy bank policies, allocation, surge, reload and stale-state recovery | Passed (`--policy-only`) |
| Remaining runtime, telemetry, sound, tablet and lifecycle suites | Passed |
| Repository JavaScript/configurator suites | 45 tests passed |
| Native Havok reactor contacts | Passed offline under the existing Wine setup |
| Shared menu coverage (`tests/check_arcane_categories.py`) | Existing failure: expects every public variant to appear directly in the category |
| Full Energy Core asset check (`tools/check_energy_core.py`) | Existing failure: delivered ring MWM differs from its canonical native-baseline file; runtime policy checks pass |

The category test/definitions and Energy Core model/baseline inputs were unchanged
by this work. No geometry or definitions were edited to hide these failures.

Reproducible primary commands, from the repository root:

```sh
python3 ArcanePower/tools/check_multiplayer.py
python3 ArcanePower/tools/check_energy_core.py --policy-only
python3 ArcanePower/tools/check_thermal_runtime.py
python3 ArcanePower/tools/check_reactor_fuel_modes.py
python3 ArcanePower/tools/check_meltdown.py
python3 ArcanePower/tools/check_radiator_physics.py
python3 ArcanePower/tools/compile_mod.py
node --test tests/*.test.mjs docs/scf-configurator/*.test.mjs
python3 ArcanePower/tools/check_thermal_delivery.py
git diff --check
```

## Package and compatibility

The unpublished local `ArcanePower/.cache/release/ArcanePower-0.3.0.zip` was
rebuilt with all new runtime sources: 697 files, 444,417,118 bytes. Native
dependencies, archive CRCs/checksums and the runtime dependency closure passed
the delivery gate. Release and native-motion fingerprints were refreshed.
Workshop publishing was not performed. The local package remains unpublished.

Existing entity-bound gameplay saves retain their storage keys and field tags.
Hazard save files remain XML lists; the versioned/batched envelope is a network
format. Reload the world and run matching mod sources on server and clients;
mixed old/new hazard wire formats are unsupported.

## Live multiplayer validation still required

Packet tests simulate a dedicated server and two clients, plus listen-host
automation, queued game-thread delivery, ownership changes, late join, reconnect,
relevance changes, stale state and reordered batches. They are not live SE
network sessions. Native mesh and Havok checks are offline too.

Before claiming live multiplayer certification, exercise this matrix on a real
dedicated server and repeat the automation rows on a listen host:

| Scenario | Expected result |
| --- | --- |
| Two clients observe startup, load changes, maintenance and cooldown | Matching confirmed status; local visuals/audio; no dedicated-server visual transforms |
| Join a running plant without opening its inventory | Correct fuel, tile, controller, bank and cooling readouts |
| Disconnect/reconnect rapidly and leave/re-enter replication range | State and shell geometry recover; distant entries clear |
| Change ownership, use a foreign block, trigger owner timers/PBs | Unauthorized remote actions fail; native authorized automation works independently of the host identity |
| Save/reload during venting or with an armed/ejected core | Consumables, paid energy, physical handoff and fuse remain conserved |
| Remove/detonate the final core | Both clients remove warnings, sound, light and shell visuals |
| Interrupt state delivery and restore it | Prediction pauses, stale state is explicit, retries recover the current baseline |

Live multiplayer validation was **not run** in this environment.
