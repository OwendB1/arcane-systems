"""Original fuel geometry, periodic mineral textures, FBXs and rendered icons.

Run: blender -b --factory-startup --python ArcanePower/assets/build_fuel_assets.py
Then: python3 ArcanePower/tools/compile_fuel_assets.py
Owns only arcane-power-fuels.blend and the fuel asset folders; no reactor edits.
"""
import math
from pathlib import Path
import struct
import sys
import xml.etree.ElementTree as ET

import bpy
from mathutils import Vector
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT/'src/Models/Items/ArcanePower'
TEXTURES = ROOT/'src/Textures/Models/ArcanePower/Fuels'
VOXELS = ROOT/'src/Textures/Voxels/ArcanePower'
ICONS = ROOT/'assets/icons/fuels'
for folder in (MODELS, TEXTURES, VOXELS, ICONS):
    folder.mkdir(parents=True, exist_ok=True)
TIERS = [
    ('Aether', 'ArcaneOre', 'ArcaneAetherConcentrate', 'ArcaneFuelI', (.08, .76, .94)),
    ('Helion', 'ArcaneHelionOre', 'ArcaneHelionConcentrate', 'ArcaneFuelII', (1., .48, .055)),
    ('Empyrean', 'ArcaneEmpyreanOre', 'ArcaneEmpyreanConcentrate', 'ArcaneFuelIII', (.64, .22, .95)),
]


def tga(path, pixels):
    """Write exact packed channels, without a display colour transform."""
    h, w, _ = pixels.shape
    rgba = np.uint8(np.clip(pixels, 0, 1)*255+.5)
    header = struct.pack('<BBBHHBHHHHBB', 0, 0, 2, 0, 0, 0, 0, 0, w, h, 32, 40)
    path.write_bytes(header+rgba[:, :, [2, 1, 0, 3]].tobytes())


def packed(folder, name, cm, ng, add):
    for suffix, pixels in [('cm', cm), ('ng', ng), ('add', add)]:
        tga(folder/(name+'_'+suffix+'.tga'), pixels)


def constant_material(name, color, metallic, gloss, emission=0):
    cm = np.tile((*color, metallic), (16, 16, 1))
    ng = np.tile((.5, .5, 1, gloss), (16, 16, 1))
    add = np.tile((1, emission, 0, 0), (16, 16, 1))
    packed(TEXTURES, name, cm, ng, add)
    return material(name, TEXTURES, color, metallic, gloss, emission)


def material(name, folder, color, metallic, gloss, emission=0, textured=False):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Metallic'].default_value = metallic
    shader.inputs['Roughness'].default_value = 1-gloss
    shader.inputs['Emission Color'].default_value = (*color, 1)
    shader.inputs['Emission Strength'].default_value = emission
    # MwmBuilder ignores even XML materials when the FBX has no diffuse texture.
    # Wire the packed colour map for constant mechanical finishes as well as ore.
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    tex = nodes.new('ShaderNodeTexImage')
    tex.image = bpy.data.images.load(str(folder/(name+'_cm.tga')))
    tex.image.alpha_mode = 'CHANNEL_PACKED'
    links.new(tex.outputs['Color'], shader.inputs['Base Color'])
    links.new(tex.outputs['Color'], shader.inputs['Emission Color'])
    if textured:
        coords = nodes.new('ShaderNodeTexCoord')
        tex.projection = 'BOX'
        tex.projection_blend = .18
        links.new(coords.outputs['Generated'], tex.inputs['Vector'])
        bump = nodes.new('ShaderNodeBump')
        bump.inputs['Strength'].default_value = .4
        bump.inputs['Distance'].default_value = .015
        links.new(tex.outputs['Color'], bump.inputs['Height'])
        links.new(bump.outputs['Normal'], shader.inputs['Normal'])
    mat['texture_folder'] = folder.relative_to(ROOT/'src').as_posix()
    return mat


def deposit(name, color, seed):
    # Wrapped cellular fractures and Fourier strata: genuinely periodic in X/Y.
    size = 1024
    y, x = np.mgrid[:size, :size]/size
    rng = np.random.default_rng(seed)
    noise = np.zeros_like(x)
    for frequency, amplitude in [(3, .22), (9, .12), (27, .06), (81, .025)]:
        for _ in range(5):
            a, b = rng.integers(-frequency, frequency+1, 2)
            noise += amplitude*np.sin(math.tau*(a*x+b*y)+rng.uniform(0, math.tau))/5
    first = np.full_like(x, 10)
    second = first.copy()
    for px, py in rng.random((65, 2)):
        dx = (x-px+.5) % 1-.5
        dy = (y-py+.5) % 1-.5
        distance = np.sqrt(dx*dx+dy*dy)
        second = np.minimum(second, np.maximum(first, distance))
        first = np.minimum(first, distance)
    seam = np.exp(-((second-first)/.007)**2)
    crystals = np.clip(seam*(.7+noise*2), 0, 1)
    stone = np.clip(.16+noise, .035, .4)
    rgb = stone[:, :, None]*np.array([.65, .76, .9])
    rgb = rgb*(1-crystals[:, :, None]) + np.array(color)*crystals[:, :, None]
    height = noise*.2+crystals*.035
    dx = (np.roll(height, -1, 1)-np.roll(height, 1, 1))*12
    dy = (np.roll(height, -1, 0)-np.roll(height, 1, 0))*12
    normal = np.stack((-dx, dy, np.ones_like(x)), axis=2)
    normal /= np.linalg.norm(normal, axis=2)[:, :, None]
    cm = np.dstack((rgb, .05+crystals*.35))
    ng = np.dstack((normal*.5+.5, .15+crystals*.45))
    add = np.dstack((.8+crystals*.2, crystals*.12, np.zeros_like(x), np.zeros_like(x)))
    packed(VOXELS, name, cm, ng, add)
    packed(VOXELS, name+'_far', *[a.reshape(512, 2, 512, 2, 4).mean(axis=(1, 3)) for a in (cm, ng, add)])
    return material(name, VOXELS, color, .15, .3, .06, textured=True)


def finish(obj, name, mat, bevel=0):
    obj.name = name
    obj.data.materials.append(mat)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        mod = obj.modifiers.new('Machined edges', 'BEVEL')
        mod.width, mod.segments = bevel, 2
        bpy.ops.object.modifier_apply(modifier=mod.name)
        mod = obj.modifiers.new('Face normals', 'WEIGHTED_NORMAL')
        bpy.ops.object.modifier_apply(modifier=mod.name)
    return obj


def cylinder(name, radius, depth, z, mat, vertices=12, bevel=.003):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=(0, 0, z))
    return finish(bpy.context.object, name, mat, bevel)


def box(name, pos, size, mat, bevel=.003):
    bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
    obj = bpy.context.object
    obj.dimensions = size
    return finish(obj, name, mat, bevel)


def studio(scene):
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 48
    scene.cycles.use_denoising = True
    scene.render.resolution_x = scene.render.resolution_y = 512
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.world = bpy.data.worlds.new(scene.name+' studio')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.24, .27, .32, 1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value = .65
    scene.view_settings.view_transform = 'AgX'
    for name, pos, power, size in [('Key', (1, -2, 3), 160, 3), ('Fill', (-2, -1, 1), 110, 2), ('Rim', (1, 2, 2), 220, 2)]:
        data = bpy.data.lights.new(name, 'AREA')
        data.energy, data.size = power, size
        obj = bpy.data.objects.new(name, data)
        scene.collection.objects.link(obj)
        obj.location = pos
        obj.rotation_euler = (-obj.location).to_track_quat('-Z', 'Y').to_euler()
    data = bpy.data.cameras.new('Camera')
    cam = bpy.data.objects.new('Camera', data)
    scene.collection.objects.link(cam)
    cam.location = (.6, -1, .7)
    cam.rotation_euler = (-cam.location).to_track_quat('-Z', 'Y').to_euler()
    data.type = 'ORTHO'
    scene.camera = cam
    meshes = [o for o in scene.objects if o.type == 'MESH']
    corners = [cam.rotation_euler.to_matrix().transposed() @ (o.matrix_world @ v.co) for o in meshes for v in o.data.vertices]
    data.ortho_scale = 1.22*max(max(p[i] for p in corners)-min(p[i] for p in corners) for i in (0, 1))


def export(scene, folder=None):
    folder = folder or MODELS
    folder.mkdir(parents=True, exist_ok=True)
    meshes = [o for o in scene.objects if o.type == 'MESH']
    bpy.ops.object.select_all(action='DESELECT')
    for obj in meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    # Stock Blender FBX stores centimetres; MwmBuilder reads positions as metres.
    # SEUT's patched exporter uses a different scale, so do not copy its 0.1 here.
    bpy.ops.export_scene.fbx(filepath=str(folder/(scene.name+'.fbx')), use_selection=True,
        object_types={'MESH'}, global_scale=.01, axis_forward='Z', axis_up='Y',
        bake_anim=False, use_tspace=True, use_triangles=True, mesh_smooth_type='OFF')
    root = ET.Element('Model', Name=scene.name)
    for name, value in [('RescaleFactor', '1.0'), ('Centered', 'false'), ('RescaleToLengthInMeters', 'false')]:
        ET.SubElement(root, 'Parameter', Name=name).text = value
    for mat in sorted({slot.material for o in meshes for slot in o.material_slots}, key=lambda m: m.name):
        node = ET.SubElement(root, 'Material', Name=mat.name)
        ET.SubElement(node, 'Parameter', Name='Technique').text = 'MESH'
        for key, suffix in [('ColorMetalTexture', 'cm'), ('NormalGlossTexture', 'ng'), ('AddMapsTexture', 'add')]:
            ET.SubElement(node, 'Parameter', Name=key).text = mat['texture_folder']+'/'+mat.name+'_'+suffix+'.dds'
    ET.indent(root)
    ET.ElementTree(root).write(folder/(scene.name+'.xml'), encoding='utf-8', xml_declaration=True)
    if scene.camera is None:studio(scene)
    scene.render.filepath = str(ICONS/(scene.name+'.png'))
    bpy.ops.render.render(write_still=True)


def build_canister():
    # Reuse the fitted Aether shell with a dark, unpowered chamber/contact.
    old = bpy.data.scenes.get('ArcaneAetherCanister')
    if old:
        bpy.data.scenes.remove(old)
    scene = bpy.data.scenes.new('ArcaneAetherCanister')
    source = bpy.data.scenes['ArcaneFuelI']
    dark = bpy.data.materials['ArcaneFuelCeramic']
    for original in source.objects:
        if original.type != 'MESH':
            continue
        obj = original.copy()
        obj.data = original.data.copy()
        scene.collection.objects.link(obj)
        if original.name.startswith(('Sealed fuel core', 'Concentric contact')):
            obj.data.materials.clear()
            obj.data.materials.append(dark)
            obj.name = 'Empty containment chamber' if original.name.startswith('Sealed') else 'Unpowered contact'
    bpy.context.window.scene = scene
    bpy.context.view_layer.update()
    export(scene)
    print('FUEL ASSET ArcaneAetherCanister', flush=True)


def build_fuels():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    steel = constant_material('ArcaneFuelSteel', (.3, .36, .43), .75, .58)
    dark = constant_material('ArcaneFuelCeramic', (.035, .055, .08), .1, .35)
    for tier, (name, ore, concentrate, fuel, color) in enumerate(TIERS, 1):
        rock = deposit('Arcane'+name, color, 100+tier)
        crystal = constant_material('Arcane'+name+'Crystal', color, .4, .68, .18)
        # A restrained glow preserves tier colour under the game's bloom/exposure.
        light = constant_material('Arcane'+name+'FuelLight', color, .15, .5, .25)
        for kind, subtype in [('ore', ore), ('concentrate', concentrate), ('fuel', fuel)]:
            scene = bpy.data.scenes.new(subtype)
            bpy.context.window.scene = scene
            if kind == 'ore':
                bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=.16)
                obj = bpy.context.object
                rng = np.random.default_rng(tier)
                for v in obj.data.vertices:
                    v.co *= float(rng.uniform(.88, 1.12))
                    v.co.z *= .75
                finish(obj, 'Fractured mineral matrix', rock)
            elif kind == 'concentrate':
                # Bare refined hexagonal slug, with one/two/three assay notches.
                cylinder('Refined crystal slug', .10, .095, 0, crystal, 6, .012)
                cylinder('Cut assay face', .079, .004, .049, crystal, 6, .001)
                for i in range(tier):
                    box('Assay mark', ((i-(tier-1)/2)*.025, -.025, .052), (.010, .065, .003), dark, .001)
            else:
                cylinder('Sealed fuel core', .065, .23, 0, light)
                for z in (-.115, .115):
                    cylinder('Armored end cap', .087, .037, z, steel)
                    cylinder('Ceramic end inset', .065, .007, z+math.copysign(.022, z), dark)
                    cylinder('Concentric contact', .034, .010, z+math.copysign(.026, z), crystal)
                for angle in range(0, 360, 90):
                    a = math.radians(angle)
                    obj = box('Protective spine', (.072*math.sin(a), .072*math.cos(a), 0), (.026, .019, .205), dark)
                    obj.rotation_euler.z = -a
                for i in range(tier):
                    cylinder('Tier identification band', .076, .012, (i-(tier-1)/2)*.040, steel)
                for obj in scene.objects:
                    if obj.type == 'MESH':
                        obj.location *= 1.5
                        for vertex in obj.data.vertices:
                            vertex.co *= 1.5
            bpy.context.view_layer.update()
            export(scene)
            print('FUEL ASSET', subtype, flush=True)


def build_residuum(write_export=True):
    """Recovered metallic nugget; independent of the ore and fuel scenes."""
    name='ArcaneAetherResiduum'
    old=bpy.data.scenes.get(name)
    if old:
        for obj in list(old.objects):bpy.data.objects.remove(obj,do_unlink=True)
        bpy.data.scenes.remove(old)
    scene=bpy.data.scenes.new(name)
    bpy.context.window.scene=scene
    for mat in list(bpy.data.materials):
        if mat.name.startswith('ArcaneResiduum') and mat.users==0:bpy.data.materials.remove(mat)
    metal=constant_material('ArcaneResiduumMetal',(.24,.32,.36),1,.70)
    dark=constant_material('ArcaneResiduumVeins',(.17,.23,.26),1,.60)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2,radius=.055)
    obj=bpy.context.object
    rng=np.random.default_rng(704)
    for v in obj.data.vertices:
        v.co*=float(rng.uniform(.86,1.12))
        v.co.y*=.86
        v.co.z*=.68
    finish(obj,'Aether Residuum / collapsed metallic matrix',metal,.0009)
    obj.data.materials.append(dark)
    for face in obj.data.polygons:
        if face.index%17==0:face.material_index=1
    bpy.context.view_layer.update()
    if write_export:export(scene, ROOT/'.cache/residuum/models')
    return scene


if __name__ == '__main__':
    if '--residuum-only' in sys.argv:
        bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/arcane-power-fuels.blend'))
        build_residuum()
    else:
        if '--canister-only' in sys.argv:
            bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/arcane-power-fuels.blend'))
        else:
            build_fuels()
        build_canister()
        if '--canister-only' not in sys.argv:build_residuum()
    bpy.context.window.scene = bpy.data.scenes['ArcaneAetherResiduum' if '--residuum-only' in sys.argv else 'ArcaneFuelI']
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/arcane-power-fuels.blend'))
    print('Saved fuel-chain assets.', flush=True)
