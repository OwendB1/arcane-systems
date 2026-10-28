"""Connect the exported storage family, native batteries and construction models."""
import hashlib
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as E
from prepare_lab import MOD, save, set_text, XSI, model_source, write_block_menu

BLOCKS = {
 'ArcanePower_EnergyCore': ('Arcane Energy Core',1000,1),
 'ArcanePower_EnergyCapacity': ('Arcane Capacity Module',10000,1),
 'ArcanePower_EnergyCapacityAdvanced': ('Arcane Advanced Capacity Module',100000,10),
 'ArcanePower_EnergyTransfer': ('Arcane Transfer Module',0,1),
 'ArcanePower_EnergyTransferAdvanced': ('Arcane Advanced Transfer Module',0,10),
 'ArcanePower_EnergyStabilizer': ('Arcane Stabilizer',0,1),
 'ArcanePower_EnergyStabilizerAdvanced': ('Arcane Advanced Stabilizer',0,10),
}


def icon_path(name):
 """Avoid retaining a cached compact/older icon across in-game reloads."""
 source=MOD/'Textures/GUI/Icons/ArcanePower'/(name+'.dds')
 content=source.read_bytes()
 target=source.parent/'Energy'/(name+'_r'+hashlib.sha256(content).hexdigest()[:12]+'.dds')
 target.parent.mkdir(exist_ok=True)
 if not target.exists():target.write_bytes(content)
 assert target.read_bytes()==content, 'Immutable energy icon collision'
 return target.relative_to(MOD).as_posix()


def refresh_icons():
 path=MOD/'Data/CubeBlocks/ArcanePower_EnergyCore.sbc'
 tree=E.parse(path);blocks=tree.find('CubeBlocks')
 for block in blocks:
  name=block.findtext('Id/SubtypeId').removesuffix('_Pillar')
  if name in BLOCKS:block.find('Icon').text=icon_path(name)
 save(tree.getroot(),path)
 energy_block_menu(blocks)
 # Only this tool's immutable icon copies are disposable; stable DDS files
 # still serve the hidden legacy block definitions and remain build inputs.
 referenced={n.text for p in (MOD/'Data').rglob('*.sbc') for n in E.parse(p).iter('Icon')}
 for p in (MOD/'Textures/GUI/Icons/ArcanePower/Energy').glob('ArcanePower_Energy*_r*.dds'):
  if p.relative_to(MOD).as_posix() not in referenced:p.unlink()


def model_revision():
 folder=MOD/'Models/Cubes/large'
 # Reuse the exact reactor hoops, including their original UVs/materials.
 files=[model_source(name) for name in ('ArcanePower_EnergyRotor','ArcanePower_EnergyFan','ArcanePower_Ring3','ArcanePower_Ring4')]
 for name in BLOCKS:
  files += [model_source(name+suffix) for suffix in ('','_BS1','_BS2','_BS3')]
 digest=hashlib.sha256(b''.join(p.name.encode()+p.read_bytes() for p in files)).hexdigest()[:12]
 revision=folder/('energy_'+digest);revision.mkdir(exist_ok=True)
 for p in files:shutil.copy2(p,revision/p.name)
 return revision


def refresh_models():
 """Wire a new export without regenerating balance or other block settings."""
 revision=model_revision()
 path=MOD/'Data/CubeBlocks/ArcanePower_EnergyCore.sbc'
 tree=E.parse(path)
 for block in tree.findall('CubeBlocks/Definition'):
  name=block.findtext('Id/SubtypeId').removesuffix('_Pillar')
  if name not in BLOCKS:continue
  block.find('Model').text=(revision/(name+'.mwm')).relative_to(MOD).as_posix()
  for stage in block.findall('BuildProgressModels/Model'):
   stage.set('File',(revision/Path(stage.get('File')).name).relative_to(MOD).as_posix())
 save(tree.getroot(),path)
 return revision


def energy_block_menu(blocks):
 write_block_menu(blocks,'Energy',[
  ('BatteryUpgrades','Arcane Battery Upgrades','Scroll through capacity, transfer and stabilizer modules, including advanced versions.',
   [name+'_Pillar' for name in BLOCKS if name!='ArcanePower_EnergyCore'])],MOD)


def description(name):
 _,capacity,multiplier=BLOCKS[name]
 if name=='ArcanePower_EnergyCore':
  return (
   '3x3x3 Energy Core storage controller.\n\n'
   'INSTALLATION\nFour upright 1x3x1 bays accept capacity, transfer or stabilizer modules.\n'
   'Align module Up with core Up and face its connectors toward the core.\n\n'
   'STORAGE AND TRANSFER\nBase: 1,000 MWh capacity / 4 GW charging / 10 GW discharge.\n'
   'Capacity modules add 10,000 or 100,000 MWh.\n'
   'Standard transfer: 40 GW charging / 100 GW discharge.\n'
   'Advanced transfer: 200 GW charging / 1 TW discharge.\n'
   'Standard/advanced stabilizers support matching or lower tier modules.\n'
   'Duplicate stabilizer/transfer modules use the strongest tier without stacking.\n\n'
   'CHARGING\nNative Auto / Recharge / Discharge modes.\n'
   'Starts empty; 90% charge efficiency.\n'
   'Emergency reactor support switches Recharge to Auto and leaves it in Auto.\n\n'
   'RESERVE\nDefault: 10% emergency reserve. Configure in Custom Data:\n'
   '[ArcaneEnergyCore]\nReservePercent=10\nEmergencySupport=true\n\n'
   'TERMINAL / TOOLBAR\nSurge: charges affordable jump drives in 5 seconds at 90% efficiency.\n'
   'Bank discharge increases with the selected batch.\n'
   'Each additional drive adds 25% of the base recovery time.\n'
   'Burst: double discharge for 10 seconds.\n'
   'Both abilities share recovery and protect the reserve.\n\n'
   'UPKEEP\nStored-charge loss rises with fill; stabilizers reduce loss.\n'
   'Passive loss continues while disabled or detached.')
 installation=(
  'Full 1x3x1 large-grid pillar.\n\n'
  'INSTALLATION\nAttach to any of the four Energy Core bays.\n'
  'Align Up with core Up and face the connectors toward the core.')
 if capacity:
  return installation+(
   '\nRequires a matching or stronger attached stabilizer.\n\n'
   f'STORAGE\nStores {capacity:,} MWh in this block.\n'
   'Removal retains its charge; destruction loses it.\n'
   'New, projected and copied blocks start empty.\n'
   'The core sets bank transfer limits and charge mode.')
 if 'Transfer' in name:
  return installation+(
   '\n\nTRANSFER\nRaises bank charging / discharge ceilings to '+('200 GW / 1 TW' if multiplier==10 else '40 GW / 100 GW')+'.\n'
   'Effective tier is limited by the strongest attached stabilizer.\n'
   'Does not add capacity. Duplicate transfer modules do not stack.')
 return installation+(
  '\n\nSUPPORT\nSupports '+('both standard and advanced' if multiplier==10 else 'standard')+' capacity and transfer modules.\n'
  'The strongest attached stabilizer tier applies; duplicates do not stack.\n'
  'Loss disables unsupported modules without deleting stored charge.')


def main():
 revision=model_revision()
 root=E.Element('Definitions');blocks=E.SubElement(root,'CubeBlocks')
 for name,(label,capacity,multiplier) in BLOCKS.items():
  core=name=='ArcanePower_EnergyCore'
  kind='BatteryBlock' if capacity else 'UpgradeModule'
  definition=E.SubElement(blocks,'Definition',{'{'+XSI+'}type':'MyObjectBuilder_'+kind+'Definition'})
  for path,value in {'Id/TypeId':kind,'Id/SubtypeId':name+'_Pillar','DisplayName':label,'Description':description(name),
   'Icon':icon_path(name),'CubeSize':'Large','BlockTopology':'TriangleMesh',
   'Model':(revision/(name+'.mwm')).relative_to(MOD).as_posix(),'BlockPairName':name+'_Pillar','EdgeType':'Light',
   'BuildTimeSeconds':180 if core else 60*multiplier,'PCU':100 if core else 25,'IsAirTight':'false','Public':'true',
   'DamageEffectName':'Damage_Electrical_Damaged','DamagedSound':'ParticleElectrical',
   'DestroyEffect':'BlockDestroyedExplosion_Large','DestroySound':'PoofExplosionCat3','EmissiveColorPreset':'Default'}.items():set_text(definition,path,value)
  width=3 if core else 1
  E.SubElement(definition,'Size',x=str(width),y='3',z=str(width))
  E.SubElement(definition,'Center',x=str(width//2),y='1',z=str(width//2))
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
   E.SubElement(mounts,'MountPoint',Side=side,StartX='0',StartY='0',EndX=str(width),EndY=str(width if side in ('Top','Bottom') else 3))
  if capacity:
   for path,value in {'ResourceSourceGroup':'Battery','MaxPowerOutput':2000000,'ResourceSinkGroup':'BatteryBlock',
    'RequiredPowerInput':200000,'AdaptibleInput':'true','MaxStoredPower':capacity,'InitialStoredPowerRatio':0,'RechargeMultiplier':.9}.items():set_text(definition,path,value)
  else:
   upgrades=E.SubElement(definition,'Upgrades')
   upgrade=E.SubElement(upgrades,'MyUpgradeModuleInfo')
   set_text(upgrade,'UpgradeType','ArcaneEnergyTransfer' if 'Transfer' in name else 'ArcaneEnergyStabilizer')
   set_text(upgrade,'Modifier',multiplier)
   set_text(upgrade,'ModifierType','Additive')
 save(root,MOD/'Data/CubeBlocks/ArcanePower_EnergyCore.sbc')
 energy_block_menu(blocks)
 print('Connected seven energy blocks, 21 construction models and rotor:',revision.relative_to(MOD))

if __name__=='__main__':
 if '--icons-only' in sys.argv:refresh_icons()
 elif '--models-only' in sys.argv:print('Connected new model family:',refresh_models().relative_to(MOD))
 else:main()
