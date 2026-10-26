"""Focused acceptance for legacy reloads, initialization interlocks and teardown cues.

Compiles the actual changed C# methods with small engine doubles; requires Mono.
"""
from pathlib import Path
import os
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src/Data/Scripts/ArcanePower'
GAME = Path.home() / '.local/share/Steam/steamapps/common/SpaceEngineers/Bin64'


def method(file, name):
    source = (SRC / file).read_text()
    start = re.search(r'^        (?:private|internal|public) [^{\n]*?\b' + name + r'\(', source, re.M).start()
    opening = source.index('{', start)
    depth, end = 1, opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end].replace('public override ', 'public ') + '\n'


motion = (SRC / 'Reactor.Motion.cs').read_text()
state = motion[motion.index('    public enum CorePhase'):motion.index('    public sealed partial class Reactor')]
state = re.sub(r'\[Proto(?:Contract|Member\([^]]+\))\]', '', state)
safety = (SRC / 'Reactor.Safety.cs').read_text()
source = '''using System; using System.Collections.Generic; using System.IO; using System.Xml.Serialization; using VRage.Utils; using ArcanePower;
namespace ProtoBuf {
 public class ProtoContractAttribute:Attribute {}
 public class ProtoMemberAttribute:Attribute { public bool OverwriteList; public ProtoMemberAttribute(int id){} }
}
namespace ArcanePower {
 public class ThermalRotorState { public bool Valid(long id){return true;} }
 public class ThermalRadiatorState { public bool Valid(long id){return true;} }
}
''' + state + (SRC / 'MechanismEvents.cs').read_text() + r'''
class GatewayRole { public bool IsServer=true; }
class GatewayUtilities {
 public bool IsDedicated=true;
 public string SerializeToXML<T>(T value){using(var w=new StringWriter()){new XmlSerializer(typeof(T)).Serialize(w,value);return w.ToString();}}
}
static class MyAPIGateway {
 public static GatewayRole Multiplayer=new GatewayRole();
 public static GatewayUtilities Utilities=new GatewayUtilities();
}
namespace VRage.Utils { static class MyLog {
 public static Logger Default=new Logger(); public class Logger { public List<string> Lines=new List<string>(); public void WriteLineAndConsole(string s){Lines.Add(s);} }
} }
class MyModStorageComponent : Dictionary<Guid,string> {}
class Slim { public float BuildLevelRatio=1; }
class Block {
 public bool Enabled=true,IsFunctional=true;
 public Slim SlimBlock=new Slim();
 public long EntityId=1;
 public MyModStorageComponent Storage=new MyModStorageComponent();
 public Dictionary<string,float> UpgradeValues=new Dictionary<string,float>();
 public void RefreshCustomInfo(){}
}
class Check {
 Block Entity=new Block(),reactor;
 MotionState Motion=new MotionState();
 int initializationFrames=120,controllerRingCapacity=2,controllerDiscoveryFrames=600,reloadPowerFrames;
 float previousControllers=-1;
 bool restoreLegacyHardware,motionInitialized=true,routeReady;
 bool IsLive=true,ThermalVariant,thermalRestoreFault;
 static float[] PowerMW={10000,100000,1000000};
 long Id {get{return reactor.EntityId;}}
 Guid MotionStorage=Guid.NewGuid();
 static int[] TileTypes=new int[3];
 Check(){reactor=Entity;Hardware(4);}
 void Hardware(int capacity,int count=2){reactor.UpgradeValues["ArcaneContainment"]=capacity;reactor.UpgradeValues["ArcaneControllerCount"]=count;}
 void RefreshVentRoute(){Motion.VentReady=routeReady;}
 void UpdateSafety(){} void UpdateFuel(){} void UpdatePower(){} void UpdateTiles(){} void UpdateMotion(){}
 void UpdateAppearance(){} void UpdateSound(){} void DrawMotion(){} void DrawVentOutlet(){}
 void RefreshRestPoses(){}
 void UpdateThermalMode(){} void UpdateCriticalCore(){}
 bool HasIntactControllers(){return reactor.UpgradeValues["ArcaneControllerCount"]>=2;}
''' + ''.join(method(file, name) for file, name in (
    ('Reactor.Motion.cs', 'RestoreMotionState'), ('Reactor.Motion.cs', 'Valid'),
    ('Reactor.Motion.cs', 'SaveMotion'), ('Reactor.Tiles.cs', 'ValidTileGrades'),
    ('Reactor.cs', 'CheckContainment'), ('Reactor.cs', 'UpdateBeforeSimulation'),
    ('Reactor.VentRoute.cs', 'CheckVentRoute'))) + safety[safety.index('        private bool CanOperate'):safety.index('        private bool NeedsAutoEjection')] + r'''
 static void Need(bool ok,string message){if(!ok)throw new Exception(message);}
 static MotionState Read(string xml){return (MotionState)new XmlSerializer(typeof(MotionState)).Deserialize(new StringReader(xml));}
 static void Reload(){
  string old="<MotionState><EntityId>1</EntityId><Core>Running</Core><CoreTick>25521</CoreTick><Profile>2</Profile><Enabled>true</Enabled><InstalledTiles>80</InstalledTiles><ReserveMJ>90</ReserveMJ><TileWear>0.57</TileWear></MotionState>";
  var c=new Check();c.Entity.Storage[c.MotionStorage]=old;c.RestoreMotionState(Read(old));
  Need(c.Motion.Core==CorePhase.Running && c.Motion.FuelTier==2 && c.restoreLegacyHardware,"legacy XML restores its fuel tier and running phase");
  c.SaveMotion();Need(c.Entity.Storage[c.MotionStorage]==old,"do not rewrite an unresolved legacy snapshot");
  for(int frame=119;frame>0;frame--){
   c.Hardware(frame>20?2:4,frame>20?0:2);c.UpdateBeforeSimulation();
   Need(c.reactor.Enabled && c.Motion.Core==CorePhase.Running,"loading connections cannot shut down saved core");
  }
  c.routeReady=true;c.UpdateBeforeSimulation();c.SaveMotion();
  Need(c.initializationFrames==0 && c.reactor.Enabled && c.Motion.RingCount==4 && !c.restoreLegacyHardware,"legacy hardware adopted only after grace period");
  Need(c.Motion.InstalledTiles==80 && c.Motion.ReserveMJ==90 && c.Motion.TileWear==.57f,"migration preserves consumables and reserve");
  string current=c.Entity.Storage[c.MotionStorage];var saved=Read(current);
  Need(!current.Contains("<Profile") && saved.FuelTier==2 && saved.RingCount==4,"new XML writes only independent fuel and hardware tiers");
  c=new Check();c.RestoreMotionState(saved);c.routeReady=true;
  for(int n=0;n<120;n++)c.UpdateBeforeSimulation();
  Need(c.reactor.Enabled && c.Motion.RingCount==4 && !c.restoreLegacyHardware,"modern reload preserves running hardware");
  c.routeReady=false;c.UpdateBeforeSimulation();Need(!c.reactor.Enabled,"real post-init vent loss still disables reactor");
  c=new Check();c.RestoreMotionState(saved);c.routeReady=true;c.Hardware(3);c.initializationFrames=0;c.CheckContainment();
  Need(!c.reactor.Enabled && c.Motion.RingCount==4,"modern hardware mismatch still shuts down without relatching");
  c=new Check();c.RestoreMotionState(Read(old));c.initializationFrames=1;c.UpdateBeforeSimulation();
  Need(!c.reactor.Enabled,"missing route at grace expiry fails closed");
  c=new Check();c.RestoreMotionState(Read(old.Replace("<Profile>2", "<Profile>9")));
  Need(c.Motion.Core==CorePhase.Off && !c.restoreLegacyHardware,"invalid legacy tier rejected");
  c.RestoreMotionState(Read(old.Replace("<EntityId>1", "<EntityId>2")));
  Need(c.Motion.Core==CorePhase.Off && !c.restoreLegacyHardware,"pasted entity cannot inherit saved running state");
  c=new Check();c.initializationFrames=0;c.Motion.VentReady=true;MyAPIGateway.Multiplayer.IsServer=false;c.CheckVentRoute();
  Need(c.Motion.VentReady && c.reactor.Enabled,"client preserves server vent readiness");MyAPIGateway.Multiplayer.IsServer=true;
  Console.WriteLine("PASS: legacy/current XML reload, consumables, initialization grace, missing/broken vents, hardware mismatch, invalid/copy rejection and client authority");
 }
 static void Retraction(){
  var s=new MotionState{Core=CorePhase.Running,CoreTick=5000};var e=new ArcanePower.MechanismEvents();
  Need(e.Observe(s,true)==0,"running baseline silent");s.Core=CorePhase.Stopping;s.StopTick=90;
  int pulls=0,catches=0;
  for(int age=1170;age>=0;age--){
   s.CoreTick=age;int hit=e.Observe(s,true);if((hit&4)!=0)pulls++;if((hit&8)!=0)catches++;
   Need((hit&3)==0 && e.Observe(s,true)==0,"teardown only, no stationary repeats");
  }
  Need(pulls==20 && catches==20,"twenty retract/catch pairs");
  s.CoreTick=1038;e.Observe(s,true);s.CoreTick=1037;Need(e.Observe(s,true)==0,"rollback cannot replay a release");
  s.Core=CorePhase.Off;e.Observe(s,true);s.Core=CorePhase.Stopping;s.CoreTick=1038;e.Observe(s,true);
  s.CoreTick=1037;Need(e.Observe(s,true)==4,"new cycle resets reverse events");
  e=new ArcanePower.MechanismEvents();s.CoreTick=900;Need(e.Observe(s,true)==0,"late join has no catch-up burst");
  s.CoreTick=750;Need(e.Observe(s,false)==0 && e.Observe(s,true)==0,"approach has no replay");
  s.CoreTick=750;s.Paused=true;Need(e.Observe(s,true)==0,"paused teardown silent");
  s.Paused=false;s.CoreTick=749;Need(e.Observe(s,true)==4,"resume releases quartet at crossing");
  e=new ArcanePower.MechanismEvents();s.Core=CorePhase.Starting;s.CoreTick=740;e.Observe(s,false);
  s.Core=CorePhase.Stopping;pulls=catches=0;
  for(int age=740;age>=0;age--){s.CoreTick=age;int hit=e.Observe(s,true);if((hit&4)!=0)pulls++;if((hit&8)!=0)catches++;}
  Need(pulls==11 && catches==12,"partial startup retracts only deployed quartets, including one still in flight");
  e=new ArcanePower.MechanismEvents();s.CoreTick=1038;e.Observe(s,true);s.CoreTick=1037;s.PayloadReleased=true;
  Need(e.Observe(s,true)==0,"ejected payload never makes return sounds");
  Console.WriteLine("PASS: reverse timing, twenty quartet pairs, partial assembly, pause, replay suppression, approach/late join and ejected payload");
 }
 static void RoundingReload(string fixture){
  string xml=File.ReadAllText(fixture);var original=Read(xml);
  var c=new Check();c.Entity.EntityId=original.EntityId;c.reactor.Enabled=false;c.routeReady=true;
  c.RestoreMotionState(Read(xml));
  Need(c.Motion.Core==CorePhase.Running && c.reactor.Enabled,"actual affected world snapshot restores running and enabled");
  Need(c.Motion.FuelDebt==-2.288216908615642E-07,"retain saved rounding credit without clamping");
  c.SaveMotion();
  Need(c.Entity.Storage[c.MotionStorage]==MyAPIGateway.Utilities.SerializeToXML(original),"all saved fields survive restore/save unchanged");
  for(int frame=0;frame<120;frame++)c.UpdateBeforeSimulation();
  Need(c.Motion.Core==CorePhase.Running && c.reactor.Enabled,"affected state survives connection initialization");
  foreach(double debt in new[]{-.0000005,0.0,.0000005,.999999}){
   var saved=Read(xml);saved.FuelDebt=debt;Need(Valid(saved),"accept valid signed remainder boundary");
  }
  foreach(double debt in new[]{-.00000050001,-.01,1.0,double.NaN,double.NegativeInfinity,double.PositiveInfinity}){
   var saved=Read(xml);saved.FuelDebt=debt;Need(!Valid(saved),"reject invalid remainder");
   var rejected=new Check();rejected.Entity.EntityId=saved.EntityId;int logs=MyLog.Default.Lines.Count;
   rejected.RestoreMotionState(saved);
   Need(rejected.Motion.Core==CorePhase.Off && MyLog.Default.Lines.Count==logs+1,"invalid saved state is rejected with a diagnostic");
  }
  var disabled=Read(xml);disabled.Enabled=false;c=new Check();c.Entity.EntityId=disabled.EntityId;c.RestoreMotionState(disabled);
  Need(!c.reactor.Enabled && c.Motion.Core==CorePhase.Running,"saved manual off flag remains off");
  c=new Check();c.RestoreMotionState(Read(xml));Need(c.Motion.Core==CorePhase.Off,"copied entity rejects signed-credit snapshot");
  Console.WriteLine("PASS: actual affected running XML, all fields preserved, enabled/manual-off state, signed boundaries, invalid diagnostics and copy rejection");
 }
 static void Main(string[] args){RoundingReload(args[0]);Reload();Retraction();}
}
'''
with tempfile.TemporaryDirectory(prefix='arcane-reload-retract-') as directory:
    target = Path(directory) / 'check.cs'
    target.write_text(source)
    exe = target.with_suffix('.exe')
    subprocess.run(['mcs', '-warn:0', '-r:/usr/lib/mono/4.5/Facades/netstandard.dll',
                    '-r:' + str(GAME / 'VRage.Library.dll'), '-out:' + str(exe), str(target),
                    str(SRC / 'ThermalPlant.cs'), str(SRC / 'ThermalLoops.cs')], check=True)
    subprocess.run(['mono', str(exe), str(ROOT / 'tools/fixtures/reactor-running-rounding.xml')], check=True,
                   env={**os.environ, 'MONO_PATH': str(GAME)})
