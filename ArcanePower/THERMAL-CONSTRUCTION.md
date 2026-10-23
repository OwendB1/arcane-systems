# Building and verifying a Brayton plant

The construction guide, 24 public thermal blocks and 28 hidden pipe compatibility definitions and native models are
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

## Build the shared network

Place the **Arcane Reactor**, a Brayton turbine/compressor train and an atmospheric cooler or space radiator. The reactor has the standalone/Brayton switch and retracting pipe manifolds.

The reactor produces its own CO2 working fluid. No CO2 generator, tank or separate
filling conveyor is needed. Its powered eight-second commissioning phase fills
and pressurizes the sealed loop; circulation then reuses that working fluid.
A changed bank or reload requires another powered commissioning pass.

With standard reactor fuel, start with one standard train and **two fully effective
cooling units**, or four standard trains and at least one fully effective cooler.
Leave cooling headroom for environmental losses. Keep the entire thermal plant on **one physical large grid**.
Pistons, rotors, connectors and antennas do not transport this mod's heat between
grids. Parallel machines can be added after a basic plant works.

Connect the reactor, trains and coolers to one shared network of duplex pipes.
Use tees or crosses for parallel branches. Every train is a terminal machine with
one socket: it cannot serve as an inline connection to another train. The regular
and mirrored versions put that socket on opposite sides; both have standard and
upgraded tiers. Face normals must oppose and H/C marks must align at every joint.

All four trains occupy **2 blocks wide × 2 high × 5 long** (5×5×12.5 m). The socket
is in the lower side cell near the compressor. The shaft line sits 0.55 m lower.
Hot gas enters the first compressor casing, passes directly through its tapered
rear casing into the constant-diameter turbine and leaves at the turbine rear beside the
generator. The external runs sit close to the housing, with clearance pockets
in the supports. Dense blade stacks and inspection windows remain.

Existing two-socket trains need reconnecting to the single lower socket. Remove
or cap the abandoned branch. Replace older, larger blocks before reconnecting.
Power ratings, efficiency tiers and component costs remain unchanged. Old HP/LP
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

To circulate around the reactor room, route a reactor branch along the
room perimeter with straights and elbows before reaching the train.
Each block already carries both H and C, so the same route supplies heat and
returns coolant. Keep unused branches capped. The example in
`assets/review_thermal_models.py::plant(room_loop=True)` uses 93 routed pipe
blocks plus the machines, adapters, caps and four perimeter elbows.
The reactor's internal distributor, pump heads and chamber injectors are
integrated housing details; they require no separately placed pump block.

1. Finish the reactor's containment, two functional controllers, vent route,
   fuel/tile supplies and containment power. Keep the reactor off while building.
2. If changing an operating reactor from standalone, stop and let it cool. Select
   Brayton mode. Delivered power or the paid reserve moves the manifolds only
   after the shutdown/drain interlocks clear. Wait until deployment is complete.
3. Fit a **reactor adapter** between the housing's native-height PRIMARY manifold
   and the regular pipe lattice. It resolves the 170 mm socket offset. A rotated
   straight pipe cannot replace it.
4. Build the shared network and its machine branches. Use the placement arrows to
   align the socket faces and H/C bores. Preserve the native 2.5 m grid spacing.
5. Cap every unused reactor, machine and branch socket with an
   end cap. Each socket needs exactly one peer. A pipe crossing another pipe is
   not a connection.
6. Fully weld and repair the connected blocks. Obtain access to the source and
   machinery, and enable completed thermal machines before operation.

## Verify construction, then operation

Once running, green edge lamps and moving streaks/wisps indicate measured
circulation. Amber means the selected route is connected but idle. A capped spur
or standby branch stays still. Cold start can circulate cold fluid before the
hot bands warm up. Internal circulation also works in powered standalone mode;
the external room route operates in Brayton mode.

Aim at a block in the assembly and resolve the guide's next instruction:

1. **Connections:** no open or mismatched socket ends. Check facing
   and H/C roll; use adapters at the reactor. Unfinished blocks stay in the inspection
   graph, so a bad joint or missing weld cannot hide the rest of the build.
2. **Functions:** one reactor, a connected train and cooler. Detached unfinished assemblies are
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
   500 MW of startup supply, plus containment demand. Check fuel, containment
   tiles, controllers, vent readiness and ownership on the reactor dashboard.
6. **Commissioning:** once the mode is settled, start the reactor manually. Watch
   the **Server** line in the guide and the reactor's native terminal/dashboard.
   **Internal CO2 generation / loop pressurization** shows delivered startup
   progress. It also reports the actual mode and operating limit. The electric
   compressor spools first; turbine motion follows the paid heat and gameplay
   pressure estimate. Verify power export and heat rejection under a real load.

Four active, eligible turbines reach the tier ceiling: 40% starter, then 55%, 66%
and 78% with suitable source temperature and equipment. One, two and three active
turbines reach 40%, 60% and 80% of that ceiling; a fourth reaches 100%. Extra units
add capacity or standby. Standalone remains a separate 20% mode. Restore cooling
or shut down early when waste accumulates; keep circulation power during cooldown.

Space radiators connect to the shared network through the bottom socket. The base occupies 3×3×3
large-grid cells with a full-height pedestal in the bottom cell. Stack up to two
3×2×3 Radiator Panel blocks directly above it, in the same orientation and on the
same physical grid. The two side pipes must meet. Weld and enable all sections;
access is checked against the base owner. Connected panels turn together at
3°/s, edge-on to the sun. Their 25 cm frame gaps leave the sealed couplings clear.
Three equally exposed panels dissipate up to 45 GW, three times the base's 15 GW.
A detached, misaligned, unfinished, disabled or third extension adds no cooling.
Keep both faces open to space and the entire rotation envelope clear. The faint
red-orange panel glow follows actual heat rejection, not requested power.

For shutdown or conversion back to standalone, stop the source and retain
circulation/cooling power while stored heat drains. Wait for the mode transition
and manifold retraction to finish before restarting. A local green connection
marker never overrides the server's safeguards.

## Verification available in the repository

`python3 ArcanePower/tools/check_thermal_runtime.py` checks the authored starter
layout, incomplete and detached builds, wrong/open/crowded joints, all 24 grid
orientations, reactor offsets, missing turbine/cooling and the existing runtime
accounting. `python3 ArcanePower/tools/compile_mod.py` checks native SE imports and
the Mod API whitelist. Live HUD rendering, commissioning and multiplayer gameplay
remain unverified until tested in a live SE world.
