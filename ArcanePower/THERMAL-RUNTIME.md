# Thermal runtime — 17 October 2026

The first C# implementation targets the separate
`ArcanePower_Thermal_ReactorHousing` subtype and the 30 other authored thermal
models. Existing `ArcanePower_ReactorPrototype` definitions retain direct-electric
operation. All 31 thermal block definitions and native models are installed locally
and included in the unpublished 0.1.0 alpha ZIP. Their 93 construction stages,
122 LODs and 24 moving subparts pass native import checks. Live SE world validation
remains pending. [Delivery checks](validation/thermal-models/delivery-check.json).

Every thermal definition references a distinct 512 px DDS icon rendered from its
production main model. PRIMARY/HP/LP badges distinguish pipe circuits, adapter
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
three circuit routes, adapters, H/C roll, welding, cooling and powered startup.
The client construction guide follows SCF's placement-arrow/HUD pattern using
independent native texture IDs, without an SCF dependency. It shares socket
matching and coordinate transforms with server dispatch, considers all 24 grid
orientations, and inspects unfinished blocks separately from running health.
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

Standalone converts paid heat at 20%, using integrated rejection. Brayton exposes
the manifolds and supplies separate native generator trains: 40% starter net,
up to 78% with eligible source temperature, hardware and recovery. Running
auxiliaries are deducted internally once. Cold starting draws 2% of dispatched
design heat rating through a real heater-mounted electrical sink for eight
delivered seconds. This also pays for the reactor's integrated CO2 generation,
closed-loop filling and pressurization; there are no separate gas supply blocks
or consumable gas inventory. A changed bank or reload requires another paid start. Fan
cooling and transport depend on measured circulation support; shutdown requests
external power to drain the bank. Radiator surfaces can passively reject their
own stored heat.

Both train variants have six turbine rotor rows (64 blades each), alternating
with six fixed 68-vane rows. The independent compressor has six 56-blade rotor
rows and seven fixed 60-vane rows. Tapered drums carry the roots within hollow
inspection casings; static vane rows stay outside the rotating subparts. The 22 conduit variants and machine fluid headers reuse the
reactor's registered `ArcanePower_ClearChamber` glass, retaining metal interfaces,
clamps and supporting frames. The production texture stage reapplies
`assets/refine_thermal_visibility.py` on rebuild. The reactor housing/manifold
rig and the accepted external train side manifolds are unchanged. Internally,
HP H enters the turbine's front end plenum, crosses the alternating axial rows,
and leaves its rear plenum through LP H. LP C enters the compressor front;
HP C carries rear discharge toward the heater. Bored pressure walls and seated
nozzles replace the previous tubes ending in the middle of the chamber.


`ThermalRotors` drives cosmetic shaft motion from the selected bank's actual
circulation support and paid hot inventory. Its gameplay estimate approaches
8–22 MPa over two seconds; estimated inlet temperature combines the source tier
and available hot inventory. These are operating indicators, not a fluid-pressure
or material-temperature solver. Higher pressure differential and heat increase
turbine speed; the independently powered compressor can spool during cold start.
Loss of routing, heat, circulation or functional hardware removes drive. Shafts
accelerate over four seconds and coast over eight, without altering MJ accounting.
Visual speeds are capped at 20/24 rpm, keeping dense rows below 24 blade passes/s;
these are not engineering shaft-speed ratings.

The server saves phase/inertia with the train's entity-bound heat inventory.
Reload preserves the pose but clears drive until a newly paid start. A secure
read-only channel supplies initial and twice-per-second rotor snapshots. Clients
integrate between snapshots and use bounded corrections around the shortest
angular arc; incoming client drive/state is rejected. Old saves without rotor
state remain valid. Blender's explicit `preview_angle_degrees` controls and
optional replay of compiled C# samples are inspection aids, not exported actions.

The command and snapshot channels are distinct: reactor commands use 49371,
ejected-core snapshots 49372, flow 49373, battery commands 49374 and train rotors
49375. The compiled runtime checks reject duplicate channels and verify game
logic registrations for all 31 thermal subtypes. Delivery checks compare every
runtime script and definition with the actual ZIP and its hashed manifest.

Visible circulation follows the same typed physical graph and dispatched machines.
PRIMARY shows liquid streaks; HP/LP show soft gas wisps. H travels toward the
heater/train/cooler for each circuit and C returns through its paired bore.
Capped spurs and unselected standby branches stay still. A complete room-perimeter
example uses the existing 2.5 m pipe blocks, including the reactor adapters;
`tests/fixtures/thermal-room-layout.json` and the generated room grid bill record
all 122 placed blocks. This layout adds no new gameplay component or resource.

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
status lamps show pumping green, connected idle amber, unhealthy red and
unconnected dim. Reactor socket indicators retract with their pipe carriages.
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

Dispatch compares eligible duty banks and cold-end choices, retaining spare trains
when they do not improve supported output. Recovery is normalized to dispatched
design flow. Standard machinery provisionally handles 25 GWth; upgraded heaters,
trains and recovery handle 2.5 TWth. A standard cooler rejects 15 GW at reference
conditions. Reactor fuel tiers provide 25/250/2,500 GWth. These are editable balance
values in the generated model contract, not claims about real compact machinery.
Fuel is charged for newly admitted thermal MJ, including finite warm-up inventory;
stock and the saved fractional debt bound the final fuel quantum.

Prototype boundaries:

- One reactor supplies one connected HP/LP bank on a single physical grid.
  Parallel machinery is supported; shared reactor supplies are rejected.
- Socket positions, pressure circuits and hot/return roll come from all 31 model
  contracts, including the 170 mm adapter. Unused ports require caps. Failed/off
  machines close their valves; missing pipes leave an invalid route.
- Recovery receives credit on shortest physical heater/train and train/cooler
  routes, including equal parallel paths. Unequal recovery loops are conservative.
- Pipes are ideal links within one simulation step. MJ resides on real source
  and machine blocks; fluid mass, per-pipe transit delay and pressure are not
  simulated. The normalized core hazard is separate from this housing/loop ledger.
- Atmospheric density is sampled from the local planet. Ambient temperature is
  currently the 25°C reference. Radiators sample eight exposure rays over 250 m;
  sink temperature uses space/atmosphere reference values. Weather, solar loading,
  detailed occlusion and material-temperature dynamics remain future work.
- Per-block inventories stay on the server. Reactor motion snapshots carry
  mode, deployment and plant totals; train snapshots carry rotor state. Native multiplayer power
  behavior, physics, splits/merges and the complete coordinator need world tests.

Native authoring contract (implemented):

1. Export the reactor housing and both train variants as native reactor blocks
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
4. Both train variants need two root subparts, `Thermal_TurbineRotor` and
   `Thermal_CompressorRotor`. Use `assets/thermal-rotor-runtime.json` for the
   Blender pivots. The generated native pivots are `(1.35, .45, 0)` and
   `(4.25, .45, 0)`, with identity-oriented dummies. Bake rotor meshes in their
   **shaft-local** coordinates, excluding them from the static main. This differs
   from the reactor's identity-root, stowed-space manifold contract. The native
   rotation axis is -X. Preserve the existing clear-glass material ID and its
   `Data/TransparentMaterials.sbc` definition.
5. Complete native collision, construction/LOD and asset-dependency gates before
   installing definitions. Validate the isolated prototype in SE before migrating
   existing reactors or publishing.

Verification from the repository root:

```sh
python3 ArcanePower/tools/build_thermal_runtime_contract.py --check
python3 ArcanePower/tools/check_thermal_runtime.py
python3 ArcanePower/tools/compile_mod.py
dotnet build arcane-systems.sln
```

The focused checks execute the compiled production kernel with native math. They
cover budgets, mixed train sizes, standby/loss capacity, one-hour conservation
scenarios at 20/40/78%, fuel exhaustion, reload/copy identity, mode/startup guards,
47 manifold poses, heat/pressure rotor response, cold compressor startup,
coastdown, native shaft transforms, frame-size-independent phase integration,
and the captured authored starter layout, including
pressure/roll faults and grid separation. They do not execute the coordinator in
a live SE world or establish native collision/animation compatibility.
