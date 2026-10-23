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

The current thermal catalog contains 24 public blocks: 16 pipe fittings, four
train variants, the reactor, atmospheric cooler, radiator and panel extension.
The 28 former HP/LP pipe IDs are hidden compatibility definitions sharing current
assets. All public blocks have icons, three construction stages and LODs where
required. Native checks cover collision, material dependencies, the reactor's
20 manifold subparts, eight shaft subparts and two radiator subparts.

The reactor generates its own CO2 during powered commissioning. Trains and coolers
share one duplex network, preserving H/C roll at every joint. Each train has one
lower-cell socket and regular/mirrored variants. The shaft line is 0.55 m lower;
close pipe runs use relieved supports. H enters the first compressor casing and
C leaves the turbine rear. Existing two-socket trains require pipe rerouting.
The 2×2×5 train includes a glazed compressor taper and a tightly joined generator
with a 24-tooth copper armature driven by the existing turbine subpart. Its fixed
magnet lining, lower inspection window and closed far wall are shared by all
four variants. The lengthened generator, window, armature and magnets meet the
smaller electrical cabinet through a half-round coupling cover. Rounded cable
bends, a continuous chamfered foundation and distinct standard/upgraded casings
complete the exterior. Low compressor saddles clear the manifold; the larger
struts use enclosed coolant passages and round cable sockets. The foundation
seats continuously on the block bottom without underside rails. Standard plates
read EX / 1200 B; upgraded plates retain EX / 2200 C. Fitted service doors,
rear cooling grilles, curved housing covers and manifold stiffeners fill the
previously blank reverse faces. Derived stages
and LODs follow the same source.
The sole playable reactor keeps its thermal subtype ID. Archived authoring
sources remain outside the shipped mod. Reactor internal plumbing is preserved.

Brayton efficiency now reaches its tier ceiling with four active turbines:
one through four provide 40%, 60%, 80% and 100% of that ceiling. Cooling deficits
retain paid return waste in the reactor instead of silently limiting production.
Accumulated heat feeds the existing 125% irreversible failure/ejection lifecycle.
The Power page reports cooling capacity, required rejection and retained waste.
Review existing one-train/one-cooler builds: at standard source power a single
train now needs two fully effective cooling units, or use four trains with at
least one fully effective cooler. Allow headroom for environmental losses.

[Block catalog check](tools/check_block_catalog.py) and
[native delivery evidence](validation/thermal-models/delivery-check.json) cover the
local package. Live SE appearance, multiplayer behavior and balance remain pending.

The advanced capacity, transfer and stabilizer modules and advanced containment
controller use the same gold **II** badge as the upgraded turbine. Their icon
renderers share `assets/icon_badges.py`; rerenders preserve the badge. Render only
selected battery icons with `render_energy_core.py -- --icons-only SCENE_NAME`.
Source PNGs live under `assets/icons/`; DDS conversion uses
`tools/texture_conversion.py::convert(..., icon=True)` before packaging.
The four 512-pixel transparent PNG/DDS pairs were visually reviewed and checked
in the local release package. Standard and hidden legacy icons are unchanged.

The 13 October runtime pass closes construction-stage startup/generation gaps,
restricts cold-start reserve requests to eligible reactors, revokes removed storage
module allocations immediately and finishes offline/distant storage visuals.
The native shared menu includes eleven Power blocks and 24 public thermal blocks. Earlier compact banks
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
