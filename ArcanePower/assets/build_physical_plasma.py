"""Apply the reviewed plasma texture, open tile frames and physical debris collision."""
import bpy, bmesh, importlib, math
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
COLS = importlib.import_module('space-engineers-utilities.seut_collections')
checkpoint = ROOT/'assets/arcane-power-before-physical-plasma.blend'
if not checkpoint.exists():
    bpy.ops.wm.save_as_mainfile(filepath=str(checkpoint), copy=True)
original_scene = bpy.context.window.scene
template = next(o for o in bpy.data.objects if o.type == 'MESH' and o.rigid_body)
native = {m.name:m for m in bpy.data.materials if m.library}

def mesh(name, vertices, faces, material, collection, parent):
    data=bpy.data.meshes.new(name); data.from_pydata(vertices,[],faces)
    bm=bmesh.new(); bm.from_mesh(data); bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces)); bm.to_mesh(data); bm.free()
    data.materials.append(material)
    uv=data.uv_layers.new(name='UVMap')
    for p in data.polygons:
        for j in p.loop_indices:
            v=data.vertices[data.loops[j].vertex_index].co; uv.data[j].uv=(v.x+.5,v.y+.5)
    obj=bpy.data.objects.new(name,data); collection.objects.link(obj); obj.parent=parent
    return obj

def collision_collection(scene):
    cols=COLS.get_collections(scene)
    if cols['hkt']: result=cols['hkt'][0]
    else:
        result=bpy.data.collections.new('Collision - Main ('+scene.name+')')
        cols['seut'][0].children.link(result)
        result.seut.scene=scene; result.seut.col_type='hkt'; result.seut.version=3
        result.seut.ref_col=cols['main'][0]
    for o in list(result.objects): bpy.data.objects.remove(o,do_unlink=True)
    return result

def collider(name, vertices, faces, collection, parent):
    obj=template.copy(); obj.data=bpy.data.meshes.new(name); obj.data.from_pydata(vertices,[],faces)
    obj.data.uv_layers.new(name='UVMap')
    obj.data.materials.append(native['Metal_Dull'])
    obj.name=name; collection.objects.link(obj); obj.parent=parent
    obj.matrix_basis.identity(); obj.rigid_body.collision_shape='CONVEX_HULL'
    return obj

def prism(points, low, high):
    n=len(points); v=[(x,y,z) for z in (low,high) for x,y in points]
    f=[tuple(reversed(range(n))),tuple(range(n,2*n))]
    f += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    return v,f

def rim(points, inside, low, high):
    v=[(x*k,y*k,z) for z in (low,high) for k in (1,inside) for x,y in points]
    f=[]
    for i in range(3):
        j=(i+1)%3
        f.extend([(i,j,j+6,i+6),(i+3,i+9,j+9,j+3),(i+6,j+6,j+9,i+9),(i,i+3,j+3,j)])
    return v,f

# Preserve the generated artwork; only resize and pack technical SE texture channels.
folder=ROOT/'src/Textures/Models/ArcanePower'; folder.mkdir(parents=True,exist_ok=True)
image=bpy.data.images.load(str(ROOT/'assets/textures/plasma-filaments-source.png'),check_existing=True)
image.scale(2048,1024)
pixels=np.empty(2048*1024*4,dtype=np.float32); image.pixels.foreach_get(pixels)
pixels.reshape((-1,4))[:,3]=0
def packed(name,w,h,data):
    result=bpy.data.images.new(name,width=w,height=h,alpha=True)
    if name.endswith(('_ng','_add')): result.colorspace_settings.name='Non-Color'
    result.pixels.foreach_set(data); result.filepath_raw=str(folder/(name+'.tga')); result.file_format='TARGA'; result.save()
    return result
cm=packed('ArcanePlasma_cm',2048,1024,pixels)
add=packed('ArcanePlasma_add',4,4,[1,1,0,0]*16)
ng=packed('ArcanePlasma_ng',4,4,[.5,.5,1,0]*16)
mat=bpy.data.materials.get('ArcanePlasma')
if not mat:
    mat=native['Emissive'].copy(); mat.name='ArcanePlasma'
for node,img in [('CM',cm),('ADD',add),('NG',ng)]: mat.node_tree.nodes[node].image=img

scene=bpy.data.scenes['ArcanePower_Plasma']; bpy.context.window.scene=scene
main=COLS.get_collections(scene)['main'][0]; parent=next(o for o in main.objects if o.type=='EMPTY')
for o in list(main.objects):
    if o.type=='MESH': bpy.data.objects.remove(o,do_unlink=True)
bpy.ops.mesh.primitive_uv_sphere_add(segments=64,ring_count=32,radius=.60)
orb=bpy.context.object; orb.name='Plasma / turbulent energy core'
for col in list(orb.users_collection): col.objects.unlink(orb)
main.objects.link(orb); orb.parent=parent; orb.data.materials.append(mat)
for p in orb.data.polygons: p.use_smooth=True
hc=collision_collection(scene)
bm=bmesh.new(); bmesh.ops.create_icosphere(bm,subdivisions=2,radius=.60)
bm.verts.ensure_lookup_table(); bm.verts.index_update()
collider('Collision / plasma core',[v.co[:] for v in bm.verts],[[v.index for v in f.verts] for f in bm.faces],hc,parent); bm.free()

for number in (1,2):
    scene=bpy.data.scenes['ArcanePower_Tile'+str(number)]; main=COLS.get_collections(scene)['main'][0]
    parent=next(o for o in main.objects if o.type=='EMPTY')
    old=next(o for o in main.objects if o.type=='MESH' and 'frame' in o.name.lower())
    points=[tuple(v.co[:2]) for v in list(old.data.vertices)[:3]]
    for o in list(main.objects):
        if o.type=='MESH': bpy.data.objects.remove(o,do_unlink=True)
    v,f=rim(points,.72,-.0225,.0225); mesh('Tile / open containment frame',v,f,native['PaintedMetal_VeryDark'],main,parent)
    v,f=rim([(x*.91,y*.91) for x,y in points],.86,.0226,.027)
    mesh('Tile / luminous frame edge',v,f,native['Emissive'],main,parent)
    hc=collision_collection(scene)
    for i in range(3):
        j=(i+1)%3; quad=[points[i],points[j],tuple(x*.72 for x in points[j]),tuple(x*.72 for x in points[i])]
        v,f=prism(quad,-.0225,.027); collider('Collision / tile edge '+str(i),v,f,hc,parent)

for number,radius in enumerate((1.09,1.29,1.49,1.69),1):
    scene=bpy.data.scenes['ArcanePower_Ring'+str(number)]; main=COLS.get_collections(scene)['main'][0]
    parent=next(o for o in main.objects if o.type=='EMPTY'); hc=collision_collection(scene)
    for i in range(8):
        a=i*math.tau/8; b=(i+1)*math.tau/8
        pts=[(r*math.cos(t),r*math.sin(t)) for r,t in [(radius-.045,a),(radius+.045,a),(radius+.045,(a+b)/2),(radius+.045,b),(radius-.045,b)]]
        v,f=prism(pts,-.052,.052); collider('Collision / ring segment '+str(i),v,f,hc,parent)

bpy.context.window.scene=original_scene
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/arcane-power-prototype.blend'))
print('Plasma texture/sphere, two open tile frames and seven physical collision scenes saved.')
