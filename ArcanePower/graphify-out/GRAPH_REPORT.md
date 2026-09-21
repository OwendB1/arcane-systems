# Graph Report - /home/owendb/Documents/GitHub/arcane-systems/ArcanePower  (2026-09-16)

## Corpus Check
- 3 files · ~622 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 544 nodes · 1159 edges · 43 communities (21 shown, 22 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 54 edges (avg confidence: 0.79)
- Token cost: host semantic usage unavailable; no external LLM extraction calls.

## Community Hubs (Navigation)
- LEARNINGS.md / README.md
- Reactor.Motion.cs / 
- prepare_lab.py / build_animation_geometry.py
- CoreHazards.cs / ContainmentController.cs
-  / Reactor.cs
-  / VentSession.cs
-  / ReactorDashboard.cs
- CoreHazards.cs / 
- Reactor.Status.cs / 
- build_vent_bell.py / build_ejection_hatch.py
- build_tablet.py / fit_three_cells.py
- curve_chamber_glass.py / highlight_inventory_hatches.py
- check_prototype.py / seat_tiedown_handles.py
- build_physical_plasma.py
- build_deployable_chamber.py
- build_external_hardware.py
- STATUS-DISPLAYS.md
- THERMAL-FAILURE.md
- ArcanePower.csproj
- export_prototype.py
- widen_housings.py
- REACTOR-PERSISTENCE.md
- flush_roof.py
- integrate_supports.py
- refine_interfaces.py
- render_plasma_review.py
- COMPILATION.md
- 
- 
- 
- 
- 
- 
- 
- 
- 
- 
- 
- 
- 
- 
- 
- 

## God Nodes (most connected - your core abstractions)
1. `Arcane Power engineering learnings` - 101 edges
2. `Reactor` - 33 edges
3. `bpy` - 31 edges
4. `pathlib` - 30 edges
5. `importlib` - 28 edges
6. `math` - 24 edges
7. `Arcane Power 103-part direct-runtime prototype` - 24 edges
8. `CoreHazards` - 24 edges
9. `VentSession` - 23 edges
10. `mathutils` - 21 edges

## Surprising Connections (you probably didn't know these)
- `Arcane Power engineering learnings` --references--> `Prior-revision low-load spectator recordings`  [EXTRACTED]
  LEARNINGS.md → validation/recordings/recordings.json
- `Arcane Power engineering learnings` --references--> `Prior reactor and two-controller repair evidence`  [EXTRACTED]
  LEARNINGS.md → validation/recordings/repair.json
- `Prior-revision low-load spectator recordings` --bounds evidence for--> `Unproven gameplay and collision behavior`  [EXTRACTED]
  validation/recordings/recordings.json → LEARNINGS.md
- `Arcane Power 103-part direct-runtime prototype` --references--> `Prior-revision low-load spectator recordings`  [EXTRACTED]
  README.md → validation/recordings/recordings.json
- `Arcane Power 103-part direct-runtime prototype` --references--> `Prior reactor and two-controller repair evidence`  [EXTRACTED]
  README.md → validation/recordings/repair.json

## Import Cycles
- 1-file cycle: `assets/curve_chamber_glass.py -> assets/curve_chamber_glass.py`
- 1-file cycle: `assets/export_prototype.py -> assets/export_prototype.py`
- 1-file cycle: `tools/repair_seut_preview_textures.py -> tools/repair_seut_preview_textures.py`
- 1-file cycle: `assets/check_prototype.py -> assets/check_prototype.py`

## Hyperedges (group relationships)
- **Native controller recognition depends on detector geometry and fresh model data** — arcanepower_learnings_native_upgrade_matching, arcanepower_learnings_dummy_translation, arcanepower_learnings_model_cache_workaround, arcanepower_learnings_native_connection_evidence [EXTRACTED 1.00]
- **Curved transparent chamber solution** — arcanepower_learnings_curved_chamber_glass, arcanepower_learnings_clear_chamber_material, arcanepower_learnings_vanilla_glass_textures [EXTRACTED 1.00]

## Communities (43 total, 22 thin omitted)

### Community 0 - "LEARNINGS.md / README.md"
Cohesion: 0.06
Nodes (76): One-cell crescent controllers and native mating face, Stackable duct and outlet geometry export, SEUT active-material callback guard, Actual alternative fuels, selected capacity and public replenishment, Historical Animation Engine upstream source and wiki, Historical Installed Animation Engine V2 contract, Fixed solid island and four retracting annular leaves, Historical Binary MWM reference and rest-transform validation (+68 more)

### Community 1 - "Reactor.Motion.cs / "
Cohesion: 0.07
Nodes (24): Guid, IMyInventory, MyItemType, Random, Reactor, Matrix, MatrixD, Vector3 (+16 more)

### Community 2 - "prepare_lab.py / build_animation_geometry.py"
Cohesion: 0.06
Nodes (34): add(), Author native inert hand-tool, inventory item and assembler recipe definitions., vector(), Subtle baseline haze plus native window dirt/reflections; no MWM rebuild., base64, hashlib, os, pil (+26 more)

### Community 3 - "CoreHazards.cs / ContainmentController.cs"
Cohesion: 0.14
Nodes (29): ArcanePower, draygo.api, protobuf, sandbox.common.objectbuilders, sandbox.game, sandbox.game.entities, sandbox.game.entitycomponents, sandbox.game.gamesystems.textsurfacescripts (+21 more)

### Community 4 - " / Reactor.cs"
Cohesion: 0.05
Nodes (26): MyEntitySubpart, MyGameLogicComponent, MyInventoryBase, MyLight, MyReactor, MyResourceSinkComponent, ContainmentController, float (+18 more)

### Community 5 - " / VentSession.cs"
Cohesion: 0.07
Nodes (22): IEnumerable, IMyTerminalAction, IMyTerminalControl, IMyTerminalControlButton, MyObjectBuilder_SessionComponent, CorePhase, MotionState, VentPhase (+14 more)

### Community 6 - " / ReactorDashboard.cs"
Cohesion: 0.10
Nodes (21): HudAPIv2, IMyHudNotification, MyIni, MySessionComponentBase, MyTSSCommon, Reactor, ScriptUpdate, ReactorDashboard (+13 more)

### Community 7 - "CoreHazards.cs / "
Cohesion: 0.13
Nodes (13): CoreHazard, CoreHazards, bool, Dictionary, float, int, List, long (+5 more)

### Community 8 - "Reactor.Status.cs / "
Cohesion: 0.18
Nodes (7): Reactor, StatusReport, StatusRow, double, int, List, string

### Community 9 - "build_vent_bell.py / build_ejection_hatch.py"
Cohesion: 0.15
Nodes (11): Inner four-leaf vent closure and lined door pockets joining the roof hatch., Replace the top conveyor skin with a four-leaf, conveyor-connected vent hatch., Replace static intake grille bars with 32 radial shutter subparts., Ceiling vent intake and six nested, separately exportable blast-shield sleeves., Static inspection only; no timeline/keyframes or runtime trigger., set_vent_pose(), Repair already-built solids affected by the original annulus winding bug.  Leave, Neutral SEUT material preview; keep vanilla material references for export.  If (+3 more)

### Community 10 - "build_tablet.py / fit_three_cells.py"
Cohesion: 0.16
Nodes (7): Arcane handheld telemetry tablet; original geometry with SEUT native materials., Fit the reactor to 5x3x5 SE cells without scaling its native interfaces., Give all four grid-facing conveyor mouths native SE inventory access panels.  Ru, Replace the side conveyor bays with native upgrade sockets in the same base row., Restore a true 80-triangle sphere after housing scaling; radius 1.30 m., math, mathutils

### Community 11 - "curve_chamber_glass.py / highlight_inventory_hatches.py"
Cohesion: 0.19
Nodes (6): Run after fit_three_cells.py in Blender: seated curved, low-reflection glass., Export native hatch sections and point conveyor highlights at those sections., Render inventory/build-menu icons directly from the authored models., bpy, copy, pathlib

### Community 12 - "check_prototype.py / seat_tiedown_handles.py"
Cohesion: 0.22
Nodes (6): Blender geometry evidence, not a substitute for an in-game interaction check., Remove obsolete trunk boxes after the widened round housing has been built., Centre native tiedown decals on accessible deck plates, preserving atlas UVs., Seat native SEUT atlas decals onto the actual faceted drum armor., importlib, mathutils.bvhtree

### Community 14 - "build_deployable_chamber.py"
Cohesion: 0.36
Nodes (5): annulus(), box(), mesh_object(), prism(), Author SEUT subparts and the direct-script motion manifest; no Blender timeline

### Community 16 - "STATUS-DISPLAYS.md"
Cohesion: 0.33
Nodes (6): LCD dashboard and equippable antenna-gated tablet, Asset and implementation references, Delivery evidence and remaining review, Equippable tablet, LCD setup, Values and warning semantics

### Community 17 - "THERMAL-FAILURE.md"
Cohesion: 0.33
Nodes (6): Current thermal failure and physical ejection implementation, Accepted behavior, Asset delivery, Explosion scale, Physical discharge and persistence, Provisional thermal balance

### Community 18 - "ArcanePower.csproj"
Cohesion: 0.40
Nodes (4): net48, Mal.Mdk2.ModAnalyzers (2.1.15), Mal.Mdk2.References (2.2.7), Microsoft.NET.Sdk

### Community 21 - "REACTOR-PERSISTENCE.md"
Cohesion: 0.50
Nodes (4): Reactor save timing and restart restoration, Native source evidence and delivery, Restore timing, Save timing

### Community 22 - "flush_roof.py"
Cohesion: 0.67
Nodes (3): Seat the complete round roof against the 3-cell ceiling, retaining recessed seam, seat(), top()

### Community 23 - "integrate_supports.py"
Cohesion: 0.67
Nodes (3): project_uv(), Replace blocky pillar feet and flat upgrade adapters with curved housing details, solid()

### Community 24 - "refine_interfaces.py"
Cohesion: 0.67
Nodes (3): box(), move(), Add glass and native, integer-cell controller interfaces to export scenes.

## Knowledge Gaps
- **33 isolated node(s):** `net48`, `Mal.Mdk2.ModAnalyzers (2.1.15)`, `Mal.Mdk2.References (2.2.7)`, `Microsoft.NET.Sdk`, `base64` (+28 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **22 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.
## Scoped update audit — 16 September 2026

Current runtime sources and compilation helper were re-extracted using Graphify AST extraction and source replacement. The new COMPILATION.md specification was semantically indexed by the host. Earlier document nodes remain historical snapshots; consult the current specification for compiler compatibility fix. No agents or external LLM calls were used; host semantic token cost is unavailable, not a measured zero. No regression suite or game interaction ran. Binary assets are linked by the specification but were not indexed as source.
