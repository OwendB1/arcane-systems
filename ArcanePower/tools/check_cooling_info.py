"""Exercise cooling terminal text, measured capacity and the real telemetry packet."""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src/Data/Scripts/ArcanePower'
GAME = Path.home() / '.local/share/Steam/steamapps/common/SpaceEngineers/Bin64'
session = (SRC / 'ThermalSession.cs').read_text()


def member(signature):
    start = session.index(signature)
    end = session.index('{', start) + 1
    depth = 1
    while depth:
        depth += (session[end] == '{') - (session[end] == '}')
        end += 1
    return session[start:end]


fixture = r'''
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using ProtoBuf;
using ArcanePower;
namespace VRage.Utils { public class MyLog {public static MyLog Default=new MyLog();public void WriteLine(string value){}} }
static class MyAPIGateway {
 public static class Multiplayer {
  public static bool IsServer;public static byte[] Sent;
  public static void SendMessageTo(ushort channel,byte[] bytes,ulong target){Sent=bytes;}
 }
 public static class Utilities {
  static ProtoBuf.Meta.RuntimeTypeModel model=ProtoBuf.Meta.RuntimeTypeModel.Create();
  public static void InvokeOnGameThread(Action action){action();}
  public static byte[] SerializeToBinary<T>(T value){using(var s=new MemoryStream()){model.Serialize(s,value);return s.ToArray();}}
  public static T SerializeFromBinary<T>(byte[] bytes){using(var s=new MemoryStream(bytes))return (T)model.Deserialize(s,null,typeof(T));}
 }
}
namespace ArcanePower {
 [ProtoContract] public class ThermalRotorState {public bool Valid(long id){return true;}}
 public class Slim {public float BuildLevelRatio=1;}
 public class EngineBlock {
  public long EntityId=1;public bool Enabled=true,IsFunctional=true;public Slim SlimBlock=new Slim();public int Refreshes;
  public void RefreshCustomInfo(){Refreshes++;}
 }
 public abstract partial class ThermalBlock {
  internal EngineBlock Block=new EngineBlock();internal EngineBlock Entity {get{return Block;}}
  internal ThermalModel Spec=new ThermalModel();internal ThermalStore Store=new ThermalStore();
  internal ThermalBlock RadiatorBase;internal List<ThermalBlock> RadiatorPanels=new List<ThermalBlock>();
  internal double PanelCoolingMW,CoolingRejectedMW;internal bool CoolingConnected,CoolingPowered=true;double coolingMW,clearExhaust;internal int Samples;
  internal bool IsRadiator {get{return Spec.Kind==ThermalKind.Radiator || Spec.Kind==ThermalKind.RadiatorPanel;}}
  internal bool Healthy {get{return Block.Enabled && Block.IsFunctional && Block.SlimBlock.BuildLevelRatio>=1 && Fault==null;}}
  internal string Fault {get{return Store.Fault;}}
  private void UpdateEnvironment(){Samples++;}
  internal void Sample(double available,double own,double density,double clear){coolingMW=available;PanelCoolingMW=own;airDensity=density;clearExhaust=clear;}
  internal string Text(){var b=new StringBuilder();AppendCoolingInfo(b);return b.ToString();}
  internal void ReceiveRotor(ThermalRotorState value){}
  internal void ReceiveRadiator(ThermalRadiatorState value){if(value!=null)Store.Radiator=value;}
 }
 public class CoolingProbe:ThermalBlock {}
 // PACKET
 public class ThermalSession {
  static bool ready=true;const ushort RotorChannel=49375;
  internal static Dictionary<long,ThermalBlock> Blocks=new Dictionary<long,ThermalBlock>();
  internal static ThermalRotorPacket Packet(ThermalBlock b){return MotionPacket(b);}
  internal static bool Eligible(ThermalBlock b){return HasTelemetry(b);}
  internal void Receive(byte[] bytes,bool server){ReceiveRotor(RotorChannel,bytes,42,server);}
  // SESSION
 }
 class Checks {
  static int checks;
  static void Need(bool value,string message){checks++;if(!value)throw new Exception(message);}
  static void Near(double a,double b,string message){Need(Math.Abs(a-b)<.00001,message);}
  static CoolingProbe Block(ThermalKind kind,double rating=1000){return new CoolingProbe{Spec=new ThermalModel{Kind=kind,CoolingMW=rating}};}
  static byte[] Wire(ThermalRotorPacket packet){return MyAPIGateway.Utilities.SerializeToBinary(packet);}
  static void Main(){
   var air=Block(ThermalKind.AirCooler);Need(air.Text().Contains("Waiting for cooling readings"),"unmeasured state is explicit");
   double capacity=ThermalMath.AirCooling(1000,.5,.5);air.Sample(capacity,capacity,.5,.5);
   air.Store.HotMJ=20;air.Store.WasteMJ=30;
   var measured=air.CaptureCooling();Need(measured.Valid(1),"measured cooler snapshot validates");
   Need(air.Text().Contains("Stored heat: 50.0 MJ"),"existing stored heat information retained");
   Need(air.Text().Contains("Efficiency: 12.5%") && air.Text().Contains("125 MW / 1 GW rated"),"capacity includes both density and squared clearance");
   Need(air.Text().Contains("Airflow factor: 25%") && air.Text().Contains("Clear 2.5 m"),"partial blockage explains nonlinear loss");
   Near(measured.AvailableMW,capacity,"display preserves simulation capacity before circulation");
   air.Block.Enabled=false;air.CaptureCooling();Need(air.Text().Contains("SWITCHED OFF") && air.Text().Contains("Efficiency: 0%"),"disabled cooler is unavailable");
   air.Block.Enabled=true;air.Block.SlimBlock.BuildLevelRatio=.9f;air.CaptureCooling();Need(air.Text().Contains("FINISH WELDING"),"unfinished cooler is explained");
   air.Block.SlimBlock.BuildLevelRatio=1;air.Sample(0,0,0,1);air.CaptureCooling();Need(air.Text().Contains("Requires atmosphere"),"vacuum loss is explained");
   var active=Block(ThermalKind.AirCooler,25000);active.Sample(25000,25000,1,1);
   Need(active.CaptureCooling().Valid(1) && active.Text().Contains("25 GW / 25 GW rated") && active.Text().Contains("Efficiency: 100%"),"25 GW cooler fits telemetry and reaches full atmospheric rating");
   active.CoolingConnected=true;active.CoolingPowered=false;active.CaptureCooling();
   Need(active.Text().Contains("waiting for reactor auxiliary power") && active.Text().Contains("Efficiency: 0%"),"unpowered connected active cooler exposes unavailable capacity");
   active.CoolingPowered=true;active.CaptureCooling();Need(active.Text().Contains("Efficiency: 100%"),"auxiliary supply restores capacity without a flow multiplier");
   active.Sample(0,0,0,1);active.CaptureCooling();Need(active.Text().Contains("Efficiency: 0%") && active.Text().Contains("Air density: 0%"),"25 GW cooler is unavailable in vacuum");
   var thin=Block(ThermalKind.Radiator,10000);thin.Store.Radiator=new ThermalRadiatorState{EntityId=1,Exposure=1};
   double thinCapacity=ThermalRadiators.Cooling(10000,1,.0011,0);thin.Sample(thinCapacity,thinCapacity,.0011,1);thin.CaptureCooling();
   Need(thin.Text().Contains("Air density: 0.1%") && thin.Text().Contains("Ambient cooling factor: 99.9%"),"terminal uses measured density without a full-atmosphere cutoff");
   var root=Block(ThermalKind.Radiator);var panel=Block(ThermalKind.RadiatorPanel,10000);
   root.Store.Radiator=new ThermalRadiatorState{EntityId=1,Exposure=1,SunIncidence=1};
   panel.Store.Radiator=new ThermalRadiatorState{EntityId=2,Exposure=.75};panel.Block.EntityId=2;
   root.RadiatorPanels.Add(panel);panel.RadiatorBase=root;
   root.Sample(8000,500,0,0);panel.Sample(0,7500,0,0);
   measured=root.CaptureCooling();Near(measured.RatedMW,11000,"mixed panel ratings summed once");
   Near(measured.AvailableMW,8000,"extension counted once in stack capacity");
   Need(root.Text().Contains("Efficiency: 72.7%") && root.Text().Contains("Base panel: 50% / 500 MW"),"stack efficiency weighted by capacity");
   Need(root.Text().Contains("Solar cooling factor: 50%") && root.Text().Contains("Ambient cooling factor: 100%") && root.Text().Contains("Air density: 0%"),"radiator losses and vacuum measurement exposed");
   panel.CaptureCooling();Need(panel.Text().Contains("Efficiency: 75%") && panel.Text().Contains("7.5 GW / 10 GW rated"),"extension shows its own contribution");
   Need(panel.Text().Contains("attached to radiator axis") && root.Samples==2,"extension reads its base's cached environment");
   panel.RadiatorBase=null;panel.CaptureCooling();Need(panel.Text().Contains("UNATTACHED PANEL") && panel.Text().Contains("Efficiency: 0%"),"detached extension cannot report stale capacity");
   root.Store.Fault="Test isolation";root.CaptureCooling();Need(root.Text().Contains("ISOLATED / Test isolation") && root.Text().Contains("Efficiency: 0%"),"runtime isolation visible");
   root.Store.Fault=null;
   foreach(var target in new[]{air,root,panel,Block(ThermalKind.Train)})Need(ThermalSession.Eligible(target),"all cooling blocks and shafts have telemetry");
   Need(!ThermalSession.Eligible(Block(ThermalKind.Pipe)),"pipes do not gain cooling broadcasts");
   var packet=ThermalSession.Packet(root);packet.Cooling.Fault=new string('x',256);
   byte[] bytes=Wire(packet);Need(bytes.Length<=1024,"cooling plus radiator snapshot fits existing packet limit");
   var copy=MyAPIGateway.Utilities.SerializeFromBinary<ThermalRotorPacket>(bytes);
   Need(copy.Cooling.Valid(1) && copy.Cooling.Fault.Length==256,"real protobuf preserves cooling fields");
   Near(copy.Cooling.AvailableMW,8000,"protobuf preserves measured capacity");
   var client=Block(ThermalKind.Radiator);ThermalSession.Blocks[1]=client;var receiver=new ThermalSession();
   MyAPIGateway.Multiplayer.IsServer=false;receiver.Receive(bytes,false);
   Need(client.Block.Refreshes==0,"client ignores readings from another client");
   receiver.Receive(bytes,true);Need(client.Block.Refreshes==1 && client.Text().Contains("8 GW / 11 GW rated"),"server snapshot refreshes native terminal");
   receiver.Receive(bytes,true);Need(client.Block.Refreshes==1,"duplicate sequence ignored");
   foreach(Action<ThermalCoolingState> corrupt in new Action<ThermalCoolingState>[] {
    s=>s.EntityId=2,s=>s.Sequence=-1,s=>s.RatedMW=0,s=>s.AvailableMW=double.NaN,
    s=>s.AvailableMW=s.RatedMW+1,s=>s.PanelMW=s.AvailableMW+1,s=>s.Clearance=-.1,
    s=>s.SunExposure=2,s=>s.AirDensity=double.PositiveInfinity,s=>s.Panels=4,s=>s.StoredHeatMJ=double.NaN,s=>s.Fault=new string('x',257)}){
    var invalid=MyAPIGateway.Utilities.SerializeFromBinary<ThermalRotorPacket>(bytes);invalid.Cooling.Sequence++;corrupt(invalid.Cooling);
    receiver.Receive(Wire(invalid),true);Need(client.Block.Refreshes==1,"malformed cooling snapshot ignored");
   }
   MyAPIGateway.Multiplayer.IsServer=true;MyAPIGateway.Multiplayer.Sent=null;ThermalSession.Blocks[1]=root;
   receiver.Receive(bytes,false);Need(MyAPIGateway.Multiplayer.Sent==null,"clients cannot submit cooling measurements");
   receiver.Receive(Wire(new ThermalRotorPacket{EntityId=1}),false);
   Need(MyAPIGateway.Multiplayer.Sent!=null,"read-only sync request receives live measurements");
   var old=Wire(new ThermalRotorPacket{EntityId=1,Radiator=root.Store.Radiator});
   MyAPIGateway.Multiplayer.IsServer=false;ThermalSession.Blocks[1]=client;receiver.Receive(old,true);
   Need(client.Block.Refreshes==1 && client.Text().Contains("8 GW / 11 GW rated"),"older packets without cooling preserve the last reading");
   Console.WriteLine("PASS: "+checks+" cooling terminal, mixed-panel capacity, environment, protobuf and authority checks");
  }
 }
}
'''
packet = session[session.index('    [ProtoContract]'):session.index('    [MySessionComponentDescriptor')]
fixture = fixture.replace('// PACKET', packet).replace('// SESSION', '\n'.join(member(signature)
    for signature in ('private static bool HasTelemetry(', 'private static ThermalRotorPacket MotionPacket(', 'private void ReceiveRotor(')))
with tempfile.TemporaryDirectory(prefix='arcane-cooling-info-') as folder:
    source = Path(folder) / 'check.cs'
    source.write_text(fixture)
    exe = source.with_suffix('.exe')
    subprocess.run(['mcs', '-warn:0', '-langversion:6', '-out:' + str(exe),
                    '-r:/usr/lib/mono/4.5/Facades/netstandard.dll',
                    *['-r:' + str(GAME / (name + '.dll')) for name in
                      ('ProtoBuf.Net.Core', 'ProtoBuf.Net', 'VRage.Math', 'VRage.Library')], str(source),
                    *[str(SRC / name) for name in ('ThermalBlock.Status.cs', 'ThermalPlant.cs',
                       'ThermalLoops.cs', 'ThermalRadiators.cs', 'ThermalNetwork.cs')]], check=True)
    subprocess.run(['mono', str(exe)], env={**os.environ, 'MONO_PATH': str(GAME)}, check=True)
