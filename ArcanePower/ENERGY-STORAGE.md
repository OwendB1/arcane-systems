# Arcane Energy Core

The pillar installation uses a **3×3×3 large-grid core**, with separate
**1×3×1 large-grid capacity, transfer and stabilizer pillars**. The modules retain
a full-block footprint, with curved backs fitted around the chamber. The seven blocks have models,
icons and three construction stages each. [Model and stage sheet](validation/energy-core-stages.png).

The storage family shares the reactor's segmented round housings, machined
collars, clear curved chamber glass and recessed service hardware. All four core
faces and the six module variants use the original, unscaled SE upgrade port.
The [storage blueprint](workshop/images/energy-blueprint.png) shows a mounted bank.

## Placement and provisional balance

Place modules at the center of the corresponding core face, two grid cells from
the core's center. Each module's connector/Forward face must point toward the
core, and its Up direction must match the core. All pillars stand upright; the
stabilizer occupies the front socket. Modules must be fully welded, functional, enabled, accessible to the core
owner and on the same physical grid. Connector-linked grids do not form a bank.

Native `detector_upgrade` sockets mate at the grid faces. Transfer and stabilizer
blocks advertise native upgrade compatibility with the Energy Core. Capacity
modules remain batteries; the bank's existing placement, access and tier checks
still control all allocations. Native connection feedback alone does not bypass
the required socket role or stabilizer tier.

| Block | Position | Capacity or capability |
| --- | --- | --- |
| Energy Core | Center | 1,000 MWh; base 10 GW bank transfer |
| Capacity Module | Left/right; up to two | +10,000 MWh each |
| Advanced Capacity Module | Left/right; up to two | +100,000 MWh each |
| Transfer Module | Rear; one | 100 GW bank transfer |
| Advanced Transfer Module | Rear; one | 1 TW bank transfer |
| Stabilizer | Front; one | Supports standard modules |
| Advanced Stabilizer | Front; one | Supports standard and advanced modules |

The bare core operates without a stabilizer. Both capacity sockets may use the
same tier or mixed tiers. Losing the stabilizer disables unsupported expansions;
losing the transfer module restores the base transfer ceiling. Component costs,
capacity, PCU and transfer ratings are provisional. Ratings align with the
reactor's 10/100/1,000 GW tiers; they are not final survival balance.

## Existing compact banks

Previously placed 3×3×3 cores and one-cell modules retain their original geometry,
sockets, capacities and stored charge. Their definitions are hidden from the build
menu; new construction uses the pillar family. Compact banks still use a top
stabilizer. Compact and pillar modules cannot be mixed.

## Native energy accounting

Each storage cell is a native battery with fixed capacity. The core reports the
aggregate and divides the bank transfer allowance proportionally among attached
cells. It never changes shared definitions or copies charge between batteries.
Consequently, an empty cell's unused output allowance is not redistributed to
other cells. Native capacity and availability limits may reduce actual transfer.

Native Auto/Recharge/Discharge modes are selected on the core and applied to its
active capacity modules. Charging uses the native 90% recharge multiplier. New,
projected and copied storage starts empty. Saved block IDs retain their own
charge; detaching a module preserves its charge but disables transfer. Destroying
that battery loses its stored energy. Creative mode retains native creative
battery behavior; conservation claims apply to survival.

The normal battery details can display the definition's 1 TW maximum. The
**ARCANE ENERGY STORAGE** custom information reports the bank ceiling and each
cell's effective input/output limits. Actual transfer still depends on grid demand
and supply. Vanilla batteries remain usable for reactor startup and backup.

## Emergency reserve

Core Custom Data accepts:

```ini
[ArcaneEnergyCore]
ReservePercent=10
EmergencySupport=true
```

ReservePercent is clamped to 0–90. The default holds 10% in every cell. An
accessible Arcane reactor on the same grid requesting startup, cooling, stopping
or venting releases that reserve. A cold reactor requests startup support only
after initialization, with a complete functional reactor, both complete controllers,
usable fuel and a valid vent route. Damaged reactors already cooling or venting
can still request support. If the core was in Recharge it visibly switches
to Auto and stays Auto afterward. Set EmergencySupport=false to disable both
reserve release and that mode override. The core must remain enabled and fully
built to supply power.

Released reserve supplies the native grid. It is not an exclusive power channel
to containment; competing loads can consume it. The native 100-tick battery
accounting interval bounds the output permitted near the reserve threshold.

## Visuals and construction

Stored fraction controls glow intensity and four fill markers. Cyan indicates
charging, amber discharge and muted blue idle. The core has a slow rotating
subpart. Offline or disconnected cells extinguish their glow and fill markers;
an offline core stops rotating. Visual updates stop beyond 300 m, and emissives
refresh six times per simulation second. This is independent of the reactor's restored original dark, static core
texture. No reactive plasma was reintroduced.

All twelve public Arcane Power blocks now have three native construction models,
36 stages total. Welding and grinding choose stages from native build progress.
Damage lowers integrity independently of build progress, so these are not a
custom damage-mesh system. Existing accepted reactor collisions are preserved.

The 12 October art revision replaces the original thin outlines and solid
intermediate boxes with vanilla-inspired channel frames, diagonal bracing,
mounted cells/transformers/coils and partial armor. The last Energy Core stage
shows a static, unpowered central assembly; the finished block retains its
existing animation and materials. The 14 October refinement replaces the storage
main models and carries their native sockets and machinery into the build stages.
Standard and advanced modules have different cell, bus or winding arrangements.
The reactor models and collision geometry are unchanged.

## Verification and remaining release work

The three-cell pillar revision passed native model/socket and all 21 stage checks,
plus placement policy checks across all 24 cardinal orientations. The isolated
pillar world verified both native upgrade connections, 111,000 MWh mixed capacity,
a 1 TW ceiling, the 12 MW test load and front-stabilizer disable/re-enable. The
original compact save also reloaded with its geometry, connections and charge
preserved. See [pillar evidence](validation/energy-pillars.json), the
[live bank](validation/energy-pillars-live.png) and the updated blueprint above.


The 14 October refinement passed native socket/mating and model-bound checks for
all seven finished models, plus embedded collision checks for all 21 build stages.
In the isolated survival world, both native upgrade modules report one connection;
the mixed bank retains 111,000 MWh capacity, a 1 TW ceiling and supplies the native
12 MW test load. Stabilizer disable/re-enable and saved-charge reload also passed.
See [refinement evidence](validation/energy-refinement.json) and the
[in-game view](validation/energy-refined-live.png). This remains a single-client check.

The SE compatibility build passes with zero warnings/errors. Focused policy
checks cover tiers, total transfer allocation, native output resets, reserve
limits, emergency modes, access, orientation, incomplete/disabled hardware and
detachment. The 13 October hardening also checks immediate removal of old module
allocations, disabled/incomplete native output resets, client mode authority,
startup reserve eligibility and the full-build generation interlock. The shared
menu check verifies all twelve Power blocks alone and all 36 combined Arcane
Systems blocks through the native category merger. Native model import checks cover all 36 stages, embedded collision,
bounds and construction materials.

The isolated survival world loaded the family without mod compilation errors.
It measured a 111,000 MWh mixed bank and 1 TW source ceiling, supplying a native
12 MW charging battery. Disabling/restoring the stabilizer removed/restored the
expansions and retained their energy. A deliberately mismatched copied identity
reset to zero charge. The subsequent save contains the updated native charge and
matching identity markers. [Evidence](validation/energy-runtime.json).

The interrupted saved-charge reload was completed on 14 October; all three cells
retained their saved energy. A separate dedicated-server launch stopped before loading mods because
the Wine environment lacks the required C++ redistributable. Dedicated operation,
two-client replication/late join, live ownership changes, splits/merges,
projection/grinding, sustained rated load, emergency contention and distance
performance remain release gates. Policy doubles do not establish those live
behaviors. Source inspection of the local Ship Core Framework finds its producer
multiplier targets reactors, not batteries; combined-mod gameplay is unverified.

Rebuild checks with `python3 ArcanePower/tools/check_energy_core.py` and
`python3 ArcanePower/tools/check_construction_stages.py`. The disposable world
generator is `tools/prepare_energy_lab.py`; it refuses to overwrite an existing
world and installs its separate instrumentation mod only for that world. Use
the host's native save path when loading through SE Remote. First XML load may
require the game's format-conversion acknowledgment.

`python3 ArcanePower/tools/package_release.py` prepares an unpublished alpha ZIP
under `.cache/release/` and writes `validation/release-manifest.json`. It follows
native MWM subparts/material dependencies and omits authoring files, obsolete
model families and the validation harness. See [release notes](RELEASE.md).
