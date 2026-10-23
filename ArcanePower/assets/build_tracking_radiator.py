"""Reviewed radiator: fixed bottom duplex socket, full-cell pedestal, yawing panels.

Run apply() in the visible production Blender session. Only this main is rebuilt.
The 3-cell square envelope contains the entire sweep; the 2.5 m pedestal is fixed.
"""
import json
import math
from pathlib import Path
import runpy
import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
PIVOT = (0, 0, -1.1)
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
    heat_material(p)
    # A hollow pedestal seats the manifold without a solid slab closing its bores.
    for x in (-1.14, 1.14):
        p.box('pedestal side armor', (x, 0, -2.5), (.20, 2.48, 2.5), 'PaintedMetal_Colorable')
    for y in (-1.14, 1.14):
        p.box('pedestal end armor', (0, y, -2.5), (2.08, .20, 2.5), 'PaintedMetal_Colorable')
    deck = p.box('pedestal bearing deck', (0, 0, -1.33), (2.08, 2.08, .16), 'PaintedMetal_Darker')
    for y in (-1, 1):
        door = p.panel('rotary union service cover', (0, y*1.249, -2.55), (1.66, .018, 1.66), (0, y, 0))
        p.label(door, 'ROTARY CO2 / AUTO TRACK', (0, y*1.260, -2.13), (y*-1, 0, 0), (0, 0, 1), .086)
        for x in (-.48, .48):
            p.box('service handle foot', (x, y*1.28, -2.84), (.07, .07, .11), 'Metal_Dull')
        p.box('service handle', (0, y*1.32, -2.84), (1.02, .045, .07), 'Metal_Dull')
    p.port('CO2', (0, 0, -3.75), (0, 0, -1), 'CO2_LP', (0, 1, 0))
    for sign in (-1, 1):
        p.tube('fixed coolant riser', [(0, sign*.46, -3.52), (0, sign*.46, -1.40)], .275, 'Metal_Dull', .045, 40)
    p.cylinder('fixed rotary union', (0, 0, -1.30), (0, 0, -1.10), .92, 'Metal_Dull', 64)
    for i in range(12):
        a=i*math.tau/12
        p.bolt('bearing deck bolt', (math.cos(a)*.99, math.sin(a)*.99, -1.242), (0, 0, 1), deck, .035)
    fixed=set(p.col.objects)
    p.cylinder('rotating union crown', (0, 0, -1.085), (0, 0, -.91), .88, 'PaintedMetal_Darker', 64)
    p.cylinder('rotary shaft', (0, 0, -.92), (0, 0, -.76), .42, 'Metal_Dull', 48)
    p.box('carrier bearing saddle', (0, 0, -.715), (1.12, 1.0, .09), 'PaintedMetal_Darker')
    panels(p,-.57,3.515)
    for x in (-3.05,3.05):side_pipe(p,x,-.70,3.75)
    p.cylinder('stack axis coupling',(0,0,3.515),(0,0,3.744),.21,'Metal_Dull',48)
    axis_collar(p,'stack axis collar',3.66,3.75)
    # Distribution runs inside the carrier beam. Only the two straight,
    # solid-capped vertical side pipes remain exposed above the rotary union.
    bpy.context.view_layer.update()
    moving=set(p.col.objects)-fixed
    root=bpy.data.objects.new('Space radiator / sun tracking pivot',None);p.col.objects.link(root)
    root.location=PIVOT;root['native_subpart']=PART;root.empty_display_size=.3
    bpy.context.view_layer.update()
    for obj in moving:
        world=obj.matrix_world.copy();obj.parent=root
        obj.matrix_parent_inverse=Matrix.Identity(4);obj.matrix_basis=Matrix.Translation(-Vector(PIVOT))@world
    refinement=runpy.run_path(str(ROOT/'assets/refine_thermal_models.py'))
    refinement['tighten_ports'](p)
    for obj in p.col.objects:
        if obj.type=='FONT' and obj.data.body=='CO2 / LP':obj.location=(0,.92,-3.738)
    # Convert authored labels to exportable meshes, keeping parent-local transforms.
    for obj in list(p.col.objects):
        if obj.type=='FONT':
            obj['thermal_text']=obj.data.body
            obj['thermal_decal_support']=obj['thermal_marking_support']
            bpy.ops.object.select_all(action='DESELECT');obj.select_set(True)
            bpy.context.view_layer.objects.active=obj;bpy.ops.object.convert(target='MESH')
            m['BUILD']['uv'](bpy.context.object)
    refinement['pressure_seal_fit'](p)
    for obj in p.col.objects:
        if obj.type=='MESH':refinement['cylindrical_uv'](obj, Vector((.17,.31)))
    flow=runpy.run_path(str(ROOT/'assets/refine_thermal_flow.py'))
    flow['indicators'](p)
    p.col['grid_cells']=(3,3,3)
    for axis in ('X','Y','Z'):p.scene.seut['bBox_'+axis]=3
    p.scene['radiator_tracking_revision']=1
    p.scene['thermal_detail_revision']=p.scene['thermal_texture_revision']=1
    p.finish();p.scene['thermal_phase']='textures';m['record'](p.name)
    # Opaque rotary plumbing hides the transfer beyond the stationary bottom bores.
    data=json.loads((ROOT/'assets/thermal-flow-paths.json').read_text())
    data['models'][p.scene.name]=[flow['path_row']([(0,s*.46,-3.75),(0,s*.46,-1.40)],'CO2_LP',s>0,0,.16,label='fixed pedestal riser') for s in (-1,1)]
    (ROOT/'assets/thermal-flow-paths.json').write_text(json.dumps(data,indent=2)+'\n')
    return m['record'](p.name)


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
    # centres remain exactly 6.25 m / 5 m apart on the large-grid lattice.
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
