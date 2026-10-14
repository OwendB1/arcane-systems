# Arcane Power — Workshop publishing

Workshop item: [3819727962](https://steamcommunity.com/sharedfiles/filedetails/?id=3819727962).
The publishing source of truth is `workshop/title.txt`, `workshop/version.txt`,
`workshop/description.bbcode`, `src/modinfo.sbmi.main` and `src/thumb.gif`.
The title is generated as **Arcane Power (1.0.0)** from the two text files.
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

The local ZIP remains a separate development artifact; CI uploads the current
`src` tree with the selected metadata profile and animated preview.
