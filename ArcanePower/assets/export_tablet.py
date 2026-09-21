import bpy,importlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
s=bpy.data.scenes['ArcanePower_Tablet']; bpy.context.window.scene=s
importlib.import_module('space-engineers-utilities.seut_errors').show_popup_report=lambda c,t,x:print(t,x,flush=True)
area=next(a for a in bpy.context.screen.areas if a.type=='VIEW_3D')
with bpy.context.temp_override(area=area,region=next(r for r in area.regions if r.type=='WINDOW')):
    print('TABLET EXPORT',bpy.ops.scene.export(),flush=True)
s.render.filepath=str(ROOT/'validation/tablet-model.png'); bpy.ops.render.render(write_still=True)
