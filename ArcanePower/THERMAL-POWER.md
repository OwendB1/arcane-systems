# Modular Brayton power

The reactor has **four independent duplex manifold circuits** on one physical
large grid. Each circuit needs exactly one turbine and its own atmospheric cooling
or space radiators. Every socket carries separate H and C bores; match their roll
and opposing faces. Tees/crosses branch within a circuit. Never join two reactor
outlets or share machinery between circuits. Cap unused pipe mouths; unused
reactor outlets stay closed automatically.
Heaters and recuperators are retired from the mod. Their authoring models remain
in the production blend for future reuse, outside the shipped catalog.

[Construction instructions](THERMAL-CONSTRUCTION.md) cover adapters, H/C roll,
placement guidance, welding, commissioning and shutdown.

The reactor supplies CO2 automatically, without filling, pressure or simulated
circulation. Containment still needs startup energy and power during hot cooldown.
Turbines have no separate compressor-startup electricity request. Running auxiliary
cost is included once in conversion efficiency; active coolers require the existing
reactor auxiliary supply/reserve. Space radiators cool passively.

Electrical demand sets fuel use: `fuel input = electrical output / conversion`.
Standalone Aether converts 10% into electricity and uses integrated cooling.
Brayton converts a flat 80%, independently of fuel or turbine tier. Its gameplay
cooling rule is **1 GW electrical output requires 1 GW cooling** in that circuit.
Half load means half fuel use and half cooling load. Zero demand stops new fuel
use and cooling load after the small paid reserve is filled.

Fuel input and cooling backlog are separate budgets. The unused paid fuel reserve
persists safely; accumulated cooling load remains until cooling removes it.
Environmental conditions affect cooling capacity, not fuel conversion.
Each complete circuit keeps its eligible conversion efficiency and receives
at most one quarter of the reactor's nominal heat flow. Four equal circuits provide
100% capacity; three provide 75%, two 50%, one 25%. There is no additional
turbine-count efficiency penalty, standby pool or redistribution to surviving
circuits. Turbine ratings and source temperature still constrain actual output.
Standalone and Brayton are alternative paths for the same paid heat; their
outputs never add together.

Standard and upgraded trains have regular and mirrored versions, with one duplex
socket each. A breach isolates its circuit; repaired circuits resume as soon as
their connections validate. See [construction and recovery](THERMAL-CONSTRUCTION.md) for
placement, startup, shutdown and migration, and [runtime ownership](THERMAL-RUNTIME.md)
for topology validation, saved state and energy accounting.

Cooling capacity is independent of turbine load. Each circuit accumulates waste
that its own cooling cannot reject; another circuit's spare cooling cannot offset
that shortage. Output is not silently throttled to make an undersized installation
safe. Stopping generation preserves heat and allows cooldown. The hottest circuit
feeds the existing core-temperature response. Yellow warns when a 60-second
projection of current net heat buildup predicts a rise into overheating; stable
full-load heat and safe cooldown remain neutral. Actual heat still arms irreversible
failure at **125%**. Restore cooling or shut down early; retain containment power for
active coolers. An already armed critical fuse cannot be cancelled by cooling.

The LCD and tablet Power pages show cooling load, available capacity, weakest-circuit
margin, potential cooling, cooldown backlog and fuel burn. Output already states
current/maximum electricity, so a separate full-load cooling row is unnecessary:
size cooling to that maximum output. Unit terminals retain environmental and power
diagnostics. Complete offline circuits show potential cooling before startup.
Cooldown progress and ETA remain visible after output and new cooling load stop.

Fuel input ratings are **5 / 50 / 250 GW** for Aether / Helion / Empyrean.
Standalone Aether provides **500 MW** at 10% conversion. Brayton converts 80%:
**4 GW Aether**, **14 GW Helion with T1**, **40 GW Helion with T2**, and
**200 GW Empyrean with T2**. Standard turbines are capped at **3.5 GW each**
(4.375 GW fuel input); upgraded turbines at **50 GW each** (62.5 GW fuel input).
Turbine-limited operation burns less fuel; unused potential is not extra heat.
Regular and mirrored variants share these limits. Full-load canister endurance
remains 2.5 minutes for Aether and 10 minutes for higher fuels before controllers.

Each of four circuits needs cooling equal to its own electrical output:
**1 GW Aether**, **3.5 GW T1 Helion**, **10 GW T2 Helion**, **50 GW Empyrean**.
At full air density with clear fans, fit one T1 atmospheric cooler per circuit for
Aether/T1 Helion, or one T2 per circuit for T2 Helion/Empyrean. Empyrean has no
spare capacity with exactly one T2 cooler per circuit.
In ideal shaded vacuum, each circuit needs one T1 radiator section for Aether,
two T1 sections for T1 Helion, one T2 section for T2 Helion, or three T2 sections
for Empyrean. At full sunlight in vacuum, Empyrean needs five T2 sections per
circuit across two stacks. Allow extra capacity for environmental losses.

Atmospheric coolers reject **5/50 GW per T1/T2 unit**. Radiator sections retain
**2/20 GW per T1/T2 panel**. Effective cooling depends on the installation:

- Atmospheric: `rating × density × clear exhaust fraction²`. Half-clear exhaust
  provides 25% cooling at reference density; fully blocked fans provide none.
  Density is clamped to 0–1: vacuum gives zero, 0.5 atmosphere gives half, and
  1 atmosphere gives full capacity with clear exhausts.
- Space: radiative cooling weighted between vacuum and the 25°C reference
  atmosphere by measured density, with space clearance,
  multiplied by `1 - 0.5 × solar exposure`. Zero, half and full sunlight retain
  100%, 75% and 50% cooling. Each moving panel samples its own angle, shade
  and weather; clearance to space remains a separate limit. Trace atmosphere
  no longer triggers the full atmospheric penalty: at 0.1% density, 99.91% of
  capacity remains before sun and clearance losses; at full density, 12.36% remains.
- A one-cell airtight radiator rotor base supports three separate panels and
  provides no cooling itself. Three equally exposed panels provide
  6 GW standard or 60 GW upgraded; mixed stacks add each section's capacity.
  Disconnected or excess extensions contribute nothing and cannot duplicate MJ.

The [construction guide](THERMAL-CONSTRUCTION.md) covers cooling placement and
rotation clearances; [runtime details](THERMAL-RUNTIME.md) document sampling.

The old 40-block starter and 106-block room fixtures remain socket-geometry and
migration examples. Their shared layouts are deliberately rejected by the current
runtime; do not use them as current construction blueprints. Independent-circuit
checks cover all 24 grid rotations, branch failures, pressure, charging and retained
energy. The reactor's 170 mm adapters and all native pipe sockets are unchanged.

Plant balance examples (effective cooling GW per circuit):

```sh
python3 ArcanePower/tools/thermal_budget.py --fuel helion --cooling-gw 3.5
python3 ArcanePower/tools/thermal_budget.py --fuel empyrean --turbine-tier 2 --cooling-gw 50
```

Authoring sources, named checkpoints and accepted collision inputs are retained.
Current definitions, icons, construction stages, LODs and native motion contracts
are checked by the release pipeline. In-game appearance, multiplayer behavior and
survival balance still require live-world validation.
