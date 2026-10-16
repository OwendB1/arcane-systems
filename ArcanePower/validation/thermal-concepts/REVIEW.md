# Modular Brayton: current concept review

15 October 2026. Official Blender MCP, existing Blender 5.2.1 LTS window.
Current file: `assets/arcane-thermal-concepts.blend`, saved and reopened with
`Thermal / Parallel train bank` active. The prior study is retained only as an
undo checkpoint and under `history-before-brayton-only/`; it is not current design.

Current component set: 11 editable concepts, 1,127 meshes. The former converter,
magnet equipment, utility ports and combined cooler are absent from active models.
Production reactor/battery Blender source hashes remain unchanged.

- Four connected whole-plant studies: atmosphere/space, base/premium hardware.
  Their premium floor markings show a ceiling, not an efficiency awarded without
  extra recovery modules. Each plant has five typed external thermal links.
- Three-train bank: two duty units and one standby, on two shared duplex headers.
  Both header bores actually connect through all three branches. External header
  ports connect to heat-exchanger/cooling banks outside this assembly scene.
- Separate atmospheric fan cooler and two-sided space radiator, with a 1.9 m
  engineer in `Thermal / Cooling comparison` and a full component lineup.
- 25 detail targets reviewed at 1.8/2.4/3.0 m: 75 actual UI images, fixed 48 mm
  lens and lighting/target per set. See `ui-reviews.json` and `contact-0.jpg`
  through `contact-8.jpg`. Current whole views are `ui-cooling-comparison.png`,
  `ui-parallel-train-bank.png`, `ui-lineup.png` and environment layout images.

Repairs found during the loop: cooler rear posts now reach their foundation;
controller moved clear of the pressure header onto a backed mount; HT text moved
onto the exposed cassette face. Shared headers use connected hollow geometry,
exact booleans with offset branch tessellation, and micron-scale cleanup for
coincident edges. Both mirrored headers and the tee pass closed-solid checks.

`audit.json` and `reload.json` pass envelopes, finite native UV/material references,
closed positive-volume components, full bolt/text/decal backing, port alignment,
flange necks, bypass separation, fan envelopes, four layouts and bank branches.
Fan shroud clearance remains ~79 mm and grille clearance ~224 mm. Checks do not
establish final mechanical fluid routing, collision, structural load ratings,
manufacturability, native model exports or runtime behavior.

`energy-budget.json` passes 24 reference cases plus focused modular, environmental,
invalid-input, temperature-gating and monotonic-dispatch checks. Examples per
100 MWth: starter 40 MWe; two recovery units 52.5 MWe; six recovery units with
premium hot end 64.21875 MWe. At 200 MWth, three of each module produce ~94.6447 MWe
and retain at least 80 MWe after the worst single-module loss and successful
failover. This assumes intact headers, startup power and batteries for transients.

Automatic dispatch compares candidate banks: adding machinery or offered heat
must not reduce net power by unnecessarily starting another train. Missing cooling
keeps trains idle. Heat not accepted stays upstream; it is not silently deleted.

Python syntax checks and the solution build pass; build output is in `build.log`.
This work adds no thermal runtime, block definitions or native exports. Extraction
seat, final pipe block bills, production collision and subsequent derived art are
still pending. The current game reactor/battery behavior is preserved.
