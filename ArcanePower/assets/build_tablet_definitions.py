"""Author native inert hand-tool, inventory item and assembler recipe definitions."""
from pathlib import Path
import xml.etree.ElementTree as E
import math
ROOT=Path(__file__).resolve().parents[1]
root=E.Element('Definitions',{'xmlns:xsi':'http://www.w3.org/2001/XMLSchema-instance','xmlns:xsd':'http://www.w3.org/2001/XMLSchema'})
def add(parent,tag,text=None,**attrs):
    e=E.SubElement(parent,tag,attrs)
    if text is not None:e.text=str(text)
    return e
def vector(parent,tag,values):
    e=add(parent,tag)
    for axis,value in zip('XYZW',values):add(e,axis,value)
physical=add(add(root,'PhysicalItems'),'PhysicalItem',**{'xsi:type':'MyObjectBuilder_ToolItemDefinition'})
add(physical,'Id',Type='MyObjectBuilder_PhysicalGunObject',Subtype='ArcanePower_Tablet')
for k,v in [('DisplayName','Arcane Reactor Tablet'),('Icon',r'Textures\GUI\Icons\ArcanePower\Tablet.dds'),('Description','Read-only reactor telemetry. Requires suit antenna enabled and an accessible bidirectional grid antenna link. Equip: left click selects a reachable reactor; right click changes page. Text HUD API enables the full live dashboard.')]:add(physical,k,v)
vector(physical,'Size',[.36,.26,.062])
for k,v in [('Mass',1.4),('Volume',3),('Model',r'Models\Items\ArcanePower_Tablet.mwm'),('PhysicalMaterial','Metal'),('HitDistance',0),('ShowAmmoCount','false'),('DepositAllEnabled','false')]:add(physical,k,v)
add(physical,'PrimaryActions');add(physical,'SecondaryActions')
hand=add(add(root,'HandItems'),'HandItem',**{'xsi:type':'MyObjectBuilder_HandItemDefinition'})
add(hand,'Id',Type='MyObjectBuilder_HandToolBase',Subtype='ArcanePower_Tablet')
add(hand,'PhysicalItemId',Type='MyObjectBuilder_PhysicalGunObject',Subtype='ArcanePower_Tablet')
# Item poses are head-relative; grip targets are item-relative. SE composes
# hand * item world matrices, so counter-rotate grips when turning the device.
def quaternion_product(a,b):
    x,y,z,w=a; X,Y,Z,W=b
    q=(w*X+x*W+y*Z-z*Y, w*Y-x*Z+y*W+z*X,
       w*Z+x*Y-y*X+z*W, w*W-x*X-y*Y-z*Z)
    length=math.sqrt(sum(v*v for v in q))
    return [round(v/length,9) for v in q]
turn_back=(0,-1,0,0)  # inverse of the item's 180-degree Y turn
right=(-.365488,-.486906,-.550798,.570931)
# Work in final tablet-local coordinates: mirror the entire right grip
# across the centre plane X=0. Position mirrors X; orientation is S*R*S,
# i.e. quaternion (x,-y,-z,w). No accumulated left-only corrective turns.
right_grip=quaternion_product(turn_back,right)
left_grip=(right_grip[0],-right_grip[1],-right_grip[2],right_grip[3])
vector(hand,'LeftHandOrientation',left_grip)
vector(hand,'RightHandOrientation',right_grip)
right_position=(-.162,-.015,0)
vector(hand,'LeftHandPosition',[-right_position[0],right_position[1],right_position[2]])
vector(hand,'RightHandPosition',right_position)
for tag in ['ItemOrientation','ItemWalkingOrientation','ItemShootOrientation','ItemIronsightOrientation','ItemOrientation3rd','ItemWalkingOrientation3rd','ItemShootOrientation3rd','ItemIronsightOrientation3rd']:vector(hand,tag,[0,1,0,0])
# +Z moves the tablet back toward the holder: 30 cm instead of 36 cm forward.
for tag in ['ItemPosition','ItemWalkingPosition','ItemShootPosition','ItemIronsightPosition','ItemPosition3rd','ItemWalkingPosition3rd','ItemShootPosition3rd','ItemIronsightPosition3rd']:vector(hand,tag,[0,-.20,-.30])
for tag in ['ItemPositioning','ItemPositioningWalk','ItemPositioningShoot','ItemPositioningIronsight','ItemPositioning3rd','ItemPositioningWalk3rd','ItemPositioningShoot3rd','ItemPositioningIronsight3rd']:add(hand,tag,'TransformFromData')
for k,v in [('BlendTime',.15),('ShootBlend',.15),('XAmplitudeScale',.1),('YAmplitudeScale',.1),('ZAmplitudeScale',0),('RunMultiplier',1),('AmplitudeMultiplier3rd',1),('SimulateLeftHand','true'),('SimulateRightHand','true'),('FingersAnimation','HoldingTool')]:add(hand,k,v)
blueprint=add(add(root,'Blueprints'),'Blueprint');add(blueprint,'Id',Type='MyObjectBuilder_BlueprintDefinition',Subtype='ArcanePower_Tablet')
add(blueprint,'DisplayName','Arcane Reactor Tablet');add(blueprint,'Icon',r'Textures\GUI\Icons\ArcanePower\Tablet.dds')
pre=add(blueprint,'Prerequisites')
for sub,num in [('Iron',3),('Silicon',1),('Nickel',.5)]:add(pre,'Item',Amount=str(num),TypeId='Ingot',SubtypeId=sub)
add(blueprint,'Result',Amount='1',TypeId='PhysicalGunObject',SubtypeId='ArcanePower_Tablet');add(blueprint,'BaseProductionTimeInSeconds',12)
classes=add(root,'BlueprintClassEntries')
for cls in ['BasicTools','Tools','EliteTools']:add(classes,'Entry',Class=cls,BlueprintSubtypeId='ArcanePower_Tablet')
E.indent(root);E.ElementTree(root).write(ROOT/'src/Data/Tablet.sbc',encoding='utf-8',xml_declaration=True)
