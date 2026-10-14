"""Connect the exported storage family, native batteries and construction models."""
import hashlib
from pathlib import Path
import shutil
import xml.etree.ElementTree as E
from prepare_lab import MOD, save, set_text, XSI

BLOCKS = {
 'ArcanePower_EnergyCore': ('Arcane Energy Core',1000,1),
 'ArcanePower_EnergyCapacity': ('Arcane Capacity Module',10000,1),
 'ArcanePower_EnergyCapacityAdvanced': ('Arcane Advanced Capacity Module',100000,10),
 'ArcanePower_EnergyTransfer': ('Arcane Transfer Module',0,1),
 'ArcanePower_EnergyTransferAdvanced': ('Arcane Advanced Transfer Module',0,10),
 'ArcanePower_EnergyStabilizer': ('Arcane Stabilizer',0,1),
 'ArcanePower_EnergyStabilizerAdvanced': ('Arcane Advanced Stabilizer',0,10),
}


def main():
 folder=MOD/'Models/Cubes/large'
 files=[folder/'ArcanePower_EnergyRotor.mwm']
 for name in BLOCKS:
  files += [folder/(name+suffix+'.mwm') for suffix in ('','_BS1','_BS2','_BS3')]
 digest=hashlib.sha256(b''.join(p.name.encode()+p.read_bytes() for p in files)).hexdigest()[:12]
 revision=folder/('energy_'+digest);revision.mkdir(exist_ok=True)
 for p in files:shutil.copy2(p,revision/p.name)
 root=E.Element('Definitions');blocks=E.SubElement(root,'CubeBlocks')
 categories=E.Element('Definitions');category=E.SubElement(E.SubElement(categories,'CategoryClasses'),'Category',{'{'+XSI+'}type':'MyObjectBuilder_GuiBlockCategoryDefinition'})
 for path,value in {'Id/TypeId':'GuiBlockCategoryDefinition','Id/SubtypeId':'ArcaneSystems_Energy','DisplayName':'Arcane Systems','Name':'ArcaneSystems'}.items():set_text(category,path,value)
 items=E.SubElement(category,'ItemIds')
 for name,(label,capacity,multiplier) in BLOCKS.items():
  core=name=='ArcanePower_EnergyCore'
  kind='BatteryBlock' if capacity else 'UpgradeModule'
  definition=E.SubElement(blocks,'Definition',{'{'+XSI+'}type':'MyObjectBuilder_'+kind+'Definition'})
  description=('Compact 3x3x3 storage controller. Side sockets: capacity; rear: transfer; top: stabilizer. Modules must face the core. Base 1,000 MWh / 10 GW; capacities add 10,000 or 100,000 MWh. Transfer modules raise the bank ceiling to 100 GW / 1 TW. Standard/advanced stabilizers support matching or lower tier modules. Native Auto/Recharge/Discharge. Starts empty; 90% charge efficiency. Default 10% emergency reserve; Custom Data [ArcaneEnergyCore] ReservePercent=10, EmergencySupport=true. Recharge switches visibly to Auto for reactor startup/cooldown/venting and stays Auto.' if core else
   'Attach to a side-center Energy Core socket, with the connector/forward face toward the core. Requires a matching or stronger top stabilizer. Stores '+str(capacity)+' MWh in this block; removal retains its charge, destruction loses it, new/projected/copied blocks start empty. The core sets bank transfer limits and charge mode.' if capacity else
   'Attach to the rear-center Energy Core socket, with the connector/forward face toward the core. Raises bank charge/discharge ceiling to '+('1 TW' if multiplier==10 else '100 GW')+'. Requires matching or stronger top stabilizer; does not add capacity.' if 'Transfer' in name else
   'Attach to the top-center Energy Core socket, connector/forward face toward the core. Supports '+('both standard and advanced' if multiplier==10 else 'standard')+' capacity and transfer modules. Loss disables unsupported modules without deleting stored charge.')
  for path,value in {'Id/TypeId':kind,'Id/SubtypeId':name,'DisplayName':label,'Description':description,
   'Icon':'Textures/GUI/Icons/ArcanePower/'+name+'.dds','CubeSize':'Large','BlockTopology':'TriangleMesh',
   'Model':(revision/(name+'.mwm')).relative_to(MOD).as_posix(),'BlockPairName':name,'EdgeType':'Light',
   'BuildTimeSeconds':180 if core else 60*multiplier,'PCU':100 if core else 25,'IsAirTight':'false','Public':'true',
   'DamageEffectName':'Damage_Electrical_Damaged','DamagedSound':'ParticleElectrical',
   'DestroyEffect':'BlockDestroyedExplosion_Large','DestroySound':'PoofExplosionCat3','EmissiveColorPreset':'Default'}.items():set_text(definition,path,value)
  size=3 if core else 1
  E.SubElement(definition,'Size',x=str(size),y=str(size),z=str(size))
  E.SubElement(definition,'Center',x=str(size//2),y=str(size//2),z=str(size//2))
  E.SubElement(definition,'ModelOffset',x='0',y='0',z='0')
  components=E.SubElement(definition,'Components')
  amounts=[('SteelPlate',1000 if core else 100),('Construction',500 if core else 100),
           ('PowerCell',1200 if core else 1500 if capacity else 0),
           ('Superconductor',1000 if core else 1000 if capacity else 300),
           ('Computer',200 if core else 100),('Motor',80 if core else 20),('SteelPlate',200 if core else 50)]
  for component,amount in amounts:
   if amount:E.SubElement(components,'Component',Subtype=component,Count=str(amount*multiplier))
  E.SubElement(definition,'CriticalComponent',Subtype='Computer',Index='0')
  stages=E.SubElement(definition,'BuildProgressModels')
  for n,ratio in enumerate(('0.33','0.67','1.00'),1):E.SubElement(stages,'Model',BuildPercentUpperBound=ratio,File=(revision/(name+'_BS'+str(n)+'.mwm')).relative_to(MOD).as_posix())
  mounts=E.SubElement(definition,'MountPoints')
  for side in ('Front','Back','Left','Right','Top','Bottom'):
   E.SubElement(mounts,'MountPoint',Side=side,StartX='0',StartY='0',EndX=str(size),EndY=str(size))
  if capacity:
   for path,value in {'ResourceSourceGroup':'Battery','MaxPowerOutput':1000000,'ResourceSinkGroup':'BatteryBlock',
    'RequiredPowerInput':1000000,'AdaptibleInput':'true','MaxStoredPower':capacity,'InitialStoredPowerRatio':0,'RechargeMultiplier':.9}.items():set_text(definition,path,value)
  else:E.SubElement(definition,'Upgrades')
  E.SubElement(items,'string').text=kind+'/'+name
 save(root,MOD/'Data/CubeBlocks/ArcanePower_EnergyCore.sbc')
 save(categories,MOD/'Data/EnergyCoreCategories.sbc')
 print('Connected seven energy blocks, 21 construction models and rotor:',revision.relative_to(MOD))

if __name__=='__main__':main()
