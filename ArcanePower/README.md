# Arcane Power prototype

[Steam Workshop](https://steamcommunity.com/sharedfiles/filedetails/?id=3819727962)
· [Publishing workflow and gallery sources](RELEASE.md)

Arcane Power is an SE1 reactor, fuel-processing and energy-storage mod in development. The current large-grid reactor fits **5×5×3 cells** (SE `Size=(5,3,5)`). Its rounded housing has three native-size conveyor access hatches plus a centered top conveyor connection behind the vent hatch, two base upgrade sockets and curved chamber glass. This is an engineering slice of the [mod plan](../docs/arcane-power-plan.md), not the finished progression.

## Construction and Energy Core delivery — 11 October 2026

All twelve public blocks now have **three native construction stages**, 36 models
for welding/grinding. The existing collisions remain as accepted. Native imports,
stage bounds, construction materials, embedded collisions and reactor model
transitions pass their focused checks.

The **compact 3×3×3 Energy Core** is implemented with two side capacity sockets,
a rear transfer socket and a top stabilizer. Standard/advanced expansions provide
fixed native storage and 10/100/1,000 GW bank transfer tiers. It includes native
charge modes, emergency reserve controls, charge-dependent glow, slow rotation,
icons and construction models. [Setup, ratings and validation](ENERGY-STORAGE.md)
· [Stage sheet](validation/energy-core-stages.png).

The isolated survival test verified native output allocation, stabilizer
disconnect/reconnect and copied-charge reset. Updated charge and identity markers
were saved; final reload remains unverified after the client connection closed.
The dedicated launch was blocked by its missing C++ runtime before mod loading.
The compatibility build and focused checks pass. Multiplayer, high-load balance
and the other [release gates](../docs/arcane-power-remaining-work.md) remain open.
An [unpublished alpha package](RELEASE.md) is prepared.

The reactor retains the user's selected **original dark static texture**, without
reactive plasma. Earlier dated notes below describe their respective revisions.

The user approved moving all animation from Animation Engine into the mod and adding normal shutdown. **Direct C# now owns every animated transform and visibility state.** The saved [Blender model](assets/arcane-power-prototype.blend) has **103 subparts**: four rings, four floor leaves, 80 field tiles, one plasma, six blast-shield sleeves, four outer ejection-hatch leaves and four inner ceiling-door leaves.

## Latest Blender fit revision

A [width comparison](validation/pack-width-comparison.png) now shows 1.6 m and 2.0 m packs at the same 1.0 m height, with 2.3 m and 3.0 m socket surrounds. The 2.0 m version is a rough, non-exported comparison in `AP pack width comparison (not exported)`; the user selected the **1.6 m pack with its 2.3 m socket surround**. Native upgrade empties were compared before/after and retain their transforms.

The saved reactor scene now includes both controllers at their native adjacent-cell centres, plus a roof duct/outlet stack, in `AP mounted hardware (not exported)`. Controllers are compact piggyback power packs, 1.60 m wide × 1.00 m high around the native 0.68 m socket. Their backs follow the drum with a 12 mm seam and a recessed connector cavity. The packs are 12 cm shallower than the initial cartridge revision, with twin cell covers, retaining clips and one/two fuel status bars. A curved base manifold forms an open socket surround whose lip ends 25 mm behind the pack face. Packs and native ports are raised 17 cm to center on the white panels, with 9 cm above/below each socket surround. Native occupied cells and block anchors are unchanged; only the visual mating skirt enters the unused space beside the curved drum. Vent service details have actual recesses, and the reactor roof backing has clearance behind its liner and panel seats. See [fit_hardware_assembly.py](assets/fit_hardware_assembly.py). **This revision has now been exported to MWM; local deployment is recorded in [local-deployment.json](validation/local-deployment.json). The recordings below still show the preceding revision.**

## Required reactor vent tube

Install **1–15 Arcane Vent Duct blocks followed by one Arcane Vent Outlet**, centered
above the reactor roof hatch. Each section occupies 3×1×3 large-grid cells; the
first tube's center is two cells (5 m) along reactor Up, and subsequent sections
are one cell (2.5 m) apart. Use the same grid, match each section's Up orientation,
and fully weld every section. The existing native conveyor ports connect through
the stack. Keep the outlet and its ejection path clear.

The server checks the route before fuel, precharge and startup tile work. Missing,
unfinished, nonfunctional, offset or reversed sections block startup and switch
off a running reactor, preserving powered cooldown. Repair the route and restart
manually. **Existing reactors without this stack will switch off after world
connections initialize.** A roof outlet alone no longer satisfies the interlock.
During the existing 120-frame initialization window, route checks update readiness
without disabling the saved reactor; missing routes still block generation.
Older saves with `Profile` migrate to the selected fuel tier and adopt the attached
controllers' ring capacity once their native connections settle. Current saves
retain their explicit ring count and still shut down on a real hardware mismatch.
The unresolved legacy snapshot stays intact until migration completes.
Terminal, toolbar, LCD and tablet readiness use the replicated route state.

Every vent tube and outlet uses a red native fallback, so an orphan conveyor
cannot advertise readiness. Green requires a functional reactor and a complete,
fully built, aligned tube-and-outlet stack; the same route validator serves the
startup interlock and the lamps. Venting/critical alarms pulse red. Local checks
refresh all section lamps, including disconnected pieces, every ten frames.

The outlet's four leaves open with the reactor hatch. Breaking a committed route
before physical payload release pauses its mechanisms; heat and any critical
countdown continue. Rebuild the original stack height to resume. A replacement
outlet at the same position is accepted; shortening an active trajectory is not.
There is no direct-roof release fallback. After payload release, closure can finish
even if the route breaks.

The existing fitted tube/outlet art is finalized in
[prepare_vent_tube.py](assets/prepare_vent_tube.py), with eight baked convex wall
sectors per block. The duct, outlet and shared hatch are exported together.
[Model checks](validation/vent-tube-model.json) cover ports, leaf links, open bores
and platform contacts; `python3 ArcanePower/tools/check_vent_route.py` exercises
the actual route/interlock methods offline. The compatibility build also passed.
Export evidence is in [vent-tube-export.json](validation/vent-tube-export.json).
The local mod symlink picks up these files; reload the world to load new models.
No live game or multiplayer validation has run. Moving hatch collision remains
unfinished; transit through the reactor and tube is scripted until outlet release.

## Startup, normal shutdown and vent mechanism

[Reactor.Motion.cs](src/Data/Scripts/ArcanePower/Reactor.Motion.cs) implements `Off → Starting → Running → Cooling → Stopping`. The base startup spans 1,170 authored simulation ticks: annular leaves open around the fixed solid island, rings rise, dispensers assemble twenty four-tile batches, the plasma grows from zero over ticks 1038–1170 (2.2 seconds after the final quartet latches), and rings enter armillary motion. For a hot running reactor, normal shutdown first holds the assembled shell in Cooling, slowing the rings until heat falls to 15% or lower (about 57 seconds from full heat with the 30-second cooling response). It then brakes both ring axes over 90 ticks while the plasma shrinks and fades to nothing over the same 90 ticks, and reverses deployment at its original 1× pace. Passive cooling continues if damage pauses the mechanisms. An interrupted startup reverses from its current age, including its fractional position.

Venting is a committed, finite **core-ejection cycle**: shield closes for 4 seconds, intake/hatch opens for 1.5, the core and deployed rings eject upward for 2, intake closes for 1.5, and shield retracts for 4 (about 13 seconds total). Native power is cut only once the shield is fully closed. The cycle ends automatically and leaves the reactor Off; a manual restart builds a fresh containment field. Another toolbar click does not reverse an active ejection.

Healthy heat approaches actual load with the existing heating/cooling response. Tile starvation now cuts output to 10% of the captured operating load while burning fuel at 10× its normal rate and accelerating heat. At 125% heat, an irreversible saved detonation timer starts. Tier I/II/III cores use 5×/20×/100× large-warhead damage with cube-root radius scaling. Ejection transfers that hazard to the physical core; subcritical ejected cores decay. Details, provisional values and limits are in [THERMAL-FAILURE.md](THERMAL-FAILURE.md).

After a payload vent completes, server damage applies once: reactor `1% + 4% × load + 10% × heat`, compatible attached modules `2% + 6% × load + 12% × heat`. Heat above 100% can exceed the old 15%/20% healthy maxima. The scripted payload now becomes physical spent rings/tiles and a plasma carrier once clear of the outlet. Moving shutter collision remains unfinished.

Damage at **60% reactor integrity remaining or lower** automatically requests core ejection once a payload is deployed. Both attached controllers must be fully built and functional. Every vent tube and the outlet must also be fully built, functional and aligned; blocked ejection retries when the route is repaired. Damage to the reactor itself does not disable emergency vent actuation while the controllers and containment power/reserve remain available. Losing a controller or vent before physical release pauses ejection without stopping heat or critical timers.

The terminal **Security mode** switch defaults to **On**: losing the vent route while running causes controlled shutdown. **Off** allows an already-running reactor to keep generating with a visible vent-fault warning. Both modes require a complete route for initial startup and shut down an interrupted startup if that route breaks. Automatic damage ejection remains active in both modes. Security mode is saved, synchronized and changed through the existing access-checked server command path.

[VentSession.cs](src/Data/Scripts/ArcanePower/VentSession.cs) provides a **Vent reactor** terminal button and `ArcanePower_StartVent` / `ArcanePower_ToggleVent` actions. Commands use secure messages with server-side ownership/access validation. The server owns motion state, sends snapshots every 30 ticks and persists state in mod storage. These paths are implemented, not yet confirmed in a live multiplayer/save-load session.

[Reactor.cs](src/Data/Scripts/ArcanePower/Reactor.cs) enforces two functional controllers and available ring capacity. [Reactor.Fuel.cs](src/Data/Scripts/ArcanePower/Reactor.Fuel.cs) now selects and consumes actual fuel tiers:

| Fuel | Minimum controller ring capacity | Colour | Rated output |
| --- | --- | --- | --- |
| Aether | 2 | Cyan | 10,000 MW |
| Helion | 3 | Amber | 100,000 MW |
| Empyrean | 4 | Violet | 1,000,000 MW |

The highest compatible fuel present is selected only while Off, vent Idle and output zero, then locked through operation/shutdown. Each filled canister holds 10 fuel units: 10 ideal full-load minutes, or **8/9/9.9 minutes** with controller tiers 1/2/3. Consumption divides by controller efficiency and falls with demand. Native inventory amounts include the remaining fraction of a canister; telemetry labels stock and burn in canisters. Refineries retain base yields of 0.1%/0.01%/0.001% for Aether/Helion/Empyrean concentrates.

Craft an **Aether Containment Canister (Empty)** in a full assembler, then fill
or upgrade it through the existing fuel chain:

| Recipe | Ingredients | Output | Base time |
| --- | --- | --- | --- |
| Empty canister | 100 iron, 40 cobalt, 10 silver, 5 platinum ingots; 10 superconductors, 4 computers, 4 metal grids | 1 empty canister | 60 s |
| Fill Aether | 1 empty canister + 10 kg Aether concentrate | 1 Aether fuel canister | 100 s |
| Upgrade Helion | 1 Aether canister + 10 kg Helion concentrate | 1 Helion fuel canister | 300 s |
| Upgrade Empyrean | 1 Helion canister + 10 kg Empyrean concentrate | 1 Empyrean fuel canister | 900 s |

These are base costs/times; filling and upgrade recipes ignore assembler
material-efficiency multipliers to consume exactly one whole container and
preserve payload accounting. Production speed multipliers still apply. Empty
canister crafting uses normal assembler efficiency. Upgrades retain the paid
container. Burning fuel does not return empty containers. All canisters occupy
24 L; filled mass includes the shell and cumulative 10 kg concentrate charges.
The empty item's model/icon reuse the Aether shell with a dark unpowered chamber.

Four **Standard Containment Tiles** now cost 20 iron, 8 cobalt, 4 silver and
2 platinum ingots, plus 4 superconductors, 4 computers, 1 detector component and
4 metal grids. Reinforced and Advanced multiply every ingredient, crafting time
and lifetime by 10 and 100 respectively. Normal assembler efficiency applies.
A Standard 80-tile shell costs 40 platinum ingots and 80 superconductors before
assembler efficiency, alongside the other materials. All grades support all fuels.

Native `FuelInfos` is empty because multiple native entries represent concurrent inputs rather than alternative fuels. The mod allows all three fuels in its inventory, maintains native energy capacity for the selected fuel and consumes it explicitly. Conveyor replenishment uses public inventory transfers with conveyor reachability and access checks.

Controllers determine active rings and tile deployment independently of fuel. Only sphere assembly (authored ages 320–1038) accelerates with controller hardware: two rings use 1×, three use 1.5×, four use 2×. Assembly takes 718/479/359 real ticks and complete startup takes 1,170/931/811 ticks respectively (about 19.5/15.52/13.52 seconds at 60 ticks/s). Mechanical deployment and normal shutdown retain their original speed.

| Controller installation | Rings | Tile deployment/maintenance rate | Fuel efficiency | Full-load canisters/min |
| --- | --- | --- | --- | --- |
| Tier 1: two standard | 2 | 1× | 80% | 0.125 |
| Tier 2: standard + advanced | 3 | 1.5× | 90% | 0.11111… |
| Tier 3: two advanced | 4 | 2× | 99% | 0.10101… |

Every supported fuel uses all installed controller rings and the same hardware-dependent tile rate. Aether with two advanced controllers therefore deploys four rings at 2× speed with 99% efficiency. Fuel still determines output, colour, tile wear and containment power demand. Fuel-limited electrical capacity uses the same efficiency as normal and starvation fuel accounting. Deployed ring count is saved/synchronized and held through cooldown, dismantling and ejection; hardware changes require a fresh startup.

Controller count and ring capacity are separate values; one advanced controller cannot satisfy the two-controller interlock. Capacity changes force a shutdown/restart. Tile inventory and startup/containment energy accounting are implemented below. The native reactor remains demand-driven. Available electrical output ramps from zero to the selected rating over 600 ticks after Core reaches Running; the tier MaxOutput rating stays unchanged. Startup itself produces no output.

## Status colours and load-driven motion

Emissives pulse red/black over 120 ticks when construction is incomplete, the block is nonfunctional or fewer than two controllers are attached. A complete reactor is steady red when off, yellow when enabled without fuel, and uses its selected fuel colour otherwise. Fuel-starvation yellow persists through automatic shutdown until refuelling. Parent emissives can update before Ring1 renders. Emissives now use twelve-times intensity (up from four), and an active vent pulses bright red. The reactor and terminal vent outlet share that intensity. One client-only, shadowless light with a 4.5 m range follows the visible plasma to illuminate nearby chamber surfaces in the current fuel/alarm colour. Its strength follows the core emission and growth/shrink envelope; it turns off with the hidden core and is released when the reactor closes. Surface bloom depends on the player's graphics settings; the mod does not alter them.

The server derives load from native `CurrentOutput / MaxOutput`, smoothed with a 60-tick response. Running ring speed ranges from three times the original speed at zero load to nine times at full load. Both primary and secondary phase/rate are saved and synchronized. Each ring has a perpendicular second rotation axis with distinct alternating signed rates (magnitudes 0.07/0.09/0.11/0.13), driven by smooth phase modulation; shutdown brakes both axes from their captured speeds. Tiles and plasma share a smooth irregular drift and gentle vertical bob that grows with load, stays below 6 cm, starts near the end of startup and settles during shutdown. The plasma keeps its rest orientation relative to the reactor while sharing the field's drift/bob and ejection translation. The containment shell tumbles around multiple axes: slow continuous yaw/roll spin is combined with unequal broad sweeps that reverse direction and carry the shell through half-turns, plus the smaller 6°–9.25° irregular tilt. The saved load-driven spin phase drives this motion without per-frame randomness or jumps at phase wrapping. Shutdown brakes the tumbling, then aligns the intact shell before reverse assembly releases its first quartet. Translational wiggle/bob and ring movement are unchanged. This motion is presentation; the separate normalized heat state drives vent purging/damage.

## Geometry and authoring

[build_deployable_chamber.py](assets/build_deployable_chamber.py) authors the original 89 startup parts and [deployment.json](assets/deployment.json). The field has nominal radius 0.88 m with 0.045 m tile thickness; four ring radii are 1.09/1.29/1.49/1.69 m. Two tile shapes are reused by 60 and 20 congruent instances. The solid central island stays fixed while four surrounding leaves retract.

[build_vent_bell.py](assets/build_vent_bell.py) and [vent.json](assets/vent.json) describe the recessed upper bell, ceiling pocket and six sleeves. Their smallest inner radius is 1.924 m, sitting 4 mm outside the floor fuel trace. The earlier 32 intake vanes were removed because they conflicted with the lined passage; the Intake state now times the doors without a vane loop. Native emissive strips on the bell, shield and doors follow the selected fuel.

[build_ejection_hatch.py](assets/build_ejection_hatch.py) removes the visible top conveyor skin while retaining its centered conveyor dummy. Four leaves sharing one MWM open a 3.72 m visual bore by dropping 0.3 m and sliding 1.95 m diagonally; the later passage revision removes the former intake vanes. The hatch is render-only and static roof collision is unchanged.

[build_ceiling_hatch.py](assets/build_ceiling_hatch.py) adds four inner doors sharing the VentHatch mesh and its underside trims/emissives. From Z=2.365 m they lift 0.32 m, then slide 1.98 m between the dispensers, rotated 45 degrees relative to the outer doors. A radius-1.86 m lined bore and retraction pockets connect the inner and outer openings; overlapping central tube geometry was removed.

[highlight_inventory_hatches.py](assets/highlight_inventory_hatches.py) assigns each conveyor detector to its access-hatch mesh, with the intended frame left unselected. The reported failure was traced to zero mesh sections in the compiled MWM despite correct detector targets. The helper now gives all four hatch meshes the `_section` suffix required by MwmBuilder and updates their detector links. At the earlier four-hatch stage, the compiled MWM contained four matching sections, each with 1,146 indices; revision `lab_3ed994c27b1f` was deployed. That evidence predates replacement of the top hatch. In-game highlighting remains unverified. The current glass uses native dirt/chrome textures; material tuning and the first-load emissive retry are recorded in [LEARNINGS.md](LEARNINGS.md).

Iterate geometry in Blender using Blender MCP and SEUT. **Do not run regression suites unless the user asks.** Review static poses in Blender; do not create a substitute timeline animation. Earlier [mockups](assets/mockups/README.md) and shape scripts are historical stages and can overwrite later work if rerun indiscriminately.

### Reactor sound and feedback

The original procedural sound bank uses resonant tones, beating harmonics and
distortion, with upper harmonics adding definition to the deep field tones.
[Listen to the palette](validation/audio/reactor-palette.wav): assembly
at 0s, ignition/running at 8s, increasing load from 13s, instability from 23s,
vent at 30s, explosion at 34s and shutdown at 40s. This is an abbreviated listening
demo, not an in-game recording or the actual startup timing.

[Reactor.Sound.cs](src/Data/Scripts/ArcanePower/Reactor.Sound.cs) mixes field and actuator
3D loops from the replicated motion, load and heat. Assembly follows progress and
actuator pauses. Assembly starts at 0.65× pitch. Resonance and load hum blend five
native pitch levels from 0.65× at idle to 1.10× at full utilization, following the
saved/synchronized one-second load response. Pitch falls as demand falls;
reaction loops fade with residual heat during cooldown and reach silence at the
15% dismantling threshold, even if maintenance or actuator power delays teardown.
Ignition fires
when plasma appears, while shutdown and payload ejection have separate cues.
First snapshots/reloads restore loops without replaying historical one-shots.
Emitters stop on removal and outside 160m; dedicated servers do not create them.
Ejected cores retain a fading resonance or critical distortion at their physical
carrier. Native realistic-sound hearing rules still apply.

The core uses the original dark, static filament material, selected again after
reviewing the reactive and sunspot variants. Its surface does not change brightness
with load or heat and has no animated texture swaps. Steady fuel-coloured chamber
lighting follows only core growth/shrink; ejected-core lighting fades on decay.
Startup growth, shutdown shrink, bobbing, sounds and reactor behavior remain.

The core retains its own orientation while sharing the field bob. Critical detonation uses the custom energy-fracture sound with the native
large-warhead particles scaled by the same cube-root tier factor as the blast
radius. Native explosion replication carries both sound and effect, including
detonations after carrier removal. Damage, fuse and safety checks are unchanged.
Ordinary block damage/destruction retains its native sounds/effects.

Tile placement has a crisp dispenser release and a damped, low thunk with a short
catch click, once per simultaneous quartet. Short attack fades preserve the
contact transient without a sustained metallic ring. Initial assembly follows the authored release/contact
points at 320 + 36×batch and 34 ticks later. Replacement releases at maintenance
tick 24 and latches at completion (90); both follow the controller installation’s tile deployment rate.
The local observer suppresses replay after first snapshots, approaching from
outside earshot and prediction corrections. Separate emitters let release and
latch tails overlap without interrupting ignition/ejection sounds.
Normal disassembly has a geared release/pull cue as each quartet leaves the field
and a deeper catch at its dispenser. These follow the reverse tile timeline,
including interrupted startup, with silent reload/approach baselines and no replay
after prediction corrections. Ejected tiles do not play retraction cues.

Deck and vent-hatch motor loops combine low motor body with brighter gear harmonics
and dry tooth chatter. They follow opening/closing, including reverse deck
motion during teardown. They stop on actuator pauses; the roof hatch and terminal
outlet have separate spatial emitters. Interior field/ignition/shutdown sounds reach
24 m and tile/deck/hatch sounds reach 18 m. Native `Poly2` attenuation gives
25% gain at half range, 6.25% at three-quarter range, and silence at the boundary.
The external vent discharge reaches 60 m; the explosion reaches 1500 m.
[Listen to the mechanism palette](validation/audio/reactor-mechanisms.wav): deck
at 0–2 s, three tile releases/latches at 3–5 s, hatch motion at 6–7.5 and
9–10.5 s, and retraction/catches at 12–14.2 s. This is a palette preview, not a game recording. Focused acceptance
checks in `tools/check_mechanism_feedback.py` and the mod compatibility build
passed; in-game levels, realistic-sound hearing and multiplayer audition remain
unverified.

Regenerate the thirteen mono 44.1kHz/16-bit PCM assets and twenty-one SBC cue
definitions (pitch variants reuse their source WAVs) with
`python3 ArcanePower/assets/build_audio.py` (NumPy required). No third-party sound
recordings are used. `python3 ArcanePower/tools/check_audio.py` checks asset paths,
format, headroom, DC offset and loop seams. Asset checks and the SE compatibility
build passed; no regression suites, deployment or in-game audition have run for
this pass. Spatial falloff, realistic mode, overlapping reactors, multiplayer
transitions and blast size still need in-game review.

`python3 ArcanePower/tools/check_reload_retraction.py` exercises the actual changed
C# methods for legacy/current save restoration, initialization interlocks, and
reverse tile cue timing using engine doubles. It does not reload a game world.
`python3 ArcanePower/tools/check_core_feedback.py` checks the actual core emission,
growth/shrink and pose methods, plus the delivered sound ranges and falloff.
`python3 ArcanePower/tools/check_hum_pitch.py` checks adjacent pitch blends,
voice fade behavior and native semitone definitions.
Build and focused checks passed; in-game visual/audio review remains pending.

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

[Reactor.VentRoute.cs](src/Data/Scripts/ArcanePower/Reactor.VentRoute.cs) follows up to 16 contiguous, functional, aligned duct/outlet sections on the same grid. The terminal outlet shares the reactor Intake clock; all route lamps show connection readiness and vent alarms; ejection travel grows with route length. The required installation is 1–15 fully built tubes plus an outlet. Missing or broken routes block startup, shut down generation and pause a committed launch until repaired; direct roof ejection is removed. Elbows, arbitrary obstacle checks beyond the outlet and moving shutter collision remain unfinished. Physical discharge now begins beyond the outlet plane.

[Reactor.Tiles.cs](src/Data/Scripts/ArcanePower/Reactor.Tiles.cs) reserves **80 tiles before initial startup** in survival. Assembly still animates twenty quartets; inventory is reserved upfront, not during each flight. Normal shutdown retains installed stock and wear. Running maintenance consumes four tiles per batch, initially 1/2/4 batches per minute at full tier load before heat adjustment; idle wear is 20%, and the quadratic heat factor reaches 4× at 100% heat. An unreplaceable worn quartet now causes 10% output, 10× fuel burn and runaway heating, with an incomplete alarm. Resupplying four tiles can arrest the runaway before supercriticality. Conveyor replenishment targets 80 loose tiles of each supplied grade (480 L total) within the 2,000 L reactor inventory. Venting discards installed tiles; a subsequent manual restart needs another shell. Creative mode supplies tiles without consumption.

All three tile grades work with Aether, Helion and Empyrean. New installation and maintenance choose the highest available grade in same-grade quartets; a shell can contain quartets of different grades. Installed grades and wear survive shutdown and save/reload; loading better stock does not upgrade installed tiles without paid replacement; venting or detonation discards all grades.

| Tile grade | Lifetime | Ingredients per four tiles | Base crafting time |
| --- | --- | --- | --- |
| Standard | 1× | 20 iron, 8 cobalt, 4 silver, 2 platinum; 4 superconductors, 4 computers, 1 detector, 4 metal grids | 10 s |
| Reinforced | 10× | 10× every Standard ingredient | 100 s |
| Advanced | 100× | 100× every Standard ingredient | 1,000 s |

Recipes mix ingots with self-control components. Higher grades reduce delivery and replacement frequency while maintaining the same material cost per wear budget. Wear remains dependent on fuel, load and heat; it pauses during quartet replacement. Telemetry shows available complete quartets by grade and forecasts reserve endurance across the installed grades. Component geometry and icons are shared. Regenerate these definitions with `prepare_lab.containment_tiles()`, without running the full lab generator. Installed quantity, wear and starvation are persisted/synchronized; copied entity IDs cannot inherit another reactor's installed reserve. Maintenance replacement now cycles through the twenty quartets, retiring each worn group and launching four replacements from fixed pillar dispensers into the moving shell. The 90-tick sequence follows the controller installation’s 1×/1.5×/2× rates, is saved/synchronized, and completes before normal dismantling. Terminal information includes loose stock, restart shortages and maintenance endurance at current load/heat. Balance, flight clearance and lifecycle validation remain outstanding.

See the [remaining-work overview](../docs/arcane-power-remaining-work.md) for the implementation sequence and evidence gaps.

## Grid power and inventory UI — 15 September 2026

[ContainmentController.cs](src/Data/Scripts/ArcanePower/ContainmentController.cs) places native electrical sinks on the two external controllers. SE pairs a generator and electrical sink in the same component container as storage, so the reactor remains a normal source while controllers draw the operating energy. The new `ArcaneContainment` sink group has priority 2 (after vanilla safe zones, before defense) and accepts partial supply. Native grid behavior and split/merge handling still require game review.

[Reactor.Power.cs](src/Data/Scripts/ArcanePower/Reactor.Power.cs) uses provisional containment demand **1/10/100 MW**, a **90-second** internal shutdown reserve (**0.025/0.25/2.5 MWh**), and up to three times operating demand for charging. Full precharge therefore requests **4/40/400 MW** and takes approximately **30 seconds** with sufficient grid supply, before the existing assembly and output ramp. Startup requires grid input and a full reserve; the reserve cannot start the reactor or export electricity. Creative also requires electrical supply. Reserve charging uses actual distributed input, and persisted energy remains tied to the original entity ID.

A containment-input shortfall triggers controlled shutdown and manual restart lockout. Grid input or the reserve powers cooldown, dismantling and vent actuation even after the reactor is disabled. An exhausted reserve pauses mechanisms until input returns; passive cooling continues. A destructive breach is not implemented. Older saved prototypes start with no reserve unless they have saved this version's charged state. Terminal information shows input/request, gross generation and net contribution after containment/charging, reserve seconds, and supply/shutdown reasons.

The reactor inventory now receives an explicit six-item whitelist and matching empty-slot tooltip on server and clients: Aether, Helion, Empyrean and Standard/Reinforced/Advanced Containment Tiles. The reactor-specific definition uses the same filter for native conveyor pull information. This replaces the stale generic tooltip derived from empty native `FuelInfos`; alternative-fuel consumption remains scripted to avoid native simultaneous-fuel requirements.

This script pass is compiled and locally deployed; the model revision remains `lab_06d121e6bcac`. No regression suites or game reload were performed. Supply accounting, UI appearance, late joins and maintenance flight clearance are implemented but not yet game-validated. See [build log](validation/survival-power-build.log).

## Knowledge graph

The scoped [JSON graph](graphify-out/graph.json), [interactive view](graphify-out/graph.html) and [audit report](graphify-out/GRAPH_REPORT.md) index these documents and selected small runtime/authoring tools. Heavy binary assets and generated per-part coordinate arrays are excluded. The repository-wide graph is separate.

## Thermal failure and plasma delivery — 16 September 2026

The local mod now contains `lab_64ff9a73f168`: updated smooth plasma, open thick containment frames, seven embedded collision models, generated CM/NG/ADD textures, spent-part definitions and direct-script thermal/physical ejection. The native upgrade empties and housing retain the selected fit. The final script build passed with zero warnings/errors; 54 delivery files were copied. [Static fuel-colour preview](validation/plasma-fuel-review.png), [behavior and remaining limits](THERMAL-FAILURE.md), [deployment record](validation/local-deployment.json). No game reload, destructive test or regression suite was run.

## Reactor housing collision repair — 9 October 2026

[build_reactor_collision.py](assets/build_reactor_collision.py) replaces the old
thin bottom plate, four rectangular base blocks and quarter-pane hulls with a
full round base/platform, a roof platform and eight narrower glass hulls. All ten
convex bodies have their placement baked into mesh vertices. The old exported
base/roof shapes were centred at the origin and relied on separate rigid-body
transforms; the new Havok shapes directly occupy the intended model coordinates.
The base supports the deck at Z=-1.26m, the roof supports Z=3.75m, and glass follows
the visible 4.944m radius without blocking the outer ledge.

[Focused geometry probes](assets/check_reactor_collision.py) passed 768 base,
768 roof and 128 glass contacts plus 384 clear-ledge probes. Native exported
shape bounds match within 5mm, and the game model importer verified all 110
dummies and the visible bounds are unchanged, with the new HKT embedded exactly
in the MWM. [Source evidence](validation/reactor-collision.json),
[compiled evidence](validation/reactor-collision-export.json).

The native Havok world additionally passed **1,664** base-side, deck and roof
ray contacts using the installed game's physics library
([repeatable check](tools/check_reactor_havok.py)). The running game had loaded
the previous model before this corrected export; ordinary world reloads can
retain that model in SE's cache. `prepare_lab.py` now references a content-hashed
copy of the reactor MWM, giving each revision a fresh model/physics cache key.
This supersedes the main reactor collision in the earlier delivery above. The
local mod is a symlink to `src`; reload the world to load the new definition.
No in-game walk/jetpack check or regression suite was run. Moving hatch
collision remains unimplemented: the base/roof platforms are static, including
across the visual hatch openings. MwmBuilder still reports degenerate triangles
in the visual mesh; export succeeded after bypassing a Wine/.NET trace-listener
failure in a temporary copy of the compiler.

## Construction stages — 9 October 2026

**Art revision, 12 October:** all 36 stages now follow the vanilla large battery's
construction language: broad open channel steel, diagonal webs and corner knees,
exposed mounted components, then grouped armor sheets with open service bays.
Capacity cells, transfer transformers and stabilizer coils are visible before
completion. The Energy Core's last stage includes its unpowered central assembly.
The reactor and vent frames retain their round chamber/exhaust openings. Finished
models, accepted collisions and build thresholds are unchanged.
[Reactor/hardware sheet](validation/construction-stages.png) ·
[Energy Core family sheet](validation/energy-core-stages.png).

The reactor, standard/advanced controllers, vent tube and vent outlet now each
have three native build-progress models: exposed construction-steel framework,
installed internals, then partial housing. Glazing, powered trim and animated
subparts appear with the completed model. [Preview](validation/construction-stages.png).
The vent stages retain an open central bore. Each stage embeds its finished
block's static collision, matching SEUT's normal fallback behavior.

`BuildProgressModels` uses bounds `0.33`, `0.67`, `1.00`. SE scales these against
the block's critical (functional) integrity threshold, as with vanilla blocks;
the final model appears at that threshold. Grinding reverses the same stages.
Reactor motion now refreshes dummy rest poses when the native model changes,
without resetting saved motion, fuel or installed tiles.

To regenerate, run [build_construction_stages.py](assets/build_construction_stages.py)
and [export_construction_stages.py](assets/export_construction_stages.py) in the
prototype Blender project, then `python ArcanePower/tools/compile_construction_stages.py`.
Compilation uses the installed SEUT toolchain and updates the five definitions
with content-hashed stage references. Definition generation and local deployment
also preserve this hookup. [render_construction_stages.py](assets/render_construction_stages.py)
renders matched stage views for inspection.

The same stage author/export scripts also run in `assets/arcane-energy-core.blend`;
compile that family with `python3 ArcanePower/tools/compile_construction_stages.py --energy`.
`build_energy_core.py` reuses the shared stage author when regenerating its whole
family. After rendering both files, `tools/construction_contact_sheets.py` updates
the review sheets. Stage changes receive fresh native model paths automatically.

The [focused acceptance check](tools/check_construction_stages.py) passed all 15
delivered models through the native importer: nonempty geometry, construction
material, bounds inside the finished envelope and exact embedded HKT. It also
checked animation-cache transitions through completion, grinding and repair.
`dotnet build arcane-systems.sln` passed with zero warnings/errors.
[Evidence](validation/construction-stages.json). Live welding/grinding and
character collision still need in-game verification; no regression suite ran.

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


## Containment tile grades and inventory — 9 October 2026

Standard/Reinforced/Advanced tile lifetimes and crafting costs are 1×/10×/100×;
all grades support all fuels. Grade state is initialized explicitly for every quartet.
The reactor inventory is now 2,000 L at the normal inventory multiplier.
`python3 ArcanePower/tools/check_tile_tiers.py` checks actual tile accounting
with recording stand-ins, explicit grade state, mixed grades, starvation recovery, forecasts,
XML and protobuf roundtrips, conveyor selection, recipes and inventory size.
The focused check and SE compatibility build passed. No game reload or existing
regression suite was run; crafting, native inventory behavior and multiplayer
operation still need game review.


## Asteroid ore and dense fuel progression — 9 October 2026

| Ore | Deposit weight | Mined-ore ratio | Base refining yield | Concentrate/fuel volume |
| --- | --- | --- | --- | --- |
| Aetherite | 5 | 0.1 | 0.1% | 0.01 L/kg |
| Helionite | 2 | 0.03 | 0.01% | 0.005 L/kg |
| Empyrite | 1 | 0.01 | 0.001% | 0.001 L/kg |

All three are rare, detector-visible asteroid materials, with successively lower
mining and refining yields. Vanilla asteroid deposit weights are scaled uniformly
by 100, retaining their relative weights, mining yields, textures and other
properties; each vanilla deposit has weight at least 100. These are relative
selection weights, not percentages or guaranteed counts per asteroid. Native
selection/removal of materials still controls each procedural deposit. This uses
native definitions for generator versions 3 and later; no voxel-scanning script
runs, and planetary ore maps and meteorites do not supply these materials.
Other mods overriding the same vanilla materials can change the final weights.

Raw ore occupies 0.37 L/kg. Refining removes its bulk matrix and concentrates the
active material: densities are 100/200/1,000 kg/L. Volumes are at least the native
inventory quantum per kg. Batches of 100 kg produce 0.1/0.01/0.001 kg of concentrate
in 10/20/40 base seconds. Standard refinery effectiveness and speed upgrades still
apply. Assemblers use 1 kg concentrate per 1 kg fuel, adding 1 kg of the preceding
fuel for Helion and Empyrean, at 10/30/90 base seconds; native assembler/world
multipliers apply. Higher fuels therefore require mining their own rare ores.

The mod is in alpha; definition and state changes do not include migration support
for older test saves. Refining and preparation recipes have explicit names/IDs.
The native asteroid provider rebuilds from its stored seeds and current material
definitions, so regenerated procedural asteroids can change deposits. No world
was loaded, terrain edited or save rewritten in this pass.

Regenerate only these assets with `prepare_lab.fuel_definitions()`.
`python3 ArcanePower/tools/check_fuel_progression.py` passed: definitions/references,
rarity ordering and unchanged vanilla properties, yields below platinum/uranium,
finite dense volumes and cumulative recipe ingredients.
Actual discovery frequency, drilling, refinery throughput and fuel preparation
still need in-game balance review.

### Fuel artwork

All nine ore/concentrate/fuel items and the empty containment canister have original models and rendered inventory
icons, with matching recipe icons. Aether uses cyan, Helion amber and Empyrean
violet. Fractured mineral rocks, hexagonal concentrate slugs and armored fuel
cartridges distinguish processing stages; one/two/three assay marks and cartridge
bands also identify tiers. The three deposits have original seamless near/far
colour-metal, normal-gloss and AO/emission textures. Vanilla ore materials and
all production/balance values are unchanged.

Fuel cartridges are now 1.5× their original model size (0.261 × 0.438 × 0.261 m
in SE axes), with correspondingly larger native item collision. Their emission
mask is reduced from 0.85 to 0.25 to retain the tier hues under bloom.
Packed material textures convert through PNG: the installed converter treats
entirely zero legacy TGA alpha as opaque. That previously made the fuel surfaces
paintable and the plasma fully metallic, suppressing its diffuse-based emission.
The plasma material experiments were subsequently reverted at the user's request:
the delivered CM/NG/ADD DDS files are restored byte-for-byte to the original dark
version. Corrected PNG sources remain as authoring references; they are not
reconverted during cache refresh. `python3 ArcanePower/tools/compile_plasma_material.py`
versions the existing DDS maps, recompiles their material bindings and refreshes
reactor/ejected-core model definitions. Add `--refresh-cache` for fresh paths even
when content is unchanged. The latest dark-material reversion still needs an
in-game reload to review.

[Visual sheet](validation/fuel-assets.png) · [Blender source](assets/arcane-power-fuels.blend)

Rebuild with `blender -b --factory-startup --python assets/build_fuel_assets.py`
from this directory, then `python3 tools/compile_fuel_assets.py`. The compiler
uses the installed Wine/MwmBuilder/texconv setup and refreshes only fuel
definitions through `prepare_lab.fuel_definitions()`. The separate fuel blend
does not modify the reactor's authoring file.

Ore items explicitly use a one-entry `Models` list: the native floating-object
code otherwise replaces `Model` with vanilla amount-based debris. Dropped ore
uses its deposit's voxel shader, while concentrates and cartridges use their
own packed model materials. Native floating-object sphere/box collision is
derived from model bounds; these items do not need block-style Havok exports.

`python3 tools/check_fuel_assets.py` checks compiled MWM bounds/material paths,
all definition links and BC7 formats/full mip chains. Export evidence is in
[fuel-assets.json](validation/fuel-assets.json). The local mod symlink exposes
the assets on the next world load. Inventory, dropped objects and voxel
near/far appearance still need in-game review; no live game or regression suite
was run for this art pass.
