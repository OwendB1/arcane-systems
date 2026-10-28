# Accepted physics inputs

These HKT files are build inputs, excluded from the loadable mod. Player MWMs
already embed the collision bytes. Keep these inputs when deleting generated
FBX/XML/MWM staging: material and fitted-detail exports reuse the accepted physics.

`Cubes/large/` holds the original reactor, storage and hardware inputs;
`Cubes/large/Thermal/` holds thermal main, moving-subpart and construction inputs,
including retained historical variants. The current native export ledger identifies
the active families. Bare-pipe hulls follow the pipe solids; enclosed fittings,
rotors and the radiator base follow their sealed casings. The native export and
construction validators read these inputs from here.

The 0.3.0 radiator base uses six flat convex casing hulls, including its recessed
bearing deck. `tools/check_thermal_installation.py` extracts the actual installed
HKT and checks it against these inputs, then runs native Havok face-contact and
upper-clearance sweeps for the radiator and both pipe rotor parts. The original
radiator inputs are retained in `checkpoints/radiator-base-before-finish/`.

The thermal reactor main and its three construction stages contain **ten flat
convex hulls**: the original deck and roof, four glass quadrants and four fitted
pillars. The original `Cubes/large/ArcanePower_ReactorPrototype.hkt` stays unchanged;
`Thermal/APT_ReactorHousing_Pillars.hkt` retains the pillar-only export. The merger
combines adjacent original glass hulls into four convex quadrants. Their outside
boundary stays at the glass; their inner chords extend further into the chamber.
The exterior walkway, platform and pillars retain their accepted bounds.

Do not wrap additional hulls in one top-level list. SE loads at most ten top-level
shapes. Its block collector expands a list's children but records the original
array length; the grid consumes only that recorded count. The previous list of
fourteen hulls therefore lost all but its first hull in actual grid physics.
The native probe now rejects nested shapes and validates the count consumed by
the grid, plus deck/roof/glass contacts, pillar faces and character/walkway sweeps.

To rebuild after changing pillar geometry, run `apply()` from
`assets/build_reactor_pillar_collision.py` in the production Blender scene, then
export and merge before the regular model export:

```sh
blender -b ArcanePower/assets/arcane-thermal-models.blend --python-exit-code 1 \
  --python ArcanePower/assets/build_reactor_pillar_collision.py -- \
  --export ArcanePower/src/Models/Cubes/large/.pillar-collision-stage
PYTHONDONTWRITEBYTECODE=1 python3 ArcanePower/tools/build_reactor_pillar_collision.py \
  ArcanePower/src/Models/Cubes/large/.pillar-collision-stage/ArcanePower_Thermal_ReactorHousing.hkt
```

SEUT requires this temporary export directory under the mod's `Models` directory;
remove it after validation. The merge installs the main/stage inputs only after
native Havok checks pass. After compiling the models, run
`tools/check_reactor_havok.py` to verify the delivered MWM embeds the accepted HKT
and passes the same contacts. This does not replace an in-game reload check.

For a collision-only rebuild, the maintained merger can also replace just the
collision tags in the installed main and construction MWMs. It verifies the
native roundtrip and unchanged interfaces, and selects a fresh content-hashed
model folder so the game cannot reuse the broken physics cache:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 ArcanePower/tools/build_reactor_pillar_collision.py \
  ArcanePower/assets/collisions/Cubes/large/Thermal/APT_ReactorHousing_Pillars.hkt --install
```

Refresh native motion validation and the unpublished release package after
installing, then run delivery and Havok checks.
