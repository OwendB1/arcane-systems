# Arcane Power prototype

Arcane Power is an SE1 reactor, fuel-processing and energy-storage mod in development. The current large-grid reactor fits **5×5×3 cells** (SE `Size=(5,3,5)`). Its rounded housing has three native-size conveyor access hatches plus a centered top conveyor connection behind the vent hatch, two base upgrade sockets and curved chamber glass. This is an engineering slice of the [mod plan](../docs/arcane-power-plan.md), not the finished progression.

The user approved moving all animation from Animation Engine into the mod and adding normal shutdown. **Direct C# now owns every animated transform and visibility state.** The saved [Blender model](assets/arcane-power-prototype.blend) has **103 subparts**: four rings, four floor leaves, 80 field tiles, one plasma, six blast-shield sleeves, four outer ejection-hatch leaves and four inner ceiling-door leaves.

## Latest Blender fit revision

A [width comparison](validation/pack-width-comparison.png) now shows 1.6 m and 2.0 m packs at the same 1.0 m height, with 2.3 m and 3.0 m socket surrounds. The 2.0 m version is a rough, non-exported comparison in `AP pack width comparison (not exported)`; the user selected the **1.6 m pack with its 2.3 m socket surround**. Native upgrade empties were compared before/after and retain their transforms.

The saved reactor scene now includes both controllers at their native adjacent-cell centres, plus a roof duct/outlet stack, in `AP mounted hardware (not exported)`. Controllers are compact piggyback power packs, 1.60 m wide × 1.00 m high around the native 0.68 m socket. Their backs follow the drum with a 12 mm seam and a recessed connector cavity. The packs are 12 cm shallower than the initial cartridge revision, with twin cell covers, retaining clips and one/two fuel status bars. A curved base manifold forms an open socket surround whose lip ends 25 mm behind the pack face. Packs and native ports are raised 17 cm to center on the white panels, with 9 cm above/below each socket surround. Native occupied cells and block anchors are unchanged; only the visual mating skirt enters the unused space beside the curved drum. Vent service details have actual recesses, and the reactor roof backing has clearance behind its liner and panel seats. See [fit_hardware_assembly.py](assets/fit_hardware_assembly.py). **This revision has now been exported to MWM; local deployment is recorded in [local-deployment.json](validation/local-deployment.json). The recordings below still show the preceding revision.**

## Startup, normal shutdown and vent mechanism

[Reactor.Motion.cs](src/Data/Scripts/ArcanePower/Reactor.Motion.cs) implements `Off → Starting → Running → Cooling → Stopping`. The base startup spans 1,170 authored simulation ticks: annular leaves open around the fixed solid island, rings rise, dispensers assemble twenty four-tile batches, plasma appears and rings enter armillary motion. For a hot running reactor, normal shutdown first holds the assembled shell in Cooling, slowing the rings until heat falls to 15% or lower (about 57 seconds from full heat with the 30-second cooling response). It then brakes both ring axes over 90 ticks while plasma fades over the first 60, and reverses deployment at its original 1× pace. Passive cooling continues if damage pauses the mechanisms. An interrupted startup reverses from its current age, including its fractional position.

Venting is a committed, finite **core-ejection cycle**: shield closes for 4 seconds, intake/hatch opens for 1.5, the core and deployed rings eject upward for 2, intake closes for 1.5, and shield retracts for 4 (about 13 seconds total). Native power is cut only once the shield is fully closed. The cycle ends automatically and leaves the reactor Off; a manual restart builds a fresh containment field. Another toolbar click does not reverse an active ejection.

Healthy heat approaches actual load with the existing heating/cooling response. Tile starvation now cuts output to 10% of the captured operating load while burning fuel at 10× its normal rate and accelerating heat. At 125% heat, an irreversible saved detonation timer starts. Tier I/II/III cores use 5×/20×/100× large-warhead damage with cube-root radius scaling. Ejection transfers that hazard to the physical core; subcritical ejected cores decay. Details, provisional values and limits are in [THERMAL-FAILURE.md](THERMAL-FAILURE.md).

After a payload vent completes, server damage applies once: reactor `1% + 4% × load + 10% × heat`, compatible attached modules `2% + 6% × load + 12% × heat`. Heat above 100% can exceed the old 15%/20% healthy maxima. The scripted payload now becomes physical spent rings/tiles and a plasma carrier once clear of the outlet. Moving shutter collision remains unfinished.

[VentSession.cs](src/Data/Scripts/ArcanePower/VentSession.cs) provides a **Vent reactor** terminal button and `ArcanePower_StartVent` / `ArcanePower_ToggleVent` actions. Commands use secure messages with server-side ownership/access validation. The server owns motion state, sends snapshots every 30 ticks and persists state in mod storage. These paths are implemented, not yet confirmed in a live multiplayer/save-load session.

[Reactor.cs](src/Data/Scripts/ArcanePower/Reactor.cs) enforces two functional controllers and available ring capacity. [Reactor.Fuel.cs](src/Data/Scripts/ArcanePower/Reactor.Fuel.cs) now selects and consumes actual fuel tiers:

| Fuel | Required ring capacity | Colour | Rated output |
| --- | --- | --- | --- |
| Fuel I | 2 | Cyan | 10,000 MW |
| Fuel II | 3 | Amber | 100,000 MW |
| Fuel III | 4 | Violet | 1,000,000 MW |

The highest compatible fuel present is selected only while Off, vent Idle and output zero, then locked through operation/shutdown. Initial balance consumes one selected fuel unit per minute at full rated output, proportionally less at lower demand. Higher processing recipes use a 10:1 ratio; the current definitions consume one lower-tier unit to produce 0.1 higher-tier unit, with base times of 12/24 seconds. These are initial balance values.

Native `FuelInfos` is empty because multiple native entries represent concurrent inputs rather than alternative fuels. The mod allows all three fuels in its inventory, maintains native energy capacity for the selected fuel and consumes it explicitly. Conveyor replenishment uses public inventory transfers with conveyor reachability and access checks.

Only sphere assembly (authored ages 320–1038) accelerates with the profile: two rings use 1×, three use 1.5×, four use 2×. Assembly takes 718/479/359 real ticks and complete startup takes 1,170/931/811 ticks respectively (about 19.5/15.52/13.52 seconds at 60 ticks/s). Mechanical deployment and normal shutdown retain their original speed.

Controller count and ring capacity are separate values; one advanced controller cannot satisfy the two-controller interlock. Capacity changes force a shutdown/restart. Tile inventory and startup/containment energy accounting are implemented below. The native reactor remains demand-driven. Available electrical output ramps from zero to the selected rating over 600 ticks after Core reaches Running; the tier MaxOutput rating stays unchanged. Startup itself produces no output.

## Status colours and load-driven motion

Emissives pulse red/black over 120 ticks when construction is incomplete, the block is nonfunctional or fewer than two controllers are attached. A complete reactor is steady red when off, yellow when enabled without fuel, and uses its selected fuel colour otherwise. Fuel-starvation yellow persists through automatic shutdown until refuelling. Parent emissives can update before Ring1 renders. Emissives now use twelve-times intensity (up from four), and an active vent pulses bright red. The reactor and terminal vent outlet share that intensity. One client-only, shadowless light with a 4.5 m range follows the visible plasma to illuminate nearby chamber surfaces in the current fuel/alarm colour. Its strength follows the vent pulse and shutdown/ejection fades; it turns off with the hidden core and is released when the reactor closes. Surface bloom depends on the player's graphics settings; the mod does not alter them.

The server derives load from native `CurrentOutput / MaxOutput`, smoothed with a 60-tick response. Running ring speed ranges from three times the original speed at zero load to nine times at full load. Both primary and secondary phase/rate are saved and synchronized. Each ring has a perpendicular second rotation axis with distinct alternating signed rates (magnitudes 0.07/0.09/0.11/0.13), driven by smooth phase modulation; shutdown brakes both axes from their captured speeds. Tiles and plasma share a smooth irregular drift and gentle vertical bob that grows with load, stays below 6 cm, starts near the end of startup and settles during shutdown. The whole field now tumbles around multiple axes: slow continuous yaw/roll spin is combined with unequal broad sweeps that reverse direction and carry the shell through half-turns, plus the smaller 6°–9.25° irregular tilt. The saved load-driven spin phase drives this motion without per-frame randomness or jumps at phase wrapping. Shutdown brakes the tumbling, then aligns the intact shell before reverse assembly releases its first quartet. Translational wiggle/bob and ring movement are unchanged. This motion is presentation; the separate normalized heat state drives vent purging/damage.

## Geometry and authoring

[build_deployable_chamber.py](assets/build_deployable_chamber.py) authors the original 89 startup parts and [deployment.json](assets/deployment.json). The field has nominal radius 0.88 m with 0.045 m tile thickness; four ring radii are 1.09/1.29/1.49/1.69 m. Two tile shapes are reused by 60 and 20 congruent instances. The solid central island stays fixed while four surrounding leaves retract.

[build_vent_bell.py](assets/build_vent_bell.py) and [vent.json](assets/vent.json) describe the recessed upper bell, ceiling pocket and six sleeves. Their smallest inner radius is 1.924 m, sitting 4 mm outside the floor fuel trace. The earlier 32 intake vanes were removed because they conflicted with the lined passage; the Intake state now times the doors without a vane loop. Native emissive strips on the bell, shield and doors follow the selected fuel.

[build_ejection_hatch.py](assets/build_ejection_hatch.py) removes the visible top conveyor skin while retaining its centered conveyor dummy. Four leaves sharing one MWM open a 3.72 m visual bore by dropping 0.3 m and sliding 1.95 m diagonally; the later passage revision removes the former intake vanes. The hatch is render-only and static roof collision is unchanged.

[build_ceiling_hatch.py](assets/build_ceiling_hatch.py) adds four inner doors sharing the VentHatch mesh and its underside trims/emissives. From Z=2.365 m they lift 0.32 m, then slide 1.98 m between the dispensers, rotated 45 degrees relative to the outer doors. A radius-1.86 m lined bore and retraction pockets connect the inner and outer openings; overlapping central tube geometry was removed.

[highlight_inventory_hatches.py](assets/highlight_inventory_hatches.py) assigns each conveyor detector to its access-hatch mesh, with the intended frame left unselected. The reported failure was traced to zero mesh sections in the compiled MWM despite correct detector targets. The helper now gives all four hatch meshes the `_section` suffix required by MwmBuilder and updates their detector links. At the earlier four-hatch stage, the compiled MWM contained four matching sections, each with 1,146 indices; revision `lab_3ed994c27b1f` was deployed. That evidence predates replacement of the top hatch. In-game highlighting remains unverified. The current glass uses native dirt/chrome textures; material tuning and the first-load emissive retry are recorded in [LEARNINGS.md](LEARNINGS.md).

Iterate geometry in Blender using Blender MCP and SEUT. **Do not run regression suites unless the user asks.** Review static poses in Blender; do not create a substitute timeline animation. Earlier [mockups](assets/mockups/README.md) and shape scripts are historical stages and can overwrite later work if rerun indiscriminately.

[build_animation_geometry.py](tools/build_animation_geometry.py) generates [AnimationGeometry.cs](src/Data/Scripts/ArcanePower/AnimationGeometry.cs) from the geometry manifests. `tools/build_animation.py` remains a compatibility entry point for that generator; it no longer produces BSL. Build the solution with `dotnet build arcane-systems.sln` when compilation is needed, respecting the separate restriction on regression suites.

## Lab deployment and current evidence

[prepare_lab.py](tools/prepare_lab.py) deploys to `~/.config/SpaceEngineers/Mods/ArcanePower-Prototype` and creates **Arcane Power - Prototype Lab** only if absent. Existing worlds are preserved. Model families are deployed together under a content-versioned directory so relative subpart references resolve. Deployment removes the old `Data/Animation/main.bsl`; newly created worlds omit the Animation Engine dependency. The current running world's mod list is unchanged.

Two [spectator recordings](validation/recordings/recordings.json) capture the preceding reactor revision `lab_c05a1c7be62e`: [startup and shutdown](validation/recordings/reactor-startup-shutdown.mp4), and [vent ejection](validation/recordings/reactor-vent.mp4). GPU Screen Recorder captured the primary DP-4 monitor at 3440×1440/60 fps. These show low-load visual operation, not rated electrical output or hot cooldown. Existing ceiling blocks obscure the roof hatch. [Repair evidence](validation/recordings/repair.json) confirms the reactor and both controllers returned to full integrity/build after reload and resave.

The earlier hardware/tile pass compiled with zero warnings/errors. On 15 September the selected pack/socket and vent refinements were exported and five icons refreshed. That asset pass deployed 45 files under `lab_06d121e6bcac`; the subsequent power/inventory/maintenance script pass adds three files. Neither new pass has been loaded in-game. No regression suites or new C# build were run during the asset export. [local-deployment.json](validation/local-deployment.json) distinguishes deployment from live evidence. New hardware, inventory behavior and synchronization still need in-game review.

## External hardware and consumable tiles

[build_external_hardware.py](assets/build_external_hardware.py) and [external-hardware.json](assets/external-hardware.json) define the new parts. The saved Blender file includes a static **Arcane Power external hardware review** lineup.

- Vent duct and outlet each occupy **3×1×3 SE cells**: a 3×3 cross-section, one cell deep for stacking. Their lined 3.72 m bore matches the reactor passage. Eight convex collision wedges leave the duct aperture open. The outlet has four shared hatch subparts, recessed pockets and emissive trim; its leaves drop 0.30 m and slide 1.40 m per axis inside the housing.
- Standard and advanced controllers each occupy one grid cell. Their selected 1.6 m × 1.0 m piggyback packs follow the reactor base, with a recessed native connector, twin cell covers and one/two status bars. The curved visual mating skirt extends into the unused space beside the reactor drum; occupied cells and native upgrade empty transforms are unchanged by the width revision.
- The containment component uses an actual thick, framed triangle from the shell, approximately 0.535×0.390×0.045 m. [render_hardware_icons.py](assets/render_hardware_icons.py) produces the five new icons from the models.

[Reactor.VentRoute.cs](src/Data/Scripts/ArcanePower/Reactor.VentRoute.cs) follows up to 16 contiguous, functional, aligned duct/outlet sections on the same grid. The terminal outlet shares the reactor Intake clock and vent alarm emissives; ejection travel grows with route length. A started custom duct chain without a valid outlet rejects vent requests. With no custom chain, the earlier direct roof ejection remains available. Elbows, obstacle checks, broken routes during a committed cycle, and moving shutter collision are unfinished. Physical discharge now begins beyond the outlet plane.

[Reactor.Tiles.cs](src/Data/Scripts/ArcanePower/Reactor.Tiles.cs) reserves **80 tiles before initial startup** in survival. Assembly still animates twenty quartets; inventory is reserved upfront, not during each flight. Normal shutdown retains installed stock and wear. Running maintenance consumes four tiles per batch, initially 1/2/4 batches per minute at full tier load before heat adjustment; idle wear is 20%, and the quadratic heat factor reaches 4× at 100% heat. An unreplaceable worn quartet now causes 10% output, 10× fuel burn and runaway heating, with an incomplete alarm. Resupplying four tiles can arrest the runaway before supercriticality. Conveyor replenishment targets 160 loose tiles. Venting discards installed tiles; a subsequent manual restart needs another shell. Creative mode supplies tiles without consumption.

The provisional assembler recipe is **2 iron + 0.1 nickel + 0.2 silicon ingots → 4 tiles**, with a base time of 10 seconds. Installed quantity, wear and starvation are persisted/synchronized; copied entity IDs cannot inherit another reactor's installed reserve. Maintenance replacement now cycles through the twenty quartets, retiring each worn group and launching four replacements from fixed pillar dispensers into the moving shell. The 90-tick sequence follows the 1×/1.5×/2× tier rates, is saved/synchronized, and completes before normal dismantling. Terminal information includes loose stock, restart shortages and maintenance endurance at current load/heat. Balance, flight clearance and lifecycle validation remain outstanding.

See the [remaining-work overview](../docs/arcane-power-remaining-work.md) for the implementation sequence and evidence gaps.

## Grid power and inventory UI — 15 September 2026

[ContainmentController.cs](src/Data/Scripts/ArcanePower/ContainmentController.cs) places native electrical sinks on the two external controllers. SE pairs a generator and electrical sink in the same component container as storage, so the reactor remains a normal source while controllers draw the operating energy. The new `ArcaneContainment` sink group has priority 2 (after vanilla safe zones, before defense) and accepts partial supply. Native grid behavior and split/merge handling still require game review.

[Reactor.Power.cs](src/Data/Scripts/ArcanePower/Reactor.Power.cs) uses provisional containment demand **1/10/100 MW**, a **90-second** internal shutdown reserve (**0.025/0.25/2.5 MWh**), and up to three times operating demand for charging. Full precharge therefore requests **4/40/400 MW** and takes approximately **30 seconds** with sufficient grid supply, before the existing assembly and output ramp. Startup requires grid input and a full reserve; the reserve cannot start the reactor or export electricity. Creative also requires electrical supply. Reserve charging uses actual distributed input, and persisted energy remains tied to the original entity ID.

A containment-input shortfall triggers controlled shutdown and manual restart lockout. Grid input or the reserve powers cooldown, dismantling and vent actuation even after the reactor is disabled. An exhausted reserve pauses mechanisms until input returns; passive cooling continues. A destructive breach is not implemented. Older saved prototypes start with no reserve unless they have saved this version's charged state. Terminal information shows input/request, gross generation and net contribution after containment/charging, reserve seconds, and supply/shutdown reasons.

The reactor inventory now receives an explicit four-item whitelist and matching empty-slot tooltip on server and clients: Fuel I, Fuel II, Fuel III and Containment Tiles. The reactor-specific definition uses the same filter for native conveyor pull information. This replaces the stale generic tooltip derived from empty native `FuelInfos`; alternative-fuel consumption remains scripted to avoid native simultaneous-fuel requirements.

This script pass is compiled and locally deployed; the model revision remains `lab_06d121e6bcac`. No regression suites or game reload were performed. Supply accounting, UI appearance, late joins and maintenance flight clearance are implemented but not yet game-validated. See [build log](validation/survival-power-build.log).

## Knowledge graph

The scoped [JSON graph](graphify-out/graph.json), [interactive view](graphify-out/graph.html) and [audit report](graphify-out/GRAPH_REPORT.md) index these documents and selected small runtime/authoring tools. Heavy binary assets and generated per-part coordinate arrays are excluded. The repository-wide graph is separate.

## Thermal failure and plasma delivery — 16 September 2026

The local mod now contains `lab_64ff9a73f168`: updated smooth plasma, open thick containment frames, seven embedded collision models, generated CM/NG/ADD textures, spent-part definitions and direct-script thermal/physical ejection. The native upgrade empties and housing retain the selected fit. The final script build passed with zero warnings/errors; 54 delivery files were copied. [Static fuel-colour preview](validation/plasma-fuel-review.png), [behavior and remaining limits](THERMAL-FAILURE.md), [deployment record](validation/local-deployment.json). No game reload, destructive test or regression suite was run.

## Reactor LCD and handheld tablet

Select the **Arcane Reactor** LCD script, or craft/equip **Arcane Reactor Tablet**.
The tablet's left click selects a reachable reactor; right click changes pages.
It requires an enabled suit antenna and an accessible bidirectional grid antenna
link, and is read-only. Text HUD API enables the full SCF-style card dashboard;
without it the held tool provides a live native text readout. Setup, asset sources
and validation limits: [STATUS-DISPLAYS.md](STATUS-DISPLAYS.md).

World saves/save-and-exit now snapshot current reactor state before grid
serialization and restore it after native module reconnection. Running reactors
resume; manual and completed-vent shutdowns remain off. See
[restart persistence](REACTOR-PERSISTENCE.md) for behavior and validation limits.

## Compiling scripts before deployment

Run `python ArcanePower/tools/compile_mod.py` from the repository root. It applies
SE's compatibility imports before compiling with the existing MDK analyzers, so
namespace collisions introduced by the game are caught. A plain SDK build misses
that import step. [Compiler setup and evidence](COMPILATION.md).

## Live local mod directory

`~/.config/SpaceEngineers/Mods/ArcanePower-Prototype` is now a symlink to this
repository's `ArcanePower/src`. Edit/export into `src`; no copy/deploy step is
needed. The prior copied deployment is preserved under SpaceEngineers/ModBackups.
`prepare_lab.deploy()` recognizes the link and does not rewrite source definitions
with deployment-only model paths. File edits still need the relevant game reload;
a filesystem link does not hot-reload definitions already held in memory.
