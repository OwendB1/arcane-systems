# Curved reactor manifold repair — 16 October 2026

Current model source: `assets/arcane-thermal-models.blend`, scene
`ArcanePower_Thermal_ReactorHousing`. Rebuilt from maintained Python, saved and
reopened in the existing official-MCP Blender 5.2.1 LTS window.

The rejected flat external cassettes are retained only in
`assets/arcane-thermal-flat-manifold-baseline.blend` and the rejected evidence
folder. This repair reuses the exact uncut lower armor profile from the preserved
pre-exterior-detail checkpoint, splits each sector into two closed leaves and
retains its native UVs. Four bays flank the two existing controller sockets.

Closed: all pipe heads are hidden behind the original curved profile. Open:
leaves inset 0.36 m then slide 0.125 rad sideways under the neighbouring armor;
two-stage pressure tubes then extend 1.65 m. The original collars, foundation,
controller receivers, glass, pillars, ring-well liner and ejection interface stay
unchanged. A real one-cell transition handles the 170 mm difference between the
native band height and the normal pipe lattice.

Refinement findings and repairs:

1. Flat housings broke the drum silhouette: replaced with original armor.
2. Existing service cuts left holes in reused panels: restored the exact uncut
   profile before splitting, rather than leaving an empty hatch opening.
3. Legacy detail provenance was being renamed with live references: provenance
   now stays tied to the original object; the gate rejects self-references.
4. Door corners and long pipes clipped the drum/ring well during travel: opened
   internal side pockets and used two telescoping stages outside the ring well.
5. Coincident annular caps caused jagged shading: staggered the end planes.
6. An internal radial cap became nonmanifold after boolean welding: removed
   that interior face without changing solid volume. New cut UVs are reprojected;
   UV validation ignores numerical slivers below 0.01 mm².
7. Old decals would float over the new opening: replaced with supported native
   warning marks which travel on the actual armor leaves. Internal studs seat on
   the real pressure bulkhead; hot/return bands are material faces, not overlays.

Evidence:

- 48 actual UI images: four bays, closed seams, both pipe heads and their roots,
  each at 1.8, 2.4 and 3.0 m. Fixed target/lens/light per triplet; metadata in
  `ui-reviews.json`. Contact sheets: `curved-contact-0.jpg` through `-7.jpg`.
- Transition UI images show inset, sideways opening and telescopic extension.
- `curved-manifold-audit.json`: all 14 sampled deployment positions clear fixed
  geometry and other moving groups; 264 samples confirm closed nose occlusion.
- `audit.json`: 31 main sources pass solids, dimensions, native materials/UVs,
  supported details and sockets; two actual grid assemblies pass 108 mating
  joints. Original reactor, battery and concept source hashes are unchanged.
- `reload.json`: focused and full model gates pass after save/reopen.
- Python compilation, grid-routing self-check, thermal balance self-check and
  `dotnet build arcane-systems.sln` pass (zero build warnings/errors).

These are model and rig proofs. New native collision/subpart exports, in-game
animation and standalone/Brayton gameplay switching are not installed. Other
machine detail and texture loops remain at their base-model stage during this
focused repair. No LOD/build-stage, Workshop, gallery or publication work done.
