---
type: "query"
date: "2026-09-13T20:21:54.304736+00:00"
question: "What caused the inside-out reactor deck and conveyor-frame corner gaps, and how were the local fixes verified?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["Annulus winding repair and 87-solid migration", "Native chamfered conveyor-frame cutters", "Latest local geometry and interface QA"]
---

# Q: What caused the inside-out reactor deck and conveyor-frame corner gaps, and how were the local fixes verified?

## Answer

Expanded from graph vocabulary: annulus, winding, chamfered, cutters, geometry. BFS retrieved 47 nodes. LEARNINGS.md:78-82 records inward annulus face winding and reversal of 87 closed generated solids with negative signed volume; the migration asserts positive volume, while check_prototype verifies 24 upward deck tops. LEARNINGS.md:84-88 records cutters derived from the native Conveyor Frame LG projected convex hull, with chamfered corners and 1% clearance. The current 46 rays include hatch and frame edges; the previous 30-ray result is historical. Bounds, six detectors and ten colliders remain valid locally. In-game interaction/physics for the latest revision remain unproven; no deployment or game calls were performed.

## Outcome

- Signal: useful

## Source Nodes

- Annulus winding repair and 87-solid migration
- Native chamfered conveyor-frame cutters
- Latest local geometry and interface QA