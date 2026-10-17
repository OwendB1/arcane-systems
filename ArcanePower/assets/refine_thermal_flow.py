"""Native thermal indicator materials and one shared pipe-centreline contract.

Game draw code owns moving fluid; the temporary Blender preview consumes these
same paths. Existing reactor sources and accepted manifold mechanics stay separate.
"""
import json
import math
import copy
import xml.etree.ElementTree as ET
from pathlib import Path
import runpy
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(str(ROOT/'assets/build_thermal_models.py'))
REVISION = 1
COLOURS = {'ThermalHot': (1., .24, .035, 1.), 'ThermalCold': (.025, .48, .78, 1.),
           'ThermalStatus': (.025, .72, .32, 1.)}


def materials(p):
    folder = ROOT/'src/Textures/Models/ArcanePower/Thermal'
    folder.mkdir(parents=True, exist_ok=True)
    for name, color in COLOURS.items():
        mat = bpy.data.materials.get(name)
        if mat is None:
            mat = p.native['Emissive'].copy()
            mat.name = name
            mat['thermal_native_emissive'] = True
            for node, suffix, rgba in [('CM', 'cm', (1, 1, 1, 0)),
                                       ('NG', 'ng', (.5, .5, 1, .12)), ('ADD', 'add', (1, 1, 0, 0))]:
                key = 'Thermal indicator packed '+suffix
                img = bpy.data.images.get(key)
                if img is None:
                    img = bpy.data.images.new(key, width=16, height=16, alpha=True)
                    if suffix != 'cm': img.colorspace_settings.name = 'Non-Color'
                    img.alpha_mode = 'CHANNEL_PACKED'
                    img.pixels.foreach_set(list(rgba)*256)
                    img.filepath_raw = str(folder/('Indicator_'+suffix+'.png'))
                    img.file_format = 'PNG'; img.save()
                mat.node_tree.nodes[node].image = img
            group = mat.node_tree.nodes['SEUT_NODE_GROUP']
            group.node_tree = group.node_tree.copy()
            group.node_tree.links.new(group.node_tree.nodes['Group Input'].outputs['Color Override'],
                                      group.node_tree.nodes['Principled BSDF'].inputs['Emission Color'])
            group.inputs['Color Override'].default_value = color
            group.inputs['Color Override Alpha'].default_value = 1
            group.inputs['Emission Strength'].default_value = .65
        p.native[name] = mat


def indicators(p):
    for port in p.ports:
        reactor = p.name == 'Reactor housing'
        before=set(p.col.objects)
        c, n, up = (Vector(port[k]) for k in ('position', 'normal', 'hot_axis'))
        across = up.cross(n)
        frame = Matrix((across, up, n) if reactor else (-n, up, across)).transposed().to_4x4()
        for label, size, offset, material in [
                ('status bezel', (.075, .18 if reactor else .28, .025), -.1175 if reactor else -.0205, 'PaintedMetal_VeryDark'),
                ('status lens', (.045, .14 if reactor else .24, .012), -.100 if reactor else -.009, 'ThermalStatus')]:
            obj = p.box(port['id']+' '+label, (0, 0, 0), size, material, .002)
            obj.matrix_world = frame
            obj.location = c+across*.24+n*offset if reactor else c-n*.10+across*(1.0325 if label=='status bezel' else 1.050)
            obj['thermal_flow_fixture'] = True
        for hot in (False, True):
            at = c+up*(.46 if hot else -.46)-n*(.11 if reactor else .205)
            band = p.tube(port['id']+' '+('hot' if hot else 'cold')+' indicator',
                          [at-n*.015, at+n*.015], .277 if reactor else .360,
                          'ThermalHot' if hot else 'ThermalCold', .014 if reactor else .012, 40)
            band['thermal_flow_fixture'] = True
        if reactor:
            bpy.context.view_layer.update()
            row=next(r for r in json.loads(p.col['manifold_motion']) if 'primary '+r['id']==port['id'])
            carriage=bpy.data.objects[row['carriage']]
            for obj in set(p.col.objects)-before:
                local=Matrix.Translation(Vector(row['deployed_face'])).inverted()@obj.matrix_world
                obj.parent=carriage
                obj.matrix_parent_inverse=Matrix.Identity(4)
                obj.matrix_basis=local
                obj['thermal_motion_group']=carriage.name


def path_row(points, circuit, hot, port, radius, inside=False, label=''):
    points = [list(map(float, v)) for v in points]
    assert len(points) >= 2 and all(math.dist(a, b) > 1e-7 for a, b in zip(points, points[1:])), label
    return dict(points=points, circuit=circuit, hot=bool(hot), port=port,
                radius=round(radius, 5), internal=inside, label=label)


def paths(p):
    rows = []
    if p.name == 'Reactor housing':
        # Chamber plumbing is authored separately and recorded in reactor_paths.
        rows.extend(json.loads(p.col.get('thermal_internal_flow_paths', '[]')))
        for i, port in enumerate(p.ports):
            for hot in (False, True):
                at = Vector(port['position'])+Vector(port['hot_axis'])*(.46 if hot else -.46)
                end = Vector((math.copysign(3.15, at.x), at.y, at.z))
                rows.append(path_row([at, end], 'PRIMARY', hot, i, .16, label='deployed manifold bore'))
    shape = p.col.get('pipe_shape')
    if shape in ('Tee', 'Cross'):
        for hot in (False, True):
            centre = Vector((0, 0, .46 if hot else -.46))
            for i, port in enumerate(p.ports):
                end = Vector(port['position'])+Vector(port['hot_axis'])*(.46 if hot else -.46)
                rows.append(path_row([end, centre], port['type'], hot, i, .22, label='branch '+str(i)))
    else:
        for obj in p.col.objects:
            if obj.type != 'MESH' or not obj.get('thermal_pressure_glass') or not obj.get('pipe_path'):
                continue
            points = list(map(Vector, json.loads(obj['pipe_path'])))
            if obj.get('thermal_internal_coolant'):
                continue
            candidates = [(min((points[end]-(Vector(port['position'])+Vector(port['hot_axis'])*sign*.46)).length
                               for end in (0, -1)), i, sign)
                          for i, port in enumerate(p.ports) for sign in (-1, 1)]
            if not candidates: continue
            error, port, sign = min(candidates)
            if error > .42: continue
            socket = Vector(p.ports[port]['position'])+Vector(p.ports[port]['hot_axis'])*sign*.46
            if (points[-1]-socket).length < (points[0]-socket).length: points.reverse()
            rows.append(path_row(points, p.ports[port]['type'], sign > 0, port,
                                 min(.22, obj['pipe_radius']*.65), label=obj.name))
    return rows


def record(p):
    target = ROOT/'assets/thermal-flow-paths.json'
    data = json.loads(target.read_text()) if target.exists() else {'revision': REVISION, 'models': {}}
    data['models'][p.scene.name] = paths(p)
    target.write_text(json.dumps(data, indent=2)+'\n')
    return {'model': p.name, 'paths': len(data['models'][p.scene.name])}


def apply(name):
    p = M['Parts'](name, existing=True)
    materials(p)
    if name == 'Reactor housing':
        reactor_plumbing(p)
        reactor_sight_frames(p)
        reactor_tube_contrast(p)
        if p.scene.get('thermal_manifold_indicator_revision') != 2:
            for obj in list(p.col.objects):
                if obj.get('thermal_flow_fixture') and any(obj.name.startswith(name+' / '+port['id']+' ') for port in p.ports):
                    bpy.data.objects.remove(obj,do_unlink=True)
            indicators(p)
            p.scene['thermal_manifold_indicator_revision']=2
            p.scene['thermal_flow_revision']=REVISION
    if name != 'Reactor housing' and p.scene.get('thermal_indicator_revision') != 2:
        for obj in list(p.col.objects):
            if obj.get('thermal_flow_fixture'):
                bpy.data.objects.remove(obj,do_unlink=True)
        indicators(p)
        p.scene['thermal_indicator_revision']=2
        p.scene['thermal_flow_revision'] = REVISION
    coolant_glass(p)
    uniform_glass_materials()
    runpy.run_path(str(ROOT/'assets/refine_thermal_models.py'))['pressure_seal_fit'](p)
    external_pipe_jackets(p)
    row = record(p)
    M['record'](name)
    return row


def reactor_plumbing(p):
    """Floor-level distributor, paired pump heads and visible chamber injection."""
    if p.col.get('thermal_chamber_coolant_revision') == REVISION:
        return
    V = runpy.run_path(str(ROOT/'assets/refine_thermal_visibility.py'))
    rows = []
    # Preserve the established riser envelope and couplings, opening only these
    # solid authoring cylinders into actual hollow pressure-glass sight lengths.
    risers = [o for o in p.col.objects if o.type == 'MESH' and
              o.get('reactor_source_name', '').startswith('Coolant riser pipe')]
    for i, old in enumerate(sorted(risers, key=lambda o:o.name)):
        ps = [old.matrix_world@v.co for v in old.data.vertices]
        x, y = sum(v.x for v in ps)/len(ps), sum(v.y for v in ps)/len(ps)
        path = [(x, y, min(v.z for v in ps)), (x, y, max(v.z for v in ps))]
        obj = p.tube('temporary hollow riser', path, .126, 'Metal_Shiny', .026, 48)
        obj.data.transform(old.matrix_world.inverted())
        old.data = obj.data
        for key in ('pipe_path', 'pipe_radius'): old[key] = obj[key]
        old['thermal_internal_coolant'] = True
        bpy.data.objects.remove(obj, do_unlink=True)
        rows.append(path_row(path if i%2 else path[::-1], 'PRIMARY', bool(i%2==0), -1, .075, True, old.name))
    radius = 4.78
    def at(angle, r, z): return Vector((r*math.cos(angle), r*math.sin(angle), z))
    for hot, z in ((True, -.70), (False, -.98)):
        for quarter in range(4):
            path = [at((quarter+i/32)*math.pi/2, radius, z) for i in range(33)]
            if not hot: path.reverse()
            obj = p.tube(('hot collection' if hot else 'cold supply')+' distributor quadrant '+str(quarter),
                         path, .10, 'Metal_Dull', .025, 24)
            obj['thermal_internal_coolant'] = True
            rows.append(path_row(path, 'PRIMARY', hot, -1, .06, True, obj.name))
    for i in range(4):
        angle = i*math.pi/2
        n = Vector((math.cos(angle), math.sin(angle), 0));t = Vector((-n.y,n.x,0))
        body = p.box('chamber circulation pump '+str(i), at(angle,radius,-.915),
                     (.56,.56,.65), 'PaintedMetal_Darker', .003)
        body['thermal_coolant_pump'] = True
        # The four distributor joints live within these sealed pump bodies.
        cap = p.box('pump service lid '+str(i),at(angle,radius,-.574),
                    (.46,.46,.032),'Metal_Dull',.003)
        p.bolt('pump lid captive stud', at(angle,radius,-.556), (0,0,1), cap, .025)
        for hot in (False,True):
            a = angle+math.radians(2 if hot else -2)
            height = .16 if hot else .62
            ring_z = -.70 if hot else -.98
            path = [at(a,4.78,ring_z),at(a,4.78,height),at(a,4.54,height)]
            path = V['rounded_path'](path,.14)
            if hot: path.reverse()
            obj = p.tube(('warm chamber pickup ' if hot else 'chamber injector feed ')+str(i),
                          path,.085,'Metal_Dull',.022,32)
            obj['thermal_internal_coolant'] = True
            rows.append(path_row(path,'PRIMARY',hot,-1,.045,True,obj.name))
            tip = at(a,4.54,height)
            collar = p.tube(('pickup' if hot else 'injector')+' mouth '+str(i),
                           [tip+n*.015,tip-n*.030],.105,'Metal_Dull',.042,32)
            collar['thermal_flow_fixture'] = True
            band = p.tube('chamber '+('return' if hot else 'feed')+' emissive '+str(i),
                         [tip+n*.055,tip+n*.085],.090,'ThermalHot' if hot else 'ThermalCold',.010,32)
            band['thermal_flow_fixture'] = True
            if not hot:
                rows.append(path_row([tip-n*.035,tip-n*.30], 'CHAMBER',False,-1,.045,True,'chamber injection mist '+str(i)))
        lens=p.box('pump running light '+str(i),at(angle,radius,-.552)+t*.13,
                   (.045,.09,.012),'ThermalStatus',.002)
        lens['thermal_flow_fixture']=True
    V['transparent_pipes'](p)
    # Small 170 mm injector feeds also need visible sight lengths.
    for obj in p.col.objects:
        if obj.type!='MESH' or not obj.get('thermal_internal_coolant') or obj.get('thermal_pressure_glass'): continue
        slot,_=V['glass_slots'](p,obj)
        path=list(map(Vector,json.loads(obj['pipe_path'])))
        for face in obj.data.polygons:
            point=obj.matrix_world@face.center
            if min((point-path[0]).length,(point-path[-1]).length)>.14:
                face.material_index=slot
        obj['thermal_pressure_glass']=True
    p.col['thermal_internal_flow_paths']=json.dumps(rows)
    p.col['thermal_chamber_coolant_revision']=REVISION


def reactor_sight_frames(p):
    """Seated metal elbows and guarded windows keep clear feeds legible."""
    if p.col.get('thermal_sight_frames_revision') == 5:
        return
    for obj in list(p.col.objects):
        if obj.name.startswith((p.name+' / injector sight window seat',p.name+' / injector sight window guard')):
            bpy.data.objects.remove(obj,do_unlink=True)
    for obj in list(p.col.objects):
        if obj.name.startswith(p.name+' / chamber circulation pump '):
            a=int(obj.name.rsplit(' ',1)[1])*math.pi/2
            position=(4.78*math.cos(a),4.78*math.sin(a),-.915)
            temp=p.box('temporary seated pump',position,(.56,.56,.65),'PaintedMetal_Darker',.003)
            obj.data=temp.data;obj.matrix_world=Matrix.Translation(Vector(position))
            bpy.data.objects.remove(temp,do_unlink=True)
        if obj.name.startswith(p.name+' / pump service lid '):
            a=int(obj.name.rsplit(' ',1)[1])*math.pi/2
            position=(4.78*math.cos(a),4.78*math.sin(a),-.574)
            temp=p.box('temporary seated pump lid',position,(.46,.46,.032),'Metal_Dull',.003)
            obj.data=temp.data;obj.matrix_world=Matrix.Translation(Vector(position))
            bpy.data.objects.remove(temp,do_unlink=True)
        if obj.name.startswith(p.name+' / pump lid captive stud'):
            support=bpy.data.objects[obj['thermal_support']]
            a=int(support.name.rsplit(' ',1)[1])*math.pi/2
            point=Vector((4.78*math.cos(a),4.78*math.sin(a),-.556))
            temp=p.cylinder('temporary seated pump stud',point-Vector((0,0,.009)),
                            point+Vector((0,0,.009)),.025,'Metal_Shiny',6)
            obj.data=temp.data;obj.matrix_world=Matrix.Identity(4);obj['support_point']=tuple(point)
            bpy.data.objects.remove(temp,do_unlink=True)
        if obj.name.startswith(p.name+' / pump running light '):
            obj.location.z = -.552
        if not obj.name.startswith((p.name+' / chamber injector feed ', p.name+' / warm chamber pickup ')):
            continue
        path = list(map(Vector, json.loads(obj['pipe_path'])))
        low, high = max(-.49,min(v.z for v in path)+.20), max(v.z for v in path)-.22
        # Sight boundaries must be real mesh rings. A long unsplit quad cannot
        # carry metal ends and a glass centre based on its face centroid.
        split = [path[0]]
        for a,b in zip(path,path[1:]):
            cuts = [((z-a.z)/(b.z-a.z),z) for z in (low,high)
                    if abs(b.z-a.z)>1e-6 and min(a.z,b.z)<z<max(a.z,b.z)]
            split.extend(a.lerp(b,t) for t,z in sorted(cuts))
            split.append(b)
        temp=p.tube('temporary framed sight tube',split,.085,'Metal_Dull',.022,32)
        temp.data.transform(obj.matrix_world.inverted())
        obj.data=temp.data
        bpy.data.objects.remove(temp,do_unlink=True)
        runpy.run_path(str(ROOT/'assets/refine_thermal_visibility.py'))['glass_slots'](p,obj)
        metal = next(i for i, mat in enumerate(obj.data.materials) if mat and mat.name == 'Metal_Dull')
        glass = obj.data.materials.find('ArcanePower_ClearChamber')
        for face in obj.data.polygons:
            c = obj.matrix_world@face.center
            face.material_index = glass if low < c.z < high else metal
        base = min(path, key=lambda v:v.z).copy()
        radial = Vector((base.x,base.y,0)).normalized()
        tangent = Vector((-radial.y,radial.x,0))
        for z in (low,high):
            centre=Vector((base.x,base.y,z))
            clamp=p.tube('injector sight window seat',[centre-Vector((0,0,.018)),centre+Vector((0,0,.018))],
                         .098,'Metal_Dull',.033,32)
            clamp['thermal_flow_fixture']=True
        for side in (-1,1):
            rail=base+tangent*(side*.087)
            p.tube('injector sight window guard',[(rail.x,rail.y,low),(rail.x,rail.y,high)],
                   .010,'Metal_Dull',.004,12)['thermal_flow_fixture']=True
    p.col['thermal_sight_frames_revision']=5


def coolant_glass(p, internal=False):
    """Reflective external glass; preserve the accepted internal coolant finish."""
    name = 'ArcanePower_InternalCoolantGlass' if internal else 'ArcanePower_CoolantGlass'
    glass = bpy.data.materials.get(name)
    if glass is None:
        glass = bpy.data.materials['ArcanePower_ClearChamber'].copy()
        glass.name = name
    glass['thermal_native_glass'] = True
    p.native[name] = glass
    active = bpy.context.view_layer.objects.active
    mesh = bpy.data.meshes.new('Temporary coolant glass context')
    host = bpy.data.objects.new('Temporary coolant glass context', mesh)
    p.col.objects.link(host)
    mesh.materials.append(glass)
    bpy.context.view_layer.objects.active = host
    try:
        glass.seut.color = (.42, .60, .68, .62)
        glass.seut.color_add = (.006, .009, .012, .16 if internal else .10)
        glass.seut.reflectivity = .22 if internal else .45
        glass.seut.fresnel = .70 if internal else .90
        glass.seut.specular_color_factor = 6 if internal else 8
    finally:
        bpy.context.view_layer.objects.active = active
        bpy.data.objects.remove(host, do_unlink=True)
        bpy.data.meshes.remove(mesh)
    nodes = glass.node_tree.nodes
    preview = nodes['Arcane clear glass preview']
    preview.inputs['Base Color'].default_value = (.10, .18, .22, 1) if internal else (.28, .42, .48, 1)
    preview.inputs['Roughness'].default_value = .19 if internal else .075
    preview.inputs['IOR'].default_value = 1.48 if internal else 1.50
    nodes['AP glass dirt alpha'].inputs[1].default_value = .35
    nodes['AP glass dirt alpha'].inputs[2].default_value = .24 if internal else .18
    nodes['AP glass preview opacity'].inputs[1].default_value = .20 if internal else .40
    glass.diffuse_color = (.10, .18, .22, .40) if internal else (.28, .42, .48, .30)
    # The native glass ID has its own definition; the outer chamber stays clear.
    file = ROOT/'src/Data/TransparentMaterials.sbc'
    tree = ET.parse(file)
    definitions = tree.getroot().find('TransparentMaterials')
    definition = next((d for d in definitions if d.findtext('Id/SubtypeId') == name), None)
    if definition is None:
        definition = copy.deepcopy(next(d for d in definitions if d.findtext('Id/SubtypeId') == 'ArcanePower_ClearChamber'))
        definitions.append(definition)
    definition.find('Id/SubtypeId').text = name
    for key, values in [('Color',glass.seut.color),('ColorAdd',glass.seut.color_add)]:
        for axis,value in zip(('X','Y','Z','W'),values): definition.find(key+'/'+axis).text = str(round(value,5))
    for key,value in [('Reflectivity',glass.seut.reflectivity),('Fresnel',glass.seut.fresnel),('SpecularColorFactor',glass.seut.specular_color_factor)]:
        definition.find(key).text = str(round(value,5))
    ET.indent(tree); tree.write(file,encoding='utf-8',xml_declaration=True)
    return glass


def uniform_glass_materials():
    """Remove window-edge dirt from custom glass, in SE and its live preview.

    Native Glass/Pixel.hlsl multiplies Color by the CA texture, then adds
    ColorAdd and reflections. Zero CA makes the baseline haze uniform and
    leaves angle-dependent reflections intact. A flat NG removes gloss dirt.
    """
    folder = ROOT/'assets/textures/thermal'
    folder.mkdir(parents=True, exist_ok=True)
    images = {}
    for suffix, rgba in [('ca', (0, 0, 0, 0)), ('ng', (.5, .5, 1, .25))]:
        key = 'Arcane uniform glass '+suffix
        img = bpy.data.images.get(key)
        if img is None:
            img = bpy.data.images.new(key, width=16, height=16, alpha=True)
            img.alpha_mode = 'CHANNEL_PACKED'
            img.colorspace_settings.name = 'Non-Color' if suffix == 'ng' else 'sRGB'
            img.pixels.foreach_set(list(rgba)*256)
            img.filepath_raw = str(folder/('UniformGlass_'+suffix+'.png'))
            img.file_format = 'PNG'
            img.save()
        images[suffix] = img
    for mat in bpy.data.materials:
        if not mat.name.startswith(('ArcanePower_ClearChamber', 'ArcanePower_CoolantGlass', 'ArcanePower_InternalCoolantGlass')):
            continue
        nodes = mat.node_tree.nodes
        nodes['CM'].image = images['ca']
        nodes['NG'].image = images['ng']
        # The existing preview alpha expression now samples constant zero CA.
        mat['thermal_uniform_glass_revision'] = 1
    file = ROOT/'src/Data/TransparentMaterials.sbc'
    tree = ET.parse(file)
    for definition in tree.getroot().find('TransparentMaterials'):
        if definition.findtext('Id/SubtypeId') not in ('ArcanePower_ClearChamber', 'ArcanePower_CoolantGlass', 'ArcanePower_InternalCoolantGlass'):
            continue
        for tag, suffix in [('Texture', 'ca'), ('GlossTexture', 'ng')]:
            definition.find(tag).text = 'Textures/Models/ArcanePower/Thermal/UniformGlass_'+suffix+'.dds'
    ET.indent(tree)
    tree.write(file, encoding='utf-8', xml_declaration=True)


def external_pipe_jackets(p):
    """Seated stainless rings and smoked sight lengths, matching side struts.

    Only authored fluid pressure walls qualify. Keep telescoping fits clear:
    their existing glands provide the rings; no added clamp travels into a bore.
    """
    if p.col.get('thermal_external_jacket_revision') == 2:
        return
    glass = p.native['ArcanePower_CoolantGlass']
    V = runpy.run_path(str(ROOT/'assets/refine_thermal_visibility.py'))
    for obj in list(p.col.objects):
        if obj.get('thermal_external_pipe_clamp'):
            bpy.data.objects.remove(obj, do_unlink=True)
    # Reclassify from the authored paths, recovering walls that revision 1
    # changed to metal. End fittings remain outside the glass sight length.
    V['transparent_pipes'](p)
    tubes = [o for o in p.col.objects if o.type == 'MESH' and o.get('thermal_pressure_glass')
             and not o.get('thermal_internal_coolant') and (o.get('pipe_path') or
             (p.col.get('pipe_shape') in ('Tee', 'Cross') and ' / connected ' in o.name))]
    for obj in tubes:
        if obj.data.users > 1:
            obj.data = obj.data.copy()
        if obj.get('pipe_path'):
            paths = [list(map(Vector, json.loads(obj['pipe_path'])))]
            radius = obj['pipe_radius']
            # Clamp spacing stays anchored to the socket face when the
            # pressure wall is shortened behind its insert and seal.
            if obj.get('thermal_seal_fit_revision'):
                for end in (0,-1):
                    for port in p.ports:
                        for sign in (-1,1):
                            socket = Vector(port['position'])+Vector(port['hot_axis'])*(sign*.46)
                            if (paths[0][end]-socket).length < .12:
                                paths[0][end] = socket
        else:
            z = .46 if 'connected H ' in obj.name else -.46
            centre = Vector((0, 0, z))
            paths = [[centre, Vector((x, y, z))] for x, y in
                     [(-1.25, 0), (1.25, 0), (0, 1.25)]+
                     ([(0, -1.25)] if p.col['pipe_shape'] == 'Cross' else [])]
            radius = .355
        for mat in (glass, p.native['Metal_Dull']):
            if mat.name not in obj.data.materials:
                obj.data.materials.append(mat)
        window = obj.data.materials.find(glass.name)
        metal = obj.data.materials.find('Metal_Dull')
        telescopic = bool(obj.get('thermal_motion_group')) or 'fixed telescopic sleeve' in obj.name
        for face in obj.data.polygons:
            mat = obj.data.materials[face.material_index]
            if mat.seut.technique == 'GLASS':
                face.material_index = window
            elif mat.name.startswith('PaintedMetal'):
                face.material_index = metal
        obj['thermal_external_pipe_style'] = 2
        if telescopic:
            continue
        for path in paths:
            lengths = [(b-a).length for a, b in zip(path, path[1:])]
            total = sum(lengths)
            if total < 1.02:
                continue
            margin = .48 if len(paths) == 1 else max(.50, radius*1.45)
            span = total-2*margin
            count = 1 if span < .45 else math.ceil(span/.85)+1
            for i in range(count):
                at = total/2 if count == 1 else margin+(total-2*margin)*i/(count-1)
                remaining = at
                for a, b, length in zip(path, path[1:], lengths):
                    if remaining <= length+1e-6:
                        direction = (b-a).normalized()
                        centre = a+direction*remaining
                        band = p.tube('pressure sight-glass clamp',
                                      [centre-direction*.035, centre+direction*.035],
                                      radius+.018, 'Metal_Shiny', .030, 32)
                        # Bypass bends can pass beside a socket before the
                        # centreline has travelled far from its endpoint.
                        # Keep the full 150 mm socket neck and sampled bore clear.
                        tree = BVHTree.FromPolygons([band.matrix_world@v.co for v in band.data.vertices],
                                                    [list(f.vertices) for f in band.data.polygons])
                        blocked = False
                        for port in p.ports:
                            c, n, up = (Vector(port[k]) for k in ('position', 'normal', 'hot_axis'))
                            across = up.cross(n)
                            for sign in (-1, 1):
                                bore = c+up*(sign*.46)
                                samples = [bore]+[bore+.20*(across*math.cos(j*math.tau/8)+up*math.sin(j*math.tau/8)) for j in range(8)]
                                if any(tree.ray_cast(point+n*.05, -n, .20)[0] is not None for point in samples):
                                    blocked = True
                        if blocked:
                            bpy.data.objects.remove(band, do_unlink=True)
                            break
                        band['thermal_external_pipe_clamp'] = True
                        band['thermal_seated_on'] = obj.name
                        band['thermal_clamp_path_distance'] = at
                        band['thermal_clamp_radius'] = radius
                        break
                    remaining -= length
    p.col['thermal_external_jacket_revision'] = 2


def reactor_tube_contrast(p):
    """Smoked sight glass inside a metal pressure jacket, with seated clamps."""
    glass = coolant_glass(p, internal=True)
    name = glass.name
    tubes = [o for o in p.col.objects if o.type == 'MESH' and o.get('thermal_internal_coolant')]
    if p.col.get('thermal_tube_contrast_revision') == 2: return
    for obj in list(p.col.objects):
        if obj.get('thermal_tube_jacket'): bpy.data.objects.remove(obj,do_unlink=True)
    V = runpy.run_path(str(ROOT/'assets/refine_thermal_visibility.py'))
    for obj in tubes:
        path = list(map(Vector,json.loads(obj['pipe_path'])))
        radius = obj['pipe_radius']
        riser = obj.get('reactor_source_name','').startswith('Coolant riser pipe')
        if name not in obj.data.materials: obj.data.materials.append(glass)
        if 'Metal_Dull' not in obj.data.materials: obj.data.materials.append(p.native['Metal_Dull'])
        metal, window = obj.data.materials.find('Metal_Dull'), obj.data.materials.find(name)
        for face in obj.data.polygons:
            material = obj.data.materials[face.material_index]
            point = obj.matrix_world@face.center
            sight = riser and min((point-end).length for end in (path[0],path[-1])) > .14
            if not material or not (material.seut.technique == 'GLASS' or sight): continue
            centre = V['nearest'](point,path)
            inward = -Vector((centre.x,centre.y,0)).normalized()
            visible = -inward if riser else inward
            face.material_index = window if (point-centre).normalized().dot(visible) > 0 else metal
        # Three clamps per sight length. End collars and pump joints remain clear.
        lengths = [(b-a).length for a,b in zip(path,path[1:])]
        total = sum(lengths)
        for fraction in (.20,.50,.80):
            remaining = total*fraction
            for a,b,length in zip(path,path[1:],lengths):
                if remaining <= length:
                    direction = (b-a).normalized();centre = a+direction*remaining
                    band = p.tube('coolant jacket clamp',[centre-direction*.035,centre+direction*.035],
                                  radius+.018,'Metal_Shiny',min(.04,radius*.35),32)
                    band['thermal_tube_jacket'] = True
                    break
                remaining -= length
        if obj.get('reactor_source_name','').startswith('Coolant riser pipe'):
            inward = -Vector((path[0].x,path[0].y,0)).normalized()
            tangent = Vector((-inward.y,inward.x,0))
            for side in (-1,1):
                offset = inward*.025+tangent*(side*(radius+.004))
                rail = p.cylinder('coolant riser jacket rail',path[0]+offset+Vector((0,0,.10)),
                                  path[-1]+offset-Vector((0,0,.10)),.012,'Metal_Dull',12)
                rail['thermal_tube_jacket'] = True
    p.col['thermal_tube_contrast_revision'] = 2
