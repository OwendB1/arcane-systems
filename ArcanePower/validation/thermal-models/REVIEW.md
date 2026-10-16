# Rounded reactor manifolds and controller backing — 16 October 2026

Maintained source: `assets/build_reactor_thermal_manifolds.py`; output:
`assets/arcane-thermal-models.blend`, scene `ArcanePower_Thermal_ReactorHousing`.
Official Blender MCP, live Blender 5.2.1 LTS. Previous accepted state is preserved
in `assets/arcane-thermal-before-rounded-manifolds.blend`.

Four rounded twin-bore castings now unite each pair of deployed pipe heads.
Each has a tapered rounded rear connector that reaches inside the curved shell,
travels with the pipe carriage and retracts through a small bulkhead guide. Its
extending neck stays engaged in that guide throughout deployment. The preview
uses native axial scaling for this neck; game subpart integration must reproduce
that motion rather than assume Blender drivers export automatically.
Native SEUT materials, metric UVs, captive studs and a supported PRIMARY marking
finish the casting. Hot and return remain separate through-bores.

The original curved covers still close over the whole assembly. They inset
0.36 m and slide 0.155 rad under neighboring armor before the pipe carriages
extend 1.41 m. Deployed faces remain at X=±6.25 m, Y=±2.5 m, Z=−2.33 m, with
the existing 170 mm grid-height adapter. Original controller sockets and the
5×5×3 Blender-cell envelope are preserved.

Refinement findings and repairs:

1. A shared casting needs more room than the old two circular bores: cut a real
   internal travel pocket behind the original armor.
2. The first rear shoulder overlapped the intermediate sleeves and fixed glands:
   shortened the shoulder and fitted the connector neck between the glands.
3. A 14-position check missed a brief door collision during extension: expanded
   the gate to 47 positions, including motion boundaries, and widened sideways
   cover travel and its internal storage pocket.
4. New boolean walls inherited collapsed UVs: reproject only those faces while
   preserving accepted exterior UVs.
5. Close review found an undersized rear connector and coincident bore surfaces:
   extended the connector into the shell through a supported guide and offset
   the casting bore by 2 mm from the adjoining pipe interiors.
6. A rigid long guide tail entered the protected ring-well liner: replaced it
   with an extending neck anchored outside the liner. The guide remains engaged
   without cutting or moving the liner.

Evidence:

- `rounded-manifold-review-plan.json`: 48 close UI views, four bays, upper/lower
  heads, the bridge and rear joints at 1.8/2.4/3.0 m. Target/lens/light stay fixed
  within each triplet; actual view metadata is in `ui-reviews.json`.
- `rounded-contact-LA.jpg`, `-LB.jpg`, `-RA.jpg`, `-RB.jpg`: close-review sheets.
- Eight sampled motion UI views, closed/open final views and a whole-assembly
  view supplement the closeups. Earlier failure evidence is in `rounded-pass1/`.
- `curved-manifold-audit.json`: 47 sampled positions clear other moving groups
  and fixed geometry; original covers occlude the nose discs and full casting /
  connector silhouettes. Four castings and connectors are closed positive
  solids, share the pipe carriages and keep both bores open. Deployed connector
  roots reach inside the shell.
- `audit.json`: all 31 main sources and the two grid assemblies pass geometry,
  native material/UV, supported-detail and socket gates. The accepted reactor,
  battery and concept source hashes are unchanged.
- `reload.json`: saved-file consistency and validation results.

Controller backing correction (revision 4): the inherited conveyor-sized recess
behind each controller receiver is now filled to the curved drum/armor profile,
including the notch below the receiver. Only the 0.60 m native-port aperture
remains. The earlier partial lower infills were replaced by continuous closed
solids fitted directly to the original opening edges. Native yellow ports and
their transforms remain unchanged. The focused audit samples both restored
surfaces and retains all 47 motion checks. `controller-backing-review-plan.json`
and `controller-*-*.png` record front, lower, side and chamber UI checks at
1.8/2.4/3.0 m; the chamber views confirm the retained inner wall. Before editing,
the accepted source was preserved in
`assets/arcane-thermal-before-controller-backing.blend`.

This pass is modeling and a mechanical preview rig. Native subpart exports and
in-game animation/mode switching remain pending. Other models retain their base
state while this requested manifold refinement is completed. Workshop/gallery
publication remains paused.
