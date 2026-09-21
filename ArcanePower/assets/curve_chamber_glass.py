"""Run after fit_three_cells.py in Blender: seated curved, low-reflection glass."""
import bpy
import importlib
import math
import copy
from pathlib import Path
import xml.etree.ElementTree as ET

s = bpy.data.scenes['ArcanePower_ReactorPrototype']
assert s.get('three_cells_applied'), 'Fit the three-cell housing first'
bpy.context.window.scene = s
cols = importlib.import_module('space-engineers-utilities.seut_collections').get_collections(s)
col = cols['main'][0]
root = next(o for o in col.objects if o.parent is None)
native = {m.name: m for m in bpy.data.materials if m.library}

for o in list(col.objects):
    if o.name.startswith(('Chamber glass /', 'Glazing frame', 'Curved chamber /')):
        bpy.data.objects.remove(o, do_unlink=True)

# Own material ID, retaining the installed game's window dirt and chrome textures.
# Never override GlassInside/GlassOutside globally.
mat = bpy.data.materials.get('ArcanePower_ClearChamber')
if mat is None:
    mat = native['GlassInside'].copy()
    mat.name = 'ArcanePower_ClearChamber'
# SEUT callbacks target context.active_object.active_material, not the property
# owner. Bind this material while changing properties to avoid changing hull preview.
binding = bpy.data.objects.new('Temporary glass material context', bpy.data.meshes.new('Temporary glass context'))
col.objects.link(binding)
binding.data.materials.append(mat)
bpy.context.view_layer.objects.active = binding
mat.seut.technique = 'GLASS'
mat.seut.color = (.98, .99, 1.0, .06)
mat.seut.color_add = (0, 0, 0, 0)
mat.seut.reflectivity = .02
mat.seut.fresnel = .10
mat.seut.reflection_shadow = .10
mat.seut.specular_color_factor = .5
mat.seut.is_flare_occluder = False
# SEUT's stock preview shader does not reflect these game-side transparency
# constants. Keep its texture nodes for export, but show a clear Blender preview.
nodes = mat.node_tree.nodes
preview = nodes.get('Arcane clear glass preview')
if preview is None:
    preview = nodes.new('ShaderNodeBsdfPrincipled')
    preview.name = 'Arcane clear glass preview'
preview.inputs['Base Color'].default_value = (.90, .96, 1.0, 1.0)
preview.inputs['Metallic'].default_value = 0
preview.inputs['Roughness'].default_value = .14
preview.inputs['Alpha'].default_value = .06
output = next(n for n in nodes if n.type == 'OUTPUT_MATERIAL')
mat.node_tree.links.new(preview.outputs['BSDF'], output.inputs['Surface'])
mat.surface_render_method = 'BLENDED'
mat.diffuse_color = (.90, .96, 1.0, .06)
bpy.data.objects.remove(binding, do_unlink=True)


def mesh_object(name, vertices, faces, material, target=col):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    if material:
        mesh.materials.append(material)
    # MwmBuilder processes the collision FBX too and requires UVs even there.
    uv = mesh.uv_layers.new(name='UVMap')
    for p in mesh.polygons:
        axes = [i for i in range(3) if i != max(range(3), key=lambda i: abs(p.normal[i]))]
        for loop in p.loop_indices:
            v = mesh.vertices[mesh.loops[loop].vertex_index].co
            uv.data[loop].uv = (v[axes[0]] / 2.5, v[axes[1]] / 2.5)
    obj = bpy.data.objects.new(name, mesh)
    target.objects.link(obj)
    if target == col:
        obj.parent = root
    return obj


# Continuous cylindrical chamber, four quarter panes with seams hidden by pillars.
# Glass embeds into the deck (-1.34) and cap underside (+2.888), eliminating gaps.
radius, bottom, top, segments = 4.12, -1.40, 2.96, 32
for quarter in range(4):
    start = math.pi / 4 + quarter * math.pi / 2
    vertices = []
    for i in range(segments + 1):
        a = start + i * math.pi / (2 * segments)
        vertices.extend([(radius * math.cos(a), radius * math.sin(a), z) for z in (bottom, top)])
    for inside in (False, True):
        faces = [(2*i, 2*i+2, 2*i+3, 2*i+1) for i in range(segments)]
        if inside:
            faces = [tuple(reversed(f)) for f in faces]
        obj = mesh_object('Curved chamber / pane %s %s' % (quarter, 'inside' if inside else 'outside'), vertices, faces, mat)
        for p in obj.data.polygons:
            p.use_smooth = True
            for loop in p.loop_indices:
                vertex = obj.data.loops[loop].vertex_index
                obj.data.uv_layers[0].data[loop].uv = (vertex // 2 / segments, vertex % 2)

# Rectangular annular seals, buried into both housings with a small visible lip.
for center in (-1.32, 2.90):
    vertices, faces = [], []
    for i in range(128):
        a = i * math.tau / 128
        vertices.extend([(r*math.cos(a), r*math.sin(a), z)
                         for r, z in [(4.04, center-.09), (4.20, center-.09),
                                      (4.20, center+.09), (4.04, center+.09)]])
    for i in range(128):
        for j in range(4):
            faces.append((4*i+j, 4*((i+1)%128)+j, 4*((i+1)%128)+(j+1)%4, 4*i+(j+1)%4))
    mesh_object('Curved chamber / housing seal', vertices, faces, native['Metal_Dull'])

# Four conservative convex quarter-shell colliders keep the existing ten-body budget.
# Their inner chords remain outside the animated ring sweep; final collision QA is pending.
for o in list(cols['hkt'][0].objects):
    if o.name.startswith('Curved chamber collision') or (o.type == 'MESH' and abs(o.location.z-.6) < .01):
        bpy.data.objects.remove(o, do_unlink=True)
for quarter in range(4):
    vertices, faces = [], []
    for i in range(9):
        a = math.pi/4 + quarter*math.pi/2 + i*math.pi/16
        vertices.extend([(r*math.cos(a), r*math.sin(a), z)
                         for r, z in [(4.04, bottom), (4.12, bottom), (4.12, top), (4.04, top)]])
    for i in range(8):
        for j in range(4):
            faces.append((4*i+j, 4*(i+1)+j, 4*(i+1)+(j+1)%4, 4*i+(j+1)%4))
    faces.extend([(3, 2, 1, 0), (32, 33, 34, 35)])
    mesh_object('Curved chamber collision', vertices, faces, None, cols['hkt'][0])
assert len(cols['hkt'][0].objects) == 10
# SBC export is disabled to protect our hand-authored block definitions.
# Emit the namespaced material explicitly, retaining the game's texture references.
game = Path.home()/'.local/share/Steam/steamapps/common/SpaceEngineers/Content'
source = ET.parse(game/'Data/TransparentMaterials.sbc').getroot()
definition = copy.deepcopy(next(d for d in source.find('TransparentMaterials')
                                if d.findtext('Id/SubtypeId') == 'GlassInside'))
definition.find('Id/SubtypeId').text = mat.name
for tag, values in [('Color', mat.seut.color), ('ColorAdd', mat.seut.color_add)]:
    for axis, value in zip('XYZW', values):
        definition.find(tag+'/'+axis).text = str(round(value, 4))
for tag, value in [('Reflectivity', .02), ('Fresnel', .10), ('ReflectionShadow', .10),
                   ('SpecularColorFactor', .5), ('IsFlareOccluder', 'false')]:
    node = definition.find(tag)
    if node is None:
        node = ET.SubElement(definition, tag)
    node.text = str(value)
definitions = ET.Element('Definitions')
ET.SubElement(definitions, 'TransparentMaterials').append(definition)
ET.indent(definitions)
ET.ElementTree(definitions).write(Path(s.seut.mod_path)/'Data/TransparentMaterials.sbc', encoding='utf-8', xml_declaration=True)
s['chamber_glazing'] = 'R4.12, Z -1.40..2.96, 128 segments; own clear glass using vanilla textures'
bpy.context.view_layer.update()
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
print(s['chamber_glazing'])
