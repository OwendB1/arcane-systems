# Arcane Power 0.2 alpha — unpublished package

This development package adds the compact modular Energy Core and three
construction stages for every public block. It includes the current reactor,
fuel/voxel art, containment hardware, vents, LCD and tablet implementations.

The 13 October runtime pass closes construction-stage startup/generation gaps,
restricts cold-start reserve requests to eligible reactors, revokes removed storage
module allocations immediately and finishes offline/distant storage visuals.
The native shared menu includes all twelve Power blocks.

Build the runtime ZIP from the repository root:

```sh
python3 ArcanePower/tools/compile_mod.py
python3 ArcanePower/tools/check_construction_stages.py
python3 ArcanePower/tools/check_energy_core.py
python3 ArcanePower/tools/package_release.py
```

The output is `.cache/release/ArcanePower-0.2-alpha.zip` under ArcanePower.
Extract its contents into a local mod directory and enable it in an experimental
SE1 world. The local development symlink already exposes `src` on the next world
load. Do not load both the extracted package and the development copy together.
The manifest records every packaged file's SHA-256 and required vanilla assets.

Direct mod code owns animation; Animation Engine is unnecessary. Text HUD API
is optional for rich handheld telemetry, with native text fallback. Runtime
assets and C# are included; Blender, SEUT, authoring FBX/HKT and development tools
are not required by players. Prototype ratings and recipes may change.

Read [Energy Core setup and test limits](ENERGY-STORAGE.md), the
[reactor instructions](README.md), and the [remaining work](../docs/arcane-power-remaining-work.md)
before survival testing. The package is ready for alpha testing, **not certified
for public release**. Multiplayer, final saved-charge reload, rated-load balance,
mixed-mod gameplay and complete mining-to-generation survival remain open.

Suggested Workshop title: **Arcane Power (Alpha)**. Description: Large-grid
arcane reactors, tiered fuels and containment, physical vent hardware, telemetry,
and expandable native battery storage. Construction stages support welding and
grinding. Experimental prototype; consult setup instructions and known limits.

No Workshop item has been created or updated.
