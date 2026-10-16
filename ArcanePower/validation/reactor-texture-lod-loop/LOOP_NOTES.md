# Reactor texture and derived-model loop

Source: `assets/arcane-power-prototype.blend`; official MCP, Blender 5.2.1 LTS.
Checkpoint: `assets/arcane-power-before-reactor-texture-lods.blend`.

Native texture pass adds folded cover seams, electrical warnings, roof lift markings, rolled drum welds and upper-band divisions. Broad paint stays clean. Curved decals are subdivided before projection so their faces do not chord through armor. Audit samples actual face centers rather than the overall centroid of a curved strip. Native atlas UVs remain interpolated.

Rejected placements: roof service cutouts, recessed jacket faces and occupied native hardpoint shoulders. Final backing and visibility checks pass. Reactor geometry, accepted pillars, roof seats, collision and native interfaces stay protected.

Actual live viewport inspected and shown to user: overview and 2.4 m drum close-up. The latter is `ui-drum-2.4m.png`. Matched 1.8/2.4/3.0 m surface views are in `distance-review.json`; derived comparisons in `derived-review.json`. Review helpers are hidden when judging construction meshes.

Reactor/controller construction stages now use current assemblies and pillar centers. Fittings follow their installed owner; decals over absent backing are omitted. Previous derived fingerprints are archived in `*-protected.json`, while accepted main/collision fingerprints remain active. Battery stages remain accepted and will be checked rather than rebuilt.

Distance meshes retain glazing and powered surfaces, drop subpixel hardware/decals and reduce curved tessellation. Native LOD descriptors resolve from mod root, so delivery uses immutable hashed filenames rather than export staging paths. No speculative thermal gameplay changes are included.

Status: complete. 32 mains, 50 LODs and nine refreshed construction stages passed native import and delivery checks. Twenty-one accepted battery stages retain identical delivered bytes. All 15 reactor/controller/vent stages passed bounds, collision, material and runtime rest-pose transition checks. The unpublished 306-file package resolves all runtime dependencies, including LODs. Both production files are saved; the live UI is left on the finished reactor overview. No game reload or Workshop publication.

Compiler finding: MWMBuilder ignores XML LOD Model paths and derives sibling paths. The native probe appends a replacement LOD tag and changes only its index pointer; all geometry, materials, anchors and physics payload bytes remain untouched. Native re-import verifies the new paths, distances and triangle counts.
