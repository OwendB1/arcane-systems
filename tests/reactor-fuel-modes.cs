// Engine doubles for check_reactor_fuel_modes.py. Production members are injected.
using System;
using System.Collections.Generic;
using VRage;
using VRageMath;
using ArcanePower;
using VRage.Utils;
using IMyTerminalBlock = Block;
using IMyReactor = ReactorBlock;
namespace ProtoBuf {
 public class ProtoContractAttribute : Attribute {}
 public class ProtoMemberAttribute : Attribute { public bool OverwriteList; public ProtoMemberAttribute(int id){} }
}
namespace ArcanePower {
 public class ThermalRotorState { public bool Valid(long id){return true;} }
 public class ThermalRadiatorState { public int RequiredPanels;public bool Valid(long id){return true;} }
}
class Grid {
 public long EntityId=1;
 public object Physics=new object();
 public Dictionary<Vector3I,Slim> Cells=new Dictionary<Vector3I,Slim>();
 public Vector3I WorldToGridInteger(Vector3D point){return Vector3I.Round(point/2.5);}
 public Slim GetCubeBlock(Vector3I cell){Slim block;return Cells.TryGetValue(cell,out block)?block:null;}
}
class Definition { public string SubtypeName; public object[] FuelInfos=new object[0]; public float MaxPowerOutput=19500; }
class ComponentStack {
 public bool IsFunctional=true;
 public event Action IsFunctionalChanged;
 public void SetFunctional(bool value){if(IsFunctional==value)return;IsFunctional=value;if(IsFunctionalChanged!=null)IsFunctionalChanged();}
}
class Slim { public float BuildLevelRatio=1; public Block FatBlock; public ComponentStack ComponentStack=new ComponentStack(); }
class Logic { public object Component=new ContainmentController(); public T GetAs<T>() where T:class{return Component as T;} }
class ContainmentController {
 public float Input,Requested;
 public float Request(long id,float demand){Requested=demand;return Input;}
}
class Block {
 public long EntityId,OwnerId;
 public Grid CubeGrid;
 public bool Closed,MarkedForClose,HasInventory=true,Accessible=true;
 public bool IsFunctional {get{return SlimBlock.ComponentStack.IsFunctional;}set{SlimBlock.ComponentStack.SetFunctional(value);}}
 bool enabled=true;
 public bool Enabled {get{return enabled;}set{if(enabled==value)return;enabled=value;if(EnabledChanged!=null)EnabledChanged(this);}}
 public event Action<Block> EnabledChanged;
 public event Action<Block> IsWorkingChanged;
 public void PowerChanged(){if(IsWorkingChanged!=null)IsWorkingChanged(this);}
 public MatrixD WorldMatrix=MatrixD.Identity;
 public int InventoryCount=1;
 public Slim SlimBlock=new Slim();
 public Definition BlockDefinition=new Definition();
 public Logic GameLogic=new Logic();
 public Inventory Inventory=new Inventory();
 public Inventory GetInventory(int index=0){return Inventory;}
 public bool HasPlayerAccess(long owner){return Accessible;}
}
class Attachment { public bool Compatible=true; public Block Block; }
class MyCubeBlock : Block { public Dictionary<int,Attachment> CurrentAttachedUpgradeModules=new Dictionary<int,Attachment>(); }
class ReactorBlock : MyCubeBlock {
 public bool UseConveyorSystem;
 public float CurrentOutput,Capacity,PowerOutputMultiplier=1;
 public Dictionary<string,float> UpgradeValues=new Dictionary<string,float>();
 public void RefreshCustomInfo(){}
}
class NativeReactor { public float Capacity; }
class MyObjectBuilder_Ingot { public string SubtypeName; }
class MyObjectBuilder_Component { public string SubtypeName; }
class MyDefinitionId {public MyDefinitionId(Type t,string name){}}
namespace VRage.Utils {public class MyLog {public static MyLog Default=new MyLog();public void WriteLineAndConsole(string message){}}}
struct MyItemType {
 public string Id;
 public static MyItemType MakeComponent(string id){return new MyItemType{Id=id};}
 public static MyItemType MakeIngot(string id){return new MyItemType{Id=id};}
 public static bool operator ==(MyItemType a,MyItemType b){return a.Id==b.Id;}
 public static bool operator !=(MyItemType a,MyItemType b){return a.Id!=b.Id;}
 public override bool Equals(object o){return o is MyItemType && this==(MyItemType)o;}
 public override int GetHashCode(){return Id.GetHashCode();}
}
struct MyInventoryItem { public MyItemType Type; public MyFixedPoint Amount; }
class Inventory {
 public Dictionary<string,MyFixedPoint> Stock=new Dictionary<string,MyFixedPoint>();
 public bool Reachable=true,Room=true,RejectAdd;
 public bool CanItemsBeAdded(MyFixedPoint n,MyDefinitionId id){return Room;}
 public void AddItems(MyFixedPoint n,MyObjectBuilder_Component item){if(!RejectAdd && Room)Stock[item.SubtypeName]=GetItemAmount(MyItemType.MakeComponent(item.SubtypeName))+n;}
 public MyFixedPoint GetItemAmount(MyItemType type){MyFixedPoint n;return Stock.TryGetValue(type.Id,out n)?n:(MyFixedPoint)0;}
 public void RemoveItemsOfType(MyFixedPoint n,MyObjectBuilder_Ingot type){Stock[type.SubtypeName]-=n;}
 public bool CanTransferItemTo(Inventory target,MyItemType type){return Reachable && target.Reachable;}
 public void GetItems(List<MyInventoryItem> items,Func<MyInventoryItem,bool> filter){
  foreach(var pair in Stock){var item=new MyInventoryItem{Type=MyItemType.MakeIngot(pair.Key),Amount=pair.Value};if(filter(item))items.Add(item);}
 }
 public void TransferItemFrom(Inventory source,MyInventoryItem item){TransferItemFrom(source,item,item.Amount);}
 public void TransferItemFrom(Inventory source,MyInventoryItem item,MyFixedPoint amount){
  if(!Room || !source.CanTransferItemTo(this,item.Type))return;
  source.Stock[item.Type.Id]-=amount;Stock[item.Type.Id]=GetItemAmount(item.Type)+amount;
 }
}
class Terminal {
 public List<Block> Blocks=new List<Block>();
 public void GetBlocksOfType<T>(List<T> list,Func<T,bool> filter) where T:class {
  foreach(var block in Blocks){var b=block as T;if(b!=null && filter(b))list.Add(b);}
 }
}
static class MyAPIGateway {
 public static class Multiplayer {public static bool IsServer=true;}
 public static class Session {public static bool CreativeMode;public static int GameplayFrameCounter;}
 public static class Utilities {public static bool IsDedicated=true;}
 public static class TerminalActionsHelper {
  public static Terminal Terminal=new Terminal();
  public static Terminal GetTerminalSystemForGrid(object grid){return Terminal;}
 }
}
static class ThermalManifolds {
 public static string[] Parts=new string[0];
 public static string Name(int bay,string part){return part;}
 public static int Pose(int bay,string part,float deployment){return 0;}
}
static class ThermalRadiators {
 public const int MaxPanels=3;
 // PRODUCTION_RADIATOR_FIT
}
// PRODUCTION_STATE
class Reactor {
 double reservedThermalMJ; ThermalOutputGrant standaloneGrant;
 internal ReactorBlock reactor=new ReactorBlock();
 internal ReactorBlock Block {get{return reactor;}}
 internal ThermalEndpoint CircuitEndpoint;
 internal ThermalEndpoint ThermalEndpoint(){return CircuitEndpoint;}
 MyCubeBlock Entity;
 NativeReactor nativeReactor=new NativeReactor();
 internal MotionState Motion=new MotionState{Thermal=new ThermalReactorState()};
 int controllerRingCapacity=4,initializationFrames,networkTick=1,appearanceRefresh;
 int controllerDiscoveryFrames=600,reloadPowerFrames,criticalChecks;
 float previousControllers=2;
 bool restoreLegacyHardware,thermalStartRequested;
 bool IsLive=true,ThermalVariant=true,motionInitialized=true,thermalRestoreFault,CanOperate=true,ManifoldRigReady=true;
 List<IMyTerminalBlock> fuelSources=new List<IMyTerminalBlock>();
 List<MyInventoryItem> transferItems=new List<MyInventoryItem>();
 readonly List<ContainmentController> powerControllers=new List<ContainmentController>();
 const float CooldownHeat=.15f;
 internal long Id=1;
 int publications;
 static bool ValidTileGrades(int[] grades){return grades!=null && grades.Length==20;}
 void PublishMotion(){publications++;}
 void Part(string name,int pose){}
 void PullTiles(Inventory source,Inventory target){}
 void RefreshRestPoses(){} void DrawMotion(){} void DrawVentOutlet(){}
 void UpdateAppearance(){} void UpdateSound(){} void UpdateTiles(){}
 void UpdateCriticalCore(){criticalChecks++;}
 void CheckVentRoute(){if(initializationFrames==0 && !CanOperate)reactor.Enabled=false;}
 void UpdateSafety(){Motion.ControllersReady=HasIntactControllers();}
 void UpdateMotion(){if(!reactor.Enabled)BeginShutdown();}
 // PRODUCTION_MEMBERS
 static int checks;
 static void Need(bool value,string message){checks++;if(!value)throw new Exception(message);}
 static void Near(double actual,double expected,string message){Need(Math.Abs(actual-expected)<1e-7*Math.Max(1,Math.Abs(expected)),message+": "+actual+" != "+expected);}
 Reactor(){Entity=reactor;reactor.CubeGrid=new Grid();Motion.RingCount=4;Controllers(true);reactor.EnabledChanged+=ThermalEnabledChanged;}
 void Controllers(bool advanced){
  Entity.CurrentAttachedUpgradeModules.Clear();
  for(int i=0;i<2;i++)Entity.CurrentAttachedUpgradeModules[i]=new Attachment{Block=new Block{EntityId=i+2,CubeGrid=reactor.CubeGrid}};
  Entity.CurrentAttachedUpgradeModules[0].Block.BlockDefinition.SubtypeName=advanced?"ArcanePower_AdvancedContainmentController":"ArcanePower_ContainmentController";
  reactor.UpgradeValues["ArcaneControllerCount"]=2;reactor.UpgradeValues["ArcaneContainment"]=4;
 }
 void Supply(float mw){foreach(var entry in reactor.CurrentAttachedUpgradeModules.Values)entry.Block.GameLogic.GetAs<ContainmentController>().Input=mw/2;}
 void Mode(ThermalMode mode){Motion.Thermal.Mode=Motion.Thermal.Requested=mode;Motion.Thermal.Deployment=mode==ThermalMode.Brayton?1:0;}
 void Stock(int tier,double amount){reactor.Inventory.Stock[Fuels[tier-1]]=(MyFixedPoint)amount;}
 double Stock(int tier){return (double)reactor.Inventory.GetItemAmount(MyItemType.MakeIngot(Fuels[tier-1]));}
 void Running(){Motion.Core=CorePhase.Running;Motion.CoreTick=1170;Motion.Heat=.8f;Motion.PowerRamp=1;Motion.ReserveMJ=10000;}
 static void RebalancedRatings(){
  var r=new Reactor();
  for(int tier=1;tier<=3;tier++){
   r.Motion.FuelTier=tier;
   Near(r.ThermalHeatMW,new[]{5000.0,50000,250000}[tier-1],"fuel heat rating");
   r.Mode(ThermalMode.Brayton);
   Near(r.ElectricalRatingMW,new[]{4000.0,40000,200000}[tier-1],"Brayton native electrical ceiling");
  }
  r.Motion.FuelTier=1;r.Mode(ThermalMode.Standalone);
  Near(r.ElectricalRatingMW,500,"standalone Aether converts 5 GW fuel input into 500 MW electricity");
  Near(r.ThermalHeatMW-r.ElectricalRatingMW,4500,"standalone Aether integrated cooling handles 4.5 GW at full load");
  r.Motion.FuelTier=3;r.Mode(ThermalMode.Brayton);
  foreach(bool upgraded in new[]{false,true}){
   double expected=upgraded?50000:3500;
   var block=new ThermalBlock{Block=new Block(),Generator=new ReactorBlock(),
    Spec=new ThermalModel{Grade=upgraded?3:0,RatingMW=upgraded?62500:4375}};
   block.Generator.BlockDefinition.MaxPowerOutput=(float)expected;
   block.SetOutput(expected);
   Near(block.Generator.PowerOutputMultiplier*block.Generator.BlockDefinition.MaxPowerOutput,expected,"native theoretical turbine maximum");
   Near(block.Generator.Capacity*216000,expected,"native effective turbine maximum");
  }
  r.Running();r.BeginShutdown();Near(r.Motion.CooldownStartHeat,.8f,"shutdown captures actual starting heat");
  r.Motion.Heat=.4f;r.BeginShutdown();Near(r.Motion.CooldownStartHeat,.8f,"repeated shutdown checks preserve original progress baseline");
  var serializer=new System.Xml.Serialization.XmlSerializer(typeof(MotionState));
  var saved=new System.IO.StringWriter();serializer.Serialize(saved,r.Motion);
  var restored=(MotionState)serializer.Deserialize(new System.IO.StringReader(saved.ToString()));
  Near(restored.CooldownStartHeat,.8f,"shutdown progress baseline survives saved-world reload");
  r.Motion.EntityId=r.Id;r.Motion.Thermal.Store.EntityId=r.Id;r.Motion.ReserveMJ=0;
  r.Motion.Thermal.Store.HotMJ=1000000;
  Need(Valid(r.Motion),"pre-rebalance paid heat remains loadable");
 }
 static void ReloadInitialization(){
  var snapshot=new MotionState{EntityId=1};
  Need(Valid(snapshot),"older snapshots default to an unconfirmed forecast with unknown ETAs");
  foreach(float seconds in new[]{-2f,61f,float.NaN,float.PositiveInfinity}){
   snapshot.ForecastOverheatSeconds=seconds;Need(!Valid(snapshot),"reject invalid overheat ETA");snapshot.ForecastOverheatSeconds=-1;
   snapshot.ForecastMeltdownSeconds=seconds;Need(!Valid(snapshot),"reject invalid critical ETA");snapshot.ForecastMeltdownSeconds=-1;
  }
  foreach(float seconds in new[]{-2f,3601f,float.NaN,float.PositiveInfinity}){
   snapshot.ForecastCooldownSeconds=seconds;Need(!Valid(snapshot),"reject invalid cooldown ETA");snapshot.ForecastCooldownSeconds=-1;
  }
  foreach(float heat in new[]{-.1f,4.1f,float.NaN,float.PositiveInfinity}){
   snapshot.CooldownStartHeat=heat;Need(!Valid(snapshot),"reject invalid shutdown baseline");snapshot.CooldownStartHeat=0;
  }
  snapshot.ForecastCircuit=5;Need(!Valid(snapshot),"reject nonexistent forecast circuit");
  var r=new Reactor();r.Mode(ThermalMode.Brayton);r.Stock(2,10);r.Motion.FuelTier=2;r.Running();
  r.Motion.ReserveMJ=r.ReserveCapacityMJ;r.initializationFrames=120;
  r.Entity.CurrentAttachedUpgradeModules.Clear();r.reactor.UpgradeValues.Clear();
  for(int frame=0;frame<180;frame++){
   r.UpdateBeforeSimulation();
   Need(r.reactor.Enabled && r.Motion.Core==CorePhase.Running && !r.ThermalInitialized,"delayed native discovery preserves restored state without dispatch");
  }
  Need(r.criticalChecks==180,"critical-core tracking continues during discovery");
  r.Controllers(true);r.reactor.UpgradeValues["ArcaneControllerCount"]=1;
  r.UpdateBeforeSimulation();Need(!r.ThermalInitialized,"partial upgrade registration is not ready");
  r.reactor.UpgradeValues["ArcaneControllerCount"]=2;
  r.UpdateBeforeSimulation();Need(!r.ThermalInitialized,"controller sinks get a priming interval");
  r.UpdateBeforeSimulation();Need(!r.ThermalInitialized,"both priming ticks follow complete controller discovery");
  r.UpdateBeforeSimulation();
  Need(r.ThermalInitialized && r.reactor.Enabled && !r.Motion.PowerPaused && !r.Motion.PowerStarved,"paid reserve bridges the first restored dispatch frame");
  Near(r.Motion.ReserveMJ,r.ReserveCapacityMJ-r.ContainmentMW/60.0,"reload debits actual missing containment energy");
  r.UpdateBeforeSimulation();r.Supply(r.ContainmentMW);r.UpdateBeforeSimulation();
  Need(r.reactor.Enabled && r.reloadPowerFrames==0,"measured native input completes reload handoff");
  r.Supply(0);r.UpdateBeforeSimulation();
  Need(!r.reactor.Enabled && r.Motion.PowerStarved,"normal post-recovery power loss still shuts down immediately");
  foreach(bool staleCounts in new[]{false,true}){
   r=new Reactor();r.Mode(ThermalMode.Brayton);r.Stock(1,10);r.Running();r.initializationFrames=120;
   r.Entity.CurrentAttachedUpgradeModules.Clear();if(!staleCounts)r.reactor.UpgradeValues.Clear();
   for(int frame=0;frame<650;frame++)r.UpdateBeforeSimulation();
   Need(r.initializationFrames==0 && !r.reactor.Enabled,"missing physical controllers fail closed by bounded deadline even with stale counts");
  }
  foreach(bool critical in new[]{false,true}){
   r=new Reactor();r.Stock(1,10);r.Running();r.initializationFrames=1;
   r.Motion.Critical=critical;r.Motion.ReserveMJ=critical?r.ReserveCapacityMJ:0;
   r.UpdateBeforeSimulation();
   Need(!r.reactor.Enabled && r.Motion.PowerStarved,"empty reserve or critical core never gets a power bypass");
  }
  r=new Reactor();r.Stock(1,10);r.Running();r.initializationFrames=1;r.reactor.Enabled=false;
  r.UpdateBeforeSimulation();Need(!r.reactor.Enabled && r.reloadPowerFrames==0,"saved disabled core never auto-restarts");
  r=new Reactor();r.Stock(1,10);r.initializationFrames=1;r.UpdateBeforeSimulation();
  Need(r.Motion.Core==CorePhase.Off && r.reloadPowerFrames==0,"cold startup gets no reload allowance");
  r=new Reactor();r.Stock(1,10);r.Running();r.initializationFrames=1;r.Motion.ReserveMJ=r.ReserveCapacityMJ;
  for(int frame=0;frame<121;frame++)r.UpdateBeforeSimulation();
  Need(!r.reactor.Enabled && r.Motion.PowerStarved && r.Motion.ReserveMJ>0,"handoff deadline stops a persistent outage even with remaining reserve");
  r=new Reactor();r.Mode(ThermalMode.Brayton);r.Stock(1,10);r.Running();r.initializationFrames=1;
  r.UpdateBeforeSimulation();r.CheckLoopSafety();
  Need(!r.reactor.Enabled && !r.Motion.Thermal.LoopTrip,"reload allowance cannot bypass all-circuit loss or create a manual-start latch");
 }
 static bool TerminalEnabled(Reactor target){
  var Reactors=new Dictionary<long,Reactor>{{1,target}};
  Func<Block,bool> gate=/* TERMINAL_GATE */;
  return gate(new Block{EntityId=1});
 }
 static void FuelMatrix(){
  foreach(bool creative in new[]{false,true})foreach(ThermalMode mode in Enum.GetValues(typeof(ThermalMode)))
  foreach(bool advanced in new[]{false,true})for(int capacity=2;capacity<=4;capacity++)for(int tier=1;tier<=3;tier++){
   var r=new Reactor();r.Mode(mode);r.Controllers(advanced);r.controllerRingCapacity=capacity;r.Motion.FuelTier=tier;r.Stock(tier,10);r.Running();
   MyAPIGateway.Session.CreativeMode=creative;
   bool allowed=tier<capacity && (mode==ThermalMode.Standalone?tier==1:advanced);
   Need(r.HasUsableFuel()==allowed,"fuel eligibility matrix");Need(r.ThermalCanRun==allowed,"generation matrix");
   r.ProduceThermal(r.ThermalHeatMW);Need((r.Motion.Thermal.FuelHeatMJ>0)==allowed,"reaction admits no disallowed heat");
   r.GrantStandaloneOutput();r.RefreshFuelCapacity();Need((r.nativeReactor.Capacity>0)==(allowed && mode==ThermalMode.Standalone),"native standalone export matrix");
   r.UpdateFuel();Need(allowed || !r.reactor.Enabled,"server interlock rejects unsafe enabled state");
   Need(r.Motion.FuelTier==tier,"hot tier is latched");
  }
  MyAPIGateway.Session.CreativeMode=false;
  var mixed=new Reactor();for(int i=1;i<=3;i++)mixed.Stock(i,10);mixed.UpdateFuel();
  Need(mixed.Motion.FuelTier==1 && mixed.Stock(2)==10 && mixed.Stock(3)==10,"mixed inventory uses Aether only");
  mixed.Mode(ThermalMode.Brayton);mixed.UpdateFuel();Need(mixed.Motion.FuelTier==3,"Brayton selects highest supported stock");
  mixed.Mode(ThermalMode.Standalone);mixed.Stock(1,0);mixed.UpdateFuel();
  Need(mixed.Motion.FuelTier==1 && !mixed.HasUsableFuel(),"higher fuel alone cannot start standalone");
  Need(!mixed.CanPrepareContainment,"blocked fuel cannot charge containment");
  mixed.Motion.Thermal.Requested=ThermalMode.Brayton;
  Need(!mixed.HasUsableFuel(),"transition cannot bypass startup gate");
  foreach(ThermalMode mode in Enum.GetValues(typeof(ThermalMode))){
   var r=new Reactor();r.Mode(mode);r.reactor.UseConveyorSystem=true;r.networkTick=0;
   var cargo=new Block();for(int i=0;i<3;i++)cargo.Inventory.Stock[Fuels[i]]=(MyFixedPoint)100;
   MyAPIGateway.TerminalActionsHelper.Terminal.Blocks.Clear();MyAPIGateway.TerminalActionsHelper.Terminal.Blocks.Add(cargo);
   r.UpdateFuel();Need(r.Stock(1)==10,"conveyor supplies Aether");
   Need(r.Stock(2)==(mode==ThermalMode.Brayton?10:0) && r.Stock(3)==(mode==ThermalMode.Brayton?10:0),"conveyor follows fuel mode");
  }
 }
 static void ControllerAndCommands(){
  var r=new Reactor();r.Controllers(false);
  Need(r.HasIntactControllers() && !r.HasAdvancedController(),"two standard controllers cannot unlock Brayton");
  Need(!TerminalEnabled(r),"terminal locked without advanced controller");
  r.RequestThermalMode(ThermalMode.Brayton);Need(r.Motion.Thermal.Requested==ThermalMode.Standalone && r.reactor.Enabled,"server rejects forged Brayton request without mutating mode");
  r.Controllers(true);r.Entity.CurrentAttachedUpgradeModules.Remove(1);
  Need(r.HasAdvancedController() && !r.HasIntactControllers(),"one advanced unlocks mode but cannot operate alone");
  Need(!r.CanPrepareContainment,"both controllers still required for startup");
  Need(TerminalEnabled(r),"one advanced unlocks switch independent of aggregate ring count");
  r.RequestThermalMode(ThermalMode.Brayton);Need(r.Motion.Thermal.Requested==ThermalMode.Brayton && !r.reactor.Enabled,"advanced enables safe transition");
  foreach(Action<Reactor> damage in new Action<Reactor>[]{
   c=>c.Entity.CurrentAttachedUpgradeModules[0].Compatible=false,
   c=>c.Entity.CurrentAttachedUpgradeModules[0].Block=null,
   c=>c.Entity.CurrentAttachedUpgradeModules[0].Block.Closed=true,
   c=>c.Entity.CurrentAttachedUpgradeModules[0].Block.IsFunctional=false,
   c=>c.Entity.CurrentAttachedUpgradeModules[0].Block.SlimBlock.BuildLevelRatio=.99f,
   c=>c.Entity.CurrentAttachedUpgradeModules[0].Block.CubeGrid=new Grid(),
   c=>c.Entity.CurrentAttachedUpgradeModules[0].Block.GameLogic.Component=null,
   c=>c.Entity.CurrentAttachedUpgradeModules.Clear()}){
   r=new Reactor();damage(r);Need(!r.HasAdvancedController() && !TerminalEnabled(r),"unavailable advanced does not unlock terminal");
   r.RequestThermalMode(ThermalMode.Brayton);Need(r.Motion.Thermal.Requested==ThermalMode.Standalone,"server rejects unavailable controller");
  }
  r=new Reactor();r.ManifoldRigReady=false;r.RequestThermalMode(ThermalMode.Brayton);Need(r.Motion.Thermal.Requested==ThermalMode.Standalone,"rig gate retained");
  r=new Reactor();MyAPIGateway.Multiplayer.IsServer=false;r.RequestThermalMode(ThermalMode.Brayton);Need(r.Motion.Thermal.Requested==ThermalMode.Standalone,"client cannot change mode");MyAPIGateway.Multiplayer.IsServer=true;
  r.initializationFrames=120;r.RequestThermalMode(ThermalMode.Brayton);Need(r.Motion.Thermal.Requested==ThermalMode.Standalone && !TerminalEnabled(r),"restore barrier gates commands and UI");
 }
 static void CoolingAndAccounting(){
  var r=new Reactor();r.Mode(ThermalMode.Brayton);r.Motion.FuelTier=3;r.Stock(3,10);r.Running();r.Motion.Thermal.Store.HotMJ=1000;r.Motion.Thermal.Store.WasteMJ=400;r.Motion.Thermal.AttachedHeatMJ=300;
  r.Controllers(false);r.UpdateFuel();r.UpdateThermalMode();r.BeginShutdown();
  Need(!r.reactor.Enabled && !r.ThermalCanRun && r.Motion.Core==CorePhase.Cooling,"controller loss shuts down hot Brayton");
  Need(r.Motion.Thermal.Deployment==1 && r.Motion.Thermal.Mode==ThermalMode.Brayton,"controller loss preserves deployed cooling");
  Near(r.Motion.Thermal.Store.HotMJ+r.Motion.Thermal.Store.WasteMJ+r.Motion.Thermal.AttachedHeatMJ,1700,"controller loss retains all heat");
  Need(r.NeedsStorageSupport,"cooldown retains power support");
  Need(TerminalEnabled(r),"controller loss still permits safe exit from Brayton");
  r.RequestThermalMode(ThermalMode.Standalone);r.UpdateThermalMode();Need(r.Motion.Thermal.Deployment==1 && r.Motion.FuelTier==3,"hot transition cannot retract or change fuel");
  r.Motion.Core=CorePhase.Off;r.Motion.Heat=0;r.Motion.Thermal.Store.HotMJ=r.Motion.Thermal.Store.WasteMJ=0;r.UpdateFuel();Need(r.Motion.FuelTier==3,"attached machine heat prevents tier mutation");
  r.Motion.Thermal.AttachedHeatMJ=0;r.Motion.Thermal.FuelHeatMJ=r.ThermalHeatMW*600*r.FuelEfficiency*.1;
  r.UpdateFuel();Need(r.Motion.FuelTier==3,"pending heat charge preserves old tier");Near(r.Stock(3),9.9,"old tier pays old thermal debit");
  r.Motion.FuelDebt=.2;r.UpdateFuel();Need(r.Motion.FuelTier==3,"billable debt prevents tier mutation");Near(r.Stock(3),9.7,"old tier settles debt");
  r.UpdateFuel();Need(r.Motion.FuelTier==1,"cold settled accounting can select Aether");
  r.Motion.PowerInputMW=1;for(int i=0;i<400;i++)r.UpdateThermalMode();Need(r.Motion.Thermal.Settled && r.Motion.Thermal.Mode==ThermalMode.Standalone,"cold powered retraction allowed without advanced controller");
  r=new Reactor();r.RequestThermalMode(ThermalMode.Brayton);r.Motion.PowerInputMW=1;r.UpdateThermalMode();float partial=r.Motion.Thermal.Deployment;
  r.Controllers(false);for(int i=0;i<400;i++)r.UpdateThermalMode();Near(r.Motion.Thermal.Deployment,partial,"controller loss pauses partial deployment");
  r.Controllers(true);for(int i=0;i<400;i++)r.UpdateThermalMode();Need(r.Motion.Thermal.Settled && !r.reactor.Enabled,"repair resumes deployment but requires manual restart");
  foreach(bool creative in new[]{false,true}){
   r=new Reactor();r.Motion.SecurityMode=false;r.Motion.FuelTier=3;r.Stock(3,10);r.Running();r.Motion.Thermal.Store.HotMJ=1000;MyAPIGateway.Session.CreativeMode=creative;
   r.UpdateFuel();r.ProduceThermal(r.ThermalHeatMW);r.BeginShutdown();
   Need(!r.reactor.Enabled && r.Motion.Core==CorePhase.Cooling && r.Motion.FuelTier==3,"old unsafe standalone save cools even with vent security disabled");
   Near(r.Motion.Thermal.Store.HotMJ,1000,"legacy save retains paid heat");Near(r.Motion.Thermal.FuelHeatMJ,0,"legacy save produces no unsafe heat");
  }
  MyAPIGateway.Session.CreativeMode=false;
 }
 static void CircuitShutdown(){
  foreach(bool critical in new[]{false,true}){
   var r=new Reactor();r.Mode(ThermalMode.Brayton);r.Motion.FuelTier=3;r.Stock(3,10);r.Running();
   r.Motion.Thermal.Store.HotMJ=1000;r.Motion.Thermal.Store.WasteMJ=400;r.Motion.Thermal.AttachedHeatMJ=300;
   r.Motion.Thermal.FuelHeatMJ=125;r.Motion.FuelDebt=.25;r.Motion.Critical=critical;r.Motion.CriticalSeconds=17;
   r.Motion.Heat=critical?1.3f:.8f;r.nativeReactor.Capacity=9;
   r.StopForLoopLoss();
   Need(!r.reactor.Enabled && !r.ThermalCanRun && !r.Motion.Thermal.LoopTrip,"all-circuit running loss stops generation without a startup latch");
   Need(r.nativeReactor.Capacity==0 && r.Motion.Core==CorePhase.Cooling,"last-loop loss uses normal powered cooldown");
   Near(r.Motion.Thermal.Store.HotMJ+r.Motion.Thermal.Store.WasteMJ+r.Motion.Thermal.AttachedHeatMJ,1700,"circuit trip retains every attached MJ");
   Need(r.Motion.Thermal.Mode==ThermalMode.Brayton && r.Motion.Thermal.Deployment==1,"no standalone fallback or manifold retraction");
   Need(r.Motion.Critical==critical && r.Motion.CriticalSeconds==17,"circuit trip cannot cancel or restart a critical fuse");
   r.ProduceThermal(r.ThermalHeatMW);Near(r.Motion.Thermal.FuelHeatMJ,125,"shutdown cannot admit fresh fuel heat");
   Near(r.Motion.FuelDebt,.25,"pending fuel debt survives trip");
   Need(r.NeedsStorageSupport,"last-loop shutdown retains containment support");
  }
  var old=new Reactor();old.Mode(ThermalMode.Brayton);old.Running();
  old.Motion.Thermal.Store.HotMJ=1000;old.Motion.Thermal.Store.WasteMJ=400;
  old.InitializeThermalRuntime();
  Need(old.Motion.Thermal.LoopVersion==2 && !old.reactor.Enabled,"legacy shared save migrates disabled");
  Near(old.Motion.Thermal.RetainedHeatMJ,1400,"legacy migration preserves heat");
  var loaded=new Reactor();loaded.Mode(ThermalMode.Brayton);loaded.Motion.Thermal.LoopVersion=1;
  loaded.Motion.Thermal.Loops[0].Connected=true;
  loaded.Motion.Thermal.Store.WasteMJ=50;loaded.InitializeThermalRuntime();
  Need(loaded.Motion.Thermal.ConnectedLoops==0,"reload requires fresh topology validation");
  Near(loaded.Motion.Thermal.RetainedHeatMJ,50,"reload retains every saved MJ");
  Need(!loaded.Motion.Thermal.LoopTrip,"reload before topology validation is not a manual start");
  foreach(CorePhase phase in Enum.GetValues(typeof(CorePhase)))for(int connected=0;connected<=4;connected++){
   var r=new Reactor();r.Mode(ThermalMode.Brayton);r.Stock(1,10);r.Motion.Core=phase;
   for(int i=0;i<connected;i++)r.Motion.Thermal.Loops[i].Connected=true;
   r.reactor.Enabled=false;r.BeginShutdown();r.CheckLoopSafety();
   Need(!r.Motion.Thermal.LoopTrip,"normal Off/starting/running/cooling/stopping shutdown never latches for any defect count");
  }
  for(int connected=0;connected<=4;connected++){
   var r=new Reactor();r.Mode(ThermalMode.Brayton);r.Stock(1,10);
   for(int i=0;i<connected;i++)r.Motion.Thermal.Loops[i].Connected=true;
   r.CheckLoopSafety();Need(!r.Motion.Thermal.LoopTrip,"passive topology checks without manual On do not latch");
   r.reactor.Enabled=false;r.reactor.Enabled=true;
   Need(r.thermalStartRequested && !r.CanPrepareContainment,"manual On defers containment preparation until topology is checked");
   r.CheckLoopSafety();
   Need(r.Motion.Thermal.LoopTrip==(connected==0) && r.reactor.Enabled==(connected>0),"manual startup latches only with four defective circuits");
   Need(!r.thermalStartRequested,"one manual On produces exactly one startup validation");
   if(connected>0){
    Need(r.Motion.Thermal.ConnectedLoops==connected,"complete circuits are available immediately");
    r.Running();r.CheckLoopSafety();Need(r.reactor.Enabled && !r.Motion.Thermal.LoopTrip,"valid circuits do not trigger a running loss");
    r.Motion.Thermal.Loops=ThermalLoops.Empty();r.CheckLoopSafety();
    Need(!r.reactor.Enabled && !r.Motion.Thermal.LoopTrip,"last structural circuit loss stops without latching");
   }
  }
  var retry=new Reactor();retry.Mode(ThermalMode.Brayton);retry.reactor.Enabled=false;retry.reactor.Enabled=true;retry.CheckLoopSafety();
  retry.Motion.Thermal.Loops[0].Connected=true;retry.CheckLoopSafety();
  Need(retry.Motion.Thermal.LoopTrip && !retry.reactor.Enabled,"repair alone cannot restart a rejected startup");
  retry.reactor.Enabled=true;retry.CheckLoopSafety();Need(!retry.Motion.Thermal.LoopTrip && retry.reactor.Enabled,"manual retry clears the startup latch after one circuit is repaired");
  for(int working=0;working<4;working++){
   var single=new Reactor();single.Mode(ThermalMode.Brayton);single.Stock(1,10);
   single.Motion.Thermal.Loops[working].Connected=true;
   single.reactor.Enabled=false;single.reactor.Enabled=true;single.CheckLoopSafety();
   Need(single.reactor.Enabled && !single.Motion.Thermal.LoopTrip && single.Motion.Thermal.ConnectedLoops==1,
    "manual startup accepts any one of the four complete circuits");
   single.Running();single.CheckLoopSafety();Need(single.ThermalCanRun,"one complete circuit remains operational with three incomplete circuits");
  }
  var cancelled=new Reactor();cancelled.Mode(ThermalMode.Brayton);cancelled.reactor.Enabled=false;cancelled.reactor.Enabled=true;cancelled.reactor.Enabled=false;cancelled.CheckLoopSafety();
  Need(!cancelled.Motion.Thermal.LoopTrip,"manual Stop cancels a queued startup check");
  var stale=new Reactor();stale.Mode(ThermalMode.Brayton);stale.Motion.Thermal.LoopVersion=1;stale.Motion.Thermal.LoopTrip=true;stale.reactor.Enabled=false;stale.InitializeThermalRuntime();
  Need(!stale.Motion.Thermal.LoopTrip && !stale.reactor.Enabled,"old false saved latch clears on reload without re-enabling the reactor");
  MyAPIGateway.Multiplayer.IsServer=false;
  var client=new Reactor();client.Mode(ThermalMode.Brayton);client.reactor.Enabled=false;client.reactor.Enabled=true;
  Need(!client.thermalStartRequested,"clients cannot arm the server startup latch");MyAPIGateway.Multiplayer.IsServer=true;
 }
 static void RuntimeFaultShutdown(){
  foreach(var mode in new[]{ThermalMode.Standalone,ThermalMode.Brayton}){
   var r=new Reactor();r.Mode(mode);r.Stock(1,10);r.Running();
   r.Motion.Thermal.Store.HotMJ=40;r.Motion.Thermal.Loops[0].ExcessMJ=20;
   r.Motion.Thermal.Loops[0].Connected=true;
   r.FailThermalRuntime();
   Need(!r.reactor.Enabled && r.Motion.Core==CorePhase.Cooling && !r.ThermalCanRun,"runtime exception explicitly starts cooldown");
   Need(r.Motion.Thermal.Faulted && r.Motion.Thermal.Loops[0].Connected,"runtime exception preserves connected cooling");
   Near(r.Motion.Thermal.Store.HotMJ,40,"shutdown preserves paid heat inventory");
   Near(r.Motion.Thermal.Loops[0].ExcessMJ,20,"shutdown preserves retained waste");
   r.reactor.Enabled=true;r.UpdateThermalMode();Need(!r.reactor.Enabled,"fault cannot be bypassed by toggling either reactor mode");
  }
  var source=new Reactor();source.Mode(ThermalMode.Brayton);source.Stock(1,10);source.Running();
  source.Motion.Thermal.Store.HotMJ=10;source.Motion.Thermal.Loops[0].Connected=true;
  var block=new ThermalBlock{Block=new Block(),Generator=new ReactorBlock(),Spec=new ThermalModel{RatingMW=100}};
  block.OutputGrant=new ThermalOutputGrant(source.Motion.Thermal,source.Motion.Thermal.Loops[0],1,.4);
  block.Generator.CurrentOutput=100;MyAPIGateway.Session.GameplayFrameCounter++;block.AccountOutput();
  Need(source.Motion.Thermal.Faulted && block.Fault==null,"paid output fault trips generation without latching physical circuit");
  source.CheckLoopSafety();
  Need(!source.reactor.Enabled && source.Motion.Core==CorePhase.Cooling,"accounting fault stops running core despite ThermalCanRun already false");
  Need(ThermalLoops.OpenValves(source.Motion.Thermal)==1,"accounting fault leaves intact cooling path open");
 }
 static void OutputLifetime(){
  var state=new ThermalReactorState{Store=new ThermalStore{EntityId=1,HotMJ=10},LoopVersion=2};
  var block=new ThermalBlock{Block=new Block(),Generator=new ReactorBlock(),Spec=new ThermalModel{RatingMW=100}};
  block.OutputGrant=new ThermalOutputGrant(state,state.Loops[0],1,.4);
  block.Generator.CurrentOutput=(float)(block.OutputGrant.MaximumMW*.5);
  MyAPIGateway.Session.GameplayFrameCounter++;block.AccountOutput();double credit=state.Store.HotMJ;
  block.OutputGrant=new ThermalOutputGrant(state,state.Loops[0],1,.4);
  block.AccountOutput();Near(state.Store.HotMJ,credit,"same-frame close cannot bill an interval twice");
  block.Block.Closed=true;MyAPIGateway.Session.GameplayFrameCounter++;block.AccountOutput();
  Need(state.Store.HotMJ<credit && block.Fault==null,"removed native generator settles conservatively without returning potentially spent credit");
  block.SetOutput(100);Near(block.Generator.Capacity,0,"closed generator receives no native writes");
 }
 static void ReservationSafety(){
  var r=new Reactor();r.Mode(ThermalMode.Brayton);r.Motion.Thermal.LoopVersion=2;r.Stock(1,1);r.Running();
  r.BeginThermalFrame();var grant=r.ReserveThermalOutput(r.Motion.Thermal.Loops[0],r.ThermalHeatMW,.4);
  Need(r.Stock(1)<1 && r.Motion.Thermal.FuelHeatMJ==0,"fuel is debited before a native grant becomes available");
  r.Stock(1,0);Need(grant.Settle(grant.MaximumMW),"removing remaining fuel cannot make the issued grant unpaid");
  r.BeginThermalFrame();Need(r.ReserveThermalOutput(r.Motion.Thermal.Loops[0],r.ThermalHeatMW,.4)==null,"exhausted stock cannot fund another grant");
 }
 static void FixedElectricalDemand(){
  foreach(var mode in new[]{ThermalMode.Standalone,ThermalMode.Brayton}){
   var r=new Reactor();r.Mode(mode);r.Stock(1,10);r.Running();
   double eta=mode==ThermalMode.Standalone?.10:.80;
   for(int tick=0;tick<3600;tick++){
    r.BeginThermalFrame();
    var grant=r.ReserveThermalOutput(null,r.ThermalHeatMW,eta);
    Need(grant.Settle(100),"constant electrical demand stays within paid fuel grant");
    r.UpdateFuel();r.Motion.Thermal.Store.WasteMJ=0;
   }
   double energyPerCanister=r.ThermalHeatMW*2.5*60*r.FuelEfficiency;
   double spent=10-r.Stock(1)+r.Motion.FuelDebt-r.Motion.Thermal.Store.HotMJ/energyPerCanister;
   Near(spent,100/eta*60/energyPerCanister,"same electrical demand burns fuel in inverse proportion to conversion efficiency");
   Near(r.FuelUnitsPerMinute(),100/eta*60/energyPerCanister,"fuel-use display follows the higher Brayton efficiency");
  }
 }
 static void FuelBalance(){
  foreach(var mode in new[]{ThermalMode.Standalone,ThermalMode.Brayton})
  for(int rings=2;rings<=4;rings++)for(int tier=1;tier<rings;tier++){
   if((mode==ThermalMode.Standalone && tier!=1) || (mode==ThermalMode.Brayton && rings==2))continue;
   double minutes=tier==1?2.5:10,efficiency=new[]{.8,.9,.99}[rings-2];
   double rating=new[]{5000.0,50000,250000}[tier-1];
   foreach(double load in new[]{0.0,.25,.5,.75,1.0}){
    var r=new Reactor();r.Mode(mode);r.Motion.RingCount=rings;r.Motion.FuelTier=tier;r.Stock(tier,10);r.Running();
    double admitted=0;
    for(int tick=0;tick<3600;tick++){
     r.BeginThermalFrame();
     double before=r.Motion.Thermal.Store.HotMJ;
     var grant=r.ReserveThermalOutput(null,rating,mode==ThermalMode.Standalone?.10:.80);
     admitted+=r.Motion.Thermal.Store.HotMJ-before;
     Need(grant.Settle(grant.MaximumMW*load),"fuel-backed output settles once");
     r.UpdateFuel();r.Motion.Thermal.Store.WasteMJ=0; // Adequate integrated cooling.
    }
    double burned=10-r.Stock(tier);
    Near(admitted-r.Motion.Thermal.Store.HotMJ,rating*load*60*.999999,"paid fuel equals delivered reaction plus unused credit");
    Near(burned+r.Motion.FuelDebt,load*.999999/(minutes*efficiency)+r.Motion.Thermal.Store.HotMJ/(rating*minutes*60*efficiency),"one-minute debit uses Aether 2.5 / higher-tier 10 minute endurance");
    Near(r.FuelUnitsPerMinute(),load*.999999/(minutes*efficiency),"UI burn agrees with actual heat debit");
    if(load>0)Near(1/r.FuelUnitsPerMinute(),minutes*efficiency/(load*.999999),"UI endurance follows controllers and active circuits");
    double recovered=(double)r.reactor.Inventory.GetItemAmount(MyItemType.MakeComponent(ResiduumSubtype))
      +r.Motion.ResiduumMicroUnits/(double)ResiduumScale;
    Near(recovered,tier==1?burned*10:0,"paid Aether still recovers exactly ten Residuum per canister");
   }
   var low=new Reactor();low.Mode(mode);low.Motion.RingCount=rings;low.Motion.FuelTier=tier;low.Stock(tier,.000002);low.Running();
   double energy=rating*minutes*60*efficiency;
   low.Motion.FuelDebt=.000001;low.Motion.Thermal.FuelHeatMJ=energy*.00000025;
   low.ProduceThermal(rating);
   Near(low.Motion.Thermal.Store.HotMJ,energy*.00000075,"near-empty admission subtracts both fuel debt and unbilled heat");
   low.UpdateFuel();Near(low.Stock(tier),0,"admitted heat consumes the last available fuel");
   double hot=low.Motion.Thermal.Store.HotMJ;low.ProduceThermal(rating);
   Near(low.Motion.Thermal.Store.HotMJ,hot,"empty fuel cannot create additional heat");
   var starved=new Reactor();starved.Mode(mode);starved.Motion.RingCount=rings;starved.Motion.FuelTier=tier;starved.Stock(tier,10);starved.Running();
   starved.Motion.TileStarved=true;starved.Motion.StarvedLoad=.4f;
   for(int tick=0;tick<3600;tick++)starved.UpdateFuel();
   Near(10-starved.Stock(tier)+starved.Motion.FuelDebt,4/(minutes*efficiency),"starvation fuel penalty follows the selected endurance");
   Near(starved.nativeReactor.Capacity,0,"starvation still blocks thermal generation");
  }
 }
 static void Residuum(){
  foreach(var mode in new[]{ThermalMode.Standalone,ThermalMode.Brayton}){
   var r=new Reactor();r.Mode(mode);r.Stock(1,2);r.Running();
   // Native fixed-point quantum: repeated tiny real debits equal a full canister.
   for(int i=0;i<100000;i++){r.Motion.FuelDebt=.00001;r.UpdateFuel();}
   Near(r.Stock(1),1,"tiny fuel debits total one canister");
   Near((double)r.reactor.Inventory.GetItemAmount(MyItemType.MakeComponent(ResiduumSubtype)),10,"ten recovered components per canister in both modes");
   Need(r.Motion.ResiduumMicroUnits==0,"no fractional drift");
   r.UpdateFuel();Near((double)r.reactor.Inventory.GetItemAmount(MyItemType.MakeComponent(ResiduumSubtype)),10,"idle produces no material");
  }
  var full=new Reactor();full.Stock(1,1);full.Running();full.reactor.Inventory.Room=false;
  full.Motion.FuelDebt=.125;full.UpdateFuel();Need(full.Motion.ResiduumMicroUnits==1250000,"full inventory preserves paid recovery credit");
  full.Motion.EntityId=1;full.Motion.Thermal.Store.EntityId=1;full.Motion.ReserveMJ=0;
  var xml=new System.Xml.Serialization.XmlSerializer(typeof(MotionState));
  string saved;using(var writer=new System.IO.StringWriter()){xml.Serialize(writer,full.Motion);saved=writer.ToString();}
  MotionState state;using(var reader=new System.IO.StringReader(saved))state=(MotionState)xml.Deserialize(reader);
  var copy=new Reactor();copy.Id=2;copy.RestoreMotionState(state);Need(copy.Motion.ResiduumMicroUnits==0,"pasted identity cannot duplicate earned credit");
  var loaded=new Reactor();loaded.RestoreMotionState(state);Need(loaded.Motion.ResiduumMicroUnits==1250000,"fractional recovery survives actual state serialization and restore");
  loaded.reactor.Inventory.RejectAdd=true;loaded.RecoverResiduum();Need(loaded.Motion.ResiduumMicroUnits==1250000,"failed native add cannot erase credit");
  loaded.reactor.Inventory.RejectAdd=false;loaded.RecoverResiduum();Need(loaded.Motion.ResiduumMicroUnits==250000,"retry delivers whole unit and keeps fraction");
  Near((double)loaded.reactor.Inventory.GetItemAmount(MyItemType.MakeComponent(ResiduumSubtype)),1,"retry adds only paid whole unit");
  loaded.Motion.ResiduumMicroUnits=-1;Need(!Valid(loaded.Motion),"reject negative recovery state");
  loaded.Motion.ResiduumMicroUnits=1000000000000001L;Need(!Valid(loaded.Motion),"reject overflowing recovery state");
  loaded.Motion.ResiduumMicroUnits=250000;loaded.BeginDismantling();Need(loaded.Motion.ResiduumMicroUnits==250000,"shutdown retains recovery credit");
  foreach(int tier in new[]{2,3}){var r=new Reactor();r.Mode(ThermalMode.Brayton);r.Motion.FuelTier=tier;r.Stock(tier,2);r.Running();r.Motion.FuelDebt=.5;r.UpdateFuel();Need(r.Motion.ResiduumMicroUnits==0 && r.reactor.Inventory.GetItemAmount(MyItemType.MakeComponent(ResiduumSubtype))==0,"higher tiers cannot farm Residuum");}
  foreach(int kind in new[]{0,1,2}){
   var r=new Reactor();r.Stock(1,2);r.Running();r.Motion.FuelDebt=.5;
   MyAPIGateway.Session.CreativeMode=kind==0;MyAPIGateway.Multiplayer.IsServer=kind!=1;r.IsLive=kind!=2;
   r.UpdateFuel();Near(r.Stock(1),2,"creative/client/removed do not burn");Need(r.Motion.ResiduumMicroUnits==0,"creative/client/removed cannot earn credit");
   r.Motion.ResiduumMicroUnits=ResiduumScale;if(kind!=0){r.RecoverResiduum();Need(r.Motion.ResiduumMicroUnits==ResiduumScale,"client/removed cannot create components");}
  }
  MyAPIGateway.Session.CreativeMode=false;MyAPIGateway.Multiplayer.IsServer=true;
  var empty=new Reactor();empty.Running();empty.Motion.FuelDebt=.5;empty.UpdateFuel();Need(empty.Motion.ResiduumMicroUnits==0,"unpaid debt earns nothing");
  foreach(int kind in new[]{0,1,2,3}){
   var r=new Reactor();r.Stock(1,2);r.reactor.Inventory.Stock[ResiduumSubtype]=(MyFixedPoint)3;r.reactor.UseConveyorSystem=kind!=1;r.networkTick=0;
   var cargo=new Block{Accessible=kind!=2};cargo.Inventory.Reachable=kind!=3;
   MyAPIGateway.TerminalActionsHelper.Terminal.Blocks.Clear();MyAPIGateway.TerminalActionsHelper.Terminal.Blocks.Add(cargo);
   r.UpdateFuel();Near((double)cargo.Inventory.GetItemAmount(MyItemType.MakeComponent(ResiduumSubtype)),kind==0?3:0,"export obeys conveyor toggle, access and connectivity");
   Near((double)cargo.Inventory.GetItemAmount(MyItemType.MakeIngot(Fuels[0])),0,"export never removes fuel");
  }
  MyAPIGateway.TerminalActionsHelper.Terminal.Blocks.Clear();
 }
 static void CircuitAccounting(){
  var r=new Reactor();r.Mode(ThermalMode.Brayton);r.Stock(1,10);r.Running();
  r.Motion.Thermal.Store.EntityId=r.Id;
  var session=new ThermalSession();var machines=new List<ThermalBlock>();var hosts=new List<ThermalBlock>();
  Func<int,int,ThermalPort> port=(x,sign)=>new ThermalPort("CO2",new Vector3(x,0,0),Vector3.UnitX*sign,Vector3.UnitY);
  var roots=new ThermalPort[4];
  for(int i=0;i<4;i++){
   int x=i*10;roots[i]=port(x,1);
   var ports=new[]{new[]{port(x,-1),port(x+1,-1),port(x+2,-1)},new[]{port(x+1,1)},new[]{port(x+2,1)}};
   for(int j=0;j<3;j++){
    var spec=new ThermalModel{Kind=j==0?ThermalKind.Pipe:j==1?ThermalKind.Train:ThermalKind.AirCooler,
     RatingMW=r.ThermalHeatMW,CoolingMW=j==2?10000:0,Ports=ports[j]};
    var machine=new ThermalBlock{Spec=spec,Block=new Block{EntityId=10+i*3+j,CubeGrid=r.Block.CubeGrid}};
    machine.Node=new ThermalEndpoint{Id=machine.Block.EntityId,GridId=1,Healthy=true,Model=spec,Ports=spec.Ports};
    machine.Store.EntityId=machine.Block.EntityId;
    if(j==1){machine.Generator=new ReactorBlock();hosts.Add(machine);}
    machine.ObserveChanges();machines.Add(machine);ThermalSession.Blocks.Add(machine.Block.EntityId,machine);
   }
  }
  r.CircuitEndpoint=new ThermalEndpoint{Id=r.Id,GridId=1,Healthy=true,
   Model=new ThermalModel{Kind=ThermalKind.Reactor,Ports=roots},Ports=roots};
  r.reactor.Enabled=false;r.Motion.Core=CorePhase.Off;
  session.Step(r,machines);
  Need(r.Motion.Thermal.ConnectedLoops==4 && session.Valves==15,"complete circuits validate before powerup");
  foreach(var host in hosts)Near(host.OutputGrantMW,0,"validating a cold stopped circuit grants no electricity");
  var removed=machines[0];machines.Remove(removed);ThermalSession.Blocks.Remove(removed.Block.EntityId);session.Changed(1);
  Need(ThermalSession.circuitGraphs[r.Id].Invalidated,"block removal invalidates the grid while retaining the previous membership");
  session.Step(r,machines);
  Need(r.Motion.Thermal.ConnectedLoops==3 && session.Valves==14,"removal updates circuit validity while reactor is off");
  machines.Insert(0,removed);ThermalSession.Blocks.Add(removed.Block.EntityId,removed);session.Changed(1);
  session.Step(r,machines);
  Need(r.Motion.Thermal.ConnectedLoops==4 && !r.reactor.Enabled,"addition restores validity without starting reactor");
  var cached=ThermalSession.circuitGraphs[r.Id];
  r.reactor.Enabled=true;r.Running();r.Motion.ReserveMJ=r.ReserveCapacityMJ;
  r.initializationFrames=1;r.Motion.Thermal.LoopVersion=2;r.InitializeThermalRuntime();
  Need(r.Motion.Thermal.ConnectedLoops==0,"reload discards saved connection claims");
  r.UpdateBeforeSimulation();
  Need(r.reactor.Enabled && r.ThermalCanRun,"before-simulation handoff permits validated after-simulation dispatch");
  double reserveAfter=r.Motion.ReserveMJ;
  session.Step(r,machines);
  Need(r.reactor.Enabled && !r.Motion.Thermal.LoopTrip,"restored valid circuits keep running without a manual startup latch");
  r.UpdateBeforeSimulation();Near(r.Motion.ReserveMJ,reserveAfter-r.ContainmentMW/60.0,"next native interval still pays containment deficit");
  r.Supply(r.ContainmentMW);r.UpdateBeforeSimulation();
  Need(r.reloadPowerFrames==0 && r.reactor.Enabled,"native power ends recovery after circuit dispatch");
  Need(Object.ReferenceEquals(cached,ThermalSession.circuitGraphs[r.Id]),"powerup uses the existing validated physical graph");
  Need(r.Motion.Thermal.ConnectedLoops==4 && session.Valves==15,"cold circuits are immediately ready with open valves");
  Near(r.Motion.Thermal.ProducedMW,0,"an unused native grant produces no reaction heat");
  foreach(var host in hosts) {
   Need(host.OutputGrantMW>0,"cold validated turbine receives a fuel-backed grant without pump startup");
   host.Generator.CurrentOutput=(float)(host.OutputGrantMW*.25);
  }
  session.Step(r,machines);
  Near(r.Motion.Thermal.ProducedMW,r.Motion.Thermal.NetOutputMW/.8,"actual demand sets reaction heat");
  foreach(var host in hosts) Near(host.RotorLoad,.25*.999999,"quarter demand gives quarter shaft target");
  double capacity=r.Motion.Thermal.CoolingMW;
  foreach(var host in hosts) host.Generator.CurrentOutput=(float)host.OutputGrantMW;
  session.Step(r,machines);
  Near(r.Motion.Thermal.CoolingMW,capacity,"cooling capacity is independent of load");
  var failedCooler=machines[2];
  failedCooler.Store.Radiator=new ThermalRadiatorState();
  foreach(var kind in new[]{ThermalKind.AirCooler,ThermalKind.Radiator,ThermalKind.HullRadiator}){
   failedCooler.Spec.Kind=kind;failedCooler.Block.IsFunctional=false;failedCooler.CircuitRevision++;session.Step(r,machines);
   Need(r.Motion.Thermal.ConnectedLoops==4 && session.Valves==15,"failed cooler retains pressure in production dispatcher");
   Near(r.Motion.Thermal.Loops[0].CoolingMW,0,"failed cooler has zero production rejection");
   Need(hosts[0].OutputGrantMW>0,"failed cooling does not revoke paid generation");
   failedCooler.Block.IsFunctional=true;failedCooler.Block.Enabled=false;failedCooler.CircuitRevision++;session.Step(r,machines);
   Need(session.Valves==15 && r.Motion.Thermal.Loops[0].CoolingMW==0,"disabled cooler keeps pressure without cooling");
   failedCooler.Block.Enabled=true;failedCooler.CircuitRevision++;
  }
  failedCooler.Spec.Kind=ThermalKind.AirCooler;
  machines.Remove(failedCooler);ThermalSession.Blocks.Remove(failedCooler.Block.EntityId);session.Step(r,machines);
  Need(r.Motion.Thermal.ConnectedLoops==3 && session.Valves==14,"removed cooler closes only its circuit in production dispatcher");
  machines.Insert(2,failedCooler);ThermalSession.Blocks[failedCooler.Block.EntityId]=failedCooler;session.Step(r,machines);
  Need(session.Valves==15 && r.Motion.Thermal.Loops[0].CoolingMW>0,"replacement cooler restores seal and cooling");
  var broken=machines[0];broken.Block.IsFunctional=false;session.Step(r,machines);
  Need(r.Motion.Thermal.ConnectedLoops==3 && session.Valves==14,"breach isolates only its quarter allocation");
  broken.Block.IsFunctional=true;broken.Block.EntityId=99;broken.Node.Id=99;ThermalSession.Blocks.Remove(10);ThermalSession.Blocks.Add(99,broken);
  session.Step(r,machines);
  Need(r.Motion.Thermal.ConnectedLoops==4 && session.Valves==15,"replacement pipe restores its circuit without a refill");
  r.FailThermalRuntime();
  Need(!r.reactor.Enabled && r.Motion.Core==CorePhase.Cooling,"full plant runtime isolation stops the core");
  session.Step(r,machines);
  Need(r.Motion.Thermal.Faulted && session.Valves==15,"source failure leaves all four intact cooling circuits open");
  Need(r.Motion.Thermal.CoolingMW>0 && machines.TrueForAll(m=>m.Fault==null),"runtime fault retains cooling without latching machinery");
  foreach(var host in hosts)Near(host.OutputGrantMW,0,"source runtime fault revokes new generation grants");
  r.Motion.Thermal.Faulted=false;
  double paid=r.Motion.Thermal.FuelHeatMJ;r.reactor.Enabled=false;r.BeginShutdown();
  foreach(var host in hosts)host.Generator.CurrentOutput=0;
  r.Motion.Thermal.Loops[0].ExcessMJ=100;
  double before=r.Motion.Thermal.RetainedHeatMJ;
  session.Step(r,machines);
  foreach(var host in hosts)Near(host.OutputGrantMW,0,"shutdown grants no new electrical conversion");
  Need(r.Motion.Thermal.RetainedHeatMJ<before,"connected cooling drains retained circuit heat without generation");
  Near(r.Motion.Thermal.FuelHeatMJ,paid,"shutdown circulation admits no new fuel heat");
  r.Motion.Thermal.Store.HotMJ=r.Motion.Thermal.Store.WasteMJ=0;
  foreach(var machine in machines)machine.Store.HotMJ=machine.Store.WasteMJ=0;
  session.Step(r,machines);
  foreach(var host in hosts)Near(host.OutputGrantMW,0,"cold stopped plant grants no power");
  r.Motion.ReserveMJ=0;r.Motion.PowerInputMW=0;r.Motion.PowerPaused=true;
  r.Motion.Thermal.Loops[0].ExcessMJ=100;session.Step(r,machines);
  Need(r.Motion.Thermal.PotentialCoolingMW>0 && r.Motion.Thermal.Loops[0].PotentialCoolingMW>0,
   "complete offline circuits expose potential cooling without auxiliary power");
  Near(r.Motion.Thermal.CoolingMW,0,"active coolers require containment auxiliary power during cooldown");
  Near(r.Motion.Thermal.Loops[0].ExcessMJ,100,"unpowered active cooling cannot erase heat");
  machines[2].Spec.Kind=ThermalKind.Radiator;machines[2].CircuitRevision++;session.Step(r,machines);
  Near(r.Motion.Thermal.Loops[0].ExcessMJ,0,"passive radiator cools without turbine output or auxiliary supply");
  Need(machines[2].CoolingRejectedMW>0,"radiator glow receives actual heat rejection");
  machines[2].Spec.Kind=ThermalKind.AirCooler;machines[2].CircuitRevision++;r.Motion.PowerPaused=false;session.Step(r,machines);

  // The historical radiator exception left the vessel and turbines faulted,
  // even though construction topology was complete. Recheck only changed circuits.
  r.Motion.EntityId=r.Id;r.Motion.ReserveMJ=0;
  r.Motion.Thermal.Faulted=true;r.Motion.Thermal.Diagnostic="Runtime fault; heat inventory isolated and retained";
  r.Motion.Thermal.LoopTrip=true;r.Motion.Thermal.Store.HotMJ=40;r.Motion.Thermal.Store.WasteMJ=20;
  hosts[0].Fault=hosts[1].Fault="Native output exceeded its paid heat allocation; isolated";
  hosts[0].Store.HotMJ=7;hosts[0].Store.WasteMJ=3;
  session.Step(r,machines);
  Need(r.Motion.Thermal.Faulted && session.Valves==12,"source fault preserves healthy cooling paths without resetting generation fault");
  Need(r.Motion.Thermal.Diagnostic.Contains("Runtime fault") && r.Motion.Thermal.Loops[0].Diagnostic.Contains("fault"),
   "runtime fault is not overwritten by an unsealed connection or startup message");
  machines[0].Block.Enabled=false;session.Step(r,machines);
  Need(r.Motion.Thermal.Faulted,"an incomplete changed circuit cannot clear source isolation");
  machines[0].Block.Enabled=true;session.Step(r,machines);
  Need(!r.Motion.Thermal.Faulted && !r.Motion.Thermal.LoopTrip && !r.Block.Enabled,
   "repaired circuit clears valid retained faults without automatically starting reactor");
  Need(hosts[0].Fault==null && hosts[1].Fault!=null && session.Valves==13,
   "only the changed circuit retries its machine fault; independent circuits keep their state");
  Need(session.Colour(machines[0].Block.EntityId)==ThermalFlowMode.Ready && session.Colour(hosts[0].Block.EntityId)==ThermalFlowMode.Ready,
   "recovered cold circuit restores normal pipe and turbine emissives before startup");
  Need(session.Colour(machines[3].Block.EntityId)==ThermalFlowMode.Unconnected && session.Colour(hosts[1].Block.EntityId)==ThermalFlowMode.Fault,
   "unchanged faulted circuit retains its own red indicators");
  Near(r.Motion.Thermal.Store.HotMJ,40,"recheck preserves reactor hot inventory");
  Near(r.Motion.Thermal.Store.WasteMJ,20,"recheck preserves reactor waste inventory");
  Near(hosts[0].Store.HotMJ,0,"recheck migrates old turbine hot inventory into its circuit");
  Near(hosts[0].Store.WasteMJ,0,"recheck migrates old turbine waste before cooling");
  Near(r.Motion.Thermal.FuelHeatMJ,paid,"recheck creates no fuel credit or reaction heat");
  Need(r.Motion.Thermal.Loops[1].Diagnostic.Contains("Train fault"),"machine isolation reports the actual fault");
  hosts[0].Fault="Repeated accounting fault";session.Step(r,machines);
  session.Changed(1);session.Step(r,machines);
  Need(hosts[0].Fault!=null,"unrelated grid invalidation cannot clear an unchanged circuit's fault");
  hosts[0].CircuitRevision++;session.Step(r,machines);
  Need(hosts[0].Fault==null,"a changed member revision triggers revalidation");
  hosts[0].Fault="Retry after pipe repair";
  int revision=machines[0].CircuitRevision;
  machines[0].Block.IsFunctional=false;machines[0].Block.IsFunctional=true;
  Need(machines[0].CircuitRevision==revision+2 && hosts[0].Fault!=null,
   "functional events retain a between-tick repair without clearing faults inside engine callbacks");
  session.Step(r,machines);
  Need(hosts[0].Fault==null && hosts[1].Fault!=null && session.Valves==13,
   "between-tick pipe repair restores only its circuit's valve");
  Need(session.Colour(machines[0].Block.EntityId)==ThermalFlowMode.Ready && !r.Block.Enabled,
   "event-driven recovery restores normal emissives while reactor remains stopped");
  Near(hosts[0].Store.HotMJ,0,"functional repair cannot recreate migrated energy");
  Near(hosts[0].Store.WasteMJ,0,"functional repair cannot recreate migrated waste");
  Near(r.Motion.Thermal.FuelHeatMJ,paid,"functional repair does not mint fuel credit");
  hosts[0].Fault="Retry after toggling pipe";
  machines[0].Block.Enabled=false;machines[0].Block.Enabled=true;
  session.Step(r,machines);
  Need(hosts[0].Fault==null && hosts[1].Fault!=null,"between-tick on/off change retries only its circuit");
  hosts[0].Fault="Power is not a repair";cached=ThermalSession.circuitGraphs[r.Id];revision=machines[0].CircuitRevision;
  machines[0].Block.PowerChanged();hosts[0].Block.PowerChanged();machines[0].Block.IsFunctional=true;
  session.Step(r,machines);
  Need(hosts[0].Fault!=null && machines[0].CircuitRevision==revision && Object.ReferenceEquals(cached,ThermalSession.circuitGraphs[r.Id]),
   "ordinary power events and unchanged functionality cannot reset faults or rebuild topology");
  machines[0].StopObservingChanges();revision=machines[0].CircuitRevision;
  machines[0].Block.Enabled=false;machines[0].Block.IsFunctional=false;
  machines[0].Block.IsFunctional=true;machines[0].Block.Enabled=true;
  Need(machines[0].CircuitRevision==revision,"unsubscription releases functional and enabled event handlers");
  machines[0].ObserveChanges();machines[0].Block.Enabled=false;revision=machines[0].CircuitRevision;
  machines[0].Block.IsFunctional=false;machines[0].Block.IsFunctional=true;
  Need(machines[0].CircuitRevision==revision+2,"damage and repair still signal when a pipe is switched off");
  session.Step(r,machines);Need(hosts[0].Fault!=null,"repair of a disabled pipe cannot open its circuit");
  machines[0].Block.Enabled=true;session.Step(r,machines);Need(hosts[0].Fault==null,"enabling the repaired pipe completes the safe recheck");
  hosts[0].Fault="Invalid inventory";hosts[0].Store.HotMJ=-1;hosts[0].CircuitRevision++;
  session.Step(r,machines);Need(hosts[0].Fault!=null,"invalid inventories remain isolated after block updates");
  hosts[0].Store.HotMJ=7;hosts[0].preserveInvalidSave=true;hosts[0].CircuitRevision++;
  session.Step(r,machines);Need(hosts[0].Fault!=null,"unreadable saved inventory remains protected");
  hosts[0].preserveInvalidSave=false;hosts[0].Generator.CurrentOutput=1;hosts[0].RecheckCircuitFault();
  Need(hosts[0].Fault!=null,"active native output prevents accounting fault reset");
  hosts[0].Generator.CurrentOutput=0;hosts[0].Generator.BlockDefinition.FuelInfos=new object[1];hosts[0].RecheckCircuitFault();
  Need(hosts[0].Fault!=null,"invalid native fuel definition cannot clear its fault");
  hosts[0].Generator.BlockDefinition.FuelInfos=new object[0];hosts[0].Generator.BlockDefinition.MaxPowerOutput=0;
  hosts[0].RecheckCircuitFault();Need(hosts[0].Fault!=null,"invalid native rating cannot clear its fault");
  r.Motion.Thermal.Faulted=true;r.Motion.Critical=true;r.RecheckThermalFault();
  Need(r.Motion.Thermal.Faulted && r.Motion.Critical,"reactor fault recovery cannot undo a meltdown");
  r.Motion.Critical=false;r.thermalRestoreFault=true;r.RecheckThermalFault();
  Need(r.Motion.Thermal.Faulted,"invalid restored reactor state cannot be reset by topology edits");
  r.thermalRestoreFault=false;r.Motion.Thermal.Store.HotMJ=double.NaN;r.RecheckThermalFault();
  Need(r.Motion.Thermal.Faulted,"invalid live reactor state remains isolated");
  foreach(var machine in machines)machine.StopObservingChanges();
 }
 static void RadiatorRemoval(){
  ThermalSession.Blocks.Clear();
  var root=new ThermalBlock{Spec=new ThermalModel{Kind=ThermalKind.Radiator},Block=new Block{EntityId=70,CubeGrid=new Grid()}};
  root.Entity=root.Block;
  var removed=new ThermalBlock{Spec=new ThermalModel{Kind=ThermalKind.RadiatorPanel},Block=new Block{EntityId=71,Closed=true},Entity=null};
  root.RadiatorPanels.Add(removed);ThermalSession.Blocks.Add(70,root);
  ThermalSession.Link();
  Need(root.RadiatorPanels.Count==0 && root.CircuitRevision==1,"removed panel with released GameLogic.Entity detaches without runtime failure");
  ThermalSession.Link();Need(root.CircuitRevision==1,"unchanged panel layout does not repeatedly recheck faults");
  var panel=new ThermalBlock{Spec=new ThermalModel{Kind=ThermalKind.RadiatorPanel},Block=new Block{EntityId=72,CubeGrid=root.Block.CubeGrid}};
  panel.Block.WorldMatrix=MatrixD.CreateTranslation(ThermalRadiators.ExtensionCentre(root.Block.WorldMatrix,0));panel.Entity=panel.Block;
  root.Block.CubeGrid.Cells[root.Block.CubeGrid.WorldToGridInteger(panel.Block.WorldMatrix.Translation)]=new Slim{FatBlock=panel.Block};
  ThermalSession.Blocks.Add(72,panel);ThermalSession.Link();
  Need(root.RadiatorPanels.Count==1 && panel.RadiatorBase==root && root.CircuitRevision==2,
   "replacement panel changes its base circuit revision and restores the link");
  panel.ObserveChanges();panel.Block.IsFunctional=false;panel.Block.IsFunctional=true;
  Need(root.CircuitRevision==4 && panel.CircuitRevision==2,
   "between-tick extension repair invalidates its connected radiator base");
  ThermalSession.Link();Need(root.CircuitRevision==4,"unchanged panel links do not duplicate the event invalidation");
  panel.Entity=null;panel.StopObservingChanges();panel.Block.IsFunctional=false;panel.Block.Enabled=false;
  Need(root.CircuitRevision==4 && panel.CircuitRevision==2,"removed extension unsubscribes even after GameLogic.Entity is released");
  ThermalSession.Blocks.Clear();
 }
 static void Main(){RuntimeFaultShutdown();RebalancedRatings();ReloadInitialization();OutputLifetime();ReservationSafety();FixedElectricalDemand();FuelBalance();Residuum();FuelMatrix();ControllerAndCommands();CoolingAndAccounting();CircuitShutdown();CircuitAccounting();RadiatorRemoval();Console.WriteLine("PASS: "+checks+" production fuel/mode/controller checks; survival/creative, terminal/server, inventory/conveyors, restore, cooldown and paid-heat accounting");}
}

// Recording engine doubles; the circuit dispatcher and heat transport are injected unchanged.
class ThermalBlock {
 internal Block Block,Entity;
 internal ReactorBlock Generator;
 internal ThermalModel Spec;
 internal ThermalStore Store=new ThermalStore{Radiator=new ThermalRadiatorState()};
 internal ThermalEndpoint Node;
 internal ThermalBlock RadiatorBase;
 internal int CircuitRevision;
 ComponentStack circuitComponents;
 internal void ObserveChanges(){WatchCircuitChanges();}
 internal void StopObservingChanges(){UnwatchCircuitChanges();}
 internal bool preserveInvalidSave;
 int environmentAt;
 internal string Fault {get{return Store.Fault;}set{Store.Fault=value;}}
 internal List<ThermalBlock> RadiatorPanels=new List<ThermalBlock>();
 internal long SourceId {get{return Store.SourceId;}set{Store.SourceId=value;}}
 int outputAccountedAt=-1;
 internal ThermalOutputGrant OutputGrant;
 internal bool CoolingConnected,CoolingPowered;
 internal double RotorLoad,RotorHotC,OutputGrantMW,CoolingRejectedMW;
 internal bool IsCooling {get{return Spec.Kind==ThermalKind.AirCooler || Spec.Kind==ThermalKind.Radiator || Spec.Kind==ThermalKind.HullRadiator || Spec.Kind==ThermalKind.RadiatorPanel;}}
 internal ThermalUnit Unit(){return new ThermalUnit{Id=Block.EntityId,Kind=Spec.Kind,Grade=Spec.Grade,RatingMW=Spec.RatingMW,CoolingMW=Healthy?Spec.CoolingMW:0};}
 internal ThermalEndpoint Endpoint(long owner){Node.Healthy=CircuitReady;Node.Revision=CircuitRevision;return Node;}
 // PRODUCTION_BLOCK_CHECKS
}
static class ThermalPipeJoint {internal static List<ThermalEndpoint> Snapshot(long owner){return new List<ThermalEndpoint>();}}
class ThermalSession {
 internal static Dictionary<long,ThermalBlock> Blocks=new Dictionary<long,ThermalBlock>();
 internal static Dictionary<long,ThermalCircuitCache> circuitGraphs=new Dictionary<long,ThermalCircuitCache>();
 internal void Changed(long grid){InvalidateCircuits(grid);}
 internal static void Link(){LinkRadiators();}
 bool captureFlow=true;
 class FlowView {internal ThermalFlowState State;}
 Dictionary<long,FlowView> flows=new Dictionary<long,FlowView>();
 void ResetColour(long id,int ports,bool healthy){flows[id]=new FlowView{State=new ThermalFlowState{
  EntityId=id,Ports=new byte[ports],Mode=healthy?ThermalFlowMode.Unconnected:ThermalFlowMode.Fault}};}
 internal ThermalFlowMode Colour(long id){return flows[id].State.Mode;}
 internal byte Valves;
 void CaptureIsolation(ThermalNetwork network,List<ThermalEndpoint> endpoints,byte valves){Valves=valves;}
 internal void Step(Reactor source,List<ThermalBlock> machines){
  source.BeginThermalFrame();
  MyAPIGateway.Session.GameplayFrameCounter++;
  foreach(var machine in machines)machine.AccountOutput();
  ResetColour(source.Id,source.CircuitEndpoint.Ports.Length,!source.Motion.Thermal.Faulted);
  foreach(var machine in machines){machine.Entity=machine.Block;machine.OutputGrantMW=0;
   machine.CoolingConnected=false;machine.CoolingRejectedMW=0;
   ResetColour(machine.Block.EntityId,machine.Node.Ports.Length,machine.Healthy);}
  AdvanceLoops(source,new List<Reactor>{source},machines,new HashSet<long>());
  foreach(var machine in machines)if(machine.Generator!=null && machine.OutputGrant==null)machine.Generator.CurrentOutput=0;
 }
 // PRODUCTION_LOOPS
}
