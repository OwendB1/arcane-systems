# Accepted physics inputs

These HKT files are build inputs, excluded from the loadable mod. Player MWMs
already embed the collision bytes. Keep these inputs when deleting generated
FBX/XML/MWM staging: material and fitted-detail exports reuse the accepted physics.

`Cubes/large/` holds the original reactor, storage and hardware inputs;
`Cubes/large/Thermal/` holds the 31 thermal mains and 93 construction inputs.
The native export and construction validators read them from here.
