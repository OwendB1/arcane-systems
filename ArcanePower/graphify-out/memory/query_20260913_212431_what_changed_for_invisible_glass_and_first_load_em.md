---
type: "query"
date: "2026-09-13T21:24:31.527729+00:00"
question: "What changed for invisible glass and first-load emissives?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["Glass visibility tuning after user report", "First-load emissive render-readiness retry"]
---

# Q: What changed for invisible glass and first-load emissives?

## Answer

Expanded from graph vocabulary: [glass, visibility, emissive, retry]. Glass parameters now use alpha0.28, reflectivity0.10 and Fresnel0.45 with unchanged native textures. A60-tick emissive retry handles render objects becoming ready after the first cached update; actual-method recording tests passed. Both fixes were redeployed, but live rendering remains unconfirmed. Source: LEARNINGS.md144-150.

## Outcome

- Signal: useful

## Source Nodes

- Glass visibility tuning after user report
- First-load emissive render-readiness retry