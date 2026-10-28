# Arcane Power — Workshop publishing

Workshop item: [3819727962](https://steamcommunity.com/sharedfiles/filedetails/?id=3819727962).
The publishing source of truth is `workshop/title.txt`, `workshop/version.txt`,
`workshop/description.bbcode`, `src/modinfo.sbmi.main` and `src/thumb.gif`.
The title is generated as **Arcane Power (0.3.0)** from the two text files.
The animated preview uses the 480×270 GIF below 1 MB.

`.github/workflows/arcane-power-workshop-upload.yml` calls the existing shared
Steam uploader. Pull requests build and validate metadata without publishing;
relevant pushes to `main` and manual dispatch build and then update this item.
There is one Power item, so its profile is always `main`. The repository's
existing `STEAM_USERNAME` and `STEAM_CONFIG_VDF` secrets are reused. Other mods
retain their PNG thumbnails and existing main/beta behavior.

Native `.mwm` models and source `.blend` files use Git LFS. Keep LFS enabled when
committing and pushing exports; the pre-push hook uploads their contents before
publishing the Git commit. The upload job fetches only the selected mod's `src/`
assets, so it publishes real models without downloading Blender checkpoints.
Existing Git history is preserved. After cloning for local asset work, run
`git lfs pull`; source-only CI builds do not need those binary downloads.

Fuel input ratings are **5 / 50 / 250 GW** for Aether / Helion / Empyrean,
including canister names and assembly instructions. Standalone Aether converts
10% for **500 MW**. Brayton converts a flat **80%** with every fuel.

| Setup | Electrical output |
| --- | ---: |
| Standalone Aether | 500 MW |
| T1 Brayton Aether | 4 GW |
| T1 Brayton Helion | 14 GW |
| T2 Brayton Helion | 40 GW |
| T2 Brayton Empyrean | 200 GW |

Regular and mirrored turbine limits match.
Standard/mirrored T1 turbines are capped at **3.5 GW each**; T2 at **50 GW each**.
Brayton cooling load equals delivered electricity, independently of fuel use.
Coolers retain **5/50 GW** ratings; radiator sections **2/20 GW**. Full Empyrean
needs 50 GW cooling per circuit, or 200 GW total. Existing saved heat is retained
without rescaling. Full-load canister endurance and controller economy are preserved.

Runtime isolation now stops generation and enters cooldown while keeping intact
cooling circuits open. Native GW output rounding no longer causes false accounting
trips. Complete circuits show potential cooling even while off; actual active
cooling still needs auxiliary power. LCD/tablet Overview and Power pages show
cooldown progress and an estimated simulation time to the 15% threshold.
The atmospheric and radiator Workshop plates reflect the doubled cooler ratings.
Version 0.1.3 also formats block and item descriptions into readable sections,
with native line breaks preserved by their definition generators.
The corrected ratings passed compiled runtime, fuel accounting, cooling telemetry,
fuel-definition regeneration and MDK compatibility checks. The current live world
has not been reloaded for this balance change; reload it to load new definitions.

Version 0.2.0 applies the gameplay cooling scale, simplifies flat conversion and
removes duplicate diagnostics and serialized telemetry. Retired ProtoBuf tags
remain reserved. LCD/tablet Power pages show cooling load, capacity, weakest-circuit
margin, potential cooling, cooldown backlog and fuel burn. Shutdown progress and
ETA remain available. Reactor and turbine blueprint plates use the new ratings.

Blueprint gallery images live in `workshop/images/` and are uploaded through
Steam's gallery editor. Upload the same filenames to replace images without
adding duplicates. SteamCMD handles the primary preview, not these gallery
uploads. Rebuild the original-model illustrations with:

```sh
blender -b --factory-startup --python-exit-code 1 --python ArcanePower/assets/render_workshop_blueprints.py
python3 ArcanePower/tools/compose_workshop_blueprints.py
```

The render scripts use temporary scenes and do not save the authoring blends. The renderer reads the saved SEUT Main collections directly, uses the actual mesh crease edges, and runs without the Blender UI or export add-on callbacks.

The twelve plates cover the reactor, controllers/vent route, storage cutaway,
four turbine variants, atmospheric cooling, radiator stacks, enclosed pipes,
bare pipes, the full Energy Core bank, all six storage modules, the native pipe
rotor and hull radiator arrays. Existing filenames remain stable, including
`framed-pipes-blueprint.png`, which now shows the enclosed casings. All plates
use matching 1600×900 cyan-on-navy layouts. The full-bank plate retains the
complete casing, glazing outlines and four attached modules.

The 0.3.0 gallery refresh uses the final saved models for plates 01, 02, 05, 06
and 07, and adds `pipe-rotor-blueprint.png` (11) and
`hull-radiators-blueprint.png` (12). The radiator stack shows the separate
1×1×1 base and three panels at their actual grid spacing; only the panels
provide cooling. The outlet drawing includes all four hatch subparts. The
rotor assembly uses its native default head offset, and the hull array uses
four adjoining radiators with self-sealing edge unions. Local image updates
and gallery uploads are authorized; publishing the mod package remains paused.

Rebuild selected plates with `compose_workshop_blueprints.py --plates 01 02 05 06 07 11 12`
after rendering their named studies. The local image bundle is
`.cache/arcane-power-workshop-blueprints.zip`; it is separate from the mod ZIP.
All twelve PNGs were checked at 1600×900, and the seven changed/new plates were
visually reviewed. The five unaffected plates, three authoring blends and
0.3.0 mod ZIP retain their pre-refresh hashes. Temporary render studies and
logs were removed after verifying the image bundle against the final PNGs.

## Local alpha package

This development package includes the 3×3×3 Energy Core, full-block 1×3×1
upgrade pillars and three
construction stages for every public block. It includes the current reactor,
fuel/voxel art, containment hardware, vents, LCD and tablet implementations.

Energy Core bays now accept any module type in any of the four positions. The
strongest attached stabilizer and transfer tiers apply without stacking; alignment,
access, construction and stabilizer support checks remain. Up to three capacity
modules can share one stabilizer. Charging tiers are 4/40/200 GW; ordinary
discharge stays 10/100/1,000 GW. Capacity shares are applied independently to each
ceiling, and native battery input caps match the 200 GW upper tier.
Existing modules reconnect after a world reload.

Jump-drive surge now charges an automatic affordable batch, selecting the smallest
charge deficits first and accounting for 90% efficiency and protected reserve.
Selected drives charge in five seconds through a batch-scaled discharge boost;
ordinary charging limits stay unchanged during surge. Recovery is the stabilization base plus
25% of that base per additional accepted drive, retained across cancellation and
reload. The single-drive picker is replaced by a batch summary in core details;
existing terminal/toolbar action IDs remain valid.

The current thermal catalog contains 31 public blocks: 16 pipe fittings, four
train variants, the reactor, two native pipe rotor parts and eight cooling
variants (tracking bases, panels, hull arrays and atmospheric coolers).
The 28 former HP/LP pipe IDs are hidden compatibility definitions sharing current
assets. All public blocks have icons, three construction stages and LODs where
required. Native checks cover collision, material dependencies, the reactor's
20 manifold subparts, eight shaft subparts and two radiator subparts.

The reactor supplies CO2 automatically, without timed filling or a pressure gate.
Its four independent duplex circuits each connect one train and its cooling,
preserving H/C roll at every joint. Cold startup and hot cooldown retain metered
compressor power. Repairs and reloads revalidate connections without refilling.
Each train has one
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
The roof backing is recessed beneath the central hatch surround: the previous
2 mm gap collapsed during MWM vertex packing and caused visible z-fighting.
The main and both distance meshes now pass native clearance sampling before
installation and during delivery checks. Construction stages were refreshed;
accepted collision inputs are unchanged. Headless close-ups at 1.8, 2.4 and
3.0 m and a separate in-game review world verified the repaired roof on 2026-10-27.
Reactor adapters have square-edged receiving lips that overlap the deployed
manifold noses. External pipe ends use short metal ferrules with matching inner
and outer glass boundaries, including framed/bare pipes and moving manifolds.
Metal annular faces close the ferrule walls toward the glass while keeping the
flow bore open; the glass is seated 2 mm behind each shoulder.

Brayton fuel conversion is a flat 80% with every fuel.
Each complete circuit keeps that efficiency. One through four circuits receive
25%, 50%, 75% and 100% of the reactor's nominal heat allocation. Cooling deficits
retain paid return waste in the reactor instead of silently limiting production.
Accumulated heat feeds the existing 125% irreversible failure/ejection lifecycle.
The Power page reports cooling capacity, required rejection and retained waste.
Each circuit needs cooling equal to output: 1 GW Aether, 3.5 GW T1 Helion,
10 GW T2 Helion or 50 GW Empyrean. Allow headroom for environmental losses.

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
in the local release package. First-tier capacity, transfer and stabilizer icons
now use the finished module models, including the stabilizer's separate fan
meshes. Hidden legacy icons are unchanged.

The 13 October runtime pass closes construction-stage startup/generation gaps,
restricts cold-start reserve requests to eligible reactors, revokes removed storage
module allocations immediately and finishes offline/distant storage visuals.
The native shared menu includes eleven Power blocks and 31 public thermal blocks. Earlier compact banks
retain their original hidden definitions and assets, preserving existing saves.

Build the runtime ZIP from the repository root:

```sh
python3 ArcanePower/tools/compile_mod.py
python3 ArcanePower/tools/check_thermal_runtime.py
python3 ArcanePower/tools/check_thermal_installation.py
python3 ArcanePower/tools/check_construction_stages.py
python3 ArcanePower/tools/check_energy_core.py
python3 ArcanePower/tools/check_native_thermal_motion.py
python3 ArcanePower/tools/package_release.py
python3 ArcanePower/tools/check_thermal_delivery.py
```

The output is `.cache/release/ArcanePower-0.3.0.zip` under ArcanePower.
Manifold pipe variants now use fully enclosed, airtight casings. Radiators use
an airtight 1×1×1 rotor base and up to three separate panels. Existing combined
radiators are replaced by the base; rebuild their panels and reconnect the
bottom socket as described in [the construction guide](THERMAL-CONSTRUCTION.md).
The eight enclosed pipe shapes and rotor base passed geometry audits and live
Blender reviews at 1.8, 2.4 and 3.0 m, including socket faces and the three-panel
assembly. Refreshed construction stages, LODs, collisions and icons accompany
the native models. Automated checks cover welded airtightness, panel linking,
cooling readouts and exported motion; this change still needs an in-game check.
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

The 0.3.0 source preflight reconciled the protected prototype fingerprint after
the authorized ejection hatch seal repair. Comparing against
`arcane-power-before-hatch-seal.blend` found 2,577 unchanged source/collision
objects, zero modified or removed objects, and exactly six additions: the hatch
pressure seal, outlet seat collar and four outlet hull corners. Existing reactor
exterior and controller detail audits also passed. The accepted prototype SHA-256
is `71122cff83d47918664085f89820b2d4a5e410adbf4550be70454b8e52917526` (previous protected fingerprint `2acf06e52fdd1ec7aa9210d1be61b992f7ec4b8e5a3b1341cd5b52367449657b`).

The final radiator-base finish keeps a recessed bearing dock: a 2.30 m square
deck sits 100 mm below the side-wall rim, with eight raised bolt heads and a
5 mm radial clearance around the bearing. The pressure seal backs that clearance
below the deck. Butt-jointed side armor removes the overlapping exterior strips;
eight recessed H/C lamps match the pipe rotor. Live Blender inspection covered
both top corners, side lamps and the underside at 1.8, 2.4 and 3.0 m with a fixed
48 mm lens and studio light. Both LODs and all three construction stages were
also inspected. Side fittings now follow their supporting panel through the
radiator and rotor construction stages, and their frames stay inside the casing.

The source audit passed all 59 models; a focused recheck passed after the final
construction attachment changes. Native installation checks extract and compare
the actual shipped collision bytes, verify hot/cold emissives on the three mains
and both LODs (plus radiator status), and exercise six flat Havok hulls per block:
486 face contacts and 44 clear sweeps above each casing. The radiator's moving
subpart collision remains unchanged; its old casing inputs have a named checkpoint.
The 255 native airtightness/stack-link checks and 1,820 exported-motion checks
passed. Solution and SE compatibility/whitelist builds passed.

Native compilation is **not warning-free**: the full thermal batch emitted
18,399 degenerate-triangle warnings from MWMBuilder's packed-vertex checks, mostly
in reactor/turbine fine detail. The native import, material, collision and motion
checks pass, but these warnings remain a visual-validation limitation. No live
game reload or new in-game acceptance test was performed for this 0.3.0 export.

The completed 0.3.0 local package contains 692 files (444,406,459 bytes), including
466 native meshes across the mod. Its thermal catalog has 27 authored families,
31 public variants, 81 construction models and 158 LODs. The existing scripts
also refreshed 23 prototype scenes and 15 hardware construction stages, using
the thermal source's accepted sealed blast shields. Delivery validation checks
every ZIP member against the installed mod, including all 51 scripts and 25
definition files. The package SHA-256 is
`68c990b2966d6019ac77c4caef372e03b8058a69cad5f88b0e3e4f5319aefa7d`.
