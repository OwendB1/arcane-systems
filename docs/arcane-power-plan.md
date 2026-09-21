Arcane Power — implementation plan, revision 0.9

Updated 15 September 2026. Implementation and export prototyping have started. Names, production recipes, final power values, and failure severity below remain proposals unless identified as accepted or implemented.

Accepted direction after initial refinement: the general scope and delivery sequence, sustained electrical generation with meaningful startup/cooldown, and an expandable battery that handles surplus output, peak demand, startup, and emergency containment. Controllable reactor venting is also in scope. Its detailed hardware, operating modes, and balance below are proposals to refine.

The [first Blender review set](../ArcanePower/assets/mockups/README.md) established silhouettes and scale. The current [engineering prototype](../ArcanePower/README.md) now implements all motion directly in C#, following user approval to replace Animation Engine and add normal shutdown. Its 103 subparts include the existing 89-part startup, six telescoping shield sleeves, four outer hatch leaves and four inner ceiling leaves. The accepted vent now ejects the core and deployed rings upward in a finite cycle, purges normalized heat and damages the reactor/attached modules. Ejected rings/tiles now become physical spent components beyond the outlet, with an independently saved hazardous plasma core. Moving roof-door collision remains unfinished. See [thermal failure implementation](../ArcanePower/THERMAL-FAILURE.md).

Current accepted reactor envelope is **5×5×3 cells (length×width×height)**, or SE definition `Size=(5,3,5)`: 12.5×7.5×12.5 m. Round housings have been widened to sit flush with native-size interfaces. Front/back and centred top/bottom faces provide conveyors; left/right base bays provide upgrade sockets, replacing the raised receiver boxes. The chamber uses nearly transparent curved glass seated into both housings. Roof panels and decals stay beneath the common three-cell ceiling plane, with millimetre-scale recessed detail for an exposed roof.

Current workflow: **iterate geometry in Blender; run no regression suites unless the user asks.** Do not create another Blender timeline preview. Direct mod state owns startup, normal shutdown and finite ejection. Requested spectator recordings now demonstrate low-load startup/shutdown and vent ejection on revision `lab_c05a1c7be62e`; the reactor and both controllers were repaired afterward. The subsequent hardware/tile pass exported five models, compiled without warnings/errors and locally deployed 45 files as `lab_5d37d651a7ca`. It has not been loaded for game review. See the [remaining-work overview](arcane-power-remaining-work.md); earlier AE/offline checks are historical.

The current geometry uses vanilla SE cargo/conveyor references, parks nested rings in an annular bay around a solid central island, and provides four dispensers angled inward/down 45 degrees under the pillar tops. Eighty thick outlined tiles assemble in twenty batches of four. [The v02 startup study](../ArcanePower/assets/mockups/STARTUP.md) is historical; the new implementation uses exported subparts and generated C# geometry. Those triangles now have a physical component model, provisional assembler recipe and server inventory accounting. Quartet maintenance animation is implemented; survival balance and in-game validation remain unfinished.

Arcane Power becomes a separate entry in Arcane Systems: an industrial power installation with a visible plasma core, fuel-dependent containment hardware, a controllable exhaust system, and an expandable energy store. Its gameplay loop is **mine → refine → prepare fuel → establish containment → generate power → store and release energy**, with controlled shutdown and venting completing the operating cycle.

The requested foundation is three fuel levels requiring **two, three, and four containment rings**, respectively. External upgrade blocks physically attach to the reactor and control those rings. Ring emissives identify the active fuel. The reactor and battery share Arcane Ship Cores’ visual language.

**Visual direction and scope**

Use the third supplied image for the main composition: a heavy lower generator housing, an upper containment cap, an exposed luminous reaction chamber, and substantial side connections. Use the first two images for the suspended core and independently moving rings. Explore two arrangements in Blender: tilted gyroscopic rings around a central core, and stacked rings around a vertical plasma column. The first is the initial preference because it connects most directly to the old models; the third image supplies the surrounding machinery.

The existing core and upgrade icons show blue-grey industrial panels, strong bevels, recessed machinery, fittings, and small displays. Carry these into the reactor base, upper cap, module connectors, and battery casing. Keep the luminous chamber readable through the frame. Mechanical surfaces remain paintable; dedicated emissive strips carry fuel colour. Confirm materials against an in-game Arcane Core before final texturing: the repository icons alone cannot establish the complete material palette.

Start with one large-grid reactor and one large-grid battery family. Compare a compact shipboard blockout against a larger engineering-room installation with astronaut and existing-core scale references before fixing block dimensions. Small-grid variants and elaborate decorative pipe packs can follow after the full large-grid loop works.

Arcane Power should operate independently of Ship Core Framework. Later, add its subtype IDs to relevant Arcane Cores limits and check framework power modifiers for compatibility. Sharing a visual identity does not require inheriting ship-class behaviour.

**Fuel and containment proposal**

Working names deliberately remain descriptive until the fiction and palette are agreed.

| Fuel | Proposed processing | Required external hardware | Active rings | Candidate emissive |
| --- | --- | --- | --- | --- |
| I: Stabilized fuel | New base ore → refined material → fuel cartridge | Two standard containment controllers | 2 | Cyan |
| II: Energized fuel | Base material + a second, rarer ore-derived catalyst → energized cartridge | One standard + one advanced controller | 3 | Amber |
| III: Exotic fuel | Earlier materials + a third, rare ore-derived additive → exotic cartridge | Two advanced controllers | 4 | Violet |

**Current implementation boundary:** actual Fuel I/II/III are selected and consumed at 10,000/100,000/1,000,000 MW. The highest compatible fuel present is chosen only Off/Idle at zero output, then locked through operation/shutdown. Initial balance burns one selected fuel unit per minute at full rated load; current higher-fuel recipes convert one lower unit to 0.1 higher at base 12/24-second times. Native FuelInfos remains empty because entries are concurrent inputs, not alternatives; the mod maintains selected-fuel capacity and public conveyor transfers. Ore distribution and startup-energy accounting remain unfinished; tile reservation and maintenance consumption are now implemented but await survival validation. Two functional controllers are required separately from ring capacity.


Three new ores are a proposed progression, not a requirement for three entirely separate production chains. Higher tiers should increase useful output and energy per cartridge while demanding rarer inputs, more startup energy, and stronger containment. Establish values through an energy budget covering refining, fuel preparation, reactor output, containment consumption, and storage losses. Account for world assembler/refinery multipliers so an apparently expensive recipe does not become trivial under common server settings.

Begin with standard refinery/assembler recipes where the game supports the required item types. Add a dedicated fuel processor only if special processing behaviour or presentation warrants another block. Prototype the reactor fuel representation early: native fuel support, per-instance output control, inventory filtering, and scripted consumption must agree before recipes and balance are finalized.

Each controller occupies a defined attachment socket. Verify position, orientation, completion, functional state, and controller subtype; proximity alone does not qualify. A controller cannot satisfy two sockets or serve two reactors. Lower fuel tiers remain usable with higher-tier hardware installed. The current implementation selects the highest available compatible fuel while Off/Idle with zero output, then locks that tier until shutdown; unsupported fuel cannot sustain operation. A future explicit selector would be a separate behavior change.

Represent moving rings as reactor model subparts, with external modules controlling their deployment and operation. Include all four ring subparts in the model hierarchy; inactive rings park in designed recesses or disappear only where the housing makes that believable. Validate the complete motion envelope before detail work. Animated rings are visual mechanisms; static collision and mount geometry must give players a predictable build envelope.

Keep the solid central island fixed and open the annular ring-storage bay around it. Four annular leaves drop 0.32 m and slide outward 1 m. Rings park horizontally below the deck, rise through this annular opening, and later tilt into their operating planes. Reserve that opening and full deployment volume in both mesh and static collision design. No ring should visibly pass through a solid floor, service panel, dispenser, or neighbouring block.

New ore work includes voxel materials, mined item definitions, refining recipes, icons, and distribution. Test ore availability separately on supported planets and procedural asteroids. Document effects on existing saves and already-generated terrain. Custom planet compatibility needs an explicit strategy rather than assuming every planet automatically gains the new ores.

**Reactor behaviour**

Use a readable operating sequence: off/parked → preflight and containment power → ring deployment → shell assembly → rings assume operating angles → ignition → running → controlled shutdown → cooling → shell recovery and ring parking → off. Faults can interrupt that sequence. Startup requires external power; a running reactor can cover its containment cost, but a grid outage or lost module must have a defined outcome.

**Containment shell assembly and consumable tiles**

Four dispenser heads build the low-poly inner sphere by placing four triangular facets per batch. The initial visual prototype uses one 80-triangle shell, assembled in twenty batches. The current implementation reserves eighty inventory tiles for a new shell, retaining installed material across normal shutdown; venting discards that reserve. This ratio remains a balance value. Higher fuels retain their required 2/3/4 rings; any change in shell count or tessellation requires a separate visual/performance decision.

Keep rings horizontal during assembly to leave the dispenser paths clear, then tilt and spin them after the last tile is installed. Ignition is gated on actual completion and hardware readiness. The current model includes all four rings and twenty four-tile batches under direct C# control. Its nominal field radius is 0.88 m, tile thickness 0.045 m, and ring radii are 1.09/1.29/1.49/1.69 m. The geometry manifest reports a minimum inter-ring radial-shell gap of about 0.1099 m and floor clearance of about 0.0644 m; validate the actual engine motion and repeated interruptions for all three hardware profiles. Native output stays at zero during startup and ramps over ten seconds after assembly reaches Running.

Implemented prototype item: a crafted **Containment Tile**, supplied through the reactor's normal conveyor-fed inventory. The tiles form a replaceable lining or field lattice that wears while the reaction runs. This gives cargo capacity, resupply routes, and production throughput a practical role alongside fuel and electrical reserves.

- Preflight checks fuel, controller tier, containment power, tile availability, and the required vent route before attempting ignition.
- Current accounting reserves all 80 tiles before startup and animates installation in batches of four. Installed stock and wear persist; validate interruption and save/load to ensure no duplicate debit.
- Running wear depends on fuel tier, operating load, and thermal stress. Replenishment replaces spent material in four-tile batches, with a short matching dispenser animation. Balance consumption in items per operating time, independently of client frame rate or visual update frequency.
- A controlled shutdown retains reusable installed material and its remaining wear budget internally for the next assembly. Do not restore worn material as pristine inventory components. Decide the loss from emergency venting or a breach during balancing; emergency dumping cannot yield both intact tiles and refunded stock.
- Low reserves produce a resupply warning and an estimated operating reserve. Failure to replenish degrades containment and triggers the configured shutdown/vent response while recovery remains possible. A visual missing panel reflects an authoritative state change; a hidden or delayed animation cannot itself cause damage.
- Conveyor disconnection is survivable while local stocks last. Expose tile stock, installed condition, replenishment state, and blocked input on the terminal. Fuel and tiles remain separate resources and separate inventory accounting.

The implementation tracks aggregate installed material/condition; flying subparts are visual, not inventory entities. Clients animate triangle subparts from those authoritative states. Test partial startup, stock removal mid-assembly, missed updates, save/load, grinding, blueprint/projector rebuilding, interrupted replacement, and late join for duplication or reset exploits. Initial balance uses 2 iron + 0.1 nickel + 0.2 silicon for four tiles in ten base seconds, one tile per facet, 1/2/4 maintenance quartets per minute at full tier load before heat adjustment, and total installed-shell loss on vent. These values remain tunable; quartet replacement animation and reserve estimates are now implemented, pending in-game review.

The maintenance cost must add a logistics decision without routine busywork. A healthy reactor should replenish automatically from supplied stock; visual replacement frequency can be reduced at distance without changing material consumption.

The reactor supplies sustained output with a player-selected operating level and bounded ramp rates. Starting, changing load, and cooling take meaningful time. Distinguish the reaction's generated energy from electricity actually accepted by the grid: when demand drops and storage fills, surplus must cause throttling, shutdown, or a defined thermal/venting cost. Prototype that behaviour against native power distribution; a scripted output limit alone does not establish a sustained reaction. Ordinary operation should be automatable without constant player intervention.

Expose selected fuel, fuel remaining, gross/net MW, containment reserve, temperature or instability, attached controllers, and shutdown reason in terminal information. Ring speed follows operating intensity, brightness follows field strength, and fuel determines hue. Use a separate alarm pulse and explicit status text so colour alone does not carry fault information.

Accepted initial power-loss behaviour is an automatic shutdown attempt using a finite, grid-charged internal containment reserve. The first implementation draws 1/10/100 MW through controller sinks and holds 90 seconds of operating energy; exhausted reserves pause mechanisms until power is restored. Severe containment loss can progress to a damaging breach after clear warnings and a recovery window. Decide whether that breach is local or threatens the surrounding ship before implementing damage. Fuel exhaustion, disabling the block, missing hardware, battle damage, and power starvation need distinct transitions. A cold reactor losing a module should simply become unready.

The first implementation exports electrical power directly, concentrating the challenge in fuel processing, containment, venting, and storage. AutoMcD-style plasma distribution to remote generators remains a possible later expansion. Reactor exhaust ducts serve disposal and cooling; they do not introduce a second power distribution network.

**Controllable reactor venting**

Use the reactor venting sequence in *Passengers* (2016) as the reference for scale, mechanical exhaust doors, warning buildup, and a forceful exterior plasma discharge. The film's blocked exterior vent motivates a gameplay distinction between commanding a vent and having a working exhaust path. This is fictional engineering inspiration; the following mechanics are Arcane Power design proposals. [Film sequence context](https://en.wikipedia.org/wiki/Passengers_%282016_film%29)

Add a reactor exhaust connection, dedicated duct sections, and an exterior vent outlet with animated shutters. Begin with a straight, same-grid duct run from one reactor to one outlet; evaluate bends and additional outlets after the basic route works. Validate continuity, orientation, functional state, and outlet clearance. A disconnected or blocked route cannot silently dispose of the reactor's heat or plasma. Define a bounded clearance check and exhaust hazard volume in the prototype; do not depend on simulating fluid flow or proving that an outlet reaches open space.

| Control | Intended behaviour | Tradeoff |
| --- | --- | --- |
| Manual regulated vent | Player selects a vent rate; controlled discharge reduces the reactor's thermal load | Sacrifices usable reaction energy and can reduce electrical output |
| Automatic vent | Controller regulates discharge toward a temperature target within a player-set maximum rate | Handles routine transients but remains limited by exhaust capacity |
| Emergency vent and shutdown | Stops fuel injection, opens the functional exhaust route fully, and dumps the active reaction charge | Loses that charge, interrupts generation, and requires cooldown/restart |

Expose vent mode, target/rate, emergency vent, and status through terminal controls and toolbar actions suitable for buttons and timers. Report commanded versus actual vent rate, route/outlet faults, thermal state, and shutdown progress. Changing automatic settings requires normal block access. A manual vent command can be stopped or adjusted; emergency vent commits to shutdown until restart conditions are met. Exact controls and programmable-block support are to be verified during the prototype.

Venting removes a finite thermal load and/or active plasma charge; it does not empty unrelated fuel inventory or restore missing containment hardware. Account for vented energy as a loss so it cannot also be exported as electricity. Higher fuels increase the required exhaust capability, with the same outlet model potentially supporting upgraded internals rather than requiring three unrelated designs. Venting must not bypass the 2/3/4-ring requirements or make the highest fuel safe with insufficient containment.

The battery bridges the generation drop during venting and powers containment and vent actuation through the shutdown interval. Proposed power-loss behaviour: an opened shutter mechanically latches open; loss of actuator power before opening reports a failed vent. Establish this as explicit simulated state, independent of whether a client's shutter animation has completed. Loss of containment power can still cause a breach even with an open vent, so venting is a recovery tool with finite capability.

The exhaust plume presents a directional danger to characters and blocks, including the ship's own structure. Players must design outlet placement and a clear discharge area. Obstruction reduces or prevents effective venting and reports a fault; simply hiding the particle effect cannot remove its server-side consequences. The initial implementation uses a bounded damage region and conservative obstruction checks; detailed plume propagation and propulsion forces are outside the initial scope.

Animate warning indicators, shutter opening, increasing glow, fuel-tinted plasma discharge, and a decaying cooldown plume with corresponding sounds. Effects track actual discharge. A failed shutter remains visibly closed with a fault indication; it cannot show a successful full plume. A local maintenance/override control may be added later, but routine operation must not require a character standing in the exhaust as in the film.

**Battery system**

Create an Arcane Energy Core as a second major machine: a visible energy centre with attached stabilizers, capacity modules, and transfer modules. Give it the same panels and fittings, with calmer motion than the reactor. Stored-energy fraction controls the visible core intensity and fill indicators; charging and discharging have distinct effects.

Its explicit role is to store energy, not generate it. It supplies containment startup before ignition, absorbs surplus reactor generation, bridges weapon/shield/industrial demand spikes, and sustains containment during shutdown, cooling, and emergency venting. This allows a ship to size its reactor for sustained demand and its battery for short peaks and reserve endurance.

Prototype one controller with two expansion levels. Capacity modules increase stored MWh; transfer modules control maximum charge/discharge MW; stabilizers maintain the supported storage configuration. Keep those limits separate so capacity upgrades do not imply unlimited output. A full battery can still lack sufficient discharge power for weapons and containment together; high discharge power can still exhaust a small reserve quickly. Provide normal Auto, Recharge, and Discharge behaviour, and let the battery supply reactor startup and emergency containment through the grid power system. Define emergency behaviour when Recharge mode would prevent reserve delivery, and make any automatic mode change visible. Do not assume the grid will reserve energy for containment over competing consumers; verify resource priority and load-shedding behaviour in the power prototype.

Vanilla batteries remain valid for startup and backup. The Arcane Energy Core earns its place through expandable high capacity, configurable transfer capability, and physical stabilizer/module placement. It is the preferred large-installation storage option, not an arbitrary prerequisite for reactor ignition.

Prefer native battery behaviour where it meets the design. Verify whether a single block can safely change capacity per instance; otherwise evaluate fixed-capacity battery modules contributing their actual native storage, with the central core presenting the aggregate. Avoid changes to shared definitions that accidentally alter every battery of that subtype.

Capacity removal must never create energy. A planned removal can require discharging to the remaining capacity; destruction needs a defined excess-energy loss or vent rule. Save/load, blueprints, projection construction, and grid splits must preserve correct accounting. Wireless pylons and enormous remote storage networks are later options, not assumed requirements.

**Animation ownership: direct mod runtime accepted**

Animation Engine provided useful reference material for subpart interpolation and event-driven motion. Its inspected V2 libraries lacked a general bridge for arbitrary reactor state, and the terminal component was a stub. The user approved migrating all existing motion into Arcane Power itself. Earlier AE parser/VM results remain historical study material; the mod no longer ships BSL or requires AE in newly created test worlds. The current running world's mod list remains unchanged.

[Reactor.Motion.cs](../ArcanePower/src/Data/Scripts/ArcanePower/Reactor.Motion.cs) owns all matrices and visibility. Core phases are Off, Starting, Running, Cooling and Stopping: only sphere assembly accelerates by profile (1×/1.5×/2×), giving complete startup durations of 1,170/931/811 ticks; normal shutdown holds an assembled hot core in Cooling until heat<=15%, then brakes both ring axes for 90 ticks with a 60-tick plasma fade and reverses deployment at the original 1× speed. Available output ramps over 600 ticks after Running, with zero startup output. Interrupted startup reverses from its current fractional age.

The committed ejection cycle closes the shield for 240 ticks, opens the intake/hatch for 90, ejects for 120, closes the intake for 90 and retracts the shield for 240. Native generation is cut only after full shield closure. The cycle ends automatically Off, requiring a manual restart with a fresh field. Heat follows load with a 60-second heating response, cools over a 30-second response and is purged during ejection. A payload vent applies one synchronized damage event: 15% reactor and 20% connected compatible module maximum integrity at 100% load/heat, with greater damage above 100% heat. Discharge now hands off to native physical spent rings/tiles and a plasma carrier beyond the outlet; moving-door collision and obstruction handling remain later work.

[VentSession.cs](../ArcanePower/src/Data/Scripts/ArcanePower/VentSession.cs) provides a Vent reactor button/StartVent and ToggleVent actions, ownership-validated server commands, snapshots every 30 ticks and saved motion state. Live rendering, interrupted transitions, multiplayer and save/load behavior still need user-requested in-game review. Do not treat implemented synchronization or successful compilation as proof of these behaviors.

**Blender and asset production workflow**

Blender MCP, Blender 5.2.1 LTS and SEUT are operational. The current model has 103 subparts; final main/shared hatch exports finished. Four ceiling leaves lift and retract between dispensers, with a lined radius-1.86m passage to the outer doors. Earlier 89-part AE and binary-transform evidence is historical. Sixteen maintenance decals and sixteen accessible tiedowns are seated on native armor/deck panels. The upper bell, six sleeves and inner/outer doors now support finite ejection; the old 32 intake vanes were removed to clear the lined passage. No regression suites accompany these iterations unless requested.

Update from the mockup session: the installation's existing `export-check.json` records successful sample MWM compilation and Havok collision generation. The five mockup scenes are now saved and open for review. The installation smoke test was not an in-game inspection and does not validate these new models or their animated subparts.

The repository contains core/upgrade MWM models, construction-stage/LOD assets, and icons. The user confirmed that original Blender files and old reactor models are unavailable. Author fresh geometry against the supplied images and existing Arcane Core visual references.

For the SE integration pass, inspect the installed SDK's large-grid `CargoContainerSmall.FBX` and `ConveyorTube.FBX`, their material references, and logistics block definitions. The checked definitions give a 1×1×1-cell small cargo container, 3×3×3-cell large cargo container, and 1×1×1-cell conveyor junction/tube. Use actual geometry for port proportions and recessed panel/corner treatments, and the installed paint/conveyor textures for material studies. Place prototype conveyor connections on cell-aligned faces and distinguish them clearly from containment upgrade sockets and exhaust takeoffs. The v02 scene uses a provisional 5×5×5 large-grid envelope; valid mount points, conveyor dummy axes, inventory access, and final paint masks still need export/in-game checks.

1. Establish an asset/export smoke test: a simple block, one rotating subpart, a named emissive material, static collision, and mount points. Use Blender MCP to create and inspect the scene and Space Engineers Utilities to export it. Verify the result in game, including scale, subpart pivot, collision, and material response. Resolve tool compatibility here before building finished art.
2. Create reactor and battery blockouts in saved `.blend` files. Use MCP Python operations for repeatable geometry and the Blender viewport/screenshots for visual inspection of silhouettes, clearances, normals, materials, and animation. Use available UI/computer controls for export panels and visual checks where needed. MCP scene control and screenshots are confirmed; a general desktop mouse/keyboard tool was not exposed in this session, so UI-only operations need an available local route when execution begins.
3. Present front, side, top and perspective views. Use the direct mod runtime for motion; do not build another Blender timeline preview or run unsolicited regression suites. Compare against an Arcane Core and astronaut scale reference. Refine proportions before topology detail or UV work.
4. Produce the reactor housing, ring storage bay, upper cap/supports, four ring subparts, faceted shell with separately controlled tile batches, four dispenser heads, core/plasma mesh, and three controller designs. Include grid-aligned conveyor faces and service panels, the exhaust connection, initial straight duct, outlet housing, moving shutters, and discharge emitter dummies; review the outlet both closed and venting. Produce the battery housing, energy core, stabilizers, capacity modules, and transfer modules. Reuse panel treatments, fittings, and material palettes across this set.
5. UV unwrap, bake detail, and prepare game-compatible packed textures through the installed material/export workflow. Verify channel packing and emissive naming in game. Use image generation for concept sheets, original surface motifs, and supporting texture/icon artwork when useful; bake and author mechanical surfaces to match actual UVs. Render block icons from the final Blender models for consistency, with ore/fuel icons sharing the same palette and lighting.
6. Add collision meshes, construction stages, LODs, mount/conveyor/upgrade dummies as applicable, and consistent subpart origins. Confirm four rings can move through the whole cycle without intersecting the housing or exceeding the intended occupied volume.
7. Export MWM models and DDS textures, install into a local test mod, and compare in-game lighting, paint masks, damaged/build states, icons, and distance transitions. Keep source scenes, texture sources, and repeatable export instructions alongside the project.

Organization follows the existing mod layout: `ArcanePower/assets/` holds editable scenes and authoring scripts; `ArcanePower/src/` contains definitions, direct C# and exported models; `ArcanePower/tools/build_animation_geometry.py` generates C# geometry from the manifests, with `build_animation.py` retained as a compatibility entry point. `ArcanePower/ArcanePower.csproj` is in the renamed `arcane-systems.sln`. Add Workshop release metadata when packaging is authorized.

Visual refinement update: the user prefers the earlier rounded silhouette and closer adherence to Space Engineers models/specifications. The [v03 detail study](../ArcanePower/assets/mockups/DETAIL.md) restores a circular base and cap while retaining four grid-aligned radial connections. Inspection confirmed that the installed [SEUT asset library](https://github.com/enenra/seut-assets) includes reusable conveyor ports/frames/access hatches, upgrade ports, terminals, LOD variants, and surface decal atlases. Use these native-size interfaces and original UV/material references rather than approximate fittings. v03 includes a source manifest, detail renders, and the preserved two-ring/four-triangle startup. The current export prototype supersedes v03's dimensions and interface layout. Extend this surface vocabulary to remaining tiers, battery, and controllable vent system after review; direct runtime review and the survival loop remain phase 2 work.

**Delivery sequence and completion criteria**

| Phase | Deliverable | Ready to proceed when |
| --- | --- | --- |
| 1. Refine the brief | Record accepted reactor/battery roles; settle scale, rings, fuel progression, exhaust layout, and failure severity | Major architecture and silhouette choices are recorded |
| 2. Prove the technical path — active | Direct 103-part startup/shutdown, finite core ejection and actual three-fuel implementation; straight exterior vent route, tile maintenance, inventory UI and grid-funded containment reserve implemented; requested game review, then battery work | A crude in-game machine demonstrates state-driven visuals, sustained reaction accounting, actual grid transfer limits, vent losses/obstruction, and correct late join |
| 3. Build one complete gameplay loop | One mineable ore, refined fuel, two controllers, working reactor, basic battery, and controllable vent outlet | A survival player can mine, process, ignite, generate, store, vent, and shut down without admin spawning |
| 4. Extend progression | All three ores/fuels, 2/3/4 containment tiers, exhaust capacity progression, and battery capacity/transfer expansions | Invalid hardware/fuel combinations are rejected and upgrades preserve correct energy |
| 5. Finish the assets | Final models, textures, icons, effects, sounds, build stages, and LODs | Visual review and in-game export checks pass for each asset family |
| 6. Harden and package | Multiplayer, balance, compatibility, documentation, and Workshop-ready package | Tests below pass and dependencies are documented |

Validate single-player, listen server, and dedicated server with a joining second client. Exercise save/reload, reconnect, blueprint/projector rebuild, split/merge, ownership changes, damaged/removed controllers, mixed fuel, fuel exhaustion, grid blackout, capacity loss, and interrupted animation. Confirm client visual settings cannot change simulation, and that fuel/energy cannot duplicate across lifecycle events. Measure multiple reactors and batteries, including distant or invisible machines. Compare Arcane Power alone and alongside Arcane Cores/Ship Core Framework to detect conflicting power modifiers. Compile implementation changes as needed; run regression suites only when the user asks; in-game checks remain necessary for modelling, power distribution, and synchronization.

Include demand spikes, full storage during generation, charge/discharge rate limits, and containment reserve exhaustion. Test all vent modes, rate changes, emergency restart lockout, blocked outlets, broken ducts, shutter faults, power loss before/during opening, obstruction appearing during discharge, and fuel changes after cooldown. Save/reload and join while actively venting. Check plume damage on the authoritative server with particles disabled on the client, correct energy/fuel loss, and bounded performance for repeated obstruction checks. Verify that venting buys the intended recovery time without guaranteeing survival after unrecoverable containment loss.

**Choices for our first refinement**

- Accepted reactor role: sustained direct electrical generation with meaningful startup, ramping, and cooldown; storage handles surplus and transient demand.
- Accepted form: gyroscopic core within a rounded industrial housing, with two to four nested rings.
- Accepted scale: 5×5×3-cell reactor; external vents use a 3×3 cross-section with one-cell stackable depth; selected 1.6 m × 1.0 m piggyback controllers occupy one cell each, with curved mating skirts and 2.3 m reactor socket surrounds.
- Accepted failure: heat-dependent tile wear; failed maintenance cuts output to 10% of the prior load and raises fuel burn 10×. Supercritical cores explode irreversibly, inside or ejected, with 5×/20×/100× large-warhead damage and cube-root radius. Ejection can save the housing by moving the blast away. Below-threshold ejected cores decay. Threshold/fuse values are provisional; [implementation](../ArcanePower/THERMAL-FAILURE.md).
- Accepted battery role: startup, surplus capture, peak demand, and emergency containment, with distinct capacity and transfer limits and vanilla battery compatibility. Refine the attached module layout and stabilizer requirements.
- Venting: controllable reactor exhaust is required; refine the proposed straight duct/outlet layout, regulated/automatic/emergency modes, capacity progression, and plume hazard dimensions.
- Containment tiles: initial component, recipe, 80-tile reserve, maintenance batches and vent loss are implemented. Visible quartet replacement and reserve estimates are implemented; refine balance and validate the paths and accounting.
- Progression: the proposed three-ore cumulative recipes, final material names, and fuel colours.

Inspiration references: [AutoMcD’s MA Plasma Reactor](https://steamcommunity.com/sharedfiles/filedetails/?id=2847666099), [Draconic Evolution](https://www.curseforge.com/minecraft/mc-mods/draconic-evolution), and the three supplied images. These guide the design; Arcane Power’s assets and balance will be its own.

**Thermal/physical implementation update — 16 September 2026**

Phase 2 now also includes a saved, server-owned critical-core ledger, heat-dependent fuse, native explosion request, physical spent-ring/tile ejection and a dynamic plasma carrier. New filament plasma art is fuel-tinted, visible through open thick triangular frames, and exported with compound collision. Local revision `lab_64ff9a73f168` and all scripts are deployed; compilation succeeded. These paths remain unverified in-game. [Detailed behavior and tunables](../ArcanePower/THERMAL-FAILURE.md), [Blender preview](../ArcanePower/validation/plasma-fuel-review.png). No regression suites were run.

### Reactor status displays — implemented prototype, 16 September 2026

Shared grouped telemetry now feeds a compact terminal summary, SCF-inspired native
LCD dashboard, and an actual equippable handheld tablet with a live HUD dashboard.
The tablet is read-only and requires suit broadcast plus an accessible mutual
antenna connection to the reactor grid; it grants no remote control or terminal
access. Model, collision, material maps, icon and crafting recipe are exported.
Text HUD API provides the card overlay; native live text is the fallback.
[Setup and remaining game review](../ArcanePower/STATUS-DISPLAYS.md).
