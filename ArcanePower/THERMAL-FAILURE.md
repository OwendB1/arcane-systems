# Thermal failure, physical ejection and plasma — 16 September 2026

Implemented in the local prototype; compiled and exported, **not validated in-game**. No regression suites or game control accompanied this pass. The numerical thresholds below are provisional balance values.

## Accepted behavior

An exhausted maintenance quartet reduces electrical output to **10% of the operating load immediately before failure**, while fuel consumption becomes **10× the normal consumption for that same load**. These are separate multipliers: together they mean 100× the fuel per unit of delivered electrical energy. Idle inventory being empty does not fail a still-serviceable installed shell; failure starts when its next worn quartet cannot be replaced.

The core is the source of the catastrophic explosion. Ejecting it can save the housing by moving the blast away; the housing is not granted blast immunity. Once supercritical, detonation remains inevitable after ejection, shutdown, resupply or cooling. Confirmed behavior: **detonation becomes unavoidable only after the threshold; cooler ejected cores decay**. A tile-starved, unrepaired core continues heating even after electrical shutdown; an armed core remains explosive after ejection.

## Provisional thermal balance

- Healthy heat approaches operating load (0–100%) with the existing 60-second heating / 30-second cooling response.
- Tile wear in quartets/minute is `tierBase × (0.2 + 0.8 × reactionLoad) × (1 + 3 × heat²)`, where tierBase is 1/2/4. At 100% heat, wear is four times its cold value. Eighty initial tiles and four-tile replacement batches remain unchanged.
- Starvation captures the actual electrical load before reduction. The reactor remains running at its reduced capacity; fuel burn uses the captured load, not its now-reduced electrical output. An explicit shutdown or fully closed vent shield stops fuel consumption/output.
- Failed containment heats toward 250–300%, with a 12-second response, even during electrical shutdown. Replacing four tiles before supercriticality stops that runaway. The replacement animation can finish during cooling.
- A warning appears at 100%; **supercriticality latches at 125%**. The in-housing critical reaction heats toward 400%, with the same 12-second response. Mechanism pauses do not pause thermal progression or detonation.
- The saved fuse starts with 45 units. Each simulation second consumes `1 + 4 × max(0, peakHeat − 1.25)` units. At constant 125/150/200/300/400% heat this corresponds to 45/22.5/11.25/5/3.75 seconds. Rising heat shortens it further; cooling never lengthens it. Time pauses with the simulation/world, not wall-clock time.
- A subcritical ejected core fades and disappears after 20 simulation seconds. A supercritical ejected core retains its fuse and peak heat. The reactor reports outstanding ejected-core countdowns in terminal info.

At full pre-failure load, degraded T1/T2/T3 output is 1/10/100 GW, with ten fuel units/minute. Original ratings remain 10/100/1,000 GW.

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

- [Static Blender material comparison](validation/plasma-fuel-review.png) — illustrative lighting; not an in-game screenshot.
- [Art/technical channel authoring](assets/build_physical_plasma.py), [review renderer](assets/render_plasma_review.py), [texture provenance](assets/textures/plasma-filaments-provenance.json).
- [Build log](validation/thermal-ejection-build.log), [seven model exports and embedded collision evidence](validation/physical-plasma-export.json), [local deployment](validation/local-deployment.json).

Next game review must establish native capacity limiting, 10× fuel debits, resupply recovery, overheating and irreversible timers, interior/ejected detonation positions, save/rejoin/removal behavior, physical clearance/gravity, and shader appearance. Compilation and asset export do not establish these runtime outcomes.
