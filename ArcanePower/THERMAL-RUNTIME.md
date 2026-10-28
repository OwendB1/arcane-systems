# Thermal runtime — 25 October 2026

The sole playable reactor is `ArcanePower_Thermal_ReactorHousing`. The current
catalog has 31 public thermal blocks and 28 hidden pipe compatibility aliases. The old reactor prototype, heaters and recuperators are excluded from
the shipped definitions. Authoring sources remain available for rebuilding.
Live SE world validation remains pending; native and kernel checks are recorded
in the [delivery summary](validation/thermal-models/delivery-check.json).

Each public thermal block references a distinct 512 px DDS icon rendered from its
production main model; compatibility aliases reuse the canonical icon. Adapter
badges distinguish roll/reactor transitions, and tier II marks upgraded machinery.
`assets/render_thermal_icons.py` maintains the source PNGs; the existing DDS
converter applies sRGB BC7 compression, mipmaps and premultiplied icon alpha.
`tools/check_block_catalog.py` checks every block, including hidden legacy and
ejected-core definitions, and runs as part of the delivery check.

Inventory hatch detectors retain the original reactor's section highlights: the
two side hatches and bottom access hatch each select their own native mesh section;
the top selects its four vent-hatch leaves. Source cloning remaps SEUT object
references, and native export resolves the final mesh-section and subpart names.
The native release gate rejects missing targets before installing a model revision.

[Construction and commissioning instructions](THERMAL-CONSTRUCTION.md) cover the
four independent duplex circuits, adapters, H/C roll, welding, cooling and powered startup.
The client construction guide follows SCF's placement-arrow/HUD pattern using
independent native texture IDs, without an SCF dependency. It shares socket
matching and coordinate transforms with server dispatch, considers all 24 grid
orientations, and inspects unfinished blocks separately from running health.
Mismatch messages count one faulty connection, retaining both socket highlights.
Construction verification is advisory; existing server diagnostics and safeguards
remain authoritative. Text HUD API is optional, with a native notification
fallback. Native in-game visual validation is still pending.

The reactor owns modes, manifolds, fuel accounting, four independent circuit heat
balances and replicated diagnostics. `ThermalSession` reads actual native electrical
output before changing topology or granting the next interval. Fuel input is
`electrical output / conversion`: 80% in Brayton, 10% in standalone Aether.
Brayton's gameplay cooling load equals delivered electricity. It is accounted
separately from fuel credit; the two budgets are not a thermodynamic energy split.
Standalone retains its automatic integrated cooling of unused input energy.

Native grants reserve at most one simulation interval of paid source energy.
Fuel is debited before a grant is exposed; unused credit remains saved in source
`Store.HotMJ`. This small reserve is bookkeeping, not simulated coolant or a warmup
requirement. It cannot multiply output or disappear on a reload. Removing fuel
cannot make an already issued grant unpaid. Initial reservation can debit a small
fraction of fuel even at zero demand; subsequent idle ticks consume no more.

Each circuit owns `ExcessMJ`. Connected coolers subtract their available capacity
from that circuit's waste; surplus cooling cannot drain another circuit. New
operation stores no heat on pipes, turbines or coolers. `LoopVersion=2` preserves
legacy source heat across the four circuits and folds old machinery heat into its
circuit exactly once when it reconnects. Unattached old radiator inventories can
still radiate locally. Invalid saves remain isolated and copies cannot inherit heat.

The reactor supplies CO2 automatically. There is no filling, pressure, circulation
multiplier or turbine pump-startup consumer. Existing containment charging remains.
Net conversion efficiency already includes running auxiliaries; active coolers
require the reactor's existing containment supply/reserve, including during cooldown.
Space radiators remain passive. Retired wire tags stay reserved.

[Power balance](THERMAL-POWER.md) owns efficiency tiers and fixed quarter-capacity
allocations. Server validation still requires one turbine and cooling per sealed
circuit; cross-connected manifolds, extra turbines and open mouths cannot operate.
The existing critical-core latch, fuse, vent, tile and containment paths remain.

Circuit validity follows assembly changes, including while the reactor is off.
Adding or removing thermal blocks invalidates cached circuit graphs on that grid.
Snapshots also detect changed health, access, grid membership, placement, H/C roll
and manifold availability before dispatch; unchanged graphs reuse their results.
Starting the reactor does not rebuild an unchanged graph. An explicit native On
action while Off queues one safety decision using those current circuit results,
before containment charging, tile debit or deployment.
`LoopTrip` latches only if that manual startup finds all four circuits defective;
one valid sealed circuit is sufficient.
Losing all valid circuits while running stops generation without setting this
startup latch. Normal shutdown and cooldown never set it. Restoring a saved
diagnostic clears the old latch without re-enabling the reactor. Repaired circuits can
resume powered cooldown while off; a rejected startup requires another manual On.
There is no automatic switch to standalone. Cooling capacity follows the installed
equipment, sunlight, density, clearance and availability, independently of load.
Actual rejection is limited by heat present. Cooling shortfalls accumulate per
circuit and drive the existing 125% irreversible critical latch. The hottest
circuit determines the warning contribution; three cold circuits cannot hide it.
After each completed accounting interval the server samples paid production into
a four-second rolling window. Four times per second, and immediately on changes
to cooling capacity, connectivity or operation, it projects retained heat against
current cooling capacity for 60 seconds. The forecast applies the live core
response in 0.1-second steps without changing physical stores; inventories stop at
zero and housing production excludes loop totals. Shutdown stops projected new
heat immediately and shares the existing passive cooldown budget across stores.
Motion snapshots carry the peak, limiting circuit, danger ETAs and warning state.
Yellow requires a projected rise above both current heat and the healthy 100%
limit, with a 0.1-percentage-point rounding margin, sustained for two seconds.
Failed containment and predicted critical heat warn immediately. Five safe seconds
clear the warning; displays identify this recovery hold. Stable or cooling residual
heat and normal warmup do not initiate it. Critical/ejection red retains priority.
No cooling-based output throttle makes an undersized plant silently safe.
Shutdown stops new reaction heat, retains excess, and permits connected cooling;
the small passive housing rejection also drains isolated heat and unused fuel
credit. Current-load waste and full-load cooling requirements are displayed separately.

All four train variants have six turbine rotor rows (64 blades each), alternating
with six fixed 68-vane rows. The independent compressor has fourteen 56-blade rotor
rows and fifteen fixed 60-vane rows, including eight of each in its glazed
expanding casing. Tapered drums carry the roots within hollow inspection casings;
static vane rows stay outside the rotating subparts. The generator joins the
turbine through a short, steep taper. Its turbine-driven armature has 24 laminated
teeth and 960 rounded copper turns in four layers per tooth. Twenty-seven fixed,
filleted shiny magnets line the casing, with one-degree circumferential gaps and
extended end tiles beside the inspection opening and a continuous uppermost
magnet bar. The generator body is 2.24 m long, with its window, armature and magnets
lengthened by 12% and its rear cradle relocated to match. The 1.77 m window keeps
80% of its former height; the opposite wall is opaque to close the upward sightline.
The rear casing joins a cabinet reduced by 30% on each axis, seated directly on
the chamfered foundation. A half-round coupling cover encloses the shaft at the
cabinet roof. The electrical cable uses 0.24 m rounded bends and a fitted cabinet
gland, with clearance above the deck. Four flared turbine/generator struts carry
round cable sockets on both faces; the turbine struts fully enclose the coolant
pipe in machined liners. Two low compressor saddles stay beneath the drum,
clear of the manifold plate and pipes. The clipped,
sloping foundation extends continuously to the block bottom, replacing the
underside rails, and retains its recessed deck inserts.
Standard trains retain dark casings; upgraded trains use white outer casings,
fitted crown jackets and lower cooling fins. Standard identification plates read
EX / 1200 B; upgraded plates retain EX / 2200 C. Rear electrical access doors,
paired cooling grilles, curved casing inspection covers, a bearing access cover
and reverse manifold stiffeners complete both hands. Mirrored trains reflect this arrangement.
The 16 public pipe variants and machine fluid headers reuse the
reactor's registered `ArcanePower_ClearChamber` glass, retaining metal interfaces,
clamps and supporting frames. The production texture stage reapplies
`assets/refine_thermal_visibility.py` on rebuild. The reactor housing/manifold
rig is preserved. Each train has one lower-cell socket, on the opposite side for
mirrored variants. H enters the compressor front, its expanding casing joins directly to the turbine front, and C leaves the turbine rear. Close side
runs, relieved supports and fitted nozzles keep the pressure paths clear.
The shared glass finish is owned by `assets/tune_chamber_glass.py`. Uniform zero
CA textures remove dirt patches; the native shader therefore takes body opacity
from `ColorAdd.W`, not `Color.W`. Chamber, external pipe and internal coolant
materials use smoked blue-grey bodies with restrained reflections. Native mesh
checks confirm the straight-pipe walls are glass on both sides. This finish pass
preserves geometry, UVs, assignments, sockets, collision and internal plumbing;
its Blender preview remains an approximation of SE's lighting. Reload the world
to review the native appearance after material-definition changes.



`ThermalRotors` drives both cosmetic shafts linearly from delivered output divided
by the circuit's allocated electrical rating. Temperature colour follows the same
load and the fuel tier. No stored-heat or circulation multiplier controls speed.
Healthy enabled turbines idle at 5 RPM. Both shafts target
`5 + 95 × utilization` RPM, reaching 100 RPM at full utilization.
With no load, both shafts ramp from rest to idle over five seconds (1 RPM per
second). Load present at startup or arriving during that ramp immediately uses
the existing four-second response toward its load-dependent target; it never waits
to reach idle first. Disabled, damaged or faulted turbines coast to rest with the
existing eight-second response; an unloaded restart below idle resumes the gentle
ramp from the current speed. Valid saved speeds from the former 4,000 RPM range
are clamped to 100 RPM on reload, preserving shaft pose and stored heat.
Shaft motion does not alter energy accounting.
The displayed block name is **Arcane Turbine**; subtype IDs remain unchanged for
existing grids. Dense blades can appear to strobe at these speeds as frames sample
the actual shaft angle.

Standard turbines retain copper armature windings; upgraded turbines use cyan
metallic windings with the same packed metalness/gloss and no armor-skin mask.
All four variants have 21 recessed status lights on the inspection rails and rear
switchgear hatch. They use the existing circuit-status emissive, including fault,
ready and pumping states. The visible finish is maintained by
`assets/refine_train_service_details.py:finish`, also called during regeneration.
The finish was inspected in live Blender at 1.8, 2.4 and 3.0 m, with the armature
exposed temporarily to check the winding material; the production glazing and
magnet geometry are preserved.

The server saves phase/inertia with the train's entity-bound visual state.
Reload preserves the pose but clears drive until validated power delivery resumes. A secure
read-only channel supplies initial and twice-per-second rotor snapshots. Clients
integrate between snapshots and use bounded corrections around the shortest
angular arc; incoming client drive/state is rejected. Old saves without rotor
state remain valid. Blender's explicit `preview_angle_degrees` controls and
optional replay of compiled C# samples are inspection aids, not exported actions.

The command and snapshot channels are distinct: reactor commands use 49371,
ejected-core snapshots 49372, flow 49373, battery commands 49374 and train/radiator motion
49375. The compiled runtime checks reject duplicate channels and verify game
logic registrations for all 52 thermal subtypes. Delivery checks compare every
runtime script and definition with the actual ZIP and its hashed manifest.

Visible circulation follows each validated circuit graph and dispatched machinery.
Internal reactor coolant and external CO2 show broad, luminous moving streaks.
Supply is amber through orange with increasing heat; return is cyan. The pipe
streak material is independent of scene lighting so circulation stays readable
through the smoked glass in dark machinery rooms. Streaks are spaced 0.50 m
apart, each spanning up to 0.30 m of its path with one continuous texture.
Curved paths retain the same glob size without restarting the texture at every
authored vertex. Bore-clearance checks cover the full streak width on all shipped
paths. Each streak counts once against the shared billboard budget; chamber injector
wisps retain their softer treatment. H travels toward the
dispatched train/cooler branches and C returns through its paired bore.
Capped spurs and unavailable circuits stay still. The historical 40-block starter
and 106-block room fixtures retain the old shared routing as migration/geometry
checks. They are rejected for operation until replumbed into independent circuits.
Current checks use independent circuits in all 24 grid orientations.

The chamber's distributor rings, pump heads, injector pipes, mouths and clamps
have been removed. Four recessed floor vents replace them. Each metal cover
hinges down into its own well as Brayton mode deploys, then closes during
retraction. They share the existing powered mode transition, saved deployment
state and native rig checks; no separate animation state is required. Fixed
grilles and the accepted floor collider preserve walkability.

The eight pillar coolant risers, their metal jackets, clamps and guard rails
retain their geometry, UVs and material assignments. Their streaks still work
in standalone mode. Floor-vent wisps require settled Brayton mode; external
wisps follow verified Brayton routes. Speed follows load, with slow cosmetic
flow during cooldown. These effects never determine cooling or output.

`build_reactor_chamber_vents.py` owns the floor openings and covers;
`refine_thermal_flow.py` records the remaining paths. The native export checks
sample all four new covers under the compiled runtime matrices. Exterior pillar
receivers also use full recesses, with deeper vent backing to clear their louvers.

Floor vents now use a continuous rebated rim with 6 mm cover overlap and 2 mm
vertical clearance. The existing lid dimensions and hinge stay unchanged, so the
covers seal the visible aperture and still swing clear into their wells. Pillar
side inspection frames have full jacket recesses with a 10 mm perimeter reveal.
Their ledges and middle seats now sit 10 mm behind the cover backs, clearing the
complete sidewall as well as the upper/lower edges and middle joint.
The maintained builders reproduce both fixes. The geometry audit checks 572
closed-aperture rays, 101 travel positions per vent, and all eight pillar side
receivers. Live material views were inspected at 1.8, 2.4 and 3.0 m, including
closed/open vents and upper/lower/middle pillar joints. After native packing, the
main and both LODs passed 1,716 closure rays, 564 cover/fixed-mesh collision checks
using the compiled runtime poses, and 192 pillar surface-clearance checks.
The vent repair passed native import and the existing 1,918 native motion checks.

The eight obsolete pillar end yokes and their dependent fasteners are replaced
by sixteen annular sockets fitted to the original eight coolant risers. The
risers, their UVs and clamps remain unchanged. The socket flanges seat in the
existing feet and roof supports; their bores remain open and exact in both LODs.
All four pillars' upper/lower sockets, side covers and number plates were reviewed
in the live material viewport at 1.8, 2.4 and 3.0 m.

Four buried `SEUT / Tech Panel` decals caused the white control-panel pattern to
show over the numbered covers as viewing distance changed. Those legacy decals
are removed; pillar paint is unchanged. The four original number glyphs and their
backing plates are retained in both LODs rather than being culled with small
hardware and atlas decals. `fit_pillar_labels()` and the shared LOD builder own
this behavior. The packed main and both LODs retain all eight number/stock parts
(400 checked face corners per mesh, maximum position error 2.14 mm); all four
glyphs retain their atlas UVs. No legacy tech-panel triangles remain over the
numbered covers.

The original collision contained the base, roof and glazing but no pillars.
Thermal main and construction models now add four hulls fitted to the pillar
jackets, while retaining the original ten housing hulls. A single top-level Havok
list holds all fourteen convex children to avoid SE's ten-top-level-shape limit.
Native Havok validation checks 1,664 base/deck/roof contacts, 64 pillar-face
contacts, eight blocked character-sized capsule sweeps and four clear walkway
sweeps. The original housing-only HKT remains an unchanged rebuild input; see
[`assets/collisions/README.md`](assets/collisions/README.md). In-game reload review
is pending. Local revision `thermal_7765322cc0b9` contains all 42 rebuilt reactor
meshes, passes 1,918 native motion checks and the delivered-HKT contact/sweep
checks above, and is included in the validated 662-entry release ZIP.

Each blast shield's lower metal seal is joined to its sleeve as one closed shell.
This removes the coincident 45 mm inner strip while preserving bore diameter,
outer envelope, pivots and travel. All six inner joints were reviewed in the live
material viewport at 1.8, 2.4 and 3.0 m; both distance meshes derive from the repair.

`ThermalHot`, `ThermalCold` and `ThermalStatus` are independent native-derived
emissive materials. Hot bands respond to source heat, returns stay blue, and
status lamps show pumping green and connected idle amber. Pipe blocks use solid
red at half indicator brightness (0.325 emission) on both H/C connector rings and any status lamps
when disconnected or part of an invalid circuit. Bare pipes use their existing
rings; manifold pipes also have status lamps. A valid idle circuit
does not show a fault. Stale observations extinguish emission rather than
inventing a connection fault. Other unconnected equipment remains dim, and
reactor socket indicators retract with their pipe carriages.
Each validated circuit restores its own members' normal colours, including
capped spurs and redundant paths with no animated flow. Incomplete circuits
remain red independently. A single complete circuit can start at 25% capacity.
The server sends validated read-only flow observations twice per second on
channel 49373; clients stop stale flow after 90 frames. Rendering uses native
depth-tested billboards, an 80 m cutoff and a shared 768-particle limit.
Gas and liquid billboards are self-lit, with a 1.5× RGB brightness boost that
preserves their existing opacity and endpoint fades.
No fluid inventory, pressure authority or electrical grant is created by drawing.

`assets/refine_thermal_flow.py` maintains the fixtures and shared centreline
contract. `tools/build_thermal_runtime_contract.py` generates native coordinates.
`assets/preview_thermal_flow.py::install()` creates isolated Blender review meshes
from those paths and compiled route-selection evidence; rerun it after reopening
to enable viewport playback. These preview meshes are outside all native main
collections. The native MWMs and definitions are delivered. Game appearance still
requires an in-game check; Blender previews do not establish that result.

Mode selection uses the existing authenticated reactor command channel. It stops
fresh heat admission, shuts down, drains housing/attached inventories, then moves
the panels and telescopes under the existing containment power/reserve policy.
Restart is manual. Broken Brayton routing cuts conversion without awarding an
additional standalone electrical path. A small passive housing rejection path
remains available for trapped heat; it produces no electricity.

Dispatch checks one turbine, compatible fuel temperature and attached cooling.
There is no cold-end temperature search or auxiliary-efficiency curve. Fuel ratings
are 5/50/250 GW. Standard turbines accept up to 4.375 GW input and export 3.5 GW;
upgraded turbines accept 62.5 GW and export 50 GW. Every Brayton circuit converts
80%, needs cooling equal to its actual output, and never transfers spare capacity
to another circuit. Full plants provide 4 GW Aether, 14 GW T1 Helion, 40 GW T2 Helion
or 200 GW Empyrean. Capacity-limited operation throttles fuel use automatically.
Generated model contracts own equipment ratings; native caps match them.
Retired duplicate circuit input/reaction/cooling telemetry and standby counts leave
their ProtoBuf tags reserved. Circuit cooling load derives from delivered output;
maximum cooling demand is already the circuit's maximum electrical output.
Pre-rebalance saved heat remains valid and retained; new admission and dispatch
use the rebalanced ratings.
Fuel is debited into the one-interval native output reserve; stock and saved
fractional debt bound the final quantum. Displayed burn follows actual reaction
heat, while unused paid credit remains saved until used or drained at shutdown.

Prototype boundaries:

- One reactor supplies four independent duplex circuits. Ordinary sockets mate only
  on the same physical grid; the Arcane pipe rotor is the explicit exception.
  Each has one turbine and its own cooling; shared reactor supplies are rejected.
- Socket positions, facing and hot/return roll come from all 59 runtime model
  contracts, including the 170 mm adapter. Unused ports require caps. Failed/off
  machines and missing pipes invalidate their circuit, closing its reactor valve.
  The adapter's authored `reactor_transition` port generates a `ReactorOnly`
  runtime role, preserved through placement transforms. Its peer must be the
  reactor vessel, enforced by the shared matcher and construction guide.
  `ThermalLoops.OpenValves` opens each validated complete circuit on fully
  deployed Brayton manifolds, including cold/off circuits. Fuel-backed grants
  and actual delivered power govern output separately.
  Construction inspection stops at unselected vessels, so another circuit's
  mismatched sockets do not contaminate a healthy selected circuit's report.
- Pipes define connectivity only. Excess heat resides in the owning reactor's
  per-circuit balances; per-pipe fluid mass, pressure and transit delay are not
  simulated. The normalized core hazard follows the hottest circuit's balance.
- Atmospheric density is sampled from the local planet. Ambient temperature is
  currently the 25°C reference. Native `MyPlanet.GetAirDensity` returns zero
  outside its atmospheric altitude, including non-atmospheric planets; finding
  a nearby planet alone does not apply an atmosphere penalty. Atmospheric coolers
  are rated at 5 GW (T1) or 50 GW (T2) and sample 18 authored exhaust
  positions (nine per fan) once per 60 simulation ticks, transformed by the
  block's world matrix. Each checks 2.5 m forward from beyond the guard hardware.
  Same-grid block occupancy catches armor enclosing the ray origin; forward and
  reverse physics rays also check other grids and physical obstacles. Available
  capacity is `rating × clamp(density) × clamp(clear fraction)²`, with both clamps
  bounded to 0–1. Fully blocked exhaust yields zero cooling and lets waste accumulate;
  clearing it restores capacity at the next sample. Terminal diagnostics expose
  clearance and available MW. The server owns heat rejection; client terminal
  inspection only samples local conditions. These discrete rays are an obstruction
  approximation, not an airflow simulation; in-game physics remains to be verified.
  Radiators sample eight exposure rays over 250 m. Their ambient cooling factor
  blends vacuum and reference-atmosphere rejection in proportion to clamped
  native density; the old `density > 0.001` full-atmosphere switch is removed.
  Zero density retains 100%; full density retains 12.36%. Their own terminal
  reports measured air density and the same ambient factor used by the simulation.
  Solar exposure follows the native two-sided solar formula: absolute normal/sun dot
  product × fraction of lit pivots × solar weather multiplier, bounded to 0–1.
  Cooling multiplies the result by `1 - 0.5 × solar exposure`: 100% in shade or
  edge-on, 50% at full sun on either face. The server samples 32 points on each
  moving panel with the vanilla 100 m/layer-15 ray rules, own-block exclusion,
  near-surface night check and 20-radius planetary shadows (500 m/90% terrain
  margin). All pivots refresh in the existing once-per-second environment pass,
  rather than vanilla’s staggered one-pivot updates. Partial shade resolves in
  3.125% steps, limiting each sample's cooling effect to 1.5625 percentage points
  at face-on incidence with the normal weather multiplier; the angle response
  remains continuous. Base and extensions sample
  independently. Automatic tracking still targets edge-on. Clear-sky obstruction
  and sink temperature are separate limits. Material-temperature dynamics remain
  outside this gameplay model.
- Per-block inventories stay on the server. Reactor motion snapshots carry
  mode, deployment and plant totals; train snapshots carry rotor state. Native multiplayer power
  behavior, physics, splits/merges and the complete coordinator need world tests.

Radiator sections use `Thermal_RadiatorPanels` root subparts. The base pivots at
native `(0,-1.1,0)`; the extension pivots at zero. `ThermalRadiators.Pose` supplies
the native rotation. Server attachment checks accept at most three consecutive,
present, accessible, upright extensions on the same grid. Only functional enabled
panels contribute cooling. Placed yaw is unrestricted;
`ThermalRadiators.PanelAngle` compensates block yaw in server/client motion and
solar/clearance sampling, keeping each H/C coupling in the base world frame.
Radiator collision includes the axial top dock for placement; adjoining stack
colliders are recessed 25 mm per face to clear their convex margins. Six solid-derived
face/frame hulls belong to each rotating subpart. Native kinematic model physics
follows its pose on clients and dedicated servers; native tool rays resolve those
hits to the owning grid section for grinding. Model refresh/removal closes the
subpart physics. Export checks cover both faces and unobstructed outward cooling
rays. The base owns
the only heat store and cooling budget. Extensions contribute sampled cooling
without duplicating MJ. Their client visuals use the base's interpolated angle
so side-pipe joints stay together between snapshots. Motion state is entity-bound,
validated and replicated read-only; startup behavior remains server-owned.

The prior glass pass changed the protected Energy Core blend's material settings.
Before recording that accepted source hash, all 15,284 mesh instances were compared
with the previous protected file: geometry, UVs, material assignments and world
transforms were identical.

## Native authoring contract

1. Export the reactor housing and all four train variants as native reactor blocks
   with empty `FuelInfos`; use the existing 10,000 MW base definition rating for
   the housing. Export other thermal blocks as functional upgrade-module blocks.
   Use the exact generated subtypes and SE cell dimensions in `ThermalModels.cs`.
2. Export five **root** subparts per bay, named
   `Thermal_{LA|LB|RA|RB}_{Carriage|Intermediate|CoverMinus|CoverPlus|ConnectorTail}`.
   Bake their meshes in reactor-local **stowed** coordinates with identity root
   dummies. The rounded casting and moving connector belong to `Carriage`;
   `ConnectorTail` scales independently about its fixed guide anchor. Preserve
   original reactor subparts and accepted collision geometry.
3. Use `assets/thermal-manifold-runtime.json` for the exact revision-4 panel
   angles/source groups. The runtime reproduces the authored inset/slide/extension
   phases and refuses Brayton deployment if the required native rig is absent.
   The eight armor leaves now close against backed outer seams. Concealed pocket
   relief clears the wider leaves throughout all 47 sampled poses; the existing
   inset/slide/extension transforms are unchanged.
   `fit_roof_surfaces()` in `assets/refine_reactor_exterior.py` clears all sixteen
   roof receiver frames and seats their screw decals above the metal. The central
   cap opening is R2.05 m around the R2.04 m hatch seat: a 10 mm seam backed by the
   housing, with no cap/seat surface intersections. Live views were checked at
   1.8, 2.4 and 3.0 m, including grazing angles.
   The inner ceiling hatch parks 99 mm higher, with its underside at Z2.460 m.
   Its lift is now 0.221 m, preserving the previous fully-open endpoint and slides.
   The seat and concealed backing pocket follow `assets/vent.json`; a 41-pose
   geometry sweep clears the ceiling and deployed blast shields. The compiled
   runtime/native mesh check passed 164 ceiling poses, with a 2.459998 m closed
   underside and less than 0.000001 m change to the fully-open endpoint. Export the main,
   moving parts, all three construction stages and LODs together after these edits.
4. All four train variants need two root subparts, `Thermal_TurbineRotor` and
   `Thermal_CompressorRotor`. Use `assets/thermal-rotor-runtime.json` for the
   Blender pivots. The compact train's generated native pivots are `(-1.0, -.10, 0)`
   and `(4.4, -.10, 0)`, with identity-oriented dummies. Bake rotor meshes in their
   **shaft-local** coordinates, excluding them from the static main. This differs
   from the reactor's identity-root, stowed-space manifold contract. The native
   rotation axis is -X. Preserve the existing clear-glass material ID and its
   `Data/TransparentMaterials.sbc` definition.
   All four train definitions use native `(5,2,2)` cells: length is native X, giving
   the requested 2-wide × 2-high × 5-long footprint. The single native socket is
   `(5,-1.25,-2.5)` or `(5,-1.25,2.5)` for the mirrored variant. Reroute
   existing trains to the lower socket and cap/remove abandoned branches.
5. Complete native collision, construction/LOD and asset-dependency gates before
   installing definitions. Validate the isolated prototype in SE before migrating
   existing reactors or publishing.

6. Reactor shut-offs use `assets/arcane-thermal-isolation.blend` and
   `assets/build_thermal_isolation.py`. Build/export in the live thermal authoring
   scene, then run `tools/prepare_thermal_isolation.py --compile`; omit `--compile`
   to validate installed meshes. The authored contract retains 48 samples: four
   reactor ports, both bores, a seat and five gate poses. The probe requires every
   unique combination and checks native UVs, textures and pivots. It also checks
   the exported vertices every 5 degrees through 90 degrees of travel: 160 bore
   clearance checks across all eight valves.
   The 411 mm disc, 454 mm seat and reduced spindle/bearings fit the reactor's
   460 mm, 40-sided stem ID, with at least 1.42 mm wall clearance after native
   vertex packing. Live Blender review covered front, side and chamber-facing
   views at 1.8, 2.4 and 3.0 m, plus nine opening poses. Native checks pass;
   in-game visual review remains pending.
   Pipe and machine mouths have no runtime valve subparts.

Verification from the repository root:

```sh
python3 ArcanePower/tools/build_thermal_runtime_contract.py --check
python3 ArcanePower/tools/check_thermal_runtime.py
python3 ArcanePower/tools/compile_mod.py
dotnet build arcane-systems.sln
```

The focused checks execute the compiled production kernel with native math. They
cover budgets, fixed four-circuit capacity, per-loop equipment limits, isolated losses, conservation
scenarios at 10% standalone and 80% Brayton, cooling overload/recovery and the 125% heat threshold,
linear load response, per-circuit cooling isolation, fuel exhaustion,
reload/copy identity, mode/startup guards,
47 manifold poses, linear rotor response, cold startup without pump power,
coastdown, native shaft transforms, frame-size-independent phase integration,
and the captured authored starter layout, including
facing/roll faults and grid separation. They do not execute the coordinator in
a live SE world or establish native collision/animation compatibility.

### Runtime faults and cooling continuity

A generation/runtime fault disables the reactor and explicitly enters its normal
shutdown/cooldown sequence. It does not disconnect sealed circuits or close their
valves. Electrical output accounting faults latch generation at the source;
physical faults or invalid machinery inventories still isolate the affected circuit.
A complete circuit continues rejecting retained heat with the available auxiliary
supply (or passively for radiators). Generation requires revalidation and a manual
restart. Potential environmental cooling is measured independently of auxiliary
power, while actual heat rejection never uses an unpowered active cooler.

Native generation uses float Capacity/CurrentOutput. Settlement permits the float
roundtrip within the existing 1 ppm output headroom, while still requiring every
MJ to fit both the reserved allocation and remaining paid fuel inventory. This
prevents false isolation at GW output without granting unpaid electricity.
Outstanding reservations survive a runtime exception long enough to settle the
last native interval; stopping output must not discard their accounting evidence.


## Sealed pipe rotor

The new `Pipe rotor` and `Pipe rotor head` in `arcane-thermal-models.blend` use
`MotorAdvancedStator` and `MotorAdvancedRotor`. Native SE owns head creation,
attachment, torque/limits, locking, detachment, replication and item conveyors.
The base and head each occupy 1×1×1 large-grid cells; the base's sealed pressure
bulkhead closes the hull even when detached. Both definitions are
airtight. Oxygen rooms remain separate across subgrids. Ordinary thermal pipe
blocks still do not carry inventory items.

The radiator/“solar” tracking base remains a separate UpgradeModule with animated
model subparts, up to three same-grid radiator panels, no physical rotor head and
no new subgrid. Native motor head creation always creates another cube grid, so
one interchangeable native base cannot also preserve that behavior. Both bases
reuse `build_pipe_rotor.py::side_shell`; existing radiator IDs are preserved.

`ThermalPipeJoint` accepts only the reciprocal, nonpending native attachment
between the two exact Arcane pipe rotor subtypes. Both blocks must be complete,
functional and accessible to the source owner, on distinct physical grids.
Switching the motor off stops rotation without opening the sealed pipe. A missing,
foreign, damaged or inaccessible head breaks that circuit; there is no proximity
or general mechanical-group heat transfer. Attachment/build revisions invalidate
cached circuits. Ordinary sockets still use grid-local positions and H/C axes.
The construction guide, coolant flow display and circuit accounting follow the
explicit rotary connection. A detached union does not stop unrelated circuits.

The rotating cuff belongs to the native head. Native displacement spans −0.10 to
+0.10 m, giving a 10–30 cm casing gap and a 20 cm gap at zero. The deep sealed
bearing well retains at least 295 mm of cuff engagement, 70 mm of bottom clearance
and 19.5 mm of radial clearance throughout travel. The six casing collision inputs
and their existing Havok margin inset are preserved; the cuff remains noncolliding.

`MyMotorStator.SetConstraintPosition` and `AlignGridsForAttach` constrain the head's
block origin to the stator's displaced `electric_motor`, not to the head's `wheel`
dummy. The stator dummy is therefore at 2.70 m, the head dummy and its initial
placement offset are zero, and `RotorDisplacementInModel` is zero. This corrects the
earlier source-only dummy/placement assumption. The maximum position still overlaps
the native large-grid head query box after the casing collider inset.

Pipe-rotor armor uses butt joints instead of coincident exterior strips. Recessed
H/C lamps, machined service latches, bearing retainer bolts and segmented cyan cuff
inlays use existing native/thermal materials and the existing runtime emissive
controls. The radiator base now shares the recessed H/C side lamps and service
latches. Its 2.30 m square bearing deck fits inside the side walls, 100 mm below
their rim, with raised bolts and a 5 mm radial bearing clearance backed by a
pressure seal. The six casing solids meet without overlapping exterior strips.
No new textures or runtime animation controller are needed.
The head's square body sweeps outside its stationary footprint; keep that area
clear of other blocks. Native models and collision are built by the existing SEUT/MWM pipeline.
Motion/attachment behavior in a running Space Engineers world still needs validation.

Source validation for the cuff: 15 tests of the production native attachment
adapter; prospective definition/displacement checks; 174 closed solids, 7,500 hull
samples and 216 actual-mesh poses over full rotation at minimum/default/maximum
displacement. Both the solution and SE compatibility/whitelist builds passed with
zero warnings/errors. Live Blender
5.2.1, official MCP, reviewed covers, corners, sockets, deck and underside at
1.8/2.4/3.0 m using the same 48 mm lens and studio light, plus the assembled
bearing from opposite sides and a 1.9 m scale figure. The cuff pass inspected 24
settled live views covering both assembled sides, the two travel limits, the open
base seat, the head underside and the two service-cover orientations. The 0.3.0 preflight reconciled the old prototype fingerprint against its saved
hatch checkpoint: 2,577 existing objects unchanged, with exactly six authorized
seal additions. The full thermal geometry audit passes.

Checkpoints: `assets/arcane-thermal-before-pipe-rotor.blend` and
`assets/arcane-thermal-before-rotor-cuff.blend`. Rebuild with
`assets/build_pipe_rotor.py::build`, validate with its `audit()` and
`tools/check_pipe_rotor.py`; `review_travel()` shows the three casing gaps in the
live UI without saving its temporary scene into production. Rotor weld frames
stay within their casing instead of extending a full-width cage along the cuff.
Bearing surfaces and the cuff retain their exact radial profiles in both LODs.

References: [Advanced Rotor](https://spaceengineers.wiki.gg/wiki/Advanced_Rotor),
[Advanced Rotor Part](https://spaceengineers.wiki.gg/wiki/Advanced_Rotor_Part),
and [Keen's visual rotor comparison](https://support.keenswh.com/spaceengineers/pc/topic/25699-rotor-not-passing-ore-log-block-no-mods-dedicated-server).
Native `MyMechanicalConnectionBlockBase.CreateTopPart` creates a new CubeGrid;
`MyMotorAdvancedStator.Attach` links conveyors only to the native advanced head.

## Hull radiator

`Hull radiator` is a fixed **1 deep × 2 high × 3 wide** large-grid block
(native size 3×2×1). Its 7.5×2.5×5 m envelope has full airtight backing and a
flush front frame. The 36 graphite tiles, substrates, edge pipes and retention
hardware reuse one face of the existing radiator panel, preserving its UVs.
There are no tracking subparts or new grids. Standard/upgraded cooling is
1/10 GW, half the two-sided panel rating. Neither recipe uses Solar Cells.

Four midpoint edge unions join only other hull radiator edges, with H toward
the exterior. A standard H/C socket occupies the lower rear cell. All five
sockets start closed when unused, so one rear connection can feed a contiguous
array. Matching peers still need valid H/C roll, access and grid identity;
incompatible or crowded peers fault the loop. Failed radiators retain their
physical connection with zero heat rejection. Hull sockets self-seal whenever
their peer disappears; remaining connected radiators retain flow with lower
total cooling. Ordinary feed pipes exposed by removal still breach the circuit.
The existing circuit
rules forbid sharing an array between reactor manifolds. Ordinary pipe mouths
retain their cap requirement. Closed unions carry no flow and are excluded
from construction fault markers.

Cooling uses 32 samples outside the fixed front plane, same-grid occupancy and
forward/reverse physics rays. Backing and armor behind the radiator do not
obstruct the front. Only front-facing sunlight heats the panel; planet shadow,
weather and atmospheric losses use the existing radiator calculation. The
native terminal reports fixed-face capacity and clearance without tracking or
panel-stack controls. Heat glow applies to the main model.

Source validation: 1,407,492 compiled thermal checks, 55 cooling/telemetry checks,
and 43,657 checks of the production fixed-face sampler across all 24 block
orientations. Prospective definitions pass dimensions, airtightness and recipe
checks without modifying the installed catalog. The source geometry has 141
closed solids, 3,750 sealed hull samples, 36 front tiles and five sockets. The
general audit passes, including the reconciled prototype preservation baseline.
The required solution build passes with five existing NexusAPI field warnings;
the SE compatibility/whitelist build passes with zero warnings and errors.

Live Blender 5.2.1/official MCP review covered tiles, fasteners, corners, side/top
unions, rear feed, horizontal/vertical array seams and rear backing at
1.8/2.4/3.0 m, with a fixed target, 48 mm lens and studio light per set. An
assembled array beside armor and a 1.9 m figure confirms scale and flush fit.
The production file excludes the temporary array review scene.

Source: `assets/arcane-thermal-models.blend`; checkpoint:
`assets/arcane-thermal-before-hull-radiator.blend`. Reproduce with
`assets/build_hull_radiator.py::build`, inspect with `review()`, and check with
`audit()` and `tools/check_hull_radiator.py` after the solution build.
The standard export generates the hull backing/frame collision, two LODs and
three construction stages; upgraded variants reuse that geometry. Native and
package checks cover the installed catalog. No live game check is claimed.

## Cooling failure versus pressure loss

`ThermalBlock.CircuitReady` separates physical cooling connections from
`HardwareReady`/`Healthy`, which still govern heat rejection. A damaged,
unfinished or switched-off cooling block remains sealed while present on a
physical grid. Owner access and exact socket placement remain required.
Ordinary pipe, turbine and native rotary-union damage rules are unchanged.
Invalid saved heat and electrical-accounting faults retain their safety gates.

Stack linking also uses physical presence: a failed middle panel remains in the
stack, healthy panels above it still contribute, and only healthy panels add
cooling capacity. A disabled or failed base rejects no heat. Zero cooling does
not disconnect an otherwise sealed circuit or throttle its paid generation;
the existing waste-heat, forecast, critical-core and ejection logic applies.

`ThermalRadiatorState.RequiredPanels` records the installed tracking-stack height,
with a zero default for old saves. Removing a stacked panel leaves a breach until
it is replaced. This state survives reloads and reaches client construction
guides through existing radiator telemetry. Shortening a tracking stack requires
rebuilding its base to establish fresh connections.

Hull-radiator sockets self-seal after removal and carry no connection history.
Arrays can therefore shrink without rebuilding surviving radiators. Retired
wire tag 11 and the former XML `RequiredPorts` field are ignored on load; they
cannot preserve an obsolete hull-socket breach. A grid split excludes detached
radiators from cooling and seals the remaining hull edges. Mismatched, crowded
or inaccessible peers still fail validation while present.

`tools/check_cooling_integrity.py` executes the production eligibility, stack
linking and cooling methods against block-state fixtures, plus the real network,
dispatch, heat budget and valve mask. It covers failed/disabled/incomplete
coolers, removal, access, projections, repaired and missing stack panels, saved
connection history, client state and thermal runaway. These are offline checks;
a running game remains the final integration check.

Validation passes: 1,407,974 thermal runtime checks, 152,405 production
fuel/mode/dispatcher checks, 3,715 cooling-integrity checks and 56 cooling
terminal/telemetry checks. The solution and SE compatibility/whitelist builds
pass. Temporary test logs are pruned after recording these results.
