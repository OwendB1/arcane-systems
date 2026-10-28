# Thermal failure, physical ejection and plasma — 28 October 2026

The generated Blender previews mentioned below were pruned during repository
cleanup on 16 October 2026. Maintained models, texture sources and runtime assets
remain unchanged.

Implemented in the local prototype; **the revised physical lifecycle is not yet validated in-game**.
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
- New supercritical cores receive a fixed **60 simulation seconds** before detonation. Rising heat cannot accelerate this countdown, and cooling cannot extend it. This leaves about 55 seconds beyond the five-second shield/intake/ejection sequence; broken vents or exhausted actuation power can still delay ejection. Controller failure alone does not block the launch: stored containment reserve powers it, and the physical handoff requires a paid actuation step. Time pauses with the simulation/world, not wall-clock time.
- Legacy armed cores convert their old heat-weighted fuse to its remaining seconds once. Reload, shutdown, core ejection and housing/carrier removal never grant a fresh countdown. The reactor's saved fallback countdown uses the same seconds as the independent hazard ledger.
- Yellow housing/ring emissives indicate a **60-second projected rise into overheating**. Each completed thermal interval feeds a four-second rolling production average. The server projects current retained heat against each circuit's available cooling capacity, clamps inventories at zero, and applies the live core response. Circuits remain independent; unused fuel credit is not waste. Shutdown stops projected production immediately and uses the shared passive cooldown budget. The forecast runs four times per second and immediately when cooling capacity, connections, generation or containment failure changes.
- Ordinary risk must persist for two simulation seconds to turn yellow; five safe seconds clear it. Failed containment and a forecast reaching 125% bypass confirmation. A 0.1-percentage-point margin rejects numerical noise. Normal warmup toward 100%, stable heat and safe cooldown do not initiate a warning. After reload, production history fills over four seconds; saved warnings retain their recovery hold. These advisory filters never change heat inventories, safety interlocks or detonation timing.
- Terminal heat text, LCD/tablet heat colours, coolant status and instability audio share the server-confirmed warning. The terminal and Containment pages show the 60-second peak, responsible circuit and estimated time to overheating or critical heat. A safe forecast during the recovery hold is labelled as recovering. Fuel starvation is white; critical cores and venting retain red priority. Critical housing/ring emissives and coolant status blink red once per second, overriding the yellow warning and its recovery hold. Idle reactor coolant indicators and closed manifold valves use cyan rather than amber.
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

**Test vent shields** is a separate dry run available in the control panel and toolbar. It lowers and retracts the shields with the hatch closed, without releasing payload or shutting down a running reactor. Working controllers and containment power/reserve are required; a vent route is not. Real ejection takes priority over an active test.

The existing direct-script launch carries the payload through the housing and straight duct. After the largest ring has cleared the outlet plane by its radius plus clearance, the server replaces it with native physical objects:

- When venting before plasma forms, two to four rings and the fully assembled tile quartets become **spent floating components**. Seven exported MWM models include embedded HKT collision; ring and tile frame holes are preserved with compound convex shapes. Native floating-object pickup, gravity, collision, replication and world cleanup apply. Spent parts are not accepted as fresh containment tiles and have no conversion recipe.
- Every ejection with plasma keeps those same ring/tile models rigidly attached to one plasma carrier, including subcritical ejections. Subcritical carriers and their attached shells disappear after the existing 20-second decay; critical carriers retain their detonation countdown. Their actual handoff poses are saved and replicated; they are visual subparts, not independent floating objects. The existing spherical core collider owns physics. Critical carriers are noneditable and indestructible until detonation, including carriers restored from older saves.
- Plasma becomes a hidden, model-backed 3×3×3 small-grid block on a dynamic grid. Its convex sphere collision is approximately 0.6 m radius. It inherits reactor grid motion and gets an outlet launch impulse of at least 22.5 m/s along the tube axis, plus small randomized lateral/angular motion. Longer ducts use half their previous scripted exit velocity, including the 1.5× ejection-speed multiplier. Lateral launch scatter is also halved; inherited ship velocity and angular spin are unchanged. The ready physics body receives its launch velocity directly. Debris receives varied launch/spin impulses too. The core receives native natural gravity and an additional scripted artificial-gravity force.
- The physical handoff uses the same pose functions as the visible subparts, including on a dedicated server. Original visual parts are hidden and installed tile stock cleared once. Failed core creation retains the payload for retry instead of silently discarding it.
- All vent stages run at 1.5× speed: approximately 2.67 s shield closing, 1 s opening, 1.33 s launch, 1 s closing and 2.67 s shield retraction (8.7 s total). The original authored launch clock retains a fractional tick for smooth motion and compatible mid-ejection saves. A failed physical handoff holds the final launch pose until creation succeeds. Speed changes never shorten the critical fuse or bypass outlet clearance.
- `CoreHazards.cs` stores heat, peak heat, fuse, source/carrier IDs, position, rotation, velocities and attached shell poses in `ArcanePower-CoreHazards.xml`. A removed critical carrier is recreated at its last pose with its saved velocity and remaining fuse. If an armed source housing disappears, its hazard likewise becomes a physical ball instead of a stationary invisible bomb. Expired fuses never reset, and a refused explosion enqueue retains its hazard for retry. Logs record source/carrier IDs and the actual blast position.
- A housing that becomes nonfunctional while it contains plasma releases a ball at the core position, inheriting ship velocity without any launch impulse. This requires neither controllers nor a working vent route. The vessel's existing collision traps the ball until the vessel is opened or destroyed. Both critical and subcritical balls retain their assembled tiles and rings at the handoff poses. Critical balls keep the same countdown; subcritical balls and their shells decay normally. Successful handoff clears the reactor's contained state once, so it cannot spawn a second copy.
- Core snapshots synchronize late joins and client plasma lights. Only the server creates physical entities, consumes resources and requests explosions. The reactor retains its existing saved/synchronized motion state.

Contained heat at or above 125% damages the vessel and attached containment controllers once per simulation second. The rates are `0.135% × (heat − 1)` and `6% × (heat − 1)` of maximum integrity respectively, with heat expressed as a fraction. At 125% this is 0.03375% vessel integrity and 1.5% controller integrity per second; at 200% it is 0.135%/6%. The vessel rate is calibrated to the current housing's component-derived 85.98% functional cutoff: starting at full integrity and 125% heat, the normal 12-second heat response toward 400% makes it nonfunctional at 45 seconds, leaving about 15 seconds on the unchanged detonation fuse. Prior damage, repairs and damage modifiers can change this timing. Controllers keep their separate rate and may become nonfunctional sooner, but ejection remains available with an intact vent route and sufficient containment reserve. No heat damage applies below 125%, after physical release, or to a nonfunctional vessel while physical creation is being retried. The existing core heat gauge drives this rate; no separate vessel-temperature simulation is introduced. Damage crossing the functionality threshold immediately attempts physical release.

Venting has no additional damage penalty and ends **off until manually restarted**. The old saved vent-damage fields are retained for compatibility but are no longer used. Ejection stops scripted heat damage; it does not protect the ship from a nearby core's actual blast. Blast position follows the carrier, while reactor ownership is used only for damage attribution. The explosion does not set a source-grid exclusion through SE's turret friendly-fire setting.

Moving-door collision, arbitrary roof obstructions, elbows and regulated venting remain unfinished. Native floating-object cleanup may remove ordinary spent parts; it cannot remove the independent critical countdown.

`python3 ArcanePower/tools/check_meltdown.py` runs focused checks of the production release, tracking, damage and explosion methods with recording engine doubles and native math. It covers critical/ordinary ejection, exact shell poses, duplicate prevention, failed creation/retry, housing failure, carrier recovery, XML/protobuf persistence, server authority, blast location and refused explosions. It does not establish live collision clearance or rendering behavior.

## Asset delivery

The plasma uses a new monochrome filament texture, tinted per fuel at runtime. The sphere is smooth and 1.2 m across inside the existing 1.76 m containment shell. Tile faces now have open centres, thick 45 mm frames and luminous edges, allowing the plasma to show through. Four ring models remain shared across tiers. Native upgrade empties and the reactor housing were not scaled.

- Static Blender material comparison — illustrative lighting; not an in-game screenshot.
- [Art/technical channel authoring](assets/build_physical_plasma.py), [review renderer](assets/render_plasma_review.py), [texture provenance](assets/textures/plasma-filaments-provenance.json).
- Build log, seven model exports and embedded collision evidence (report pruned), local deployment (report pruned).

Next game review must establish native capacity limiting, 10× fuel debits, resupply recovery, overheating and irreversible timers, interior/ejected detonation positions, save/rejoin/removal behavior, physical clearance/gravity, and shader appearance. Compilation and asset export do not establish these runtime outcomes.
