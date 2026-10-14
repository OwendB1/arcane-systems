"""Create a separate, disposable survival validation world; never edit the user's lab."""
import uuid
from pathlib import Path
import xml.etree.ElementTree as E
from prepare_lab import GAME,USER,ROOT,save,set_text,XSI
WORLD=USER/'Saves/76561198074076521/Arcane Energy - Validation'
KEY='f6e09e9a-76ef-4d21-9ef1-31e5cd759881'

def main():
 if WORLD.exists():raise RuntimeError('Preserving existing validation world: '+str(WORLD))
 template=GAME/'Content/CustomWorlds/Empty World'
 checkpoint=E.parse(template/'Sandbox.sbc').getroot()
 for path,value in {'SessionName':'Arcane Energy - Validation','WorldId':str(uuid.uuid4()),'Description':'Disposable native construction and energy bank validation. Original lab untouched.',
  'Settings/GameMode':'Survival','Settings/OnlineMode':'OFFLINE','Settings/EnableCopyPaste':'true','Settings/EnableSpectator':'true','Settings/EnableResearch':'false','Settings/EnableEconomy':'false',
  'Settings/EnableEncounters':'false','Settings/CargoShipsEnabled':'false','Settings/EnableDrones':'false','Settings/AutoSaveInMinutes':0}.items():set_text(checkpoint,path,value)
 mods=checkpoint.find('Mods')
 if mods is None:mods=E.SubElement(checkpoint,'Mods')
 mods.clear()
 for name in ('ArcanePower-Prototype','ArcaneEnergy-ValidationHarness'):
  m=E.SubElement(mods,'ModItem',FriendlyName=name)
  for path,value in {'Name':name,'PublishedFileId':0,'PublishedServiceName':'Steam'}.items():set_text(m,path,value)
 sector=E.parse(template/'SANDBOX_0_0_0_.sbs').getroot();objects=sector.find('SectorObjects')
 # Preserve the template character/checkpoint bindings, but put the rig nearby.
 grid=E.SubElement(objects,'MyObjectBuilder_EntityBase',{'{'+XSI+'}type':'MyObjectBuilder_CubeGrid'})
 for path,value in {'EntityId':880000000000100,'PersistentFlags':'CastShadows InScene','GridSizeEnum':'Large','IsStatic':'true','DisplayName':'Arcane Energy validation rig','DestructibleBlocks':'true'}.items():set_text(grid,path,value)
 pose=E.SubElement(grid,'PositionAndOrientation');E.SubElement(pose,'Position',x='0',y='0',z='25');E.SubElement(pose,'Forward',x='0',y='0',z='-1');E.SubElement(pose,'Up',x='0',y='1',z='0')
 blocks=E.SubElement(grid,'CubeBlocks');next_id=880000000001000
 def block(kind,name,pos,forward='Forward',up='Up',build=1,stored=None,identity=True):
  nonlocal next_id
  next_id+=1;b=E.SubElement(blocks,'MyObjectBuilder_CubeBlock',{'{'+XSI+'}type':'MyObjectBuilder_'+kind})
  for path,value in {'SubtypeName':name,'EntityId':next_id,'BuildPercent':build,'IntegrityPercent':build,'Owner':0,'ShareMode':'All','Enabled':'true','CustomName':name+' '+str(next_id)}.items():set_text(b,path,value)
  E.SubElement(b,'Min',x=str(pos[0]),y=str(pos[1]),z=str(pos[2]));E.SubElement(b,'BlockOrientation',Forward=forward,Up=up)
  E.SubElement(b,'ColorMaskHSV',x='0.58',y='-0.2',z='0.05')
  if stored is not None:
   set_text(b,'CurrentStoredPower',stored);set_text(b,'ChargeMode',0)
   if name.startswith('Arcane'):
    container=E.SubElement(b,'ComponentContainer');entries=E.SubElement(container,'Components');entry=E.SubElement(entries,'ComponentData');set_text(entry,'TypeId','MyModStorageComponent')
    component=E.SubElement(entry,'Component',{'{'+XSI+'}type':'MyObjectBuilder_ModStorageComponent'});storage=E.SubElement(component,'Storage');dictionary=E.SubElement(storage,'dictionary');item=E.SubElement(dictionary,'item')
    set_text(item,'Key',KEY);set_text(item,'Value',next_id if identity else next_id-10000)
  return b
 for x in range(-5,19):
  for z in range(-4,5):block('CubeBlock','LargeBlockArmorBlock',(x,0,z))
 block('BatteryBlock','ArcanePower_EnergyCore',(-1,1,-1),stored=500)
 block('BatteryBlock','ArcanePower_EnergyCapacity',(-2,2,0),'Right',stored=5000)
 block('BatteryBlock','ArcanePower_EnergyCapacityAdvanced',(2,2,0),'Left',stored=50000)
 block('UpgradeModule','ArcanePower_EnergyTransferAdvanced',(0,2,2))
 block('UpgradeModule','ArcanePower_EnergyStabilizerAdvanced',(0,4,0),'Down','Forward')
 # Independent copied core must discard the serialized charge on its new ID.
 block('BatteryBlock','ArcanePower_EnergyCore',(7,1,-1),stored=500,identity=False)
 # A native battery in Recharge provides a steady demand without custom power code.
 load=block('BatteryBlock','LargeBlockBatteryBlock',(4,1,0),stored=0);set_text(load,'ChargeMode',1)
 # Construction-stage fixtures for every new block, separate from the powered rig.
 from prepare_energy_core import BLOCKS
 for row,name in enumerate(BLOCKS):
  kind='BatteryBlock' if BLOCKS[name][1] else 'UpgradeModule'
  for col,ratio in enumerate((.1,.35,.65,1)):
   block(kind,name,(-3+col*5,1,10+row*5),build=ratio,stored=0 if kind=='BatteryBlock' else None)
 WORLD.mkdir(parents=True)
 save(checkpoint,WORLD/'Sandbox.sbc');save(sector,WORLD/'SANDBOX_0_0_0_.sbs')
 probe=USER/'Mods/ArcaneEnergy-ValidationHarness/Data/Scripts/Validation/Probe.cs'
 probe.parent.mkdir(parents=True,exist_ok=True)
 probe.write_text((ROOT/'tools/fixtures/EnergyRuntimeProbe.cs').read_text())
 print(WORLD)
if __name__=='__main__':main()
