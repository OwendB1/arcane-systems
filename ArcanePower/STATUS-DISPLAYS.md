# Reactor displays and handheld tablet

The LCD and equippable tablet share `Reactor.ReadStatus` and the SCF-inspired
`ReactorDashboard` layout. Power, heat, emergency reserve and spare tiles stay
visible above five pages: Overview, Power, Containment, Supplies and Vent.
Critical and ejected-core countdown warnings remain visible on every page.
The native reactor terminal sidebar is a short grouped summary.

## LCD setup

Select **Arcane Reactor** under the screen's Scripts content mode. A single
reactor on the same mechanical construct is selected automatically. For multiple
reactors, name the intended reactor explicitly in the screen block's Custom Data:

```ini
[ArcaneReactor]
Reactor=My Reactor
Page=Overview
```

`Reactor` accepts an exact block name (case insensitive) or entity ID. Ambiguous
names show a configuration message instead of silently choosing another reactor.
`Page` accepts Overview, Power, Containment, Supplies or Vent. All surfaces on a
block currently share this configuration. The square layout fits within the
surface without stretching; wide screens leave space beside the dashboard.
LCDs are local grid displays and do not require an antenna or Text HUD API.

## Equippable tablet

Craft **Arcane Reactor Tablet** in an assembler's tools category (3 iron,
1 silicon and 0.5 nickel ingots, 12 base seconds). Its inventory subtype is
`PhysicalGunObject/ArcanePower_Tablet`; hand entity subtype is
`HandToolBase/ArcanePower_Tablet`. It uses the native inert tool class, with empty
primary/secondary actions: no ammunition, mining, welding or firing behavior.

Equip it from the toolbar. Left click cycles through accessible reactors in
entity-ID order; the header identifies the selected reactor. Right click cycles
pages. Selection lasts for the current session and survives putting the tablet
away. It never changes reactor settings, opens the native terminal, controls the
grid, or issues a vent command.

All tablet readings require:

- A living player's equipped tablet and enabled suit broadcast antenna.
- A working, accessible radio/laser antenna on the reactor's logical grid group.
- A bidirectional connection through SE's actual broadcaster/receiver graph,
  with player access at relay hops and at the reactor itself.

There is no arbitrary proximity bypass, global distance allowance or requirement
for a Remote Control block. Native radio radii, connected laser links, relays,
logical grid connections and sharing permissions determine connectivity.
Connection is re-evaluated every ten simulation frames while held. Lost antenna
power, suit broadcast, range or access clears the report and shows disconnection;
reconnection resumes the same selected reactor. Unequipping or opening menus
hides the readout. Only locally replicated reactors can be selected; this does
not force replication of distant grids beyond SE's streaming range.

The tablet now displays live telemetry on its physical screen using SE's native
LCD texture renderer. It needs no Text HUD API dependency or attached grid.
The existing hand-tool renderer and grip are retained; the screen follows the
tool naturally. The cyan/amber connection light still identifies link status.
The handheld layout uses the display's landscape aspect ratio, with the same
five pages, status colors and antenna gating as the block LCD. Text and positions
use the same fitted canvas scale; an additional 10% font multiplier was removed
because it reduced glyphs to a few pixels before mipmapping. Placed LCD text
sizes are unaffected. Exported screen UVs map the held screen left-to-right and
top-to-bottom, accounting for the tool pose and SEUT axis conversion. The base
screen is uniform nonmetallic matte black, without baked cards or lettering.
While the readout is visible, a neutral emissive backlight keeps the panel
readable in darkness. It also lights the disconnected message. Hiding or
unequipping the tablet turns the backlight off and restores the matte black
base texture; it does not cast a lamp beam into the scene.
The generated readout also uses zero alpha, matching native LCDs: the offscreen
renderer preserves that channel, and the screen's ColorMetal material reads it
as metalness. Opaque alpha made the live screen fully metallic and suppressed
its emissive albedo, leaving it readable only under reflected sunlight.
The tablet's emissive multiplier is 0.025: its full emission mask is amplified
by scene HDR lighting. The earlier 2.0 setting washed the dark background grey
and clipped coloured labels toward white after the metalness correction. The
lower multiplier retains the dashboard palette and backlighting; native block
LCD brightness is unaffected. In-game confirmation of this adjustment is pending.

## Values and warning semantics

Output includes actual and tier-rated electrical production. Net subtracts
containment draw and reserve charging. Heat uses the current provisional 125%
supercritical threshold. Reserve reports available seconds and MWh. Supplies
show stock, current fuel burn/endurance, heat/load-driven tile demand, startup
shortfall and conveyor mode. Estimates exclude future conveyor deliveries.
Venting includes route state and shield/intake progress.

Unavoidable detonation begins only after crossing the supercritical threshold.
Ejection relocates that hazard; it does not cancel it. Cooler ejections decay.
The tablet provides information only, even during an emergency.

## Asset and implementation references

- `assets/arcane-power-prototype.blend`, scene `ArcanePower_Tablet`: 0.36 m wide,
  0.26 m high armored device with recessed display, grips, keys and collision.
- `assets/build_tablet.py`, `refine_tablet.py`, `export_tablet.py`,
  `render_tablet.py`, `build_tablet_definitions.py`: authoring sources.
- `src/Models/Items/ArcanePower_Tablet.mwm`, `src/Data/Tablet.sbc`: native model,
  inventory/hand/recipe definitions; nine bespoke DDS material maps and icon.
- `Reactor.Status.cs`, `ReactorDashboard.cs`, `ReactorLcd.cs`,
  `ReactorTablet.cs`, `TabletScreen.cs`, `TabletLink.cs`: shared telemetry,
  native display rendering and access.
- `validation/tablet-model.png`: Blender review render (powered emissive preview).

SE source references: `MyHandToolBase.Init` and `Shoot`,
`MyDefinitionManager.GetPhysicalItemForHandItem`,
`MyAntennaSystem.GetAllRelayedBroadcasters`, `MyRadioReceiver`,
`IMyControllableEntity.EnabledBroadcasting` and `MyTSSCommon`.
The internal `MyAntennaSystem` entry point is not mod-whitelisted; the mod walks
its exposed `MyDataReceiver`/`MyDataBroadcaster` links with the same mutual-link
and access conditions. No game-code reflection or plugin is required.

## Delivery evidence and remaining review

Compilation uses the installed SE assemblies and MDK mod whitelist analyzer.
SEUT exported the MWM and collision and converted the custom material textures.
No regression suites or in-game actions were run for this pass. Hand grip/pose,
first/third-person orientation, live LCD/HUD scale and antenna-loss behavior still
need user-requested in-game review. The current world was not reloaded or changed.

### Hand pose correction after first game review

The native item pose now turns 180 degrees around Y to face the user and moves
6 cm back toward the holder (head-relative Z -0.36 → -0.30 m). This applies to
idle, walking, use and ironsight in first and third person. Grip anchors exchange
model-space sides to match the turned device. The right wrist counter-rotates
against the device turn to retain its previous orientation. The first left-wrist
roll pointed the palm into the screen in the user's game screenshot. The left
grip now mirrors the right-hand rotation across the tablet centre plane, with
the same device-turn compensation. A subsequent 180-degree local Z flip corrects
the upside-down fingers reported in the next review. Source and local Tablet.sbc are updated;
the next game review must confirm the corrected grip alignment. No MWM re-export is
needed because this is a native hand-item definition adjustment.

The earlier tablet HUD origin adjustment has been superseded by the native
screen rendering; tablet telemetry is no longer placed in the HUD.

Latest left-grip refinement: following the user's debug-axis observation, apply
a further 180-degree rotation about the current grip's green/local Y axis.
Only the left-hand orientation changes; visual confirmation remains pending.

Current grip revision supersedes the incremental flips above: the left grip is a
fresh mirror of the final right grip in tablet-local coordinates. Reflect position
X across the centre plane and use quaternion (x,-y,-z,w); no additional left-only
turns. The live SBC edit preserves other hand/item tuning. Both hand origins are
relative to the held item; the item's own pose then places it relative to the
character. Visual confirmation is still pending.

## External tablet grip editor

Run from the repository root:

```bash
python3 ArcanePower/tools/tablet_pose_editor.py
```

This opens a separate Blender window with the actual exported tablet geometry
and the installed male astronaut glove meshes, skinned to editable finger rigs.
The initial finger pose is native `HoldingTool`; subsequent launches load your
exported finger poses.
It reads local game assets using the native MWM importer. Blender, Mono (`mcs`
and `mono`) and the installed game are required; `--game PATH` overrides the
default Linux Steam installation path. Extracted meshes stay in the ignored
`ArcanePower/.cache/tablet-pose` folder.

Open the viewport sidebar with **N**, then select the **Tablet** tab. Select
**Left**, **Right** or **Tablet** and use the gizmo, **G** to move, **R** to rotate,
or the numeric position/rotation fields. Local axes are selected by default for
wrist adjustments; **Ctrl+Z** undoes edits. Blue is the left glove and orange the
right. The item-pose dropdown previews idle, walking, use and ironsight in both
views. Native SE shares one ironsight transform between views; the editor edits
that shared transform rather than the unused `…Ironsight…3rd` XML vectors.

**Mirror right wrist to left** accounts for the native palm bones' different bind
bases. **Copy item pose to all eight modes** explicitly applies the current item
placement across modes. Hand targets are relative to the item, so adjusting the
tablet's own pose moves both hands with it.

To edit individual digits, choose **Hand**, **Finger** (thumb, index, middle,
ring or little), and **Joint** (base, middle or tip), then click **Edit finger
joint**. This selects the joint in Blender Pose Mode. Use **R** to bend/twist,
**G** to move, or the joint offset/rotation fields. The glove deforms immediately;
children follow their parent joint. Select **Left**, **Right** or **Tablet** to
return to wrist/item editing. Each hand has 15 editable joints. Finger poses
are shared across all eight item modes; wrist mirroring does not mirror fingers.

**Export edited transforms to mod** updates only changed pose vectors in
`src/Data/Tablet.sbc`, preserving unrelated definitions, and saves the pose source
in `assets/tablet-poses.json`. The definition generator reads this source so later
regeneration keeps the edited grips. When fingers change, export also saves
`assets/tablet-fingers.json`, builds
`src/Models/Characters/Animations/ArcaneTabletGrip.mwm` through SE's native
exporter, and generates `src/Data/TabletFingers.sbc`. The animation contains
joint-local translations/rotations, and a finger-only layer appended to the male
and female default animation controllers activates while the tablet is equipped.
It does not replace the controllers' existing layers or arm/wrist animation.
The tablet's legacy FingersAnimation is set to the same custom grip.

Export stages and verifies the native animation before writing live files,
and refuses conflicting transform edits
made on disk since import; **Reload definitions** discards pending editor changes
and reloads the current SBC and finger source. Reload the SE world to apply an
exported pose. An already-open editor needs to be relaunched for new code;
export any pending edits first.

This is a static grip preview using the male astronaut rig. SE still evaluates arm reach,
elbow IK, animation blending, camera positioning and walking motion in-game.
Check the resulting fit on both character models in-game. No tablet model
re-export is needed for grip changes. Opening the editor changes no
live definitions until Export is clicked.

Focused verification:

```bash
python3 ArcanePower/tools/tablet_pose_editor.py --background-check
```

The check exercises native VRage versus Blender matrix composition, both hands,
mirroring, view switching/shared ironsight, no-op and edited XML export,
native glove skinning, individual joint deformation, Pose Mode selection,
all thirty joints through native MWM export/re-import, finger JSON reload,
tablet-only controller masks/conditions, regeneration, and conflict/export-failure
handling against temporary files.

### Authored tablet grip

The fitted grip uses balanced wrist targets at item-local X ±0.208 m,
Y −0.040 m, Z −0.110 m, with the left wrist mirrored using the native palm
bases. The thumbs rest along the front side grips; the other fingers wrap
around the rear casing. Twenty-five joints have authored rotations; native
joint translations and bone lengths are preserved. The exported finger
animation is installed with the tablet-specific controller layer.

### Native handheld display verification

`TabletScreen` borrows the equipped tool's render IDs for
`MyRenderComponentScreenAreas` texture methods. It binds a helper to the tool's
component container without replacing its native hand-tool renderer. The helper
creates one generated texture, rebinds if native render IDs change and releases
the texture on unequip, opening menus/chat, losing the player, tool closure or
world unload. Rendering is local; no grid, block inventory or networked LCD
entity is created. Antenna/access checks still clear live readings when the
link is lost.

`assets/prepare_tablet_screen.py` removes baked artwork in front of the screen,
maps the screen UVs, sets its matte base/live emissive material and exports through
SEUT/MWMBuilder. It uses the established Wine trace-listener workaround and
rejects a stale MWM. PNG staging preserves packed zero alpha in the DDS maps.
Run it with Blender against
`assets/arcane-power-prototype.blend` after the tablet's authoring steps.

`tools/check_tablet_screen.py` compiles the shipped renderer, tablet controls
and layouts with engine doubles, and reads the shipped MWM through SE's native
importer. It checks page bounds with alerts, native font metrics with a minimum
readable glyph height, final texture coordinates after the native shift and
shader viewport division, render-ID replacement, texture ownership/cleanup,
selection and page controls, antenna-loss clearing, upright exported UVs and
uniform matte base textures.
It also checks the live texture's zero metalness alpha, so an emissive strength
alone cannot pass while the generated readout still blocks its own backlight.
`tools/compile_mod.py` also passes with zero warnings/errors. Actual GPU rendering
and first/third-person appearance still need an in-game review; restart SE to
ensure the updated model is loaded. The last in-game screenshot still showed
the removed baked ARCANE lettering, four cards and cyan diagnostic lines; world
reloads alone can retain that earlier model in SE's asset cache.

Front, back and side reviews are in `validation/tablet-grip-*.png`; the pose
and geometry-check report is `validation/tablet-grip.json`. Checks against the
native casing mesh found no glove vertices inside it after the 5 mm lowering
and a small right-thumb-tip clearance adjustment. Native animation export/re-import and
editor reload checks pass. The pose is fitted to the male reference rig;
arm IK and the female character fit still need a world reload and in-game
visual confirmation.

## Thermal readings

Reaction heat follows actual electrical output divided by conversion efficiency.
Cooling capacity is the connected equipment's available rejection, independent of
turbine load. Cooling required shows current waste heat; Full-load cooling is a
separate sizing target. Heat removed is actual rejection, bounded by available heat.
Accumulated heat is retained excess across the four independent circuits. Cooling
unit terminals also show connection/auxiliary-power state and their own heat removal.
