# Modular Brayton power

The reactor, turbine/compressor trains and coolers share **one duplex pipe network**.
Every socket carries separate H and C bores. Each train has one socket and connects
as a terminal branch, so trains operate in parallel. Match H to H and C to C on
every face; there are no separate high- and low-pressure pipe blocks.
Heaters and recuperators are retired from the mod. Their authoring models remain
in the production blend for future reuse, outside the shipped catalog.

[Construction instructions](THERMAL-CONSTRUCTION.md) cover adapters, H/C roll,
placement guidance, welding, commissioning and shutdown.

The reactor generates its own sealed CO2 charge. Its eight-second commissioning
phase draws grid electricity through the train's built-in compressor. No gas
generator, tank, separate heater or manual valve sequence is needed. Running
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
The table gives the ceiling with **four active, eligible turbines**. One, two,
three and four turbines reach **40%, 60%, 80% and 100%** of that ceiling:

| Active turbines | Starter net | Exotic net |
| ---: | ---: | ---: |
| 1 | 16% | 31.2% |
| 2 | 24% | 46.8% |
| 3 | 32% | 62.4% |
| 4 | 40% | 78% |

Additional turbines provide capacity or standby without a further efficiency bonus.
Standalone and Brayton are alternative paths for the same paid heat; their
outputs never add together.

Standard and upgraded trains each have regular and mirrored versions. All four
fit a 2-wide × 2-high × 5-long envelope (5×5×12.5 m). The round machinery sits
0.55 m lower and the single duplex socket occupies the lower side cell. H enters
the first compressor casing; the compressor casing flares directly into the turbine front, and C
returns from its rear beside the generator. Close side runs pass through relieved
supports. Ratings, dense blade rows and inspection windows are retained.
Existing two-socket trains need their connections rerouted to the single lower
socket; remove or cap the abandoned branch. Older, larger trains need replacement.

Parallel trains add efficiency up to four active units, then capacity or standby.
Available source heat and train throughput limit output. Dispatch chooses the highest available output
and uses fewer machines on ties. A broken connection prevents generation rather
than teleporting heat. Existing inventories stay on their source and machine
blocks and must cool before a mode change.

Cooling must reject `reaction heat × (1 − net efficiency)`. An undersized,
blocked or poorly exposed cooling bank no longer quietly throttles the reaction
to a safe output. Paid waste heat returns to the reactor and builds up after the
cooling buffers fill. Full stores stop fresh fuel use without clearing that heat.
The terminal, LCD and tablet Power page show available and required cooling,
returned waste and active/standby turbines. Heat warns at 100% and arms the
existing irreversible failure sequence at **125%**. Restore cooling or shut down
early; keep cooldown power supplied. Once critical, ejecting moves the hazard but
cannot cancel its detonation timer.
Act on the retained-waste warning immediately: core temperature lags the stored
heat and can continue rising after cooling is restored.

At the standard 25 GWth source, one turbine needs 21 GW of rejection: two fully
effective 15 GW cooling units. Four standard turbines need 15 GW, so one clear
unit meets the design point, with extra cooling recommended for obstruction or
environmental losses. The requirement scales with source power and turbine tier.

Atmospheric coolers require air and powered circulation. Their airtight
3×3×2-cell casing fits flush against surrounding armor; only the front fan
assemblies project beyond the hull. Connect the shared duplex network at the rear. Leave 2.5 m clear
beyond both fan guards. Cooling scales with atmospheric density and the square
of the clear exhaust fraction: half clear gives 25% cooling, fully blocked gives
none. Clearing an obstruction restores capacity on the next environment sample.

Space radiators need a
cold, exposed sink. The new radiator uses a bottom duplex manifold and a full
2.5 m pedestal, with a 3×3×3-cell reserved sweep. Its panels turn automatically
edge-on to sunlight at 3°/s. Broadside solar loading reduces rejection by 35%;
eight rays per panel sample both actual moving faces. A faint, ribbed red-orange
glow follows heat actually dissipated, with a three-second response.

Up to two 3×2×3-cell Radiator Panel extensions stack above one base. All sections
share the same axis and connected side pipes. Each contributes the same 15 GW
rated cooling; three equally exposed sections provide 45 GW. Ownership, build
state, orientation, grid identity and consecutive placement gate attachment.
Extra or disconnected sections cannot generate cooling or duplicate stored heat.

The side members remain metal ribs. Only terminal collars use the established
reflective glass and hot/cold emissives; opaque caps close exposed ends. Both
stack joints have 25 cm frame gaps centered on the connection plane. The center
collars have 35 mm clearance to each rail. Structural edges use narrow chamfers.

The authored starter fixture contains 40 blocks; the room-perimeter fixture has
106. Both are generated by `assets/review_thermal_models.py` and exercised against
the compiled runtime. Standard reactor adapters preserve the native 170 mm
manifold offset. Existing pipe socket geometry is unchanged. These one-train/one-cooler
fixtures verify topology; add cooling before sustained full-load operation with
the new efficiency curve.

Normalized balance examples (100 MWth per train):

```sh
python3 ArcanePower/tools/thermal_budget.py --heat-mw 200 --trains 4 --coolers 3
python3 ArcanePower/tools/thermal_budget.py --stage exotic --cooler space
```

Authoring sources, named checkpoints and accepted collision inputs are retained.
Current definitions, icons, construction stages, LODs and native motion contracts
are checked by the release pipeline. In-game appearance, multiplayer behavior and
survival balance still require live-world validation.
