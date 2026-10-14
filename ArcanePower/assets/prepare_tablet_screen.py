"""Prepare the tablet's front face for native LCD rendering, then save/export with SEUT."""
import bpy
import importlib
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
scene = bpy.data.scenes['ArcanePower_Tablet']
bpy.context.window.scene = scene
# Baked cards/traces would sit in front of the live LCD texture.
for obj in list(scene.objects):
    if any(part in obj.name for part in ('screen card', 'diagnostic trace', 'engraved wordmark')):
        bpy.data.objects.remove(obj, do_unlink=True)

glass = next(obj for obj in scene.objects if 'glass display' in obj.name)
uv = glass.data.uv_layers.active or glass.data.uv_layers.new(name='UVMap')
for face in glass.data.polygons:
    axis = max(range(3), key=lambda i: abs(face.normal[i]))
    for index in face.loop_indices:
        vertex = glass.data.vertices[glass.data.loops[index].vertex_index].co
        # Project each face on its dominant plane; edge UVs must not collapse.
        if axis == 1:
            u = (vertex.x + .135) / .270
            v = (vertex.z + .087) / .174
            # SEUT reverses exported X and flips V. The held tool faces the
            # player after its Y half-turn: U follows visible right, V down.
            value = (u, v)
        elif axis == 0:
            value = ((vertex.y + .0015) / .003, (vertex.z + .087) / .174)
        else:
            value = ((vertex.x + .135) / .270, (vertex.y + .0015) / .003)
        uv.data[index].uv = value

material = bpy.data.materials['ArcaneTabletScreen']
# Uniform, nonmetallic matte black when the native live texture is unbound.
# ADD retains emission for the live LCD; black base colour emits no light.
for node, rgba in [('CM', (0, 0, 0, 0)), ('NG', (.5, .5, 1, .08)), ('ADD', (1, 1, 0, 0))]:
    image = material.node_tree.nodes[node].image
    image.pixels[:] = list(rgba) * (image.size[0] * image.size[1])
    image.save()
# Reuse the native toolchain's established Wine trace-listener workaround.
setup = Path.home() / '.local/share/blender-se1-setup'
builder = ROOT / '.cache/tablet-screen/MWMBuilder'
shutil.copytree(setup / 'assets/Tools/MWMBuilder', builder, dirs_exist_ok=True)
(builder / 'MwmBuilder.exe.config').write_text(
    '<configuration><system.diagnostics><trace><listeners><clear />'
    '</listeners></trace></system.diagnostics></configuration>')
bpy.context.preferences.addons['space-engineers-utilities'].preferences.mwmb_path = str(builder / 'MwmBuilder.exe')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / 'assets/arcane-power-prototype.blend'))
importlib.import_module('space-engineers-utilities.seut_errors').show_popup_report = lambda c, t, x: print(t, x, flush=True)
area = next(area for area in bpy.context.screen.areas if area.type == 'VIEW_3D')
with bpy.context.temp_override(area=area, region=next(region for region in area.regions if region.type == 'WINDOW')):
    result = bpy.ops.scene.export()
    if 'FINISHED' not in result:
        raise RuntimeError('Tablet LCD export failed: ' + str(result))
model = ROOT / 'src/Models/Items/ArcanePower_Tablet.mwm'
if model.stat().st_mtime < model.with_suffix('.fbx').stat().st_mtime:
    raise RuntimeError('Tablet MWM conversion failed; see the exporter log')
# SEUT's direct TGA conversion can turn all-zero packed alpha opaque. Preserve
# metalness/paint masks using the project's established PNG staging converter.
import subprocess
for suffix in ('cm', 'ng', 'add'):
    source = ROOT / 'src/Textures/Models/ArcanePower' / ('ArcaneTabletScreen_' + suffix + '.tga')
    # Blender's bundled Python has no Pillow; use the authoring environment.
    subprocess.run([shutil.which('python3'), '-c',
                    'import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); '
                    'from texture_conversion import convert; p=Path(sys.argv[2]); '
                    'convert(p, p.parent, linear=not p.stem.endswith("_cm"))',
                    str(ROOT / 'tools'), str(source)], check=True)
print('Prepared/exported native tablet LCD: mapped front face, emissive display, no baked screen artwork.', flush=True)
