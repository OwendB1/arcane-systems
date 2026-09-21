Arcane Power — v02 deployment and containment-tile study

[Open the v02 Blender file](arcane-power-mockups-v02.blend) or [watch the 20-second startup preview](previews/startup-sequence.mp4). The original five v01 studies are retained. New scene **06 Tile assembly startup** demonstrates the revised mechanism; scene **07 SE logistics references** contains imported vanilla SDK cargo/conveyor reference geometry, separate from the Arcane models.

Select scene 06, go to frame 1, and press Space over the viewport to play. Timeline markers name the phases. This prototype demonstrates a two-ring reactor; three/four-ring deployment, shutdown recovery, and operating tile replacement still need animation studies.

| Frames | Sequence |
| --- | --- |
| 1–30 | Rings parked horizontally in the open base bay |
| 30–120 | Rings rise to their shared operating height |
| 120–199 | Raised hold / containment preparation |
| 200–359 | Four dispensers place eighty triangular tiles in twenty batches of four |
| 360–405 | Rings tilt around the completed faceted shell |
| 415–440 | Plasma ignition and spin-up |
| 440–480 | Running preview |

Keeping the rings horizontal during assembly leaves a clear central tile path. The storage bay is open geometry, replacing the old solid pedestal. The moving parts remain within the intended bay and chamber; they do not rise through an existing solid floor.

Review stills:

- [Parked rings](previews/startup-parked.png)
- [Raised rings](previews/startup-raised.png)
- [Half-built shell: forty tiles](previews/startup-40-tiles.png)
- [Running reactor](previews/startup-running.png)

The square base uses a provisional 5×5-cell footprint, service panels on the 2.5 m pitch, four conveyor connection placeholders on the outer faces, reinforced corners, and separate containment controllers. The human is 1.8 m tall. The intended block envelope is provisionally 5×5×5 large-grid cells, not yet an SBC definition.

Reference sources inspected locally:

- SDK `OriginalContent/Models/Cubes/large/CargoContainerSmall.FBX` and its material XML: port proportions, corner reinforcement, recessed panels, labels, and terminal placements.
- SDK `OriginalContent/Models/Cubes/large/ConveyorTube.FBX`: conveyor framing and connection geometry.
- Installed `CubeBlocks_Logistics.sbc`: small cargo is 1×1×1 cells, large cargo is 3×3×3, and the conveyor junction/tube are 1×1×1.
- SEUT material library and the installed `PaintedMetalColorable_cm.TIF`: reference materials and paint texture study. The original FBX files contain old/unresolved texture references, so the reference materials were remapped to the installed SEUT library.

The v02 file relies on this machine's installed SEUT material/texture paths under `/home/owendb/.local/share/blender-se1-setup/assets/`. It is not a self-contained texture package. The Arcane hull shader uses a simplified tinted paint preview; full game channel packing, UVs, paint masks, mount points, collision, and conveyor dummy axes remain production work. The vanilla meshes are reference objects, not part of the Arcane reactor geometry.

The triangle supply mechanic is specified as a proposal in the [design plan](../../../docs/arcane-power-plan.md): conveyor-fed Containment Tiles, startup installation, wear-based replacement, retained remaining condition on safe shutdown, and low-stock warnings. Blender demonstrates placement only. Eighty facets do not yet fix the inventory cost, recipe, or wear rate, and no live inventory consumption has been implemented.

Reproduce the new Arcane scene by opening v01 in Blender and running `build_startup.py`; this saves v02 and preserves the prior scenes. It does not import the optional reference scene. Save any manual v02 edits under another filename before rebuilding. Render and check from this directory:

```sh
blender -b arcane-power-mockups-v02.blend --python check_startup.py
blender -b arcane-power-mockups-v02.blend -t 8 --python render_startup.py
blender -b arcane-power-mockups-v02.blend -t 4 --python render_startup.py -- --animation
ffmpeg -y -framerate 6 -i previews/frames-startup/%03d.png -c:v libx264 -pix_fmt yuv420p -movflags +faststart previews/startup-sequence.mp4
```

[startup-validation.json](startup-validation.json) records all twenty four-tile batch checks, ignition timing, and bay/cap bounds at twelve ring poses. These checks do not establish exhaustive collision, game export feasibility, Animation Engine integration, or multiplayer behaviour.
