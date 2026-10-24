// Engine doubles for check_reactor_fuel_modes.py. Production members are injected.
using System;
using System.Collections.Generic;
using VRage;
using ArcanePower;
using IMyTerminalBlock = Block;
using IMyReactor = ReactorBlock;
namespace ProtoBuf {
 public class ProtoContractAttribute : Attribute {}
 public class ProtoMemberAttribute : Attribute { public bool OverwriteList; public ProtoMemberAttribute(int id){} }
}
namespace ArcanePower {
 public class ThermalRotorState { public bool Valid(long id){return true;} }
 public class ThermalRadiatorState { public bool Valid(long id){return true;} }
}
class Definition { public string SubtypeName; }
class Slim { public float BuildLevelRatio=1; }
class Logic { public object Component=new ContainmentController(); public T GetAs<T>() where T:class{return Component as T;} }
class ContainmentController {}
class Block {
 public long EntityId,OwnerId;
 public object CubeGrid;
 public bool Closed,IsFunctional=true,HasInventory=true,Accessible=true;
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
 public bool Enabled=true,UseConveyorSystem;
 public float CurrentOutput,PowerOutputMultiplier=1;
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
 public static class Session {public static bool CreativeMode;}
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
// PRODUCTION_STATE
class Reactor {
 ReactorBlock reactor=new ReactorBlock();
 MyCubeBlock Entity;
 NativeReactor nativeReactor=new NativeReactor();
 MotionState Motion=new MotionState{Thermal=new ThermalReactorState()};
 int controllerRingCapacity=4,initializationFrames,networkTick=1,appearanceRefresh;
 float previousControllers=2;
 bool restoreLegacyHardware;
 bool IsLive=true,ThermalVariant=true,motionInitialized=true,thermalRestoreFault,CanOperate=true,ManifoldRigReady=true;
 List<IMyTerminalBlock> fuelSources=new List<IMyTerminalBlock>();
 List<MyInventoryItem> transferItems=new List<MyInventoryItem>();
 const float CooldownHeat=.15f;
 long Id=1;
 int publications;
 static bool ValidTileGrades(int[] grades){return grades!=null && grades.Length==20;}
 void PublishMotion(){publications++;}
 void Part(string name,int pose){}
 void PullTiles(Inventory source,Inventory target){}
 // PRODUCTION_MEMBERS
 static int checks;
 static void Need(bool value,string message){checks++;if(!value)throw new Exception(message);}
 static void Near(double actual,double expected,string message){Need(Math.Abs(actual-expected)<1e-7*Math.Max(1,Math.Abs(expected)),message+": "+actual+" != "+expected);}
 Reactor(){Entity=reactor;reactor.CubeGrid=new object();Motion.RingCount=4;Controllers(true);}
 void Controllers(bool advanced){
  Entity.CurrentAttachedUpgradeModules.Clear();
  for(int i=0;i<2;i++)Entity.CurrentAttachedUpgradeModules[i]=new Attachment{Block=new Block{EntityId=i+2,CubeGrid=reactor.CubeGrid}};
  Entity.CurrentAttachedUpgradeModules[0].Block.BlockDefinition.SubtypeName=advanced?"ArcanePower_AdvancedContainmentController":"ArcanePower_ContainmentController";
 }
 void Mode(ThermalMode mode){Motion.Thermal.Mode=Motion.Thermal.Requested=mode;Motion.Thermal.Deployment=mode==ThermalMode.Brayton?1:0;}
 void Stock(int tier,double amount){reactor.Inventory.Stock[Fuels[tier-1]]=(MyFixedPoint)amount;}
 double Stock(int tier){return (double)reactor.Inventory.GetItemAmount(MyItemType.MakeIngot(Fuels[tier-1]));}
 void Running(){Motion.Core=CorePhase.Running;Motion.CoreTick=1170;Motion.Heat=.8f;Motion.PowerRamp=1;Motion.ReserveMJ=10000;}
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
   r.RefreshFuelCapacity();Need((r.nativeReactor.Capacity>0)==(allowed && mode==ThermalMode.Standalone),"native standalone export matrix");
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
   c=>c.Entity.CurrentAttachedUpgradeModules[0].Block.CubeGrid=new object(),
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
   Need(!r.reactor.Enabled && !r.ThermalCanRun && r.Motion.Thermal.LoopTrip,"last-loop loss disables generation and latches shutdown");
   Need(r.nativeReactor.Capacity==0 && r.Motion.Core==CorePhase.Cooling,"last-loop loss uses normal powered cooldown");
   Near(r.Motion.Thermal.Store.HotMJ+r.Motion.Thermal.Store.WasteMJ+r.Motion.Thermal.AttachedHeatMJ,1700,"pressure trip retains every attached MJ");
   Need(r.Motion.Thermal.Mode==ThermalMode.Brayton && r.Motion.Thermal.Deployment==1,"no standalone fallback or manifold retraction");
   Need(r.Motion.Critical==critical && r.Motion.CriticalSeconds==17,"pressure trip cannot cancel or restart a critical fuse");
   r.ProduceThermal(r.ThermalHeatMW);Near(r.Motion.Thermal.FuelHeatMJ,125,"shutdown cannot admit fresh fuel heat");
   Near(r.Motion.FuelDebt,.25,"pending fuel debt survives trip");
   Need(r.NeedsStorageSupport,"last-loop shutdown retains containment support");
  }
  var old=new Reactor();old.Mode(ThermalMode.Brayton);old.Running();
  old.Motion.Thermal.Store.HotMJ=1000;old.Motion.Thermal.Store.WasteMJ=400;
  old.InitializeThermalRuntime();
  Need(old.Motion.Thermal.LoopVersion==1 && !old.reactor.Enabled,"legacy shared save migrates disabled");
  Near(old.Motion.Thermal.Store.HotMJ+old.Motion.Thermal.Store.WasteMJ,1400,"legacy migration preserves heat");
  var loaded=new Reactor();loaded.Mode(ThermalMode.Brayton);loaded.Motion.Thermal.LoopVersion=1;
  loaded.Motion.Thermal.Loops[0].Connected=true;loaded.Motion.Thermal.Loops[0].Charge=1;
  loaded.Motion.Thermal.Store.WasteMJ=50;loaded.InitializeThermalRuntime();
  Need(loaded.Motion.Thermal.AvailableLoops==0,"reload requires topology validation and paid filling");
  Near(loaded.Motion.Thermal.Store.WasteMJ,50,"reload never trades retained heat for charge");
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
 static void Main(){Residuum();FuelMatrix();ControllerAndCommands();CoolingAndAccounting();CircuitShutdown();Console.WriteLine("PASS: "+checks+" production fuel/mode/controller checks; survival/creative, terminal/server, inventory/conveyors, restore, cooldown and paid-heat accounting");}
}
