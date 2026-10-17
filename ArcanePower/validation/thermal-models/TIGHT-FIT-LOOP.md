# Hard edges and tight assembly refinement

The generated captures and review queues described here were pruned during the
16 October 2026 cleanup. Blends, checkpoints, audits and the pre-pass interface
fingerprint remain; this document records the historical refinement decisions.

User feedback: the basics are decent, but the models still read as rounded and
loosely spaced. Preserve the previous detail pass as a baseline, then fix the
geometry before adding further native asset/texture detail.

Live source: `assets/arcane-thermal-models.blend`, official Blender MCP,
Blender 5.2.1 LTS. Checkpoint: `arcane-thermal-before-tight-fit-refinement.blend`.
`tight-fit-before-interfaces.json` records all cells and ports before editing.
The approved reactor variant and original reactor/battery/concept sources stay
on their existing builders and retain their geometry.

Diagnosis: the production builder still inherits broad generic chamfers and a
concept flange template. Major machine bays also retain blockout spacing:
separated train casings, sparse heater vessels, wide roof-hatch margins, open
plate-bank pitch and unsupported-looking pipe flange blocks. Atlas details were
added before these proportions were settled.

Skill decision: use the existing live/modeling/UV/native-atlas methods. Explicit
user and repository hard-edge rules override the generic rounded hard-surface
recipe. Enforce the edge profile in the production builder and audit; close the
specific mechanical gaps, preserve functional curvature and real air/service
clearances, then fit native detail assets to supported surfaces. No new skill or
dependency is needed for these repairs.

Gates: checkpoint and interface fingerprint → geometry review → native detail /
UV review → 1.8/2.4/3.0 m fixed-target/lens/light triplets → full assemblies →
save/reload and source/geometry/socket/reactor regression checks.

Geometry pass:

- Production boxes use flat faces with at most a 3 mm, one-segment chamfer;
  low-sided fastener meshes keep faceted normals. Curved bores, drums, pipes and
  fan grilles retain their functional curvature.
- The production flange has a 14 mm face setback, giving a 28 mm joint between
  two new flanges instead of 80 mm. Socket planes, hot/cold roll and neck bores
  stay fixed. A separate template preserves the approved reactor/concept flange.
- Train casing gaps reduce from 525/400 mm to 115/125 mm, including end-cover
  and stud clearance. Motor, cradles and supported markings move together.
- Heater vessels grow to 1.02 m radius at +/-1.12 m centres, with 1.08 m bands;
  the vessel gap is 200 mm and the band gap 80 mm. Roof hatch gap is 80 mm.
- Each recuperator now has 84 plates with about 22 mm air gaps and real bank
  feet. Radiator tile joints reduce to 10 mm in both directions.
- Machine manifold brackets carry the sockets onto the skids. Existing frame
  posts replace redundant lower legs where they already carry that load.
  Thin, angular pipe flange webs replace the old rounded-looking blocks.
- Service cassettes fit their native panel footprints; the fan controller fits
  inside the actual 300 mm shroud gap with a 280 mm backing.

Detail/texture loop:

1. Fresh whole-model geometry views, then 69 closeups at 1.8/2.4/3.0 m.
2. Fit native square vents, compact control faces, fastener plates and welded
   seams onto real backing. Retain original asset aspect ratios and UVs.
3. Reject large rounded native cover motifs as well as broad authored chamfers.
4. Reject the first trapezoidal detail where its atlas normal fringe makes dark
   triangular corners in the oblique roof view; use complete angular framed
   assets already validated on the cabinet instead.
5. Rescale the enlarged vessel-band UV circumferences and update their recorded
   paths/radii. Preserve native atlas UVs and all protected source assets.

The audit checks edge style, flat hardware, preserved interface fingerprints,
load-support clearance around flowing channels, the 14 mm face setback, packed
train clearances, dense plate banks, solids, UVs and full backing. Visual review
is still required; numerical passes do not accept a model by themselves.

The final closeups also exposed pill-shaped normal-map borders on the native
Wire Vent motif. Replace that motif with the already-validated angular Square
Vent rather than stretching or repainting its atlas. Rounded cover motifs,
trapezoidal normal fringes and pill frames remain in rejected-view evidence.

A front compressor vent was partly hidden by the cold header and, on the premium
unit, the controller. Move that native asset to the clear rear casing surface;
fit it to the true curved backing and repeat the three-distance review. Initial
pipe-web camera rays passed through the cold pipe; the repeated views approach
through the open cage and inspect the flange/post load path directly.

Curved-support projection needed another repair: the initial 80 mm decal grid
passed its vertex checks but its chords dipped through the faceted cylinder,
producing a dark stripe. Curved supports now use a 20 mm projection grid; flat
panels retain the lighter grid. The audit samples triangle centres and edge
midpoints for buried decal faces. Native UV rectangles and the 1.5 mm outward
offset are retained.

Completion: saved and reopened `arcane-thermal-models.blend`. All 30 revised
mains retain detail/texture revision 2; 31 mains, both grid assemblies and all
47 reactor poses pass. The current evidence set contains 102 three-distance
triplets, 30 whole models and two assembled layouts. All 45 native image
references resolve. No native exports, LOD/build-stage or gameplay changes were
made in this refinement pass.
