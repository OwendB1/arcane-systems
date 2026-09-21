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

The full card overlay uses **Text HUD API** (Workshop 758597413), the existing
SCF integration. Add that dependency to the world for the full overlay. Without
it, the same equipped item gives a live native text readout with page selection
and identical antenna gating. Its model has a static screen motif and a cyan/
amber connection light; live values are displayed in the HUD beside the held
model, not rendered into the physical mesh screen.

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
  `ReactorTablet.cs`, `TabletLink.cs`: shared telemetry, renderers and access.
- `HudAPIv2.cs`: Draygo's Text HUD API wrapper, reused unchanged from SCF.
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

The tablet HUD origin is raised by 3% of screen height (about 32 pixels at
1080p), retaining a 24-pixel top margin. Text and background move together.

Latest left-grip refinement: following the user's debug-axis observation, apply
a further 180-degree rotation about the current grip's green/local Y axis.
Only the left-hand orientation changes; visual confirmation remains pending.

Current grip revision supersedes the incremental flips above: the left grip is a
fresh mirror of the final right grip in tablet-local coordinates. Reflect position
X across the centre plane and use quaternion (x,-y,-z,w); no additional left-only
turns. The live SBC edit preserves other hand/item tuning. Both hand origins are
relative to the held item; the item's own pose then places it relative to the
character. Visual confirmation is still pending.
