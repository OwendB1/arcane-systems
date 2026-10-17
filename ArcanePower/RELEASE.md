# Arcane Power — Workshop publishing

Workshop item: [3819727962](https://steamcommunity.com/sharedfiles/filedetails/?id=3819727962).
The publishing source of truth is `workshop/title.txt`, `workshop/version.txt`,
`workshop/description.bbcode`, `src/modinfo.sbmi.main` and `src/thumb.gif`.
The title is generated as **Arcane Power (0.1.0)** from the two text files.
The animated preview uses the 480×270 GIF below 1 MB.

`.github/workflows/arcane-power-workshop-upload.yml` calls the existing shared
Steam uploader. Pull requests build and validate metadata without publishing;
relevant pushes to `main` and manual dispatch build and then update this item.
There is one Power item, so its profile is always `main`. The repository's
existing `STEAM_USERNAME` and `STEAM_CONFIG_VDF` secrets are reused. Other mods
retain their PNG thumbnails and existing main/beta behavior.

Blueprint gallery images live in `workshop/images/` and are uploaded through
Steam's gallery editor. Upload the same filenames to replace images without
adding duplicates. SteamCMD handles the primary preview, not these gallery
uploads. Rebuild the original-model illustrations with:

```sh
blender -b ArcanePower/assets/arcane-energy-core.blend --python ArcanePower/assets/render_workshop_blueprints.py
python3 ArcanePower/tools/compose_workshop_blueprints.py
```

The render scripts use temporary scenes and do not save the authoring blends.

## Local alpha package

This development package includes the 3×3×3 Energy Core, full-block 1×3×1
upgrade pillars and three
construction stages for every public block. It includes the current reactor,
fuel/voxel art, containment hardware, vents, LCD and tablet implementations.

The 17 October delivery adds all 31 thermal blocks, including the latest reactor
manifolds, internal smoked coolant glass, turbine/compressor rotors and typed pipe
kit. All 93 thermal construction models and 186 LODs are exported. Native import
checks validate 334 meshes, collision bytes, material dependencies, 20 manifold
rest frames and four shaft pivots/frames. The reactor generates and pressurizes
its own CO₂ charge during powered commissioning; no gas supply blocks are needed.
The thermal design is now the sole playable Arcane Reactor; the old prototype
definition is retained under `assets/definitions/` and excluded from the mod. Its
Blender sources and accepted native comparison inputs remain outside the mod.
Existing thermal reactor subtype IDs are unchanged.
External pipe walls use continuous reflective glass; internal coolant plumbing
retains its accepted finish and geometry. Socket inserts and face seals now have
separate seats. Runtime manifold validation tolerates native export rounding,
and reactor connection guidance is limited to incomplete, settled Brayton setups.
Native moving meshes now share the main model's axes, correcting reversed pipe
travel and misplaced tail anchors. Actual exported vertices and LODs pass 1,376
runtime-pose comparisons against the authoring rig, including both train variants.
Each thermal block has its own
model-rendered inventory icon. Pipe icons identify
PRIMARY, HP and LP circuits; upgraded machines carry a tier marker. All 50 block
definitions, including seven hidden legacy blocks and the ejected core, are checked
for icons, model references and recipes. All 42 buildable blocks have menu entries
and three construction stages. [Block catalog](validation/block-catalog.json).
[Native delivery evidence](validation/thermal-models/delivery-check.json).

The 13 October runtime pass closes construction-stage startup/generation gaps,
restricts cold-start reserve requests to eligible reactors, revokes removed storage
module allocations immediately and finishes offline/distant storage visuals.
The native shared menu includes eleven Power blocks and 31 thermal blocks. Earlier compact banks
retain their original hidden definitions and assets, preserving existing saves.

Build the runtime ZIP from the repository root:

```sh
python3 ArcanePower/tools/compile_mod.py
python3 ArcanePower/tools/check_thermal_runtime.py
python3 ArcanePower/tools/check_construction_stages.py
python3 ArcanePower/tools/check_energy_core.py
python3 ArcanePower/tools/check_native_thermal_motion.py
python3 ArcanePower/tools/package_release.py
python3 ArcanePower/tools/check_thermal_delivery.py
```

The output is `.cache/release/ArcanePower-0.1.0.zip` under ArcanePower.
Extract its contents into a local mod directory and enable it in an experimental
SE1 world. The local development symlink already exposes `src` on the next world
load. Do not load both the extracted package and the development copy together.
The manifest records every packaged file's SHA-256 and required vanilla assets.
After packaging resolves all native subparts and LODs, it removes unused files
from `src/Models/Cubes/large`. Accepted collisions and native comparison inputs
are preserved under `assets/collisions/` and `assets/native-baselines/`; production
blends remain the rebuild source. Export staging must be regenerated for another
native compile. Ordinary deployment uses the current definitions and needs no raw
export files.

Direct mod code owns animation; Animation Engine is unnecessary. Text HUD API
is optional for rich handheld telemetry, with native text fallback. Runtime
assets and C# are included; Blender, SEUT, authoring FBX/HKT and development tools
are not required by players. Prototype ratings and recipes may change.

Read [Energy Core setup and test limits](ENERGY-STORAGE.md), the
[reactor instructions](README.md), and the [remaining work](../docs/arcane-power-remaining-work.md)
before survival testing. The package is ready for alpha testing, **not certified
for public release**. Multiplayer, rated-load balance,
mixed-mod gameplay and complete mining-to-generation survival remain open.

The local ZIP remains a separate development artifact; CI uploads the current
`src` tree with the selected metadata profile and animated preview.
