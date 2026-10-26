"""Exercise shipped startup power/telemetry and emissives with recording engine doubles.

This is an offline behavior check, not a running-game visual check. Requires Mono.
"""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src/Data/Scripts/ArcanePower'
reactor = (SRC / 'Reactor.cs').read_text()
power = (SRC / 'Reactor.Power.cs').read_text()
status = (SRC / 'Reactor.Status.cs').read_text()
motion = (SRC / 'Reactor.Motion.cs').read_text()
fuel = (SRC / 'Reactor.Fuel.cs').read_text()
safety = (SRC / 'Reactor.Safety.cs').read_text()


def member(source, signature):
    start = source.index(signature)
    end = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end] + '\n'


fields = reactor[reactor.index('        private IMyReactor reactor;'):reactor.index('        public override void Init')]
fields += fuel[fuel.index('        private static readonly string[] Fuels'):fuel.index('        private MyReactor nativeReactor;')]
state = motion[motion.index('    public enum CorePhase'):motion.index('    public sealed partial class Reactor')]
methods = ''.join(member(source, signature) for source, signature in [
    (reactor, '        private void UpdateAppearance()'),
    (reactor, '        private void UpdateStatus()'),
    ((SRC / 'Reactor.Failure.cs').read_text(), '        private void UpdateThermal()'),
    ((SRC / 'Reactor.Failure.cs').read_text(), '        internal void UpdateThermalForecast()'),
    (power, '        private bool CanPrepareContainment'),
    (power, '        private float ContainmentMW'),
    (power, '        private double ReserveCapacityMJ'),
    (power, '        private bool Precharging'),
    (power, '        private double PrechargeMW'),
    (power, '        private void UpdatePower()'),
    (fuel, '        private bool HasUsableFuel()'),
    ((SRC / 'Reactor.Thermal.cs').read_text(), '        private bool ThermalFuelModeReady'),
    (safety, '        private bool CanOperate'),
    (safety, '        private bool NeedsAutoEjection'),
])
# Compile the complete status builder too; terminal text and dashboard inputs
# must agree with the actual reserve accounting, including short terminal reports.
methods += status[status.index('        // LCD, tablet'):status.index('    internal sealed class StatusRow')].rsplit('    }', 1)[0]
types = status[status.index('    internal sealed class StatusRow'):].rsplit('}', 1)[0]
stubs = r'''
using System;
using System.Globalization;
using System.Collections.Generic;
using System.Text;
using ArcanePower;
using ProtoBuf;
namespace ProtoBuf {
 class ProtoContractAttribute:Attribute {}
 class ProtoMemberAttribute:Attribute { public bool OverwriteList; public ProtoMemberAttribute(int id){} }
}
struct Color {
 public int R,G,B; public Color(int r,int g,int b){R=r;G=g;B=b;}
 public static Color Red=new Color(255,0,0),Yellow=new Color(255,255,0),White=new Color(255,255,255);
}
class MyLight {}
class Render { public bool Visible=true; }
class MyEntity {
 public Dictionary<string,MyEntitySubpart> Subparts=new Dictionary<string,MyEntitySubpart>();
 public bool Ready,Closed; public int Applied; public float Intensity; public Color Color;
 public Render Render=new Render();
 public void SetEmissiveParts(string name,Color color,float intensity){if(Ready){Applied++;Color=color;Intensity=intensity;}}
 public void SetEmissivePartsForSubparts(string name,Color color,float intensity){foreach(var p in Subparts.Values)p.SetEmissiveParts(name,color,intensity);}
}
class MyEntitySubpart:MyEntity {}
class MyCubeBlock:MyEntity { public Dictionary<int,Upgrade> CurrentAttachedUpgradeModules=new Dictionary<int,Upgrade>(); }
class Upgrade { public bool Compatible=true; public ControllerBlock Block=new ControllerBlock(); }
class ControllerBlock { public bool Closed,IsFunctional=true; public Logic GameLogic=new Logic(); }
class Logic { public ContainmentController Controller=new ContainmentController(); public T GetAs<T>() where T:class{return Controller as T;} }
class ContainmentController { public float Supply,Requested; public float Request(long id,float demand){Requested=demand;return Math.Min(Supply,demand);} }
class Slim { public float BuildLevelRatio=1,Integrity=100,MaxIntegrity=100; }
class Inventory { public double Stock=10; public double GetItemAmount(string type){return Stock;} }
static class MyItemType { public static string MakeIngot(string type){return type;} public static string MakeComponent(string type){return type;} }
class IMyReactor:MyCubeBlock {
 public bool Enabled=true,MarkedForClose,IsFunctional=true,UseConveyorSystem=true;
 public string CustomName="Test reactor"; public float CurrentOutput;
 public Slim SlimBlock=new Slim(); public Inventory Inventory=new Inventory();
 public Inventory GetInventory(){return Inventory;}
}
static class MyAPIGateway {
 public static class Utilities { public static bool IsDedicated; }
 public static class Multiplayer { public static bool IsServer=true; }
 public static class Session { public static bool CreativeMode; }
}
namespace ArcanePower {
 public class ThermalRotorState { public bool Valid(long id){return true;} }
 public class ThermalRadiatorState { public bool Valid(long id){return true;} }
}
static class CoreHazards { public static float EjectedCountdown(long id,out int count){count=0;return 0;} }
class Reactor {
 public MyEntity Entity;
 MotionState Motion=new MotionState(); bool receivedState=true,thermalRestoreFault,thermalStartRequested;
 ThermalForecast heatForecast;
 bool ThermalCanRun {get{return reactor.Enabled && Motion.Core==CorePhase.Running;}}
 bool ThermalVariant {get{return Motion.Thermal!=null;}} double ThermalHeatMW=25000;
 const float CooldownHeat=.15f,AutoEjectionIntegrity=.60f;
 readonly List<ContainmentController> powerControllers=new List<ContainmentController>();
 long Id=1;
 string[] TileNames={"Standard","Reinforced","Advanced"};
 bool HasIntactControllers(){return Motion.ControllersReady;}
 bool HasAdvancedController(){return true;}
 string ThermalModeTransitionHint {get{return "Mode transition";}}
 int[] SpareTileQuartets(){return new[]{20,0,0};} int NeededTileQuartets(){return 20;}
 int InstalledTileGrade(int batch){return 0;} double TileWearRate(){return 1;}
 double TileReserveSeconds(){return 60;} double FuelUnitsPerMinute(){return 0;}
 float PlasmaScale(float tick){return 0;} void UpdateCoreGlow(MyEntity entity,Color color,float scale){}
 void BeginShutdown(){Motion.Core=CorePhase.Stopping;}
'''
checks = r'''
 static void Need(bool value,string message){if(!value)throw new Exception(message);}
 static void Near(double a,double b,string message){Need(Math.Abs(a-b)<.0001,message+": "+a+" != "+b);}
 Reactor(int tier=1){
  reactor=new IMyReactor();Entity=reactor;initializationFrames=0;previousControllers=2;controllerRingCapacity=4;
  Motion.FuelTier=tier;Motion.ControllersReady=true;Motion.VentReady=true;
  Motion.Thermal=new ThermalReactorState();
  if(tier>1){Motion.Thermal.Mode=Motion.Thermal.Requested=ThermalMode.Brayton;Motion.Thermal.Deployment=1;}
  reactor.CurrentAttachedUpgradeModules.Add(0,new Upgrade());reactor.CurrentAttachedUpgradeModules.Add(1,new Upgrade());
  for(int i=1;i<=4;i++)Entity.Subparts["Ring"+i]=new MyEntitySubpart();
  UpdateStatus();
 }
 void Supply(float total){foreach(var p in reactor.CurrentAttachedUpgradeModules.Values)p.Block.GameLogic.Controller.Supply=total/2;}
 void Tick(){UpdatePower();UpdateStatus();UpdateAppearance();}
 void RenderReady(){Entity.Ready=true;foreach(var p in Entity.Subparts.Values)p.Ready=true;}
 static void Charging(){
  for(int tier=1;tier<=3;tier++){
   var r=new Reactor(tier);r.RenderReady();
   var report=r.ReadStatus(false);
   Need(report.Precharging && report.State.Contains("WAITING FOR POWER"),"empty startup explicitly waits for power");
   Need(report.Value("Charge ETA")=="Waiting for surplus power","no ETA without delivered surplus");
   r.Supply(r.ContainmentMW);r.Tick();
   Near(r.Motion.ReserveMJ,0,"containment-only input cannot charge");Near(r.PrechargeMW,0,"no advertised charging without surplus");
   float first=r.Entity.Intensity;for(int i=0;i<30;i++)r.UpdateAppearance();
   Need(r.Entity.Color.Equals(Color.White) && r.Entity.Intensity>0 && r.Entity.Intensity<first,"waiting slowly fades white");
   r.Supply(r.ContainmentMW*4);r.Tick();report=r.ReadStatus(false);
   Need(report.State.Contains("CHARGING STARTUP RESERVE") && report.Tone=="white","active startup has distinct white presentation");
   Near(r.PrechargeMW,r.ContainmentMW*3,"charge rate excludes containment draw");
   Need(report.Value("Charge ETA")=="~30 s" && report.Value("Startup charge")=="0%","empty reserve ETA uses actual input");
   Need(report.Text().Contains("Reserve energy:") && report.Text().Contains("requested"),"short terminal includes stored energy and actual/requested draw");
   int on=0,off=0;
   for(int i=0;i<60;i++){
    r.UpdateAppearance();
    if(r.Entity.Intensity==EmissiveIntensity)on++;else if(r.Entity.Intensity==0)off++;
    Need(r.Entity.Color.Equals(Color.White),"charging never uses a fuel colour");
    Near(r.Entity.Subparts["Ring1"].Intensity,r.Entity.Intensity,"housing and subparts share charging blink");
   }
   Need(on==30 && off==30,"charging blinks once per second with equal on/off time");
   for(int i=1;i<900;i++)r.Tick();
   Near(r.Motion.ReserveMJ/r.ReserveCapacityMJ,.5,"15 seconds of full input stores half the reserve");
   // An exact half-full saved/replicated state avoids accumulated sub-percent
   // floating-point error at the integer display boundary.
   r.Motion.ReserveMJ=r.ReserveCapacityMJ/2;report=r.ReadStatus(true);
   Need(report.Value("Startup charge")=="50%" && report.Value("Charge ETA")=="~15 s","half-full progress and ETA");
   r.Supply(r.ContainmentMW*2);r.Tick();report=r.ReadStatus(false);
   Need(report.Value("Charge ETA")=="~45 s","partial supply slows ETA");
   r.Supply(0);double stored=r.Motion.ReserveMJ;r.Tick();report=r.ReadStatus(false);
   Near(r.Motion.ReserveMJ,stored,"offline reserve remains stored");
   Need(report.Value("Charge rate")=="0 MW net" && report.State.Contains("WAITING FOR POWER"),"loss of surplus stops charging indication");
   r.Supply(r.ContainmentMW*4);
   for(int i=0;i<901;i++)r.Tick();
   Need(r.Motion.PowerReady && !r.Precharging && !r.ReadStatus(false).Precharging,"full reserve clears charging presentation");
   Near(r.Entity.Intensity,EmissiveIntensity,"completion restores steady brightness immediately");
   Need(r.Entity.Color.Equals(FuelColors[tier-1]),"completion restores selected fuel colour");
   Need(r.ReadStatus(false).Value("Charge ETA")=="--","completion removes obsolete ETA");
   r.Supply(0);r.Tick();report=r.ReadStatus(false);
   Need(report.State.Contains("WAITING FOR POWER") && report.Value("Charge ETA")=="Reserve full","stored energy alone cannot start reactor");
   Need(report.Text().Contains("Reserve full; supply"),"full-reserve hint asks for containment power");
  }
  Console.WriteLine("PASS: measured startup charge, rate/ETA, partial/no supply, full reserve and all fuel tiers");
 }
 static void Priority(){
  for(int connected=0;connected<=4;connected++){
   var stopped=new Reactor();stopped.Motion.Thermal.Mode=stopped.Motion.Thermal.Requested=ThermalMode.Brayton;
   stopped.Motion.Thermal.Deployment=1;stopped.reactor.Enabled=false;stopped.Motion.Core=CorePhase.Cooling;
   for(int i=0;i<connected;i++)stopped.Motion.Thermal.Loops[i].Connected=true;
   Need(stopped.ReadStatus(false).State=="COOLING DOWN","normal shutdown shows cooldown for every circuit defect count");
   var circuitReport=stopped.ReadStatus(false);
   Need(circuitReport.Value("Circuits available")==connected+" / 4 ("+connected*25+"% allocation)","available count follows validated circuits immediately");
   for(int i=0;i<4;i++)Need(circuitReport.Value("Circuit "+(i+1))==(i<connected?"Ready / valve open":"Unavailable / valve closed"),"dashboard valve state matches the actual valve mask");
   Need(!circuitReport.Text().Contains("MPa") && !circuitReport.Text().Contains("charged / valve"),"circuit diagnostics contain no retired pressure or filling state");

   stopped.Motion.Thermal.LoopTrip=true;
   Need(stopped.ReadStatus(false).State=="STARTUP BLOCKED / ALL FOUR CIRCUITS DEFECTIVE","only explicit rejected startup shows the circuit latch");
  }
  foreach(Action<Reactor> change in new Action<Reactor>[]{
   r=>r.reactor.Enabled=false, r=>r.receivedState=false, r=>r.initializationFrames=120,
   r=>r.reactor.Inventory.Stock=0, r=>r.Motion.TileStarved=true, r=>r.Motion.PowerPaused=true,
   r=>r.Motion.ControllersReady=false, r=>r.Motion.VentReady=false,
   r=>r.Motion.Thermal.Requested=ThermalMode.Brayton, r=>r.Motion.Thermal.Faulted=true,
   r=>r.Motion.Critical=true, r=>r.Motion.Vent=VentPhase.Ejecting,
   r=>r.reactor.IsFunctional=false, r=>r.Motion.Core=CorePhase.Starting,
   r=>r.Motion.Core=CorePhase.Running, r=>r.Motion.Core=CorePhase.Cooling,
   r=>r.Motion.Core=CorePhase.Stopping}){
   var r=new Reactor();r.RenderReady();r.Supply(4);r.Tick();change(r);r.UpdateStatus();r.UpdateAppearance();
   Need(!r.Precharging && !r.ReadStatus(false).Precharging,"interlocks and other phases suppress startup charge");
   if(r.Motion.Critical || r.Motion.Vent!=VentPhase.Idle)Need(r.Entity.Color.Equals(Color.Red),"critical/vent alarm overrides charging");
  }
  var client=new Reactor();client.Motion.ReserveMJ=45;client.Motion.PowerInputMW=4;
  MyAPIGateway.Multiplayer.IsServer=false;client.Tick();
  Near(client.Motion.ReserveMJ,45,"client does not invent charge progress");
  Need(client.ReadStatus(false).Value("Charge ETA")=="~15 s","client presents replicated measured input");
  MyAPIGateway.Multiplayer.IsServer=true;
  Console.WriteLine("PASS: fault/vent/interlock priority, phase transitions and client presentation");
 }
 static void RenderRecovery(){
  var r=new Reactor();r.Motion.Core=CorePhase.Running;r.Motion.PowerReady=true;
  var ring=r.Entity.Subparts["Ring1"];r.UpdateAppearance();Need(ring.Applied==0,"fixture drops early render updates");
  r.RenderReady();for(int i=0;i<60;i++)r.UpdateAppearance();
  Need(ring.Applied==1 && ring.Color.Equals(FuelColors[0]),"delayed renderer recovers without toggling");
  var late=new MyEntitySubpart{Ready=true};r.Entity.Subparts["Ring4"]=late;
  for(int i=0;i<60;i++)r.UpdateAppearance();Need(late.Applied==1,"later child replacement recovers");
  r.Motion.FuelTier=3;r.UpdateAppearance();Need(late.Color.Equals(FuelColors[2]),"fuel changes apply immediately");
  int before=ring.Applied;MyAPIGateway.Utilities.IsDedicated=true;
  for(int i=0;i<65;i++)r.UpdateAppearance();Need(ring.Applied==before,"dedicated servers skip rendering");
  MyAPIGateway.Utilities.IsDedicated=false;
  Console.WriteLine("PASS: late/recreated render objects, immediate fuel updates, dedicated skip");
 }
 static void ThermalWarnings(){
  for(int tier=1;tier<=3;tier++){
   var r=new Reactor(tier);r.RenderReady();r.Motion.Core=CorePhase.Running;r.Motion.PowerReady=true;
   foreach(float heat in new[]{0f,.5f,.85f,1f}){
    r.Motion.Heat=heat;r.Motion.TargetLoad=1;r.UpdateThermal();r.UpdateThermalForecast();r.UpdateStatus();r.UpdateAppearance();
    Need(r.Entity.Color.Equals(FuelColors[tier-1]),"healthy heat keeps the running fuel colour, including full load");
    Need(r.ReadStatus(false).HeatTone=="white","healthy warmup and full load do not colour terminal/LCD heat as a warning");
   }
   r.reactor.Inventory.Stock=0;r.UpdateStatus();r.UpdateAppearance();
   Need(r.Motion.Status==ReactorStatus.OutOfFuel && r.Entity.Color.Equals(Color.White),"fuel starvation is neutral white, not a thermal alarm");
   r.reactor.Enabled=false;r.UpdateStatus();r.UpdateAppearance();
   Need(r.Motion.Status==ReactorStatus.OutOfFuel && r.Entity.Color.Equals(Color.White),"automatic shutdown cannot latch yellow for missing fuel");
   r.reactor.Inventory.Stock=10;r.reactor.Enabled=true;r.Motion.TileStarved=true;r.Motion.TileWear=1;r.Motion.Heat=.6f;
   r.UpdateThermal();r.UpdateThermalForecast();r.UpdateStatus();r.UpdateAppearance();
   Need(r.Entity.Color.Equals(Color.Yellow) && r.Entity.Subparts["Ring1"].Color.Equals(Color.Yellow),"failed worn tiles warn on housing and subparts before heat crosses 100%");
   Need(r.ReadStatus(false).HeatTone=="yellow" && r.ReadStatus(false).State=="MELTDOWN RISK / NEXT 60 S","status and heat tone use the same predictive warning");
   r.Motion.TileStarved=false;r.Motion.TileWear=0;r.UpdateThermal();r.UpdateThermalForecast();r.UpdateStatus();r.UpdateAppearance();
   Need(r.Entity.Color.Equals(Color.Yellow) && r.ReadStatus(false).State=="THERMAL WARNING / RECOVERING","repair begins a stable recovery hold");
   for(int i=0;i<315;i++){r.UpdateThermal();r.UpdateThermalForecast();}r.UpdateStatus();r.UpdateAppearance();
   Need(r.Entity.Color.Equals(FuelColors[tier-1]),"safe forecast clears yellow after recovery confirmation");
   r.Motion.Core=CorePhase.Cooling;r.reactor.Enabled=false;r.Motion.Heat=1.1f;r.UpdateThermal();r.UpdateThermalForecast();r.UpdateStatus();r.UpdateAppearance();
   Need(!r.Entity.Color.Equals(Color.Yellow) && r.ReadStatus(false).HeatTone=="white","hot residual core cooling safely does not claim runaway");
   r.Motion.Thermal.Loops[0].ExcessMJ=50000;r.Motion.Thermal.Loops[0].RequiredCoolingMW=5000;
   r.Motion.Thermal.RequiredCoolingMW=5000;
   for(int i=0;i<135;i++){r.UpdateThermal();r.UpdateThermalForecast();}r.UpdateAppearance();
   Need(r.Entity.Color.Equals(Color.Yellow),"retained circuit heat that will drive the core higher still warns during shutdown");
   r.Motion.Critical=true;r.UpdateAppearance();Need(r.Entity.Color.Equals(Color.Red),"critical warning takes priority over yellow");
   r.Motion.Critical=false;r.Motion.Vent=VentPhase.ShieldClosing;r.UpdateAppearance();Need(r.Entity.Color.Equals(Color.Red),"ejection takes priority over yellow");
   r.Motion.Vent=VentPhase.Idle;r.Motion.Heat=1;r.Motion.ForecastPeakHeat=1;r.Motion.ForecastWarning=false;r.UpdateAppearance();Need(!r.Entity.Color.Equals(Color.Yellow),"server-cleared warning restores the normal colour");
   r.Motion.ForecastPeakHeat=3;MyAPIGateway.Multiplayer.IsServer=false;r.UpdateThermal();r.UpdateThermalForecast();
   Need(r.Motion.ForecastPeakHeat==3,"clients present the server forecast rather than inventing their own");MyAPIGateway.Multiplayer.IsServer=true;
   r.Motion.Heat=2;r.Motion.PayloadReleased=true;r.UpdateAppearance();Need(!r.Entity.Color.Equals(Color.Yellow),"released core does not leave a stale housing alarm");
   r.Motion.PayloadReleased=false;r.Motion.Core=CorePhase.Off;r.Motion.TileStarved=true;r.Motion.TileWear=1;
   r.UpdateStatus();r.UpdateAppearance();Need(!r.Entity.Color.Equals(Color.Yellow),"missing startup tiles without a core are not runaway");
  }
  var named=new Reactor();named.Motion.Core=CorePhase.Running;named.Motion.ForecastWarning=true;
  named.Motion.ForecastPeakHeat=1.1f;named.Motion.ForecastOverheatSeconds=42.3f;named.Motion.ForecastCircuit=2;
  Need(named.ReadStatus(false).Value("Thermal outlook")=="Circuit 2 / overheating in ~43 s","terminal forecast names the limiting circuit and rounds ETA up");
  named.Motion.ForecastMeltdownSeconds=50;named.Motion.ForecastPeakHeat=2;
  Need(named.ReadStatus(false).Value("Thermal outlook")=="Circuit 2 / critical heat in ~50 s","critical forecast has its own ETA");
  named.Motion.Critical=true;
  Need(named.ReadStatus(false).Value("Thermal outlook")=="Supercritical / countdown active","armed hazard cannot claim a safe outlook");
  Console.WriteLine("PASS: rolling forecasts, warning/recovery timing, circuit ETAs, server authority and critical/ejection priority");
 }
 static void Main(){Charging();Priority();RenderRecovery();ThermalWarnings();}
}
'''
with tempfile.TemporaryDirectory(prefix='arcane-appearance-') as folder:
    path = Path(folder) / 'check.cs'
    path.write_text(stubs + fields + methods + checks + state + types)
    exe = path.with_suffix('.exe')
    subprocess.run(['mcs', '-warn:0', '-out:' + str(exe), str(path),
                    str(SRC/'ThermalPlant.cs'), str(SRC/'ThermalLoops.cs'), str(SRC/'ThermalForecast.cs')], check=True)
    subprocess.run(['mono', str(exe)], check=True)
