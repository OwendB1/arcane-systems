# Accepted native comparison inputs

These unversioned MWM files preserve accepted detector/subpart interfaces and
finished/stage comparison geometry for the existing export validators. They are
authoring inputs outside the loadable mod, not additional playable blocks.
Production `.blend` files remain the source of geometry, materials, LODs and weld
stages. `prepare_lab.model_source()` prefers a fresh export and otherwise uses
these accepted baselines. Successful packaging refreshes these inputs before
pruning loose exports from `src/Models/Cubes/large`.

Exact accepted Havok inputs are stored separately in `assets/collisions/`.
