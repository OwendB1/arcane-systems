"""Focused storage acceptance using the shipped policy methods and native models."""
import os,re,subprocess,tempfile,xml.etree.ElementTree as ET
from pathlib import Path
from prepare_lab import ROOT,MOD,GAME
from prepare_energy_core import BLOCKS

def method(source,name):
 start=re.search(r'^        (?:private|internal) [^{\n]*?\b'+name+r'\(',source,re.M).start()
 opening=source.index('{',start);depth=1;end=opening+1
 while depth:
  depth+=(source[end]=='{')-(source[end]=='}');end+=1
 return source[start:end]+'\n'

source=(MOD/'Data/Scripts/ArcanePower/EnergyCore.cs').read_text()
methods=''.join(method(source,n) for n in ('IsPillar','BaseSubtype','Healthy','Socket','Tier','FindController','UpdateBank','Disconnect','ApplyLimits','ClampNativeOutput'))
harness=(ROOT/'tools/EnergyCoreProbe.cs').read_text().replace('// METHODS',methods)
game=GAME/'Bin64'
with tempfile.TemporaryDirectory(prefix='arcane-energy-check-') as directory:
 cs=Path(directory)/'Check.cs';cs.write_text(harness);exe=cs.with_suffix('.exe')
 subprocess.run(['mcs','-out:'+str(exe),'-r:/usr/lib/mono/4.5/Facades/netstandard.dll',
                 '-r:'+str(game/'VRage.Math.dll'),'-r:'+str(game/'VRage.Library.dll'),str(cs)],check=True)
 subprocess.run(['mono',str(exe)],check=True,env={**os.environ,'MONO_PATH':str(game)})
path=MOD/'Data/CubeBlocks/ArcanePower_EnergyCore.sbc'
if path.exists():
 definitions=ET.parse(path).findall('CubeBlocks/Definition')
 assert len(definitions)==7
 for block in definitions:
  subtype=block.findtext('Id/SubtypeId');assert subtype.endswith('_Pillar')
  name=subtype.removesuffix('_Pillar');assert name in BLOCKS
  assert block.find('Size').attrib==dict(x='3' if name=='ArcanePower_EnergyCore' else '1',y='3',z='3' if name=='ArcanePower_EnergyCore' else '1')
  assert (MOD/block.findtext('Model')).exists()
  assert (MOD/block.findtext('Icon')).exists()
  assert len(block.findall('BuildProgressModels/Model'))==3
  for stage in block.findall('BuildProgressModels/Model'):assert (MOD/stage.get('File')).exists()
  if BLOCKS[name][1]:
   assert float(block.findtext('MaxStoredPower'))==BLOCKS[name][1]
   assert float(block.findtext('InitialStoredPowerRatio'))==0
   assert float(block.findtext('RechargeMultiplier'))==.9
  else:
   upgrade=block.find('Upgrades/MyUpgradeModuleInfo')
   key='ArcaneEnergyTransfer' if 'Transfer' in name else 'ArcaneEnergyStabilizer'
   assert upgrade.findtext('UpgradeType')==key
   assert float(upgrade.findtext('Modifier'))==BLOCKS[name][2]
   assert upgrade.findtext('ModifierType')=='Additive'
   assert 'block.AddUpgradeValue("'+key+'", 0f)' in source
 print('PASS seven storage definitions, 21 stages, native fixed capacities, empty initial charge and 90% efficiency')
 legacy=ET.parse(MOD/'Data/CubeBlocks/ArcanePower_EnergyCoreLegacy.sbc').findall('CubeBlocks/Definition')
 assert {b.findtext('Id/SubtypeId') for b in legacy}==set(BLOCKS)
 for block in legacy:
  name=block.findtext('Id/SubtypeId');width='3' if name=='ArcanePower_EnergyCore' else '1'
  assert block.findtext('Public')=='false'
  assert block.find('Size').attrib==dict(x=width,y=width,z=width)
  assert block.findtext('Model')=='Models/Cubes/large/energy_109d27f880a0/'+name+'.mwm'
  for asset in [block.findtext('Model'),block.findtext('Icon')]+[s.get('File') for s in block.findall('BuildProgressModels/Model')]:
   assert (MOD/asset).is_file(),asset
  if BLOCKS[name][1]:
   assert float(block.findtext('MaxStoredPower'))==BLOCKS[name][1]
   assert '"'+name+'"' in source and '"'+name+'_Pillar"' in source
 print('PASS seven hidden compact definitions retain original dimensions, capacities, models and runtime bindings')
 with tempfile.TemporaryDirectory(prefix='arcane-energy-models-') as directory:
  probe=Path(directory)/'Models.exe'
  sockets=Path(directory)/'Sockets.exe'
  subprocess.run(['mcs','-out:'+str(sockets),'-r:/usr/lib/mono/4.5/Facades/netstandard.dll',
   *['-r:'+str(game/(n+'.dll')) for n in ('VRage.Render','VRage.Math','VRage.Library')],
   str(ROOT/'tools/EnergySocketProbe.cs')],check=True)
  subprocess.run(['mcs','-out:'+str(probe),'-r:/usr/lib/mono/4.5/Facades/netstandard.dll',
   *['-r:'+str(game/(n+'.dll')) for n in ('VRage.Render','VRage.Math','VRage.Library')],
   str(ROOT/'tools/ConstructionModelProbe.cs')],check=True)
  for block in definitions:
   name=block.findtext('Id/SubtypeId').removesuffix('_Pillar')
   subprocess.run(['mono',str(sockets),str(MOD/block.findtext('Model'))],check=True,
    env={**os.environ,'MONO_PATH':str(game)})
   for stage in block.findall('BuildProgressModels/Model'):
    subprocess.run(['mono',str(probe),str(MOD/stage.get('File')),
     str(MOD/'Models/Cubes/large'/(name+'.hkt')),str(MOD/block.findtext('Model'))],
     check=True,env={**os.environ,'MONO_PATH':str(game)})
