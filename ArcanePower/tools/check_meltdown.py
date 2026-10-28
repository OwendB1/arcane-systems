"""Focused production meltdown/ejection checks with engine doubles; requires .NET SDK and Mono.

Runs the real ownership, damage, release, tracking and explosion methods. Native
physics, collision clearance and visual appearance still require a running game.
"""
from pathlib import Path
import os
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src/Data/Scripts/ArcanePower'
GAME = Path.home() / '.local/share/Steam/steamapps/common/SpaceEngineers/Bin64'
# Match SE's component-derived functional cutoff for the shipped housing.
components = ET.parse(GAME.parent / 'Content/Data/Components.sbc')
component_integrity = {c.findtext('Id/SubtypeId'): float(c.findtext('MaxIntegrity'))
                       for c in components.findall('.//Component') if c.find('MaxIntegrity') is not None}
housing = next(b for b in ET.parse(ROOT / 'src/Data/CubeBlocks/ArcanePower_Thermal.sbc').findall('.//Definition')
               if b.findtext('Id/SubtypeId') == 'ArcanePower_Thermal_ReactorHousing')
housing_integrity = housing_cutoff = critical_group = 0
for component in housing.find('Components'):
    integrity = component_integrity[component.get('Subtype')]
    housing_integrity += integrity * int(component.get('Count'))
    if component.get('Subtype') == housing.find('CriticalComponent').get('Subtype'):
        if critical_group == int(housing.find('CriticalComponent').get('Index')):
            housing_cutoff = housing_integrity - integrity
        critical_group += 1


def member(file, name):
    source = (SRC / file).read_text()
    start = re.search(r'^        (?:private|internal|public) [^{\n]*?\b' + name + r'\(', source, re.M).start()
    end = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end].replace('public override void', 'public void') + '\n'


hazards = (SRC / 'CoreHazards.cs').read_text()
types = hazards[hazards.index('    [ProtoContract]'):hazards.index('    // The hazard')]
motion = (SRC / 'Reactor.Motion.cs').read_text()
state = motion[motion.index('    public enum CorePhase'):motion.index('    public sealed partial class Reactor')]
hazard_methods = ''.join(member('CoreHazards.cs', name) for name in (
    'Inside', 'Arm', 'Release', 'CreateCarrier', 'RestoreCarrier', 'Seconds', 'AdvanceFuse',
    'UpdateBeforeSimulation', 'Explode', 'EjectedCountdown'))
reactor_methods = ''.join(member('Reactor.Failure.cs', name) for name in (
    'TrackCore', 'CoreWorldPosition', 'UpdateCriticalCore', 'CoreDetonated', 'TryReleasePayload',
    'CaptureCoreShell', 'CompletePayloadRelease', 'TryReleaseFailedHousing', 'ApplyOverheatDamage',
    'WorldPose', 'RandomVector', 'LaunchVelocity'))
reactor_methods += ''.join(member('Reactor.Motion.cs', name) for name in (
    'UpdateMotion', 'AdvanceMotion', 'AdvanceVentShieldTest', 'RequestVentShieldTest', 'RequestVent',
    'AdvanceSpin', 'BeginShutdown', 'BeginDismantling',
    'Span', 'Ease', 'RingOrientation', 'ShutdownRingOrientation', 'ContainmentOffset',
    'ContainmentRotation', 'EjectionOffset', 'PayloadRingPose', 'PayloadTilePose',
    'PlasmaScale', 'PayloadPlasmaPose'))
reactor_methods += member('Reactor.Tiles.cs', 'DiscardTiles')
reactor_methods += member('Reactor.Power.cs', 'UpdatePower')
power = (SRC / 'Reactor.Power.cs').read_text()
reactor_methods += power[power.index('        internal bool VentPowerAvailable'):power.index('        // Presentation')]
reactor_methods += motion[motion.index('        internal bool CanTestVentShields'):motion.index('        internal void RequestVentShieldTest')]
reactor_methods += re.search(r'        private const float VentSpeed = [^;]+;', motion).group() + '\n'

heat_methods = ''.join(member('ThermalPlant.cs', name) for name in ('CoreHeatResponse', 'ApproachCoreHeat'))

stubs = r'''
using System;
using System.Collections.Generic;
using System.IO;
using System.Xml.Serialization;
using ProtoBuf;
using VRageMath;
using VRage.Utils;
using ArcanePower;
namespace VRage.Utils {
 static class MyLog { public static Logger Default=new Logger(); public class Logger {public void WriteLine(string s){}} }
 struct MyStringHash {public static MyStringHash GetOrCompute(string s){return new MyStringHash();}}
}
namespace Sandbox.Common.ObjectBuilders { class MyObjectBuilder_Warhead {} }
namespace Sandbox.Definitions {
 class MyWarheadDefinition { public float WarheadExplosionDamage=15000; public double ExplosionRadius=22.4415; }
 class MyDefinitionManager { public static MyDefinitionManager Static=new MyDefinitionManager(); public object GetCubeBlockDefinition(object id){return new MyWarheadDefinition();} }
}
namespace ArcanePower {
 class MyDefinitionId { public MyDefinitionId(Type t,string id){} }
 enum MyCubeSize { Small }
 enum MyPersistentEntityFlags2 { Enabled=1,InScene=2 }
 enum MyExplosionTypeEnum { CUSTOM }
 enum MyPhysicsForceType { APPLY_WORLD_FORCE }
 class MyPositionAndOrientation { public MatrixD World; public MyPositionAndOrientation(MatrixD m){World=m;} }
 class MyObjectBuilder_CubeBlock { public string SubtypeName; public Vector3I Min; public float BuildPercent,IntegrityPercent; }
 class MyObjectBuilder_CubeGrid {
  public MyCubeSize GridSizeEnum;public bool IsStatic,CreatePhysics,DestructibleBlocks=true,Editable=true;
  public MyPositionAndOrientation PositionAndOrientation;public Vector3 LinearVelocity,AngularVelocity;
  public string DisplayName;public MyPersistentEntityFlags2 PersistentFlags;
  public List<MyObjectBuilder_CubeBlock> CubeBlocks=new List<MyObjectBuilder_CubeBlock>();
 }
 class MySoundPair {public MySoundPair(string s){} }
 class MyExplosionInfo {
  public BoundingSphereD Sphere; public float Damage;public long OriginEntity;public Vector3 Velocity;
  public float StrengthImpulse,ParticleScale;public int ObjectsRemoveDelayInMiliseconds;
  public MySoundPair CustomSound;public string CustomEffect;public bool IgnoreFriendlyFireSetting;public MyEntity OwnerEntity;
  public MyExplosionInfo(int a,float d,BoundingSphereD s,MyExplosionTypeEnum e,bool b){Damage=d;Sphere=s;}
 }
 static class MyExplosions {
  public static bool Allowed=true;public static List<MyExplosionInfo> Blasts=new List<MyExplosionInfo>();
  public static bool AddExplosion(ref MyExplosionInfo info){if(!Allowed)return false;Blasts.Add(info);return true;}
 }
 class Physics {
  public Vector3 LinearVelocity,AngularVelocity;public float Mass=100;
  public Vector3 GetVelocityAtPoint(Vector3D p){return LinearVelocity;}
  public void AddForce(MyPhysicsForceType type,Vector3 force,object p,object t){}
 }
 class Logic {public object Component;public T GetAs<T>() where T:class{return Component as T;} }
 interface IMyEntity {
  long EntityId{get;}bool Closed{get;}bool MarkedForClose{get;}MatrixD WorldMatrix{get;}Physics Physics{get;}Logic GameLogic{get;}void Close();
 }
 interface IMyCubeGrid:IMyEntity {}
 class MyEntity:IMyEntity {
  public long EntityId{get;set;}public bool Closed{get;set;}public bool MarkedForClose{get;set;}
  public MatrixD WorldMatrix{get;set;}=MatrixD.Identity;public Physics Physics{get;set;}=new Physics();
  public Logic GameLogic{get;set;}=new Logic();public void Close(){Closed=true;}
 }
 class MyCubeGrid:MyEntity,IMyCubeGrid {public bool DestructibleBlocks=true,Editable=true;}
 interface IMySlimBlock {float MaxIntegrity{get;}void DoDamage(float amount,MyStringHash type,bool sync,long attackerId);}
 class Slim:IMySlimBlock {
  public float Integrity=1000,Maximum=1000,FunctionalCutoff=600;public float MaxIntegrity{get{return Maximum;}}public int Hits;
  public void DoDamage(float amount,MyStringHash type,bool sync,long attackerId){Integrity-=amount;Hits++;}
 }
 class Attachment {public bool Compatible=true;public MyCubeBlock Block;}
 class MyCubeBlock:MyEntity {
  public bool Enabled=true,Functional=true;public bool IsFunctional{get{return Functional && SlimBlock.Integrity>SlimBlock.FunctionalCutoff;}}
  public float CurrentOutput,MaxOutput=1;
  public Slim SlimBlock=new Slim();public MyCubeGrid CubeGrid=new MyCubeGrid();
  public Dictionary<int,Attachment> CurrentAttachedUpgradeModules=new Dictionary<int,Attachment>();
 }
 class ContainmentController {public float Request(long id,float demand){return 0;}}
 [ProtoContract] public class ThermalReactorState {public double ProducedMW;public bool Settled=true;}
 static class ThermalMath {public static double Clamp(double v,double lo,double hi){return Math.Max(lo,Math.Min(hi,v));}
''' + heat_methods + r'''
}
 enum VentCommand {Sync}
 static class VentSession {public static void SendCommand(long id,VentCommand command){}}
 static class MyAPIGateway {
  public static class Multiplayer {public static bool IsServer=true;}
  public static class Utilities {public static bool IsDedicated=true;}
  public static class Physics {
   public static Vector3 CalculateNaturalGravityAt(Vector3D p,out float interference){interference=0;return Vector3.Zero;}
   public static Vector3 CalculateArtificialGravityAt(Vector3D p,float interference){return Vector3.Zero;}
  }
  public static class Entities {
   public static Dictionary<long,IMyEntity> All=new Dictionary<long,IMyEntity>();
   public static bool Fail;public static int Creates;static long next=100;
   public static MyObjectBuilder_CubeGrid Last;
   public static bool TryGetEntityById(long id,out IMyEntity e){return All.TryGetValue(id,out e);}
   public static IMyEntity CreateFromObjectBuilderAndAdd(MyObjectBuilder_CubeGrid b){
    Last=b;if(Fail)return null;Creates++;
    var g=new MyCubeGrid{EntityId=++next,WorldMatrix=b.PositionAndOrientation.World,DestructibleBlocks=b.DestructibleBlocks,Editable=b.Editable};
    All[g.EntityId]=g;return g;
   }
  }
 }
'''
harness = r'''
 class CoreHazards {
  internal const float SupercriticalHeat=1.25f,CriticalDurationSeconds=60;
  static CoreHazards instance;internal List<CoreHazard> cores=new List<CoreHazard>();bool ready=true;int tick;
  public static CoreHazards Reset(){instance=new CoreHazards();MyAPIGateway.Entities.All.Clear();MyAPIGateway.Entities.Fail=false;MyAPIGateway.Entities.Creates=0;MyExplosions.Blasts.Clear();MyExplosions.Allowed=true;MyAPIGateway.Multiplayer.IsServer=true;return instance;}
  void Broadcast(){}void DrawCores(){}
''' + hazard_methods + r'''
 }
 class Reactor {
  MyCubeBlock Entity=new MyCubeBlock();MyCubeBlock reactor{get{return Entity;}}
  long Id{get{return Entity.EntityId;}}bool IsLive{get{return !Entity.Closed && !Entity.MarkedForClose;}}
  MotionState Motion=new MotionState();bool receivedState=true,intactControllers=true;int overheatDamageTick,spent,published,initializationFrames;
  Dictionary<string,Matrix> restPoses=new Dictionary<string,Matrix>{{"BlastShield6",Matrix.Identity},{"VentHatch4",Matrix.Identity}};
  void RefreshVentRoute(){}
  const float ContainmentMW=1;const double ReserveCapacityMJ=90;int reloadPowerFrames;
  bool CanPrepareContainment{get{return false;}}
  readonly List<ContainmentController> powerControllers=new List<ContainmentController>();
  bool thermalStartRequested,ThermalVariant;bool CanOperate{get{return reactor.IsFunctional;}}
  const double ThermalHeatMW=5000;const float CooldownHeat=.15f;int controllerRingCapacity=4,appearanceRefresh,networkTick;
  const int PlasmaStartTick=1038;Random ejectRandom=new Random(1);
  Matrix Rest(string name){var m=Matrix.Identity;m.Translation=name=="Plasma"?AnimationGeometry.Center:Vector3.Zero;return m;}
  Matrix MaintenancePose(TilePose tile,Matrix pose){return pose;}
  void RefreshFuelCapacity(){}void SaveMotion(){}void PublishMotion(){published++;}
  bool HasUsableFuel(){return true;}bool PrepareTiles(){return true;}void UpdateStatus(){}
  void UpdateThermal(){}void DrawMotion(){}void DrawVentOutlet(){}
  void SpawnSpent(string subtype,MatrixD world,float scatter){spent++;}
''' + reactor_methods + r'''
  static int checks;
  static void Need(bool ok,string message){checks++;if(!ok)throw new Exception(message);}
  static void Near(double a,double b,string message){Need(Math.Abs(a-b)<.0001,message+": "+a+" != "+b);}
  static Reactor Running(float heat=1.25f){
   var r=new Reactor();r.Entity.EntityId=1;r.Entity.WorldMatrix=MatrixD.CreateTranslation(100,200,300);
   r.Entity.GameLogic.Component=r;MyAPIGateway.Entities.All[1]=r.Entity;
   r.Entity.CubeGrid.Physics.LinearVelocity=new Vector3(7,0,0);
   r.Motion.Core=CorePhase.Running;r.Motion.CoreTick=1170;r.Motion.Heat=heat;r.Motion.RingCount=4;r.Motion.InstalledTiles=80;
   return r;
  }
  bool HasIntactControllers(){return intactControllers;}
  void ReadyVent(){
   Motion.Vent=VentPhase.Ejecting;Motion.VentHadPayload=true;Motion.VentReady=true;Motion.VentOutletId=2;Motion.EjectTick=119;
   MyAPIGateway.Entities.All[2]=new MyEntity{EntityId=2,WorldMatrix=Entity.WorldMatrix};
  }
  static void Ejection(){
   var client=CoreHazards.Reset();var remote=Running();remote.ReadyVent();MyAPIGateway.Multiplayer.IsServer=false;remote.UpdateMotion();
   Need(client.cores.Count==0 && MyAPIGateway.Entities.Creates==0 && !remote.Motion.PayloadReleased,"client simulation cannot create or transfer physical cores");
   var session=CoreHazards.Reset();var r=Running();r.ReadyVent();r.UpdateCriticalCore();var core=CoreHazards.Inside(1);core.Fuse=42;
   MyAPIGateway.Entities.Fail=true;r.TryReleasePayload();
   Need(!r.Motion.PayloadReleased && r.Motion.InstalledTiles==80 && core.CarrierId==0 && session.cores.Count==1,"failed creation preserves contained payload, inventory and hazard");
   MyAPIGateway.Entities.Fail=false;r.TryReleasePayload();
   Need(r.Motion.PayloadReleased && !r.Motion.Critical && r.Motion.Heat==0 && r.Motion.InstalledTiles==0,"successful handoff clears contained state once");
   Need(core.CarrierId!=0 && CoreHazards.Inside(1)==null && session.cores.Count==1,"handoff transfers the same hazard without duplication");
   Need(core.Shell.Count==84 && r.spent==0,"critical rings and eighty tiles stay attached; no debris is spawned");
   Need(!MyAPIGateway.Entities.Last.DestructibleBlocks && !MyAPIGateway.Entities.Last.Editable,"critical carrier resists damage and grinding");
   Near(core.Fuse,42,"ejection preserves remaining fuse");
   var world=MyAPIGateway.Entities.All[core.CarrierId].WorldMatrix;
   var expected=r.WorldPose(r.PayloadRingPose(0,1170));
   Matrix local=core.Shell[0].Pose;MatrixD attached=(MatrixD)local*world;
   Need(Vector3D.Distance(attached.Translation,expected.Translation)<.0001,"attached ring retains its exact handoff pose");
   int count=MyAPIGateway.Entities.Creates;r.TryReleasePayload();r.UpdateCriticalCore();Need(MyAPIGateway.Entities.Creates==count && session.cores.Count==1,"repeated handoff cannot duplicate or rearm");
   int hazards;Near(CoreHazards.EjectedCountdown(1,out hazards),42,"ejected countdown uses actual remaining time");core.Fuse=55;Near(CoreHazards.EjectedCountdown(1,out hazards),55,"new sixty-second fuses are not capped at forty-five");
   var serializer=new XmlSerializer(typeof(CoreHazard));var writer=new StringWriter();serializer.Serialize(writer,core);
   var restored=(CoreHazard)serializer.Deserialize(new StringReader(writer.ToString()));
   Need(restored.Shell.Count==84 && restored.CarrierId==core.CarrierId && restored.Critical,"reload retains physical identity and intact shell");Near(restored.Fuse,55,"reload preserves fuse");
   var wire=ProtoBuf.Meta.RuntimeTypeModel.Create();
   using(var buffer=new MemoryStream()){
    wire.Serialize(buffer,core);buffer.Position=0;restored=(CoreHazard)wire.Deserialize(buffer,null,typeof(CoreHazard));
    Need(restored.Shell.Count==84 && restored.Shell[0].Pose==core.Shell[0].Pose,"multiplayer snapshots preserve intact shell geometry");
    Need(restored.Rotation==core.Rotation && restored.Spin==core.Spin,"multiplayer snapshots preserve physical rotation and spin");
   }
   session=CoreHazards.Reset();r=Running(.8f);r.ReadyVent();
   MyAPIGateway.Entities.Fail=true;r.TryReleasePayload();
   Need(!r.Motion.PayloadReleased && r.Motion.InstalledTiles==80 && r.spent==0 && session.cores.Count==0,"failed subcritical launch retains the entire payload for retry");
   MyAPIGateway.Entities.Fail=false;r.TryReleasePayload();
   Need(!session.cores[0].Critical && session.cores[0].Shell.Count==84 && r.spent==0,"subcritical vent ejection keeps all tiles and rings attached to the ball");
   Need(r.Motion.PayloadReleased && r.Motion.InstalledTiles==0,"subcritical launch transfers tile stock once");
   count=MyAPIGateway.Entities.Creates;r.TryReleasePayload();
   Need(MyAPIGateway.Entities.Creates==count && session.cores.Count==1 && r.spent==0,"repeated subcritical launch cannot duplicate the ball or shell");
   var ordinary=session.cores[0];ordinary.Decay=.001f;session.UpdateBeforeSimulation();
   Need(session.cores.Count==0 && MyExplosions.Blasts.Count==0 && MyAPIGateway.Entities.All[ordinary.CarrierId].Closed,"subcritical core decays without an explosion");
   session=CoreHazards.Reset();r=Running(.8f);r.Motion.CoreTick=354;r.ReadyVent();r.TryReleasePayload();
   Need(session.cores.Count==0 && r.Motion.PayloadReleased && r.spent==8,"before plasma forms, venting ejects four rings and only the first latched tile quartet as debris");
  }
  static void Tracking(){
   var session=CoreHazards.Reset();var r=Running();r.ReadyVent();r.UpdateCriticalCore();r.TryReleasePayload();var core=session.cores[0];
   var carrier=(MyCubeGrid)MyAPIGateway.Entities.All[core.CarrierId];carrier.WorldMatrix=MatrixD.CreateTranslation(-900,40,75);core.Fuse=0;
   MyExplosions.Allowed=false;session.UpdateBeforeSimulation();
   Need(session.cores.Count==1 && !carrier.Closed,"refused explosion retains armed carrier for retry");
   MyExplosions.Allowed=true;session.UpdateBeforeSimulation();
   Need(session.cores.Count==0 && carrier.Closed && MyExplosions.Blasts.Count==1,"detonation consumes one carrier and one hazard");
   var blast=MyExplosions.Blasts[0];Need(blast.Sphere.Center==carrier.WorldMatrix.Translation,"blast follows moved core, not reactor");
   Need(blast.OriginEntity==0 && blast.OwnerEntity==r.Entity,"source attribution cannot exclude the source grid from explosion damage");
   session=CoreHazards.Reset();r=Running();r.ReadyVent();r.UpdateCriticalCore();r.TryReleasePayload();core=session.cores[0];
   carrier=(MyCubeGrid)MyAPIGateway.Entities.All[core.CarrierId];carrier.WorldMatrix=MatrixD.CreateTranslation(-4,5,6);carrier.Physics.LinearVelocity=new Vector3(4,3,2);session.UpdateBeforeSimulation();
   long old=core.CarrierId;float fuse=core.Fuse;carrier.Close();session.UpdateBeforeSimulation();
   Need(core.CarrierId!=old && session.cores.Count==1 && core.Shell.Count==84,"carrier cleanup restores one intact moving core");
   Need(core.Position==new Vector3D(-4,5,6) && core.Velocity==new Vector3(4,3,2),"recovery preserves last pose and velocity");Near(core.Fuse,fuse-1f/60,"recovery cannot reset the fuse");
   carrier=(MyCubeGrid)MyAPIGateway.Entities.All[core.CarrierId];carrier.DestructibleBlocks=true;carrier.Editable=true;session.UpdateBeforeSimulation();
   Need(!carrier.DestructibleBlocks && !carrier.Editable,"legacy physical carriers gain critical protection");
   session=CoreHazards.Reset();r=Running();r.UpdateCriticalCore();core=session.cores[0];r.Entity.Close();session.UpdateBeforeSimulation();
   Need(core.CarrierId!=0 && session.cores.Count==1,"destroying housing materializes its armed orphan core");
   core.Fuse=0;session.UpdateBeforeSimulation();Need(MyExplosions.Blasts.Count==1,"orphan retains its countdown and explosion");
   session=CoreHazards.Reset();r=Running();r.UpdateCriticalCore();core=session.cores[0];core.Fuse=0;r.Entity.Close();session.UpdateBeforeSimulation();
   Need(((MyCubeGrid)MyAPIGateway.Entities.All[core.CarrierId]).Closed,"same-frame orphan creation and detonation leave no immortal carrier");
  }
  static void Damage(){
   var session=CoreHazards.Reset();var r=Running(1);var module=new MyCubeBlock{CubeGrid=r.reactor.CubeGrid};module.GameLogic.Component=new ContainmentController();
   r.Entity.CurrentAttachedUpgradeModules[0]=new Attachment{Block=module};
   r.Entity.CurrentAttachedUpgradeModules[1]=new Attachment{Block=module};
   var unrelated=new MyCubeBlock{CubeGrid=r.reactor.CubeGrid};r.Entity.CurrentAttachedUpgradeModules[2]=new Attachment{Block=unrelated};
   foreach(float heat in new[]{0f,1f,1.1f,1.2f,1.2499f}){
    r.Motion.Heat=heat;for(int i=0;i<120;i++)r.ApplyOverheatDamage();
    Need(r.reactor.SlimBlock.Hits==0 && module.SlimBlock.Hits==0,"no heat damage below 125 percent");
   }
   r.Motion.Heat=1.25f;for(int i=0;i<59;i++)r.ApplyOverheatDamage();
   r.Motion.Heat=1.2499f;r.ApplyOverheatDamage();
   r.Motion.Heat=1.25f;for(int i=0;i<59;i++)r.ApplyOverheatDamage();
   Need(r.reactor.SlimBlock.Hits==0,"falling below 125 percent resets the damage interval");
   r.ApplyOverheatDamage();
   Near(r.reactor.SlimBlock.Integrity,999.6625,"125 percent heat damages vessel 0.03375 percent per second");Near(module.SlimBlock.Integrity,985,"125 percent heat damages controllers one and a half percent per second");
   Need(module.SlimBlock.Hits==1 && unrelated.SlimBlock.Hits==0,"duplicate sockets do not multiply damage and unrelated modules are untouched");
   r.Motion.Heat=2;for(int i=0;i<60;i++)r.ApplyOverheatDamage();Near(r.reactor.SlimBlock.Integrity,998.3125,"damage rate increases with excess heat");Near(module.SlimBlock.Integrity,925,"controller damage also increases");
   MyAPIGateway.Multiplayer.IsServer=false;for(int i=0;i<60;i++)r.ApplyOverheatDamage();Near(r.reactor.SlimBlock.Integrity,998.3125,"clients cannot apply heat damage");MyAPIGateway.Multiplayer.IsServer=true;
   r.Motion.PayloadReleased=true;for(int i=0;i<120;i++)r.ApplyOverheatDamage();Near(r.reactor.SlimBlock.Integrity,998.3125,"ejection immediately ends vessel heat damage even with stale hot telemetry");Near(module.SlimBlock.Integrity,925,"ejection ends controller damage");
   session=CoreHazards.Reset();r=Running();r.Entity.Functional=false;r.UpdateCriticalCore();var core=session.cores[0];core.Fuse=35;MyAPIGateway.Entities.Fail=true;r.TryReleaseFailedHousing();
   Need(!r.Motion.PayloadReleased && r.Motion.InstalledTiles==80 && core.CarrierId==0,"failed housing release retries without dropping its hazard or tiles");
   var tile=AnimationGeometry.Tiles[0];
   MatrixD tileWorld=r.WorldPose(r.PayloadTilePose(tile,1170,r.ContainmentRotation(1170)));
   MyAPIGateway.Entities.Fail=false;r.TryReleaseFailedHousing();
   MatrixD carriedTile=(MatrixD)core.Shell[4].Pose*MyAPIGateway.Entities.All[core.CarrierId].WorldMatrix;
   Need(Vector3D.Distance(carriedTile.Translation,tileWorld.Translation)<.0001
    && Vector3D.Distance(carriedTile.Forward,tileWorld.Forward)<.0001,"failed housing preserves tile position and orientation at handoff");
   Need(r.Motion.PayloadReleased && r.Motion.Core==CorePhase.Off && core.CarrierId!=0 && core.Shell.Count==84 && r.Motion.InstalledTiles==0 && r.spent==0,"nonfunctional vessel transfers all tiles and rings onto one physical meltdown ball without controllers or vents");
   Need(core.Velocity==new Vector3(7,0,0),"trapped ball inherits ship velocity without a launch impulse");Near(core.Fuse,35,"housing failure preserves fuse");
   int creates=MyAPIGateway.Entities.Creates;r.TryReleaseFailedHousing();Need(MyAPIGateway.Entities.Creates==creates,"failed housing cannot release twice");
   session=CoreHazards.Reset();r=Running();r.reactor.SlimBlock.Integrity=600.1f;r.UpdateCriticalCore();for(int i=0;i<60;i++)r.ApplyOverheatDamage();
   Need(r.Motion.PayloadReleased && session.cores[0].CarrierId!=0,"overheating crossing functionality materializes the core in the same update");
   session=CoreHazards.Reset();r=Running();r.ReadyVent();r.Entity.Functional=false;r.UpdateMotion();
   Need(session.cores.Count==1 && session.cores[0].Shell.Count==84 && session.cores[0].Velocity==new Vector3(7,0,0),"actual update prioritizes failed housing ball over normal vent launch");
   r.UpdateMotion();Need(session.cores.Count==1 && MyAPIGateway.Entities.Creates==1,"next update cannot rearm a failed housing after physical handoff");
  }
  static void VentTiming(){
   for(int ducts=1;ducts<=15;ducts++)foreach(var up in new[]{Vector3D.Up,Vector3D.Right,Vector3D.Forward}){
    var session=CoreHazards.Reset();var r=Running();
    r.Entity.WorldMatrix=MatrixD.CreateWorld(new Vector3D(100,200,300),up==Vector3D.Forward?Vector3D.Left:Vector3D.Forward,up);
    r.ReadyVent();r.Motion.Vent=VentPhase.ShieldClosing;r.Motion.EjectTick=0;r.Motion.ControllersReady=true;
    r.Motion.EjectionTravel=Math.Max(18,(ducts+4)*2.5f);
    var outlet=(MyEntity)MyAPIGateway.Entities.All[2];outlet.WorldMatrix=MatrixD.CreateTranslation(r.Entity.WorldMatrix.Translation+up*((ducts+2)*2.5));
    var phases=new int[7];bool released=false;int frames=0;
    while(r.Motion.Vent!=VentPhase.Idle && frames++<600){
     phases[(int)r.Motion.Vent]++;r.UpdateMotion();session.UpdateBeforeSimulation();
     if(!released && r.Motion.PayloadReleased){
      released=true;var core=session.cores[0];var carrier=MyAPIGateway.Entities.All[core.CarrierId];
      Vector3 relative=carrier.Physics.LinearVelocity-r.Entity.CubeGrid.Physics.LinearVelocity;
      Need(Vector3D.Dot(relative,up)>=22.5-.0001,"outlet applies at least 22.5 m/s along its axis for every duct length and orientation");
      Vector3D lateral=relative-up*Vector3D.Dot(relative,up);
      Need(lateral.Length()<=Math.Sqrt(2)*.4+.0001,"launch scatter is halved while ship velocity is inherited in full");
      double travelSpeed=VentSpeed*r.Motion.EjectionTravel*(r.Motion.EjectTick+r.Motion.EjectSubtick)/120;
      Near(Vector3D.Dot(relative,up),Math.Max(45,travelSpeed)*.5,"physical launch halves the previous impulse for every duct length and orientation");
      double clear=Vector3D.Dot(carrier.WorldMatrix.Translation-outlet.WorldMatrix.Translation,up);
      Need(clear>3,"physical handoff remains beyond the outlet and full hoop radius");
      Need(frames<=302 && core.Critical && core.Fuse>54.9,"faster ejection transfers the armed core within five seconds without speeding its fuse");
     }
    }
    Need(released && frames>=520 && frames<=524,"complete vent cycle runs at 1.5x speed, about 8.7 seconds");
    Need(phases[(int)VentPhase.Ejecting]==80,"scripted ejection takes eighty simulation frames");
    Need(r.Motion.EjectTick==0 && r.Motion.EjectSubtick==0,"finished cycle clears both parts of the launch clock");
   }
   CoreHazards.Reset();var held=Running();held.ReadyVent();held.Motion.PayloadReleased=false;
   held.AdvanceMotion();Need(held.Motion.EjectTick==120 && held.Motion.Vent==VentPhase.Ejecting,"outlet waits at its final pose until physical release succeeds");
   held.AdvanceMotion();Need(held.Motion.EjectTick==120 && held.Motion.Vent==VentPhase.Ejecting,"retry cannot run past the end of the launch trajectory");
   var serializer=new XmlSerializer(typeof(MotionState));
   var legacy=(MotionState)serializer.Deserialize(new StringReader("<MotionState><EjectTick>45</EjectTick></MotionState>"));
   Need(legacy.EjectTick==45 && legacy.EjectSubtick==0,"old mid-ejection saves preserve their authored launch position");
   legacy.EjectSubtick=.5f;var writer=new StringWriter();serializer.Serialize(writer,legacy);
   var restored=(MotionState)serializer.Deserialize(new StringReader(writer.ToString()));
   Near(restored.EjectTick+restored.EjectSubtick,45.5,"reload preserves fractional ejection progress");
  }
  static void ReserveEjection(){
   foreach(bool failDuringLaunch in new[]{false,true}){
    var session=CoreHazards.Reset();var r=Running();r.ReadyVent();r.Motion.Vent=VentPhase.Idle;r.Motion.EjectTick=0;
    r.intactControllers=failDuringLaunch;r.Motion.ControllersReady=failDuringLaunch;r.Motion.ReserveMJ=90;
    Need(r.CanStartVent,"toolbar can start emergency vent on reserve with failed controllers");r.RequestVent(true);
    int frames=0;bool released=false;
    while(r.Motion.Vent!=VentPhase.Idle && frames++<600){
     if(frames==50){r.intactControllers=false;r.Motion.ControllersReady=false;}
     r.UpdatePower();r.UpdateMotion();session.UpdateBeforeSimulation();
     if(!released && r.Motion.PayloadReleased){
      released=true;Need(!r.Motion.ControllersReady && session.cores.Count==1 && session.cores[0].Shell.Count==84,"physical release succeeds with failed controllers and retains tiles and rings");
      Need(r.Motion.ReserveMJ<90 && r.Motion.ReserveMJ>80,"emergency launch consumes real stored reserve");
      Need(session.cores[0].Fuse>54,"reserve ejection preserves the critical countdown");
     }
    }
    Need(released && frames<600 && r.Motion.Shield==0 && r.Motion.Intake==0,"reserve drives the entire vent cycle after controller failure");
   }
   CoreHazards.Reset();var stopped=Running();stopped.ReadyVent();stopped.intactControllers=false;stopped.Motion.ControllersReady=false;stopped.Motion.ReserveMJ=0;
   stopped.UpdatePower();stopped.UpdateMotion();
   Need(stopped.Motion.PowerPaused && !stopped.Motion.PayloadReleased && MyAPIGateway.Entities.Creates==0,"exhausted reserve blocks motion and physical release even at the outlet");
   stopped.Motion.ReserveMJ=10;stopped.Motion.VentReady=false;stopped.UpdatePower();stopped.UpdateMotion();
   Need(!stopped.Motion.PayloadReleased,"reserve cannot bypass a broken vent route");
   stopped.Motion.VentReady=true;stopped.UpdatePower();stopped.UpdateMotion();
   Need(stopped.Motion.PayloadReleased && MyAPIGateway.Entities.Creates==1,"restored power and route resume a single handoff without controller repair");
   CoreHazards.Reset();stopped=Running();stopped.Motion.VentReady=true;stopped.intactControllers=false;stopped.Motion.ControllersReady=false;
   Need(!stopped.CanStartVent,"toolbar rejects failed controllers without reserve");stopped.RequestVent(true);
   Need(stopped.Motion.Vent==VentPhase.Idle,"server rejects an unpowered emergency start");
  }
  static void HousingLifetime(){
   var session=CoreHazards.Reset();var r=Running();var vessel=r.reactor.SlimBlock;
   vessel.Maximum=vessel.Integrity=HOUSING_MAXIMUM;vessel.FunctionalCutoff=HOUSING_CUTOFF;
   r.UpdateCriticalCore();var core=session.cores[0];int releaseFrame=0;
   for(int frame=1;frame<=3601;frame++){
    if(!r.Motion.PayloadReleased){
     r.Motion.Heat=(float)ThermalMath.ApproachCoreHeat(r.Motion.Heat,4,true);
     r.UpdateCriticalCore();r.ApplyOverheatDamage();
     if(r.Motion.PayloadReleased)releaseFrame=frame;
    }
    session.UpdateBeforeSimulation();
    if(frame==44*60)Need(r.reactor.IsFunctional && !r.Motion.PayloadReleased,"full-integrity housing remains functional through 44 supercritical seconds");
    if(frame==45*60){
     Need(releaseFrame==45*60 && !r.reactor.IsFunctional,"housing becomes nonfunctional at 45 seconds with shipped component integrity");
     Need(core.CarrierId!=0 && core.Shell.Count==84 && MyExplosions.Blasts.Count==0,"45-second failure transfers the intact core before detonation");
     Need(Math.Abs(core.Fuse-15)<.01,"housing failure leaves fifteen seconds on the original fuse");
    }
    if(frame==59*60)Need(MyExplosions.Blasts.Count==0,"housing failure does not accelerate detonation");
   }
   Need(MyExplosions.Blasts.Count==1 && session.cores.Count==0,"core still explodes once at sixty seconds");
  }
  static void ShieldTests(){
   foreach(bool running in new[]{false,true}){
    var session=CoreHazards.Reset();var r=Running(.8f);r.Motion.ControllersReady=true;r.Motion.VentReady=running;
    if(!running){r.Motion.Core=CorePhase.Off;r.reactor.Enabled=false;}
    r.RequestVentShieldTest();Need(r.Motion.ShieldTest==ShieldTestPhase.Lowering,"shield test starts even without a vent route on an idle reactor");
    int frames=0;float peak=0;
    while(r.Motion.ShieldTest!=ShieldTestPhase.Idle && frames++<400){
     r.UpdateMotion();peak=Math.Max(peak,r.Motion.Shield);
     Need(r.Motion.Intake==0 && r.Motion.Vent==VentPhase.Idle && r.Motion.EjectTick==0,"dry run never opens the hatch or enters ejection");
     Need(!r.Motion.PayloadReleased && r.Motion.InstalledTiles==80 && r.spent==0 && session.cores.Count==0,"dry run retains the payload without spawning a ball or debris");
     Need(r.reactor.Enabled==running && r.Motion.Core==(running?CorePhase.Running:CorePhase.Off),"dry run preserves reactor operation");
     if(frames==80){
      float shield=r.Motion.Shield;r.RequestVentShieldTest();Near(r.Motion.Shield,shield,"repeated test request cannot restart active motion");
      var xml=new XmlSerializer(typeof(MotionState));var writer=new StringWriter();xml.Serialize(writer,r.Motion);
      r.Motion=(MotionState)xml.Deserialize(new StringReader(writer.ToString()));
      Need(r.Motion.ShieldTest==ShieldTestPhase.Lowering,"save/reload preserves the dry-run phase");
      var wire=ProtoBuf.Meta.RuntimeTypeModel.Create();using(var buffer=new MemoryStream()){
       wire.Serialize(buffer,r.Motion);buffer.Position=0;r.Motion=(MotionState)wire.Deserialize(buffer,null,typeof(MotionState));
      }
      Need(r.Motion.ShieldTest==ShieldTestPhase.Lowering,"multiplayer preserves the dry-run phase");Near(r.Motion.Shield,shield,"reload/sync preserves shield position");
      r.Motion.PowerPaused=true;r.UpdateMotion();Near(r.Motion.Shield,shield,"loss of containment power pauses the shield test");r.Motion.PowerPaused=false;
      r.Motion.ControllersReady=false;r.UpdateMotion();Near(r.Motion.Shield,shield,"loss of controllers pauses the shield test");r.Motion.ControllersReady=true;
     }
    }
    Need(frames>=320 && frames<=324 && peak==1 && r.Motion.Shield==0,"dry run fully lowers then retracts shields at the existing speed");
   }
   CoreHazards.Reset();var blocked=Running(.8f);blocked.Motion.ControllersReady=true;
   MyAPIGateway.Multiplayer.IsServer=false;blocked.RequestVentShieldTest();Need(blocked.Motion.ShieldTest==ShieldTestPhase.Idle,"clients cannot start a shield test directly");MyAPIGateway.Multiplayer.IsServer=true;
   blocked.intactControllers=false;blocked.RequestVentShieldTest();Need(blocked.Motion.ShieldTest==ShieldTestPhase.Idle,"server rechecks actual controllers");blocked.intactControllers=true;
   blocked.Motion.Critical=true;blocked.RequestVentShieldTest();Need(blocked.Motion.ShieldTest==ShieldTestPhase.Idle,"critical core rejects a new dry run");blocked.Motion.Critical=false;
   blocked.Motion.Intake=.5f;blocked.RequestVentShieldTest();Need(blocked.Motion.ShieldTest==ShieldTestPhase.Idle,"open hatch rejects a dry run");blocked.Motion.Intake=0;
   blocked.RequestVentShieldTest();for(int i=0;i<80;i++)blocked.UpdateMotion();float partial=blocked.Motion.Shield;
   blocked.Motion.VentReady=true;blocked.RequestVent(true);
   Need(blocked.Motion.ShieldTest==ShieldTestPhase.Idle && blocked.Motion.Vent==VentPhase.ShieldClosing,"real ejection preempts the dry run");Near(blocked.Motion.Shield,partial,"emergency handoff preserves shield position");
   blocked.RequestVentShieldTest();Need(blocked.Motion.ShieldTest==ShieldTestPhase.Idle,"dry run cannot interrupt committed ejection");
  }
  static void Main(){Ejection();Tracking();Damage();VentTiming();ReserveEjection();HousingLifetime();ShieldTests();Console.WriteLine("PASS: "+checks+" production meltdown ownership, shield dry run, vent timing/impulse, shell, damage, recovery, save and explosion checks");}
 }
}
'''

with tempfile.TemporaryDirectory(prefix='arcane-meltdown-') as directory:
    path = Path(directory) / 'check.cs'
    path.write_text(stubs + types + state + harness.replace('HOUSING_MAXIMUM', str(housing_integrity) + 'f').replace('HOUSING_CUTOFF', str(housing_cutoff) + 'f'))
    exe = path.with_suffix('.exe')
    # Native Matrix conversions use readonly ref parameters. Roslyn handles their
    # metadata correctly; mcs emits invalid IL for these conversions.
    sdk = subprocess.check_output(['dotnet', '--list-sdks'], text=True).splitlines()[-1]
    version, location = sdk.split(' ', 1)
    compiler = Path(location.strip('[]')) / version / 'Roslyn/bincore/csc.dll'
    subprocess.run(['dotnet', str(compiler), '-nologo', '-nostdlib+', '-langversion:6', '-warn:0', '-out:' + str(exe),
                    *['-r:/usr/lib/mono/4.5/' + name + '.dll' for name in ('mscorlib', 'System', 'System.Core', 'System.Xml')],
                    '-r:/usr/lib/mono/4.5/Facades/netstandard.dll',
                    *['-r:' + str(GAME / name) for name in ('VRage.Math.dll', 'VRage.Library.dll', 'ProtoBuf.Net.dll', 'ProtoBuf.Net.Core.dll')],
                    str(path), str(SRC / 'AnimationGeometry.cs'), str(SRC / 'RingMotion.cs')], check=True)
    subprocess.run(['mono', str(exe)], check=True, env={**os.environ, 'MONO_PATH': str(GAME)})
