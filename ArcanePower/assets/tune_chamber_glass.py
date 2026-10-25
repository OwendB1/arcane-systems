"""Shared smoked-glass finish for native SE materials and live Blender previews.

The uniform CA map is zero. Glass/Pixel.hlsl therefore takes its visible body
from ColorAdd, including alpha; increasing Color.W cannot darken these panes.
Keep the tint premultiplied and reflections below the old mirror-like pipe finish.
No mesh, UV, material assignment or collision changes are needed.
"""
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PROFILES = {
    'ArcanePower_ClearChamber': dict(tint=(.020, .030, .038, .24), reflection=.18,
        fresnel=.65, specular=3, preview=(.15, .22, .27, 1), roughness=.12, grazing=.16),
    'ArcanePower_CoolantGlass': dict(tint=(.022, .034, .043, .36), reflection=.20,
        fresnel=.65, specular=4, preview=(.12, .20, .25, 1), roughness=.12, grazing=.16),
    'ArcanePower_InternalCoolantGlass': dict(tint=(.018, .027, .034, .30), reflection=.18,
        fresnel=.60, specular=3, preview=(.10, .16, .20, 1), roughness=.15, grazing=.14),
}


def write_native():
    path = ROOT/'src/Data/TransparentMaterials.sbc'
    tree = ET.parse(path)
    for definition in tree.getroot().find('TransparentMaterials'):
        profile = PROFILES.get(definition.findtext('Id/SubtypeId'))
        if profile is None:
            continue
        values = {'Reflectivity': profile['reflection'], 'Fresnel': profile['fresnel'],
                  'SpecularColorFactor': profile['specular']}
        values.update(('ColorAdd/'+axis, value) for axis, value in zip('XYZW', profile['tint']))
        for key, value in values.items():
            definition.find(key).text = str(value)
    ET.indent(tree)
    tree.write(path, encoding='utf-8', xml_declaration=True)


def apply_material(material):
    import bpy
    profile = PROFILES[material.name.split('.')[0]]
    # SEUT callbacks target the active object's material rather than the owner.
    previous = bpy.context.view_layer.objects.active
    mesh = bpy.data.meshes.new('Temporary glass material context')
    host = bpy.data.objects.new('Temporary glass material context', mesh)
    bpy.context.scene.collection.objects.link(host)
    host.data.materials.append(material)
    bpy.context.view_layer.objects.active = host
    try:
        material.seut.color_add = profile['tint']
        material.seut.reflectivity = profile['reflection']
        material.seut.fresnel = profile['fresnel']
        material.seut.specular_color_factor = profile['specular']
    finally:
        bpy.context.view_layer.objects.active = previous
        bpy.data.objects.remove(host, do_unlink=True)
        bpy.data.meshes.remove(mesh)
    nodes, links = material.node_tree.nodes, material.node_tree.links
    for node, suffix in (('CM', 'ca'), ('NG', 'ng')):
        path = ROOT/'assets/textures/thermal'/('UniformGlass_'+suffix+'.png')
        image = bpy.data.images.load(str(path), check_existing=True)
        image.alpha_mode = 'CHANNEL_PACKED'
        image.colorspace_settings.name = 'Non-Color' if suffix == 'ng' else 'sRGB'
        nodes[node].image = image
    preview = nodes['Arcane clear glass preview']
    preview.inputs['Base Color'].default_value = profile['preview']
    preview.inputs['Roughness'].default_value = profile['roughness']
    preview.inputs['IOR'].default_value = 1.5
    preview.inputs['Metallic'].default_value = 0
    # Match SE's uniform body alpha and retain a restrained grazing reflection.
    dirt = nodes.get('AP glass dirt alpha') or nodes.new('ShaderNodeMath')
    dirt.name = 'AP glass dirt alpha'; dirt.operation = 'MULTIPLY_ADD'
    dirt.inputs[1].default_value = 0
    dirt.inputs[2].default_value = profile['tint'][3]
    links.new(nodes['CM'].outputs['Alpha'], dirt.inputs[0])
    grazing = nodes.get('AP glass grazing alpha') or nodes.new('ShaderNodeLayerWeight')
    grazing.name = 'AP glass grazing alpha'
    opacity = nodes.get('AP glass preview opacity') or nodes.new('ShaderNodeMath')
    opacity.name = 'AP glass preview opacity'; opacity.operation = 'MULTIPLY_ADD'; opacity.use_clamp = True
    opacity.inputs[1].default_value = profile['grazing']
    links.new(grazing.outputs['Fresnel'], opacity.inputs[0])
    links.new(dirt.outputs[0], opacity.inputs[2])
    links.new(opacity.outputs[0], preview.inputs['Alpha'])
    links.new(preview.outputs['BSDF'], next(n for n in nodes if n.type == 'OUTPUT_MATERIAL').inputs['Surface'])
    material.surface_render_method = 'BLENDED'
    material.diffuse_color = (*profile['preview'][:3], profile['tint'][3])
    material['thermal_uniform_glass_revision'] = 2
    material.update_tag()


def apply(write_definitions=True):
    import bpy
    updated = []
    for material in bpy.data.materials:
        if material.name.split('.')[0] in PROFILES:
            apply_material(material)
            updated.append(material.name)
    if write_definitions:
        write_native()
    return updated


if __name__ == '__main__':
    import bpy
    print('Updated smoked glass:', apply())
    bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
