# Rounded reactor manifolds and controller backing — 16 October 2026

Repository cleanup: generated images, contact sheets, review plans/progress and
the UI capture manifest mentioned below were pruned on 16 October 2026. These
notes record completed reviews, not an inventory of retained captures. The
maintained blends/checkpoints, `audit.json`, `curved-manifold-audit.json`,
`reload.json`, protected-source hashes and interface fingerprints remain.

Maintained source: `assets/build_reactor_thermal_manifolds.py`; output:
`assets/arcane-thermal-models.blend`, scene `ArcanePower_Thermal_ReactorHousing`.
Official Blender MCP, live Blender 5.2.1 LTS. Previous accepted state is preserved
in `assets/arcane-thermal-before-rounded-manifolds.blend`.

Four rounded twin-bore castings now unite each pair of deployed pipe heads.
Each has a tapered rounded rear connector that reaches inside the curved shell,
travels with the pipe carriage and retracts through a small bulkhead guide. Its
extending neck stays engaged in that guide throughout deployment. The preview
uses native axial scaling for this neck; game subpart integration must reproduce
that motion rather than assume Blender drivers export automatically.
Native SEUT materials, metric UVs, captive studs and a supported PRIMARY marking
finish the casting. Hot and return remain separate through-bores.

The original curved covers still close over the whole assembly. They inset
0.36 m and slide 0.155 rad under neighboring armor before the pipe carriages
extend 1.41 m. Deployed faces remain at X=±6.25 m, Y=±2.5 m, Z=−2.33 m, with
the existing 170 mm grid-height adapter. Original controller sockets and the
5×5×3 Blender-cell envelope are preserved.

Refinement findings and repairs:

1. A shared casting needs more room than the old two circular bores: cut a real
   internal travel pocket behind the original armor.
2. The first rear shoulder overlapped the intermediate sleeves and fixed glands:
   shortened the shoulder and fitted the connector neck between the glands.
3. A 14-position check missed a brief door collision during extension: expanded
   the gate to 47 positions, including motion boundaries, and widened sideways
   cover travel and its internal storage pocket.
4. New boolean walls inherited collapsed UVs: reproject only those faces while
   preserving accepted exterior UVs.
5. Close review found an undersized rear connector and coincident bore surfaces:
   extended the connector into the shell through a supported guide and offset
   the casting bore by 2 mm from the adjoining pipe interiors.
6. A rigid long guide tail entered the protected ring-well liner: replaced it
   with an extending neck anchored outside the liner. The guide remains engaged
   without cutting or moving the liner.

Evidence:

- `rounded-manifold-review-plan.json`: 48 close UI views, four bays, upper/lower
  heads, the bridge and rear joints at 1.8/2.4/3.0 m. Target/lens/light stay fixed
  within each triplet; actual view metadata is in `ui-reviews.json`.
- `rounded-contact-LA.jpg`, `-LB.jpg`, `-RA.jpg`, `-RB.jpg`: close-review sheets.
- Eight sampled motion UI views, closed/open final views and a whole-assembly
  view supplement the closeups. Earlier failure evidence is in `rounded-pass1/`.
- `curved-manifold-audit.json`: 47 sampled positions clear other moving groups
  and fixed geometry; original covers occlude the nose discs and full casting /
  connector silhouettes. Four castings and connectors are closed positive
  solids, share the pipe carriages and keep both bores open. Deployed connector
  roots reach inside the shell.
- `audit.json`: all 31 main sources and the two grid assemblies pass geometry,
  native material/UV, supported-detail and socket gates. The accepted reactor,
  battery and concept source hashes are unchanged.
- `reload.json`: saved-file consistency and validation results.

Controller backing correction (revision 4): the inherited conveyor-sized recess
behind each controller receiver is now filled to the curved drum/armor profile,
including the notch below the receiver. Only the 0.60 m native-port aperture
remains. The earlier partial lower infills were replaced by continuous closed
solids fitted directly to the original opening edges. Native yellow ports and
their transforms remain unchanged. The focused audit samples both restored
surfaces and retains all 47 motion checks. `controller-backing-review-plan.json`
and `controller-*-*.png` record front, lower, side and chamber UI checks at
1.8/2.4/3.0 m; the chamber views confirm the retained inner wall. Before editing,
the accepted source was preserved in
`assets/arcane-thermal-before-controller-backing.blend`.

This reactor work is modeling and a mechanical preview rig. Native subpart
exports and in-game animation/mode switching remain pending. Workshop/gallery
publication remains paused.

# Remaining Brayton main models and textures — 16 October 2026

Maintained sources: `assets/refine_thermal_models.py` and
`assets/build_thermal_models.py`; output: `assets/arcane-thermal-models.blend`.
The eight machine mains and 22 typed pipe/transition mains now have both the
geometry and texture stages. The approved reactor stays on revision 4 of its
separate manifold builder. The pre-detail state is preserved in
`assets/arcane-thermal-before-machine-detail.blend`.

- Both trains: bolted turbine split joints, inspection bosses, supported native
  instrument face, switchgear hinges/latch and skid anchors.
- Both heaters: bolted top pressure-service hatches, isolation-valve actuators,
  native warnings/seams, instrument cassette and fastened rear bracing.
- Both recuperators: supported hex tie nuts, instrument cassette and outward
  bank identifiers, clear of the cassette.
- Atmospheric cooler: eight supported guard retainers per fan, captive screws,
  rotor noses and an instrument face between the fan bores.
- Space radiator: small front/back tile retention shoes and screws, plus a
  supported pump-cassette pull. The two radiating faces remain exposed.
- All conduits/transition: cage anchors and tangent-aligned insulation clamps.
  PRIMARY yellow, HP blue and LP white accents cover the exposed pressure-lip
  walls and front annuli. HP/LP markings read 22 MPa / 8 MPa.

Native SEUT paint/metal and atlas assets retain their materials and source UVs.
Metric cylinder cap/wall UVs complement the transported pipe UVs. Wear stays on
small chamfers. Labels are native-material mesh markings; premium hot-end labels
now use 2200 C. Rebuilding a finished base replays both stages and relinks every
assembly instance to the new main collection.

Refinement findings:

1. The portrait native Tech Panel initially overhung its backing. Resized it at
   its original aspect ratio and checked every projected vertex against backing.
2. Captive-bolt names matched the cassette prefix. Limit detail lookup to the
   current main collection and exclude support fasteners.
3. Concept and production flange names coexist in the file. Resolve the actual
   current-main interface object rather than guessing a global datablock name.
4. Pipe neck sleeves duplicated the underlying conduit outside diameter. Remove
   those coincident pipe-only surfaces; retain the narrower machine adapters.
5. Close review caught coplanar heater brace crossings and inward recuperator
   text. Separate the braces by 20 mm, seat their ends in the posts and add
   fixings. Replace the labels with outward, split identifiers. The audit now
   checks text orientation against backing normals.
6. Head-on pipe review hid the circuit color on the lip sidewall. Extend its
   native accent to the front annulus, retaining the machined inner bore.
7. Some initial underside/anchor/riser views were occluded. Repeat from a clear
   side; rotate the inspection HDRI for the opposite-facing socket triplets.
   Lighting, lens and target remain fixed within each triplet.
8. The new brace fixing heads were backed by the braces but buried inside the
   corner posts. Move the heads onto the exposed post faces, over the embedded
   brace ends, and repeat the front/side closeups.

Evidence is captured from the actual live Blender UI with the official MCP:
`final-detail-plan.json`, `final-repair-plan.json` and `final-closure-plan.json`
record the 1.8/2.4/3.0 m triplets; `ui-reviews.json` records actual eyes,
distances, lens and studio light. The final record contains 126 triplets
(378 closeups), 30 whole models and two assemblies. `final-review.json` verifies
each image and its actual target/distance, plus fixed lens/light within each
triplet. Opposite-side HDRI angles are recorded at Blender's actual pi limit;
the review helper rejects angles outside that supported range.
`final-whole-plan.json` and the refreshed final whole captures cover all 30 mains.
`final-atmosphere-plant.png` and `final-parallel-bank.png` show linked mains in
their routed grid assemblies with a 1.9 m engineer / 2.5 m cell scale guide.
Earlier failed closeups are retained in `detail-pass1/`.

`audit.json` covers closed positive solids, bounds, native materials, UV
triangles, complete fastener/decal backing, outward text, socket necks, typed
connections/roll and occupied cells. `reload.json` records the saved-file checks;
the focused reactor audit retains its 47 poses and controller-backing samples.
After reopening the finished file, all 31 mains and both assemblies pass with
zero failures; 30 mains retain their finished geometry/texture stages. All 45
referenced native texture images are present, and all 47 reactor poses pass.
Successful Blender checks do not establish native-export or in-game results.
Thermal runtime, native exports, LODs and construction stages remain pending.

# Sharp edges and tighter assembly fit — follow-up refinement

The first detail pass above was superseded after user feedback about fillets and
excess space. The live source is now on detail/texture revision 2; the earlier
state is preserved in `assets/arcane-thermal-before-tight-fit-refinement.blend`.
The maintained production builder, rather than the concept source, now owns the
narrow edge treatment. Six/eight-sided hardware keeps flat normals; authored
housings have at most a 3 mm single chamfer. Bore walls, pressure drums, pipes and
fan guards retain their functional curvature.

The train body gaps are 115/125 mm, the heater vessels are closer and larger,
roof-hatch spacing is 80 mm, recuperators contain 84 closely spaced plates and
radiator tiles have 10 mm joints. Machine manifold load paths reach the skids,
reusing existing frame posts where possible. Pipe flanges use a separate sharp
production template with a 14 mm face setback, reducing two-flange joints from
80 mm to 28 mm. Their angular load webs replace the old blocks. Block sizes,
socket coordinates and hot/cold roll are checked against the recorded pre-pass
interface fingerprint.

The native asset/detail loop fits angular framed vents, control faces, fastener
plates and welded seams to their final backing. Cassettes fit the panel aspect
ratio, including a 280 mm fan-controller backing inside the 300 mm shroud gap.
Enlarged vessel-band UVs retain metric density. Broad rounded native cover/vent
motifs and a trapezoidal atlas fringe were rejected during the visual loop.
See `TIGHT-FIT-LOOP.md` for decisions and `tight-fit-pass1/` for rejected views.
The `tight-fit-final` and follow-up review plans contain the current closeups;
the `fit-final-*` whole views and assemblies supersede the previous `final-*`
images. Native export and game behavior have not been validated by this pass.

The revision-2 review closes with 102 fixed-target/lens/light triplets
(306 closeups), 30 whole mains and two layouts. The latest views are reconciled
in `tight-fit-review.json`; follow-up closure, visibility and curved-projection
plans supersede their matching first-pass images. Reopening the saved file
retains all 30 finished revision-2 mains. All 31 mains and both grid layouts pass
with zero failures, all 47 reactor poses pass and all 45 referenced native
texture images are present. The curved-decal gate also samples triangle centres
and edge midpoints, catching projection chords missed by vertex-only checks.

## Pressure-wall visibility and rotor pass — 16 October 2026

Visibility revision 1 adds 96 transparent fluid tubes across the 30 non-reactor
mains. Metal socket interfaces, seals, end closures, clamps and supporting cages
remain. Glass reuses the existing registered `ArcanePower_ClearChamber` material;
the stock SEUT glass preview was rejected because it obscured the internals.
Structural materials and the original reactor/manifold rig are preserved.

Both train variants now have hollow 120 mm casing walls with two upper side
inspection windows on the turbine and compressor. Narrow framed rails and
supported captive studs surround the windows. Each train contains three stages
of 18 turbine blades and two stages of 16 compressor blades, with twisted solid
airfoil sections and independent shaft-local roots. Full swept radial clearance
is 136.53 mm for the turbine and 137.24 mm for the compressor. Rebuilding both
trains from the maintained sources reproduces the geometry, native details,
glass and rotor parenting. The native casing tessellation is retained so the
projected compressor vent clears its curved backing.

The accepted UI evidence comprises 19 fixed-target triplets at 1.8, 2.4 and
3.0 m, with 48 mm lens and constant lighting within each triplet. Front/rear
windows, compressor, upgraded train, chamber, every conduit shape/adapter and
machine headers were inspected. Pipe-flange obstruction in early rear views
was resolved by changing the inspection angle. The latest header plan views
the coolant stubs from the side; metal adapters remain opaque. Six fixed-camera
motion frames replay compiled C# samples at 5/10/20/30/40/48 seconds, covering
cold compressor startup, turbine spool, hot operation and coastdown. The casing
silhouette and native texture placement stay stable as the actual blades move.

`inspection-glass-review.json` records the accepted view transforms, source and
limits. Saved-file reopening retains all 30 visibility revisions and both zero
authoring poses. All 31 mains and both grid layouts pass the updated solid,
UV/backing, native material, socket and swept-blade gates with zero failures;
protected production sources retain their hashes. The C# checks and SE
compatibility/full solution builds pass. Native thermal MWMs, definitions and
live SE motion validation remain pending; Blender preview is not game evidence.

## Dense axial train refinement — 16 October 2026

Both train variants now contain six 64-blade turbine rotor rows alternating
with six fixed 68-vane rows, plus six independent 56-blade compressor rows and
seven fixed 60-vane rows. Continuous tapered drums replace the sparse fan hubs.
Gas enters ahead of the first axial row and exits behind the last row through
seated end-plenum nozzles. The original external side sockets, grid sizes and
H/C roll are preserved.

Close inspection covers both variants at 1.8/2.4/3.0 m, with fixed targets, lens
and light per triplet. Saved-file audit passes all 31 sources and both grid
assemblies, including open bores through reinforcement bands, cradle and pipe
clearance, alternating fixed/moving rows and swept clearances. Offline runtime
checks and compatibility compilation pass. Native exports and game inspection
remain pending. [Current evidence](axial-train-review.json).

## Internal coolant visibility — 17 October 2026

The internal plumbing now has separate smoked blue-grey glass, metal backing,
three fitted collars per sight length and paired vertical guard rails. The first
candidate put the riser windows toward the pillar; the final windows face the
visible side. Distributor windows face the chamber. Native transparent-material
parameters accompany the Blender appearance.

Fixed-light, 48 mm live views cover the riser, distributor and pump at 1.8, 2.4
and 3.0 m. The complete assembly is legible at 24 m. All 31 geometry/UV/backing
audits and three grid assemblies pass. The reactor now has 208,026 source
triangles, including the added metal hardware. Original reactor/battery source
hashes remain intact. [Evidence](tube-contrast-review.json).

## Native delivery — 17 October 2026

All 31 public thermal definitions, 93 construction stages and 122 LODs are installed
in `Models/Cubes/large/Thermal/thermal_4918df2683ad` and the local 0.1.0 alpha ZIP.
The 270 new native meshes and 15 inherited subpart dependencies have complete
runtime dependency closure. All native geometry counts, collision bytes, 20
manifold rest frames and four shaft pivots/orientations pass import checks.

Mixed UV channel names initially zero-filled faces during distance-mesh joins.
The maintained LOD builder now preserves each part's render UVs before joining
and repairs reduction slivers. Rebuilt distance meshes pass native compilation
and fresh live texture review. The reactor's source remains 208,026 raw triangles;
evaluated native tessellation has 207,987. Blender's triangulation of the concave
vent accounts for the 39-triangle difference; the main was not decimated.

Native rest-frame checks also establish the required FBX empty-axis correction.
Weld stages retain 24 opaque coolant bodies beneath 88 metal jacket pieces.
The finished main view is restored in Blender. No SE world was loaded and nothing
was published. [Native import](native-export.json), [package check](delivery-check.json).
