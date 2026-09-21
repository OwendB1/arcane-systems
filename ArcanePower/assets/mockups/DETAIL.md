Arcane Power — rounded SEUT detail study (v03)

Open [arcane-power-mockups-v03.blend](arcane-power-mockups-v03.blend), scene **08 Rounded reactor detail**. Earlier studies remain in the file. Frame 440 shows the running reactor; Space plays the existing 20-second startup. Numpad 0 selects the review camera.

The circular machinery drum, open deployment well, and circular upper housing replace v02's square foundation and bridge. Four short radial trunks carry grid-aligned conveyor interfaces. Segmented deck plates, layered armor collars, cooling fins, coolant pipes and couplings, structural brackets, dispenser guide rods, and service controls provide the next level of mechanical detail.

- [Overall running view](previews/detail-rounded.png)
- [Conveyor and controller closeup](previews/detail-interfaces.png)
- [Parked rings and open deployment well](previews/detail-parked.png)

The installed SEUT library does include reusable parts. This scene uses actual meshes from `Models/Common.blend`: Conveyor LG, Conveyor Access LG, Conveyor Frame LG, Upgrade Port LG, Terminal LG, and Terminal Screen. Their original UVs and materials are retained. `Atlas3.blend` and `ButtonsAtlas.blend` supply maintenance panels, vents, fasteners, handles, and controls. These atlas details are textured planes; the structural housing, pipes, fins, and brackets are separately modeled geometry.

Sources:

- [SEUT asset repository](https://github.com/enenra/seut-assets): reusable model, material, and decal libraries. These supplied parts are reference/library assets, not original Arcane Power geometry.
- [Space Engineers Utilities](https://github.com/enenra/space-engineers-utilities): Blender authoring/export integration. Installed version inspected: 1.2.2-alpha.3, Blender 5.2.1 LTS.
- [Keen's modding guide](https://www.spaceengineersgame.com/modding-guides/modding/): Mod SDK and editable game asset sources. The installed SDK's CargoContainerSmall and ConveyorTube FBXs remain in scene 07 for comparison.
- Local `CubeBlocks_Logistics.sbc`: large-grid small cargo, conveyor junction, and conveyor tube occupy one cell; large cargo occupies 3×3×3 cells. These definitions guide reference scale rather than dictating our reactor dimensions.

| Dimension / convention | Applied in this study |
| --- | --- |
| Large-grid cell pitch | 2.5 m |
| Provisional reactor occupancy | 5×5×5 cells; 12.5 m nominal cube |
| Conveyor reference face planes | X or Y = ±6.25 m; port centers Z = 1.25 m |
| Native conveyor insert mesh width | 1.36 m; frame width 2.00 m |
| Native upgrade port mesh width | 0.68 m |
| Interface transforms | Native scale; translation and rotation only |
| Library conveyor origin | Outer face near local Z = 1.25 m; access hatch has a small raised lip |
| Astronaut reference | 1.8 m |

The reactor's design dimensions are provisional. Grid-face markers are explicitly reference empties, not functional export dummies. The source mesh bounds and instance counts are recorded in [detail-asset-sources.json](detail-asset-sources.json).

The four dispensers and two-ring animation are retained from v02: rings rise, 20 batches assemble four triangles each, rings tilt, then ignition begins. This pass does not yet detail the three/four-ring tiers, battery, or vent outlet. Those earlier concept scenes remain available. Tile consumption and Animation Engine integration remain planned gameplay/prototype work.

[detail-validation.json](detail-validation.json) records native interface sizes, four conveyor connections, two upgrade interfaces, all 20 tile batches, and ring bay/cap clearance across 480 frames. Base ring vertices stay within radius 2.628 m and Z 0.935–8.444 m. This is a geometric envelope check, not exhaustive collision validation. Production topology, housing UVs/paint masks, LODs, construction stages, export dummies, and in-game checks remain outstanding.

The blend currently depends on the installed SEUT material libraries and textures at `/home/owendb/.local/share/blender-se1-setup/assets`. It is ready for this workstation; transferring it requires the matching library or a later dependency-packaging pass. Native interface UVs are preserved; original housing surfaces still use preview materials.

Reproduce from this directory with the installed SEUT assets available:

```sh
blender --background arcane-power-mockups-v02.blend --python build_detail.py
blender --background arcane-power-mockups-v03.blend --python check_detail.py
blender --background arcane-power-mockups-v03.blend -t 8 --python render_detail.py
```

The builder preserves v02 and writes v03. Save manual v03 edits to another version before rebuilding.
