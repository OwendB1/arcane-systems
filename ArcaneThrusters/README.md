# Arcane Thrusters

Arcane Thrusters is a Space Engineers 1 propulsion pack in development. The design uses ordinary hydrogen in two states. A ship can fly on cold hydrogen, or spend heat and electricity to charge it into plasma for higher thrust. A carrier can do the charging for a small craft. Charger throughput determines the thrust a ship can sustain. Stored plasma determines how long it can exceed that rate.

**Playable development build.** The pack has ten engine blocks, two plasma tanks and one large-grid recovery charger. A loaded small-grid miner has charged from a carrier, lifted on plasma boost and returned on hydrogen in offline survival and on a private dedicated server with an independent client. Enable the companion Arcane Power development build for recovery charging and Drive Priority. [Flight measurements](#propulsion-acceptance)

### Grid roles

Install the reactor, Brayton circuit and recovery charger on a **large-grid carrier or station**. A **small-grid shuttle** carries a receiving tank, batteries for confinement, and a dual-mode thruster. It departs with a finite charge. A docked connector transfers propellant between the two vessels. Reactor heat stays on the carrier's circuit.

### Engine roster

Open **G → Arcane Systems** and select the Ship Main tile marked **+**. Scroll through eight large-grid engine variants or switch to small grid for the two Shuttle Main mounts. The plasma tank and recovery charger have their own entries.

| Engine | Status | Installation |
| --- | --- | --- |
| Small-grid shuttle main | 480 kN on ordinary hydrogen, up to 720 kN with plasma boost. | Exposed rear mount or fully enclosed hull mount. Both occupy 3 × 3 × 5 small cells and use a separate tank. |
| Large-grid ship main | 7.2 MN on hydrogen, up to 10.8 MN with plasma boost. | 3 × 3 × 3 large cells, one bell and a centered rear conveyor. |
| Vacuum Triple | Hydrogen rocket tuned for orbital transfers. | Dedicated hydrogen manifold and three vacuum bells. Exposed (3 × 3 × 3) and hull (3 × 3 × 4) mounts. |
| Atmospheric Lander | Hydrogen rocket tuned for planetary lift and braking. | Short single bell, exposed or hull-mounted. Both occupy 3 × 3 × 2 large cells. |
| Drive Priority thermal main | Thrust override diverts reactor input. At full supply, 1 GW and 5,000 L/s hydrogen deliver 12 MN. | Exposed mount 3 × 3 × 3 large cells, hull mount 3 × 3 × 4. Both have three bells, a rear conveyor and a separate hot/return flange one cell to its side. |

The recovery charger occupies 3 × 1 × 1 large cells. Its duplex flange connects to Arcane Power and its conveyor end serves the hydrogen feed and separate plasma storage. [Recovery charger model](assets/arcane-recovery-charger.blend) · [In-game view](assets/recovery-charger-review.png)

### Reading the exhaust

All ten mounts emit one plume per bell. Ordinary hydrogen burns ice blue. The dual-mode ship and shuttle mains turn violet around a pale cyan core as they spend plasma. They return to blue when the separate plasma tank runs dry. Drive Priority glows amber with a cream core while its Brayton circuit supplies heat and its tank supplies hydrogen. These colors identify drive modes in game.

The exhaust fills the bell opening. Its glow sits four percent of a nozzle diameter behind the lip, follows the rim as the bell steers, and narrows into the first compression cell downstream. At low throttle the jet is short and diffuse. At full throttle it extends about eight nozzle diameters past the lip. A translucent blue, violet or amber jet surrounds a row of bright compression points. The points fade downstream into a broader, gently wavering tail. The shape draws on the close-up of ESA’s variable-thrust engine test. In dense air the jet stays narrow and its diamonds are bright. As local atmospheric density falls, the downstream envelope widens and the diamonds soften. The exhaust keeps the same width at the bell lip. A faint compression pattern remains in vacuum as a stylistic choice. [Hot-fire footage](https://www.esa.int/ESA_Multimedia/Videos/2024/08/New_variable_engine_undergoes_dynamic_testing)

Exposed large-grid bells steer the plume with their gimbals. The visible tip does not measure the native exhaust damage range. The effect draws within 700 m of the engine. Remote clients use the existing access-filtered, once-per-second drive readings for boost and thermal color.

### Choosing a large-grid hydrogen engine

The **Vacuum Triple** has three long bells with smooth skirts and blue interior rings. On the mounting face, a centered hydrogen conveyor feeds a collector and three pump inlets. The three bolted covers provide service access. Drive Priority carries the twin-bore Brayton flange beside its hydrogen conveyor. The **Atmospheric Lander** has a shorter, narrower single bell on the ship main’s pump deck. Both specialists take hydrogen through the rear conveyor. Their fuel converters use the ship main’s settings. Fuel draw at full override follows the available thrust. [Exposed nozzle comparison](assets/environment-engines-review.png) · [Block definitions](src/Data/CubeBlocks/EnvironmentEngines.sbc)

| Rated thrust | Vacuum or airless moon | Half atmospheric influence | Full atmospheric influence |
| --- | ---: | ---: | ---: |
| Vacuum Triple | 8.64 MN | 7.20 MN | 5.76 MN |
| Ship Main | 7.20 MN | 7.20 MN | 7.20 MN |
| Atmospheric Lander | 5.76 MN | 7.20 MN | 8.64 MN |

These are initial balance values. Space Engineers interpolates the specialists’ available thrust continuously with local air density. Actual surface density varies by planet and elevation. Both mounts of an engine use the same curve. [Atmospheric exposed model](assets/arcane-atmospheric-lg-open.blend) · [Atmospheric hull model](assets/arcane-atmospheric-lg-hull.blend)

**Offline survival burn.** Twelve fueled rigs tested both mounts of each specialist in vacuum and at two elevations on an Earthlike planet. In vacuum, the triple delivered 8.64 MN and the lander 5.76 MN. In the denser air sample they delivered about 5.82 MN and 8.58 MN respectively. At the higher test elevation they delivered 6.76 MN and 7.64 MN. All twelve drew hydrogen from their attached tanks.

## Propulsion design

| Part | Player behavior |
| --- | --- |
| Recovery charger | Connect one large-grid charger to a single duplex Brayton circuit and the hydrogen supply. It transfers available heat into the hydrogen and draws grid electricity to ionize it. When a tank is full or either input runs short, charging falls to the amount the destination can accept and the inputs can support. |
| Plasma charge tank | Large- and small-grid tanks draw standby power plus a holding load that grows with stored plasma. A docked craft can use shore power. After undocking, its battery or generator must sustain the field. A power shortfall starts a visible hold timer. Once it expires, plasma gradually cools back into hydrogen. Restoring field power preserves the remaining charge. |
| Dual-mode main thruster | Hydrogen supplies baseline thrust. Plasma supplies higher peak thrust from the same nozzle. The drive draws from live production and stored charge. When charge runs out, available hydrogen supports baseline thrust, including dampener braking. The cockpit shows plasma burn time at current throttle, accounting for ongoing production. |
| Docked transfer | A carrier or station charges its own tanks and supplies connected shuttles. A shuttle needs a local tank, propellant path, and field power to leave port. It can fly its mission without an onboard reactor. |
| Drive Priority thermal main | A capital ship can dedicate one reactor outlet to a thermal main drive. Diverting paid reactor input to propulsion reduces the electricity available from that outlet. Its recovery-only counterpart uses heat already produced during generation. |

### Integration with Arcane Power

Arcane Power owns four independent circuit heat balances. Recovery may intercept new cooling load before the radiators reject it and draw down retained heat during cooldown. Power debits only the connected circuit, once, for the plasma actually produced. A circuit producing 10 GW of cooling load with one charger accepting 250 MW leaves 9.75 GW for its coolers. When charging stops, the full 10 GW returns while generation holds steady. Standalone Aether uses integrated cooling. The Brayton loop's CO₂ and the reactor's paid fuel reserve stay inside Arcane Power. [Power balance](../ArcanePower/THERMAL-POWER.md) · [Runtime accounting](../ArcanePower/THERMAL-RUNTIME.md)

### Flying a charged ship

1. Fit the charger’s duplex end to a complete carrier Brayton circuit. Feed ordinary hydrogen to the opposite conveyor end and connect a separate plasma tank. Enable Stockpile on the charger to draw hydrogen into its feed buffer. One charger can convert 250 L/s at 5 MW of ionizer power and 250 MW of recovered heat. A hot shutdown circuit can continue charging while retained heat lasts.
2. Lock the shuttle connector, enable Stockpile on its plasma tank to fill it, then turn Stockpile off before flight. Carry ordinary hydrogen and battery power. A full 50,000 L shuttle tank needs 100 kW of field power plus its native tank load.
3. Fly on hydrogen as usual. Boost ramps in above 90% of the engine’s current effective hydrogen rating. At full thrust a shuttle main adds 240 kN at 500 L/s. A ship main adds 3.6 MN at 7,500 L/s. With one full shuttle tank, one unmodified shuttle main has about 100 seconds of full boost. That full 100-second burn also requires about 38,560 L of ordinary hydrogen at stock settings. A single 15,000 L hydrogen tank sustained 38.9 seconds on the offline bench. At lower throttle the engine can brake on hydrogen alone.
4. On a cockpit screen or LCD, select **Scripts → Arcane Plasma Endurance**. It shows added thrust, draw and time remaining at the measured net withdrawal rate. Other engines and simultaneous charging affect the estimate. The terminal and blue bell ring follow the same server readings. The server samples once per simulation second. [In-game endurance display](assets/plasma-endurance-review.png)

## Delivery checklist

- [x] **Foundation.** Create the mod folder, define the plasma resource, and package validated mod data with the same command locally and in CI.
- [x] **First tank modeling pass.** Build SEUT mains for the carrier tank (3 × 1 × 1 large cells) and shuttle tank (5 × 3 × 3 small cells). Use Arcane Power's native materials and grid-specific conveyor faces. Review both service and conveyor faces at 1.8, 2.4 and 3.0 m. Each conveyor empty has a 90° roll around its outward local Z axis. [Tank mains](assets/arcane-plasma-tanks.blend) · [Procedural source](assets/build_plasma_tanks.py)
- [x] **Prepare tank prototypes for the game.** Each tank has a native main, six collision hulls, two distance LODs and three weld stages. Both conveyor empties retain the quarter-turn in the compiled MWM. Both ends support two-way transfer, with small conveyor ports on the shuttle.
- [x] **Prove storage and transfer in SE.** Load both tanks in offline survival, transfer plasma through locked connectors, disconnect mid-fill, then save and reload. The measured balances are recorded below.
- [x] **Implement powered confinement.** Verified shore power, battery handoff, an outage shorter than the hold time, sustained cooling, hydrogen overflow and a mid-outage save/reload in offline survival. [Confinement test](#powered-confinement)
- [x] **Model the standalone shuttle engine.** Review the castings, mount hardware, conveyor, bell interior, packed textures and two distance models. [Model and review](#standalone-shuttle-engine)
- [x] **Package both shuttle mounts.** Compile collision, two LODs and three weld stages for each. Install the hydrogen definitions and verify the hull seal against exposed and partial-weld controls. [Hull pressure test](#hull-mounted-shuttle-engine)
- [x] **Build both large-grid engines.** Compile and place all four variants, check hull closure and run a hydrogen burn on both ship mains. [Models and measured results](#large-grid-engines)
- [x] **Recovery charging.** Exercise running and shutdown circuits, competing chargers, exhausted heat, a cold circuit and a full destination.
- [x] **Dual-mode flight.** Verify both grids and mounts, hydrogen fallback, dampeners, override, conveyor isolation and Ship Core Framework modifiers.
- [x] **Loaded multiplayer flight.** Charge through the connector, undock on battery power, lift the ore load and redock on hydrogen with an independent client observing.
- [x] **Drive Priority.** Connect the drive to a running Brayton plant and measure turbine output surrendered under thrust override.
- [x] **Shuttle construction and exhaust.** Exercise native weld stages and compare in-line and lateral exhaust damage.
- [x] **Exposed large-grid gimbals.** Verify articulated subparts, compare neutral and trimmed flights, and steer from a piloted cockpit.
- [x] **Survival sortie and plume checks.** Charge an ore-loaded shuttle from empty, fly and redock. Check each engine mount at two throttle settings and compare the same lander in dense air, thinner air and vacuum.
- [x] **Distance models.** Inspect both mounts of all five engine families on either side of both authored LOD distances.

### Propulsion acceptance

| Test | Observed in SE1 |
| --- | --- |
| Recovery and cooling | On a hot shutdown circuit two chargers each reached 250 L/s at 5 MW. Together they converted 825 L of hydrogen into 825 L of plasma before production stopped. On a running plant a charger reduced the required cooling from 200 GW to 199.75 GW. Disabling it restored the full load. A full 500,000 L destination left the charger’s feed untouched. On a cold circuit, two powered chargers each retained their 8,000 L feed and produced zero plasma over ten seconds. |
| Plasma boost | Both shuttle and ship main mounts burned on hydrogen and plasma. A disconnected tank kept its charge. With Ship Core Framework applying 1.25× force and 1.1× efficiency, the shuttle produced 600 kN native thrust plus 300 kN boost at 625 L/s. Depletion preserved the native modifiers. |
| Loaded miner | A full iron ore hold brought the miner to 18,299 kg in 9.81 m/s² gravity. The dedicated server charged the shuttle from zero at about 250 L/s. Its 483.33 L departure charge took about two seconds of active charging, required 0.968 kW of confinement power at departure and supplied roughly 0.97 s of full boost. The independent client saw confinement, boost, depletion and the return connector lock. The server recorded a 50.14 m climb and a hydrogen-powered return. The fixture supplied retained heat in the saved reactor and used a scripted flight controller. |
| Full-tank offline sortie | One recovery charger on a running Helion carrier filled the docked shuttle from zero to 50,000 L in 200 seconds of active charging at 250 L/s and 5 MW. The 18,299 kg ore-loaded miner launched with 15,000 L of hydrogen, climbed 50.15 m in Earthlike gravity, braked and relocked after 29.0 seconds. At lock it had 9,639 L of hydrogen and 48,150 L of plasma. This short, scripted lift used 3.7% of the plasma tank. On the same planetary stand an earlier Empyrean run stopped charging at 10,883 L and lost its dock. Carrier cooling and a stockpiling charger with a replenishable hydrogen feed matter for sustained charging. |
| Sustained full boost | Two unmodified small-grid mains started at full override with 50,000 L of plasma each. The 15,000 L hydrogen supply emptied after 38.9 s. Thrust stopped with 30,558 L of plasma still aboard. The 500,000 L hydrogen supply sustained boost for 100.0 s, consuming 38,560 L of hydrogen and all the plasma. Native 480 kN thrust continued after depletion. |
| Endurance display | A separate, longer multiplayer burn drew about 500 L/s. The client showed 3, 2 and 1 seconds remaining before hydrogen fallback. The LCD rendered 240 kN and 500 L/s at full boost offline. An independent client displayed 124 kN and 258 L/s across a partially boosted sampling interval, then returned to hydrogen. The terminal reports the previous sampling interval, so boost can still appear briefly after the native tank reaches zero. |
| Drive Priority | Both the exposed and hull mounts delivered 12 MN at full override on a running Brayton circuit. In the offline hull test, the connected tank lost 5,000 L in 60 simulation frames and the reactor reported 1 GW diverted. Turbine output was 199.2 GW during the burn and returned to 200 GW after release. Hydrogen draw and reported thrust returned to zero. The hull burn used a static test stand. |
| Fuel-colored exhaust | In offline survival the exposed ship main showed a short blue plume at 15% override, full blue at 7.2 MN, violet at 10.8 MN, and blue again after plasma depletion. An oblique close-up of the ship main showed the jet starting across the inner lip. The trimmed Drive Priority triple showed three rim-sized amber sources aft and a 12 MN burn from the side. Closing its hydrogen supply extinguished the plume at full override. Releasing the override also extinguished it. [In-game comparison](assets/drive-plumes-offline.jpg) |
| Plume coverage | All ten engine mounts fired at 15% and 100% override in offline survival. The 40 side and aft views showed exhaust at the bell openings, visible rings and no visible exhaust through the hull casings. The blue low-throttle jet was faint against the starfield. [All ten mounts](assets/engine-plume-mount-check.jpg) |
| Atmospheric exhaust | The same Atmospheric Lander at full override produced 8.58, 7.64 and 5.76 MN at measured Earthlike air densities of 0.979, 0.652 and 0. Its bright, narrow shock pattern softened into a broad blue jet in vacuum. The three captures use the same camera framing on a restrained test grid. [Altitude comparison](assets/plume-atmosphere-check.jpg) |
| Shuttle construction and exhaust | Both mounts advanced through all three construction meshes. In a burn test, armor in the plume fell from 100 to 50 integrity while the lateral sample stayed at 100. Exact clearance depends on the installation. |
| Nozzle steering | With a 7.2 MN native burn, neutral had less than 0.001 m/s of lateral speed and zero angular speed. After 20 simulation frames the identical ship at 2° trim had 1.09 m/s lateral and 0.80 rad/s angular speed. The piloted cockpit reached 2° on the single bell. The triple’s six subparts also followed a 1.5° pitch and −1° yaw trim. |
| Vacuum Triple rear assembly and icons | Both mounts from the development ZIP delivered 8.64 MN in offline vacuum burns. A fully welded hull mount sealed the test chamber. The exposed mount and 75%-welded hull mount leaked. The exposed bells cleared the block boundary by at least 40 mm across the sampled steering poses, with a minimum projected inter-bell gap of 119 mm. The SE1 build menu displayed the model-rendered icons. [Rear assembly comparison](assets/environment-engines-review.png) · [Build-menu icons](assets/block-icons-review.png) |
| Camera distance | In offline survival, all ten mounts retained their silhouettes in 50 fixed-field-of-view exhaust-side captures. Both shuttle mounts were sampled at 5, 30, 40, 80 and 100 m around the native 35 and 90 m LOD settings. All eight large-grid variants were sampled at 16, 90, 110, 240 and 280 m around the 100 and 260 m settings. The bell rings become faint at the farthest distances. [Distance review sheet](assets/engine-mount-distance-review.jpg) |

The multiplayer replay used the extracted development ZIPs and a loopback dedicated server running SE 1.211.18. Pulsar and Magnetar loaded the unpublished mods through private test profiles. For the LCD replay the fixture refreshed the game’s text-surface script registry after the private profile loaded its scripts. Normal world-mod loading performs that discovery itself.

## Development pipeline

The packaging command uses the checked-in game assets. To rebuild the three exhaust sprites, run `python3 ArcaneThrusters/assets/build_plume_textures.py` on the Arcane Power texture workstation. To rebuild the native models on the Arcane Power authoring workstation, run `python3 ArcaneThrusters/tools/build_tank_models.py` for the tanks, add `--charger` for the recovery charger, or run `python3 ArcaneThrusters/tools/build_engine_models.py` for all ten engine models. Each build opens disposable Blender processes, uses Power's weld-mesh and LOD helpers, and compiles with SEUT, Havok and MWMBuilder. The game's model importer checks triangle counts, embedded collision, LOD paths, texture references, conveyor transforms and each engine’s exhaust transforms before installation into `src/`. MWMBuilder flags degenerate render triangles on some meshes, principally the distance LODs. The acceptance table records the models sampled in the game camera.

With MDK pointed at the installed SE1 binaries, run these commands from the repository root.

```sh
dotnet build arcane-systems.sln
python3 ArcaneThrusters/tools/package_mod.py
python3 ArcanePower/tools/package_release.py --preview
```

The Power preview command writes the matching companion ZIP under `ArcanePower/.cache/release/`. The packager checks mod metadata, SBC XML, the plasma gas ID, all thirteen block definitions, their main, weld and distance models, the engines’ grid dimensions and airtight flags, thirteen dedicated build-menu icons, seven model textures, three exhaust sprites and their transparent materials, steering subparts and propulsion scripts. The runtime includes 126 native MWM files. It writes `ArcaneThrusters/artifacts/ArcaneThrusters.zip` with the contents of `src/` at the archive root. For a local test, extract that ZIP into a local mod folder named `ArcaneThrusters` and enable it in the test world.

To regenerate the 13 build-menu icons, run `python3 ArcaneThrusters/tools/build_block_icons.py`. The renderer frames each block’s authored main meshes, and Arcane Power’s texture converter produces transparent premultiplied BC7 sRGB icons with a complete mip chain. Drive Priority is shown from its reactor-connection side. [Block icon sheet](assets/block-icons-review.png)

The GitHub Actions workflow runs the packaging check on relevant pull requests and pushes to `main`, and supports manual runs. It retains the ZIP as a development artifact. [Packaging workflow](../.github/workflows/arcane-thrusters.yml)

## Standalone shuttle engine

The shuttle carries a separate plasma tank and feeds the engine through one native small conveyor on its mounting face. The engine occupies **3 wide × 3 high × 5 long small-grid cells** (1.5 × 1.5 × 2.5 m). Four mounting pads surround the inlet. The smooth flared bell and offset curved duct follow the supplied Raptor 3 silhouette. The pump cover, valve manifold and cable runs stay exposed for inspection.

The close model includes tapered suspension links with pin bores, a scroll housing with raised cover webs, a stepped valve casting, a clamp latch and seven recessed injector wells. A dedicated emissive material forms the blue ring inside the bell. The drive controller brightens it during plasma boost. [Blender model](assets/arcane-shuttle-nozzle.blend) · [Detail views](assets/shuttle-engine-review.png)

| Native mesh | Switch distance | Triangles |
| --- | ---: | ---: |
| Main | Close view | 37,898 |
| LOD1 | 35 m | 16,528 |
| LOD2 | 90 m | 6,876 |

The bell uses a cylindrical UV unwrap with separate regions for the exterior and liner. A 2048 × 1024 color/metal and normal/gloss pair carries the stencil, brushed exterior, heat-tinted lip and fluted bore. The cast housings use a separate 512 × 512 pair. The blue emitter reuses the tank field textures. The LODs rebuild the bell with 40 and 24 evenly spaced sectors, respectively, preserving the liner, stencil and emitter as small hardware drops out.

**Verification.** Reviewed the model in Blender at 1.8, 2.4 and 3.0 m and compared the three detail levels from the same angle. Compiled all three meshes in a disposable SEUT/MWMBuilder export and read them back with the game's model importer. The importer confirmed the triangle counts, LOD distances, material references, mount-side conveyor and outward flame dummy. The final compile reported zero degenerate triangles. The packaged models now include collision and three weld stages. Flight measurements appear in the acceptance table.

**Rebuild.** The Blender generator uses Arcane Power's mesh and LOD helpers and the installed SEUT material libraries. The checked-in DDS maps are the inputs for a normal model rebuild. To regenerate those maps as well, run the first command before the second from the repository root.

```sh
python3 ArcaneThrusters/assets/build_nozzle_textures.py
blender -b --python-exit-code 1 -P ArcaneThrusters/assets/build_shuttle_nozzle.py
```

## Hull-mounted shuttle engine

Choose **Arcane Shuttle Main (Hull Mount)** for a pressure wall. Its square casing fills the same 1.5 × 1.5 × 2.5 m envelope as the exposed engine. The bell lip sits inside the exhaust face. A closed pocket at the opposite end surrounds the small conveyor port. Four sides and the rear accept adjacent blocks. The casing costs 30 extra steel plates. Choose **Arcane Shuttle Main (Exposed)** for external mounting on its four rear pads. Both retain the blue emitter inside the bell. [Hull model](assets/arcane-shuttle-hull.blend) · [Nozzle, conveyor and hull-fit views](assets/shuttle-hull-review.png)

**Pressure test, 21 November 2026.** Three powered small-grid armor chambers in offline SE1 each had one 3 × 3 opening. A vent and the room query sampled the chamber behind each engine. Results held across repeated simulation updates.

| Engine across the opening | Weld level | Room airtight | Vent can pressurize |
| --- | ---: | --- | --- |
| Hull mount | 100% | Yes | Yes |
| Exposed mount | 100% | No | No |
| Hull mount | 75% | No | No |

The flight measurements above use the same shuttle definitions.

To regenerate the hull after changing the exposed engine, then compile and validate both shuttle variants, run from the repository root.

```sh
blender -b ArcaneThrusters/assets/arcane-shuttle-nozzle.blend --python-exit-code 1 -P ArcaneThrusters/assets/build_hull_engine.py
python3 ArcaneThrusters/tools/build_engine_models.py --family shuttle
```

## Scripted nozzle steering

The four exposed large-grid engines accept trim from programmable blocks and server-side mods. All bells on a triple follow the same command. Use the standard SE terminal `GetProperty`, `GetValue<T>` and `SetValue<T>` methods. Check that `ArcaneGimbal.TravelLimit` exists and is positive before steering. SE registers terminal properties by block type, so a fixed or vanilla thruster can expose the IDs and return zero.

| Property ID | Type | Meaning |
| --- | --- | --- |
| `ArcaneGimbal.PitchTrim`, `ArcaneGimbal.YawTrim` | `float`, read/write | Script offsets in degrees. Positive pitch tilts vessel thrust toward the engine’s local Down. Positive yaw tilts it toward local Right. |
| `ArcaneGimbal.AppliedPitch`, `ArcaneGimbal.AppliedYaw` | `float`, read | Final pose after adding Custom Data trim, script trim and optional pilot input, then clamping each axis. |
| `ArcaneGimbal.TravelLimit` | `float`, read | Per-axis limit in degrees. Ship Main and Atmospheric Lander allow 2°. Vacuum Triple and Drive Priority allow 1.5°. |
| `ArcaneGimbal.DeliveredForce` | `Vector3D`, read | World-space force on the vessel in newtons over the last completed simulation tick. Includes native thrust and any paid plasma boost or thermal drive force. Zero on idle or unsupported engines. |

Write zero to release an axis immediately. Each axis also returns to zero after 120 simulation ticks without a write. This lets a depowered PB release the gimbal and preserves the pilot’s Custom Data settings across script restarts. Finite commands clamp to the engine’s range. Invalid numeric commands clear that axis. Multiple scripts writing the same axis share one command, with the latest write taking effect. Multiplayer client-side mods can read periodic snapshots. Writes belong on the simulation server. Force and script offsets expire on a client after two seconds without an update.

### Fly the lander assist

1. Paste the [lander-assist example](src/Examples/LanderAssist.cs) into a programmable block and compile it. The development ZIP includes the same file under `Examples/`.
2. Add `[Lander Assist]` to the names of one upright cockpit or remote control and the exposed lift engines you want it to steer. Use engines whose thrust points toward the controller’s Up direction. Mounting the gimbal below the loaded center of mass gives the sideways force leverage to level the ship.
3. For automatic leveling alone, set `FollowPilot=false` and zero fixed trim in each participating engine’s `[Arcane Gimbal]` Custom Data. Run the PB with `on`. It samples gravity and angular velocity every ten simulation ticks and steers the tagged engines while they produce thrust. Run `off` to release them.
4. Control descent speed and horizontal position with the pilot, dampeners or a separate controller. The assist commands pitch and roll through the nozzles. It leaves throttle and gyros to those other controls.

### Offline landing comparison

Across two paired trials in offline survival, the same 24,618 kg lander started each descent with 12.57 m of skid clearance, 4.00° of tilt and 2.00 m/s of downward speed. A separate speed controller held descent speed in both flights. The fixture measured horizontal displacement of the center of mass and hull angle from local vertical on the last tick before the pad collision impulse.

| PB setting | Touchdown tilt | Lateral drift | Descent speed |
| --- | ---: | ---: | ---: |
| Off | 3.99° | 13.43 m | 2.00 m/s |
| On | 0.03–0.04° | 5.50–5.62 m | 2.00 m/s |

The PB leveled this lander and reduced drift by 58–59%. A horizontal velocity remained after leveling. A precision landing still needs lateral braking. In separate offline burns the Ship Main reported 10.8 MN total at 7.2 MN native thrust, and Drive Priority reported 12.0 MN with zero native thrust. Both returned to zero on cutoff. [Reproduce the landing comparison](tests/landing/README.md)

## Large-grid engines

The **Arcane Ship Main** fits a 7.5 m cube. Four sleeved stays carry the exposed engine from its aft thrust plate. Twin turbopumps sit above the gimbal of its single flared bell. The exposed **Arcane Drive Priority** also fits a 7.5 m cube. Its three pumps sit directly beside short finned sockets on the rear manifold. The pumps and gimbals sit 2.5 m closer to the base plate than on the original four-cell prototype. The vacuum-style bells flare downstream of the throat clamp. Each measures 3.84 m from the start of the bell wall to the lip and 3.34 m across the rolled mouth. The hull mount is 10 m deep and uses shorter bells recessed behind its armor. Each smooth bell has a blue emitter, fluted liner and recessed injector wells. Both engines receive propellant from a separate tank. [Four mounting variants](assets/large-engines-review.png)

| Blender source | Exposed | Hull mount |
| --- | --- | --- |
| Ship main | [Single bell and thrust stays](assets/arcane-main-lg-open.blend) | [Single recessed aperture](assets/arcane-main-lg-hull.blend) |
| Vacuum Triple | [Exposed hydrogen manifold](assets/arcane-vacuum-lg-open.blend) | [Cased triple and service covers](assets/arcane-vacuum-lg-hull.blend) |
| Drive Priority | [Exposed vacuum bells and exchanger housings](assets/arcane-thermal-lg-open.blend) | [Three recessed apertures](assets/arcane-thermal-lg-hull.blend) |

In either exposed Blender model, open `Nozzle steering - Blender controls` and rotate a nozzle’s yaw control around local Z or its pitch control around local X. The bell, injector, emitter and exhaust marker follow the joint. The ship main allows ±2° per axis and each thermal nozzle allows ±1.5°. Across nine sampled poses per nozzle, the moving parts cleared the block boundary by at least 48 mm on the ship main and 40 mm on Drive Priority. The smallest projected gap between thermal nozzles was 119 mm. In game, exposed large-grid engines steer with a piloted controller on the same grid. To set a fixed trim, enter the following in the engine’s Custom Data. Angles are degrees. Hull-mounted and small-grid engines stay fixed. The visible plume follows the bell. SE keeps its native exhaust damage aligned with the block.

```ini
[Arcane Gimbal]
Pitch=1
Yaw=0
FollowPilot=false
```

Each hull model has a flush surround, slotted corner shields, sectional side armor and an unscaled rear large conveyor. The rear and four side faces accept neighboring blocks. The extra casing costs 100 steel plates in this prototype. Drive Priority also carries Arcane Power’s duplex flange with its hot/return orientation. Connect this flange to a running Brayton circuit and supply ordinary hydrogen through the rear conveyor. Set thrust override to request propulsion. The definition uses a nominal 1 N with zero native effectiveness so the throttle remains available. The script applies the delivered force and reports it in the terminal.

**Offline survival check, 21 November 2026.** Six large-grid chambers each had a vent and a single 3 × 3 opening. For both engine families, the game’s room query and the vent agreed that a fully welded hull mount sealed the opening. Both exposed mounts leaked, as did both hull mounts at 75% weld. Separate powered burn rigs placed a hydrogen tank directly against each ship main’s rear port. Both engines reached 7.2 MN. Each drew about 48,201 L across ten simulation seconds at full override. In the original placement test, both thermal mounts had no reactor supply and reported zero thrust. After the exposed thermal drive was shortened, a separate placement check measured its occupied span as 3 × 3 × 3 cells and found the former fourth cell clear.

The models use the shared Arcane bell maps, cast alloy, native armor and field material. Each has two authored distance meshes at 100 m and 260 m, a collision model and three weld stages. The four mounts were inspected from the nozzle and rear, with detail views at 1.8, 2.4 and 3.0 m. The exposed chamber is hollow at the injector plane so the wells remain visible through the bell.

Rebuild one family from the repository root. Use `main` for the ship main, `atmospheric` for the lander, `thermal` for Drive Priority, or `vacuum` for the hydrogen-fed Vacuum Triple. The engine compiler imports each native MWM and checks its mesh and collision data, texture references, LOD links, rear conveyor and the position, orientation and size of each exhaust dummy. [Model generator](assets/build_large_engines.py) · [Engine definitions](src/Data/CubeBlocks/LargeEngines.sbc)

```sh
family=main
for mount in open hull; do
    blender -b --python-exit-code 1 -P ArcaneThrusters/assets/build_large_engines.py -- "$family" "$mount"
done
blender -b "ArcaneThrusters/assets/arcane-${family}-lg-open.blend" --python-exit-code 1 -P ArcaneThrusters/assets/check_nozzle_travel.py
python3 ArcaneThrusters/tools/build_engine_models.py --family "$family"
python3 ArcaneThrusters/tools/package_mod.py
```

## Docked transfer test

On 20 November 2026, an offline SE1 survival fixture used a battery on each grid, a standard large-grid connector and a medium connector on the shuttle. The prototype capacities are **500,000 L** on large grid and **50,000 L** on small grid. The fixture seeded the carrier at 40% charge and enabled shuttle stockpiling after lock. It disconnected during transfer and disabled the carrier connector to prevent a second lock.

| Checkpoint | Carrier | Shuttle |
| --- | ---: | ---: |
| Before docking | 200,000 L | 0 L |
| Disconnected mid-fill | 199,000 L | 1,000 L |
| After save and reload, still disconnected | 199,000 L | 1,000 L |

The table rounds to the nearest litre. The largest per-tank change across reload was under 0.003 L. This exercise covers native storage, two-grid transfer and save persistence. This early fixture seeded the charge. The later miner flight used the recovery charger.

## Powered confinement

The prototype draws **2 W per litre of stored plasma**, plus the native tank load of 1 W at rest or 1 kW during transfer. At full charge the holding field alone takes **1 MW on large grid** or **100 kW on small grid**. A 20,000 L shuttle needs 40.001 kW at rest. The tank terminal shows field state, hold time during an outage, actual and requested power, and the recovered and vented litres from the latest cooling event.

An underpowered, switched-off or nonfunctional tank has **10 simulation seconds** of hold. After that, each additional second cools 1% of nominal capacity, capped at the plasma remaining. This gives 5,000 L/s on the carrier and 500 L/s on the shuttle. Each litre removed yields one litre of ordinary hydrogen. Accessible, working hydrogen tanks on a connected conveyor path receive what fits. The rest vents in the same tick. A grid-wide blackout can therefore lose all cooled gas even with spare tank capacity. Returning power freezes the loss at the remaining plasma level. These values are tuning choices for the first flight.

### Survival acceptance run

The carrier held 200,000 L and the shuttle held 20,000 L. Both started in Stockpile. A 15,000 L ordinary hydrogen tank on the shuttle started at 14,100 L. All values below are rounded to the nearest litre.

| Action | Shuttle plasma | Ordinary hydrogen | Observed result |
| --- | ---: | ---: | --- |
| Lock connectors and switch off the shuttle battery | 20,000 L | 14,100 L | Shore power supplied 40.001 kW to the shuttle tank. |
| Enable the battery and disconnect | 20,000 L | 14,100 L | The shuttle carried its own field load. |
| Switch the battery off for four seconds, then restore it | 20,000 L | 14,100 L | The hold countdown cleared with the charge intact. |
| Disable only the plasma tank, save six seconds into the outage, then reload | 20,000 L | 14,100 L | Four seconds of hold remained. |
| Keep the field off for three cooling ticks | 18,500 L | 15,000 L | The first 500 L fit. On the next tick 400 L fit and 100 L vented. The third tick vented all 500 L. |
| Restore the field, then cut power to the whole shuttle for a second outage | 17,500 L | 15,000 L | The restored field first held 18,500 L at 37.001 kW. After the next hold expired, 1,000 L vented while the hydrogen tank was offline. Battery power stabilized the remaining charge. |

After redocking, the carrier released 32,500 L to fill the shuttle to 50,000 L. Both tanks reported confinement throughout the 15-second observation. Their combined plasma balance before and after transfer agreed within 0.004 L.

The carrier and shuttle use the same confinement script. Native tanks own gas balances and the server debits plasma before crediting hydrogen. The tank saves its outage progress alongside the native fill level. The dedicated-server flight above checked the same field readings on an independent client.
