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

The reactor supplies CO2 automatically to complete circuits, without a fill timer
or pressure requirement. Cold startup draws grid electricity through the train's
built-in compressor; hot shutdowns retain powered circulation. Partial delivery
supports proportional flow. No gas generator, tank, separate heater or manual
valve sequence is needed. Running
auxiliaries are deducted once; no second electrical grant is created.

| Mode / eligible turbine tier | Required hot-end temperature | Maximum net efficiency |
| --- | ---: | ---: |
| Standalone | Reactor fuel tier | 20% |
| Starter | 650°C | 40% |
| Improved | 1,000°C | 55% |
| Optimized | 1,600°C | 66% |
| Exotic | 2,200°C | 78% |

The standard train supports starter operation. The upgraded train can use higher
stages when the reactor's source temperature permits. A warmer compressor inlet
derates efficiency. These are game balance values, not a real-fluid simulation.
Each complete circuit keeps its eligible conversion efficiency and receives
at most one quarter of the reactor's nominal heat flow. Four equal circuits provide
100% capacity; three provide 75%, two 50%, one 25%. There is no additional
turbine-count efficiency penalty, standby pool or redistribution to surviving
circuits. Turbine ratings and source temperature still constrain actual output.
Standalone and Brayton are alternative paths for the same paid heat; their
outputs never add together.

Standard and upgraded trains have regular and mirrored versions, with one duplex
socket each. A breach isolates its circuit; repaired circuits resume as soon as
their connections validate and circulation is powered. See [construction and recovery](THERMAL-CONSTRUCTION.md) for
placement, startup, shutdown and migration, and [runtime ownership](THERMAL-RUNTIME.md)
for topology validation, saved state and circulation authority.

Cooling must reject `reaction heat × (1 − net efficiency)`. An undersized,
blocked or poorly exposed cooling bank no longer quietly throttles the reaction
to a safe output. Paid waste heat returns to the reactor and builds up after the
cooling buffers fill. Full stores stop fresh fuel use without clearing that heat.
The terminal, LCD and tablet Power page show available and required cooling,
returned waste and available circuits. Heat warns at 100% and arms the
existing irreversible failure sequence at **125%**. Restore cooling or shut down
early; keep cooldown power supplied. Once critical, ejecting moves the hazard but
cannot cancel its detonation timer.
Act on the retained-waste warning immediately: core temperature lags the stored
heat and can continue rising after cooling is restored.

At a 25 GWth Aether source, each standard circuit admits up to 6.25 GWth,
exports up to 2.5 GW and needs 3.75 GW rejection. Install at least one fully
exposed 10 GW standard cooler/panel in each circuit: four circuits need four
separate cooling connections. Leave headroom for sunlight, atmosphere and blockage.
The same allocation and cooling accounting apply to upgraded equipment and fuels.

Standard coolers and radiator sections reject **10 GW** each; upgraded sections
reject **100 GW**. Effective cooling depends on the installation:

- Atmospheric: `rating × density × clear exhaust fraction²`. Half-clear exhaust
  provides 25% cooling at reference density; fully blocked fans provide none.
- Space: radiative cooling at the local sink temperature and space clearance,
  multiplied by `1 - 0.5 × solar exposure`. Zero, half and full sunlight retain
  100%, 75% and 50% cooling. Each moving panel samples its own angle, shade
  and weather; clearance to space remains a separate limit.
- A radiator base supports two extensions. Three equally exposed sections provide
  30 GW standard or 300 GW upgraded; mixed stacks add each section's capacity.
  Disconnected or excess extensions contribute nothing and cannot duplicate MJ.

The [construction guide](THERMAL-CONSTRUCTION.md) covers cooling placement and
rotation clearances; [runtime details](THERMAL-RUNTIME.md) document sampling.

The old 40-block starter and 106-block room fixtures remain socket-geometry and
migration examples. Their shared layouts are deliberately rejected by the current
runtime; do not use them as current construction blueprints. Independent-circuit
checks cover all 24 grid rotations, branch failures, pressure, charging and retained
energy. The reactor's 170 mm adapters and all native pipe sockets are unchanged.

Normalized balance examples (100 MWth per train):

```sh
python3 ArcanePower/tools/thermal_budget.py --heat-mw 200 --trains 4 --coolers 4
python3 ArcanePower/tools/thermal_budget.py --stage exotic --cooler space
```

Authoring sources, named checkpoints and accepted collision inputs are retained.
Current definitions, icons, construction stages, LODs and native motion contracts
are checked by the release pipeline. In-game appearance, multiplayer behavior and
survival balance still require live-world validation.
