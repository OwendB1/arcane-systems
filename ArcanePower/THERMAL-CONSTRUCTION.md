# Building and verifying a Brayton plant

The construction guide, all 31 thermal block definitions and native models are
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
- Orange bore: H. Cyan bore: C. Both channels belong to the **same typed socket**;
  align H with H and C with C, including through elbows, risers and roll adapters.
- Green socket outline: aligned and fully built at both ends. Amber: open or
  aligned but unfinished/unavailable. Red: wrong circuit, facing, H/C roll or
  overlapping sockets. The text gives the reason as well as the colour.
- The selected block shows its sockets. Other faulty sockets in the connected
  assembly are marked within 25 m. Walk around the equipment to inspect covered
  faces. The guide checks the selected preview; inspect line/mirror copies after
  placing them.

Text HUD API is optional. Without it, the guide uses a native HUD notification;
socket markers and arrows remain available. SCF is not required.

## Build the three routes

Place **Arcane Thermal Reactor** for this system, then the matching primary
heater, Brayton train, recuperator and cooler/radiator blocks. The thermal reactor
has the standalone/Brayton switch and retracting pipe manifolds.

The reactor produces its own CO2 working fluid. No CO2 generator, tank or separate
filling conveyor is needed. Its powered eight-second commissioning phase fills
and pressurizes the sealed loop; circulation then reuses that working fluid.
A changed bank or reload requires another powered commissioning pass.

Start with one standard heater, train, recuperator and cooler, using standard
reactor fuel. Keep the entire thermal plant on **one physical large grid**.
Pistons, rotors, connectors and antennas do not transport this mod's heat between
grids. Parallel machines can be added after a basic plant works.

| Circuit | Connect | Purpose |
| --- | --- | --- |
| PRIMARY | Reactor housing ⇄ primary heater | Transfers reactor heat into the working loop. |
| CO2 HP | Heater ⇄ recuperator HP leg ⇄ train HP socket | High-pressure working route. |
| CO2 LP | Train LP socket ⇄ recuperator LP leg ⇄ cooler/radiator | Low-pressure recovery and heat rejection. |

The train keeps its original HP and LP side manifolds. Inside the turbine, HP H
feeds the front inlet chamber, gas travels axially through the dense blade rows,
and LP H collects the rear exhaust. LP C feeds the compressor front; HP C returns
its rear discharge toward the heater. External socket locations and H/C roll
remain unchanged.

Every socket contains supply and return bores. Ordinary conveyor blocks cannot
replace these connections. Use the matching PRIMARY, CO2 HP or CO2 LP conduit
family throughout each route. The recuperator's HP and LP legs remain separate;
both must participate in the appropriate routes. Putting recovery on a sealed
side branch earns no efficiency credit.

To circulate around the reactor room, route the PRIMARY connection along the
room perimeter with PRIMARY straights and elbows before reaching the heater.
Each block already carries both H and C, so the same route supplies heat and
returns coolant. Keep unused branches capped. The example in
`assets/review_thermal_models.py::plant(room_loop=True)` uses 106 routed pipe
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
4. Build the PRIMARY, HP and LP routes in the table. Use the placement arrows to
   align the socket faces and H/C bores. Preserve the native 2.5 m grid spacing.
5. Cap every unused reactor, machine and branch socket with the correct circuit's
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

1. **Connections:** no open or mismatched socket ends. Check circuit type, facing
   and roll; use adapters at the reactor. Unfinished blocks stay in the inspection
   graph, so a bad joint or missing weld cannot hide the rest of the build.
2. **Functions:** one reactor, a connected primary heater and train, recovery on
   both working routes, and LP cooling. Detached unfinished assemblies are
   checked separately. A projection is a reference, never a verified real build.
3. **Welding/access:** no unfinished, damaged or unavailable blocks. The guide
   then reports **Construction verified**. This confirms the observed topology
   and build state; it does not certify thermal capacity or enable startup.
4. **Cooling:** use an atmospheric cooler in atmosphere with powered circulation,
   or give a space radiator unobstructed exposure to a cold sink. Enough cooling
   must handle the dispatched plant's rejected heat. Welding a cooler does not
   establish that it can reject heat at its location.
5. **Power and supplies:** provide external startup power in addition to reactor
   containment. Cold starting needs **2% of the selected train bank's thermal
   rating for eight delivered seconds**. A standard 25 GWth bank therefore needs
   500 MW of startup supply, plus containment demand. Check fuel, containment
   tiles, controllers, vent readiness and ownership on the reactor dashboard.
6. **Commissioning:** once the mode is settled, start the reactor manually. Watch
   the **Server** line in the guide and the reactor's native terminal/dashboard.
   **Internal CO2 generation / loop pressurization** shows delivered startup
   progress. It also reports the actual mode and operating limit. The electric
   compressor spools first; turbine motion follows the paid heat and gameplay
   pressure estimate. Verify power export and heat rejection under a real load.

The starter target is 40% net conversion. Additional eligible recovery can improve
it, subject to source temperature, hardware grade and cooling, up to 78%. Extra
trains cannot substitute for missing heaters, recovery or cooling. Standalone
remains a separate 20% mode with integrated rejection and hidden manifolds.

For shutdown or conversion back to standalone, stop the source and retain
circulation/cooling power while stored heat drains. Wait for the mode transition
and manifold retraction to finish before restarting. A local green connection
marker never overrides the server's safeguards.

## Verification available in the repository

`python3 ArcanePower/tools/check_thermal_runtime.py` checks the authored starter
layout, incomplete and detached builds, wrong/open/crowded joints, all 24 grid
orientations, reactor offsets, missing recovery/cooling and the existing runtime
accounting. `python3 ArcanePower/tools/compile_mod.py` checks native SE imports and
the Mod API whitelist. Live HUD rendering, commissioning and multiplayer gameplay
remain unverified until tested in a live SE world.
