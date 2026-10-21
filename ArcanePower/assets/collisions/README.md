# Accepted physics inputs

These HKT files are build inputs, excluded from the loadable mod. Player MWMs
already embed the collision bytes. Keep these inputs when deleting generated
FBX/XML/MWM staging: material and fitted-detail exports reuse the accepted physics.

`Cubes/large/` holds the original reactor, storage and hardware inputs;
`Cubes/large/Thermal/` holds the 53 thermal mains and 159 construction inputs,
including the 22 bare pipe variants. Their hulls follow actual pipe solids;
the removed cages and manifold plates do not leave collision surfaces behind.
The native export and construction validators read them from here.
