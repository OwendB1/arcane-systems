"""Camera-aligned labels shared by the native Blender icon renderers."""
import bpy


def emission(name, color):
    material = bpy.data.materials.get(name)
    if material is None:
        material = bpy.data.materials.new(name)
        material.use_nodes = True
        nodes = material.node_tree.nodes
        nodes.clear()
        shader = nodes.new('ShaderNodeEmission')
        shader.inputs['Color'].default_value = (*color, 1)
        material.node_tree.links.new(shader.outputs[0], nodes.new('ShaderNodeOutputMaterial').inputs['Surface'])
    return material


def badge(scene, text, color, x):
    scale = scene.camera.data.ortho_scale
    mesh = bpy.data.meshes.new('Icon badge')
    mesh.from_pydata([(x, -.46, 0), (x+.22, -.46, 0), (x+.22, -.33, 0), (x, -.33, 0)], [], [(0, 1, 2, 3)])
    obj = bpy.data.objects.new('Icon badge', mesh)
    scene.collection.objects.link(obj)
    obj.parent = scene.camera
    obj.location.z = -2
    obj.scale = (scale, scale, scale)
    obj.data.materials.append(emission('Icon badge dark', (.012, .020, .030)))
    font = bpy.data.curves.new('Icon legend', 'FONT')
    font.body = text
    font.align_x = 'CENTER'
    font.align_y = 'CENTER'
    font.size = .09*scale
    font.space_character = 1.1
    label = bpy.data.objects.new('Icon legend', font)
    scene.collection.objects.link(label)
    label.parent = scene.camera
    label.location = ((x+.11)*scale, -.395*scale, -1.99)
    font.materials.append(emission('Icon legend '+text, color))
    for item in (obj, label):
        item.visible_shadow = False
        item.visible_diffuse = False
        item.visible_glossy = False
        item.visible_transmission = False
    return obj, label
