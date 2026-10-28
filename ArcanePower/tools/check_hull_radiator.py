"""Check generated hull definitions and the production fixed-face cooling sampler.

Run after the solution build. No export or installation is performed.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

import prepare_thermal_release as release


def main():
    root, contract = release.ROOT, release.CONTRACT
    installed = release.MOD/'Data/CubeBlocks/ArcanePower_Thermal.sbc'
    before = hashlib.sha256(installed.read_bytes()).hexdigest()
    models = {k:v for k,v in json.loads((release.OUT/'models.json').read_text()).items() if k in contract['PLAYABLE']}
    mains = {k:'APT_'+v['subtype'].removeprefix('ArcanePower_Thermal_')+'_M' for k,v in models.items()}
    pending = release.definitions(models, mains, Path('Models/Cubes/large/Thermal/pending_full_export'), write=False)
    definitions = {b.findtext('Id/SubtypeId'):b for b in pending.find('CubeBlocks')}
    for name in ('Hull radiator', 'Hull radiator upgraded'):
        block = definitions[contract['subtype'](name)]
        assert block.findtext('Id/TypeId') == 'UpgradeModule'
        assert block.find('Size').attrib == dict(x='3', y='2', z='1')
        assert block.findtext('IsAirTight') == 'true'
        assert block.findtext('Public') == 'true'
        assert len(block.find('BuildProgressModels')) == 3
        assert 'rear' in block.findtext('Description').lower()
        assert not block.findall("Components/Component[@Subtype='SolarCell']")
    assert not definitions[contract['subtype']('Radiator panel')].findall("Components/Component[@Subtype='SolarCell']")
    assert hashlib.sha256(installed.read_bytes()).hexdigest() == before, 'Preview changed installed definitions'

    source = (root/'src/Data/Scripts/ArcanePower/ThermalBlock.Radiator.cs').read_text()
    start = source.index('private double HullRadiatorCooling(')
    end = source.index('{', start)+1
    depth = 1
    while depth:
        depth += (source[end] == '{')-(source[end] == '}'); end += 1
    fixture = r'''
using System;
using ArcanePower;
using VRageMath;
namespace VRage.Game.ModAPI { public interface IHitInfo {} }
class Grid {
 public bool Obstructed;
 public Vector3I? RayCastBlocks(Vector3D from,Vector3D to){return Obstructed?(Vector3I?)Vector3I.Zero:null;}
}
class BlockFixture {
 public MatrixD WorldMatrix;public Grid CubeGrid=new Grid();
 public Vector3D GetPosition(){return WorldMatrix.Translation;}
}
class StoreFixture { public ThermalRadiatorState Radiator=new ThermalRadiatorState(); }
static class MyGamePruningStructure {public static object GetClosestPlanet(Vector3D at){return new object();}}
static class MyVisualScriptLogicProvider {
 public static bool Dark;public static bool IsOnDarkSide(object planet,Vector3D at){return Dark;}
}
static class MyAPIGateway {
 public static class Physics {
  public static MatrixD Frame;public static bool Half,ReverseBlocked;
  public static bool CastRay(Vector3D from,Vector3D to,out VRage.Game.ModAPI.IHitInfo hit){
   hit=null;
   bool reverse=Vector3D.Dot(to-from,Frame.Forward)<0;
   Vector3D local=Vector3D.Transform(reverse?to:from,MatrixD.Invert(Frame));
   Check.Near(local.Z,-1.28,"clearance ray starts outside front");
   Check.Near((to-from).Length(),250,"clearance ray length");
   Check.Near(Math.Abs(Vector3D.Dot(Vector3D.Normalize(to-from),Frame.Forward)),1,"front-normal ray");
   return reverse?ReverseBlocked:Half && local.X<0;
  }
 }
 public static class Session {public static class WeatherEffects {
  public static double Multiplier=1;public static double GetSolarMultiplier(Vector3D at){return Multiplier;}
 }}
}
class Check {
 BlockFixture Block=new BlockFixture();StoreFixture Store=new StoreFixture();
 ThermalModel Spec=new ThermalModel{CoolingMW=1000};double PanelCoolingMW;
 int litCalls;bool halfShade;
 bool SolarPivotLit(Vector3D from,Vector3D sun){
  litCalls++;Vector3D local=Vector3D.Transform(from,MatrixD.Invert(Block.WorldMatrix));
  Near(local.Z,-1.28,"solar pivot outside front");return !halfShade || local.X>=0;
 }
 // METHOD
 static int checks;
 static void Need(bool ok,string label){checks++;if(!ok)throw new Exception(label);}
 public static void Near(double a,double b,string label){Need(Math.Abs(a-b)<.00001,label+": "+a+" != "+b);}
 void Sample(Vector3D sun,double expected,double exposure,double incidence,bool shadow=false,double density=0){
  Near(HullRadiatorCooling(density,sun,shadow),expected,"available cooling");
  Near(PanelCoolingMW,expected,"own cooling");Near(Store.Radiator.Exposure,exposure,"front clearance fraction");
  Near(Store.Radiator.SunIncidence,incidence,"front solar load");
 }
 static void Main(){
  var probe=new Check();int poses=0;
  foreach(var f in new[]{Vector3D.Right,Vector3D.Left,Vector3D.Up,Vector3D.Down,Vector3D.Forward,Vector3D.Backward})
   foreach(var up in new[]{Vector3D.Right,Vector3D.Left,Vector3D.Up,Vector3D.Down,Vector3D.Forward,Vector3D.Backward}){
    if(Math.Abs(Vector3D.Dot(f,up))>.1)continue;poses++;
    probe.Block.WorldMatrix=MyAPIGateway.Physics.Frame=MatrixD.CreateWorld(new Vector3D(21,35,-41),f,up);
    probe.Sample(-f,1000,1,0);Need(probe.litCalls==0,"rear sunlight never samples front");
    probe.Sample(f,500,1,1);Need(probe.litCalls==32,"front uses all 32 solar pivots");probe.litCalls=0;
    probe.halfShade=true;probe.Sample(f,750,1,.5);probe.halfShade=false;probe.litCalls=0;
    MyAPIGateway.Physics.Half=true;probe.Sample(-f,500,.5,0);MyAPIGateway.Physics.Half=false;
    probe.Block.CubeGrid.Obstructed=true;probe.Sample(-f,0,0,0);probe.Block.CubeGrid.Obstructed=false;
    MyAPIGateway.Physics.ReverseBlocked=true;probe.Sample(-f,0,0,0);MyAPIGateway.Physics.ReverseBlocked=false;
    probe.Sample(f,1000,1,0,true);Need(probe.litCalls==0,"planet eclipse skips solar rays");
    MyVisualScriptLogicProvider.Dark=true;probe.Sample(f,1000,1,0);MyVisualScriptLogicProvider.Dark=false;
    MyAPIGateway.Session.WeatherEffects.Multiplier=.5;probe.Sample(f,750,1,.5);
    MyAPIGateway.Session.WeatherEffects.Multiplier=1;probe.litCalls=0;
    probe.Sample(-f,ThermalRadiators.Cooling(1000,1,1,0),1,0,false,1);
   }
  Need(poses==24,"all grid orientations");
  Console.WriteLine("PASS: "+checks+" fixed-face cooling checks across 24 poses; hull recipes have zero Solar Cells; definition preview leaves installed definitions unchanged");
 }
}
'''.replace('// METHOD', source[start:end])
    game = release.GAME/'Bin64'
    output = root/'bin/Debug/net48'
    with tempfile.TemporaryDirectory(prefix='arcane-hull-radiator-') as directory:
        path = Path(directory)
        (path/'Check.cs').write_text(fixture)
        subprocess.run(['mcs','-langversion:6','-out:'+str(path/'Check.exe'),
                        '-r:/usr/lib/mono/4.5/Facades/netstandard.dll','-r:'+str(output/'ArcanePower.dll'),
                        *['-r:'+str(game/(n+'.dll')) for n in ('VRage.Math','VRage.Library')],str(path/'Check.cs')],check=True)
        subprocess.run(['mono',str(path/'Check.exe')],check=True,
                       env={**os.environ,'MONO_PATH':str(output)+':'+str(game)})


if __name__ == '__main__':
    main()
