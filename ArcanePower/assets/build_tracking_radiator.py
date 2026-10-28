"""One-cell airtight rotor base and separate, interchangeable radiator panels.

Run apply() in the visible production Blender session to rebuild only the base.
The existing two-cell-high panels retain their full three-cell-square sweep.
"""
import json
import math
from pathlib import Path
import runpy
import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
PIVOT = (0, 0, 1.0)
PART = 'Thermal_RadiatorPanels'
HEAT = [('ThermalRadiatorHeatRoot', (1,.16,.07,1), .12),
        ('ThermalRadiatorHeatMid', (1,.075,.035,1), .07),
        ('ThermalRadiatorHeatTip', (1,.035,.018,1), .0325)]


def axis_collar(p, label, bottom, top):
    """An actual annular bearing, with clearance around the rotating shaft."""
    collar=p.tube(label,[(0,0,bottom),(0,0,top)],.255,
                  'PaintedMetal_VeryDark',.040,48)
    collar.data.materials.append(p.native['Metal_Shiny'])
    bevel=collar.modifiers.new('2 mm machined bearing edges','BEVEL')
    bevel.width=.002;bevel.segments=1;bevel.material=1
    bpy.ops.object.select_all(action='DESELECT');collar.select_set(True)
    bpy.context.view_layer.objects.active=collar
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    collar['thermal_chamfer_m']=.002;collar['thermal_chamfer_segments']=1
    collar['thermal_bore_axis']=2
    for face in collar.data.polygons:
        face.use_smooth=abs(face.normal.z)<.01
    return collar


def side_pipe(p, x, bottom, top, stack_bottom=False, parent=None):
    """Shared pipe-block glass, stainless bands and sealed H/C couplings."""
    before=set(p.col.objects)
    glass=bpy.data.materials['ArcanePower_CoolantGlass']
    p.native[glass.name]=glass
    # The long pressure member is an opaque structural rib. Only the short
    # terminal collars have glass, backed by sealed opaque end plates.
    p.cylinder('side pipe metal rib',(x,0,bottom+.07),(x,0,top-.07),.15,'Metal_Dull',40)
    for low,high in ((bottom,bottom+.07),(top-.07,top)):
        p.cylinder('side pipe sealed end',(x,0,low),(x,0,high),.15,'Metal_Dull',40)
    ends=[(top-.10,top)]
    if stack_bottom:ends.append((bottom,bottom+.10))
    for low,high in ends:
        p.tube('side pipe glass collar',[(x,0,low),(x,0,high)],.18,glass.name,.025,40)
        z=(low+high)/2
        p.tube('side pipe flow indicator',[(x,0,z-.015),(x,0,z+.015)],
               .183,'ThermalHot' if x<0 else 'ThermalCold',.014,40)
    if parent:
        for obj in set(p.col.objects)-before:obj.parent=parent


def heat_material(p):
    flow = runpy.run_path(str(ROOT/'assets/refine_thermal_flow.py'))
    flow['materials'](p)
    folder=ROOT/'src/Textures/Models/ArcanePower/Thermal'
    img=bpy.data.images.get('Radiator graphite coating') or bpy.data.images.new('Radiator graphite coating',width=256,height=256,alpha=True)
    img.source='GENERATED';img.generated_width=256;img.generated_height=256
    img.colorspace_settings.name='sRGB';img.alpha_mode='CHANNEL_PACKED'
    coating=[]
    for y in range(256):
        for x in range(256):
            u,v=x/255,y/255
            # Subtle cold-state channels follow the same eight ribs as ADD.
            # Deterministic fine grain avoids dirty blobs or visible tiling noise.
            grain=((x*73+y*151+x*y*19)%257)/256-.5
            channel=.70 if (v*8)%1 < .055 else 1
            edge=.82 if min(u,v,1-u,1-v)<.045 else 1
            tone=channel*edge*(1+grain*.08)
            coating.extend((.18*tone,.20*tone,.22*tone,0))
    img.pixels.foreach_set(coating)
    img.filepath_raw=str(folder/'Radiator_cm.png');img.file_format='PNG';img.save()
    mask=bpy.data.images.get('Radiator ribbed emission mask') or bpy.data.images.new('Radiator ribbed emission mask',width=128,height=128,alpha=True)
    mask.colorspace_settings.name='Non-Color';mask.alpha_mode='CHANNEL_PACKED'
    pixels=[]
    for y in range(128):
        for x in range(128):
            u,v=x/127,y/127
            rim=min(1,max(0,min(u,v,1-u,1-v)-.045)/.12)
            rib=.20 if (v*8)%1 < .055 else 1
            pixels.extend((1,rim*rib*(.55+.45*u),0,0))
    mask.pixels.foreach_set(pixels);mask.filepath_raw=str(folder/'Radiator_add.png');mask.file_format='PNG';mask.save()
    for name,color,strength in HEAT:
        mat=bpy.data.materials.get(name)
        if mat is None:
            mat=p.native['ThermalStatus'].copy();mat.name=name
            group=mat.node_tree.nodes['SEUT_NODE_GROUP']
            group.node_tree=group.node_tree.copy()
            # Match native ADD green emissivity in the visible Blender preview.
            multiply=group.node_tree.nodes.new('ShaderNodeMath');multiply.operation='MULTIPLY'
            group.node_tree.links.new(group.node_tree.nodes['Group Input'].outputs['Emission Strength'],multiply.inputs[0])
            group.node_tree.links.new(group.node_tree.nodes['Separate RGB (Legacy)'].outputs['Green'],multiply.inputs[1])
            group.node_tree.links.new(multiply.outputs[0],group.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'])
        group=mat.node_tree.nodes['SEUT_NODE_GROUP']
        group.inputs['Color Override'].default_value=color
        group.inputs['Color Override Alpha'].default_value=0
        group.inputs['Emission Strength'].default_value=0
        mat.node_tree.nodes['CM'].image=img;mat.node_tree.nodes['ADD'].image=mask
        p.native[name]=mat


def panels(p,carrier_z,top_z):
    bottom,top=carrier_z+.18,top_z-.15
    height=top-bottom;middle=(bottom+top)/2;tile_height=(height-.07)/6
    carrier=p.box('panel carrier beam', (0, 0, carrier_z), (6.38, .48, .28), 'PaintedMetal_Colorable')
    # Two broad, double-sided graphite panels, 10 mm joints, rigid narrow frames.
    for x in (-1.52, 1.52):
        p.box('radiator panel substrate', (x, 0, middle), (2.84, .16, height), 'Metal_Dull')
        for side in (-1, 1):
            for col in range(3):
                for row in range(6):
                    tile=p.box('high emissivity radiator tile', (x+(col-1)*.91, side*.115, bottom+.01+tile_height/2+row*(tile_height+.01)),
                               (.90, .07, tile_height), HEAT[col if x>0 else 2-col][0], .001)
                    tile['radiating_surface']=True;tile['surface_side']=side
                    uv=tile.data.uv_layers.active
                    for face in tile.data.polygons:
                        for li in face.loop_indices:
                            v=tile.data.vertices[tile.data.loops[li].vertex_index].co
                            if abs(face.normal.y)>.99:
                                uv.data[li].uv=((.5-v.x/.90 if x>0 else .5+v.x/.90), .5+v.z/tile_height)
                            else:
                                axes=[i for i in range(3) if i!=max(range(3),key=lambda j:abs(face.normal[j]))]
                                uv.data[li].uv=[.02+(.5+v[i]/(.90,.07,tile_height)[i])*.02 for i in axes]
            for dx in (-1.43, 1.43):
                p.box('panel edge heat pipe', (x+dx, side*.10, middle), (.07, .20, height+.10), 'PaintedMetal_VeryDark')
            for dx in (-1.28, 1.28):
                for z in (bottom+.08, top-.08):
                    clip=p.box('radiator tile retention shoe', (x+dx, side*.18, z), (.24,.10,.10), 'Metal_Dull')
                    p.bolt('tile retention screw', (x+dx, side*.232, z), (0, side, 0), clip, .021)
    for z in (carrier_z,top_z):
        p.cylinder('radiator distribution header',(-3.05,0,z),(3.05,0,z),.10,'Metal_Dull',40)
    rail=p.box('radiator top rail',(0,0,top_z),(6.4,.45,.22),'PaintedMetal_Colorable')
    for side in (-1,1):
        p.label(rail,'SPACE RADIATOR / KEEP SWEEP CLEAR',(0,side*.227,top_z),(-side,0,0),(0,0,1),.092)


def apply():
    m = runpy.run_path(str(ROOT/'assets/build_thermal_models.py'))
    p = m['Parts']('Space radiator', existing=True)
    for obj in list(p.col.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    p.ports = []
    p.col.pop('thermal_seal_fit_revision', None)
    # Butt the side walls at the corners, sharing the pipe rotor's recessed
    # lamps. The radiator's deck seats inside the walls, 100 mm below their rim.
    flow = runpy.run_path(str(ROOT/'assets/refine_thermal_flow.py'))
    flow['materials'](p)
    rotor = runpy.run_path(str(ROOT/'assets/build_pipe_rotor.py'))
    rotor['side_shell'](p, detailed=True)
    for obj in p.col.objects:
        if obj.get('pipe_rotor_collision'):
            # Extend only the upper edge; preserve the service recess and UVs.
            for vertex in obj.data.vertices:
                if vertex.co.z > 1.10:vertex.co.z = 1.25
    bottom = p.box('pedestal socket surround', (0, 0, -1.20), (2.5, 2.5, .10), 'PaintedMetal_Colorable', 0)
    deck = p.box('pedestal bearing deck', (0, 0, 1.10), (2.30, 2.30, .10), 'PaintedMetal_Darker', 0)
    bottom['radiator_base_collision']=deck['radiator_base_collision']=True
    for obj in p.col.objects:
        if obj.get('pipe_rotor_collision'):obj['radiator_base_collision']=True
    for target, cutter in (
        (bottom, p.box('temporary socket aperture', (0, 0, -1.20), (1.98, 1.98, .4), chamfer=0)),
        (deck, p.cylinder('temporary shaft aperture', (0, 0, .9), (0, 0, 1.4), .260, sides=48))):
        bpy.context.view_layer.objects.active = target
        mod = target.modifiers.new('Sealed union aperture', 'BOOLEAN')
        mod.operation, mod.solver, mod.object = 'DIFFERENCE', 'EXACT', cutter
        bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(cutter, do_unlink=True)
        m['BUILD']['uv'](target)
    p.port('CO2', (0, 0, -1.25), (0, 0, -1), 'CO2_LP', (0, 1, 0))
    for sign in (-1, 1):
        p.tube('fixed coolant riser', [(0, sign*.46, -1.12), (0, sign*.46, .85)], .275, 'Metal_Dull', .045, 40)
    p.cylinder('fixed rotary union', (0, 0, .76), (0, 0, .92), .92, 'Metal_Dull', 64)
    seal=p.tube('rotary shaft pressure seal', [(0, 0, 1.03), (0, 0, 1.13)], .280, 'PaintedMetal_VeryDark', .075, 48)
    collar=axis_collar(p, 'stack axis collar', 1.10, 1.25)
    for obj in (deck,seal,collar):obj['lod_keep']=True
    for i in range(8):
        angle = i*math.tau/8
        point=Vector((math.cos(angle)*.90, math.sin(angle)*.90, 1.15))
        p.bolt('bearing deck bolt', point+Vector((0,0,.009)), (0, 0, 1), deck, .032)
    fixed = set(p.col.objects)
    p.cylinder('rotating union crown', (0, 0, .925), (0, 0, 1.04), .88, 'PaintedMetal_Darker', 64)
    p.cylinder('stack axis coupling', (0, 0, 1.035), (0, 0, 1.244), .21, 'Metal_Dull', 48)
    bpy.context.view_layer.update()
    root = bpy.data.objects.new('Space radiator / sun tracking pivot', None)
    p.col.objects.link(root)
    root.location = PIVOT; root['native_subpart'] = PART; root.empty_display_size = .3
    bpy.context.view_layer.update()
    for obj in set(p.col.objects)-fixed-{root}:
        world = obj.matrix_world.copy(); obj.parent = root
        obj.matrix_parent_inverse = Matrix.Identity(4)
        obj.matrix_basis = Matrix.Translation(-Vector(PIVOT))@world
    refinement = runpy.run_path(str(ROOT/'assets/refine_thermal_models.py'))
    refinement['tighten_ports'](p)
    for obj in p.col.objects:
        if obj.type == 'FONT' and obj.data.body == 'CO2 / LP':
            obj.location = (0, .92, -1.238)
    refinement['mesh_markings'](p)
    refinement['pressure_seal_fit'](p)
    for obj in p.col.objects:
        if obj.type == 'MESH': refinement['cylindrical_uv'](obj, Vector((.17, .31)))
    for face in deck.data.polygons: face.use_smooth = False
    flow['indicators'](p)
    # The old side-facing socket lamps are internal to the closed hull.
    # Put them on the bottom flange beside its two bores instead.
    c, n, up = Vector((0, 0, -1.25)), Vector((0, 0, -1)), Vector((0, 1, 0))
    across = up.cross(n)
    for label, inset in (('status bezel', .0185), ('status lens', .007)):
        obj = next(o for o in p.col.objects if o.name == p.name+' / CO2 '+label)
        obj.matrix_world = Matrix((across, up, n)).transposed().to_4x4()
        obj.location = c+across*.78-n*inset
    p.col['grid_cells'] = (1, 1, 1)
    for axis in ('X', 'Y', 'Z'): p.scene.seut['bBox_'+axis] = 1
    p.scene['radiator_tracking_revision'] = 3
    p.scene['thermal_detail_revision'] = p.scene['thermal_texture_revision'] = 1
    p.finish(); p.scene['thermal_phase'] = 'textures'
    data = json.loads((ROOT/'assets/thermal-flow-paths.json').read_text())
    data['models'][p.scene.name] = [flow['path_row']([(0, sign*.46, -1.25), (0, sign*.46, .85)],
        'CO2_LP', sign > 0, 0, .16, label='fixed pedestal riser') for sign in (-1, 1)]
    (ROOT/'assets/thermal-flow-paths.json').write_text(json.dumps(data, indent=2)+'\n')
    return m['record'](p.name)


def audit_base():
    """Closed casing, recessed deck, supported lamps and exact shaft seating."""
    import bmesh
    from mathutils.bvhtree import BVHTree
    m=runpy.run_path(str(ROOT/'assets/build_thermal_models.py'))
    scene=m['scene_for']('Space radiator');bpy.context.window.scene=scene;bpy.context.view_layer.update()
    col=m['main_for']('Space radiator');points=[];faces=[];solids=0
    for obj in col.objects:
        if obj.type!='MESH' or obj.get('thermal_text') or obj.get('source_asset'):continue
        bm=bmesh.new();bm.from_mesh(obj.data)
        assert all(e.is_manifold for e in bm.edges),obj.name
        bm.free();solids+=1
        offset=len(points);points.extend(obj.matrix_world@v.co for v in obj.data.vertices)
        faces.extend(tuple(offset+i for i in f.vertices) for f in obj.data.polygons)
    assert all(abs(p[i])<=1.2501 for p in points for i in range(3)), 'Base exceeds one cell'
    tree=BVHTree.FromPolygons(points,faces);samples=0
    for axis in range(3):
        for sign in (-1,1):
            for u in range(-12,13):
                for v in range(-12,13):
                    origin=Vector((0,0,0));origin[axis]=sign*1.30
                    origin[(axis+1)%3]=u*.10;origin[(axis+2)%3]=v*.10
                    direction=Vector((0,0,0));direction[axis]=-sign
                    assert tree.ray_cast(origin,direction,2.6)[0] is not None,('Open base',axis,sign,u,v)
                    samples+=1
    casing=[o for o in col.objects if o.get('radiator_base_collision')]
    assert len(casing)==6
    def bounds(obj):
        p=[obj.matrix_world@v.co for v in obj.data.vertices]
        return [min(v[i] for v in p) for i in range(3)],[max(v[i] for v in p) for i in range(3)]
    for i,a in enumerate(casing):
        lo,hi=bounds(a)
        for b in casing[i+1:]:
            low,high=bounds(b)
            assert min(min(hi[j],high[j])-max(lo[j],low[j]) for j in range(3))<1e-5,('Overlapping casing slabs',a.name,b.name)
    lamps=[o for o in col.objects if ' / recessed channel emitter' in o.name]
    assert len(lamps)==8 and all(o.get('pipe_rotor_emitter') for o in lamps)
    for obj in lamps:
        normal=obj.matrix_world.to_3x3()@Vector((0,0,1));centre=obj.matrix_world.translation
        nearest=tree.ray_cast(centre+normal*.05,-normal,.06)
        assert nearest[0] is not None and (nearest[0]-centre).length<.004,('Occluded emitter',obj.name)
    shaft=next(o for o in col.objects if ' / stack axis coupling' in o.name)
    assert abs(bounds(shaft)[1][2]-1.244)<1e-5
    deck=next(o for o in casing if ' / pedestal bearing deck' in o.name)
    assert all(abs(a-b)<1e-5 for a,b in zip(bounds(deck)[1],(1.15,1.15,1.15))), 'Deck must retain its 100 mm recess'
    bolts=[o for o in col.objects if ' / bearing deck bolt' in o.name]
    assert len(bolts)==8 and all(bounds(o)[0][2]>=1.149 and bounds(o)[1][2]>1.16 for o in bolts), 'Deck bolts must protrude'
    # The bearing has 5 mm radial deck clearance; the seal backs the gap below.
    aperture=min(math.hypot(v.co.x,v.co.y) for v in deck.data.vertices)
    assert abs(aperture-.260)<1e-5, 'Bearing clearance aperture changed'
    return {'status':'passed','closed_solids':solids,'hull_samples':samples,'casing_hulls':len(casing),'visible_side_lamps':len(lamps),'deck_recess_m':.10,'bearing_radial_clearance_m':.005}


def extension():
    """Equal-rated passive panel, stacked on the same axis with no extra pipe socket."""
    m=runpy.run_path(str(ROOT/'assets/build_thermal_models.py'))
    p=m['Parts']('Radiator panel',existing=m['CONTRACT']['subtype']('Radiator panel') in bpy.data.scenes)
    for obj in list(p.col.objects):bpy.data.objects.remove(obj,do_unlink=True)
    p.ports=[];heat_material(p)
    for z in (-2.5,2.41):
        axis_collar(p,'fixed axial dock',z,z+.09)
    fixed=set(p.col.objects)
    # 250 mm between horizontal frame rails at every stack joint. The block
    # centres remain exactly 3.75 m / 5 m apart on the large-grid lattice.
    panels(p,-2.235,2.265)
    for bottom,top in ((-2.494,-2.235),(2.265,2.494)):
        p.cylinder('rotating axial coupling',(0,0,bottom),(0,0,top),.21,'Metal_Dull',48)
    for x in (-3.05,3.05):side_pipe(p,x,-2.5,2.5,True)
    moving=set(p.col.objects)-fixed
    root=bpy.data.objects.new('Radiator panel / shared axis',None);p.col.objects.link(root)
    root['native_subpart']=PART;root.empty_display_size=.2
    for obj in moving:obj.parent=root
    for obj in list(p.col.objects):
        if obj.type=='FONT':
            obj['thermal_text']=obj.data.body;obj['thermal_decal_support']=obj['thermal_marking_support']
            bpy.ops.object.select_all(action='DESELECT');obj.select_set(True)
            bpy.context.view_layer.objects.active=obj;bpy.ops.object.convert(target='MESH')
            m['BUILD']['uv'](bpy.context.object)
    refinement=runpy.run_path(str(ROOT/'assets/refine_thermal_models.py'))
    for obj in p.col.objects:
        if obj.type=='MESH':refinement['cylindrical_uv'](obj,Vector((.17,.31)))
    p.scene['thermal_visibility_revision']=1
    p.scene['radiator_tracking_revision']=1
    p.scene['thermal_detail_revision']=p.scene['thermal_texture_revision']=1
    p.finish();p.scene['thermal_phase']='textures'
    data=json.loads((ROOT/'assets/thermal-flow-paths.json').read_text())
    data['models'][p.scene.name]=[]
    (ROOT/'assets/thermal-flow-paths.json').write_text(json.dumps(data,indent=2)+'\n')
    return m['record'](p.name)


def pose(angle=0, heat=0):
    m=runpy.run_path(str(ROOT/'assets/build_thermal_models.py'))
    bpy.context.window.scene=m['scene_for']('Space radiator')
    root=next(o for o in m['main_for']('Space radiator').objects if o.get('native_subpart')==PART)
    root.rotation_euler.z=angle
    for name,color,strength in HEAT:
        bpy.data.materials[name].node_tree.nodes['SEUT_NODE_GROUP'].inputs['Emission Strength'].default_value=heat*strength
    bpy.context.view_layer.update()


if __name__=='__main__':
    print(apply())
