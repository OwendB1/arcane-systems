---
type: "query"
date: "2026-09-13T19:49:09.762257+00:00"
question: "Also, make sure to put glass around the reactor chamber itself in between the pillars. Also, upgrade modules can only be placed at coordinates that are the same as the game's grid system. Use $se-dev-game-code to understand it better. Record it as needed into the repository learnings for this new mod using $graphify"
contributor: "graphify"
outcome: "useful"
source_nodes: ["Native containment upgrade matching", "Detector translation determines connection face", "Local content-suffixed model paths", "Curved chamber glazing and housing seals"]
---

# Q: Also, make sure to put glass around the reactor chamber itself in between the pillars. Also, upgrade modules can only be placed at coordinates that are the same as the game's grid system. Use $se-dev-game-code to understand it better. Record it as needed into the repository learnings for this new mod using $graphify

## Answer

Expanded from the original request using graph vocabulary: containment, detector, translation, model, paths. BFS retrieved the native containment, translation, cache and glass nodes. LEARNINGS.md:13-17 records complementary detector_upgrade positions on neighboring integer grid cells and translation-derived connection faces; cosmetic proximity does not qualify. LEARNINGS.md:19-23 records the observed stale-MWM reload and local content-suffixed block model path workaround, followed by native count 0→1→2. LEARNINGS.md:40-44 records curved chamber glazing and the mod-specific GLASS material using vanilla window dirt and chrome textures. Fuel/output/motion proof remains pending. Current workflow is Blender-first, with further game checks only on request.

## Outcome

- Signal: useful

## Source Nodes

- Native containment upgrade matching
- Detector translation determines connection face
- Local content-suffixed model paths
- Curved chamber glazing and housing seals