"""Exercise the production stack linker and SE's native airtightness gate."""
import os
import json
from pathlib import Path
import runpy
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from prepare_lab import ROOT, MOD, GAME


def main():
    contract = runpy.run_path(str(ROOT/'assets/thermal_model_contract.py'))
    blocks = {b.findtext('Id/SubtypeId'): b for b in
              ET.parse(MOD/'Data/CubeBlocks/ArcanePower_Thermal.sbc').findall('CubeBlocks/Definition')}
    for name in contract['RUNTIME']:
        base = contract['COOLER_UPGRADES'].get(name, name)
        sealed = (' / ' in name and name not in contract['BARE_PIPES']) or base in ('Space radiator', 'Atmospheric cooler', 'Hull radiator') or name in contract['PIPE_ROTORS']
        block = blocks[contract['subtype'](name)]
        assert block.findtext('IsAirTight') == str(sealed).lower(), (name, 'Wrong airtightness')
        if base == 'Space radiator':
            assert list(map(int, (block.find('Size').get(k) for k in 'xyz'))) == [1, 1, 1]
    vents = MOD/'Data/CubeBlocks/ArcanePower_Vents.sbc'
    for block in ET.parse(vents).findall('CubeBlocks/Definition'):
        assert block.findtext('IsAirTight') == str(block.findtext('Id/SubtypeId') == 'ArcanePower_VentOutlet').lower()
    source = (MOD/'Data/Scripts/ArcanePower/ThermalSession.Radiators.cs').read_text()
    start = source.index('private static void LinkRadiators()')
    end = source.index('{', start)+1
    depth = 1
    while depth:
        depth += (source[end] == '{')-(source[end] == '}')
        end += 1
    fixture = r'''
using System;
using System.Collections.Generic;
using System.Reflection;
using System.Xml.Linq;
using ArcanePower;
using Sandbox.Definitions;
using Sandbox.Game.GameSystems;
using VRageMath;

namespace InstallationCheck {
class Grid {
 public Dictionary<Vector3I,Body> Cells=new Dictionary<Vector3I,Body>();
 public Vector3I WorldToGridInteger(Vector3D point){return Vector3I.Round(point/2.5);}
 public Slim GetCubeBlock(Vector3I cell){Body body;return Cells.TryGetValue(cell,out body)?new Slim{FatBlock=body}:null;}
}
class Slim {public Body FatBlock;}
class Body {
 public long EntityId,OwnerId=1;public bool Access=true;public MatrixD WorldMatrix;public Grid CubeGrid;
 public bool HasPlayerAccess(long owner){return Access && owner==OwnerId;}
}
class ThermalBlock {
 public Body Block;public ThermalModel Spec;public bool HardwareReady=true,CircuitReady=true;public ThermalBlock RadiatorBase;
 public ThermalStore Store=new ThermalStore{Radiator=new ThermalRadiatorState()};
 public List<ThermalBlock> RadiatorPanels=new List<ThermalBlock>();public int Invalidations;
 public void InvalidateRadiatorCooling(){Invalidations++;}
}
class Check {
 static Dictionary<long,ThermalBlock> Blocks=new Dictionary<long,ThermalBlock>();
 static int checks;
 static void Need(bool ok,string message){checks++;if(!ok)throw new Exception(message);}
 // LINKER
 static ThermalBlock Place(Grid grid,long id,ThermalKind kind,Vector3D centre,double yaw=0){
  var body=new Body{EntityId=id,CubeGrid=grid,WorldMatrix=MatrixD.CreateRotationY(yaw)};body.WorldMatrix.Translation=centre;
  var block=new ThermalBlock{Block=body,Spec=new ThermalModel{Kind=kind}};
  Blocks.Add(id,block);grid.Cells[grid.WorldToGridInteger(centre)]=body;return block;
 }
 static void Main(string[] args){
  var native=typeof(MyGridGasSystem).GetMethod("IsAirtightFromDefinition",BindingFlags.Static|BindingFlags.NonPublic);
  foreach(var file in args)foreach(var block in XDocument.Load(file).Root.Element("CubeBlocks").Elements("Definition")){
   bool sealedBlock=bool.Parse(block.Element("IsAirTight").Value);
   var definition=new MyCubeBlockDefinition{IsAirTight=sealedBlock,BuildProgressModels=new[]{
    new MyCubeBlockDefinition.BuildProgressModel{BuildRatioUpperBound=.8f}}};
   foreach(float progress in new[]{0f,.79f,.8f,1f})
    Need((bool)native.Invoke(null,new object[]{definition,progress})==(sealedBlock && progress>=.8f),"native weld/airtight gate");
  }
  var grid=new Grid();var root=Place(grid,1,ThermalKind.Radiator,Vector3D.Zero);
  var panels=new List<ThermalBlock>();
  for(int i=0;i<4;i++)panels.Add(Place(grid,2+i,ThermalKind.RadiatorPanel,ThermalRadiators.ExtensionCentre(root.Block.WorldMatrix,i),i*Math.PI/2));
  LinkRadiators();Need(root.RadiatorPanels.Count==3,"three panels attach");
  Need(panels[2].RadiatorBase==root && panels[3].RadiatorBase==null,"fourth panel stays unattached");
  int revisions=root.Invalidations;LinkRadiators();Need(root.Invalidations==revisions,"unchanged stack preserves cache");
  var third=panels[2];Blocks.Remove(third.Block.EntityId);
  panels[2]=Place(grid,20,ThermalKind.RadiatorPanel,third.Block.WorldMatrix.Translation);
  LinkRadiators();Need(root.Invalidations==revisions+1 && root.RadiatorPanels[2]==panels[2],"third-panel replacement invalidates cooling");
  panels[1].HardwareReady=false;LinkRadiators();Need(root.RadiatorPanels.Count==3,"failed middle panel preserves the circuit");
  panels[1].CircuitReady=false;LinkRadiators();Need(root.RadiatorPanels.Count==1 && panels[2].RadiatorBase==null,"removed middle panel breaks the chain");
  panels[1].CircuitReady=true;
  panels[1].HardwareReady=true;panels[1].Block.Access=false;LinkRadiators();Need(root.RadiatorPanels.Count==1,"ownership is enforced");
  panels[1].Block.Access=true;LinkRadiators();Need(root.RadiatorPanels.Count==3,"repaired middle restores stack");
  grid.Cells.Remove(grid.WorldToGridInteger(panels[0].Block.WorldMatrix.Translation));LinkRadiators();
  Need(root.RadiatorPanels.Count==0 && panels[1].RadiatorBase==null && panels[2].RadiatorBase==null,"missing first panel detaches every panel");
  grid.Cells[grid.WorldToGridInteger(panels[0].Block.WorldMatrix.Translation)]=panels[0].Block;
  root.HardwareReady=false;LinkRadiators();Need(root.RadiatorPanels.Count==3,"failed base preserves the circuit");
  root.CircuitReady=false;LinkRadiators();Need(root.RadiatorPanels.Count==0,"removed base detaches the stack");
  Console.WriteLine("PASS: "+checks+" native airtightness, construction and production stack-link checks");
 }
}
}
'''.replace('// LINKER', source[start:end])
    with tempfile.TemporaryDirectory(prefix='arcane-installation-') as directory:
        work = Path(directory)
        build = subprocess.run(['dotnet', 'build', str(ROOT/'ArcanePower.csproj'), '--nologo', '-o', str(work)],
                               capture_output=True, text=True)
        if build.returncode:
            raise RuntimeError(build.stdout+build.stderr)
        cs = work/'Check.cs'; cs.write_text(fixture)
        exe = work/'Check.exe'
        references = ['Sandbox.Game', 'VRage.Game', 'VRage.Math', 'VRage.Library', 'VRage', 'Sandbox.Common']
        subprocess.run(['mcs', '-out:'+str(exe), '-r:System.Xml.Linq',
                        '-r:/usr/lib/mono/4.5/Facades/netstandard.dll', '-r:'+str(work/'ArcanePower.dll'),
                        *['-r:'+str(GAME/'Bin64'/(name+'.dll')) for name in references], str(cs)], check=True)
        subprocess.run(['mono', str(exe), str(MOD/'Data/CubeBlocks/ArcanePower_Thermal.sbc'), str(vents)],
                       env={**os.environ, 'MONO_PATH': str(work)+':'+str(GAME/'Bin64')}, check=True)
        # Check the actual installed collision and emissive materials, including
        # the radiator base that shares the sealed pipe rotor casing design.
        from prepare_thermal_release import probe_exe, probe
        model_probe=probe_exe(work)
        ledger=json.loads((ROOT/'validation/thermal-models/native-export.json').read_text())
        collision_paths=[]
        for name in ('Space radiator','Pipe rotor','Pipe rotor head'):
            block=blocks[contract['subtype'](name)]
            model=MOD/block.findtext('Model')
            target=work/(model.stem+'.hkt')
            subprocess.run(['mono',str(model_probe),'--collision',str(model),str(target)],check=True,
                           env={**os.environ,'MONO_PATH':str(GAME/'Bin64')})
            accepted=ROOT/'assets/collisions/Cubes/large/Thermal'/target.name
            assert target.read_bytes()==accepted.read_bytes(),('Changed casing collision',name)
            collision_paths.append(target)
            record=ledger['native_models'][model.stem]
            for relative in [block.findtext('Model'),*record['lods']]:
                path=MOD/relative
                row=next(r for stem,r in ledger['native_models'].items() if path.stem==stem or path.stem.startswith(stem+'_r'))
                materials={f[1] for f in probe(model_probe,path,row['triangles']) if f[0]=='MATERIAL'}
                assert {'ThermalHot','ThermalCold'}<=materials,('Missing casing emissive channels',name,path)
                if name=='Space radiator':assert 'ThermalStatus' in materials,('Missing base status lamp',path)
        native=work/'CasingProbe.exe'
        subprocess.run(['mcs','-platform:x64','-out:'+str(native),'-r:/usr/lib/mono/4.5/Facades/netstandard.dll',
                        *['-r:'+str(GAME/'Bin64'/(n+'.dll')) for n in ('HavokWrapper','VRage.Library','VRage.Math')],
                        str(ROOT/'tools/ThermalCasingCollisionProbe.cs')],check=True)
        win=lambda path:'Z:'+str(path).replace('/',chr(92))
        subprocess.run(['wine',str(native),win(GAME/'Bin64'),*[win(p) for p in collision_paths]],check=True,
                       env={**os.environ,'WINEPREFIX':str(Path.home()/'.local/share/blender-se1-setup/wineprefix'),'WINEDEBUG':'-all'})


if __name__ == '__main__':
    main()
