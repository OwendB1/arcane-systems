"""Subtle baseline haze plus native window dirt/reflections; no MWM rebuild."""
import bpy
from pathlib import Path
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1]
path = root / 'src/Data/TransparentMaterials.sbc'
tree = ET.parse(path)
definition = next(d for d in tree.getroot().find('TransparentMaterials')
                  if d.findtext('Id/SubtypeId') == 'ArcanePower_ClearChamber')
values = {'Color/W': .28, 'Reflectivity': .10, 'Fresnel': .45,
          'ReflectionShadow': .20, 'SpecularColorFactor': 3.0,
          'ColorAdd/X': .008, 'ColorAdd/Y': .009, 'ColorAdd/Z': .010, 'ColorAdd/W': .025}
for key, value in values.items():
    definition.find(key).text = str(value)
ET.indent(tree)
tree.write(path, encoding='utf-8', xml_declaration=True)

m = bpy.data.materials['ArcanePower_ClearChamber']
# SEUT property callbacks use the active object's material, so bind the pane.
layer = bpy.context.view_layer
previous = layer.objects.active
layer.objects.active = bpy.data.objects['Curved chamber / pane 0 outside']
m.seut.color = (.98, .99, 1.0, .28)
# SE's Glass/Pixel.hlsl adds ColorAdd AFTER multiplying by the native dirt
# texture. This gives clear texels a faint haze instead of amplifying dirt.
# Keep RGB small with alpha: the shader accumulates the values together.
m.seut.color_add = (.008, .009, .010, .025)
m.seut.reflectivity = .10
m.seut.fresnel = .45
m.seut.reflection_shadow = .20
m.seut.specular_color_factor = 3.0
layer.objects.active = previous

# Preview uses the same native dirt texture. Its packed alpha must first be
# restored using repair_seut_preview_textures.py (the library's RGB TIF lost it).
nodes, links = m.node_tree.nodes, m.node_tree.links
texture = nodes['CM']
texture.image.reload()
nodes['NG'].image.reload()
preview = nodes['Arcane clear glass preview']
preview.inputs['Base Color'].default_value = (.94, .97, 1.0, 1.0)
preview.inputs['Roughness'].default_value = .12
preview.inputs['IOR'].default_value = 1.45
preview.inputs['Metallic'].default_value = .0
for name in ['AP glass dirt alpha', 'AP glass grazing alpha', 'AP glass preview opacity']:
    if nodes.get(name): nodes.remove(nodes[name])
dirt = nodes.new('ShaderNodeMath'); dirt.name = 'AP glass dirt alpha'
dirt.operation = 'MULTIPLY_ADD'; dirt.inputs[1].default_value = .28; dirt.inputs[2].default_value = .025
links.new(texture.outputs['Alpha'], dirt.inputs[0])
grazing = nodes.new('ShaderNodeLayerWeight'); grazing.name = 'AP glass grazing alpha'
opacity = nodes.new('ShaderNodeMath'); opacity.name = 'AP glass preview opacity'
opacity.operation = 'MULTIPLY_ADD'; opacity.inputs[1].default_value = .18
links.new(grazing.outputs['Fresnel'], opacity.inputs[0])
links.new(dirt.outputs[0], opacity.inputs[2])
links.new(opacity.outputs[0], preview.inputs['Alpha'])
# The preview is an approximation of SE's environment/light dependent shader.
links.new(preview.outputs['BSDF'], next(n for n in nodes if n.type == 'OUTPUT_MATERIAL').inputs['Surface'])
m.surface_render_method = 'BLENDED'
m.diffuse_color = (.94, .97, 1.0, .10)
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
print('Glass: baseline haze alpha .025, subtle cool-grey tint; native dirt/reflections retained')
