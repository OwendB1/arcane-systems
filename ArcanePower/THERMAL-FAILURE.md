# Thermal failure, physical ejection and plasma — 16 September 2026

The generated Blender previews mentioned below were pruned during repository
cleanup on 16 October 2026. Maintained models, texture sources and runtime assets
remain unchanged.

Implemented in the local prototype; compiled and exported, **not validated in-game**.
The original September asset pass did not include regression suites or game
control. The October Brayton runtime checks now exercise paid-waste accumulation,
cooling recovery and crossing the existing critical threshold; physical ejection
and detonation still need live-game validation. The numerical thresholds below
are provisional balance values.

## Accepted behavior

An exhausted maintenance quartet reduces electrical output to **10% of the operating load immediately before failure**, while fuel consumption becomes **10× the normal consumption for that same load**. These are separate multipliers: together they mean 100× the fuel per unit of delivered electrical energy. Idle inventory being empty does not fail a still-serviceable installed shell; failure starts when its next worn quartet cannot be replaced.

The core is the source of the catastrophic explosion. Ejecting it can save the housing by moving the blast away; the housing is not granted blast immunity. Once supercritical, detonation remains inevitable after ejection, shutdown, resupply or cooling. Confirmed behavior: **detonation becomes unavoidable only after the threshold; cooler ejected cores decay**. A tile-starved, unrepaired core continues heating even after electrical shutdown; an armed core remains explosive after ejection.

## Provisional thermal balance

- Brayton cooling overload now feeds this same failure path. Paid return waste
  accumulates in the reactor when the cooling bank cannot reject it. Full stores
  stop fresh fuel use but do not clear retained heat. Restore cooling or shut down
  early, maintaining circulation power; once 125% is reached the existing fuse
  remains irreversible. Standalone retains its integrated 10% conversion/cooling.
  The retained-waste warning precedes the core's temperature response; delaying
  recovery until the core itself reaches 100% can still let it cross 125% while
  the accumulated heat drains.
- Healthy heat approaches operating load (0–100%) with the existing 60-second heating / 30-second cooling response.
- Tile wear in quartets/minute is `tierBase × (0.2 + 0.8 × reactionLoad) × (1 + 3 × heat²)`, where tierBase is 1/2/4. At 100% heat, wear is four times its cold value. Eighty initial tiles and four-tile replacement batches remain unchanged.
- Starvation captures the actual electrical load before reduction. The reactor remains running at its reduced capacity; fuel burn uses the captured load, not its now-reduced electrical output. An explicit shutdown or fully closed vent shield stops fuel consumption/output.
- Failed containment heats toward 250–300%, with a 12-second response, even during electrical shutdown. Replacing four tiles before supercriticality stops that runaway. The replacement animation can finish during cooling.
- **Supercriticality latches at 125%**. The in-housing critical reaction heats toward 400%, with the same 12-second response. Mechanism pauses do not pause thermal progression or detonation.
- New supercritical cores receive a fixed **60 simulation seconds** before detonation. Rising heat cannot accelerate this countdown, and cooling cannot extend it. This leaves about 52.5 seconds beyond the normal 7.5-second shield/intake/ejection sequence; broken controllers, vents or lost actuation power can still delay ejection. Time pauses with the simulation/world, not wall-clock time.
- Legacy armed cores convert their old heat-weighted fuse to its remaining seconds once. Reload, shutdown, core ejection and housing/carrier removal never grant a fresh countdown. The reactor's saved fallback countdown uses the same seconds as the independent hazard ledger.
- Yellow housing/ring emissives indicate a **60-second projected rise into overheating**. Each completed thermal interval feeds a four-second rolling production average. The server projects current retained heat against each circuit's available cooling capacity, clamps inventories at zero, and applies the live core response. Circuits remain independent; unused fuel credit is not waste. Shutdown stops projected production immediately and uses the shared passive cooldown budget. The forecast runs four times per second and immediately when cooling capacity, connections, generation or containment failure changes.
- Ordinary risk must persist for two simulation seconds to turn yellow; five safe seconds clear it. Failed containment and a forecast reaching 125% bypass confirmation. A 0.1-percentage-point margin rejects numerical noise. Normal warmup toward 100%, stable heat and safe cooldown do not initiate a warning. After reload, production history fills over four seconds; saved warnings retain their recovery hold. These advisory filters never change heat inventories, safety interlocks or detonation timing.
- Terminal heat text, LCD/tablet heat colours, coolant status and instability audio share the server-confirmed warning. The terminal and Containment pages show the 60-second peak, responsible circuit and estimated time to overheating or critical heat. A safe forecast during the recovery hold is labelled as recovering. Fuel starvation is white; critical cores and venting retain red priority. Idle reactor coolant indicators and closed manifold valves use cyan rather than amber.
- The reactor disables native emissive-state handling. In Brayton mode its own electrical source is intentionally idle, which otherwise makes vanilla reactor logic overwrite the mod's fuel colour with yellow even when the thermal forecast is safe.
- A subcritical ejected core fades and disappears after 20 simulation seconds. A supercritical ejected core retains its fuse and peak heat. The reactor reports outstanding ejected-core countdowns in terminal info.

The legacy direct generator has 1/10/100 GW electrical ratings and falls to 10% of the captured load on tile failure. Fuel burn accelerates to 10 times its normal rate. The thermal reactor supplies 5/50/250 GW of fuel input; its mode and connected turbines determine electrical output.

## Explosion scale

Damage is multiplied; radius uses the cube root of the same multiplier. The runtime reads the loaded **large-grid warhead definition**, so another mod's definition changes also change this baseline. Vanilla reference values are 15,000 damage and 22.4415 m definition radius.

| Fuel | Damage multiplier | Vanilla baseline damage | Approximate radius |
| --- | ---: | ---: | ---: |
| I | 5× | 75,000 | 38.37 m |
| II | 20× | 300,000 | 60.92 m |
| III | 100× | 1,500,000 | 104.16 m |

This is one native `MyExplosions.AddExplosion` operation, not dozens of repeated warheads. It includes native force, damage, particles, sound, voxel effects and deformation, subject to engine damage permissions. If enqueueing is refused, the armed core remains and retries. This is a definition-relative balance scale, not a promise of the same destruction as detonating that many adjacent warheads.

## Physical discharge and persistence

The existing direct-script launch carries the payload through the housing and straight duct. After the largest ring has cleared the outlet plane by its radius plus clearance, the server replaces it with native physical objects:

- Two to four rings and the fully assembled tile quartets become **spent floating components**. Seven exported MWM models now include embedded HKT collision; ring and tile frame holes are preserved with compound convex shapes. Native floating-object pickup, gravity, collision, replication and world cleanup apply. Spent parts are not accepted as fresh containment tiles and have no conversion recipe.
- Plasma becomes a hidden, model-backed 3×3×3 small-grid block on a dynamic grid. Its convex sphere collision is approximately 0.6 m radius. It inherits reactor grid motion and gets an outlet launch impulse of at least 30 m/s, plus small randomized lateral/angular motion. Debris receives varied launch/spin impulses too. The core receives native natural gravity and an additional scripted artificial-gravity force.
- The physical handoff uses the same pose functions as the visible subparts, including on a dedicated server. Original visual parts are hidden and installed tile stock cleared once. Failed core creation retains the payload for retry instead of silently discarding it.
- `CoreHazards.cs` stores heat, peak heat, fuse, source/carrier IDs and position in `ArcanePower-CoreHazards.xml` in world storage. The hazard is independent of the physical entity: grinding/removal of its carrier cannot defuse it; an armed orphan detonates at its last known location. Source destruction likewise does not cancel an in-housing hazard.
- Core snapshots synchronize late joins and client plasma lights. Only the server creates physical entities, consumes resources and requests explosions. The reactor retains its existing saved/synchronized motion state.

Venting still damages the reactor and compatible attached modules once, based on captured load/heat, and ends **off until manually restarted**. Because heat can now exceed 100%, vent damage can exceed the previous healthy-heat 15%/20% maxima. Saved vent damage flags still prevent applying that damage twice.

Moving-door collision, arbitrary roof obstructions, damaged routes after vent commitment, elbows, regulated venting and automatic emergency venting remain unfinished. Native floating-object cleanup may remove spent parts; it cannot remove the independent critical countdown.

## Asset delivery

The plasma uses a new monochrome filament texture, tinted per fuel at runtime. The sphere is smooth and 1.2 m across inside the existing 1.76 m containment shell. Tile faces now have open centres, thick 45 mm frames and luminous edges, allowing the plasma to show through. Four ring models remain shared across tiers. Native upgrade empties and the reactor housing were not scaled.

- Static Blender material comparison — illustrative lighting; not an in-game screenshot.
- [Art/technical channel authoring](assets/build_physical_plasma.py), [review renderer](assets/render_plasma_review.py), [texture provenance](assets/textures/plasma-filaments-provenance.json).
- Build log, seven model exports and embedded collision evidence (report pruned), local deployment (report pruned).

Next game review must establish native capacity limiting, 10× fuel debits, resupply recovery, overheating and irreversible timers, interior/ejected detonation positions, save/rejoin/removal behavior, physical clearance/gravity, and shader appearance. Compilation and asset export do not establish these runtime outcomes.
