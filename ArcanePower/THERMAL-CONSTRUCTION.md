# Building and verifying a Brayton plant

The construction guide, 27 public thermal blocks and 28 hidden pipe compatibility definitions and native models are
included in the local 0.1.0 alpha package. Live SE validation of these instructions
remains pending. Construction verification is separate from server permission
to start the reactor.

## Use the guide

Select a thermal block in build mode to see its connection instructions and
placement arrows. Aim at an existing thermal block within 20 m to inspect its
connected assembly while welding or checking a finished build. Use the full HUD
for instructions and arrows. Minimal HUD retains socket markers; HUD off, chat
and menus hide the guide.

- Red arrow: current facing. Green arrow: a rotation that aligns more sockets.
  The curved arrow suggests the turn; the blue arrow marks the selected port's H
  side. Rotate the preview, or rebuild an incorrectly oriented placed block.
- Orange bore: H. Cyan bore: C. Both channels belong to the **same duplex socket**;
  align H with H and C with C, including through elbows, risers and roll adapters.
- Green socket outline: aligned and fully built at both ends. Amber: open or
  aligned but unfinished/unavailable. Red: wrong facing, H/C roll or
  overlapping sockets. The text gives the reason as well as the colour.
- The selected block shows its sockets. Other faulty sockets in the connected
  assembly are marked within 25 m. Walk around the equipment to inspect covered
  faces. The guide checks the selected preview; inspect line/mirror copies after
  placing them.

Text HUD API is optional. Without it, the guide uses a native HUD notification;
socket markers and arrows remain available. SCF is not required.

## Build four independent circuits

Place the **Arcane Reactor**, a Brayton turbine/compressor train and an atmospheric cooler or space radiator. The reactor has the standalone/Brayton switch and retracting pipe manifolds. **Standalone uses Aether only. Helion and Empyrean require Brayton**; the safety interlock blocks their reaction in standalone to prevent meltdown.

Burn Aether to recover **Aether Residuum**: 10 units per fully consumed canister,
in either mode. Fractional recovery and full-inventory backlogs survive saves;
conveyors can export the recovered material to connected accessible cargo.
Upgraded turbines require **20 units** each. Upgraded atmospheric coolers, space
radiators and extension panels require **10 units** each. **Empyrean requires
upgraded turbines**; a larger standard turbine bank cannot accept T3 heat.

The reactor produces its own CO2 working fluid. Each manifold circuit pays for
its own eight-second fill/compression phase through its turbine's electrical sink.
A full working charge represents 22 MPa. Charge and heat flow are split between
the four circuits; each operating circuit keeps its normal pressure. No separate
generator, tank or filling conveyor is needed.

Build **one turbine and its own coolers per reactor manifold**. Use tees/crosses
inside that circuit; match opposing faces and H/C roll. Never connect two reactor
manifolds or share a cooler/turbine between circuits. Cap unused pipe mouths;
unconnected reactor manifolds remain closed automatically. Keep the plant on
one physical large grid; subgrid rotors/pistons/connectors do not transport heat.
Regular/mirrored turbines provide opposite-side sockets and both equipment tiers.

With Aether, each circuit receives up to 6.25 GWth, exports 2.5 GW at starter
conversion and needs 3.75 GW rejection. Fit at least one effective standard
10 GW cooler/panel in each circuit, with environmental headroom. One circuit
works at 25% of full capacity; four independent circuits provide full capacity.
Upgraded cooling provides 100 GW per unit/panel. Empyrean requires upgraded
turbines and enough cooling within every operating circuit.

All four trains occupy **2 blocks wide × 2 high × 5 long** (5×5×12.5 m). The socket
is in the lower side cell near the compressor. The shaft line sits 0.55 m lower.
Hot gas enters the first compressor casing, passes directly through its tapered
rear casing into the constant-diameter turbine and leaves at the turbine rear beside the
generator. The external runs sit close to the housing, with clearance pockets
in the supports. Dense blade stacks and inspection windows remain.

Existing two-socket trains need reconnecting to the single lower socket. Remove
or cap the abandoned branch. Replace older, larger blocks before reconnecting.
Equipment ratings, efficiency tiers and component costs are retained. Old HP/LP
pipe IDs still load and weld as hidden aliases of the unified fittings; their
socket geometry is preserved. Ordinary conveyors cannot carry thermal flow.

Mount the atmospheric cooler flush in a **3×3-cell hull opening, two cells deep**.
Its airtight casing meets surrounding armor on all four edges. Face the fans
outside the ship and connect the **rear duplex manifold** inside it.
The intake louvers stay recessed in the exterior face. Keep **2.5 m clear beyond
both fan guards**: half-clear exhaust leaves 25% cooling, fully blocked exhaust
leaves none. Armor, another grid or terrain in the exhaust path reduces capacity.
Check **Exhaust clearance** and **Available cooling** in the cooler terminal.
Clearance is resampled about once per second during operation. Existing coolers
retain their block size, but their old side connection must be rerouted to the rear.

To circulate around the reactor room, route each independent manifold circuit
along its own perimeter path, branching to its one turbine and cooling equipment.
Every pipe carries H supply and C return. Cap all unused junction mouths.
The historical starter/room examples in `review_thermal_models.py` retain shared
routing for geometry and migration checks; they need separate circuits before use.
The reactor's internal distributor, pump heads and chamber injectors are
integrated housing details; they require no separately placed pump block.

1. Finish the reactor's containment, two fully built functional controllers (at
   least one advanced to unlock Brayton), vent route,
   fuel/tile supplies and containment power. Keep the reactor off while building.
2. If changing an operating reactor from standalone, stop and let it cool. Select
   Brayton mode. Delivered power or the paid reserve moves the manifolds only
   after the shutdown/drain interlocks clear. Wait until deployment is complete.
3. Fit a **reactor adapter** between the housing's native-height PRIMARY manifold
   and the regular pipe lattice. It resolves the 170 mm socket offset. A rotated
   straight pipe cannot replace it.
4. Build independent manifold circuits, with one turbine and cooling in each. Use the placement arrows to
   align the socket faces and H/C bores. Preserve the native 2.5 m grid spacing.
5. Every connected socket needs exactly one correctly oriented, healthy peer.
   Unused reactor outlets close automatically; cap every unused pipe mouth.
   A pipe crossing another pipe is not a connection.
6. Fully weld and repair the connected blocks. Obtain access to the source and
   machinery, and enable completed thermal machines before operation.

## Circuit damage and recovery

The reactor manifolds carry the automatic butterfly shut-offs. Damage, a missing
pipe/machine, open junction outlet, H/C fault or grid split makes that entire
circuit unavailable immediately. Both reactor bores close together over 0.35 s;
other circuits keep their own charge, efficiency and heat-flow allocation.
Do not rely on junction auto-capping: fit physical end caps on unused pipe mouths.

Loss of the final operating circuit disables the reactor and latches shutdown.
Existing heat remains on its real blocks; containment, tiles, critical-core fuse
and ejection keep their existing authority. There is no standalone fallback.
Repair the affected circuit, supply electricity for CO2 refill/compression and
restart manually after a full shutdown. Healthy circuits can keep running while
a repaired circuit commissions. External power can also refill a repaired circuit
for cooldown while the core stays off. Cold commissioning with no charged circuit
is a startup state and does not itself trigger a last-loop-loss trip.

Pipe or machinery changes revalidate/refill that circuit only. World reloads
revalidate all circuits and require paid filling; no charge is granted from elapsed
wall-clock time. Old shared-network builds migrate disabled with all heat retained;
separate their plumbing and restart. Blocked fans or sun-loaded radiators reduce
rejection without pretending that pressure was lost: insufficient cooling can
still raise retained waste to the existing 125% critical threshold.

## Verify construction, then operation

Once running, green edge lamps and moving streaks/wisps indicate measured
circulation. Amber means the selected route is connected but idle. A capped spur or unavailable circuit stays still. Cold start can circulate cold fluid before the
hot bands warm up. Internal circulation also works in powered standalone mode;
the external room route operates in Brayton mode.

Aim at a block in the assembly and resolve the guide's next instruction:

1. **Connections:** resolve mismatched socket ends and cap unused pipe mouths. Check facing
   and H/C roll; use adapters at the reactor. Unfinished blocks stay in the inspection
   graph, so a bad joint or missing weld cannot hide the rest of the build.
2. **Functions:** one turbine and cooling per manifold circuit; keep manifold circuits separate. Detached unfinished assemblies are
   checked separately. A projection is a reference, never a verified real build.
3. **Welding/access:** no unfinished, damaged or unavailable blocks. The guide
   then reports **Construction verified**. This confirms the observed topology
   and build state; it does not certify thermal capacity or enable startup.
4. **Cooling:** use an atmospheric cooler in atmosphere with powered circulation
   and clear fan exhausts,
   or give a space radiator unobstructed exposure to a cold sink. Enough cooling
   must handle the dispatched plant's rejected heat. Welding a cooler does not
   establish that it can reject heat at its location. Compare **Cooling capacity**
   with **Cooling required** on the reactor Power page. Insufficient rejection
   stores waste in the reactor; 100% heat warns and 125% starts irreversible failure.
5. **Power and supplies:** provide external startup power in addition to reactor
   containment. Cold starting needs **2% of dispatched thermal throughput
   for eight delivered seconds**, regardless of oversized nameplate capacity.
   A standard 25 GWth bank therefore needs
   500 MW for all four circuits, or 125 MW per commissioned circuit, plus containment demand. Check fuel, containment
   tiles, controllers, vent readiness and ownership on the reactor dashboard.
6. **Commissioning:** once the mode is settled, start the reactor manually. Watch
   the **Server** line in the guide and the reactor's native terminal/dashboard.
   **Circuit 1–4** diagnostics show delivered filling progress, charge, pressure,
   valve state and cooling margin. It also reports the actual mode and operating limit. The electric
   compressor spools first; turbine motion follows the paid heat and gameplay
   pressure estimate. Verify power export and heat rejection under a real load.

Eligible turbines retain 40% starter conversion, then 55%, 66% or 78% with
suitable temperature/equipment. Circuit count changes capacity rather than
conversion efficiency: 25%, 50%, 75% or 100% of nominal reactor allocation.
There is exactly one turbine per circuit. Standalone remains a separate 20% mode.
Restore cooling or shut down early when waste accumulates; keep cooldown power.

Space radiators connect within their own manifold circuit through the bottom socket. The base occupies 3×3×3
large-grid cells with a full-height pedestal in the bottom cell. Stack up to two
3×2×3 Radiator Panel blocks directly above it, in the same orientation and on the
same physical grid. The two side pipes must meet. Weld and enable all sections;
access is checked against the base owner. Connected panels turn together at
3°/s, edge-on to the sun. Their 25 cm frame gaps leave the sealed couplings clear.
Cooling follows inverse solar exposure: 0% sun gives 100% cooling, 50% sun
gives 75%, and 100% sun on either face gives 50%. Each panel samples its own
angle, partial shade, planetary shadow and weather. The terminal shows
**Solar exposure** and **Cooling after solar load**. Keep both faces clear to
space; shade alone does not compensate for enclosing the panels.
Three equally exposed standard panels dissipate up to 30 GW, or 300 GW with all
three upgraded. Mixed stacks add each section's own 10/100 GW rating.
A detached, misaligned, unfinished, disabled or third extension adds no cooling.
Keep both faces open to space and the entire rotation envelope clear. The faint
red-orange panel glow follows actual heat rejection, not requested power.

For shutdown or conversion back to standalone, stop the source and retain
circulation/cooling power while stored heat drains. Wait for the mode transition
and manifold retraction to finish before restarting with Aether. Higher-tier fuel
can remain in storage but will not be selected or automatically replenished in
standalone. Losing the last intact advanced controller stops Brayton generation
and pauses further deployment. Existing heat and deployed cooling connections
remain; keep cooldown power supplied, repair the controller and restart manually.
A local green connection marker never overrides the server's safeguards.

## Verification available in the repository

`python3 ArcanePower/tools/check_reactor_fuel_modes.py` exercises the production
fuel, controller, mode-switch and terminal predicates: survival/creative,
mixed inventories, conveyor supply, unavailable controllers, restored unsafe
states, retained heat, pending fuel charges and powered shutdown/retraction.
It also checks Residuum recovery across tiny debits, full inventories, failed
item insertion, save/load, copied identities, conveyors and creative/client guards.
The completed offline pass has 544 fuel/recovery/shutdown checks and 2,245,876 thermal
checks, including T3 hardware eligibility, 10/100 GW cooling tiers and inverse
solar exposure with shade, weather and planetary-shadow boundaries. Native
motion validation passes all 1,730 existing comparisons; isolation valves pass
48 native mesh/pose comparisons across all four reactor valve mounts. Live SE commissioning
and multiplayer verification remain pending.

`python3 ArcanePower/tools/check_thermal_runtime.py` checks rejection of the old shared starter/room
layouts, independent circuits, incomplete and detached builds, wrong/open/crowded joints, all 24 grid
orientations, reactor offsets, missing turbine/cooling and the existing runtime
accounting, four-circuit damage/repair, independent paid commissioning and preserved heat.
`python3 ArcanePower/tools/compile_mod.py` checks native SE imports and
the Mod API whitelist. Live HUD rendering, commissioning and multiplayer gameplay
remain unverified until tested in a live SE world.

Valve rebuild instructions and the 48-sample reactor mount contract are in
[the native authoring contract](THERMAL-RUNTIME.md#native-authoring-contract).
