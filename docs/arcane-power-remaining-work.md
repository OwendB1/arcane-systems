# Arcane Power — remaining implementation work

Updated 16 September 2026 after thermal failure, physical ejection and plasma asset implementation. This is the current delivery checklist; the [full plan](arcane-power-plan.md) retains the wider design direction.

## Latest asset delivery

The selected **1.6 m × 1.0 m piggyback packs**, raised **2.3 m socket surrounds**, reactor surface fixes and revised vent recesses are now exported to MWM and retained in the latest local model family `lab_64ff9a73f168`, now including new plasma/field/debris assets. Five model icons were refreshed. Native upgrade empties were not scaled. Exported-model hashes and deployed icon bytes match; no game reload or regression suites were run. The earlier crescent controller geometry below is superseded.

## Completed in the preceding hardware/tile pass

- Recorded [startup/shutdown](../ArcanePower/validation/recordings/reactor-startup-shutdown.mp4) and [vent ejection](../ArcanePower/validation/recordings/reactor-vent.mp4) from spectator view on the primary monitor at 3440×1440/60 fps. These show the preceding reactor revision at low load. Existing ceiling blocks obscure the roof hatch; footage does not establish hot cooldown or rated output.
- Repaired the reactor and both attached controllers. [Repair evidence](../ArcanePower/validation/recordings/repair.json) confirms full integrity and build after reloading and resaving the lab.
- Authored/exported stackable 3×1×3-cell vent duct and outlet, each with a 3.72 m lined bore. The outlet uses four moving leaves and fuel/alarm emissives. Direct code follows a straight aligned route and synchronizes its terminal door to the reactor doors.
- Authored/exported distinct one-cell crescent standard/advanced containment controllers with native upgrade mating detectors.
- Authored/exported a thick framed triangular component, model-rendered icons and a provisional assembler recipe. Added server-owned tile reserve, wear, conveyor supply, shortage shutdown and vent loss.
- Saved the Blender review lineup, compiled the solution without warnings/errors, and deployed 45 files as `lab_5d37d651a7ca`. This new pass has **not** been loaded or placed in-game. No regression suites ran.

## Latest survival-script pass

Implemented native containment sinks on external controllers, real grid-funded precharge, a persisted 90-second shutdown reserve, power-loss shutdown and actuator pausing after reserve exhaustion. Provisional tier demand is 1/10/100 MW; full precharge requests 4/40/400 MW for about 30 seconds. Added rotating quartet maintenance replacement, shutdown completion of active replacements, terminal stock/endurance/power information, and an explicit inventory whitelist/tooltip for all three fuels plus tiles. Script compilation passed; local deployment is recorded separately from live evidence. No destructive breach, game control or regression suites in this pass.

## Next game review, when requested

| Area | What remains to establish |
| --- | --- |
| Hardware placement | Duct/outlet fit inside their cells, native central conveyor links connect, controller concavities face the reactor, and each controller contributes the expected native upgrade value. |
| Vent travel | View both reactor doors and terminal outlet unobstructed. Confirm timing, full ring clearance through stacked ducts and a closed/restored outlet after the cycle. |
| Survival supplies | Craft/pull tiles through conveyors; debit 80 for initial startup, retain through ordinary shutdown, consume four-item wear batches, verify 10% output/10× burn on failed maintenance and precritical resupply recovery, and require fresh tiles after venting. |
| Power and inventory UI | Confirm accepted-item tooltip, manual/conveyor fuel transfers, grid-funded precharge, native controller loads and priority, blackout shutdown, reserve depletion/recovery, and zero free reserve after copying. |
| Maintenance animation | Confirm each quartet launches from stationary dispensers, joins the moving field, clears the rings and finishes before shutdown; save/rejoin during replacement. |
| Electrical behavior | Measure 10/100/1,000 GW ratings under actual demand, ten-second ramp, fuel use, hot cooldown before dismantling, and heat/load-scaled vent damage. The clips cover low-load visuals only. |
| Appearance | Check glass haze, first-load emissives, access-panel highlighting, new materials/icons and moving-door edges in the engine. |
| Persistence | Save/rejoin during assembly, maintenance and venting; verify no duplicated material, reset heat or repeated damage. |

The running lab remains repaired on its recorded revision. Local deployment becomes available on the next world load; it is not a live hot-reload.

## Remaining implementation sequence

1. **Finish the reactor survival loop.** Validate the new electrical demand, reserve priority, blackout behavior, inventory UI and visible quartet replacement in-game when requested. Refine the current reserve/stock estimates and any missing shutdown reasons. Tune fuel/tile throughput and refine interrupted startup, grinding, projector/copy and damaged-block accounting.
2. **Finish vent behavior.** Handle blocked passages/outlets, broken routes during a committed cycle and independent shutter faults. Actuation now uses the containment grid/reserve budget; validate its supply-loss behavior. Tune the new critical explosions and add discharge-specific effects/sounds, plus collision geometry appropriate to moving doors. Current routing supports straight same-grid runs of up to 16 sections; a missing terminal outlet blocks a custom chain, but ordinary obstructions on the legacy direct roof path are not checked. Ejection now hands off to native physical objects beyond the outlet; verify collision, gravity, launch speed and native cleanup limits. Define regulated/automatic vent modes and exhaust-capacity progression if retained from the broader plan.
3. **Make mining-to-generation playable.** Add ore voxel materials and asteroid/planet distribution, decide compatibility with existing/custom terrain, and finalize cumulative fuel ingredients/recipes. Ore/fuel definitions alone do not make deposits mineable. Complete a survival run without admin-spawned resources.
4. **Build Arcane Energy Core storage.** Implement battery controller, stored energy, native grid charge/discharge limits, capacity and transfer modules, stabilizers, and startup/emergency reserve controls. Model and animate the battery family. Validate surplus capture, demand peaks and reserve use without creating energy. Vanilla batteries remain a valid startup/backup option.
5. **Finish art and feedback.** Refine the new engineering models against Arcane Cores/SE materials, add construction/damage stages and LODs, tune mass/components/PCU, finish ore/fuel/battery icons, and add sound/particle feedback. Review tile flight paths, door pockets, highlights and glass in-game as requested.
6. **Harden and package.** Validate multiplayer/dedicated server, late join, save/load, splits/merges, ownership, projection, multiple reactors and distance performance. Check interactions with Arcane Cores/Ship Core Framework power modifiers. Complete balance, documentation and Workshop packaging after the full survival loop works. Run automated regression suites only when requested.

## Current balance assumptions

The shell reserves 80 tiles upfront; normal shutdown preserves installed quantity and wear, while venting loses the shell. Creative mode supplies tiles freely. The initial recipe makes four tiles from 2 iron, 0.1 nickel and 0.2 silicon in ten base seconds. Full-load wear is initially 1/2/4 quartets per minute by tier, with 20% idle wear and a quadratic heat factor reaching 4× at 100% heat. These are prototype settings, not finalized survival balance.

The vents occupy their native 3×1×3 cells and controllers retain one-cell anchors. The latest packs have a curved visual mating skirt entering unused space beside the reactor drum; fit and attachment still require placement review. Two functional controllers remain mandatory, separately from the 2/3/4-ring fuel capacity. Direct C# controls animation; Animation Engine is no longer required.

## Latest thermal/physical delivery

Implemented and locally deployed: 10% output with 10× pre-failure-load fuel consumption, heat-squared tile wear, continued runaway after electrical shutdown, precritical resupply recovery, a provisional 125% supercritical threshold, irreversible heat-accelerated fuse, and 5×/20×/100× native large-warhead damage with cube-root radius. Physical spent rings/tiles and a separate dynamic plasma carrier take over beyond the outlet. Criticality persists across ejection, source/carrier removal and save/reload; cooler ejected cores decay. Smooth textured plasma and open thick triangular frames are exported. [Full specification and limits](../ArcanePower/THERMAL-FAILURE.md).

Still to validate when requested: actual electrical/fuel limits under load; starvation/recovery and heat balance; saved critical timers inside and outside the housing; late join and destroyed/removed carriers; blast radius/occlusion and whether prompt venting saves the housing; ring/tile physical clearance and gravity; final in-game emissive texture appearance. No regression suite or destructive in-game test has run. The local mod update has not been loaded in-game.

## LCD and handheld telemetry delivery (2026-09-16)

Implemented: compact shared status report, SCF-inspired native LCD dashboard,
equippable inert handheld tablet with original SEUT model/collision/materials,
icon and assembler recipe, paged live HUD through Text HUD API, and a native text
fallback. Tablet telemetry requires suit broadcast and a mutual accessible grid
antenna connection; it grants no grid/terminal/reactor control. See
[status display setup and limits](../ArcanePower/STATUS-DISPLAYS.md).

Pending user-requested game review: equip/IK poses in both views, dashboard scale,
multi-reactor selection, suit/grid antenna power/range/relay loss and ownership
changes, reconnect, and multiplayer replication. Live render-to-texture on the
physical tablet screen is not implemented; the real held asset accompanies the
live HUD. Wide LCD tiling and per-surface page settings are future refinements.

## Restart persistence follow-up (2026-09-16)

Fixed snapshot timing and restoration order: save block state during checkpoint
capture, retain the on/off flag, hold the saved pose through native module
reconnection and prime power before judging an outage. State is persisted for
normal saves/save-and-exit, including interrupted sequences. Still awaiting
requested game review; no regression suites or running-world changes.
[Restart persistence details](../ArcanePower/REACTOR-PERSISTENCE.md).
