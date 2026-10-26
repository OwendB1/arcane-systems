"""Four recessed floor vents, driven by the existing Brayton deployment state."""
import json
import math

import bpy
from mathutils import Matrix, Vector


def apply(p):
    revision = p.col.get('chamber_floor_vent_revision', 0)
    if revision == 2:
        return {'already_applied':True}
    # Rebuild only the vent fittings; the floor openings are already machined.
    for obj in list(p.col.objects):
        if obj.get('thermal_floor_vent'):
            bpy.data.objects.remove(obj,do_unlink=True)
    retired = ('hot collection distributor','cold supply distributor','chamber injector feed',
               'warm chamber pickup','chamber circulation pump','pump service lid',
               'pump lid captive stud','pump running light','injector mouth','pickup mouth',
               'chamber feed emissive','chamber return emissive','injector sight window')
    removed = []
    for obj in list(p.col.objects):
        label = obj.name.removeprefix(p.name+' / ')
        chamber_clamp = obj.get('thermal_tube_jacket') and obj.type == 'MESH' and all(
            (obj.matrix_world@v.co).xy.length < 5.5 for v in obj.data.vertices)
        if label.startswith(retired) or chamber_clamp:
            removed.append(obj.name)
            bpy.data.objects.remove(obj,do_unlink=True)
    root = next(o for o in p.col.objects if o.get('reactor_source_name') == 'ArcanePower_ReactorPrototype root')
    deck = [o for o in p.col.objects if o.get('reactor_source_name','').startswith(
        ('Segmented access deck','Lower machinery drum','Deck removable plate'))]
    assert len(deck) > 2

    def box(label, frame, position, size, material='Metal_Dull',chamfer=.003):
        obj = p.box('floor vent '+label,(0,0,0),size,material,chamfer)
        obj.parent = root
        obj.matrix_basis = frame@Matrix.Translation(position)
        obj['thermal_floor_vent'] = True
        return obj

    for i,bay in enumerate(('LA','LB','RA','RB')):
        angle = i*math.pi/2
        n = Vector((math.cos(angle),math.sin(angle),0));t = Vector((-n.y,n.x,0))
        frame = Matrix((t,-n,Vector((0,0,1)))).transposed().to_4x4()
        frame.translation = n*4.45+Vector((0,0,-1.260))
        # Machine a real well through both floor skins. The accepted walkable
        # floor collider remains; the fixed grille explains that support.
        cutter = None if revision else box('temporary opening',frame,(0,0,-.28),(.90,.56,.66),chamfer=.004)
        bpy.context.view_layer.update()
        cp = [cutter.matrix_world@Vector(v) for v in cutter.bound_box] if cutter else []
        for target in deck if cutter else []:
            tp = [target.matrix_world@Vector(v) for v in target.bound_box]
            if any(max(v[k] for v in tp) < min(v[k] for v in cp) or min(v[k] for v in tp) > max(v[k] for v in cp) for k in range(3)):
                continue
            if target.data.users > 1: target.data = target.data.copy()
            mod = target.modifiers.new('Floor vent well','BOOLEAN')
            mod.operation = 'DIFFERENCE';mod.solver = 'EXACT';mod.object = cutter
            bpy.context.view_layer.objects.active = target
            bpy.ops.object.modifier_apply(modifier=mod.name)
        if cutter:
            bpy.data.objects.remove(cutter,do_unlink=True)
        # One rebated rim, rather than four touching bars. The upper lip overlaps
        # the cover by 6 mm and clears its top by 2 mm. Keeping the existing lid
        # and hinge preserves clearance through the complete inward swing.
        rings = [(.54,.37,-.032),(.54,.37,.008),(.424,.244,.008),
                 (.424,.244,.002),(.44,.28,.002),(.44,.28,-.032)]
        verts = [(x*w,y*h,z) for w,h,z in rings
                 for x,y in ((-1,-1),(1,-1),(1,1),(-1,1))]
        faces = [(k*4+j,k*4+(j+1)%4,((k+1)%6)*4+(j+1)%4,((k+1)%6)*4+j)
                 for k in range(6) for j in range(4)]
        rim = p.mesh('floor vent '+bay+' rebated rim',verts,faces,'PaintedMetal_Darker')
        rim.parent = root;rim.matrix_basis = frame
        rim['thermal_floor_vent'] = True
        # A dark solid well retains the existing floor level.
        for side in (-1,1):
            box(bay+' well side',frame,(side*.445,0,-.29),(.020,.56,.56),'PaintedMetal_VeryDark')
            box(bay+' well end',frame,(0,side*.275,-.29),(.87,.020,.56),'PaintedMetal_VeryDark')
        box(bay+' well floor',frame,(0,0,-.57),(.90,.56,.035),'PaintedMetal_VeryDark')
        for j in range(9):
            box(bay+' safety grille',frame,(-.4+j*.1,0,-.535),(.018,.51,.022),'Metal_Dull',.002)
        for side in (-1,1):
            box(bay+' status seat',frame,(side*.49,0,.010),(.050,.30,.012),'PaintedMetal_VeryDark',.002)
            box(bay+' status lens',frame,(side*.49,0,.018),(.025,.24,.008),
                'ThermalCold' if side<0 else 'ThermalHot',.001)
        # Hinge in the outboard edge: the cover swings into its own well, away
        # from the chamber and safely inside the original block/collision shell.
        anchor = frame@Vector((0,-.25,-.010))
        hinge = bpy.data.objects.new('Thermal chamber vent '+bay+' hinge',None)
        p.col.objects.link(hinge);hinge.parent = root
        hinge.location = anchor;hinge.rotation_mode = 'AXIS_ANGLE'
        hinge.rotation_axis_angle = (0,*t)
        hinge['native_subpart'] = 'Thermal_'+bay+'_ChamberVent'
        hinge['thermal_floor_vent'] = True
        lid = box(bay+' cover',frame,(0,0,-.010),(.86,.50,.020),'PaintedMetal_Colorable',.002)
        bpy.context.view_layer.update()
        world = lid.matrix_world.copy();lid.parent = hinge;lid.matrix_world = world
        driver = hinge.driver_add('rotation_axis_angle',0).driver
        var = driver.variables.new();var.name = 'deploy';var.type = 'SINGLE_PROP'
        var.targets[0].id_type = 'SCENE';var.targets[0].id = p.scene
        var.targets[0].data_path = '["thermal_manifolds_deployment"]'
        driver.expression = '-pi/2*max(0,min(1,(deploy-.15)/.75))'
    p.col['chamber_floor_vent_revision'] = 2
    if not revision:
        p.col['retired_chamber_plumbing'] = json.dumps(removed)
    bpy.context.view_layer.update()
    return {'floor_vents':4,'removed_chamber_parts':len(removed)}
