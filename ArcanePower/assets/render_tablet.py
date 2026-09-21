import bpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];s=bpy.data.scenes['ArcanePower_Tablet'];bpy.context.window.scene=s
# Preview only: game script supplies emissive colour/intensity on the equipped item.
m=bpy.data.materials['ArcaneTabletLight'];n=m.node_tree.nodes;out=next(x for x in n if x.type=='OUTPUT_MATERIAL');em=n.new('ShaderNodeEmission');em.inputs['Color'].default_value=(.025,.6,1,1);em.inputs['Strength'].default_value=2.5;m.node_tree.links.new(em.outputs[0],out.inputs['Surface'])
s.render.resolution_x=1024;s.render.resolution_y=768;s.render.film_transparent=False;s.render.filepath=str(ROOT/'validation/tablet-model.png');bpy.ops.render.render(write_still=True)
s.render.resolution_x=512;s.render.resolution_y=512;s.render.film_transparent=True;s.render.filepath=str(ROOT/'assets/textures/Tablet.png');bpy.ops.render.render(write_still=True)
