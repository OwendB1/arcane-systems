"""Static preview of the real exported geometry with fuel-tinted emission."""
import bpy,importlib,json,math
from pathlib import Path
from mathutils import Matrix,Vector
ROOT=Path(__file__).resolve().parents[1]
COLS=importlib.import_module('space-engineers-utilities.seut_collections')
data=json.loads((ROOT/'assets/deployment.json').read_text())
scene=bpy.data.scenes.new('Plasma material review');bpy.context.window.scene=scene
scene.render.engine='CYCLES';scene.cycles.samples=32
scene.render.resolution_x=1800;scene.render.resolution_y=820;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.world=bpy.data.worlds.new('Plasma dark studio');scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.025,.035,.05,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.4
camera=bpy.data.objects.new('Camera',bpy.data.cameras.new('Camera'));scene.collection.objects.link(camera);scene.camera=camera
camera.location=(0,-15,6.5);camera.rotation_euler=(-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.type='ORTHO';camera.data.ortho_scale=12.8
for name,pos,energy,size in [('Key',(1,-4,7),1400,7),('Rim',(-5,3,3),1700,5)]:
    d=bpy.data.lights.new(name,'AREA');d.energy=energy;d.shape='DISK';d.size=size
    o=bpy.data.objects.new(name,d);scene.collection.objects.link(o);o.location=pos;o.rotation_euler=(-o.location).to_track_quat('-Z','Y').to_euler()

def emissive(name,color,strength,texture=False):
    m=bpy.data.materials.new(name);m.use_nodes=True;n=m.node_tree.nodes;n.clear();out=n.new('ShaderNodeOutputMaterial');emit=n.new('ShaderNodeEmission');emit.inputs['Color'].default_value=(*color,1);emit.inputs['Strength'].default_value=strength;m.node_tree.links.new(emit.outputs[0],out.inputs['Surface'])
    if texture:
        tex=n.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(ROOT/'assets/textures/plasma-filaments-source.png'),check_existing=True)
        mult=n.new('ShaderNodeMixRGB');mult.blend_type='MULTIPLY';mult.inputs[0].default_value=1;mult.inputs[2].default_value=(*color,1)
        m.node_tree.links.new(tex.outputs['Color'],mult.inputs[1]);m.node_tree.links.new(mult.outputs[0],emit.inputs['Color'])
    return m

def copy_parts(name,matrix,edge,plasma):
    for source in COLS.get_collections(bpy.data.scenes[name])['main'][0].objects:
        if source.type!='MESH':continue
        o=bpy.data.objects.new(source.name+' review',source.data.copy());scene.collection.objects.link(o);o.matrix_world=matrix @ source.matrix_world
        for i,m in enumerate(o.data.materials):
            if m and m.name=='Emissive':o.data.materials[i]=edge
            if m and m.name=='ArcanePlasma':o.data.materials[i]=plasma

for tier,color in enumerate([(.06,.55,1),(1,.38,.045),(.48,.09,1)],1):
    x=(tier-2)*4.05;placement=Matrix.Translation((x,0,0));center=Vector(data['center'])
    edge=emissive('T'+str(tier)+' field edge',color,3)
    plasma=emissive('T'+str(tier)+' plasma review',color,5,True)
    copy_parts('ArcanePower_Plasma',placement,edge,plasma)
    for t in data['tiles']:
        matrix=Matrix(t['rotation']).to_4x4();matrix.translation=Vector(t['final'])-center
        copy_parts(t['model'],placement @ matrix,edge,plasma)
    for r in data['rings'][:tier+1]:
        matrix=Matrix.Rotation(math.radians(r['tilt_degrees']),4,Vector(r['axis']))
        copy_parts('ArcanePower_'+r['name'],placement @ matrix,edge,plasma)
    font=bpy.data.curves.new('Tier label','FONT');font.body=f'TIER {tier}  /  {tier+1} RINGS';font.align_x='CENTER';font.size=.23
    label=bpy.data.objects.new('Tier label',font);scene.collection.objects.link(label);label.location=(x,-.5,-2.02);label.rotation_euler=camera.rotation_euler
    font.materials.append(emissive('Label '+str(tier),(.55,.67,.8),.7))
scene.render.filepath=str(ROOT/'validation/plasma-fuel-review.png')
bpy.ops.render.render(write_still=True)
print('Rendered static fuel plasma review',flush=True)
