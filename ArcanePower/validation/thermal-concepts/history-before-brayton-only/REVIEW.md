# Thermal concepts: current review

15 October 2026. Official Blender MCP; Blender 5.2.1 LTS, existing live window.
Saved and reopened `assets/arcane-thermal-concepts.blend`; active scene is
`Thermal / Advanced plant`. Production reactor and battery file hashes match
`protected-production.json`. Earlier `arcane-thermal-before-fit-review.blend`
predates the shorter Brayton envelope; it is not the current source.

Seven editable component concepts, 750 meshes, 17 duplex ports. Component scenes,
lineup, base plant and advanced plant are separate. Maintained procedural sources:
`build_thermal_concepts.py` and `review_thermal_concepts.py` in `assets/`.

- Inspect `ui-lineup.png`, `ui-base-plant.png`, `ui-advanced-plant.png` and
  `contact-overviews.jpg` for scale and layout.
- `contact-0.jpg` through `contact-5.jpg` group 51 actual UI captures: 17 targets
  at 1.8/2.4/3.0 m. `ui-reviews.json` records eye/target, actual distance, 48 mm
  lens and fixed studio lighting. The views include front and opposite details.
- `audit.json` and `reload.json` pass component solids, UVs, material references,
  full fastener/decal/text backing, envelopes, port poses/necks, recuperator
  bypass clearance, fan envelopes and typed layout connection checks.
- `energy-budget.json`: 12 energy-balance cases and three rejected invalid inputs.
  Base net is 40%; MHD topping plus Brayton is 50.4% at the proposed design point.
- Python syntax checks pass. `dotnet build arcane-systems.sln --no-restore` passes
  with zero warnings/errors after adding the existing battery gameplay file's
  missing `VRage.ObjectBuilders` import. No thermal runtime was implemented.

Visible repairs: supported foundations, shorter train, electric compressor motor,
fitted casing saddles, fan plenum and spiders, physical pitched fan blades, lined
MHD transitions, electrode feeds, readable native markings, conditioner controls
and vents, separated recuperator bypasses and unobstructed cooler utility bores.

Concept limits: the extraction head is a proposed external interface, plant pipes
are schematic rather than a final block bill, and vertical conduit fittings remain
to be designed. Internal fluid passages, final service/fabrication clearances,
collision, fan runtime animation, thermal simulation, definitions and native
exports still require production work. Compact TW cooling is an explicit Arcane
abstraction. No new LODs, stages, Workshop upload or publication is part of this
study. See `ArcanePower/THERMAL-POWER.md` for the full contract.
