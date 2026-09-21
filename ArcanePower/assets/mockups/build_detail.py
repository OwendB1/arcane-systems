"""V03: rounded reactor with native-size SEUT interface meshes; run after v02."""
import bpy
import math
import json
from pathlib import Path
from mathutils import Vector

OUT = Path(__file__).resolve().parent
ASSETS = Path('/home/owendb/.local/share/blender-se1-setup/assets')
ns = {'__file__': str(OUT/'build_mockups.py'), '__name__': 'helpers'}
exec(compile((OUT/'build_mockups.py').read_text(), ns['__file__'], 'exec'), ns)
ns['M'] = {m.name[5:]: m for m in bpy.data.materials if m.name.startswith('AP / ')}
box, cylinder, annulus, empty, text = [ns[n] for n in ('box', 'cylinder', 'annulus', 'empty', 'text')]
PART_LIBS = {
    'Common.blend': ['Conveyor LG', 'Conveyor Access LG', 'Conveyor Frame LG', 'Upgrade Port LG', 'Terminal LG', 'Terminal Screen'],
    'Decals/Atlas3.blend': ['Tech Panel', 'Maintenance Box', 'Wire Vent', 'Tiedown Handle', 'Large Screw', 'Circular Vent', 'Corner Mount'],
    'Decals/ButtonsAtlas.blend': ['Button Emergency Stop', 'Combined Panel'],
}


def recess(target, pos, size):
    """Let the native recessed interface geometry sit inside the housing."""
    cutter = box('Temporary interface recess', pos, size, 'Dark', target.parent, 0)
    bpy.context.view_layer.update()
    modifier = target.modifiers.new('Native interface pocket', 'BOOLEAN')
    modifier.operation = 'DIFFERENCE'
    modifier.object = cutter
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def build():
    assert '08 Rounded reactor detail' not in bpy.data.scenes, 'Preserve existing detail edits.'
    parts = bpy.app.driver_namespace.get('ap_parts', {})
    for library, names in PART_LIBS.items():
        missing = [n for n in names if n not in parts]
        if missing:
            with bpy.data.libraries.load(str(ASSETS/'Models'/library), link=False) as (src, dst):
                dst.objects = missing
            parts.update(zip(missing, dst.objects))
    bpy.app.driver_namespace['ap_parts'] = parts
    s = ns['scene']('08 Rounded reactor detail', (0, 0, 4.7), (16, -23, 17), 22.5)
    s.render.resolution_x, s.render.resolution_y = 1600, 1200
    s.frame_end = 480
    root = empty('V03 / rounded reactor / 5x5x5 LG envelope')
    root['envelope_m'] = [12.5, 12.5, 12.5]
    root['status'] = 'Visual prototype; no production collision, dummies or exported subparts'
    used = []

    def part(name, pos, rotation=(0, 0, 0), parent=root, scale=1):
        o = parts[name].copy()
        o.name = 'SEUT / '+name
        s.collection.objects.link(o)
        o.parent = parent
        o.location = pos
        o.rotation_euler = rotation
        o.scale = (scale,)*3
        o.hide_render = o.hide_viewport = False
        o['source_asset'] = name
        o['source_repository'] = 'https://github.com/enenra/seut-assets'
        o['native_scale'] = scale == 1
        used.append(o)
        return o

    # Preserve the working startup animation and its independent assemblies.
    old = bpy.data.scenes['06 Tile assembly startup']
    selected = set(o for o in old.objects if o.get('ring_index') is not None or 'batch' in o or o.name.startswith(('Dispenser ', 'Ignition /')))
    for o in list(selected):
        selected.update(o.children_recursive)
    copies = {}
    for o in selected:
        c = o.copy()
        c.name = 'V03 / '+o.name
        s.collection.objects.link(c)
        copies[o] = c
    for o, c in copies.items():
        c.parent = copies.get(o.parent, root)
    for m in old.timeline_markers:
        s.timeline_markers.new(m.name, frame=m.frame)

    # Circular lower drum, open ring storage well, and segmented service deck.
    cylinder('Round foundation', (0, 0, .22), 5.40, .44, 'Dark', root, 96)
    annulus('Lower machinery drum', (0, 0, 1.40), 4.25, 2.10, 1.90, 'Panel', root)
    for z in [.55, 2.30]:
        annulus('Machined perimeter collar', (0, 0, z), 5.24, .20, .16, 'Edge', root)
    annulus('Ring well inner liner', (0, 0, 1.40), 3.16, .12, 1.88, 'Dark', root)
    annulus('Ring deployment lip', (0, 0, 2.43), 3.20, .26, .14, 'Edge', root)
    annulus('Segmented access deck', (0, 0, 2.35), 4.30, 1.83, .13, 'Dark', root)
    cylinder('Injector pedestal', (0, 0, .82), 1.30, .80, 'Panel', root)
    cylinder('Injector collar', (0, 0, 1.23), 1.20, .13, 'Edge', root)
    for i in range(24):
        a = i*math.tau/24
        annulus('Deck removable plate', (0, 0, 2.45), 4.32, 1.68, .08, 'Hull', root, a+.018, a+math.tau/24-.018)
        annulus('Drum segmented armor', (0, 0, 1.42), 5.27, .12, 1.48, 'Hull', root, a+.025, a+math.tau/24-.025)
        frame = empty('Radial maintenance station', parent=root)
        frame.rotation_euler.z = a
        part('Maintenance Box', (0, -5.35, 1.40), (math.pi/2, 0, 0), frame, 1.65)
        part('Tiedown Handle', (0, -4.78, 2.501), parent=frame)
        for x in [-.39, .39]:
            part('Large Screw', (x, -4.22, 2.501), parent=frame, scale=.32)
        # Real geometry beneath the decal detail: cooling fins and a cable channel.
        for x in [-.35, -.175, 0, .175, .35]:
            box('Heat exchanger fin', (x, -5.36, .85), (.045, .16, .36), 'Dark', frame, .01)

    # Four axial connections: library mesh outer plane is local Z=1.25 m.
    for i in range(4):
        face = empty('Cardinal grid connection', parent=root)
        face.rotation_euler.z = i*math.pi/2
        trunk = box('Radial conveyor trunk', (0, -5.15, 1.25), (2.48, 2.18, 2.48), 'Hull', face, .13)
        recess(trunk, (0, -6.17, 1.25), (1.39, .64, 1.39))
        box('Trunk top armored panel', (0, -5.12, 2.51), (2.05, 1.75, .08), 'Panel', face, .05)
        part('Conveyor Frame LG', (0, -5, 1.25), (math.pi/2, 0, 0), face)
        part('Conveyor Access LG' if i == 0 else 'Conveyor LG', (0, -5, 1.25), (math.pi/2, 0, 0), face)
        part('Tech Panel', (0, -5.2, 2.558), parent=face, scale=2)
        # Registration marker only; final detector names/axes belong to export.
        marker = empty('Grid face reference / not export dummy', (0, -6.25, 1.25), face)
        marker['grid_cell_pitch_m'] = 2.5

    # Rounded upper machine and four external structural spines.
    cylinder('Upper containment bell', (0, 0, 9.22), 3.48, .62, 'Dark', root, 96)
    annulus('Upper copper coil', (0, 0, 8.91), 2.90, .25, .16, 'Copper', root)
    cylinder('Circular upper armored housing', (0, 0, 9.86), 4.50, .80, 'Hull', root, 96)
    for z in [9.45, 10.25]:
        annulus('Upper armored rim', (0, 0, z), 4.48, .20, .13, 'Edge', root)
    cylinder('Cap central service hatch', (0, 0, 10.33), 1.85, .18, 'Panel', root, 48)
    annulus('Cap hatch rim', (0, 0, 10.43), 1.8, .11, .06, 'Edge', root)
    for i in range(16):
        a = i*math.tau/16
        annulus('Cap removable sector', (0, 0, 10.30), 3.16, 2.15, .09, 'Panel', root, a+.022, a+math.tau/16-.022)
        f = empty('Upper radial details', parent=root)
        f.rotation_euler.z = a
        part('Wire Vent', (0, -3.2, 10.351), parent=f, scale=2)
        for x in [-.29, .29]:
            part('Large Screw', (x, -4.04, 10.351), parent=f, scale=.33)
        box('Cap rim cooling inset', (0, -4.48, 9.85), (.82, .035, .35), 'Dark', f, .02)
        for z in [9.73, 9.83, 9.93]:
            box('Cap rim vent louver', (0, -4.52, z), (.78, .055, .028), 'Edge', f, .006)
    for i in range(4):
        f = empty('Radial support and coolant assembly', parent=root)
        f.rotation_euler.z = math.pi/4+i*math.pi/2
        box('Spine base foot', (0, -4.15, 2.74), (1.25, 1.55, .48), 'Edge', f)
        box('Structural spine', (0, -4.20, 6.03), (.65, .72, 6.4), 'Hull', f, .15)
        box('Spine recessed channel', (0, -4.57, 6.0), (.37, .055, 5.45), 'Dark', f, .015)
        box('Spine status emitter', (0, -4.606, 6.5), (.09, .022, 1.6), 'Cyan', f, .004)
        for x in [-.47, .47]:
            cylinder('Coolant riser pipe', (x, -4.15, 6.05), .105, 6.3, 'Copper', f, 16)
            for z in [3.25, 4.65, 7.5, 8.85]:
                cylinder('Pipe coupling', (x, -4.15, z), .145, .18, 'Edge', f, 16)
        for z in [3.6, 8.1]:
            box('Spine bolted collar', (0, -4.20, z), (.91, .92, .23), 'Edge', f, .03)
        box('Upper radial bracket', (0, -3.95, 9.20), (1.12, 1.3, .45), 'Edge', f)
        part('Tech Panel', (0, -4.58, 4.35), (math.pi/2, 0, 0), f)

    # Separate controller housings with true 0.68 m upgrade interfaces.
    for a in [-math.pi/4, math.pi/4]:
        f = empty('Containment controller module', parent=root)
        f.rotation_euler.z = a
        casing = box('Controller armored casing', (0, -4.35, 3.4), (1.18, 1.22, 1.35), 'Hull', f, .12)
        recess(casing, (.59, -4.35, 3.4), (.50, .69, .69))
        box('Controller front recess', (0, -4.98, 3.45), (.95, .07, 1.02), 'Dark', f, .045)
        part('Terminal LG', (-.28, -5.03, 3.67), (math.pi/2, 0, 0), f)
        part('Terminal Screen', (-.28, -5.038, 3.67), (math.pi/2, 0, 0), f)
        part('Button Emergency Stop', (.29, -5.031, 3.30), (math.pi/2, 0, 0), f)
        part('Combined Panel', (.23, -5.031, 3.73), (math.pi/2, 0, 0), f, .70)
        part('Upgrade Port LG', (-.65, -4.35, 3.4), (0, math.pi/2, 0), f)

    # Dispenser guide rods, cooling shrouds and tiny fasteners inside ring clearance.
    for x in [-.68, .68]:
        for y in [-.68, .68]:
            for dx in [-.23, .23]:
                cylinder('Dispenser guide rod', (x+dx, y, 2.12), .045, 1.47, 'Edge', root, 12)
            for z in [1.6, 1.85, 2.10, 2.35]:
                box('Dispenser cooling shroud', (x, y, z), (.46, .43, .075), 'Panel', root, .018)
    ns['human']((-5.0, -6.0, 0), root)
    text('ARCANE POWER', (-1.01, -6.27, 2.16), .21, 'White', root)
    text('01 / CONTAINMENT', (-.93, -6.27, .30), .115, 'White', root)
    s['visual_prototype_only'] = True
    s['source_library'] = 'SEUT assets / Common, Atlas3, ButtonsAtlas'
    s['tile_count'], s['batch_size'] = 80, 4
    s.frame_set(440)
    bpy.context.view_layer.update()
    manifest = []
    for name in sorted(set(o['source_asset'] for o in used)):
        p = parts[name]
        bounds = [[min(v.co[i] for v in p.data.vertices), max(v.co[i] for v in p.data.vertices)] for i in range(3)]
        manifest.append({'asset': name, 'source': next(k for k, v in PART_LIBS.items() if name in v), 'native_mesh_bounds_m': bounds, 'instances': sum(o['source_asset'] == name for o in used)})
    (OUT/'detail-asset-sources.json').write_text(json.dumps(manifest, indent=2)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'arcane-power-mockups-v03.blend'))
    print('Created rounded detail scene:', len(s.objects), 'objects;', len(used), 'SEUT part instances')


if __name__ == '__main__':
    build()
