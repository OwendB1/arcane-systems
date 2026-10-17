# Arcane Energy Core

Generated review images and recordings were pruned on 16 October 2026. Review
descriptions below are historical; maintained blends, checkpoints and compact
audit/source reports remain in the repository.

The pillar installation uses a **3×3×3 large-grid core**, with separate
**1×3×1 large-grid capacity, transfer and stabilizer pillars**. The modules retain
a full-block footprint, with curved backs fitted around the chamber. The seven blocks have models,
icons and three construction stages each. Model and stage sheet.

The storage family shares the reactor's segmented round housings, machined
collars, clear curved chamber glass and recessed service hardware. All four core
faces and the six module variants use the original, unscaled SE upgrade port.
Full-height docking supports connect the compartment backplates to the core,
with inter-bay bulkheads, power buses and coolant fittings behind the equipment.
The [storage blueprint](workshop/images/energy-blueprint.png) shows a mounted bank.

Distance meshes were refreshed from the current seven mains on 15 October 2026.
They preserve glazing and charge/status surfaces while reducing equipment detail
at 75 and 150 m. The small fan and driven field retain their exact main meshes.
All 21 current construction stages keep their validated exported bytes.
[Current native delivery](validation/current-model-export.json).

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
cells. It never changes shared definitions or copies charge between storage cells.
Upkeep consumes each physical cell's charge; a surge debits those cells and credits
one jump drive through the public Mod API.
Charging demand follows actual stored charge through the public resource sink,
so a previously full cell can replenish upkeep and direct surge debits even when
the native battery's internal full flag has not yet changed.
Consequently, an empty cell's unused output allowance is not redistributed to
other cells. Native capacity and availability limits may reduce actual transfer.

Native Auto/Recharge/Discharge modes are selected on the core and applied to its
active capacity modules. Charging uses the native 90% recharge multiplier. New,
projected and copied storage starts empty. Saved block IDs retain their own
charge; detaching a module preserves its charge but disables transfer. Destroying
that battery loses its stored energy. Creative mode retains native creative
battery behavior; conservation claims apply to survival.

The normal battery details can display the definition's 2 TW burst maximum. The
**ARCANE ENERGY STORAGE** custom information reports the bank ceiling and each
cell's effective input/output limits. Actual transfer still depends on grid demand
and supply. Vanilla batteries remain usable for reactor startup and backup.

## Gameplay loop — implemented 14 October, provisional balance

Generate power, accumulate a reserve, spend energy on rapid jump-drive charging
or burst discharge, then recharge while the equipment recovers. Capacity extends
endurance, transfer modules shorten surge time, and stabilizers reduce both
storage upkeep and recovery. A charged bank can also operate a ship with its
reactor shut down. Docked grids exchange ordinary electrical power through the
native connector/grid system; connected grids remain separate storage banks.

### Stored-energy upkeep

Every cell loses stored charge during simulated survival time, including while
disabled, unfinished or detached. Loss rises quadratically with that cell's fill:
half-full costs one quarter of full-cell upkeep. More capacity can spread stored
energy over a larger installation. Supported cells receive their active bank's
stabilizer reduction; isolated cells use the bare rate.

| Stabilization | Full-cell loss per minute | Full 1,000 MWh cell upkeep | Recovery after ability ends |
| --- | --- | --- | --- |
| Bare | 1% | 600 MW equivalent | 120 s |
| Standard | 0.5% | 300 MW equivalent | 90 s |
| Advanced | 0.25% | 150 MW equivalent | 60 s |

Loss comes from stored energy rather than an additional grid sink. A generator
replaces it through normal battery charging, including native charging losses.
The emergency reserve protects discharge and surge spending; passive upkeep
can consume it. There is no loss while the simulation is paused/unloaded, no
wall-clock catch-up, and no upkeep debit in creative worlds. Custom information
reports cell/bank upkeep, approximate net flow and reserve endurance at current
flow. Fractional native float rounding is carried between upkeep updates.

### Jump-drive surge

Select a drive in the core's **Surge target** list, then use **Surge jump drive**
in the terminal or toolbar. Automatic selection chooses an available drive in
stable entity-ID order. Only one fully built, enabled, accessible drive on the
same physical grid is eligible; its Recharge switch must be on and it must not
be jumping. The bank must be in Auto or Discharge.

Bare/standard/advanced transfer tiers target a full charge in **10/7.5/5 seconds**.
Only missing charge is transferred, at approximately 90% efficiency subject to
native float precision. Actual stored energy funds every increment. Surging
shares the normal bank transfer ceiling with grid output and holds back the
emergency reserve plus an allowance for native output already committed in its
100-tick accounting interval. Heavy demand or insufficient energy can stop the
surge with partial charge retained; ordinary drive recharging then continues.

The normal jump countdown, range and jump restrictions still apply. The bank
and drive enter recovery when the surge starts, lasting the surge window plus
the stabilization-dependent recovery above. Drive recovery belongs to the
physical drive, preventing another bank from surging it during recovery. Losing
access, grid connection, hardware, Recharge eligibility or bank discharge mode
stops further transfer without refunding energy already spent.

### Burst discharge and controls

**Burst discharge**, available in the terminal and toolbar, doubles output for
**10 seconds**: 20 GW / 200 GW / 2 TW at the three transfer tiers. Charging stays
at its normal ceiling and native energy availability still limits actual output.
Burst and surge share bank recovery, so they cannot be chained immediately.
Burst ends when the core becomes unavailable or enters Recharge. Normal bank
operation continues during recovery. Reactor containment support stops either
ability and keeps its existing reserve-release behavior.

The core terminal also exposes an **Emergency reserve** slider and **Reactor
emergency support** switch. These edit the existing INI settings below while
preserving other valid Custom Data. Invalid non-INI Custom Data is left intact
and reported. Cooldowns and active operations are saved against physical entity
IDs; projected/copied banks start with fresh operation state. Server-authorized
commands validate bank access and target eligibility. Server snapshots provide
client/late-join operation state and stored-energy feedback.

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

The 15 October texture pass adds finer native surface grain, individual panel
UV origins, restrained edge wear, supported side welds and isolation/lift
markings. Standard module warning strips are yellow; advanced strips are white.
Existing native paint masks, normal/gloss textures and atlas UVs remain in use.
The construction copies carry the matching surface treatment.
Texture preview and
[geometry/backing audit](validation/native-texture-detail/energy-audit.json).

The current main-model authoring pass is saved in `assets/arcane-energy-core.blend`,
with separate assembled and individual reviews in `assets/arcane-energy-core-review.blend`.
It adds recessed side service doors and intake banks to all six modules, bolted
cell retention rails, transfer-bus terminals and coolant manifolds, and chamfered
fan carriers. The core has alternating drum access panels/louvers, flush deck
pulls and supported coolant brackets. Structural edges use single-segment
chamfers. Each mating face has three unscaled native ports at 2.5 m pitch.
Further main-only loops add faceted lifting decks, corner gussets, split bolted
cell bands, thin flat fan guards, seated equipment backplanes and denser radiator
packs. Cell terminals now use plated straps, washers and mapped stud heads;
radiators have manifold returns/isolation valves and fans have supported motor
wiring. Matte-backed native equipment codes remain readable at close range.
Eight small chamber-end injectors preserve the moving-ring clearance.

Review-copy offsets were repaired by evaluating both scenes before reading
transforms. All eleven assembly copies retain matching poses after reload; the
production file contains only the authoring scenes. Collision, subparts, LODs and
construction geometry were verified unchanged during the main-model sync.
Main-model sheet,
repaired comparison,
service-door close-up
and [geometry audit](validation/energy-geometry-audit.json).
The 15 October dock pass replaces separate socket rails with closed clipped
receivers and opaque native-port backs. Three compact tapered housings per core
face and curved drum roots seat the docks into the enclosure while retaining
80 mm chamber intrusion. Eight chamfered saddles now fit the curved drum to the
straight dock cheeks, with 45 mm back seating and a 10 mm front reveal.
Both drums' 48 redundant structural bolts and oversized gasket plates are
removed. The 24 service stations have actual armor apertures, recessed floors and
support ledges; doors sit 3 mm below the skin and louvers seat at their ends.
All 48 retained captive screws fasten the access doors. Armor segment gaps are
14.4 mm rather than 180 mm. Structural surfaces use native SEUT materials and UVs,
with white native lettering on BlackMattePlastic. Missing packed alpha channels
in local SEUT preview textures were restored from the installed game DDS files;
game textures and mod texture dependencies were unchanged.

All seven main models are exported and connected to the local prototype mod as
`Models/Cubes/large/energy_87c3644f9849`. Native imports match source triangle
counts, sockets, subparts and texture dependencies; accepted collision bytes and
existing build stages remain unchanged. Geometry checks include 750 socket-back
rays, 144 door-ledge and 192 louver-end support samples, 48 screw seating checks,
216 aperture checks, and 80 saddle-to-armor/cheek checks. Production and all eleven review assemblies
pass fresh-load checks. No game reload or live validation of this art revision
has been performed. Further LOD work remains deferred. The updated battery
construction stages below are exported in the same active family.
Top saddle,
bottom saddle,
service recess,
engineer-scale inspection
and [native export proof](validation/energy-main-export.json).

Stored fraction controls field radius, glow intensity and four fill markers.
Radius interpolates from 18% of the authored size when empty to 100% when full,
with the field pivot and surrounding rings fixed. An offline field retains its
stored-energy size while its emissive switches off. Cyan indicates
charging, amber discharge and blue idle. The sphere uses a dedicated continuous
emissive material. Seated status strips share these colors; transfer/stabilizer
strips extinguish when detached or inactive. Three physical stabilizer fans turn
at 45 rpm around their native local shafts while the accepted bank is active.
Two hoops reuse the reactor’s Ring3/Ring4 models and the same
tilt, axial spin and secondary-axis transform code, including the reactor's
time-varying secondary rotation rate. Battery transfer utilization sets their
smoothly changing speed; an offline core slows them to a stop. The modulation clock
continues across cosmetic tick wraps and outside the drawing range. Offline
or disconnected cells extinguish their glow and fill markers. Drawing stops
beyond 300 m while cosmetic phases continue; emissives refresh six times per second. This is independent of the reactor's restored original dark, static core
texture. No reactive plasma was reintroduced.

All twelve public Arcane Power blocks now have three native construction models,
36 stages total. Welding and grinding choose stages from native build progress.
Damage lowers integrity independently of build progress, so these are not a
custom damage-mesh system. Existing accepted reactor collisions are preserved.

The 15 October battery revision rebuilds all 21 stages from the current main
models: channel frames and three receiver stations, mounted machinery, then
whole partial-armor assemblies. Modules use their current post positions, cell
clamps, buses, radiators, fan carriers and wiring. Stabilizer stages include
static physical fan blades at the authored shaft poses. Stage three installs
one complete module side and upper deck with its fittings; the core retains
whole service assemblies around open drum sectors. Construction machinery fits
inside the lower drum. Glazing, powered lamps, charged fields, animation dummies
and LOD references are absent. Finished art and accepted collision are preserved.
[Construction export proof](validation/energy-construction-update/native-export.json)
checks all 21 native models, bounds, materials, texture dependencies, collision
bytes and active definitions. [Distance review](validation/energy-construction-update/distance-review.json)
records 1.8, 2.4 and 3.0 m inspections. Live welding/grinding still needs game review.

## Verification and remaining release work

The new upkeep/surge/burst policy checks exercise shipped methods against API
doubles: fill-dependent loss and tier reductions, disabled/detached loss, server
authority, native float rounding, funded full drive charge, reserve/throughput
bounds, target access/grid/mode checks, shared recovery, saved bank/drive recovery,
copied identities, charging demand after direct debits, burst ceilings and
containment priority. Run the focused path
with `python3 ArcanePower/tools/check_energy_core.py --policy-only`; it skips
unrelated model/animation checks. The compatibility build checks Mod API whitelist
and SE's injected imports. These checks do not establish live behavior; gameplay,
native accounting under sustained load and multiplayer/late join remain pending.

The connected-dock revision reuses the reactor's Ring3/Ring4 MWM files byte for
byte. Shared transform checks preserve the reactor's startup and shutdown poses
and seamless phase wrapping. The live client recorded both battery ring matrices
changing across six samples, with both native upgrade connections and the
111,000 MWh / 1 TW bank intact. The continuous sphere material was tuned in-game
to retain its state colour while glowing. All seven models, 21 construction
stages and the 259-file release package passed their checks. See
[detail evidence](validation/energy-detail.json) and the
live view.

The three-cell pillar revision passed native model/socket and all 21 stage checks,
plus placement policy checks across all 24 cardinal orientations. The isolated
pillar world verified both native upgrade connections, 111,000 MWh mixed capacity,
a 1 TW ceiling, the 12 MW test load and front-stabilizer disable/re-enable. The
original compact save also reloaded with its geometry, connections and charge
preserved. See [pillar evidence](validation/energy-pillars.json), the
live bank and the updated blueprint above.


The 14 October refinement passed native socket/mating and model-bound checks for
all seven finished models, plus embedded collision checks for all 21 build stages.
In the isolated survival world, both native upgrade modules report one connection;
the mixed bank retains 111,000 MWh capacity, a 1 TW ceiling and supplies the native
12 MW test load. Stabilizer disable/re-enable and saved-charge reload also passed.
See [refinement evidence](validation/energy-refinement.json) and the
in-game view. This remains a single-client check.

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
