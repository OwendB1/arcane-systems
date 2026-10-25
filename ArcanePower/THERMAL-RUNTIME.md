# Thermal runtime — 25 October 2026

The sole playable reactor is `ArcanePower_Thermal_ReactorHousing`. The current
catalog has 27 public thermal blocks and 28 hidden pipe compatibility aliases. The old reactor prototype, heaters and recuperators are excluded from
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

The reactor owns its requested/settled mode, manifold deployment, housing heat,
pending fuel charge and replicated plant diagnostics. `ThermalSession` owns server
dispatch and reads actual native output before withdrawing the corresponding heat.
Each machine saves its own hot/waste MJ inventory with its entity ID. Copies and
projections cannot inherit heat; grid changes rebuild the physical socket graph.
Invalid stored inventories are isolated without overwriting their original records.
The existing critical-core latch, fuse, vent, tile and containment paths remain.

[Power balance](THERMAL-POWER.md) owns efficiency tiers and fixed quarter-capacity
allocations. Server topology validation requires one turbine and cooling per
sealed circuit; cross-connected manifolds, shared supplies, extra turbines and
open pipe mouths cannot operate. Reactor valves close unused outlets; pipe
junctions require physical caps.

`ThermalLoopState` records validated connectivity, capacity and cooling diagnostics
in the entity-bound reactor state. The reactor supplies CO2 automatically; complete
circuits become available immediately, with no fill timer or pressure gate. Repairs
and reloads revalidate topology without refilling. Cold turbines request metered
compressor electricity at 2% of dispatched thermal throughput; partial delivery
supports proportional circulation. Once hot inventory can support generation,
actual output supplies the running auxiliaries. Hot shutdowns still request external
circulation power. Electricity actually delivered to the compressor becomes waste
heat in its real block inventory. Retired loop-charge and rotor-pressure protobuf
tags stay reserved; older XML fields are ignored without changing saved MJ.
`LoopVersion` migrates older shared plants disabled while preserving all MJ,
fuel debt, containment and critical state.

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
There is no automatic switch to standalone. Running auxiliaries are paid once;
per-circuit fan cooling and transport use metered circulation. Shutdown requests
external power to drain the bank. Radiator surfaces can passively reject their
own stored heat.

Dispatch no longer caps reaction/output grants at the sustainable cooling limit.
Every paid conversion retains its waste, which returns to the reactor's bounded
inventory before transfer to connected coolers. Missing rejection raises core heat
and uses the existing 125% irreversible critical latch, fuse and ejection path.
Full inventories stop fresh fuel admission without deleting the thermal hazard;
ordinary unused hot reserve alone does not manufacture an overheat. Shutdown
retains waste and needs cooldown circulation; the housing's small passive
rejection is available only when the reaction is stopped. Saved/replicated
diagnostics include effective cooling and design-load rejection requirements.
Terminal, LCD and tablet share cooling-shortfall/overheat warning priority.

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



`ThermalRotors` drives cosmetic shaft motion from its circuit's actual circulation
and paid hot inventory. Temperature reflects source heat and available inventory.
Heat and circulation control turbine speed; the electric compressor can spool
during powered cold startup. No fill level or pressure estimate controls motion;
a per-pipe real-fluid or material-temperature solver is not simulated.
Loss of routing, heat, circulation or functional hardware removes drive. Shafts
accelerate over four seconds and coast over eight, without altering MJ accounting.
Visual speeds are capped at 20/24 rpm, keeping dense rows below 24 blade passes/s;
these are not engineering shaft-speed ratings.

The server saves phase/inertia with the train's entity-bound heat inventory.
Reload preserves the pose but clears drive until validated circulation resumes. A secure
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
Internal reactor coolant shows liquid streaks; external CO2 shows gas wisps. H travels toward the
dispatched train/cooler branches and C returns through its paired bore.
Capped spurs and unavailable circuits stay still. The historical 40-block starter
and 106-block room fixtures retain the old shared routing as migration/geometry
checks. They are rejected for operation until replumbed into independent circuits.
Current checks use independent circuits in all 24 grid orientations.

The thermal reactor also has glass coolant risers, two floor-level distributor
rings, four integrated pump heads, four guarded supply sight sections and four
warm pickups. Short cold wisps emerge from the upper chamber injector mouths.
Internal cooling can circulate in standalone mode with delivered containment
power/reserve and operating or retained heat. External circulation requires
verified Brayton routing and measured circulation support.

Internal coolant tubes use independent smoked blue-grey `ArcanePower_CoolantGlass`
sight sections, metal pressure-jacket backing and seated collars. Vertical risers
also have paired guard rails. Their visible apertures face out past the pillars;
the distributor apertures face the chamber. Native glass parameters and the
Blender preview are maintained together in `refine_thermal_flow.py`. Flow paths,
grid sockets and accepted reactor collision are preserved.

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

Dispatch selects an eligible tier and cold-end temperature within each circuit.
Standard trains handle 25 GWth; upgraded trains handle 2.5 TWth. Reactor fuel tiers
provide 25/250/2,500 GWth. Generated model contracts own equipment ratings.
Fuel is charged for newly admitted thermal MJ, including finite warm-up inventory;
stock and saved fractional debt bound the final fuel quantum.

Prototype boundaries:

- One reactor supplies four independent duplex circuits on a single physical grid.
  Each has one turbine and its own cooling; shared reactor supplies are rejected.
- Socket positions, facing and hot/return roll come from all 55 runtime model
  contracts, including the 170 mm adapter. Unused ports require caps. Failed/off
  machines and missing pipes invalidate their circuit, closing its reactor valve.
  The adapter's authored `reactor_transition` port generates a `ReactorOnly`
  runtime role, preserved through placement transforms. Its peer must be the
  reactor vessel, enforced by the shared matcher and construction guide.
  `ThermalLoops.OpenValves` opens each validated complete circuit on fully
  deployed Brayton manifolds, including cold/off circuits. Metered circulation
  and paid hot inventory govern transport/output separately.
  Construction inspection stops at unselected vessels, so another circuit's
  mismatched sockets do not contaminate a healthy selected circuit's report.
- Pipes are ideal links within one simulation step. MJ resides on real source
  and machine blocks; per-pipe fluid mass, pressure and transit delay are not
  simulated. The normalized core hazard is separate from this housing/loop ledger.
- Atmospheric density is sampled from the local planet. Ambient temperature is
  currently the 25°C reference. Atmospheric coolers sample 18 authored exhaust
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
  Radiators sample eight exposure rays over 250 m;
  sink temperature uses space/atmosphere reference values. Solar exposure follows the native two-sided solar formula: absolute normal/sun dot
  product × fraction of lit pivots × solar weather multiplier, bounded to 0–1.
  Cooling multiplies the result by `1 - 0.5 × solar exposure`: 100% in shade or
  edge-on, 50% at full sun on either face. The server samples eight points on each
  moving panel with the vanilla 100 m/layer-15 ray rules, own-block exclusion,
  near-surface night check and 20-radius planetary shadows (500 m/90% terrain
  margin). All pivots refresh in the existing once-per-second environment pass,
  rather than vanilla’s staggered one-pivot updates. Base and extensions sample
  independently. Automatic tracking still targets edge-on. Clear-sky obstruction
  and sink temperature are separate limits. Material-temperature dynamics remain
  outside this gameplay model.
- Per-block inventories stay on the server. Reactor motion snapshots carry
  mode, deployment and plant totals; train snapshots carry rotor state. Native multiplayer power
  behavior, physics, splits/merges and the complete coordinator need world tests.

Radiator sections use `Thermal_RadiatorPanels` root subparts. The base pivots at
native `(0,-1.1,0)`; the extension pivots at zero. `ThermalRadiators.Pose` supplies
the native rotation. Server attachment checks accept at most two consecutive,
healthy, accessible, upright extensions on the same grid. Placed yaw is unrestricted;
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
   unique combination and checks native UVs, textures, pivots and bore clearance.
   Pipe and machine mouths have no runtime valve subparts.

Verification from the repository root:

```sh
python3 ArcanePower/tools/build_thermal_runtime_contract.py --check
python3 ArcanePower/tools/check_thermal_runtime.py
python3 ArcanePower/tools/compile_mod.py
dotnet build arcane-systems.sln
```

The focused checks execute the compiled production kernel with native math. They
cover budgets, fixed four-circuit capacity, per-loop equipment limits, isolated losses, one-hour conservation
scenarios at 20/40/78%, cooling overload/recovery and the 125% heat threshold,
stable auxiliary circulation at all bank sizes and tiers, fuel exhaustion,
reload/copy identity, mode/startup guards,
47 manifold poses, heat/pressure rotor response, cold compressor startup,
coastdown, native shaft transforms, frame-size-independent phase integration,
and the captured authored starter layout, including
facing/roll faults and grid separation. They do not execute the coordinator in
a live SE world or establish native collision/animation compatibility.
