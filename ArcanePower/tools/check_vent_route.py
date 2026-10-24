"""Focused vent-route/interlock checks against actual mod methods; requires Mono."""
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'src/Data/Scripts/ArcanePower'


def method(file, name):
    source = (SCRIPTS / file).read_text()
    start = re.search(r'^        (?:private|internal) [^{\n]*?\b' + name + r'\(', source, re.M).start()
    opening = source.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end] + '\n'


motion = (SCRIPTS / 'Reactor.Motion.cs').read_text()
state = motion[motion.index('    public enum CorePhase'):motion.index('    public sealed partial class Reactor')]
state = re.sub(r'\[Proto(?:Contract|Member\([^]]+\))\]', '', state)
methods = ''.join(method('Reactor.VentRoute.cs', name) for name in ('RefreshVentRoute', 'CheckVentRoute', 'FindVentOutlet'))
methods += ''.join(method('Reactor.Motion.cs', name) for name in ('BeginShutdown', 'BeginDismantling', 'UpdateMotion'))
safety = (SCRIPTS / 'Reactor.Safety.cs').read_text()
methods += safety[safety.index('        private const float AutoEjectionIntegrity'):safety.index('        private bool IsIntactController(')]
methods += ''.join(method('Reactor.Safety.cs', name) for name in ('IsIntactController', 'HasIntactControllers', 'UpdateSafety', 'SetSecurityMode'))
methods = methods.replace('VRage.Game.ModAPI.IMyCubeBlock', 'Block')
methods += method('Reactor.Motion.cs', 'RequestVent')
power = (SCRIPTS / 'Reactor.Power.cs').read_text()
methods += power[power.index('        private bool CanPrepareContainment'):power.index('        private readonly List<ContainmentController>')]
source = r'''
using System;
using System.Collections.Generic;
using Sandbox.Game.Entities;
using VRageMath;
using IMyCubeBlock = Block;
static class MyAPIGateway {
 public static class Multiplayer { public static bool IsServer=true; }
 public static class Utilities { public static bool IsDedicated=true; }
}
class Orientation { public Base6Directions.Direction Up=Base6Directions.Direction.Up; }
class Definition { public string SubtypeName; }
class ContainmentController {}
class Logic {
 public object Component=new ContainmentController();
 public T GetAs<T>() where T:class {return Component as T;}
}
class Block {
 public long EntityId;
 public Vector3I Position;
 public Orientation Orientation=new Orientation();
 public Definition BlockDefinition=new Definition();
 public bool IsFunctional=true, Enabled=true, Closed;
 public Logic GameLogic=new Logic();
 public Slim SlimBlock;
 public Block(){SlimBlock=new Slim{FatBlock=this};}
 public float MaxOutput=1, CurrentOutput;
 public Grid CubeGrid=new Grid();
}
class Slim { public Block FatBlock; public float BuildLevelRatio=1,Integrity=100,MaxIntegrity=100; }
class Attachment { public bool Compatible=true; public Block Block; }
namespace Sandbox.Game.Entities {
 class MyCubeBlock : Block {public Dictionary<int,Attachment> CurrentAttachedUpgradeModules=new Dictionary<int,Attachment>();}
}
class Grid {
 public Dictionary<Vector3I,Slim> Blocks=new Dictionary<Vector3I,Slim>();
 public Slim GetCubeBlock(Vector3I p) { Slim s; return Blocks.TryGetValue(p,out s)?s:null; }
}
enum VentCommand { Sync }
static class VentSession { public static void SendCommand(long id,VentCommand c){} }
public class ThermalReactorState { public double ProducedMW; }
static class ThermalMath { public static double Clamp(double v,double lo,double hi){return Math.Max(lo,Math.Min(hi,v));} }
''' + state + r'''
class Check {
 const float CooldownHeat=.15f;
 Block reactor=new Block();
 MyCubeBlock Entity=new MyCubeBlock();
 Dictionary<string,int> restPoses=new Dictionary<string,int>{{"VentHatch4",0}};
 int controllerRingCapacity=2;
 MotionState Motion=new MotionState();
 bool receivedState=true,motionInitialized=true,hasFuel=true;
 bool IsLive {get{return !Entity.Closed;}}
 bool ThermalVariant=false,ThermalNeedsPowerSupport=false;
 double ThermalHeatMW=25000;
 float previousControllers=2;
 int networkTick,appearanceRefresh,initializationFrames;
 long Id=1;
 int tiles,advances,thermal,critical,publications;
 bool HasUsableFuel(){return hasFuel;}
 bool PrepareTiles(){tiles++;return true;}
 void UpdateStatus(){}
 void AdvanceMotion(){advances++;}
 void UpdateThermal(){thermal++;}
 void ApplyVentDamage(){}
 void TryReleasePayload(){}
 void UpdateCriticalCore(){critical++;}
 void RefreshFuelCapacity(){}
 void DrawMotion(){}
 void DrawVentOutlet(){}
 void PublishMotion(){publications++;}
''' + methods + r'''
 void Tick(){CheckVentRoute();UpdateSafety();UpdateMotion();}
 void Controllers(int count){
  Entity.CurrentAttachedUpgradeModules.Clear();
  for(int i=0;i<count;i++)Entity.CurrentAttachedUpgradeModules[i]=new Attachment{Block=new Block{EntityId=200+i,CubeGrid=reactor.CubeGrid}};
  UpdateSafety();
 }
 Slim Section(int index,string subtype="ArcanePower_VentDuct") {
  var p=reactor.Position+Base6Directions.GetIntVector(reactor.Orientation.Up)*(2+index);
  var b=new Block { EntityId=100+index,Position=p };
  b.Orientation.Up=reactor.Orientation.Up;b.BlockDefinition.SubtypeName=subtype;
  var slim=new Slim {FatBlock=b};reactor.CubeGrid.Blocks[p]=slim;return slim;
 }
 void Route(int ducts){for(int i=0;i<ducts;i++)Section(i);Section(ducts,"ArcanePower_VentOutlet");}
 static void Need(bool ok,string message){if(!ok)throw new Exception(message);}
 static void Main(){
  var c=new Check();c.Motion.PowerReady=true;c.Tick();
  Need(!c.Motion.VentReady && !c.reactor.Enabled && c.tiles==0 && c.Motion.Core==CorePhase.Off,"no route must block startup before tile debit");
  c.Section(0,"ArcanePower_VentOutlet");c.RefreshVentRoute();Need(!c.Motion.VentReady,"outlet alone cannot replace tube");
  c.Section(0);c.RefreshVentRoute();Need(!c.Motion.VentReady,"tube without outlet");
  c.Section(2,"ArcanePower_VentOutlet");c.RefreshVentRoute();Need(!c.Motion.VentReady,"gap");
  c.Route(1);c.reactor.Enabled=true;c.Tick();
  Need(c.Motion.VentReady && c.Motion.VentDucts==1 && c.Motion.VentOutletId==101 && c.tiles==1 && c.Motion.Core==CorePhase.Starting,"complete route starts");
  var first=c.reactor.CubeGrid.GetCubeBlock(c.reactor.Position+new Vector3I(0,2,0));
  first.FatBlock.IsFunctional=false;c.Motion.Core=CorePhase.Running;c.Motion.Heat=.8f;c.Tick();
  Need(!c.reactor.Enabled && c.Motion.Core==CorePhase.Cooling && !c.Motion.Paused,"broken route shuts down with cooling still advancing");
  first.FatBlock.IsFunctional=true;first.BuildLevelRatio=.9f;c.RefreshVentRoute();Need(!c.Motion.VentReady,"unfinished tube");
  first.BuildLevelRatio=1;first.FatBlock.Orientation.Up=Base6Directions.Direction.Down;c.RefreshVentRoute();Need(!c.Motion.VentReady,"reversed tube");
  first.FatBlock.Orientation.Up=Base6Directions.Direction.Up;first.FatBlock.Position+=Vector3I.Right;c.RefreshVentRoute();Need(!c.Motion.VentReady,"off-axis block anchor");
  first.FatBlock.Position-=Vector3I.Right;
  foreach(Base6Directions.Direction up in Enum.GetValues(typeof(Base6Directions.Direction))){
   c=new Check();c.reactor.Position=new Vector3I(23,-40,7);c.reactor.Orientation.Up=up;c.Route(15);c.RefreshVentRoute();
   Need(c.Motion.VentReady && c.Motion.VentDucts==15 && c.Motion.EjectionTravel==47.5f,"rotated maximum-length route "+up);
  }
  c=new Check();c.Route(16);c.RefreshVentRoute();Need(!c.Motion.VentReady,"overlong route");
  c=new Check();c.Route(3);c.Controllers(2);c.RefreshVentRoute();c.Motion.Vent=VentPhase.Ejecting;c.Motion.EjectTick=45;c.Motion.VentHadPayload=true;c.Motion.Critical=true;
  c.Motion.Core=CorePhase.Running;c.Motion.Heat=1.5f;c.Motion.PowerReady=true;
  long outlet=c.Motion.VentOutletId;float travel=c.Motion.EjectionTravel;
  first=c.Section(1);first.FatBlock.IsFunctional=false;c.Tick();
  Need(!c.Motion.VentReady && c.Motion.Paused && c.advances==0 && c.thermal==1 && c.critical==1,"broken committed route pauses mechanisms but not thermal/fuse updates");
  Need(c.Motion.VentOutletId==outlet && c.Motion.EjectionTravel==travel && c.Motion.EjectTick==45 && c.Motion.Critical,"retain launch and hazard state");
  first.FatBlock.IsFunctional=true;c.Section(1,"ArcanePower_VentOutlet");c.Tick();Need(!c.Motion.VentReady,"cannot shorten a committed trajectory");
  c.Section(1);c.Section(3,"ArcanePower_VentOutlet").FatBlock.EntityId=900;c.Tick();
  Need(c.Motion.VentReady && !c.Motion.Paused && c.Motion.VentOutletId==900 && c.advances==1,"repair/replacement at original height resumes");
  c.Motion.PayloadReleased=true;c.Section(1).FatBlock.IsFunctional=false;c.Tick();Need(!c.Motion.Paused,"route loss after physical handoff does not stall closure");
  c=new Check();c.Route(15);c.Motion.Vent=VentPhase.Ejecting;c.Motion.EjectionTravel=18;c.RefreshVentRoute();
  Need(!c.Motion.VentReady && c.Motion.EjectionTravel==18,"legacy save cannot change an in-flight launch distance");
  c.Motion.EjectionTravel=47.5f;c.RefreshVentRoute();Need(c.Motion.VentReady && c.Motion.VentDucts==15,"legacy route count migrates at original launch distance");
  c=new Check();c.Route(1);c.Controllers(2);c.Motion.Core=CorePhase.Running;c.Motion.CoreTick=1170;c.Motion.Heat=.8f;
  c.reactor.SlimBlock.Integrity=60.01f;c.Tick();Need(c.Motion.Vent==VentPhase.Idle,"above 60% must not auto eject");
  c.reactor.SlimBlock.Integrity=60;c.reactor.IsFunctional=false;c.Tick();
  Need(c.Motion.Vent==VentPhase.ShieldClosing && !c.Motion.Paused,"60% auto ejection works despite damaged reactor");
  int sent=c.publications;c.Tick();Need(c.Motion.Vent==VentPhase.ShieldClosing && c.publications==sent,"committed ejection starts only once");
  c.Entity.CurrentAttachedUpgradeModules[1].Block.IsFunctional=false;c.Tick();
  Need(c.Motion.Paused && !c.Motion.ControllersReady,"controller damage pauses committed ejection");
  c.Entity.CurrentAttachedUpgradeModules[1].Block.IsFunctional=true;c.Tick();Need(!c.Motion.Paused,"controller repair resumes ejection");
  foreach(int controllers in new[]{0,1}) {
   c=new Check();c.Route(1);c.Controllers(controllers);c.Motion.Core=CorePhase.Running;c.Motion.CoreTick=1170;c.reactor.SlimBlock.Integrity=50;c.Tick();
   Need(c.Motion.Vent==VentPhase.Idle,"auto ejection requires both controllers");c.RequestVent(true);Need(c.Motion.Vent==VentPhase.Idle,"manual ejection also requires both controllers");
  }
  c=new Check();c.Controllers(2);c.Entity.CurrentAttachedUpgradeModules[1]=c.Entity.CurrentAttachedUpgradeModules[0];
  Need(!c.HasIntactControllers(),"same controller cannot count twice");
  c.Controllers(2);c.Entity.CurrentAttachedUpgradeModules[1].Block.SlimBlock.BuildLevelRatio=.99f;Need(!c.HasIntactControllers(),"unfinished controller cannot eject");
  c.Controllers(2);c.Entity.CurrentAttachedUpgradeModules[1].Block.Closed=true;Need(!c.HasIntactControllers(),"removed controller cannot eject");
  c.Controllers(2);c.Entity.CurrentAttachedUpgradeModules[1].Block.CubeGrid=new Grid();Need(!c.HasIntactControllers(),"split-off controller cannot eject");
  c=new Check();c.Controllers(2);c.Motion.Core=CorePhase.Running;c.Motion.CoreTick=1170;c.Motion.SecurityMode=false;c.reactor.SlimBlock.Integrity=60;
  c.Tick();Need(c.Motion.Vent==VentPhase.Idle && c.reactor.Enabled && !c.Motion.VentReady,"broken vents block auto ejection even in warning mode");
  sent=c.publications;c.Tick();Need(c.publications==sent,"blocked auto ejection does not flood snapshots");
  c.Route(1);c.Tick();Need(c.Motion.Vent==VentPhase.ShieldClosing,"repairing vents permits pending damage ejection");
  for(int broken=0;broken<=3;broken++) {
   c=new Check();c.Route(3);c.Controllers(2);c.Motion.Core=CorePhase.Running;c.Motion.CoreTick=1170;
   c.Motion.SecurityMode=false;c.reactor.SlimBlock.Integrity=60;
   var section=c.reactor.CubeGrid.GetCubeBlock(c.reactor.Position+new Vector3I(0,2+broken,0));
   section.FatBlock.IsFunctional=false;c.Tick();
   Need(!c.Motion.VentReady && c.Motion.Vent==VentPhase.Idle,"every tube and outlet independently gates automatic ejection");
   section.FatBlock.IsFunctional=true;c.Tick();Need(c.Motion.Vent==VentPhase.ShieldClosing,"each repaired route permits ejection");
  }
  c=new Check();c.Route(1);c.Controllers(2);c.Motion.Core=CorePhase.Off;c.reactor.SlimBlock.Integrity=40;c.Tick();Need(c.Motion.Vent==VentPhase.Idle,"no core must not auto eject");
  foreach(bool secure in new[]{true,false}) {
   c=new Check();c.Controllers(2);c.Motion.SecurityMode=secure;c.Motion.PowerReady=true;c.Tick();
   Need(!c.reactor.Enabled && c.Motion.Core==CorePhase.Off && c.tiles==0,"both modes block startup without vents");
   c=new Check();c.Controllers(2);c.Motion.SecurityMode=secure;c.Motion.Core=CorePhase.Starting;c.Motion.CoreTick=200;c.Tick();
   Need(!c.reactor.Enabled && c.Motion.Core==CorePhase.Stopping,"both modes stop interrupted startup");
   c=new Check();c.Controllers(2);c.Motion.SecurityMode=secure;c.Motion.Core=CorePhase.Running;c.Motion.CoreTick=1170;c.Motion.Heat=.8f;c.Tick();
   Need(secure ? !c.reactor.Enabled && c.Motion.Core==CorePhase.Cooling : c.reactor.Enabled && c.Motion.Core==CorePhase.Running,"security mode governs vent loss after startup");
   if(!secure){c.SetSecurityMode(true);Need(!c.reactor.Enabled && c.Motion.SecurityMode,"turning security on immediately disables unsafe output");}
  }
  c=new Check();c.Route(1);c.Controllers(2);c.RefreshVentRoute();c.Motion.Core=CorePhase.Running;c.Motion.CoreTick=1170;c.reactor.SlimBlock.Integrity=50;c.initializationFrames=120;c.UpdateSafety();
  Need(c.Motion.Vent==VentPhase.Idle,"restore barrier defers automatic ejection until connections settle");
  c=new Check();c.Route(1);c.Controllers(2);c.RefreshVentRoute();c.Motion.PowerReady=true;
  Need(c.NeedsStorageSupport,"fully prepared startup releases storage reserve");
  c.hasFuel=false;Need(!c.NeedsStorageSupport,"no fuel cannot drain emergency reserve");c.hasFuel=true;
  c.reactor.SlimBlock.BuildLevelRatio=.99f;Need(!c.NeedsStorageSupport,"unfinished reactor cannot drain reserve");
  c.Tick();Need(!c.reactor.Enabled && c.tiles==0 && c.Motion.Core==CorePhase.Off,"unfinished functional reactor cannot start or debit tiles");
  c.reactor.SlimBlock.BuildLevelRatio=1;c.reactor.Enabled=true;
  c.Entity.CurrentAttachedUpgradeModules[1].Block.SlimBlock.BuildLevelRatio=.99f;Need(!c.NeedsStorageSupport,"unfinished controller cannot release startup reserve");
  c.Controllers(2);c.initializationFrames=1;Need(!c.NeedsStorageSupport,"restore barrier cannot spuriously release reserve");c.initializationFrames=0;
  c.reactor.Enabled=false;c.hasFuel=false;c.reactor.IsFunctional=false;c.Motion.Core=CorePhase.Cooling;
  Need(c.NeedsStorageSupport,"damaged fuel-less core still needs safe cooling power");
  c.Motion.Core=CorePhase.Off;c.Motion.Vent=VentPhase.Ejecting;Need(c.NeedsStorageSupport,"committed vent still needs power");
  c.Entity.Closed=true;Need(!c.NeedsStorageSupport,"removed reactor cannot request reserve");
  c=new Check();MyAPIGateway.Multiplayer.IsServer=false;c.Motion.VentReady=true;c.CheckVentRoute();Need(c.Motion.VentReady,"client must use server readiness");
  c.UpdateSafety();Need(c.Motion.Vent==VentPhase.Idle,"client cannot auto eject");
  c.SetSecurityMode(false);Need(c.Motion.SecurityMode,"client cannot mutate security mode locally");
  Console.WriteLine("PASS: vent route geometry, startup interlock, 60% auto ejection, intact/distinct controllers, damaged reactor ejection, blocked route repair, committed pause/resume, both security modes, restoration and server authority");
 }
}
'''
game = Path.home() / '.local/share/Steam/steamapps/common/SpaceEngineers/Bin64'
with tempfile.TemporaryDirectory(prefix='arcane-vent-check-') as directory:
    target = Path(directory) / 'check.cs'
    target.write_text(source)
    exe = target.with_suffix('.exe')
    subprocess.run(['mcs', '-out:' + str(exe), '-r:' + str(game / 'VRage.Math.dll'),
                    '-r:' + str(game / 'VRage.Library.dll'),
                    '-r:/usr/lib/mono/4.5/Facades/netstandard.dll', str(target)], check=True)
    import os
    subprocess.run(['mono', str(exe)], env=dict(os.environ, MONO_PATH=str(game)), check=True)

failure = (SCRIPTS / 'Reactor.Failure.cs').read_text()
release = method('Reactor.Failure.cs', 'TryReleasePayload')
assert 'if (!HasIntactControllers()) return;' in release
assert release.index('if (!HasIntactControllers()) return;') < release.index('CoreHazards.Release(')
session = (SCRIPTS / 'VentSession.cs').read_text()
assert 'packet.Command > VentCommand.Brayton' in session
assert session.index('!r.Block.HasPlayerAccess(identity)') < session.index('Apply(r, packet.Command)')
assert 'SendCommand(b.EntityId, enabled ? VentCommand.SecurityOn : VentCommand.SecurityOff)' in session
print('PASS: physical handoff checks controllers; security switch uses authorized server commands')
