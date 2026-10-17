"""Sample evaluated authoring motion independently of the native export axes."""
import json
import math
from pathlib import Path
import runpy
import bpy
import numpy as np
from mathutils import Matrix

ROOT=Path(__file__).resolve().parents[1]


def build():
    export=runpy.run_path(str(ROOT/'assets/export_thermal_models.py'))
    rig=runpy.run_path(str(ROOT/'assets/build_reactor_thermal_manifolds.py'))
    original=bpy.context.scene
    source=export['M']['scene_for']('Reactor housing')
    old=source['thermal_manifolds_deployment']
    models=[]
    try:
        for name in ('Reactor housing','Brayton train','Brayton train upgraded'):
            scene=export['M']['scene_for'](name)
            bpy.context.window.scene=scene
            bpy.context.view_layer.update()
            groups=export['subparts'](name,export['M']['main_for'](name))
            parts=[{'name':part,'samples':[]} for part,_,_ in groups]
            values=[i/46 for i in range(47)] if name=='Reactor housing' else [0,math.pi/2,math.pi,3*math.pi/2,2*math.pi]
            for value in values:
                if name=='Reactor housing':rig['pose'](value)
                deps=bpy.context.evaluated_depsgraph_get()
                for row,(_,objects,pivot) in zip(parts,groups):
                    clouds=[]
                    for obj in objects:
                        if obj.type!='MESH':continue
                        evaluated=obj.evaluated_get(deps)
                        mesh=evaluated.to_mesh()
                        try:
                            points=np.empty(len(mesh.vertices)*3,dtype=np.float32)
                            mesh.vertices.foreach_get('co',points)
                            points=points.reshape((-1,3))
                            transform=evaluated.matrix_world
                            if name!='Reactor housing':
                                transform=Matrix.Translation(pivot)@Matrix.Rotation(value,4,'X')@Matrix.Translation(-pivot)@transform
                            matrix=np.array(transform)
                            points=points@matrix[:3,:3].T+matrix[:3,3]
                            # Authoring main frame, not SEUT's subpart frame.
                            clouds.append(points[:,[0,2,1]]*[-1,1,1])
                        finally:evaluated.to_mesh_clear()
                    points=np.concatenate(clouds)
                    row['samples'].append({'value':value,'bounds':[points.min(axis=0).tolist(),points.max(axis=0).tolist()]})
            models.append({'name':name,'subtype':export['M']['CONTRACT']['subtype'](name),'parts':parts})
        target=ROOT/'assets/thermal-native-motion-contract.json'
        target.write_text(json.dumps({'coordinate_frame':'SE reactor-local = (-BlenderX, BlenderZ, BlenderY)',
                                     'source':'Evaluated production meshes and authoring drivers','models':models},indent=2)+'\n')
        return {'models':len(models),'moving_parts':sum(len(m['parts']) for m in models),'path':str(target)}
    finally:
        rig['pose'](old)
        bpy.context.window.scene=original
        bpy.context.view_layer.update()


if __name__=='__main__':result=build()
