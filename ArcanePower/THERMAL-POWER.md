# Modular Brayton power — design and model study

16 October 2026. Current direction: closed sCO₂ Brayton only. The earlier topping
converter and its dedicated utility circuit have been removed from the active
proposal, procedural sources and Blender study. This remains a gameplay/model
proposal; existing runtime reactors still generate electricity directly.

Accepted balance: **20% net standalone**, with primary manifolds hidden;
**40% net starter Brayton**, upgradeable to **78% net**. These are alternative
conversion paths for allocated reactor heat. Never award 20% plus 78% for the
same heat. Standalone operation uses integrated heat rejection; its capacity and
startup/shutdown behavior still need runtime integration.

## The engineering loop

Build **heater → turbine/generator train → cooler**, with recuperators recovering
exhaust heat into the compressed supply. Internally the CO₂ follows compressor →
recuperator cold side → primary heater → turbine → recuperator hot side → cooler
→ compressor. Primary carrier and CO₂ never mix. The train contains an electric
compressor drive and a separate turbine/generator shaft.

Players connect matching thermal sockets. Flow allocation, pressure and working
inventory are automatic; no manual valve sequence, fluid recipe spreadsheet or
real-fluid solver is required. Primary, high-pressure CO₂ and low-pressure CO₂
remain physically separate networks. Shared headers and tees allow parallel banks.

| Add more of… | Player benefit | What still limits it |
| --- | --- | --- |
| Primary heaters | More accepted reactor heat; spare heat-exchanger capacity | Reactor supply and downstream capacity |
| Turbine/compressor trains | More electrical output capacity; automatic standby/failover | Heat, recuperation and cooling |
| Recuperators | Better fuel-to-electric efficiency, with diminishing returns; capacity after damage | Hot-end hardware/temperature ceiling |
| Fan coolers | More cooling in air; atmospheric redundancy | Air density and intake temperature |
| Space radiators | More cooling in vacuum; radiator redundancy | Radiative sink temperature and exposed area |

There is no additive generator multiplier. Two trains sharing a heater sized for
one train still have only one train's heat available. Extra recuperators recover
existing heat; they never create heat. More coolers remove a bottleneck or provide
spares; they do not multiply efficiency above the cycle's limit.

Start with one of each required function. Expand banks on shared headers, protect
those headers, or build physically separate loops for fault containment. Each
machine automatically isolates on failure. A standby train starts only if an intact
route, cooling and startup power exist; switching cannot ignore stored heat or
teleport heat across a destroyed pipe.

## Efficiency progression

The starter layout targets **40% net**, after electrical auxiliaries. Recovery
capacity is measured against the full design flow of the dispatched train bank,
not instantaneous throttled flow. This avoids gaining an efficiency upgrade merely
by toggling demand or cooling. Automatically idle spare trains do not dilute the
recovery ratio. Starting another train must never reduce net output: dispatch
compares candidate banks before admitting additional heat.

For the first balance study, one heater, train or recuperator handles 100 MWth.
These normalized ratings scale with the eventual reactor tier. Define:

- `D` is the number of duty trains selected automatically to maximize supported
  net output; ties use fewer machines. Candidate counts are bounded by offered
  heat, heaters, trains and available recovery capacity.
- `R = healthy recuperator capacity / (D × 100 MWth)`.
- Recovery target `η = min(0.78, 0.40 + 0.40 × (1 − 2^−max(0, R−1)))`.
- Actual efficiency is capped by matched hot-end equipment and temperature, then
  derated for a warmer compressor inlet. Missing required equipment gives zero
  output; insufficient recovery capacity also limits accepted thermal flow.

| Recuperator capacity per duty train | Recovery target |
| --- | ---: |
| 1× | 40% |
| 2× | 60% |
| 3× | 70% |
| 4× | 75% |
| 5× | 77.5% |
| 6× | 78% |

Six units per duty train reach the requested **78%** cap with exotic hardware.
Adding the second recuperator is useful with ordinary hardware; reaching the
highest targets needs a compatible heater and train as well.

| Matched equipment class | Net ceiling | Electrical auxiliaries / accepted heat | Required turbine inlet |
| --- | ---: | ---: | ---: |
| Standard | 55% | 8% | 650°C |
| Improved | 66% | 7% | 1,000°C |
| Optimized | 74% | 6% | 1,600°C |
| Exotic | 78% | 5% | 2,200°C |

Equipment class is the weakest required heater/train capability, not a global
research buff or a choice the player can use without its machinery. Recuperator
pressure/temperature eligibility must also match. Higher-temperature primary
supply must actually exist. The intermediate classes currently reuse the base
and premium concept silhouettes; dedicated intermediate artwork is not authored.

These are **Arcane gameplay targets**, not solved sCO₂ cycle predictions. At
650°C hot / 45°C cold, Carnot efficiency is only about 65.5%. The new 78% net
target needs a much hotter exotic source: 2,200°C in this balance calculator,
where 83% gross plus 5% auxiliaries yields 78% net below the Carnot ceiling.
This is a fictional materials/gameplay target, not a real sCO₂ prediction. Normal reference pressures
remain 22 MPa HP and 8 MPa LP; compression and pressure allocation are abstracted.

## Redundancy and power examples

All examples below offer 100 MWth per duty train, use nominal cooling, and include
auxiliaries. A normal cooler rejects 60 MW at its reference conditions.

| Installation | Offered heat | Net electricity |
| --- | ---: | ---: |
| 1 heater, 1 train, 1 recuperator, 1 cooler | 100 MWth | 40 MWe |
| Improved heater/train, 2 recuperators | 100 MWth | 60 MWe |
| Exotic heater/train, 6 recuperators | 100 MWth | 78 MWe |
| 2 heaters, 2 trains, 2 recuperators, 2 coolers | 200 MWth | 80 MWe |
| 3 of each, with only 2 trains dispatched | 200 MWth | about 103.43 MWe |
| Last installation after its worst single module loss | 200 MWth | at least 80 MWe |

The last bank has one spare heater/train; all three recuperators contribute heat
recovery. Losing a recuperator reduces efficiency to the basic two-per-two ratio,
while preserving 80 MWe. Losing a train or heater activates its spare. Cooling
remains sufficient after losing one of its three units. This is a steady-state capacity guarantee after successful failover, not
uninterrupted output during the starting transient. Batteries cover that interval.
It assumes intact connected headers and adequate external startup/containment power. A common
pipe, reactor or electrical bus remains a common failure point.

The terminal should show **current net output, maximum supported output, recovery
ratio/efficiency ceiling, bottleneck(s), duty/standby counts and worst single-module
loss output**. Provide a simple diagnostic such as “Add cooling: 18% thermal flow
limited” or “Extra train is standby: heater capacity limits output.” Default auto
operation handles dispatch and failover; no per-pipe flow balancing UI is needed.

## Space and atmosphere cooling

These components are heat rejectors. Supercritical CO₂ does not condense in this
cycle, so a steam condenser is not the right physical component. Both variants
have the same CO₂ LP duplex pose and can replace each other or form parallel banks.

**Atmospheric cooler:** fin stack, two pitched solid fans, protective grille,
mounting spiders, plenum and open exhaust. Effective capacity scales with local air
density, clamped to its nominal rating. In vacuum its forced-convection capacity is
zero; do not charge fan power for useful vacuum cooling that cannot happen.
Reference air is 25°C; a 20 K approach gives 45°C compressor inlet. Hotter air raises
the cold-end temperature and reduces conversion efficiency. Thin air limits flow
capacity independently of the temperature penalty. More fans cannot cool below
ambient or bypass the temperature limit.

**Space radiator:** broad two-sided dark tiles, heat-distribution pipes, framed
panel substrates and a pump cassette. No fans or former utility/emitter bank.
Reference radiator surface is 35°C, allowing a 10 K approach to the 45°C cold inlet.
Capacity follows exposed area/sky view and normalized `(Tpanel⁴ − Tsink⁴)`. Blocking
both faces or a sink as hot as the panel gives zero usable rejection. In atmosphere
it can still radiate, but warm surroundings reduce its advantage; it receives no
fan bonus. Solar heating and detailed directional occlusion remain future runtime
integration work, not validated environment measurements in this study.

A mixed bank sums each healthy unit's environmentally valid capacity; hardware
positions and local conditions determine contribution. There is no global free
“space mode,” and high plant efficiency still needs enough waste-heat rejection.

Model-sized MW/GW/TW heat rejection remains an explicit **Arcane abstraction**.
The radiator's gameplay rating is not calculated from its visible area as if a
few square metres could conventionally reject terawatts near room temperature.
Temperature/exposure scaling supplies engineering trade-offs without claiming
physically realistic compact radiators.

## Energy and flow accounting

At a steady operating point, accepted heat becomes net electricity plus rejected
heat. All auxiliaries are included once: `gross electricity − auxiliaries = net`;
auxiliary energy returns as low-grade heat. Basic 100 MWth gives 48 MW gross,
8 MW auxiliaries, 40 MW net and 60 MW rejected. Premium six-recuperator operation
at the same heat gives 83 MW gross, 5 MW auxiliaries, 78 MW net and
22 MW rejected. Standalone converts 100 MWth into 20 MWe and 80 MW rejected.

Accepted heat is the minimum of offered supply, healthy heater/train/recovery
capacity and available cooling divided by `(1 − efficiency)`. Unaccepted heat is
not another radiator output or electricity source: it remains upstream, throttles
new reactor production, and requires finite storage/fault handling for residual
reaction heat. Startup/shutdown transients cannot erase it.

Run from the repository root:

```sh
python ArcanePower/tools/thermal_budget.py
python ArcanePower/tools/thermal_budget.py --heat-mw 200 --heaters 3 --trains 3 --recuperators 3 --coolers 3
python ArcanePower/tools/thermal_budget.py --stage exotic --recuperators 6 --cooler space
python ArcanePower/tools/thermal_budget.py --cooler atmosphere --density 0
```

The executable checks modular scaling, limits, diminishing returns, temperature
eligibility, environment behavior and single-module-loss accounting. It is a design
calculator, not production runtime or a real-fluid solver.

Provisional reactor heat ratings stay 25 GWth / 250 GWth / 2.5 TWth, preserving
10 GW / 100 GW / 1 TW starter net output. At 20% standalone these give 5 GW / 50 GW / 500 GW. At 78% Brayton the mathematical
outputs would be 19.5 GW / 195 GW / 1.95 TW, only where the source temperature
and installed hardware qualify. Do not assume every fuel can reach the exotic
class. Existing battery bank transfer caps and native recharge losses remain.

## Models and connections

Production work now lives in [arcane-thermal-models.blend](assets/arcane-thermal-models.blend):
31 main sources (eight machines, the reactor housing variant, 21 typed conduit
pieces and one reactor transition). Bases and two real grid assemblies pass the
geometry/interface gate. Other-machine geometry and texture refinement is held
while the reactor manifold repair is completed; their older hot-end stencils
also still need the new temperature targets. LODs/build stages are not being
polished ahead of main models.

The reactor variant preserves its 5×5×3 Blender-cell envelope and original
controller receivers, collars, glass, pillars and ring well. Four pairs of compact
primary pipe heads sit behind four original curved armor sectors, beside both
controller bays. Each sector is split into two solid leaves with its native UVs;
the leaves inset 0.36 m and slide 0.125 rad around the drum under neighbouring
armor. Two-stage telescopes then extend 1.65 m. Standalone state fully hides the
pipes; Brayton state exposes them. This is a saved mechanical rig, not installed
mode-switching/runtime animation.

The original lower band centres at Z=−2.33 m, 0.17 m above the nearby grid-cell
centre. A real 1×1×1 primary transition moves its inlet down to the pipe kit's
standard outlet elevation. This keeps the original curved armor height and grid
placement. The transition, unused-port caps and routed pipe blocks are included
in the assembly bill; no off-grid pipe placement is assumed.

The flat external cassettes were rejected and remain only in an undo checkpoint.
The accepted original reactor/battery files remain unchanged. The new variant
is maintained by `build_reactor_thermal_manifolds.py`. The focused
[curved-cover audit](validation/thermal-models/curved-manifold-audit.json) checks
closed-pipe occlusion, split solids and 14 deployment positions; close review
uses 1.8/2.4/3.0 m actual UI views. Native collision/subpart export and in-game
switching remain later integration gates.

The earlier concept baseline follows for reference.

[arcane-thermal-concepts.blend](assets/arcane-thermal-concepts.blend) holds editable
component concepts, four whole-plant studies (atmosphere/space, starter/premium),
a component lineup and a three-train expansion bank with two duty units and one
standby. The full premium plant's single recuperator is a **topology/hardware
study**, not a claim that one recuperator achieves 78%; its floor labels identify
the unlocked ceiling. The expansion bank demonstrates generation/header assembly;
its external ports connect to heater/recovery/cooling banks outside that scene.

| Component | Blender X×Y×Z large-grid cells |
| --- | --- |
| Train, standard/premium | 5×3×2 |
| Primary heater, standard/premium | 3×3×3 |
| Recuperator, standard/premium | 3×2×3 |
| Atmospheric cooler | 3×2×3 |
| Space radiator | 3×2×3 |
| Duplex straight, elbow and tee | 1×1×1 |

Native SEUT materials/UVs, seated fasteners, hard armor edges and single-segment
chamfers remain the style contract. Functional pipe/fan curvature is preserved.
The tee and shared train headers have actual connected hollow bores. No magnet,
electrode or separate cold-utility interface remains in the current component set.

| Circuit | Upper H | Lower C |
| --- | --- | --- |
| Primary | reactor → heater | heater → reactor |
| HP CO₂ | heater → recuperator bypass → turbine | compressor → recuperator working leg → heater |
| LP CO₂ | turbine → recuperator working leg → cooler | cooler → recuperator bypass → compressor |

Port poses/types/roll are in `validation/thermal-concepts/models.json`; routing
records are the four environment/grade `*-layout.json` files. Concept conduit
markings show primary service. The separate production sources now provide
typed variants and a complete grid kit; game exports/runtime remain separate. Do not connect HP to LP or primary through a generic tee.

The accepted reactor and battery are read-only visual references. The concept external
extraction head is obsolete; the production variant uses the hidden curved-panel
manifolds described above. Existing sockets, collisions, pillars, glazing and ejection route remain
protected. Real conduit block bills and manifold seating are now authored in the production
source. Native definitions, collision, construction stages, LODs and game exports
remain production gates.

## Runtime ownership and controls

Use server-owned finite per-block MJ stores, not an aggregate duplicated network
store. Transfer only what the receiver accepts. Damaged/hostile/disconnected
hardware cannot contribute to capacity; reject pipe type mismatches. Splits,
merges, reloads, blueprints and projectors cannot duplicate heat or stored charge.

Current `Motion.Heat` is a normalized hazard value, not a temperature/MJ store.
Fuel burn must eventually follow actual thermal production, with controller fuel
efficiency applied once. Retain 8/9/9.9 minute current full-load endurance intent
and deliberate migration of direct-electric reactors. Preserve the irreversible
125% critical latch and fuse; converter loss must not pause runaway or erase heat.

Controls: enable, load target, automatic dispatch, per-machine isolation and
controlled/emergency shutdown. Grid/battery power starts cooling and compressors
before heat admission. The earlier 2% primary rating for eight seconds remains
only a provisional startup budget; verify actual native sink delivery and avoid
simultaneous bank startup spikes. Failover also needs that power. Preserve
containment priority and its real emergency reserve.

When demand, cooling or topology drops, throttle new heat, then handle residual
reaction and trapped heat explicitly. No-demand/full-battery operation cannot
continue generating unconsumed electricity. Verify source/sink integration,
fuel exhaustion, blackout, module loss, save/load, grid splits/merges and multiplayer
in a separate runtime prototype before changing production definitions.

## Current verification

The saved study has eleven component concepts and current atmospheric/space,
base/premium layout scenes. Seventy-five actual Blender UI captures cover 25
joint/detail targets at 1.8/2.4/3.0 m. Geometry, typed connections, fan clearance,
modular/environment energy checks, solution build and save/reload checks pass.
Production reactor/battery source hashes are unchanged. See the current
[review record](validation/thermal-concepts/REVIEW.md),
[geometry audit](validation/thermal-concepts/audit.json) and
[energy examples](validation/thermal-concepts/energy-budget.json).
