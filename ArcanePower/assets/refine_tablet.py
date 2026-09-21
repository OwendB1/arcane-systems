import bpy,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];s=bpy.data.scenes['ArcanePower_Tablet'];bpy.context.window.scene=s
folder=ROOT/'src/Textures/Models/ArcanePower';native={m.name:m for m in bpy.data.materials if m.library}
def mat(name,color,gloss,emissive):
    material=bpy.data.materials.get(name) or native['Emissive'].copy();material.name=name
    for node,suffix,rgba in [('CM','cm',(*color,0)),('NG','ng',(.5,.5,1,gloss)),('ADD','add',(1,emissive,0,0))]:
        img=bpy.data.images.new(name+'_'+suffix,width=4,height=4,alpha=True)
        if suffix!='cm':img.colorspace_settings.name='Non-Color'
        img.pixels[:]=list(rgba)*16;img.file_format='TARGA';img.filepath_raw=str(folder/(name+'_'+suffix+'.tga'));img.save()
        material.node_tree.nodes[node].image=img
    return material
light=mat('ArcaneTabletLight',(.035,.6,.85),.5,1)
glass=mat('ArcaneTabletScreen',(.007,.018,.028),.7,0)
card=mat('ArcaneTabletCard',(.013,.037,.051),.4,0)
for o in s.objects:
    if o.type!='MESH' or o.rigid_body:continue
    if any('Emissive' in m.name for m in o.data.materials):o.data.materials.clear();o.data.materials.append(light)
    if 'glass display' in o.name:o.data.materials.clear();o.data.materials.append(glass)
    if 'screen card' in o.name and 'accent' not in o.name:o.data.materials.clear();o.data.materials.append(card)
# Physical engraved device label on lower bezel, no fabricated live readings.
main=next(c for c in s.collection.children if c.name.startswith('SEUT')) if False else None
import importlib
main=importlib.import_module('space-engineers-utilities.seut_collections').get_collections(s)['main'][0]
root=next(o for o in main.objects if o.type=='EMPTY')
font=bpy.data.curves.new('Arcane tablet wordmark','FONT');font.body='ARCANE';font.size=.012;font.align_x='CENTER';font.extrude=.0001
obj=bpy.data.objects.new('Tablet / engraved wordmark',font);main.objects.link(obj);obj.parent=root;obj.location=(0,-.034,.086);obj.rotation_euler=(math.pi/2,0,0);obj.data.materials.append(light)
bpy.context.view_layer.objects.active=obj;obj.select_set(True);bpy.ops.object.convert(target='MESH')
obj=bpy.context.object;obj.data.uv_layers.new(name='UVMap')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/arcane-power-prototype.blend'))
print('Tablet display has bespoke clean glass and cyan screen artwork materials.')
