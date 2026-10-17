# Arcane Power — remaining implementation work

Generated review captures were pruned again on 17 October 2026. Historical inspection
descriptions below remain; current blends, checkpoints and compact audit reports
are retained.

Updated 17 October 2026 after native thermal export and local packaging.
The current status below supersedes the historical delivery notes that follow;
the [full plan](arcane-power-plan.md) retains the wider design direction.

## Current status

- **Native thermal delivery, 17 October:** all 31 thermal block definitions and
  native mains, 24 moving subparts, 93 construction models and 174 LODs are installed
  locally and packaged in the unpublished 0.1.0 ZIP. All 322 native meshes pass
  exact evaluated triangle counts, collision-byte, material and dependency checks.
  Manifold rest frames and both train variants' shaft pivots/orientations pass.
  Custom glass now uses uniform CA/NG textures instead of window-edge dirt.
  The 120 external pressure pipes share the reactor struts' smoked glass and metal
  finish, with 355 fitted rings; telescopic sleeves keep their unobstructed glands.
  All 31 thermal icons were refreshed. Reactor tubes retain metal backing and
  guard rails; weld stages retain opaque supporting pipe bodies. CO₂ supply is
  integrated into powered commissioning. Native assets supersede the earlier
  export gates below; live SE rendering, commissioning and multiplayer validation
  remain pending. [Delivery check](../ArcanePower/validation/thermal-models/delivery-check.json).

- **Flow and emissives, 16 October:** all 31 thermal mains have separate hot,
  return and status materials. Server-derived circulation drives liquid streaks,
  gas wisps, internal coolant risers and four chamber injectors. A 122-block
  room-perimeter example uses existing grid-sized conduit pieces. Capped spurs,
  standby branches and invalid connections carry no visible flow; reactor
  indicators retract with the manifolds. Compatibility compilation, 1,323,383
  runtime checks, geometry/backing audits, 47 manifold poses and live three-distance
  reviews pass. The saved Blender source includes isolated moving previews.
  Native exports/definitions are delivered; live game appearance remains pending.
  [Flow review](../ArcanePower/validation/thermal-models/flow-emissives-review.json).

- **Construction guidance, 16 October:** SCF-style preview facing/rotation arrows,
  H/C socket markers, contextual build instructions and assembly verification
  are implemented for thermal blocks. Checks distinguish placement alignment,
  complete construction and authoritative operating status; missing recovery,
  cooling, welding and malformed joints remain actionable. The focused checks
  cover the authored layout and all 24 grid orientations. Native assets are delivered;
  in-game HUD/commissioning validation remains pending. See the
  [construction guide](../ArcanePower/THERMAL-CONSTRUCTION.md).

- **Transparent pipes and turbine internals, 16 October:** the 30 non-reactor
  mains use native clear pressure walls on conduits/fluid headers. Both train
  variants have hollow inspection windows, six dense turbine rotor rows (384
  blades) interleaved with six fixed vane rows, and six independent compressor
  rotor rows (336 blades) with seven fixed vane rows. End-plenum piping feeds
  the front and exhausts at the rear; accepted external side sockets stay fixed. Source rebuilds retain the visibility pass. Server
  rotor state follows paid heat and a gameplay pressure estimate, with smooth
  spool/coast, save identity and client synchronization. Native subparts and
  thermal definitions are delivered; in-game motion remains pending. See the
  [runtime contract](../ArcanePower/THERMAL-RUNTIME.md).

- **Thermal runtime prototype, 16 October:** separate C# subtype logic now covers
  20% standalone / 40–78% Brayton, shutdown/drain/move mode transitions, manifold
  poses, physical socket checks, per-block heat, native output/fuel accounting,
  dispatch and paid startup/cooldown circulation. Focused kernel/layout checks
  pass; existing direct-electric definitions are preserved. Native model exports and
  thermal definitions are delivered; live multiplayer/runtime validation remains a gate.
  [Implementation and boundaries](../ArcanePower/THERMAL-RUNTIME.md).

- **Brayton main models and textures, 16 October:** all eight machines and 22
  typed pipe/transition pieces now have native SEUT surface textures, supported
  atlas details, service hardware, fasteners and pressure markings. Premium
  hot-end stencils use 2200 C. Procedural rebuilds preserve the finished phases
  and assembly instances. Close UI inspection and saved-file geometry, UV,
  backing and grid/socket checks are recorded in the
  [review evidence](../ArcanePower/validation/thermal-models/REVIEW.md).
  Native exports and LODs/build stages are delivered; thermal world validation remains pending.
  A second asset/detail loop sharpens housings to at most 3 mm flat chamfers,
  gives fasteners faceted normals, reduces the flange joint to 28 mm and packs
  the train, heater vessels, exchanger plates and radiator tiles more closely.
  Supported angular brackets and fitted native details replace the loose
  blockout spacing; the original grid/socket contract is preserved.

- **Reactor manifold repair, 16 October:** original curved lower armor now splits
  and slides under adjacent panels, hiding two-stage primary pipe heads in
  standalone mode. Four bays flank the two native controller slots. A one-cell
  transition mates the native band height to the standard pipe lattice. The
  mechanical preview passes 47 sampled positions and close UI review at
  1.8/2.4/3.0 m. Original production sources remain protected. Native moving
  subparts/collision are delivered; in-game mode validation remains pending. Rounded twin-bore
  castings and moving rear connectors now tie the deployed pipes into the shell;
  both controller recesses and their lower notches are restored. Standalone/Brayton balance targets are
  now 20% / up to 78% net. [Current source](../ArcanePower/assets/arcane-thermal-models.blend).

- **Modular Brayton study, 15 October:** standalone generation targets 20% net; sCO₂ Brayton starts at 40% net,
  with additional recuperators reaching 78% behind hot-end limits. Parallel
  heaters/trains/cooling add capacity and automatic standby; executable examples
  report bottlenecks and worst single-module loss output. Distinct atmospheric
  fan cooler and two-sided space radiator replace the combined cooler. The former
  topping converter is removed from the active design/models. Editable premium
  hardware, branching conduit and a three-train bank accompany the four
  environment/grade layout studies. The separate runtime prototype now exists;
  native exports are delivered and world validation remains pending. The extraction geometry
  is superseded by the current curved-panel manifold variant. [Design and models](../ArcanePower/THERMAL-POWER.md).

- **Native texture detail, 15 October:** reactor, both controllers, battery and
  all six modules now use finer metric UVs, varied panel origins, restrained
  edge scuffs, native weld seams and supported warning markings. Battery stage
  surfaces match their installed backing. Geometry, native interfaces, collision,
  LODs and driven materials are preserved. New native MWMs are connected locally;
  fresh-load review verifies all eleven battery preview assemblies. In-game
  inspection remains pending. Preview.
- **Controller main-model detail, 15 October:** standard now has a broad service
  cassette and passive cooling bank; advanced has paired power cartridges,
  connected buses, seated heat spreaders and extra cooling. Both have native
  atlas fasteners, recessed tier indicators and top/side detail. Curved adapters,
  mating anchors, collision and construction art are preserved. Mounted and
  standalone views were inspected at 1.8, 2.4 and 3.0 m; controller and reactor
  geometry gates pass. Receiver rims now clear the casing by 6 mm, and covers
  clear their lower shoulders by at least 4.5 mm. Saved art is exported and
  connected to the local mod; game review remains pending.
  Comparison.
- **Reactor exterior review, 15 October:** saved main housing now has varied
  lower service bays, a continuous upper cooling belt, and detailed chamfered
  pillars. Accepted pillar proportions and roof seats are retained. Lower feet
  are stepped and inset within the supporting collar. Coplanar status parts now
  use real recesses and separated backing/emitter depths. New pitched dispenser
  surrounds meet the ceiling and curved glass retainer. Live views at 1.8, 2.4
  and 3.0 m were inspected; geometry/support/clearance checks pass. Protected
  dispensers, interfaces, chamber, moving parts, collision and derived art remain
  unchanged. Native export passes for all 23 prototype models, connected through
  fresh local paths under `reactor_787f4951767a` (tablet uses its item revision).
  Game inspection remains pending; LOD and reactor/controller construction
  redesign remain deferred.
  [Review evidence](../ArcanePower/validation/reactor-exterior-loop-01/distance-review.json).
  [Native export](../ArcanePower/validation/prototype-main-export.json).
- **Battery main-model review, 15 October:** seven finished authoring models now
  have recessed service doors/intakes, seated emissive strips, module-specific
  retention/cooling/fan hardware and detailed drum access panels. Further loops
  add faceted lifting decks, split cell clamps, flat fan guards, plated terminal
  straps, connected coolant returns/valves and supported motor wiring. Review
  offsets are repaired and verified after reload; collision and derived geometry
  remain unchanged. Stored charge
  drives field size through the existing battery visual path. Main geometry
  audit and focused runtime checks pass; compatibility compilation has zero
  warnings/errors. Docks now have closed clipped receivers, opaque native-port
  backs and compact tapered housings. Both drums now have chamfered saddles that
  seat into the curved armor and dock cheeks. Removed 48 redundant drum bolts
  and broad gasket plates; service doors/louvers sit in supported recesses, with
  48 captive screws retained on actual doors. Armor seams narrowed to 14.4 mm. Native SEUT
  structural textures and dark label stock replace custom label material;
  local preview packed channels are repaired. Latest art is saved in both Blender
  files and exported into local model family `energy_87c3644f9849`. Native imports,
  sockets, dependencies, collision preservation and saved assembly poses pass.
  This art revision still awaits a game reload/live inspection. User explicitly
  deferred further LOD work. The newly requested battery construction update is
  exported; reactor/controller construction redesign remains deferred.
  Mounted detail
  and [export evidence](../ArcanePower/validation/energy-main-export.json).
- **Construction complete:** three native welding/grinding stages for all twelve
  public blocks (36 models). Native imports, bounds, construction materials,
  embedded collisions and reactor model transitions pass. Damage integrity is
  distinct from native build progress. Existing reactor collisions are accepted
  by the user; further collision redesign is not a prerequisite.
  The 12 October revision replaces thin outline frames with channel steel and
  diagonal webs, exposes distinct equipment in stage two, and leaves deliberate
  service openings through stage three. The 15 October battery update rebuilds
  21 stages from current mains: three mating stations, current seated equipment,
  static fan blades and whole side/deck armor assemblies. Native import, material,
  bounds, collision and active-definition gates pass; 1.8/2.4/3.0 m views inspected.
  [Battery stage proof](../ArcanePower/validation/energy-construction-update/native-export.json).
- **Energy Core implemented:** accepted compact 3×3×3 controller plus standard/
  advanced capacity, transfer and stabilizer modules, fixed native batteries,
  charge modes, emergency reserve, icons and charge/flow visuals.
  [Configuration and provisional ratings](../ArcanePower/ENERGY-STORAGE.md).
- **Battery gameplay implemented 14 October, awaiting live validation:** quadratic
  stored-charge upkeep, stabilizer reductions, direct jump-drive surge, ten-second
  burst discharge, shared bank/drive recovery, terminal reserve controls and saved/
  server-authorized operation state. Focused policy proof is separate from the
  earlier live storage results. Validate actual native energy accounting and
  multiplayer/late join for these mechanics before release.
- **Initial hardening complete:** zero-warning compatibility build, focused
  reactor/storage checks and live isolated survival checks for 111,000 MWh mixed
  capacity, 1 TW source ceiling, a native 12 MW load, stabilizer disconnect/
  reconnect, preserved detached charge and copied-identity reset. The save
  contains updated charge and identity markers. Final saved-charge reload was
  interrupted by the client connection closing; it is not marked passed.
- **Package prepared, unpublished:** runtime ZIP and hashed dependency manifest;
  no authoring files, old model revisions or validation harness. [Release notes](../ArcanePower/RELEASE.md).
- **Appearance retained:** original dark static reactor core, without reactive
  plasma. Fuel artwork and larger, dimmer-emissive cartridges are preserved.
- **Construction/storage integration hardened:** unfinished reactors cannot start
  or generate; cold reactors release storage reserve only with usable fuel and
  complete containment hardware. Active cooldown/ejection retains emergency
  support. Removed capacity allocations are revoked in the bank's same update;
  native output refreshes respect incomplete/disabled cells. Offline storage
  visuals stop, with distance and emissive update throttling. Compatibility build,
  focused behavior checks and native shared-menu coverage pass. The game remote
  connection was unavailable on this pass, so no new live results are claimed.

## Remaining release gates

1. Complete saved-charge reload and live construction/grinding/projection,
   destruction, ownership, grid split/merge and multiple-bank checks.
2. Dedicated server and two-client/late-join validation. The isolated Windows
   dedicated launch stops before mod loading with a missing 2015–2019 x64 C++
   redistributable in its Wine environment. A local host test does not establish
   multiplayer correctness.
3. Sustained charge/discharge at rated demand, reserve contention, full/empty
   transitions and survival balance. The live test used a 12 MW native load;
   source ceilings were observed, not fully exercised at 1 TW. Validate SCF /
   Arcane Cores together in-game; local SCF source only modifies reactor producer
   multipliers, not batteries.
4. Distance/multiple-installation performance, final visual/material review,
   mining-to-generation survival, and release tuning of recipes, PCU and mass.
   Broader vent/terrain refinements below remain design backlog.

Evidence: [storage runtime](../ArcanePower/validation/energy-runtime.json),
[construction](../ArcanePower/validation/construction-stages.json),
[release manifest](../ArcanePower/validation/release-manifest.json).

## Fuel artwork delivery (2026-10-10)

Replaced uranium placeholders with nine original ore/concentrate/cartridge
models and rendered icons, six matching production icons, and three seamless
near/far voxel materials in cyan/amber/violet. The definition generator retains
these paths. Native model import, bounds, texture references and DDS mip chains
are checked; inventory, dropped ore and voxel appearance await in-game review.
No regression suite or game reload ran. [Visual sheet and rebuild instructions](../ArcanePower/README.md#fuel-artwork).

## Reactor housing collision repair (2026-10-09)

Replaced the legacy base/roof collision with baked, continuous round platforms
and eight narrower glass hulls. Ten convex bodies remain within the exporter
limit; the outside ledge is clear. Source contact probes, exported Havok bounds
and embedded collision passed inspection; the native model importer confirms all
110 dummies and visible bounds are unchanged. The local mod symlink already
exposes the corrected MWM for the next world reload. No in-game movement check
or regression suite ran. Moving hatch physics remain unfinished; the static
platforms still cover their visual openings. [Details and evidence](../ArcanePower/README.md#reactor-housing-collision-repair--9-october-2026).

## Reactor sound and feedback delivery (2026-10-08)

Implemented eight original synthesized cues: assembly, running resonance,
load pulses, instability, ignition, shutdown, vent discharge and critical blast.
Client loops follow existing synchronized state, resume without historical
ignition cues and follow physical ejected cores. Plasma/light pulses reflect
load and heat; critical explosions replicate a custom sound and tier-scaled
native warhead particles. [Listening preview and implementation notes](../ArcanePower/README.md#reactor-sound-and-feedback).

SE compatibility compilation and sound-asset checks pass. No deployment, live
audition or regression suites in this pass. Remaining: tune the mix, falloff,
realistic-sound behavior and explosion scale in-game; verify multiplayer, late
join/reload, paused startup, hot shutdown and overlapping reactors. A bespoke
arcane explosion particle asset remains an art refinement; current visuals reuse
the native warhead effect.

## Latest asset delivery

The selected **1.6 m × 1.0 m piggyback packs**, raised **2.3 m socket surrounds**, reactor surface fixes and revised vent recesses are now exported to MWM and retained in the latest local model family `lab_64ff9a73f168`, now including new plasma/field/debris assets. Five model icons were refreshed. Native upgrade empties were not scaled. Exported-model hashes and deployed icon bytes match; no game reload or regression suites were run. The earlier crescent controller geometry below is superseded.

## Completed in the preceding hardware/tile pass

- Recorded startup/shutdown and vent ejection from spectator view on the primary monitor at 3440×1440/60 fps. These show the preceding reactor revision at low load. Existing ceiling blocks obscure the roof hatch; footage does not establish hot cooldown or rated output.
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
2. **Finish vent behavior.** Handle blocked passages/outlets and independent shutter faults. Broken routes now pause committed ejection without resetting heat/fuses and resume after repair at the original height. Actuation now uses the containment grid/reserve budget; validate its supply-loss behavior. Tune the new critical explosions and add discharge-specific effects/sounds, plus collision geometry appropriate to moving doors. Current routing requires 1–15 fully built, aligned tubes plus one outlet on the same grid before startup; subsequent route loss shuts down or warns according to the saved Security mode. There is no legacy direct roof path. Arbitrary obstructions beyond the outlet are not checked. Ejection now hands off to native physical objects beyond the outlet; verify collision, gravity, launch speed and native cleanup limits. Define regulated/automatic vent modes and exhaust-capacity progression if retained from the broader plan.
3. **Make mining-to-generation playable.** Weighted asteroid voxel materials, dense concentrates and cumulative fuel recipes are now implemented. Validate discovery/drilling/refining and existing procedural terrain behavior; decide planetary/custom-terrain support separately. Ore/fuel definitions alone do not make deposits mineable. Complete a survival run without admin-spawned resources.
4. **Validate Arcane Energy Core storage.** Implementation, models, animation and basic native host checks are complete. Validate sustained surplus capture, demand peaks, reserve contention and actual splits/projection in-game. Vanilla batteries remain a valid startup/backup option.
5. **Finish art and feedback.** Construction stages and battery icons are delivered. Further art, sound/particle refinement and mass/components/PCU tuning remain. Review ore/fuel/voxel art alongside tile flight paths, door pockets, highlights and glass in-game.
6. **Finish release hardening.** The user authorized this validation pass; focused checks and an unpublished runtime package are complete. Finish the explicit release gates above before publication.

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


## Tile progression and vessel inventory — 9 October 2026

Implemented Standard/Reinforced/Advanced tiles with 1×/10×/100× lifetime, ingredient
cost and crafting time, compatible with all fuels. Mixed-grade shells use same-grade
quartets, with highest-grade-first installation/replacement. Grade state persists;
explicit quartet state tracks grades, ordinary shutdown retains the shell, and venting
or detonation discards it. The inventory is now 2,000 L, with automatic targets of
80 loose tiles per grade. Shared telemetry reports grade stock and mixed endurance.
Focused offline checks and SE compatibility compilation passed; no existing
regression suite or game reload ran. Validate actual conveyors/crafting, native inventory behavior, multiplayer save/join
and replacement timing. Alpha changes have no backward-compatibility layer.


## Rare ores and compaction — 9 October 2026

Implemented Aetherite/Helionite/Empyrite asteroid materials, with weights 5/2/1
against vanilla weights scaled uniformly by 100. Mining ratios decrease
0.1/0.03/0.01; refining yields decrease 0.1%/0.01%/0.001%. Concentrates and fuels
occupy 0.01/0.005/0.001 L/kg versus ore's 0.37 L/kg. Standard refineries remove
the bulk ore matrix; assemblers form fuel, requiring the preceding fuel plus
rare concentrate for higher tiers. Recipes and grade state use current alpha definitions without save migration support.
The focused definition check passed. Review discovery frequency, actual refinery
and assembler behavior, throughput at common world multipliers and material
regeneration in existing procedural asteroids in-game. Native art is reused;
custom planetary maps and meteorite distribution are outside this asteroid pass.

Controller/fuel separation is implemented: two standard, mixed and two advanced controllers deploy 2/3/4 rings at 1×/1.5×/2× tile rates, independently of compatible fuel, with 80%/90%/99% fuel efficiency. Deployed hardware remains latched through cooldown and ejection. Validate lower fuels with stronger controllers, live hardware changes, near-empty fuel capacity and multiplayer/save restoration in-game.

Damage-triggered core ejection is implemented at 60% remaining reactor integrity, gated by two fully built, functional controllers and the complete vent route. Security mode defaults on (vent loss shuts down); off keeps an already-running reactor generating with a warning. Controller/vent loss pauses committed ejection, while heat/fuses continue. Focused offline checks and the SE compatibility build passed; live damage, repair, reserve-power and multiplayer validation remain pending.
