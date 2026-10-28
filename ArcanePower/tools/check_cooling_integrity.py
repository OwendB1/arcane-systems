"""Exercise production cooling eligibility, panel linking and pressure-loss rules.

Run after dotnet build arcane-systems.sln. The fixture supplies native block
state; the actual adapter methods, network, dispatch and heat budget are tested.
"""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT/'src/Data/Scripts/ArcanePower'
GAME = Path.home()/'.local/share/Steam/steamapps/common/SpaceEngineers/Bin64'


def member(file, signature):
    source = (SRC/file).read_text()
    start = source.index(signature)
    end = source.index('{', start)+1
    depth = 1
    while depth:
        depth += (source[end] == '{')-(source[end] == '}'); end += 1
    return source[start:end]


fixture = r'''
using System;
using System.Collections.Generic;
using System.IO;
using System.Xml.Serialization;
using ArcanePower;
using VRageMath;
namespace VRage.ModAPI { public interface IMyVoxelBase {} }
class Position {public Matrix LocalMatrixRef=Matrix.Identity;public Vector3D GetPosition(){return Vector3D.Zero;}}
class MyEntity {public long EntityId;public Position PositionComp=new Position();}
class Slim {public float BuildLevelRatio=1;public EngineBlock FatBlock;}
class Orientation {public void GetMatrix(out Matrix matrix){matrix=Matrix.Identity;}}
class Grid {
 public long EntityId=1;public object Physics=new object();
 public Dictionary<Vector3I,Slim> Cells=new Dictionary<Vector3I,Slim>();
 public Vector3I WorldToGridInteger(Vector3D at){return new Vector3I(at/2.5);}
 public Vector3D GetPosition(){return Vector3D.Zero;}
 public Slim GetCubeBlock(Vector3I cell){Slim slim;return Cells.TryGetValue(cell,out slim)?slim:null;}
}
class EngineBlock:MyEntity {
 public bool Closed,MarkedForClose,Enabled=true,IsFunctional=true,Access=true;
 public long OwnerId=1;public Slim SlimBlock=new Slim();public Grid CubeGrid=new Grid();
 public MatrixD WorldMatrix=MatrixD.Identity;public Orientation Orientation=new Orientation();
 public bool HasPlayerAccess(long owner){return Access;}
 public Vector3D GetPosition(){return WorldMatrix.Translation;}
}
class MyPlanet:VRage.ModAPI.IMyVoxelBase {public double AverageRadius=1000;public Position PositionComp=new Position();}
static class MyVisualScriptLogicProvider {public static Vector3D GetSunDirection(){return Vector3D.Up;}}
static class MyAPIGateway {public static class Multiplayer {public static bool IsServer=true;}public static class Session {public static class VoxelMaps {
 public static void GetInstances(List<VRage.ModAPI.IMyVoxelBase> planets,Func<VRage.ModAPI.IMyVoxelBase,bool> filter){}
}}}
class ThermalBlock {
 internal EngineBlock Block=new EngineBlock();internal MyEntity Entity {get{return Block;}}
 internal ThermalModel Spec;internal ThermalStore Store=new ThermalStore();internal int CircuitRevision;
 internal ThermalBlock RadiatorBase;internal List<ThermalBlock> RadiatorPanels=new List<ThermalBlock>();
 internal double PanelCoolingMW;double coolingMW;
 string Fault {get{return Store.Fault;}}
 internal bool IsRadiator {get{return Spec.Kind==ThermalKind.Radiator || Spec.Kind==ThermalKind.RadiatorPanel || Spec.Kind==ThermalKind.HullRadiator;}}
 internal bool IsCooling {get{return IsRadiator || Spec.Kind==ThermalKind.AirCooler;}}
 void UpdateEnvironment(){coolingMW=Spec.Kind==ThermalKind.Radiator?RadiatorCooling(0):Spec.CoolingMW;}
 double PanelCooling(double density,double angle,Vector3D sun,bool shadow){PanelCoolingMW=Spec.CoolingMW;return PanelCoolingMW;}
 double HullRadiatorCooling(double density,Vector3D sun,bool shadow){return Spec.CoolingMW;}
 internal double SamplePanels(){return RadiatorCooling(0);}
 internal void InvalidateRadiatorCooling(){CircuitRevision++;}
 // BLOCK
}
class ThermalSession {
 internal static Dictionary<long,ThermalBlock> Blocks=new Dictionary<long,ThermalBlock>();
 // LINK
 internal static void Relink(){LinkRadiators();}
}
class Checks {
 static int count;
 static void Need(bool value,string label){count++;if(!value)throw new Exception(label);}
 static void Near(double a,double b,string label){Need(Math.Abs(a-b)<.00001,label);}
 static ThermalPort Socket(float x,float normal){return new ThermalPort("CO2",new Vector3(x,0,0),new Vector3(normal,0,0),Vector3.Up);}
 static ThermalEndpoint Node(long id,ThermalKind kind,ThermalPort[] ports){return new ThermalEndpoint{
  Id=id,GridId=1,Healthy=true,Model=new ThermalModel{Kind=kind,RatingMW=100},Ports=ports};}
 static ThermalBlock Cooler(ThermalKind kind,long id=4){
  var block=new ThermalBlock{Spec=new ThermalModel{Kind=kind,RatingMW=100,CoolingMW=100,Ports=new[]{Socket(3,-1)}}};
  block.Block.EntityId=block.Store.EntityId=id;block.Store.Radiator=new ThermalRadiatorState{EntityId=id};return block;
 }
 static List<ThermalEndpoint> Layout(ThermalBlock cooler){return new List<ThermalEndpoint>{
  Node(1,ThermalKind.Reactor,new[]{Socket(0,1)}),Node(2,ThermalKind.Pipe,new[]{Socket(0,-1),Socket(2,1),Socket(3,1)}),
  Node(3,ThermalKind.Train,new[]{Socket(2,-1)}),cooler.Endpoint(1)};}
 static void Main(){
  foreach(var kind in new[]{ThermalKind.AirCooler,ThermalKind.Radiator,ThermalKind.HullRadiator,ThermalKind.RadiatorPanel}){
   var c=Cooler(kind);
   foreach(int failure in new[]{0,1,2}){
    c.Block.Enabled=failure!=0;c.Block.IsFunctional=failure!=1;c.Block.SlimBlock.BuildLevelRatio=failure==2?.2f:1;
    Need(c.CircuitReady && c.Endpoint(1).Healthy,"present failed cooler keeps physical connection");
    Need(!c.Healthy,"failed cooler is not operational");Near(c.Unit().CoolingMW,0,"failed cooler rejects no heat");
    if(kind==ThermalKind.RadiatorPanel)continue;
    var nodes=Layout(c);Need(new ThermalNetwork(nodes).Loops(nodes[0])[0].Ready,"failed cooler does not trip circuit");
    var plan=ThermalMath.Dispatch(100,650,new[]{new ThermalUnit{Kind=ThermalKind.Train,RatingMW=100},c.Unit()});
    Near(plan.NetMW,80,"cooling failure does not throttle electricity");Near(plan.CoolingMW,0,"cooling is lost");
    nodes.RemoveAt(3);Need(!new ThermalNetwork(nodes).Loops(nodes[0])[0].Ready,"removed cooler opens pipe and trips circuit");
   }
   c.Block.Enabled=c.Block.IsFunctional=true;c.Block.SlimBlock.BuildLevelRatio=1;
   Need(c.Healthy,"repair restores operation");
   c.Block.Access=false;Need(!c.Endpoint(1).Healthy,"access is still required");c.Block.Access=true;
   Need(!c.Endpoint(0).Healthy,"ownerless connection remains rejected");
   c.Block.Closed=true;Need(!c.CircuitReady,"closed block cannot seal");c.Block.Closed=false;
   c.Block.MarkedForClose=true;Need(!c.CircuitReady,"removing block cannot seal");c.Block.MarkedForClose=false;
   c.Block.CubeGrid.Physics=null;Need(!c.CircuitReady,"projection cannot seal");
  }
  foreach(var kind in new[]{ThermalKind.Pipe,ThermalKind.Train}){
   var c=Cooler(kind);c.Block.IsFunctional=false;Need(!c.Endpoint(1).Healthy,"pipe/turbine damage rules unchanged");
  }
  var failed=Cooler(ThermalKind.AirCooler);failed.Block.IsFunctional=false;
  var layout=Layout(failed);var circuit=new ThermalNetwork(layout).Loops(layout[0])[0];
  var state=new ThermalReactorState{Mode=ThermalMode.Brayton,Deployment=1};
  var loop=state.Loops[0];loop.Connected=circuit.Ready;state.Loops[1].Connected=true;
  double heat=0;
  for(int tick=0;tick<1800;tick++){
   state.Store.HotMJ+=100.0/60;
   var grant=new ThermalOutputGrant(state,loop,100.0/60,.8);Need(grant.Settle(grant.MaximumMW),"power remains paid");
   ThermalMath.CoolCircuit(loop,failed.Unit().CoolingMW);
   heat=ThermalMath.ApproachCoreHeat(heat,Math.Max(1,ThermalMath.WasteHeatLevel(state,400)),false);
   Need(ThermalLoops.OpenValves(state)==3,"failed cooling keeps pressure valve open");
  }
  Need(loop.ExcessMJ>0 && heat>1.25,"failed cooling can overheat reactor");
  layout.RemoveAt(3);loop.Connected=new ThermalNetwork(layout).Loops(layout[0])[0].Ready;
  Need(ThermalLoops.OpenValves(state)==2,"block removal closes affected valve only");

  var root=Cooler(ThermalKind.Radiator,10);ThermalSession.Blocks[root.Block.EntityId]=root;
  var panels=new List<ThermalBlock>();
  for(int i=0;i<3;i++){
   var p=Cooler(ThermalKind.RadiatorPanel,11+i);panels.Add(p);p.Block.CubeGrid=root.Block.CubeGrid;
   p.Block.WorldMatrix=MatrixD.CreateTranslation(ThermalRadiators.ExtensionCentre(root.Block.WorldMatrix,i));
   p.Block.SlimBlock.FatBlock=p.Block;root.Block.CubeGrid.Cells[root.Block.CubeGrid.WorldToGridInteger(p.Block.GetPosition())]=p.Block.SlimBlock;
   ThermalSession.Blocks[p.Block.EntityId]=p;
  }
  ThermalSession.Relink();Near(root.SamplePanels(),300,"three healthy panels cool");Need(root.Store.Radiator.RequiredPanels==3,"stack seal remembers installed panels");
  panels[1].Block.IsFunctional=false;ThermalSession.Relink();
  Need(root.RadiatorPanels.Count==3 && panels[2].RadiatorBase==root,"broken middle panel retains path to top panel");
  Need(root.Endpoint(1).Healthy,"broken middle panel does not breach base");
  Near(root.SamplePanels(),200,"only broken panel loses capacity");Near(panels[1].PanelCoolingMW,0,"broken panel contribution cleared");
  root.Block.Enabled=false;ThermalSession.Relink();Need(root.RadiatorPanels.Count==3,"disabled base retains stack plumbing");
  Near(root.Unit().CoolingMW,0,"disabled base does not reject heat");root.Block.Enabled=true;
  ThermalSession.Blocks.Remove(panels[1].Block.EntityId);ThermalSession.Relink();
  Need(root.RadiatorPanels.Count==1 && root.RadiatorBreached && !root.Endpoint(1).Healthy,"missing middle panel breaches stack");
  var serializer=new XmlSerializer(typeof(ThermalStore));
  using(var stream=new MemoryStream()){
   serializer.Serialize(stream,root.Store);stream.Position=0;root.Store=(ThermalStore)serializer.Deserialize(stream);
  }
  Need(root.Store.Valid(10,800) && root.Store.Radiator.RequiredPanels==3 && root.RadiatorBreached,"stack connection history survives XML reload");
  ThermalSession.Blocks[panels[1].Block.EntityId]=panels[1];ThermalSession.Relink();Need(!root.RadiatorBreached,"replacement repairs missing panel seal");
  MyAPIGateway.Multiplayer.IsServer=false;root.Store.Radiator.Panels=3;Need(!root.RadiatorBreached,"client uses replicated stack count");
  root.Store.Radiator.Panels=1;Need(root.RadiatorBreached,"client sees missing panel breach");MyAPIGateway.Multiplayer.IsServer=true;
  panels[1].Block.IsFunctional=true;Near(root.SamplePanels(),300,"repair restores cooling without rebuilding stack");
  root.Store.Radiator.RequiredPanels=4;Need(!root.Store.Valid(10,800),"invalid saved stack size rejected");
  Console.WriteLine("PASS: "+count+" cooling integrity, removal, stack, reload, valve and runaway checks");
 }
}
'''


def main():
    members = [('ThermalBlock.cs', signature) for signature in (
        'internal bool Healthy', 'internal bool HardwareReady', 'internal bool CircuitReady',
        'internal ThermalEndpoint Endpoint(', 'internal ThermalUnit Unit(')]
    members += [('ThermalBlock.Radiator.cs', signature) for signature in (
        'internal bool RadiatorBreached', 'private double RadiatorCooling(')]
    code = fixture.replace('// BLOCK', '\n'.join(member(*pair) for pair in members))
    code = code.replace('// LINK', member('ThermalSession.Radiators.cs', 'private static void LinkRadiators('))
    output = ROOT/'bin/Debug/net48'
    with tempfile.TemporaryDirectory(prefix='arcane-cooling-integrity-') as directory:
        path = Path(directory)
        (path/'Check.cs').write_text(code)
        subprocess.run(['mcs','-langversion:6','-out:'+str(path/'Check.exe'),
                        '-r:/usr/lib/mono/4.5/Facades/netstandard.dll','-r:'+str(output/'ArcanePower.dll'),
                        *['-r:'+str(GAME/(name+'.dll')) for name in ('VRage.Math','VRage.Library')],str(path/'Check.cs')],check=True)
        subprocess.run(['mono',str(path/'Check.exe')],check=True,
                       env={**os.environ,'MONO_PATH':str(output)+':'+str(GAME)})


if __name__ == '__main__':
    main()
