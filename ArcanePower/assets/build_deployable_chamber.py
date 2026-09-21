"""Author SEUT subparts and the direct-script motion manifest; no Blender timeline animation.

Run against the saved engineering prototype. Inspection copies are outside Main,
so one reactor MWM references all four rings, four leaves and eighty solid tiles.
"""
import bpy
import bmesh
import importlib
import json
import math
from pathlib import Path
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
COLS = importlib.import_module('space-engineers-utilities.seut_collections')
s = bpy.data.scenes['ArcanePower_ReactorPrototype']
bpy.context.window.scene = s
col = COLS.get_collections(s)['main'][0]
root = next(o for o in col.objects if o.parent is None)
native = {m.name: m for m in bpy.data.materials if m.library}
CENTER = Vector((0, 0, .575))
RADII = (1.09, 1.29, 1.49, 1.69)
PARK_Z = -2.20

# Save an explicit checkpoint before the first conversion, not on every rebuild.
checkpoint = ROOT/'assets/arcane-power-before-deployment.blend'
if not checkpoint.exists():
    bpy.ops.wm.save_as_mainfile(filepath=str(checkpoint), copy=True)

inspection = bpy.data.collections.get('AP assembled inspection (not exported)')
if inspection:
    for o in list(inspection.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.collections.remove(inspection)
inspection = bpy.data.collections.new('AP assembled inspection (not exported)')
s.collection.children.link(inspection)
for o in list(col.objects):
    if (o.name.startswith(('Dispenser ', 'V03 / Dispenser ', 'subpart_Ring',
                           'subpart_Tile', 'subpart_Floor', 'subpart_Plasma',
                           'AP dispenser /', 'AP floor /'))
            or o.name == 'Prototype faceted plasma'):
        bpy.data.objects.remove(o, do_unlink=True)


def mesh_object(name, vertices, faces, material, collection=col, parent=root):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    bm = bmesh.new(); bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh); bm.free(); mesh.update()
    mesh.materials.append(material)
    uv = mesh.uv_layers.new(name='UVMap')
    for f in mesh.polygons:
        axes = [i for i in range(3) if i != max(range(3), key=lambda i: abs(f.normal[i]))]
        for j in f.loop_indices:
            v = mesh.vertices[mesh.loops[j].vertex_index].co
            uv.data[j].uv = (v[axes[0]]/2.5, v[axes[1]]/2.5)
    o = bpy.data.objects.new(name, mesh); collection.objects.link(o); o.parent = parent
    return o


def prism(name, outline, bottom, top, material, collection=col, parent=root):
    n = len(outline)
    vertices = [(x, y, z) for z in (bottom, top) for x, y in outline]
    faces = [tuple(reversed(range(n))), tuple(range(n, 2*n))]
    faces += [(i, (i+1)%n, (i+1)%n+n, i+n) for i in range(n)]
    return mesh_object(name, vertices, faces, material, collection, parent)


def box(name, center, size, mat, matrix=Matrix.Identity(4)):
    x, y, z = size
    o = prism(name, [(-x/2,-y/2), (x/2,-y/2), (x/2,y/2), (-x/2,y/2)], -z/2,z/2,mat)
    o.data.transform(matrix @ Matrix.Translation(Vector(center)))
    return o


def annulus(name, inner, outer, bottom, top, mat, collection=col, parent=root,
            start=0, end=math.tau, segments=128):
    vertices = []
    for i in range(segments+1):
        a = start+(end-start)*i/segments
        vertices += [(r*math.cos(a),r*math.sin(a),z)
                     for r,z in [(inner,bottom),(outer,bottom),(outer,top),(inner,top)]]
    faces = [(4*i+j,4*(i+1)+j,4*(i+1)+(j+1)%4,4*i+(j+1)%4)
             for i in range(segments) for j in range(4)]
    if end-start >= math.tau-1e-6:
        # Weld the closing seam into a closed manifold ring.
        vertices = vertices[:-4]
        faces = [tuple(v % len(vertices) for v in f) for f in faces]
    else:
        faces += [(3,2,1,0), tuple(4*segments+j for j in range(4))]
    return mesh_object(name, vertices, faces, mat, collection, parent)


def subpart_scene(name):
    scene = bpy.data.scenes.get(name)
    if scene is None:
        scene = bpy.data.scenes.new(name)
        bpy.context.window.scene = scene
        bpy.ops.scene.recreate_collections()
    c = COLS.get_collections(scene)['main'][0]
    for o in list(c.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    scene.seut.sceneType = 'subpart'
    scene.seut.subtypeId = name
    scene.seut.mod_path = str(ROOT/'src')
    scene.seut.export_sbc_type = 'none'
    scene.seut.export_deleteLooseFiles = False
    r = bpy.data.objects.new(name+' root', None); c.objects.link(r)
    return scene, c, r


def instance(name, scene, rest, assembled):
    d = bpy.data.objects.new('subpart_'+name, None); col.objects.link(d)
    d.parent = root; d.matrix_basis = rest; d['file'] = scene.name
    for mesh in COLS.get_collections(scene)['main'][0].objects:
        if mesh.type != 'MESH': continue
        o = bpy.data.objects.new('Inspection / '+name+' / '+mesh.name, mesh.data)
        inspection.objects.link(o); o.matrix_world = assembled @ mesh.matrix_world
    return d


# Four corner feeders: local +Z is the inward/downward 45-degree launch normal.
feeders = []
for i in range(4):
    a = -math.pi/4+i*math.pi/2
    outward = Vector((math.cos(a), math.sin(a), 0))
    normal = (-outward+Vector((0,0,-1))).normalized()
    tangent = Vector((-math.sin(a),math.cos(a),0))
    up = normal.cross(tangent)
    mount = Matrix((tangent,up,normal)).transposed().to_4x4()
    mount.translation = outward*4.48+Vector((0,0,2.42))
    box('AP dispenser / corner cradle %s'%i,(0,0,-.15),(1.02,.90,.42),native['PaintedMetal_Colorable'],mount)
    box('AP dispenser / dark throat %s'%i,(0,0,.085),(.80,.66,.08),native['PaintedMetal_VeryDark'],mount)
    for x in (-.43,.43):
        box('AP dispenser / guide rail %s'%i,(x,0,.14),(.09,.76,.12),native['Metal_Dull'],mount)
    for y in (-.32,.32):
        box('AP dispenser / fuel strip %s'%i,(0,y,.15),(.64,.045,.035),native['Emissive'],mount)
    for x in (-.30,-.10,.10,.30):
        box('AP dispenser / cooling fin %s'%i,(x,.30,-.22),(.045,.45,.34),native['Metal_Dull'],mount)
    nozzle = mount @ Vector((0,0,.24))
    feeders.append({'position':list(nozzle), 'normal':list(normal), 'matrix':mount})

# A solid centre island stays in place. Only the annular ring bay opens:
# four curved leaves drop, then retract outward beneath the surrounding deck.
# End inside the existing 64-sided deployment lip's inner face, leaving a
# narrow seam instead of overlapping its coplanar top surface.
annulus('AP floor / fixed deck',1.83,3.539,-1.35,-1.25,native['PaintedMetal_Darker'])
annulus('AP floor / bay bezel',1.82,1.88,-1.30,-1.225,native['Metal_Dull'])
annulus('AP floor / fuel trace',1.88,1.92,-1.257,-1.24,native['Emissive'])
disk=[(.975*math.cos(i*math.tau/128),.975*math.sin(i*math.tau/128)) for i in range(128)]
prism('AP floor / solid central island',disk,-2.45,-1.225,native['PaintedMetal_Darker'])
disk=[(.92*math.cos(i*math.tau/64),.92*math.sin(i*math.tau/64)) for i in range(64)]
prism('AP floor / centre service plate',disk,-1.23,-1.215,native['PaintedMetal_Colorable'])
annulus('AP floor / island fuel trace',.91,.94,-1.216,-1.207,native['Emissive'])
# The earlier centre-opening trial needed a wall groove. Annular leaves have
# shorter travel and fit wholly inside the well, so restore that original wall.
if s.get('floor_pocket_cut'):
    original=next(o for o in col.objects if o.name.startswith('Ring well inner liner'))
    with bpy.data.libraries.load(str(checkpoint),link=False) as (source,target):
        target.objects=[original.name]
    recovered=target.objects[0]
    original.data=recovered.data
    bpy.data.objects.remove(recovered,do_unlink=True)
    s['floor_pocket_cut']=False

leaf_scene, leaf_col, leaf_root = subpart_scene('ArcanePower_FloorLeaf')
annulus('Floor leaf / annular pressure plate',.995,1.815,-.05,.05,native['PaintedMetal_Colorable'],leaf_col,leaf_root,.008,math.pi/2-.008,32)
annulus('Floor leaf / curved inset',1.51,1.56,.05,.056,native['Metal_Dull'],leaf_col,leaf_root,.07,math.pi/2-.07,32)
leaves=[]
for i in range(4):
    rest = Matrix.Translation((0,0,-1.30)) @ Matrix.Rotation(i*math.pi/2,4,'Z')
    instance('Floor%s'%(i+1),leaf_scene,rest,rest)
    a=math.pi/4+i*math.pi/2
    leaves.append({'name':'Floor%s'%(i+1),'slide':[1.0*math.cos(a),1.0*math.sin(a),0]})

rings=[]
for i,radius in enumerate(RADII):
    rs,rc,rr = subpart_scene('ArcanePower_Ring%s'%(i+1))
    annulus('Ring %s / machined hoop'%(i+1),radius-.045,radius+.045,-.045,.045,native['Metal_Dull'],rc,rr)
    for face in (-1,1):
        for j in range(16):
            annulus('Ring %s / fuel inlay'%(i+1),radius-.022,radius+.022,face*.048-.004,face*.048+.004,native['Emissive'],rc,rr,j*math.tau/16+.025,(j+1)*math.tau/16-.025,6)
    rest=Matrix.Translation((0,0,PARK_Z))
    # Static assembled inspection only: runtime rotation is generated in BSL.
    axis=Vector(((1,0,0),(0,1,0),(1,1,0),(1,-1,0))[i]).normalized()
    angle=(64,72,52,80)[i]
    assembled=Matrix.Translation(CENTER) @ Matrix.Rotation(math.radians(angle),4,axis)
    instance('Ring%s'%(i+1),rs,rest,assembled)
    inner=radius-.045; outer=math.hypot(radius+.045,.052)
    rings.append({'name':'Ring%s'%(i+1),'radius':radius,'inner':inner,'sweep_radius':outer,
                  'park_z':PARK_Z,'axis':list(axis),'tilt_degrees':angle,'speed':(.20,-.16,.13,-.11)[i]})

# Two congruent triangular tile shapes cover the 80 faces of a subdivided ico.
# Each is a closed 45-mm cartridge, with an inset luminous face and thick rim.
bm=bmesh.new();bmesh.ops.create_icosphere(bm,subdivisions=2,radius=.88)
faces=[[v.co.copy() for v in f.verts] for f in bm.faces];bm.free()
faces.sort(key=lambda vs:(round(sum(v.z for v in vs)/3,4),math.atan2(sum(v.y for v in vs),sum(v.x for v in vs))))
types={};tiles=[]
for i,vs in enumerate(faces):
    # Start with the longest edge, preserving outward winding; congruent shapes
    # then have identical local coordinates rather than skewing a generic tile.
    edge=max(range(3),key=lambda j:round((vs[(j+1)%3]-vs[j]).length,5))
    vs=vs[edge:]+vs[:edge]
    center=sum(vs,Vector())/3
    x=(vs[1]-vs[0]).normalized();z=(vs[1]-vs[0]).cross(vs[2]-vs[0]).normalized();y=z.cross(x)
    orientation=Matrix((x,y,z)).transposed()
    shape=[orientation.transposed()@(v-center)*.984 for v in vs]
    signature=tuple(round(v,4) for p in shape for v in p[:2])
    if signature not in types:
        ts,tc,tr=subpart_scene('ArcanePower_Tile%s'%(len(types)+1))
        xy=[tuple(p[:2]) for p in shape]
        prism('Tile / solid framed cartridge',xy,-.0225,.0225,native['PaintedMetal_VeryDark'],tc,tr)
        inset=[(p.x*.76,p.y*.76) for p in shape]
        prism('Tile / fuel luminous inset',inset,.0226,.027,native['Emissive'],tc,tr)
        types[signature]=ts
    ts=types[signature]
    head=i%4
    final=orientation.to_4x4();final.translation=center+CENTER
    # Launch flush to the 45-degree mouth, then rotate the physical cartridge
    # into its final face orientation while travelling above the horizontal rings.
    rest=feeders[head]['matrix'].copy();rest.translation=Vector(feeders[head]['position'])
    delta=(orientation @ rest.to_3x3().inverted()).to_quaternion()
    delta_axis,delta_angle=delta.to_axis_angle()
    instance('Tile%02d'%(i+1),ts,rest,final)
    staging=Vector((center.x*.25,center.y*.25,1.75))
    exit_point=rest.translation+Vector(feeders[head]['normal'])*.38
    tiles.append({'name':'Tile%02d'%(i+1),'model':ts.name,'batch':i//4,'dispenser':head,
                  'start':list(rest.translation),'exit':list(exit_point),'staging':list(staging),'final':list(final.translation),
                  'rotation_axis':list(delta_axis),'rotation_radians':delta_angle,
                  'rotation':[list(row) for row in orientation]})
assert len(types)==2,len(types)

ps,pc,pr=subpart_scene('ArcanePower_Plasma')
bm=bmesh.new();bmesh.ops.create_icosphere(bm,subdivisions=2,radius=.57)
mesh=bpy.data.meshes.new('Plasma seed');bm.to_mesh(mesh);bm.free()
plasma=mesh_object('Plasma / ignition core',[v.co[:] for v in mesh.vertices],[p.vertices[:] for p in mesh.polygons],native['Emissive'],pc,pr)
for polygon in plasma.data.polygons:
    for loop in polygon.loop_indices:
        direction=plasma.data.vertices[plasma.data.loops[loop].vertex_index].co.normalized()
        plasma.data.uv_layers.active.data[loop].uv=(.5+math.atan2(direction.y,direction.x)/math.tau,.5+math.asin(direction.z)/math.pi)
bpy.data.meshes.remove(mesh)
instance('Plasma',ps,Matrix.Translation(CENTER),Matrix.Translation(CENTER))

bpy.context.window.scene=s
s['containment_field']='80 solid 45-mm framed tiles, nominal R0.88 m; four pillar feeders at 45 degrees'
s['deployment']='Four nested rings R1.09/1.29/1.49/1.69 m; solid centre island R0.975; four annular floor leaves drop and retract 1m'
manifest={'center':list(CENTER),'field_radius':.88,'tile_thickness':.045,'rings':rings,'leaves':leaves,'tiles':tiles,
          'feeders':[{k:v for k,v in f.items() if k!='matrix'} for f in feeders],
          'palette':{'I':[40,185,255],'II':[255,145,40],'III':[180,85,255]},
          'subpart_scenes':[r['name'].replace('Ring','ArcanePower_Ring') for r in rings]+[leaf_scene.name]+[ts.name for ts in types.values()]+[ps.name]}
(ROOT/'assets/deployment.json').write_text(json.dumps(manifest,indent=2))
bpy.context.view_layer.update()
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
print('Authored',len(rings),'rings,',len(leaves),'floor leaves,',len(tiles),'thick tiles using',len(types),'tile meshes. No timeline animation.')
