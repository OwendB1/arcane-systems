# Arcane Power engineering learnings

Current runtime: all 103 parts use direct C# motion, including normal shutdown and finite core ejection. Actual fuel tiers and normalized heat/damage supersede the earlier Fuel-I-only and zero-discharge prototype. Animation Engine findings below are historical; see the final migration section. The user requires Blender-first review and no regression suites unless requested.

Evidence date: **2026-09-13**. SE1 client **1.210.014**, native Linux/Pulsar; prepared `$se-dev-game-code` snapshot reports the same version. Workflow preference: iterate geometry primarily in Blender; startup animation must use actual Animation Engine, not a Blender timeline preview. The user has now authorized preparation for the next in-game check; deployment/reload status is recorded separately below. These are implementation findings, separate from proposed mechanics in the [plan](../docs/arcane-power-plan.md).

## Grid dimensions and attachment

The user's **5×5×3 length × width × height** means SBC `Size x="5" y="3" z="5"`: SE uses Y up. Large-grid cells are 2.5 m, giving a 12.5×7.5×12.5 m model envelope in SE axes. Blender uses Z up, so the SEUT bounding box is X=5, Y=5, Z=3. Keep the lower conveyor row at its native cell height when compressing the housing. [Definition generation](tools/prepare_lab.py), [height fitting](assets/fit_three_cells.py).

The current top mount uses inscribed strips over the widened round roof, including outer grid cells while excluding empty corners. The bottom mount spans the 5×5 footprint. The earlier in-game revision had a central 3×3 top mount. In the lab, the placed reactor occupies approximately `[6,1,2]` through `[10,3,6]`; se-remote confirmed a real test armor block at `[8,4,4]` via `CubeExists`. The [saved response](validation/top-attachment.json) proves existence after placement; it is not a full mount/collision audit.

## Native upgrade connections

Controllers use the game's `UpgradeModule` block and `ArcaneContainment` additive upgrade. The reactor registers that key during `Init`, before the next-frame setup. Native module matching requires complementary `detector_upgrade` positions on directly neighboring grid cells; proximity or cosmetic socket placement alone does not count. Source: `MyUpgradeModule.InitDummies`, `RefreshConnections`, `CanAffectBlock`, lines 169–290 in the prepared `SpaceEngineers.Game/SpaceEngineers/Game/Entities/Blocks/MyUpgradeModule.cs`.

`MyMultilineConveyorEndpoint.GetLinePositions` derives the socket cell and direction from the dummy **translation**, block size, model offset and cell center. Dummy rotation is not used to choose its face. The local position is rotated into grid coordinates by `PositionToGridCoords`. Source: prepared `Sandbox.Game/Sandbox/Game/GameSystems/Conveyors/MyMultilineConveyorEndpoint.cs`, lines 74–82 and 150–181.

In the earlier in-game revision, exported runtime detectors lay at SE X=±6.15 m, Y≈0, Z=0. With the lab reactor rotated Forward `[-1,0,0]`, Up `[0,1,0]`, its two controller cells are `[8,2,1]` and `[8,2,7]`. Use orientation transforms for another placement, not these absolute coordinates. Native log values progressed **0→1→2**; the last observed `2` entry was 21:40:22.585. This proves native socket recognition only for that earlier arrangement; it does not validate the later base-level layout. Removal, damage and rotation combinations still need systematic testing. [Runtime interlock](src/Data/Scripts/ArcanePower/Reactor.cs).

## Model cache and export checks

In this client session, a world reload reused stale MWM data: old subpart translations remained at Y=-5.17/-4.67 and new upgrade detectors were absent. The local deployment now appends a SHA-256 content suffix to each block model path. After that revision changed, the log showed Y=-2.67/-2.17 for the parked rings and the new ±6.15 m detectors; the native connection count began working. This is observed cache behavior, not an engine-wide cache API guarantee. Stable distributable paths remain in `src`; only the local lab copies are rewritten. [Deployment implementation](tools/prepare_lab.py).

The original revision helper hashed block models only. It has now been replaced by a digest of the complete local MWM family: all model files are copied into one `lab_<digest>` directory, and local block definitions point there. Subparts resolve relative to the parent model directory, so rings, floor leaves and tiles must move together. Source definitions keep stable paths. This whole-family revision is implemented in `prepare_lab.py`; its next in-game cache refresh still needs verification.

SEUT can report a main export as finished while collision export reports failure. Inspect the whole export log and verify the final collision-bearing MWM. This prototype keeps ten collision bodies; the glazing colliders are conservative convex quarter shells, so fitting and character collision require in-game inspection. Keep automatic SBC export disabled to protect hand-authored definitions.

## Animation Engine V2 contract

The installed Workshop source is under `Data/Scripts/Math0424/Legacy`. Its loader uses **`data/animation/main.bsl`**, singular, and the prototype successfully loaded one V2 script in game. Source: `Legacy/AnimationEngine.cs`, lines 28–30 and 282–305; [upstream wiki](https://github.com/Math0424/AnimationEngine/wiki), [source repository](https://github.com/Math0424/AnimationEngine).

- Use explicit comparisons: `if (block.isworking() == true)`. A bare boolean call failed with “Cannot find logical symbol”; the corrected script parsed.
- Working-state events drive this first prototype: `create`, `built`, `working`, `notworking`, `damaged`. There is no proven custom reactor-phase bridge in the installed V2 contract. Future fuel/vent/startup phases need an explicit integration decision.
- `translate` subtracts its supplied vector while advancing the movement. Negative Y lifts a ring in SE coordinates. Source: `Legacy/Core/Movements.cs`, `TranslateAction.Tick`, lines 365–385.
- Spin speed is degrees per simulation tick; finite-duration spins can repeat through `api.startloop`. Do not assume a movement duration of -1 means forever.
- `reset()` restores the subpart local matrix and clears movement. Stop loops and delayed work explicitly on shutdown; `stopdelays()` alone does not stop a spin loop.
- AE implements `Emissive.setcolor`; its documented subpart `setemissive` entry is not implemented in the installed runtime. The current prototype deliberately assigns emissives to C# for hardware-profile colours. Inventory-fill ratio alone cannot identify a fuel tier.

Primary installed sources for these details: `Legacy/Core/ScriptLibraries/Emissive.cs`, `ScriptAPI.cs`, `Legacy/Core/EntityComponents/BlockStateComp.cs`, `InventoryFillComp.cs`, and the V2 language dictionary. The [current BSL](src/Data/Animation/main.bsl) now generates the deployable 89-subpart startup described below; actual lift, spin and repeated shutdown behavior remain unproven in game.

## Chamber glazing

The original flat dark panes obscured the core and left visible gaps at the housing. The replacement is a cylindrical chamber with four quarter panes; seams sit behind pillars. The first curved revision had radius 4.12 m and Blender model Z from -1.40 to +2.96 m, overlapping the deck and upper cap. The later housing-widening pass scales chamber XY by 1.2 (radius 4.944 m). Annular metal seals hide the joints. [Authoring script](assets/curve_chamber_glass.py).

`ArcanePower_ClearChamber` uses the SEUT **GLASS** technique and its own transparent-material definition, rather than overriding vanilla glass globally. It references the installed game's `SquareWindowDirtInside_ca.dds` and `Chrome_ng.dds`, initially with colour alpha 0.06, reflectivity 0.02 and Fresnel 0.10; the later in-game visibility correction below supersedes those values. Source: installed `Content/Data/TransparentMaterials.sbc` (`GlassInside`), and [mod material definition](src/Data/TransparentMaterials.sbc). These are shader parameters, not a promise of 94% visible transmission: the renderer, texture alpha, lighting and two-sided geometry affect the result. The first curved revision exported/reloaded successfully and showed the core and far pillars through the glass. Later widening and interface edits have not been checked in game. Full housing-contact and collision acceptance remains pending. Further game checks await an explicit user request.

## Conveyor interaction reference

The final requested layout has four accessible conveyor/inventory panels: front/back plus centered top/bottom, with left/right base bays dedicated to upgrades. The vanilla `MyUseObjectInventory` class handles both `[MyUseObject("inventory")]` and `[MyUseObject("conveyor")]`. Its supported actions include opening inventory, opening the terminal, Build Planner and deposit. A correctly placed full-hatch `detector_conveyor` can therefore provide these native interactions without stacking an overlapping inventory/terminal dummy. Source: prepared `SpaceEngineers.Game/SpaceEngineers/Game/Entities/UseObjects/MyUseObjectInventory.cs`, lines 23–80. The native-size port meshes are placed in Blender; final accessibility and exported interaction are not yet tested in game.

## Native fuel prototype and remaining proof

The definitions clone vanilla reactor/refinery item patterns: one Arcane Ore refines to 0.01 Arcane Fuel I in four base production seconds, through the standard `Ingots` blueprint class. The reactor has a 30 MW maximum and native demand-following fuel generation. The fuel item currently uses vanilla placeholder art. Ore spawning, later fuel tiers and the final energy budget are not implemented. [Definition and recipe generator](tools/prepare_lab.py).

Do not infer operational success from a loaded model or parsed animation script. Fuel refinement, transfer, measured consumption, power under load, repeated startup/shutdown, actual ring movement, multiplayer/save-load behavior and the new glass collision remain validation work. The dated source log for current observations is `~/.config/SpaceEngineers/SpaceEngineers_20260913_210502803.log`; [README validation snapshot](README.md#validation-snapshot--2026-09-13) records the present boundary.

## Latest Blender housing and port layout

The base and roof have a 6.24 m radius inside the 12.5 m square footprint. Native port meshes remain unscaled. Side conveyor detector centers are Blender `(0, ±6.22, -2.5)`; upgrade detector centers are `(±6.22, 0, -2.5)`; top/bottom conveyor centers are `(0, 0, ±3.72)`. Blender Z maps to SE Y. The side ports therefore occupy the bottom cell row, with external controllers centered at local SE `(±7.5, -2.5, 0)` before block orientation is applied. The old lab controller coordinates at reactor mid-height are obsolete for this model. [Base upgrade integration](assets/integrate_base_upgrades.py), [housing widening and axial conveyors](assets/widen_housings.py).

The roof's common ceiling is Blender Z=3.750 m. Backing, plates, decals and rims end at 3.746, 3.748, 3.749 and 3.750 m respectively. This seats the complete rounded housing under blocks above it while retaining visible panel relief when uncovered. The widening pass cuts actual skin openings for the top/bottom hatches; a detector behind an uncut housing would not make the panel accessible. [Roof seating](assets/flush_roof.py).

`four_inventory_ports.py` is an intermediate authoring stage, superseded on its left/right faces by `integrate_base_upgrades.py`. Local Blender QA passed: main and ten collision bodies fit within ±6.25 m XY and ±3.75 m Z; the latest expanded set of 46 rays across six interfaces hits the native hatch/frame faces before surrounding housing, and all 24 deck plates face upward; four conveyor and two upgrade detectors match their expected positions. Expanded barrel skins needed actual recess cuts to clear the fixed port faces. The earlier MWM/Havok source export passed after the spherical-field fix; no MWM error was reported. SEUT still emitted its existing root-empty W005 warning. SBC parsing and the C# solution build passed, with zero C# warnings/errors. That earlier housing-stage model was not deployed or checked in game. [Local check script](assets/check_prototype.py), [recorded geometry evidence](validation/blender-prototype.json). These checks do not prove game interaction or physics.

The trunk-removal pass removes all four original radial trunk meshes. The native conveyor frames remain at their grid faces. Thin upgrade adapter plates used at that stage have since been replaced by curved surrounds. The earlier local 30-ray visibility and bounds checks passed after removal; the later 46-ray check also samples frame edges. See [remove_radial_trunks.py](assets/remove_radial_trunks.py). This revision is Blender/export only.

## SEUT preview material diagnosis

Some local SEUT preview TIFs were RGB while their installed-game DDS counterparts were RGBA. Losing the packed alpha channel made metalness (CM alpha) and gloss (NG alpha) behave as full strength, producing a chrome-like hull preview. [repair_seut_preview_textures.py](tools/repair_seut_preview_textures.py) restores RGBA from the installed DDS only when the preview lacks alpha and the source has it. Original TIFs are backed up under `~/.cache/arcane-power/seut-texture-backups`; no game textures are bundled by the tool. [Repair audit](validation/preview-texture-repair.json): 19 references examined, 18 restored, one with no lost alpha.

Keep the stock SEUT hull shaders and their packed channels. Neutral studio lighting and a light paint preview make the industrial surfaces easier to assess; [setup_preview.py](assets/setup_preview.py) also resets unintended transparent-material switches on native hull shaders. The own GLASS material retains its export constants; its additional clear Blender preview shader is a viewport aid, not an engine transmission test.

A separate SEUT callback issue can change the wrong material: updating a material property targets `context.active_object.active_material` rather than reliably using the property owner. The glass script now temporarily makes an object with the intended glass material active while changing SEUT properties. This prevents a hull material from accidentally receiving glass-preview settings. [Guarded material update](assets/curve_chamber_glass.py).

## Earlier spherical-field correction

The housing's XY-only widening also stretched the faceted field into an oval. That revision rebuilt it as a true 80-triangle icosphere with radius 1.30 m (2.60 m diameter), preserving its center and materials. Every vertex radius is asserted within 1e-5 m of 1.30 m; the closest inner-ring vertex has radial distance about 1.644 m. This vertex check is a local authoring sanity check, not full animated clearance proof. [round_containment_field.py](assets/round_containment_field.py) performs the rebuild, and [widen_housings.py](assets/widen_housings.py) now excludes the sphere from radial housing scaling. Local bounds and interface checks passed again after the correction; no new in-game test was performed. The later deployable chamber supersedes this radius-1.30 m mesh with individual tiles on a nominal radius-0.88 m field.

## Outward deck and ring surfaces

The inside-out deck appearance was a mesh-winding error: all 24 deck plates had negative signed volume and their top-face normals pointed down. The shared [annulus helper](assets/mockups/build_mockups.py#L94) generated inward-facing surfaces from its cross-section order. It now reverses each generated face once; both full-ring and partial-sector checks produced positive signed volume with upward top normals.

[repair_surface_orientation.py](assets/repair_surface_orientation.py) migrates already-built closed solids by reversing faces only when every edge is manifold and signed volume is negative. The observed repair changed 87 generated solids across the main reactor and both ring scenes. Deliberately two-sided glass and other open meshes are not processed; native/open meshes were not changed in this migration. Regenerated geometry uses the corrected helper. [check_prototype.py](assets/check_prototype.py) now explicitly requires upward-facing top surfaces on all 24 deck plates; the migration separately asserts positive signed volume after each reversal.

## Conveyor openings follow the native frame

A square housing opening left gaps around the native conveyor frame's chamfered corners. The `conveyor_cutter` helper in [widen_housings.py](assets/widen_housings.py) derives its outline from the projected convex hull of the installed SEUT `Conveyor Frame LG`: approximately ±1 m extents with 0.2 m corner chamfers. Scaling that outline by 1.01 supplies about 10 mm fitting clearance. The resulting cutter is applied to the roof, floor, front and back conveyor openings; it preserves the frame's corner profile instead of cutting away a square around it.

Fourteen existing housing skins were restored from the revision before the square cuts and recut with this native outline, retaining the other model refinements. The latest local check samples hatch and frame edges: **46/46 rays across six interfaces passed**, with 24 upward deck plates, all six detector positions, the overall 5×5×3 bounds and ten collision bodies passing as well. [Recorded Blender evidence](validation/blender-prototype.json). This revision was not deployed and no new game calls were made. These geometry checks remain separate from in-game interaction and collision behavior.

## Curved pillar supports and upgrade surrounds

[integrate_supports.py](assets/integrate_supports.py) replaces four square `Spine base foot` meshes with closed curved saddles that taper into the circular deck. Their generated normals are recalculated outward. Two flat `Base upgrade / adapter plate` boxes are replaced by curved tapered socket surrounds that follow the drum; the native upgrade meshes and their detectors remain unchanged.

The same pass repairs empty material slots introduced by Boolean cuts, assigns affected faces to the existing housing material and removes those empty slots. It projects UVs only where the new cut-wall mapping is degenerate, preserving existing valid mappings. These are authoring repairs to the surrounds and housing, not new game interaction behavior.

## Opaque supports hidden by preview blending

The new supports existed but appeared invisible through the chamber glass because the native `PaintedMetal_Colorable` material's Blender `surface_render_method` had accidentally become `BLENDED`, while its exported SEUT technique remained `MESH`. Object-level alpha sorting could hide opaque supports behind glass. [setup_preview.py](assets/setup_preview.py) now explicitly restores native nontransparent previews to `DITHERED` and sets the SEUT node group's `TM Switch` to zero. The separate glass material keeps its transparent preview and exported GLASS constants.

At this earlier support revision, the preview-only fix made the Blender screenshot show the far-side pillars and supports through the glass; no geometry change was needed for that visibility correction. The saved blend passes 24 upward deck normals, 46 hatch/frame rays, **16 chamfer-corner backing samples**, detector positions, bounds and ten collision bodies. [Blender evidence](validation/blender-prototype.json). That revision’s C# solution build passed with zero warnings/errors; its main MWM export finished successfully, and both ring exports completed after the winding repairs. Only the existing SEUT root-empty W005 warning remains; the earlier collapsed-UV warnings are gone. No game calls or deployment were performed.

## Deployable chamber: solid island and annular leaves

The user's corrected floor design keeps a **solid central island** of radius 0.975 m. Four annular leaves cover the surrounding ring bay, spanning radius 0.995–1.815 m. They drop 0.32 m and slide outward 1 m before ring emergence; the island never retracts. [build_deployable_chamber.py](assets/build_deployable_chamber.py) authors actual SEUT subparts and [deployment.json](assets/deployment.json), with no Blender timeline animation.

There are 89 instances under one reactor model: four nested rings, four floor leaves, 80 thick outline tiles and one plasma. Ring radii are 1.09/1.29/1.49/1.69 m. The nominal field radius is 0.88 m, tile thickness 0.045 m, with two shape classes preserving the actual subdivided-icosphere triangles: 60 instances share one MWM and 20 share the other. Congruent faces reuse a model without distorting their geometry. Four dispensers under the pillar tops aim inward/down at 45 degrees and supply twenty batches of four tiles. The [offline geometry contract](validation/deployment.json) reports minimum inter-ring radial-shell gap about 0.1099 m and floor clearance about 0.0644 m; these are analytical checks, not proof of the complete animation or Havok interaction. Two Blender crash recoveries preserved all 89 instances and the solid-island/annular-floor arrangement without data loss.

The intended running motion uses rings rotating around different axes rather than merely spinning each hoop around its own normal. The user's [armillary-sphere discussion reference](https://www.reddit.com/r/AskScienceFiction/comments/pvd7g6/general_science_fiction_three_connected_rings_on/) supplies visual terminology/inspiration; it is not an SE API or physics specification.

## Historical Animation Engine ownership and test profiles

[build_animation.py](tools/build_animation.py) generates the historical `Data/Animation/main.bsl` (removed during migration) from the geometry manifest. It converts parent-space Blender positions and movement axes to the exported main-model frame `(-X,Z,Y)` and compensates for installed AE translation/rotation signs. Subpart mesh coordinates use a different conversion, documented below. Working-state startup opens the annular bay, lifts rings, assembles twenty four-tile batches, reveals plasma and starts armillary ring motion. `Park()` cancels loops/delays, resets all subparts and hides tiles/plasma. The current reset is immediate; it is not the final controlled cooldown or recovery animation.

**Animation Engine owns every animated matrix and tile/plasma visibility.** C# owns optional Ring3/Ring4 visibility and emissives, without writing those matrices. The installed AE V2 libraries do not directly query fuel identity or upgrade capacity. Therefore [Reactor.cs](src/Data/Scripts/ArcanePower/Reactor.cs) uses two separate native upgrade values: `ArcaneControllerCount` enforces two functional attached controllers, while `ArcaneContainment` determines capacity, clamped to two through four rings. A capacity change while enabled forces the reactor off for a fresh deployment.

Current hardware profiles are two standard controllers → two cyan rings; one standard plus one advanced → three amber rings; two advanced → four violet rings. **Every profile still consumes Arcane Fuel I with native 30 MW maximum output.** These are animation test profiles, not implemented fuel tiers II/III. Higher-tier processing, fuel-based profile selection, tile consumption and startup/containment energy are absent. Native electrical generation is not gated by visual plasma ignition; the script's visibility timing is presentation, not an authoritative reactor phase.

The prior in-game `Loaded 1 scripts` result belongs to the old simpler BSL. The new generated script has now passed the installed parser and VM offline as described below; in-game movement still needs validation. All parts and the final fixed-deck/lip-corrected main MWM exported successfully, retaining the known root-empty W005 warning. Local revision `lab_2a1f0369bfd4` was deployed and byte-verified against the full MWM family, BSL, runtime and glass; [local-deployment.json](validation/local-deployment.json) records it. No reload/game control has been performed for this startup revision. Build the renamed root solution with `dotnet build arcane-systems.sln`.

## Historical installed AE parser and VM validation

[check_animation.py](tools/check_animation.py) compiles the actual installed AE V2 source offline using local game references, without copying that dependency into the mod. It uses the real lexer, compiler, ScriptV2Runner and ScriptAPI scheduling, with recording stand-ins for subpart libraries. [animation-vm.json](validation/animation-vm.json) records success and the current BSL SHA-256.

The script compiled to 3,607 instructions with 89 subpart declarations. The recorded calls show twenty quartets at ticks `320 + 36 × batch`, plasma visibility at tick 1160, two four-ring spin periods, sixteen floor translations and eighty tile rotations. Interruptions at ticks 10, 50, 130, 260, 350, 700, 1080 and 1200 cancel all later recorded calls; fresh startup produces all eighty tile reveals again. These are parser/VM dispatch, timing and cancellation checks. They do not execute game subpart matrix math, verify actual orientation/rendering/physics, simulate the working-state event source or prove multiplayer behavior. Visual plasma reveal remains separate from native electrical generation.

## Maintenance decals align to individual armor panels

The first twenty-decal wrap was rejected: old decal centers lay on armor seams at multiples of 15 degrees, while intact panel centers lie at `7.5 + 15n` degrees. Subdividing and projecting across a seam did not solve the alignment problem. Its earlier 0.065263 m reseating distance is historical evidence from that rejected pass.

[wrap_maintenance_panels.py](assets/wrap_maintenance_panels.py) now restores each decal's original quad and native atlas UVs from the pre-deployment checkpoint, rotates it 7.5 degrees, and removes four port-adjacent decals. Each of the **sixteen remaining decals** is subdivided into a 12×12 grid and projected onto one intact `Drum segmented armor` panel, with no lower-drum fallback. A 1.5 mm normal offset avoids surface overlap. [maintenance-panels.json](validation/maintenance-panels.json) records each decal's target armor panel. The reviewed Blender view shows centered, seated frames; the corrected layout and subsequent fixed-deck/lip correction have exported successfully.

## Exported main and subpart coordinate frames

Offline binary inspection established different coordinate frames for this exported model family: main-model positions and AE movement axes use Blender `(-X,Z,Y)`, whereas subpart mesh vertices use `(X,Z,-Y)`. An identity Blender subpart placement therefore imports with a rotation approximately `diag(-1,1,-1)`, not an identity matrix. Treating both files as though they shared the subpart frame caused the first BSL conversion to have incorrect signs; [build_animation.py](tools/build_animation.py) now uses the main-model frame for parent-space movement and rotation axes.

[check_animation.py](tools/check_animation.py) opens the actual MWM using the installed game's `MyModelImporter` with a `BinaryReader`, without controlling the game. It verifies all 89 model references exist and compares every exported dummy position and orientation against the geometry manifest. Expected rotations use `mainAxes × BlenderRest × inverse(partAxes)`, transposed for the imported row-vector matrices. [animation-vm.json](validation/animation-vm.json) reports maximum position error about 7.17×10⁻⁷ m and maximum rotation-element error about 3.89×10⁻⁷, both within the check tolerance. These rest-transform checks supplement the VM's recorded dispatch checks; they do not prove actual animated matrices, rendering, collisions or multiplayer behavior.

## Deck handles and deployment-lip seam

[seat_tiedown_handles.py](assets/seat_tiedown_handles.py) centers sixteen native tiedown decals on accessible deck plates, preserving atlas UVs and projecting them 1.5 mm above the plate surface. Eight decals obscured by pillar saddles are removed rather than placed on the supports. [tiedown-handles.json](validation/tiedown-handles.json) records the surviving plate associations and removals.

The fixed deck initially extended to radius 3.72 m and overlapped the deployment lip. [build_deployable_chamber.py](assets/build_deployable_chamber.py) now ends it at 3.539 m, leaving a minimum 4.282 mm seam inside the existing 64-facet lip. Both top surfaces remain at Blender Z=-1.25 m. The final main re-export completed successfully; the installed AE parser/VM and all 89 exported rest transforms/references passed again against the fresh MWM. `dotnet build arcane-systems.sln --no-restore` passed with zero warnings/errors. Local deployment completed, but no new game collision or animated behavior is proven.

## Glass visibility and first-load emissive corrections

The user reported invisible glass in game. The installed `Data/Content/Shaders/Geometry/Materials/Glass/Pixel.hlsl` multiplies material Color by the texture; the native dirt DDS has mean alpha about 0.016095 and maximum 124/255, so the original 0.06 material alpha suppressed its already faint dirt. [tune_chamber_glass.py](assets/tune_chamber_glass.py) changes Color.W to 0.28, reflectivity to 0.10, Fresnel to 0.45, reflection shadow to 0.20 and specular factor to 3.0. Native dirt/chrome references and material identity remain unchanged, so no geometry/MWM export was needed. Two local preview TIF alpha channels were restored from native DDS; dirt and grazing-angle alpha drive an approximate Blender preview. This prepared correction has not yet been confirmed in game.

The user also reported emissives missing on first load until toggling the reactor. The previous dirty-state guard cached the appearance before render objects were ready; decompiled `MyEntity.cs:2366–2393` skips emissive updates when the render ID is `uint.MaxValue`. [Reactor.cs](src/Data/Scripts/ArcanePower/Reactor.cs) now retries every 60 simulation ticks even when Ring1 and state are unchanged; profile/off changes still apply immediately. [check_appearance.py](tools/check_appearance.py) compiles the actual method with recording stand-ins and passes delayed render readiness, later Ring4 replacement, immediate profile/off changes and dedicated-server skip. This proves retry dispatch, not live rendering.

The solution build passed. Nineteen local files were redeployed; runtime, BSL and glass were byte-verified in [local-deployment.json](validation/local-deployment.json). The model family remains `lab_2a1f0369bfd4` because its binaries did not change. No game operation or live confirmation followed these fixes.

## User workflow: Blender review, no unsolicited regression suites

The user explicitly requested stopping regression checks. Iterate models in Blender and run regression suites only when the user asks. Do not resume previously routine regression runs automatically during geometry, material or animation-authoring changes. Keep previously recorded test results as historical evidence, not permission for new runs.

## Upper vent bell and telescoping blast-shield geometry

[build_vent_bell.py](assets/build_vent_bell.py) authors six separate SEUT scenes and `BlastShield1..6` dummies; the main model now has 95 subparts, while the existing AE startup still addresses 89. [vent.json](assets/vent.json) records sleeve inner radii from 2.499 to 1.924 m in 0.115 m steps, 0.055 m walls and 0.82 m height. Stowed bottoms are `2.48 + 0.025 × i` m for zero-based i, with maximum top 3.425 m. The ceiling pocket spans radius 1.91–2.65 m and Blender Z=2.30–3.50 m.

Stage strokes are `0.640833… × (i + 1)` m, ending at 3.845 m. The smallest sleeve body ends at Z=-1.24 m and its seal at -1.25 m, meeting the deck; its inner radius sits 4 mm outside the fuel trace's 1.92 m outer radius. The recessed bell has 24 panels/vane grilles, an annular intake at radius 1.22–1.85 m and a central service cap. Native `Emissive` geometry appears on ceiling outer strips, the intake rim and sixteen seam segments per sleeve, connecting to the existing hardware-profile colour path. This does not implement fuel-based profile selection.

The stowed and deployed shapes received static Blender visual inspection only, with no keyframes or regression suites; the saved scene is stowed. All six shield exports and the main export finished, retaining the known SEUT root-empty W005 warning. Twenty-five files were deployed as `lab_10ddab59736f`, recorded in [local-deployment.json](validation/local-deployment.json) as deployment rather than a validation pass. No regression checks or game control followed. Vent-trigger AE integration, pressure handling and an exhaust route remain future work. The earlier parser/VM and 89-rest-transform results do not validate these six new parts or their movement.

## Native inventory-hatch highlighting

The user reported a conveyor detector-box highlight. [highlight_inventory_hatches.py](assets/highlight_inventory_hatches.py) assigns all four conveyor detectors through SEUT `highlight_objects` and the custom `highlight` property to their corresponding native Conveyor Access meshes only, leaving frames unselected. Decompiled `MyCharacterDetectorComponent.cs:473–489` uses custom highlights when present and otherwise falls back to DummyHighlight; `MyHudSelectedObject.cs:187–243` resolves mesh sections. The user subsequently reported highlighting was still wrong in game. Inspection found the compiled MWM had zero mesh sections even though detector highlight metadata was correct.

`MwmBuilder.MyModelProcessor.GenerateMeshSections` only accepts names matching `^(?<prefix>.+)_section_?(?<suffix>.*)$`. SEUT AddHighlightEmpty normally adds `_section_`; the manual helper had omitted that naming step. The helper now idempotently suffixes each of the four access-hatch object names with `_section` and links its detector to the renamed mesh. The saved Blender scene includes this correction and main-only export finished. Direct compiled-MWM inspection now finds four matching hatch sections (side 0, side 2, top and bottom), with detector highlight names matching each section. Every section has 1,146 indices: PaintedMetal_Yellow 432, Conveyor 6 and Metal_Dull 708. Twenty-nine files were deployed as `lab_3ed994c27b1f`. No regression checks or game reload followed; actual in-game highlighting remains unverified.

## Direct C# migration, shutdown and shield/intake control

The user authorized moving every existing animation into the mod and adding normal shutdown. The inspected AE bridge did not expose arbitrary reactor state and its `TerminalComp` was a stub; direct ownership avoids splitting custom state between two animation systems. [Reactor.Motion.cs](src/Data/Scripts/ArcanePower/Reactor.Motion.cs) now owns all 127 animated parts and their visibility. [AnimationGeometry.cs](src/Data/Scripts/ArcanePower/AnimationGeometry.cs) is generated from the deployment/vent manifests by [build_animation_geometry.py](tools/build_animation_geometry.py). The old `build_animation.py` entry point delegates to that generator; no BSL is shipped. Earlier AE checks and their axis findings remain historical evidence, not validation of this replacement.

Core phases are Off, Starting, Running and Stopping. The base startup spans 1,170 authored ticks; profile-specific sphere acceleration below shortens the elapsed startup. Normal shutdown brakes running rings for 90 ticks with plasma fading over the first 60, then reverses deployment at its original 1× pace. Partial startup reverses from its current age. The same direct runtime places rings, floor leaves, tiles, plasma, six shield sleeves and 32 intake vanes. The 60-tick appearance refresh remains, but now follows motion/profile state, including shutdown.

Vent opening closes the shield over 240 ticks and then opens the intake over 90. Stop closes the intake over 90 ticks, waits for Core Off, and retracts the shield over 240. Native generation is disabled through venting/shutdown and restart remains interlocked. This is only the requested internal mechanism: ducts, exterior outlet, pressure simulation and heat removal are absent; actual discharge is reported as zero.

[build_intake_vanes.py](assets/build_intake_vanes.py) authors 32 radial vane instances sharing one MWM. Their hinge radius is 1.5125 m at Blender Z=2.49 m; they rotate 80 degrees about local X, below a plenum floor at Z=2.70 m. Main and vane exports finished. No new Blender timeline or regression suites were run.

[VentSession.cs](src/Data/Scripts/ArcanePower/VentSession.cs) adds a terminal switch and StartVent/StopVent/ToggleVent actions prefixed `ArcanePower_`. Secure commands are validated against player access on the authoritative server; snapshots are sent every 30 ticks. State persists in ModStorage under GUID `d85a5399-b527-45ac-bcc0-aa1c442b2710`. These are implemented paths, with live synchronization, save/load and rendering still unconfirmed.

Deployment removes the old `Data/Animation/main.bsl`, and newly created worlds omit Animation Engine. Existing running-world mod lists are preserved. The final direct-runtime build passed with zero warnings/errors, and 29 files were deployed as `lab_e0c6d84fb8f0`; no regression checks or game control were run for the migration. The previous 89-part AE/offline results do not establish correctness of the direct 127-part runtime.

## Status emissives and native-load-driven motion

[Reactor.cs](src/Data/Scripts/ArcanePower/Reactor.cs) now prioritizes an Incomplete status for `BuildLevelRatio < 1`, a nonfunctional reactor or fewer than two functional controllers. This status pulses red to black with a 120-tick cosine period. Complete/off is steady red; enabled without Fuel I is yellow; active status keeps the selected hardware-profile colour. Yellow is latched through automatic shutdown until fuel returns. The Ring1-required early return was removed, allowing parent emissives to update before child render readiness; the 60-tick retry remains.

[Reactor.Motion.cs](src/Data/Scripts/ArcanePower/Reactor.Motion.cs) derives target load on the server from native CurrentOutput/MaxOutput and applies `Load += (TargetLoad - Load) / 60` per tick. Ring speed uses `3 × (1 + 2 × Load)` relative to the original speed: 3× at zero load and 9× at full load. Spin phase is integrated rather than recomputed from age, then saved and synchronized; shutdown brakes from the captured SpinRate. Legacy saved states derive phase from their former CoreTick/StopSpinAge.

A shared smooth multi-frequency translation moves every assembled field tile and the plasma together, including a gentle vertical bob. Amplitude increases with load and the bounded combined offset stays below 6 cm. The envelope ramps at startup's end and settles over shutdown. No geometry or MWM changed. This is authored runtime presentation, not heat, plasma physics or a claim of observed in-game motion. The final build passed with zero warnings/errors and 29 files were redeployed, retaining model revision `lab_3ed994c27b1f`. No game operations or regression checks were run.

## Profile-specific sphere assembly speed

Only Starting-phase authored ages `320 <= age < 1038` advance at `Motion.Profile × 0.5`: two rings use 1×, three use 1.5× and four use 2×. The boundary is clamped at 1038. This accelerates quartet spacing and tile flight together; all other startup ages advance at 1× and later phases begin earlier once assembly completes. The 718 authored assembly ticks take 718/479/359 elapsed ticks, making complete startup 1,170/931/811 ticks (about 19.5/15.52/13.52 seconds at 60 ticks/s).

`CoreSubtick` (Proto field 18, range 0 to below 1) preserves smooth fractional age through saved/synchronized state. Normal shutdown still reverses at 1× and preserves that fraction until parked. The final solution build passed with zero warnings/errors and 29 files were redeployed under unchanged model revision `lab_3ed994c27b1f`. No regression checks or game operations were run.

## Finite ejection, heat and attached-module damage

The user replaced the held-open shield/intake prototype with a finite ejection cycle in [Reactor.Motion.cs](src/Data/Scripts/ArcanePower/Reactor.Motion.cs): 240 ticks shield closing, 90 intake/hatch opening, 120 ejection, 90 intake closing and 240 shield opening. Power continues during shield closing and is disabled only after full closure. The core and deployed rings leave through the top visually; the reactor stays Off after completion until manually restarted with a fresh field. Active ejection cannot be reversed by another terminal/toolbar click. VentSession now provides a Vent reactor button plus StartVent/ToggleVent actions; the earlier StopVent/switch interface is historical.

Heat is normalized to 0–1, following actual load with a 3,600-tick heating response and 1,800-tick cooling response, then purged over the 120-tick ejection. Load/heat peaks are retained during shield closure for the vent consequence. Damage occurs once after completion and only if a payload was present: reactor fraction `0.01 + 0.04 × load + 0.10 × heat`; module fraction `0.02 + 0.06 × load + 0.12 × heat`. These fractions multiply maximum integrity, reaching 15%/20% at maximum normalized load/heat. The server snapshots compatible `ArcanePower_` entries from native `CurrentAttachedUpgradeModules` and calls synchronized `DoDamage`; nearby blocks are not searched.

[build_ejection_hatch.py](assets/build_ejection_hatch.py) replaces the visible top conveyor with four hatch leaves sharing one MWM, while retaining the centered conveyor dummy. The visual bore is 3.72 m; leaves drop 0.3 m and slide diagonally 1.95 m, while intake vanes translate radially 0.6 m. Total subparts are now 131. Static roof collision is unchanged: the opening and ejected payload are render-only, not physical debris or collision damage. The entire field now shares an irregular rigid rotation. [Reactor.cs](src/Data/Scripts/ArcanePower/Reactor.cs) uses four-times emissive intensity and a bright red vent pulse.

## Actual alternative fuels and native capacity

[Reactor.Fuel.cs](src/Data/Scripts/ArcanePower/Reactor.Fuel.cs) implements Fuel I/II/III at 10,000/100,000/1,000,000 MW. Selection chooses the highest present compatible tier only when Core Off, Vent Idle and CurrentOutput is zero; the selected tier remains locked through operation and shutdown. Two functional controllers are still required, separately from capacity. Selected fuel now drives ring count, colour and assembly speed; old hardware-only Fuel-I/30-MW tables are historical.

Native multiple FuelInfos entries are concurrent requirements rather than alternatives, so the mod definition keeps FuelInfos empty and adds all three allowed ingots to its own inventory constraint. A content-change callback restores native capacity from selected fuel energy: `units × tierMW / 60`, corresponding to sixty seconds of rated output per unit. Explicit server consumption accrues fractional fuel debt from actual native output, initially one selected unit/minute at full tier load. These are starting balance values, not validated survival balance.

The private conveyor pull API is unavailable to this mod. Public `GetTerminalSystemForGrid` inventory enumeration instead checks player access and `CanTransferItemTo` before `TransferItemFrom`. It respects UseConveyorSystem, excludes other reactors and periodically tops compatible fuels up toward ten units each. This is implemented replenishment, not proof of an observed in-game transfer. [Blueprints.sbc](src/Data/Blueprints.sbc) converts one lower fuel to 0.1 higher fuel at base 12/24-second recipe times, a 10:1 material ratio.

Main and shared hatch exports finished; Arcane Power compiled with zero warnings/errors. The subsequent completed deployment is recorded at the end of these learnings. No regression checks or game calls were run. Earlier zero-discharge, no-heat and single-fuel limitations describe previous stages and do not describe this implementation. Live output, inventory transfer, damage, save/load and rendered ejection remain unconfirmed.

## Dual-axis rings, output ramp and cooldown hold

[Reactor.Motion.cs](src/Data/Scripts/ArcanePower/Reactor.Motion.cs) adds saved/synchronized SecondaryPhase and SecondaryRate. Each hoop's second axis is perpendicular to its first; signed rates are -0.07/+0.09/-0.11/+0.13 times the shared secondary phase, which advances with smooth modulation. Shutdown integrates braking for both axes, rather than snapping either to its rest angle. The existing load-dependent primary speed remains.

Available output rises from zero to the selected rating over 600 ticks after Core reaches Running. [Reactor.Fuel.cs](src/Data/Scripts/ArcanePower/Reactor.Fuel.cs) preserves rated MaxOutput and limits native capacity to the smaller of selected-fuel energy and `rating × PowerRamp / 216000`; capacity is zero outside an enabled Running state (except ongoing shield closure can still generate). Thus startup now has no electrical output, superseding the earlier ungated prototype.

A new CorePhase.Cooling holds the assembled shell and slows rings after a hot running reactor is shut off. Only at Heat<=0.15 does the existing 90-tick brake and reverse dismantling begin. Passive cooling's 30-second response gives approximately 57 seconds to fall from normalized heat 1 to 0.15. Damage can pause mechanisms, but passive cooling continues. Partial startup still reverses directly rather than waiting for a completed running shell.

## Inner ceiling door and connected passage

[build_ceiling_hatch.py](assets/build_ceiling_hatch.py) adds CeilingHatch1..4, initially bringing the total to 135 subparts before the vane removal below. They share the VentHatch mesh with underside trims/emissives. Rest Z is 2.365 m; each lifts 0.32 m and then uses a quadrant slide of (1.4,1.4) m, rotated 45 degrees relative to the outer roof doors. This gives 1.98 m cardinal travel between dispensers. A radius-1.86 m central bore and lined retraction pockets connect the two doors. Static roof collision remains unchanged.

The final runtime build passed with zero warnings/errors; latest main/shared hatch exports finished. No regression checks or game calls were run. Earlier single-axis, immediate-dismantling and ungated-output descriptions are historical stages, not the current implementation.

The final passage refinement removes all 32 former VentVane dummies and their runtime loop, because they conflicted with the lined tube. `intake.count=0` marks that geometry as historical; the Intake state still times door opening/closing. Active part count is **103**: four rings + four floor leaves + 80 tiles + plasma + six sleeves + eight hatch leaves. The inner doors replace the vane mechanism, shared leaves retain underside emissives, and central tube overlaps were removed. Compilation passed after the runtime removal. Final main/shared VentHatch exports finished with only the existing unparented-root W005 warning; addon bounding-box messages did not indicate export failure. Thirty-one files were deployed as `lab_c05a1c7be62e`. The open bore was inspected statically in Blender, then the closed pose restored and saved. No timeline preview, game calls or regression checks were run.

### Glass haze independent of the dirt texture

The user still found the chamber glass largely invisible in game. The installed `Content/Shaders/Geometry/Materials/Glass/Pixel.hlsl` adds `ColorAdd` after multiplying `Color` by the texture. [tune_chamber_glass.py](assets/tune_chamber_glass.py) now sets `ColorAdd` RGBA to `(0.008, 0.009, 0.010, 0.025)`, providing a faint cool-grey haze even at clear texture texels. Native dirt strength, reflection and Fresnel settings remain as above. The approximate Blender preview already included a 0.025 baseline alpha; the runtime material now includes that baseline too. This parameter is not a guarantee of exact visible transmission through multiple panes. Saved Blender material and local `TransparentMaterials.sbc` were updated; no geometry/MWM export, regression checks or game reload was performed. Appearance awaits the user's next game review.

## 14 September 2026 — spectator recordings and repair

[Startup/shutdown](validation/recordings/reactor-startup-shutdown.mp4) and [venting](validation/recordings/reactor-vent.mp4) were captured with GPU Screen Recorder on primary DP-4, 3440×1440 at 60 fps, using SE Remote spectator input and the seated cockpit toolbar (`D1`/`D2`). [Metadata](validation/recordings/recordings.json) records durations and scope. Low-load assembled-field motion and upward red ejection were visible on revision `lab_c05a1c7be62e`. Existing ceiling armor obscures the roof hatch; these recordings do not establish unobstructed passage, rated output or hot cooldown.

The current SE Remote interface has input, save/reload and typed grid operations, but no arbitrary C# execution or general repair call. After saving, the sector/checkpoint/cache were backed up in `validation/recordings/before-repair`. Only the reactor and two controllers had their saved IntegrityPercent/BuildPercent restored to 1. Removing this world's backed-up binary sector cache forced XML loading; the game's expected outdated-world conversion prompt was accepted. Reloading and resaving confirmed all three full values in [repair.json](validation/recordings/repair.json). No other blocks were repaired or changed by that patch.

## 14 September 2026 — external hardware and tile implementation

[build_external_hardware.py](assets/build_external_hardware.py) creates vent duct/outlet scenes with SE Size=(3,1,3), central bore radius 1.86 m, and ±1.25 m axial bounds. The native grid reference is one-cell depth with a 3×3 cross-section. Frame sectors use sampled inner arcs rather than an eight-vertex approximation that intruded into the round opening. Export initially exceeded SEUT's ten-collision-body limit (E022); the exporter tried a UI popup in a background process and crashed that process. Reducing each vent to eight convex collision wedges resolved the export error. A process-local print reporter also avoids background popup calls; the installed addon and foreground Blender were not modified. All five final exports finished, with existing unparented-root W005 warnings.

The outlet reuses the reactor VentHatch mesh as OutletHatch1..4. Leaves sit at Z=1.08 m, drop 0.30 m and slide 1.40 m per axis into the casing pockets. [Reactor.VentRoute.cs](src/Data/Scripts/ArcanePower/Reactor.VentRoute.cs) scans centered cells from `reactor.Position + Up*2`, accepts only functional same-Up duct/outlet blocks and follows up to 16 sections. The endpoint entity ID and ejection travel are synchronized; the endpoint uses the reactor Intake clock. A started chain without an outlet rejects the request. No custom chain retains direct roof ejection; ordinary obstruction checks, mid-cycle route damage, physical debris and moving-shutter collision remain absent.

Standard/advanced controllers each occupy one cell with crescent housing, concave local Blender -Y mating side and one `detector_upgrade` dummy at (0,-1.15,0). Installed lab controller Forward directions both point toward the reactor; Blender -Y maps to SE forward. Native `MyUpgradeModule.InitDummies` scans the detector prefix and computes adjacent cell matching via `GetLinePositions`. Retaining the one mating face removes the previous four-direction controller sockets. This preserves the intended native coordinate relationship; the new models still need game placement confirmation.

The component copies the actual thick Tile1 shell mesh, approximately 0.535×0.390×0.045 m. [render_hardware_icons.py](assets/render_hardware_icons.py) renders five transparent icons directly from the models, converted to DXT5 DDS. Definitions add the two conveyor blocks, distinct controller models/icons, component and assembler recipe. The review lineup is saved in scene `Arcane Power external hardware review`; no startup timeline was built.

[Reactor.Tiles.cs](src/Data/Scripts/ArcanePower/Reactor.Tiles.cs) reserves 80 tiles before survival startup, persists installed stock/wear, retains them through shutdown and removes them during ejection. Maintenance consumes four-item batches, using tier, load and normalized heat; shortage disables the reactor and uses normal cooldown/shutdown. Conveyor pulling uses native reachability and public transfer methods, targeting 160 loose tiles. MotionState fields 29–33 add installed count, wear, starvation, outlet ID and ejection travel. A saved state's EntityId must match before installed reserves or a vent cycle can be restored to a reactor; broader projection/lifecycle behavior remains unverified. Maintenance replacement animation is not yet implemented.

Final solution compilation passed with zero warnings/errors. Forty-five files were locally deployed as `lab_5d37d651a7ca`; no regression suites ran and this new pass was not loaded into the game. Recorded operation and repair apply to the previous model/runtime revision. See the [remaining-work overview](../docs/arcane-power-remaining-work.md) for current limits and next phases. Earlier notes above describe historical implementation stages.

## Mounted fit revision — shallow faceted controllers

The standalone crescent lineup did not prove fit against the reactor. `fit_hardware_assembly.py` now instances the source model collections beside the actual reactor at Blender (±7.5,0,-2.5), with ±90-degree mating rotations, and places a duct/outlet at Z=5/7.5. These preview instances live outside export collections.

After the user rejected both excessive projection and the cylindrical exterior, `build_external_hardware.py` changed the controllers to flat armored faces, chamfered shoulders and tapered wings. Maximum projection is approximately0.8m, versus the initial roughly2.4m. The inner skirt is sampled against actual reactor meshes at12mm clearance; native occupancy remains1cell and detector remains(0,-1.15,0). Collision is clipped to the occupied cell, while only the thin visual mating skirt extends into unoccupied space inside the reactor's rectangular bounds. Earlier claims that all controller artwork stays inside one cell no longer apply.

The layered crescent mesh initially emerged with inward normals after the socket boolean; signed-volume orientation is corrected after that operation. The visible body is now closed and opaque. Vent service insets previously ended exactly on the casing surface, and paired corner rails crossed each other. Insets/latches/rails now sit in cut pockets and there is only one rail per corner. The original reactor housing bore also coincided with its new liner: backing clearance now separates those faces without changing the1.86m visible bore. Removable roof panels have individual backing seats. Opposite-facing glass meshes are intentional and were retained.

Saved and inspected in Blender, including close-up mounted controller fit. No regression suites, game calls, MWM export or deployment were performed for this art revision; the previous deployment/recordings remain historical evidence.

## Compact piggyback power-pack revision

The user rejected the large faceted/cylindrical module silhouettes. Both controller sources now use a compact0.98m-wide ×1.10m-high power-pack case around the native0.68m upgrade socket, with a curved sampled back, socket cavity, two cell covers, retaining clips, fasteners and one/two fuel status bars. Projection is approximately0.35–0.4m. Native grid centres and detectors remain unchanged; both source collections stay mounted against the reactor for review. The dark front insert is a material face of the shell, avoiding coplanar overlay panels. Saved/inspected in Blender; export and deployment remain pending.

The next proportion pass widened both packs to1.20m and reduced height to1.00m, preserving the curved back and native socket cavity. A mounted Blender screenshot is saved as `validation/piggyback-packs-mounted.png`.

## Near-flush manifold sockets

The next mounted revision moves each pack's face/details12cm toward the drum while retaining its1.20×1.00m outline, native detector and socket cavity. `fit_hardware_assembly.py` replaces both old curved adapter mounds with open receiver surrounds blended into the actual base surface. The receiver lip is at±6.43m, versus the pack face at±6.455m:25mm behind the face, with clearance around the case bevel. The original native0.68m upgrade port remains inside the empty receiver. Pack back sampling excludes the receiver geometry to avoid feeding its raised lip back into the next rebuild. Preview instances remain mounted; saved Blender art only, with MWM export/deployment still pending.

## Raised sockets aligned with side armor

Both packs, native ports and receiver surrounds now centre at Blender Z=-2.33m,17cm above their earlier position. This matches the midpoint of the white armor panels'[-3.07,-1.59]m vertical span. Receiver backing height is1.30m, leaving9cm above and below; pack height remains1m. Port mesh/detector positions moved together. Module art, collision and mating detector move+0.17m locally, while native block anchors remain(±7.5,0,-2.5). The former lower aperture is closed with curved armor infill trimmed against existing panels, avoiding overlapping surface layers. Saved/inspected in Blender; game export/deployment still pending.

## Width comparison pending selection

The1.3× width request was interpreted provisionally as1.6m for the pack and2.3m for the outer socket, rounded up to tenth-metre overall widths. Before/after inspection found no changed empty transforms in the reactor or either controller scene; the native socket cavity also retains its width. The user then requested a rough comparison before selecting1.6m or2.0m. `preview_pack_widths.py` creates a non-exported front-view comparison, with1.0m height in both cases and2.3m/3.0m socket surrounds. It copies only meshes; source empties are neither copied nor scaled. The2.0m option is a shape study, not a final mounted-fit/export change. Screenshot: `validation/pack-width-comparison.png`.

The user selected the1.6m pack /2.3m socket option. Both actual controller source meshes measure1.6×1.0m and are mounted in the reactor scene. Empty transforms remain identical to the pre-width-edit snapshot. Selection evidence: `validation/selected-pack-width.json`. The2.0m scene remains a non-exported comparison only; game export is still pending.


## Selected pack/socket asset delivery — 15 September 2026

Exported the saved 1.6m pack /2.3m socket Blender revision through SEUT: main reactor, both controller variants, vent duct and outlet. Existing subparts remain shared. Refreshed five PNG/DDS icons; icon framing now follows mesh bounds and views controller fronts from local +Y. Local deployment `lab_06d121e6bcac` includes the updated MWM family and icons; copied hashes/bytes match source. No geometry rebuild, empty scaling, game control, regression suites or C# build in this pass. Export retained existing W005 root warnings and background bbox diagnostics; all five exports produced fresh MWM files. In-game fit, glass, highlights and collision review remain pending. Evidence: `validation/current-model-export.json`, `validation/current-model-export.log`, `validation/current-icons.log`, `validation/local-deployment.json`.


## Grid power, inventory filter and maintenance — 15 September 2026

Accepted: startup needs external grid power; a small internal reserve funds controlled shutdown on supply loss. New controller GameLogic installs native sinks during block Init. Decompiled `MyResourceDistributorComponent.AddSinkLazy` puts same-container sinks/sources in InputOutputList, so sinks belong on controller blocks, not the generating reactor. Native block registration/split/merge hooks discover their sink components. Custom adaptable priority-2 group receives supply after safe zones and before defense. Initial upkeep1/10/100MW; reserve90seconds=0.025/0.25/2.5MWh; up-to3×upkeep charging plus upkeep gives4/40/400MW request and30second full precharge. Only native CurrentInput charges saved reserve; source output/fuel accounting covers self-supplied running upkeep. No cold-start/discharge export from reserve. Power loss triggers manual-restart shutdown, depleted reserve pauses mechanisms while passive cooling continues. Destructive breach remains undefined/unimplemented. Actual distribution and lifecycle behavior still need game validation.

Inventory root cause: `MyReactorDefinition.Init` constructs readonly constraint Description from FuelInfos. Adding accepted IDs afterward does not replace that string; `MyGuiControlInventoryOwner.RefreshInventoryContents` uses Description as the empty-slot tooltip. Replace both the reactor-instance inventory Constraint and reactor-specific definition constraint with the same explicit Fuel I/II/III+ContainmentTile whitelist and description on every peer. Native alternative-fuel behavior remains unsuitable; do not reintroduce concurrent FuelInfos just to populate UI.

Maintenance now consumes a quartet once, immediately publishes its animation state, shrinks the retired group, then launches replacements from stationary pillar rest poses into the moving final shell pose. Iterate all20quartets with1×/1.5×/2×tier timing over90authoredticks. Normal shutdown holds Cooling until an active replacement completes. Save/sync include reserve, power availability and maintenance batch/time; existing entity-ID guard prevents copied reserve. Fixed tile replenishment during post-ejection vent closure by restricting installed-shell provisioning to Vent Idle. Terminal shows actual requests/input, reserve seconds, net contribution, stock, shortages and conditional endurance estimates. Flight/ring clearance is not yet proven in-game.

Build/evidence: `validation/survival-power-build.log`; latest `validation/local-deployment.json`. No regression suites or game control. Models remain the selected 1.6m pack revision.


## More prominent containment rotation

Raised field yaw/pitch/roll amplitude from0.75°+3.25°×load to6°+3.25°×load. Existing waveform frequencies, translational wiggle/bob, ring motion and startup/shutdown blending are unchanged. Script compiled with zero warnings/errors and was copied to the local mod with matching bytes. No model export needed; no regression suites or game reload. Evidence: `validation/core-rotation-build.log`, `validation/local-deployment.json`.


## Continuous, reversing core tumble

User clarified the sphere needs actual spin, direction changes, half-turns and minor adjustments. Added multi-axis tumble atop the existing small tilt using saved Motion.SpinPhase: yaw0.06p+145sin(0.04p)+45sin(0.11p), pitch105[sin(0.05p+0.6rad)-sin(0.6rad)], roll0.02p+60[sin(0.09p+0.9rad)-sin(0.9rad)] (p in degrees; sine inputs converted to radians). Linear yaw/roll drift supplies continuous spin; larger mixed-frequency terms create smooth reversals. All terms close at the existing36000°phase wrap, and input phase scales with load/cooling. Preserve positional drift/bob and gyro ring code. Integrate the existing90-tick shutdown brake, then quaternion-align the intact sphere as authored age falls1170→1038 before tile recovery begins. Existing maintenance targets inherit the moving sphere pose. No new state or model export. Build passed zero warnings/errors; runtime copied to local mod with matching bytes. Game review pending; no regression suites. Evidence:`validation/core-spin-build.log`.


## Stronger emissive glow — 16 September 2026

Raised reactor/subpart and external outlet emission from4 to12 through one shared constant, preserving fuel hues and red/off/yellow/incomplete/vent state timing. Added one client-only native MyLight per visible core: intensity2.5 at full emissive phase,4.5m range,falloff2,no shadows,no lens glare. It follows plasma world position and fades through shutdown/ejection; hidden plasma disables it, reactor Close releases it, dedicated servers never allocate it. Shadowless lighting approximates shell-wide emission without the opaque plasma/tiles self-occluding a central point source; illumination is bounded by the local range. Render bloom remains dependent on user graphics settings, which are untouched. Native evidence:MyLight.Start,UpdateLight and MyEntity.SetEmissiveParts; no new model or textures required. Build passed zero warnings/errors; two runtime files deployed with matching bytes. No game control or regression suites. Evidence:`validation/emissive-glow-build.log`.

## Thermal failure, native debris and independent core hazards — 16 September 2026

[THERMAL-FAILURE.md](THERMAL-FAILURE.md) records the accepted behavior, provisional tuning and runtime limits. Tile failure means an unreplaceable worn quartet, not an empty loose inventory while installed tiles remain serviceable. Capture actual electrical load before limiting native reactor Capacity to 10% of it; burn at 10× the captured load rather than the reduced output. The fuel-limited native capacity also needs the resulting 100× fuel-per-energy conversion. Reaction heat must not follow the artificially reduced electrical output. Failed containment continues heating after electrical shutdown until repaired/ejected; once supercritical it cannot be defused by either.

Native references read from prepared SE1 decompilation: `MyFloatingObjects.Spawn(MyPhysicalInventoryItem, MatrixD, MyPhysicsComponentBase, Action<MyEntity>)` creates replicated floating objects asynchronously. Its callback requires physics; cast to public IMyEntity for velocity access. `MyFloatingObject.GetPhysicsShape` calls `MyDebris.GetDebrisShape`, which uses embedded model Havok geometry. Without HKT, a ring becomes a solid bounding box. Added eight convex ring sectors and three tile edge prisms per model; the exported MWM bytes contain their HKT payloads. Floats remain pickable and subject to native cleanup, so use separate spent definitions with no fresh-tile conversion.

A dynamic one-block small grid carries the ejected plasma, with native natural gravity plus public CalculateArtificialGravityAt/AddForce for artificial gravity. Its world-space launch inherits reactor point velocity and has a minimum30m/s outlet impulse plus modest random scatter/spin. Server pose calculations reuse client drawing helpers; never depend on dedicated-server subpart render matrices. Handoff occurs beyond the outer ring's full clearance from the outlet, keeping scripted transit through the still-static door collision. Moving-door collision/obstruction detection are not implemented.

`CoreHazards` owns a separate world-storage ledger and secure server snapshots. A record follows the reactor until release, then follows the carrier. It retains position/fuse if either disappears, avoiding defusal by grinding or cleanup. Fuse decrements in simulation time and uses peak excess heat, so cooling cannot extend it. `MyExplosions.AddExplosion` performs native replication and honors engine damage permissions; a refused request must not erase the core. Damage/radius reference the loaded LargeWarhead MyWarheadDefinition (WarheadExplosionDamage and ExplosionRadius), using direct damage and cube-root radius multipliers. One native explosion, not repeated events. Body damage is distance/engine-dependent; the housing is not specially immune.

New `ArcanePlasma` material uses generated monochrome filaments, runtime fuel tint and18 emissive intensity. Explicitly set that material name; setting only native `Emissive` misses it. The1.2m smooth plasma sphere fits within the1.76m framed shell. Open tile centres expose it while preserving45mm thick rims and luminous edges. CM has nonmetallic alpha0; NG and ADD are Non-Color technical channels. Native collision export also scans `.hkt.fbx` with MwmBuilder: collision meshes need UV channels/materials or the extra import errors even if the main MWM was written. Disable only the background popup handler in export scripts to avoid Blender crashing while showing such errors; fix the underlying mesh channels and rerun the affected exports.

Seven exports and final C# compilation succeeded. Local delivery54files, revision `lab_64ff9a73f168`; runtime and DDS copies match. Static [fuel preview](validation/plasma-fuel-review.png) is Blender lighting, not game evidence. No regression suites or game control. Full play/balance/multiplayer validation remains pending.

Prepared game shader evidence: `Content/Shaders/Geometry/Materials/PixelUtilsMaterials.hlsli` FeedOutputInternal multiplies CM-derived base_color by pixel.color_mul and ADD.y by pixel.emissive. This supports retaining the filament pattern while runtime tint/intensity changes. The current scoped Graphify update indexes fourteen runtime/authoring files and THERMAL-FAILURE.md (446 nodes, 978 edges); historical document nodes remain explicitly marked as prior snapshots in GRAPH_REPORT.md. Host semantic extraction token usage is unavailable; no external LLM extraction calls were made.

## Native handheld telemetry and antenna access (2026-09-16)

An inert equippable tablet can use MyObjectBuilder_HandToolBase paired with a
MyObjectBuilder_ToolItemDefinition PhysicalGunObject, with matching subtype names
and empty action lists. Avoid an ammo-less rifle as a dummy tool. The held entity
has no native text surface, so the model is a real carried asset and live card
telemetry is a Text HUD API overlay; a gated native notification is the fallback.

MyCharacter and MyAntennaSystem entry points fail the mod whitelist. Public
IMyControllableEntity.EnabledBroadcasting and entity components MyDataReceiver /
MyDataBroadcaster are allowed. Walk BroadcastersInRange with reciprocal receiver
membership and CanBeUsedByPlayer at each hop. Require a working accessible actual
antenna in the reactor's logical group plus reactor access. Use the native links
for ranges/laser connections; do not infer connectivity from distance alone.
The tablet is read-only and does not require or expose Remote Control.

SCF's CoreTypeLCDScript provides the card/pill/bar palette reference; its
HudAPIv2 wrapper can be reused unchanged. Native LCD sprites use SquareSimple,
but HUD billboards need the transparent material SquareFullColor. Draw pooled HUD
messages manually in sprite order so connection/page changes cannot put newly
created background rectangles over existing text. See STATUS-DISPLAYS.md.

## Reactor restart persistence (2026-09-16)

SE snapshots checkpoint and sector before session SaveData. Flush MotionState in
VentSession.GetObjectBuilder (checkpoint stage) to include the current frame in
block storage. Keep the optional Enabled flag with the state and preserve legacy
native Enabled when it is absent. Never save a default Motion before it is loaded.

Native MyUpgradeModule.RefreshConnections runs on UpdateBeforeSimulation100;
checking controller counts immediately on load falsely shuts a restored reactor
off. The first custom sink Request also has no previous distributed interval.
The 120-frame restore barrier holds pose, suppresses output until the final two
power-priming frames, and then applies normal safety checks. Critical hazard timers
continue; new entity IDs still cannot inherit consumables/reserve. See
REACTOR-PERSISTENCE.md for source evidence and validation limits.

## MDK build versus SE mod imports (2026-09-16)

MDK was already installed with the same versions as SCF (ModAnalyzers 2.1.15,
References 2.2.7). A clean SDK/whitelist build did not catch TabletLink's ambiguous
IMyControllableEntity: MyScriptManager.UpdateCompatibility injects ten namespaces,
including VRage.Game.ModAPI.Interfaces, into every source. Use the fully qualified
Sandbox.Game.Entities.IMyControllableEntity for EnabledBroadcasting. The public
VRage interface has the same short name but lacks that member.

Use tools/compile_mod.py before deploying: temporary sources include SE's imports
and compile through the existing project/MDK setup. This reproduced the game-log
CS0104 before the fix and passed afterward. It is a compile step, not a regression
suite or a claim of game validation. See COMPILATION.md and compatibility build logs.

## Tablet hand pose correction (2026-09-16)

SE composes HandItemDefinition.LeftHand/RightHand with the held entity WorldMatrix
in MyCharacter's hand IK. Rotating ItemOrientation alone also rotates and swaps the
hand targets. For the requested 180-degree player-facing tablet turn, swap local
X grip anchors and counter-rotate the right-hand quaternion. Apply the requested
left local wrist roll before transforming that target back into the turned item's
space. All eight idle/walk/use/ironsight first/third-person poses must agree to avoid
snapping back. The first adjustment moves head-relative Z from -0.36 to -0.30 m;
its visual fit still requires the user's game review. Edit the definition generator,
not just generated Tablet.sbc, so future exports retain the pose.

### Left grip follow-up from the user's screenshot

The first local-Z wrist-roll correction faced the left palm into the display.
Superseding that attempted pose: derive the left orientation by reflecting the
right-hand rotation across the tablet centre plane (quaternion x,-y,-z,w), then
apply the same inverse item turn. Change only LeftHandOrientation in Tablet.sbc;
keep the accepted device orientation, depth, anchors and right grip. This is a
screenshot-informed pose adjustment, still awaiting visual confirmation in-game.

### Mirrored left grip and HUD follow-up

The user found the mirrored left hand almost correct but upside down into the
forearm. Apply a 180-degree local Z flip to that mirrored orientation before the
inverse item turn; this reverses its finger axis while preserving the palm-normal
axis. The tablet view origin also moves upward by 3% of viewport height, clamped
to the existing top margin. Pose and display placement await the next user review.

## Live source symlink (2026-09-16)

At the user's request, Mods/ArcanePower-Prototype now directly symlinks the repo's
ArcanePower/src. The old copied directory was moved intact outside Mods into
SpaceEngineers/ModBackups; its exact location is in validation/local-deployment.json.
Do not copy source files onto the mod path anymore (they are the same files), and
do not apply deployment-only model cache rewrites through the link. The deploy
helper has a target-identity guard and returns early for this live link. Changes to
SBCs still require the game's definition reload/load path to update in-memory data.

### Reset to a direct tablet-local grip mirror

At the user's request, remove accumulated left-only Z/Y flips and mirror the final
right grip directly in item space: position (-x,y,z), quaternion (x,-y,-z,w).
Keep source generator in that same space to avoid mixing head-relative and
item-relative corrections. Patch only the left-hand fields in the live source SBC
so independent manual tuning survives. This is an iteration, not a verified final
IK pose; the game still applies each hand target through the held item WorldMatrix.
