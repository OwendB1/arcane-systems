---
type: "query"
date: "2026-09-13T20:32:01.190435+00:00"
question: "Why were the curved reactor supports hidden behind the glass, and what local evidence validates the support and preview fixes?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["Curved pillar saddles and upgrade surrounds", "Opaque supports hidden by accidental preview blending", "Latest local geometry and interface QA"]
---

# Q: Why were the curved reactor supports hidden behind the glass, and what local evidence validates the support and preview fixes?

## Answer

Expanded from graph vocabulary: supports, blending, saddles, geometry. BFS retrieved 61 nodes. LEARNINGS.md:90-94 records four curved tapered pillar saddles and two curved upgrade surrounds, preserving native fittings and detectors, plus repairs for empty Boolean material slots and degenerate UVs. LEARNINGS.md:96-100 records the visibility fault: PaintedMetal_Colorable kept SEUT technique MESH but had Blender BLENDED preview rendering. setup_preview.py restores DITHERED with TM Switch zero for native nontransparent materials; the far-side supports became visible without another geometry change. Local QA passes 24 deck normals, 46 hatch/frame rays, 16 corner backing samples, six detectors, bounds and ten colliders. Main and ring exports are current; the latest build has zero warnings/errors. Known SEUT W005 remains, collapsed-UV warnings are gone. No deployment or game operations were performed.

## Outcome

- Signal: useful

## Source Nodes

- Curved pillar saddles and upgrade surrounds
- Opaque supports hidden by accidental preview blending
- Latest local geometry and interface QA