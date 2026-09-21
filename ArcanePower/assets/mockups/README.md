Arcane Power — first Blender mockup set

Latest revision: [v03 rounded SEUT detail study](DETAIL.md), with actual library conveyor/upgrade interfaces, circular machinery housings, and mechanical surface detail. It retains the [v02 startup](STARTUP.md), with rings emerging from a base bay and four-at-a-time containment tile assembly. The v01 studies below are preserved for comparison.

Open [arcane-power-mockups-v01.blend](arcane-power-mockups-v01.blend). Use Blender's scene selector at the top right to switch studies. Press Space over the viewport to play the animation; Numpad 0 toggles the review camera. The original default scene is retained.

These are original editable blockouts made through Blender MCP, using simple materials inspired by the existing Arcane Core icons. They establish shapes, attachment space, and motion. They are not game-ready assets: no UV texture set, production collision, construction stages, LODs, or Animation Engine integration yet.

| Scene | Review purpose |
| --- | --- |
| 01 Gyroscopic reactors | Three fuel tiers with 2/3/4 rings. Independent ring spin and slower axis precession. |
| 02 Column reactors | The same three tiers around a vertical plasma column, with independently rotating horizontal rings. |
| 03 Energy Core | Four side capacity modules with cyan charge bars, two front transfer modules with copper conductors, four stabilizer columns, and a slowly moving central field. |
| 04 Vent states | Closed, open, and animated discharge studies. The right-hand outlet cycles opening, discharge, and closing over frames 1–240; frame 115 shows discharge. |
| 05 Scale study | Full reactor versus 60% silhouette, with full-size human references and a 2.5 m cube representing one large-grid Arcane Core cell. |

The human references are 1.8 m tall. Reactor nominal envelopes are 12.5 × 12.5 × 10 m and 7.5 × 7.5 × 6 m; these are provisional visual envelopes, not finalized block definitions. The compact version is a proportion study, so module dimensions and access still need redesign at that scale. The cube is a scale proxy, not a reconstruction of the existing Arcane Core.

Controller counts follow active rings. Unused sockets remain visible. The rear duct takeoff is dedicated reactor exhaust. Vent shutters and a simple emissive plume are visual placeholders, not a simulated gas or particle system. The vent sample is amber; runtime fuel-driven colouring remains to be implemented.

Review stills:

- [Gyroscopic tiers](previews/01.png)
- [Column tiers](previews/02.png)
- [Energy Core](previews/03.png)
- [Vent states](previews/04.png)
- [Scale comparison](previews/05.png)

Motion previews use solid materials to emphasize geometry rather than lighting:

- [Gyroscopic motion](previews/gyro-motion.mp4)
- [Vent sequence](previews/vent-sequence.mp4)

The Blender timeline is 24 fps. Video previews sample every fourth frame and play at 6 fps, preserving the 10-second duration. Gyroscopic precession continues across the clip boundary; the clip is not a seamless loop.

Reproducible authoring and checks, from this directory:

```sh
blender --background --factory-startup --python build_mockups.py
blender --background arcane-power-mockups-v01.blend --python check_mockups.py
blender --background arcane-power-mockups-v01.blend -t 8 --python render_previews.py
blender --background arcane-power-mockups-v01.blend -t 4 --python render_previews.py -- --animation
ffmpeg -y -framerate 6 -i previews/frames-01/%03d.png -vf 'pad=ceil(iw/2)*2:ceil(ih/2)*2' -c:v libx264 -pix_fmt yuv420p -movflags +faststart previews/gyro-motion.mp4
ffmpeg -y -framerate 6 -i previews/frames-04/%03d.png -vf 'pad=ceil(iw/2)*2:ceil(ih/2)*2' -c:v libx264 -pix_fmt yuv420p -movflags +faststart previews/vent-sequence.mp4
```

Rebuilding replaces the saved v01 output; save manual refinements under a new version first. No external textures or linked assets are required. [validation.json](validation.json) records checks for tier/controller counts, changing animated transforms, ring vertical clearance at four poses, vent sequencing, and the compact human reference. It does not certify exhaustive collision or game compatibility.

Next review: choose reactor silhouette and approximate scale; assess whether controller access, the top cap, and vent outlet proportions suit the intended engineering room. Then refine a chosen design before production mesh detail.
