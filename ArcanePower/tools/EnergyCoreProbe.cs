using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using ProtoBuf;
using System.Xml.Serialization;
using VRageMath;
using MyDefinitionId=System.Int32;
enum ChargeMode { Auto, Recharge, Discharge }
enum MyJumpDriveStatus { Charging, Ready, Jumping }
enum MyEntityUpdateEnum { NONE, BEFORE_NEXT_FRAME, EACH_FRAME }
interface IMyEntity { long EntityId {get;} Logic GameLogic {get;} }
class MyObjectBuilder_EntityBase {}
class MyModStorageComponent:Dictionary<Guid,string> {}
class MyGameLogicComponent {public IMyTerminalBlock Entity;public MyEntityUpdateEnum NeedsUpdate;public virtual void Init(MyObjectBuilder_EntityBase b){}public virtual void UpdateOnceBeforeFrame(){}public virtual void UpdateBeforeSimulation(){}public virtual void Close(){} }
class Log {public void WriteLine(string s){} }
static class MyLog {public static Log Default=new Log();}
class Slim { public float BuildLevelRatio=1; public IMyCubeBlock FatBlock; }
class Definition { public string SubtypeName; }
class Orientation { public Base6Directions.Direction Forward=Base6Directions.Direction.Forward, Up=Base6Directions.Direction.Up; }
class Logic { public object Value; public T GetAs<T>() where T:class {return Value as T;} }
class Grid { public Dictionary<Vector3I,Slim> Blocks=new Dictionary<Vector3I,Slim>(); public Slim GetCubeBlock(Vector3I p){Slim s;return Blocks.TryGetValue(p,out s)?s:null;} }
class IMyCubeBlock:IMyEntity {static long next;public long EntityId {get;set;}=++next;public Logic GameLogic {get;set;}=new Logic();public MyModStorageComponent Storage=new MyModStorageComponent();public bool Closed,IsFunctional=true;public Slim SlimBlock=new Slim();public Definition BlockDefinition=new Definition();public Orientation Orientation=new Orientation();public Vector3I Position;public Grid CubeGrid; }
class IMyFunctionalBlock:IMyCubeBlock {public bool Enabled=true;}
class IMyTerminalBlock:IMyFunctionalBlock { public bool Access=true;public long OwnerId=1;public bool HasPlayerAccess(long id){return Access;} }
class IMyBatteryBlock:IMyTerminalBlock {public float CurrentStoredPower,MaxStoredPower,CurrentInput,CurrentOutput;public ChargeMode ChargeMode; public MyResourceSourceComponent SourceComp=new MyResourceSourceComponent();public Sink ResourceSink=new Sink();public void RefreshCustomInfo(){} }
class IMyJumpDrive:IMyTerminalBlock {public bool Recharge=true;public float CurrentStoredPower,MaxStoredPower=3;public MyJumpDriveStatus Status;}
class IMyReactor:IMyTerminalBlock {}
class Reactor {public bool NeedsStorageSupport;}
class Sink {public float Max;public void SetMaxRequiredInputByType(int type,float n){Max=n;}public void Update(){} }
class MyResourceSourceComponent { public float Max;public event Action<int,float,MyResourceSourceComponent> MaxOutputChanged;public float MaxOutputUnlimitedByCapacity(int type){return Max;}public void SetMaxOutputByType(int type,float n){float old=Max;Max=n;if(old!=n && MaxOutputChanged!=null)MaxOutputChanged(type,old,this);} }
class Terminal {public List<IMyReactor> Items=new List<IMyReactor>();public List<IMyJumpDrive> Drives=new List<IMyJumpDrive>();public void GetBlocksOfType(List<IMyReactor> list,Func<IMyReactor,bool> filter){foreach(var r in Items)if(filter(r))list.Add(r);} public void GetBlocksOfType(List<IMyJumpDrive> list,Func<IMyJumpDrive,bool> filter){foreach(var r in Drives)if(filter(r))list.Add(r);} }
class Multi {public bool IsServer=true;}
class Helper {public Terminal Terminal=new Terminal();public Terminal GetTerminalSystemForGrid(Grid g){return Terminal;} }
class Session {public bool CreativeMode;}
class Entities {public Dictionary<long,IMyEntity> Items=new Dictionary<long,IMyEntity>();public bool TryGetEntityById(long id,out IMyEntity e){return Items.TryGetValue(id,out e);} }
class Utilities {public string SerializeToXML<T>(T value){var writer=new StringWriter();new XmlSerializer(typeof(T)).Serialize(writer,value);return writer.ToString();}public T SerializeFromXML<T>(string s){return (T)new XmlSerializer(typeof(T)).Deserialize(new StringReader(s));} }
static class MyAPIGateway {public static Multi Multiplayer=new Multi();public static Helper TerminalActionsHelper=new Helper();public static Session Session=new Session();public static Entities Entities=new Entities();public static Utilities Utilities=new Utilities();}
static class EnergySession {public static Dictionary<long,JumpDriveSurge> Drives=new Dictionary<long,JumpDriveSurge>();}
class EnergyCore {
 const string CoreSubtype="ArcanePower_EnergyCore";const int Electricity=0;
 IMyBatteryBlock block,battery;bool initialized=true,emergencyEnabled=true,emergency,changingLimit;
 float reserve=.1f,outputLimit,inputLimit,stored,capacity,transfer,chargeCeiling;int tick=1;string status;
 List<EnergyCore> cells=new List<EnergyCore>(),previousCells=new List<EnergyCore>();List<IMyReactor> reactors=new List<IMyReactor>();
 bool IsController {get {return BaseSubtype(block)==CoreSubtype;}}
 IMyTerminalBlock Entity {get {return block;}}
 const int SurgeDuration=300;int stabilizationTier,upkeepTier;float upkeepMW,replicatedStored=float.NaN;double upkeepDebt;
 EnergyGameplayState gameplay=new EnergyGameplayState();List<IMyJumpDrive> jumpDrives=new List<IMyJumpDrive>();
 static readonly Guid GameplayKey=new Guid("f2451ae5-ea04-47b8-a5f5-59f75583cdb4");
 float StoredEnergy {get {return MyAPIGateway.Multiplayer.IsServer || float.IsNaN(replicatedStored)?block.CurrentStoredPower:replicatedStored;}}
 bool Ready {get {return initialized && Healthy(block) && !emergency && gameplay.RecoveryTicks==0 && block.ChargeMode!=ChargeMode.Recharge;}}
 void ReadSettings(){}
 // METHODS
 // GAMEPLAY METHODS
 static void Need(bool ok,string message){if(!ok)throw new Exception(message);}
 static void Near(float a,float b,string message){Need(Math.Abs(a-b)<.2f,message+" "+a+" != "+b);}
 static EnergyCore Cell(Grid grid,Vector3I pos,string subtype,float capacity,Base6Directions.Direction forward=Base6Directions.Direction.Forward){
  var c=new EnergyCore();c.block=c.battery=new IMyBatteryBlock{CubeGrid=grid,Position=pos,MaxStoredPower=capacity,CurrentStoredPower=capacity*.5f};
  c.block.Orientation.Forward=forward;c.block.BlockDefinition.SubtypeName=subtype;c.block.GameLogic.Value=c;
  c.battery.SourceComp.MaxOutputChanged+=c.ClampNativeOutput;
  grid.Blocks[pos]=new Slim{FatBlock=c.block};return c;
 }
 static IMyTerminalBlock Module(Grid grid,Vector3I pos,string subtype,Base6Directions.Direction forward){
  var b=new IMyTerminalBlock{CubeGrid=grid,Position=pos};b.Orientation.Forward=forward;b.BlockDefinition.SubtypeName=subtype;
  grid.Blocks[pos]=new Slim{FatBlock=b};return b;
 }
 static void Main(){
  var grid=new Grid();var c=Cell(grid,Vector3I.Zero,CoreSubtype,1000);
  c.UpdateBank();Near(c.transfer,10000,"base 10GW discharge");Near(c.chargeCeiling,4000,"base 4GW charging");Near(c.capacity,1000,"base capacity");
  var left=Cell(grid,new Vector3I(-2,0,0),"ArcanePower_EnergyCapacity",10000,Base6Directions.Direction.Right);
  var right=Cell(grid,new Vector3I(2,0,0),"ArcanePower_EnergyCapacityAdvanced",100000,Base6Directions.Direction.Left);
  c.UpdateBank();Need(c.cells.Count==1,"modules require stabilizer");
  var stable=Module(grid,new Vector3I(0,2,0),"ArcanePower_EnergyStabilizer",Base6Directions.Direction.Down);
  var transfer=Module(grid,new Vector3I(0,0,2),"ArcanePower_EnergyTransfer",Base6Directions.Direction.Forward);
  c.UpdateBank();Need(c.cells.Count==2,"standard stabilizer accepts only standard capacity");Near(c.capacity,11000,"fixed capacities aggregate");Near(c.transfer,100000,"transfer tier independent of capacity");Near(c.chargeCeiling,40000,"standard 40GW charging");
  stable.BlockDefinition.SubtypeName+="Advanced";transfer.BlockDefinition.SubtypeName+="Advanced";
  c.UpdateBank();Need(c.cells.Count==3,"advanced supports both capacity tiers");Near(c.capacity,111000,"mixed bank capacity");Near(c.transfer,1000000,"advanced transfer");Near(c.chargeCeiling,200000,"advanced 200GW charging");
  float input=0,output=0;foreach(var cell in c.cells){input+=cell.inputLimit;output+=cell.outputLimit;}
  Near(input,200000,"sum input limits equals independent charging ceiling");Need(output<=1000000.2f,"output cannot exceed bank ceiling");
  float bound=right.outputLimit;right.battery.SourceComp.SetMaxOutputByType(0,1000000);Near(right.battery.SourceComp.Max,bound,"native refresh cannot bypass limit");
  right.battery.SourceComp.SetMaxOutputByType(0,0);Near(right.battery.SourceComp.Max,0,"native off remains off");
  right.block.Enabled=false;right.battery.SourceComp.SetMaxOutputByType(0,1000000);Near(right.battery.SourceComp.Max,0,"disabled cell cannot restore a stale output allocation");
  right.block.Enabled=true;right.block.SlimBlock.BuildLevelRatio=.99f;right.battery.SourceComp.SetMaxOutputByType(0,1000000);Near(right.battery.SourceComp.Max,0,"unfinished cell cannot restore a stale output allocation");
  right.block.SlimBlock.BuildLevelRatio=1;
  foreach(var cell in c.cells)cell.block.CurrentStoredPower=cell.block.MaxStoredPower*.1f;
  c.UpdateBank();foreach(var cell in c.cells)Near(cell.outputLimit,0,"reserve retained");
  left.block.CurrentStoredPower+=.01f;c.UpdateBank();Near(left.outputLimit,.01f*2160,"last interval limited to surplus above reserve");
  var r=new IMyReactor{CubeGrid=grid};r.GameLogic.Value=new Reactor{NeedsStorageSupport=true};MyAPIGateway.TerminalActionsHelper.Terminal.Items.Add(r);
  c.block.ChargeMode=ChargeMode.Recharge;c.UpdateBank();Need(c.emergency && c.block.ChargeMode==ChargeMode.Auto,"emergency visibly overrides Recharge");Need(c.outputLimit>0,"emergency releases reserve");Need(right.block.ChargeMode==ChargeMode.Auto,"bank mode propagated");
  c.emergencyEnabled=false;c.block.ChargeMode=ChargeMode.Recharge;c.UpdateBank();Need(!c.emergency && c.block.ChargeMode==ChargeMode.Recharge,"disabled emergency respects Recharge");Near(c.battery.SourceComp.Max,0,"Recharge does not discharge");
  c.block.ChargeMode=ChargeMode.Auto;
  right.block.Orientation.Forward=Base6Directions.Direction.Right;c.UpdateBank();Need(c.cells.Count==2,"wrong-facing capacity rejected");
  Near(right.inputLimit,0,"removed cell input revoked by core update");Near(right.outputLimit,0,"removed cell output revoked by core update");
  right.block.Orientation.Forward=Base6Directions.Direction.Left;right.block.Access=false;c.UpdateBank();Need(c.cells.Count==2,"inaccessible capacity rejected");
  right.block.Access=true;right.block.SlimBlock.BuildLevelRatio=.99f;c.UpdateBank();Need(c.cells.Count==2,"unfinished capacity rejected");
  right.block.SlimBlock.BuildLevelRatio=1;stable.Enabled=false;c.UpdateBank();Need(c.cells.Count==1,"disabled stabilizer isolates expansions");
  Near(left.inputLimit,0,"stabilizer loss immediately isolates previous members");
  stable.Enabled=true;c.UpdateBank();Need(c.cells.Count==3,"restored modules reconnect");
  c.block.Enabled=false;c.UpdateBank();foreach(var cell in c.cells){Near(cell.inputLimit,0,"disabled core closes bank input");Near(cell.outputLimit,0,"disabled core closes bank output");}
  c.block.Enabled=true;c.UpdateBank();
  // Clients maintain native local resource limits but never author charge modes.
  MyAPIGateway.Multiplayer.IsServer=false;c.emergencyEnabled=true;c.block.ChargeMode=ChargeMode.Recharge;right.block.ChargeMode=ChargeMode.Discharge;
  c.UpdateBank();Need(c.block.ChargeMode==ChargeMode.Recharge && right.block.ChargeMode==ChargeMode.Discharge,"client does not author emergency or module modes");
  MyAPIGateway.Multiplayer.IsServer=true;c.UpdateBank();Need(c.block.ChargeMode==ChargeMode.Auto && right.block.ChargeMode==ChargeMode.Auto,"server applies emergency and propagates modes");
  float charge=right.block.CurrentStoredPower;right.ApplyLimits(0,0);Near(right.block.CurrentStoredPower,charge,"disconnect never copies or destroys stored energy");
  grid.Blocks.Remove(Vector3I.Zero);Need(right.FindController()==null,"grid separation isolates capacity");
  // Every cardinal controller orientation yields two unique perpendicular side sockets.
  foreach(Base6Directions.Direction f in Enum.GetValues(typeof(Base6Directions.Direction)))
   foreach(Base6Directions.Direction u in Enum.GetValues(typeof(Base6Directions.Direction))){
    var fv=Base6Directions.GetIntVector(f);var uv=Base6Directions.GetIntVector(u);Vector3I side;Vector3I.Cross(ref fv,ref uv,out side);
    if((side.X*side.X+side.Y*side.Y+side.Z*side.Z)==0)continue;
    Need((side.X*side.X+side.Y*side.Y+side.Z*side.Z)==1 && side!=-side,"unique rotated side sockets");
   }
  // Full-height pillars must remain upright in the core's local frame.
  foreach(Base6Directions.Direction f in Enum.GetValues(typeof(Base6Directions.Direction)))
   foreach(Base6Directions.Direction u in Enum.GetValues(typeof(Base6Directions.Direction))){
    var fv=Base6Directions.GetIntVector(f);var uv=Base6Directions.GetIntVector(u);Vector3I side;Vector3I.Cross(ref fv,ref uv,out side);
    if(side==Vector3I.Zero)continue;
    var g=new Grid();var pc=Cell(g,Vector3I.Zero,CoreSubtype+"_Pillar",1000,f);pc.block.Orientation.Up=u;
    var cap=Cell(g,side*2,"ArcanePower_EnergyCapacityAdvanced_Pillar",100000,Base6Directions.GetDirection(-side));cap.block.Orientation.Up=u;
    var st=Module(g,fv*2,"ArcanePower_EnergyStabilizerAdvanced_Pillar",Base6Directions.GetDirection(-fv));st.Orientation.Up=u;
    var tr=Module(g,-fv*2,"ArcanePower_EnergyTransferAdvanced_Pillar",f);tr.Orientation.Up=u;
    pc.UpdateBank();Need(pc.cells.Count==2,"upright rotated pillar bank");Near(pc.capacity,101000,"pillar capacity");Near(pc.transfer,1000000,"pillar transfer");
    Need(cap.FindController()==pc,"pillar reverse controller lookup");
    Need(pc.IsModuleRunning(st),"charged accepted stabilizer runs");
    Need(pc.IsModuleRunning(tr),"accepted transfer lights");
    tr.Access=false;Need(!pc.IsModuleRunning(tr),"inaccessible transfer dark");tr.Access=true;
    g.Blocks.Remove(fv*2);Need(!pc.IsModuleRunning(tr),"transfer requires stabilizer");g.Blocks[fv*2]=new Slim{FatBlock=st};
    st.Enabled=false;Need(!pc.IsModuleRunning(st),"disabled fan stops");st.Enabled=true;
    st.SlimBlock.BuildLevelRatio=.99f;Need(!pc.IsModuleRunning(st),"unfinished fan stops");st.SlimBlock.BuildLevelRatio=1;
    st.Access=false;Need(!pc.IsModuleRunning(st),"inaccessible fan stops");st.Access=true;
    st.Orientation.Forward=f;Need(!pc.IsModuleRunning(st),"wrong-facing fan stops");st.Orientation.Forward=Base6Directions.GetDirection(-fv);
    pc.block.Enabled=false;Need(!pc.IsModuleRunning(st),"disabled core stops fan");pc.block.Enabled=true;
    pc.block.SlimBlock.BuildLevelRatio=.99f;Need(!pc.IsModuleRunning(st),"unfinished core stops fan");pc.block.SlimBlock.BuildLevelRatio=1;
    pc.block.CurrentStoredPower=cap.block.CurrentStoredPower=0;Need(!pc.IsModuleRunning(st),"empty bank stops fan");
    pc.block.CurrentInput=1;Need(pc.IsModuleRunning(st),"charging empty bank runs fan");pc.block.CurrentInput=0;
    MyAPIGateway.Multiplayer.IsServer=false;pc.replicatedStored=300;
    Need(pc.IsModuleRunning(st),"fan uses replicated charge on client");
    pc.replicatedStored=float.NaN;MyAPIGateway.Multiplayer.IsServer=true;
    pc.block.CurrentStoredPower=500;

    cap.block.Orientation.Up=Base6Directions.GetDirection(-uv);pc.UpdateBank();Need(pc.cells.Count==1,"upside-down pillar rejected");cap.block.Orientation.Up=u;
    cap.block.BlockDefinition.SubtypeName="ArcanePower_EnergyCapacityAdvanced";pc.UpdateBank();Need(pc.cells.Count==1,"compact and pillar banks cannot mix");cap.block.BlockDefinition.SubtypeName+="_Pillar";
    g.Blocks.Remove(fv*2);st.Position=uv*2;g.Blocks[st.Position]=new Slim{FatBlock=st};pc.UpdateBank();Need(pc.cells.Count==1,"pillar modules do not attach to the roof");
   }
  // Field scale must remain uniform, bounded and independent of last pose.
  Matrix rest=Matrix.CreateFromYawPitchRoll(.4f,.2f,-.3f);rest.Translation=new Vector3(2,3,-4);
  float previous=0;
  foreach(float fraction in new[]{-1f,0f,.25f,.5f,.75f,1f,2f}){
   Matrix pose=StoredFieldPose(rest,fraction,.7f);float radius=pose.Right.Length();
   Need(pose.Translation==rest.Translation,"field pivot fixed");
   Need(radius>=previous-.00001f && radius>=.17999f && radius<=1.00001f,"field monotonic bounded growth");previous=radius;
   Need(Math.Abs(pose.Up.Length()-radius)<.00001f && Math.Abs(pose.Backward.Length()-radius)<.00001f,"uniform spherical scale");
  }
  Need(Math.Abs(StoredFieldPose(rest,0,0).Right.Length()-.18f)<.00001f,"empty field seed");
  Need(Math.Abs(StoredFieldPose(rest,1,0).Right.Length()-1)<.00001f,"full field authored size");
  Need(Math.Abs(StoredFieldPose(rest,.5f,0).Right.Length()-.59f)<.00001f,"half-charge field");
  CheckUniversalBays();
  CheckGameplay();
  CheckBatchSurge();
  CheckSurgeWindow();
  Console.WriteLine("PASS energy bank: tiers, allocation, native clamp, reserve boundary, emergency/modes, orientation, access, construction, detach/split, charge preservation");
 }
 static void CheckUniversalBays(){
  int layouts=0;
  foreach(Base6Directions.Direction f in Enum.GetValues(typeof(Base6Directions.Direction)))
   foreach(Base6Directions.Direction u in Enum.GetValues(typeof(Base6Directions.Direction))){
    var fv=Base6Directions.GetIntVector(f);var uv=Base6Directions.GetIntVector(u);Vector3I side;Vector3I.Cross(ref fv,ref uv,out side);
    if(side==Vector3I.Zero)continue;
    var bays=new[]{fv,-fv,side,-side};
    for(int stableBay=0;stableBay<4;stableBay++)
     for(int transferBay=0;transferBay<4;transferBay++){
      if(stableBay==transferBay)continue;
      for(int tier=1;tier<=2;tier++)
       for(int swap=0;swap<2;swap++){
        var grid=new Grid();var core=Cell(grid,Vector3I.Zero,CoreSubtype+"_Pillar",1000,f);core.block.Orientation.Up=u;
        string suffix=tier==2?"Advanced_Pillar":"_Pillar";
        var stable=Module(grid,bays[stableBay]*2,"ArcanePower_EnergyStabilizer"+suffix,Base6Directions.GetDirection(-bays[stableBay]));stable.Orientation.Up=u;
        var transfer=Module(grid,bays[transferBay]*2,"ArcanePower_EnergyTransfer"+suffix,Base6Directions.GetDirection(-bays[transferBay]));transfer.Orientation.Up=u;
        int index=0;EnergyCore standard=null,advanced=null;
        for(int bay=0;bay<4;bay++){
         if(bay==stableBay || bay==transferBay)continue;
         bool high=index++==swap;
         var cell=Cell(grid,bays[bay]*2,"ArcanePower_EnergyCapacity"+(high?"Advanced_Pillar":"_Pillar"),high?100000:10000,Base6Directions.GetDirection(-bays[bay]));cell.block.Orientation.Up=u;
         Need(cell.FindController()==core,"reverse lookup works from every bay");
         if(high)advanced=cell;else standard=cell;
        }
        core.UpdateBank();
        Need(core.cells.Contains(standard) && core.cells.Contains(advanced)==(tier==2),"any bay accepts supported capacity tiers");
        Near(core.capacity,tier==2?111000:11000,"capacity aggregates across universal bays");
        Near(core.transfer,tier==2?1000000:100000,"transfer tier works from any bay");Near(core.chargeCeiling,tier==2?200000:40000,"charging tier works from any bay");
        Need(core.IsModuleRunning(stable) && core.IsModuleRunning(transfer),"module activity follows universal attachment");
        stable.Enabled=false;
        Need(!core.IsModuleRunning(transfer),"transfer immediately loses activity without a stabilizer in any bay");
        core.UpdateBank();Need(core.cells.Count==1,"stabilizer loss disconnects all bay positions");
        Near(standard.inputLimit,0,"removed capacity allocation revoked");Near(advanced.inputLimit,0,"unsupported advanced allocation revoked");
        layouts++;
       }
     }
   }
  var g=new Grid();var c=Cell(g,Vector3I.Zero,CoreSubtype+"_Pillar",1000);
  var lowStable=Module(g,new Vector3I(0,0,-2),"ArcanePower_EnergyStabilizer_Pillar",Base6Directions.Direction.Backward);
  var highStable=Module(g,new Vector3I(0,0,2),"ArcanePower_EnergyStabilizerAdvanced_Pillar",Base6Directions.Direction.Forward);
  Module(g,new Vector3I(-2,0,0),"ArcanePower_EnergyTransfer_Pillar",Base6Directions.Direction.Right);
  Module(g,new Vector3I(2,0,0),"ArcanePower_EnergyTransferAdvanced_Pillar",Base6Directions.Direction.Left);
  c.UpdateBank();Need(c.stabilizationTier==2,"strongest stabilizer wins");Near(c.transfer,1000000,"duplicate transfer tiers do not stack");
  highStable.Enabled=false;c.UpdateBank();Need(c.stabilizationTier==1,"fallback to remaining stabilizer");Near(c.transfer,100000,"strongest transfer remains bounded by stabilization");Near(c.chargeCeiling,40000,"charging falls back with stabilization");
  lowStable.Enabled=false;c.UpdateBank();Near(c.transfer,10000,"no stabilization restores base transfer");Near(c.chargeCeiling,4000,"no stabilization restores base charging");
  var full=new Grid();var bank=Cell(full,Vector3I.Zero,CoreSubtype+"_Pillar",1000);
  Module(full,new Vector3I(0,0,-2),"ArcanePower_EnergyStabilizerAdvanced_Pillar",Base6Directions.Direction.Backward);
  Cell(full,new Vector3I(0,0,2),"ArcanePower_EnergyCapacityAdvanced_Pillar",100000);
  var b=Cell(full,new Vector3I(-2,0,0),"ArcanePower_EnergyCapacityAdvanced_Pillar",100000,Base6Directions.Direction.Right);
  Cell(full,new Vector3I(2,0,0),"ArcanePower_EnergyCapacityAdvanced_Pillar",100000,Base6Directions.Direction.Left);
  bank.UpdateBank();Need(bank.cells.Count==4,"three capacity modules can share a stabilizer");Near(bank.capacity,301000,"all supported physical cells aggregate");
  float input=0;foreach(var cell in bank.cells)input+=cell.inputLimit;Near(input,4000,"extra capacity does not multiply charging ceiling");
  b.block.Access=false;bank.UpdateBank();Need(bank.cells.Count==3,"universal bays preserve ownership checks");Near(b.inputLimit,0,"lost access revokes capacity allocation");
  Console.WriteLine("PASS universal bays: "+layouts+" rotated tier/layout combinations, module activity, duplicate tiers, three capacities and revocation");
 }
 static IMyJumpDrive Drive(Grid grid){
  var d=new IMyJumpDrive{CubeGrid=grid};var logic=new JumpDriveSurge{Entity=d};d.GameLogic.Value=logic;
  logic.Init(null);logic.UpdateOnceBeforeFrame();MyAPIGateway.Entities.Items[d.EntityId]=d;
  MyAPIGateway.TerminalActionsHelper.Terminal.Drives.Add(d);return d;
 }
 static EnergyCore BatchCore(out Grid grid){
  MyAPIGateway.TerminalActionsHelper.Terminal.Items.Clear();MyAPIGateway.TerminalActionsHelper.Terminal.Drives.Clear();
  MyAPIGateway.Entities.Items.Clear();EnergySession.Drives.Clear();
  grid=new Grid();var bank=Cell(grid,Vector3I.Zero,CoreSubtype,1000);bank.InitializeGameplay(false);bank.UpdateBank();return bank;
 }
 static void FinishBatch(EnergyCore bank,int limit=1000){
  for(int step=0;step<limit && bank.gameplay.SurgeTicks>0;step++){
   bank.UpdateBank();bank.UpdateSurge();
   if(bank.gameplay.SurgeTicks==0)break;
   for(int frame=0;frame<10;frame++){
    bank.UpdateRecovery();foreach(var drive in EnergySession.Drives.Values)drive.UpdateBeforeSimulation();
   }
  }
  Need(bank.gameplay.SurgeTicks==0,"batch finishes within available transfer time");
 }
 static void CheckSurgeWindow(){
  foreach(int tier in new[]{0,1,2})foreach(int count in new[]{1,12,64}){
   Grid grid;var bank=BatchCore(out grid);bank.block.CurrentStoredPower=1000;
   if(tier>0){
    string suffix=tier==2?"Advanced":"";
    Module(grid,new Vector3I(0,2,0),"ArcanePower_EnergyStabilizer"+suffix,Base6Directions.Direction.Down);
    Module(grid,new Vector3I(0,0,2),"ArcanePower_EnergyTransfer"+suffix,Base6Directions.Direction.Forward);
   }
   bank.UpdateBank();bank.block.CurrentOutput=Math.Min(bank.transfer,10000);
   var drives=new List<IMyJumpDrive>();double charge=0;
   for(int i=0;i<count;i++){
    var drive=Drive(grid);drive.MaxStoredPower=i%2==0?3:6;drive.CurrentStoredPower=i%3;
    charge+=drive.MaxStoredPower-drive.CurrentStoredPower;drives.Add(drive);
   }
   float before=bank.block.CurrentStoredPower,normalInput=bank.inputLimit,normalOutput=bank.outputLimit;
   bank.RequestSurge();Need(bank.gameplay.SurgeDriveCount==count && bank.gameplay.SurgeTicks==300,"all tiers accept a five-second batch");
   Need(Math.Abs(bank.gameplay.SurgeRate-charge/.9*720*1.01)<.02,"boost scales with actual deficits and modded drive capacities");
   for(int step=0;step<30 && bank.gameplay.SurgeTicks>0;step++){
    bank.UpdateBank();bank.UpdateSurge();
    if(step==0){
     foreach(var drive in drives)Need(drive.CurrentStoredPower>0,"selected drives charge concurrently");
     Near(bank.inputLimit,normalInput,"surge leaves ordinary input unchanged");
     Near(bank.outputLimit,normalOutput,"dedicated surge allowance leaves ordinary grid throughput available");
    }
   }
   Need(bank.gameplay.SurgeTicks==0 && bank.gameplay.SurgeCompleted==count,"five-second completion tier="+tier+" count="+count+" ticks="+bank.gameplay.SurgeTicks+" completed="+bank.gameplay.SurgeCompleted);
   foreach(var drive in drives)Need(drive.CurrentStoredPower==drive.MaxStoredPower,"every accepted drive reaches full charge");
   Need(Math.Abs((before-bank.block.CurrentStoredPower)*.9-charge)<.05,"five-second batch pays for all delivered energy");
   Need(bank.block.CurrentStoredPower>=100 && bank.gameplay.SurgeRate==0,"reserve protected and temporary boost removed on completion");
   bank.UpdateBank();Near(bank.inputLimit,normalInput,"normal input restored after surge");
   Need(bank.outputLimit<=normalOutput,"normal output ceiling restored after surge");
  }
  Console.WriteLine("PASS five-second surge: all transfer tiers, mixed capacities/deficits, 1/12/64 drives, concurrent grid output, conservation and boost removal");
 }
 static void CheckBatchSurge(){
  Grid grid;var bank=BatchCore(out grid);bank.block.CurrentStoredPower=110;
  var expensive=Drive(grid);expensive.MaxStoredPower=6;expensive.CurrentStoredPower=1;
  var medium=Drive(grid);var small=Drive(grid);small.CurrentStoredPower=2;var second=Drive(grid);second.CurrentStoredPower=1;
  var full=Drive(grid);full.CurrentStoredPower=full.MaxStoredPower;
  var held=Drive(grid);held.GameLogic.GetAs<JumpDriveSurge>().StartRecovery(60);
  double cost;int eligible=bank.AffordableDrives(bank.jumpDrives,out cost);
  Need(eligible==4 && bank.jumpDrives.Count==3,"largest affordable subset excludes full/recovering drives");
  Need(bank.jumpDrives[0]==small && bank.jumpDrives[1]==second && bank.jumpDrives[2]==medium,"smallest deficits charged first");
  Need(Math.Abs(cost-6/.9)<.00001,"preview includes the full 90 percent efficiency cost");
  var text=new StringBuilder();bank.AppendGameplayInfo(text);Need(text.ToString().Contains("Surge batch: 3 / 4 available drives"),"terminal previews affordable batch");
  float before=bank.block.CurrentStoredPower;bank.RequestSurge();Need(bank.gameplay.SurgeDriveCount==3,"surge accepts previewed subset");
  Need(bank.gameplay.SurgeRecoveryTicks==10800,"three-drive bare recovery is 180 seconds");
  FinishBatch(bank);
  Need(small.CurrentStoredPower==3 && second.CurrentStoredPower==3 && medium.CurrentStoredPower==3,"selected subset fills completely");
  Need(expensive.CurrentStoredPower==1,"unaffordable drive receives no partial surge");
  Need(Math.Abs((before-bank.block.CurrentStoredPower)*.9-6)<.005 && bank.block.CurrentStoredPower>=100,"batch pays efficiency and protects reserve");
  Need(bank.gameplay.RecoveryTicks==10800,"full scaled recovery starts when batch ends");
  foreach(var d in new[]{small,second,medium})Need(!d.GameLogic.GetAs<JumpDriveSurge>().Claim(999),"every selected drive owns cooldown");

  bank=BatchCore(out grid);bank.block.CurrentStoredPower=103;var empty=Drive(grid);bank.RequestSurge();
  Need(bank.gameplay.SurgeTicks==0 && bank.gameplay.RecoveryTicks==0 && empty.CurrentStoredPower==0,"cannot afford an entire drive: no debit or cooldown");
  var near=Drive(grid);near.CurrentStoredPower=2.5f;bank.RequestSurge();FinishBatch(bank);
  Need(near.CurrentStoredPower==3 && empty.CurrentStoredPower==0,"only affordable near-full drive selected");
  bank=BatchCore(out grid);bank.block.CurrentStoredPower=104;var first=Drive(grid);Drive(grid);
  MyAPIGateway.TerminalActionsHelper.Terminal.Drives.Reverse();bank.RequestSurge();
  Need(bank.gameplay.SurgeTargets.Count==1 && bank.gameplay.SurgeTargets[0].DriveId==first.EntityId,"equal deficits use stable entity IDs");

  bank=BatchCore(out grid);var batch=new List<IMyJumpDrive>();for(int i=0;i<12;i++)batch.Add(Drive(grid));
  bank.RequestSurge();Need(bank.gameplay.SurgeDriveCount==12 && bank.gameplay.SurgeTicks==300,"large batch targets five seconds");
  before=bank.block.CurrentStoredPower;bank.block.CurrentOutput=4000;float boost=bank.gameplay.SurgeRate;
  for(int step=0;step<30 && bank.gameplay.SurgeTicks>0;step++){
   float previous=bank.block.CurrentStoredPower;bank.UpdateBank();bank.UpdateSurge();
   Need(previous-bank.block.CurrentStoredPower<=boost/21600f+.0001f,"batch debit stays within its temporary discharge allowance");
   if(step==0)foreach(var d in batch)Need(d.CurrentStoredPower>0,"batch charges drives concurrently");
   if(bank.gameplay.SurgeTicks==0)break;
   for(int frame=0;frame<10;frame++){
    bank.UpdateRecovery();foreach(var component in EnergySession.Drives.Values)component.UpdateBeforeSimulation();
   }
  }
  Need(bank.gameplay.SurgeTicks==0 && bank.gameplay.SurgeCompleted==12,"all large-batch drives finish in five seconds despite grid load");
  foreach(var d in batch)Need(d.CurrentStoredPower==3,"large batch fully fills every drive");
  Need(Math.Abs((before-bank.block.CurrentStoredPower)*.9-36)<.02,"boosted throughput conserves batch energy");
  Need(bank.gameplay.RecoveryTicks==27000,"twelve drives retain 450 seconds of post-surge recovery");

  bank=BatchCore(out grid);var lost=Drive(grid);var split=Drive(grid);var surviving=Drive(grid);
  bank.RequestSurge();bank.UpdateSurge();float lostCharge=lost.CurrentStoredPower,splitCharge=split.CurrentStoredPower;
  lost.Access=false;split.CubeGrid=new Grid();var late=Drive(grid);FinishBatch(bank);
  Need(lost.CurrentStoredPower==lostCharge && split.CurrentStoredPower==splitCharge,"access/grid loss stops only affected drives");
  Need(surviving.CurrentStoredPower==3 && late.CurrentStoredPower==0,"survivors finish without adding later arrivals");
  Need(bank.gameplay.SurgeCompleted==1 && bank.gameplay.RecoveryTicks==10800,"partial cancellation does not reduce accepted-batch cooldown");

  bank=BatchCore(out grid);Module(grid,new Vector3I(0,2,0),"ArcanePower_EnergyStabilizerAdvanced",Base6Directions.Direction.Down);bank.UpdateBank();
  Need(bank.BatchRecoveryDuration(1)==3600 && bank.BatchRecoveryDuration(2)==4500 && bank.BatchRecoveryDuration(4)==6300 && bank.BatchRecoveryDuration(8)==9900,"approved advanced cooldown examples");
  batch.Clear();for(int i=0;i<8;i++)batch.Add(Drive(grid));bank.RequestSurge();bank.block.Enabled=false;bank.UpdateSurge();
  Need(bank.gameplay.RecoveryTicks==9900,"interruption keeps original batch penalty");
  bank.SaveGameplay();bank.InitializeGameplay(true);Need(bank.gameplay.RecoveryTicks==9900,"bank cooldown above old limit survives reload");
  var restored=new JumpDriveSurge{Entity=batch[0]};restored.Init(null);restored.UpdateOnceBeforeFrame();
  for(int i=0;i<7801;i++)restored.UpdateBeforeSimulation();Need(!restored.Claim(999),"drive cooldown above old limit survives reload");
  for(int i=7801;i<9900;i++)restored.UpdateBeforeSimulation();Need(restored.Claim(999),"drive available after full scaled cooldown");restored.Release(999);

  bank=BatchCore(out grid);batch.Clear();for(int i=0;i<12;i++)batch.Add(Drive(grid));bank.RequestSurge();bank.UpdateSurge();
  batch[0].CurrentStoredPower=3;bank.UpdateSurge();Need(bank.gameplay.SurgeCompleted==1,"native recharge can finish a selected drive early");
  bank.SaveGameplay();int remaining=bank.gameplay.SurgeTicks;int accepted=bank.gameplay.SurgeDriveCount;
  foreach(var d in batch){d.GameLogic.GetAs<JumpDriveSurge>().SaveRecovery();var logic=new JumpDriveSurge{Entity=d};logic.Init(null);d.GameLogic.Value=logic;if(d!=batch[1])logic.UpdateOnceBeforeFrame();}
  bank.gameplay=new EnergyGameplayState();bank.InitializeGameplay(true);
  Need(bank.gameplay.SurgeTargets.Count==12 && bank.gameplay.SurgeTicks==remaining && bank.gameplay.SurgeDriveCount==accepted,"active batch persists all targets and remaining timing");
  before=bank.block.CurrentStoredPower;bank.UpdateSurge();Need(bank.block.CurrentStoredPower==before && bank.gameplay.SurgeTicks==remaining,"reload waits for uninitialized drive components");
  Need(!batch[0].GameLogic.GetAs<JumpDriveSurge>().ResumeClaim(999),"already-finished drive stays claimed during resumed batch");
  batch[1].GameLogic.GetAs<JumpDriveSurge>().UpdateOnceBeforeFrame();FinishBatch(bank);
  Need(bank.gameplay.SurgeCompleted==12 && bank.gameplay.RecoveryTicks==27000,"resumed batch finishes without changing its penalty");
  foreach(var d in batch)Need(!d.GameLogic.GetAs<JumpDriveSurge>().Claim(999),"resumed batch preserves every drive's recovery");

  bank=BatchCore(out grid);var legacy=Drive(grid);
  bank.block.Storage[GameplayKey]=MyAPIGateway.Utilities.SerializeToXML(new EnergyGameplayState{EntityId=bank.block.EntityId,DriveId=legacy.EntityId,SurgeTicks=600,RecoveryTicks=7800,SurgeRate=1212});
  bank.InitializeGameplay(true);Need(bank.gameplay.SurgeTargets.Count==1 && bank.gameplay.SurgeRecoveryTicks==7200,"legacy single-drive saves migrate with recovery intact");FinishBatch(bank);Need(legacy.CurrentStoredPower==3,"legacy surge resumes");

  var snapshot=new EnergyGameplayState{EntityId=bank.block.EntityId,SurgeDriveCount=10000,SurgeTicks=600,RecoveryTicks=99900};
  for(int i=1;i<=10000;i++)snapshot.SurgeTargets.Add(new EnergySurgeTarget{DriveId=i});
  using(var stream=new MemoryStream()){
   var wire=ProtoBuf.Meta.RuntimeTypeModel.Create();wire.Serialize(stream,snapshot);Need(stream.Length<256,"large batch snapshots fit existing packet limit");stream.Position=0;
   var client=(EnergyGameplayState)wire.Deserialize(stream,null,typeof(EnergyGameplayState));Need(client.SurgeDriveCount==10000 && client.SurgeTargets.Count==0,"clients receive summary without server target list");
  }
  Console.WriteLine("PASS batch surge: affordable subsets, 90% cost, boosted throughput, scaled cooldown, cancellation, reload/legacy migration and compact native protobuf snapshots");
 }
 static void CheckGameplay(){
  MyAPIGateway.TerminalActionsHelper.Terminal.Items.Clear();MyAPIGateway.TerminalActionsHelper.Terminal.Drives.Clear();
  var grid=new Grid();var c=Cell(grid,Vector3I.Zero,CoreSubtype,1000);c.InitializeGameplay(false);c.UpdateBank();
  Near(UpkeepPower(1000,1000,0),600,"full bare upkeep");Near(UpkeepPower(500,1000,0),150,"half fill costs quarter power");
  Near(UpkeepPower(1000,1000,1),300,"standard halves upkeep");Near(UpkeepPower(1000,1000,2),150,"advanced quarters upkeep");
  Near(UpkeepPower(0,1000,0),0,"empty has no upkeep");
  c.block.CurrentStoredPower=1000;Near(c.RequiredInput(),0,"full idle cell has no charging demand");float original=c.block.CurrentStoredPower;c.UpdateUpkeep();Need(c.block.CurrentStoredPower<original,"upkeep consumes charge");
  Need(c.RequiredInput()>0,"direct debit reopens charging without native full flag");
  c.block.Enabled=false;original=c.block.CurrentStoredPower;c.UpdateUpkeep();Need(c.block.CurrentStoredPower<original,"disabled cell still loses charge");Near(c.RequiredInput(),0,"disabled cell cannot charge");c.block.Enabled=true;
  c.block.ChargeMode=ChargeMode.Discharge;Near(c.RequiredInput(),0,"Discharge cannot charge");c.block.ChargeMode=ChargeMode.Auto;
  c.upkeepDebt=-.001;c.upkeepMW=0;c.block.CurrentStoredPower=.01f;original=c.block.CurrentStoredPower;c.UpdateUpkeep();Need(c.block.CurrentStoredPower<=original,"rounding debt never creates energy");
  c.block.CurrentStoredPower=1000;MyAPIGateway.Multiplayer.IsServer=false;c.UpdateUpkeep();Near(c.block.CurrentStoredPower,1000,"clients never debit upkeep");MyAPIGateway.Multiplayer.IsServer=true;
  MyAPIGateway.Session.CreativeMode=true;c.UpdateUpkeep();Near(c.block.CurrentStoredPower,1000,"creative does not leak");MyAPIGateway.Session.CreativeMode=false;
  c.upkeepDebt=0;c.block.CurrentStoredPower=500;c.UpdateBank();var drive=Drive(grid);
  c.RequestSurge();Need(c.gameplay.SurgeTicks==300,"base surge five seconds");Need(!c.Ready,"surge starts bank recovery");
  Need(!drive.GameLogic.GetAs<JumpDriveSurge>().Claim(999),"drive cooldown blocks another bank");
  float start=c.block.CurrentStoredPower;
  for(int i=0;i<30 && c.gameplay.SurgeTicks>0;i++){c.UpdateBank();c.UpdateSurge();}
  Need(drive.CurrentStoredPower==3,"surge fills native drive within five seconds: "+drive.CurrentStoredPower.ToString("R")+" "+c.gameplay.Result);
  Need(start-c.block.CurrentStoredPower>=drive.CurrentStoredPower,"surge cannot create energy");
  Need(Math.Abs((start-c.block.CurrentStoredPower)*.9f-3)<.005,"surge has 90 percent efficiency");
  Need(c.block.CurrentStoredPower>=100,"surge protects reserve");
  c.gameplay.RecoveryTicks=0;drive.CurrentStoredPower=0;c.RequestSurge();Need(c.gameplay.SurgeTicks==0,"drive recovery prevents changing bank");
  for(int i=0;i<7800;i++)drive.GameLogic.GetAs<JumpDriveSurge>().UpdateBeforeSimulation();
  drive.Enabled=false;Drive(new Grid());c.RequestSurge();Need(c.gameplay.SurgeTicks==0,"cross-grid target rejected");drive.Enabled=true;
  drive.Access=false;c.RequestSurge();Need(c.gameplay.SurgeTicks==0,"foreign target rejected");drive.Access=true;
  drive.Recharge=false;c.RequestSurge();Need(c.gameplay.SurgeTicks==0,"recharge-disabled drive rejected");drive.Recharge=true;
  drive.Status=MyJumpDriveStatus.Jumping;c.RequestSurge();Need(c.gameplay.SurgeTicks==0,"jumping drive rejected");drive.Status=MyJumpDriveStatus.Charging;
  c.block.ChargeMode=ChargeMode.Recharge;c.RequestSurge();Need(c.gameplay.SurgeTicks==0,"Recharge bank cannot surge");c.block.ChargeMode=ChargeMode.Auto;
  c.block.CurrentStoredPower=100;c.RequestSurge();Need(c.gameplay.SurgeTicks==0,"reserve cannot fund surge");
  c.UpdateUpkeep();Need(c.block.CurrentStoredPower<100,"reserve does not bypass passive loss");
  c.block.CurrentStoredPower=500;c.RequestSurge();Need(c.gameplay.SurgeTicks>0,"second surge after recovery");
  drive.CubeGrid=new Grid();original=c.block.CurrentStoredPower;c.UpdateSurge();Need(c.gameplay.SurgeTicks==0 && c.block.CurrentStoredPower==original,"split cancels surge without spending");drive.CubeGrid=grid;
  var saved=drive.Storage[JumpDriveSurge.RecoveryKey];var restored=new JumpDriveSurge{Entity=drive};restored.Init(null);restored.UpdateOnceBeforeFrame();Need(!restored.Claim(999),"drive recovery survives reload");
  drive.Storage[JumpDriveSurge.RecoveryKey]="999:7200";var copied=new JumpDriveSurge{Entity=drive};copied.Init(null);copied.UpdateOnceBeforeFrame();Need(copied.Claim(999),"copied identity does not inherit cooldown");copied.Release(999);drive.Storage[JumpDriveSurge.RecoveryKey]=saved;
  c.gameplay.RecoveryTicks=0;c.RequestBurst();Need(c.gameplay.BurstTicks==600,"burst lasts ten seconds");Near(c.outputLimit,20000,"burst doubles base discharge");Near(c.inputLimit,4000,"burst leaves charge ceiling unchanged");
  c.RequestSurge();Need(c.gameplay.SurgeTicks==0,"burst and surge share recovery");
  c.SaveGameplay();var state=c.block.Storage[GameplayKey];c.gameplay=new EnergyGameplayState();c.InitializeGameplay(true);Need(c.gameplay.BurstTicks==600 && c.gameplay.RecoveryTicks>0,"bank recovery and burst survive reload");
  for(int i=0;i<600;i++)c.UpdateRecovery();Near(c.outputLimit,10000,"burst ends at normal ceiling");Need(c.gameplay.RecoveryTicks>0,"recovery continues after burst");
  c.gameplay.RecoveryTicks=0;c.RequestBurst();c.block.Enabled=false;c.UpdateRecovery();Need(c.gameplay.BurstTicks==0,"offline cancels burst");Near(c.outputLimit,0,"offline bank supplies nothing");c.block.Enabled=true;
  c.gameplay.RecoveryTicks=0;c.block.CurrentStoredPower=500;c.UpdateBank();
  var r=new IMyReactor{CubeGrid=grid};r.GameLogic.Value=new Reactor{NeedsStorageSupport=true};MyAPIGateway.TerminalActionsHelper.Terminal.Items.Add(r);
  c.RequestBurst();Need(c.gameplay.BurstTicks==0,"containment takes priority over burst");c.RequestSurge();Need(c.gameplay.SurgeTicks==0,"containment takes priority over surge");
  MyAPIGateway.TerminalActionsHelper.Terminal.Items.Clear();
  c.InitializeGameplay(false);Need(c.gameplay.EntityId==c.block.EntityId && c.gameplay.RecoveryTicks==0 && c.gameplay.BurstTicks==0,"new identity resets saved operations");
  c.block.CurrentStoredPower=500;c.block.CurrentOutput=10000;c.UpdateBank();
  var saturated=Drive(grid);c.RequestSurge();original=c.block.CurrentStoredPower;FinishBatch(c,30);Need(saturated.CurrentStoredPower==3 && c.block.CurrentStoredPower<original,"surge adds throughput even when ordinary grid output is saturated");saturated.Enabled=false;
  c.block.CurrentOutput=0;c.gameplay.RecoveryTicks=0;
  var active=Drive(grid);c.RequestSurge();c.UpdateSurge();original=c.block.CurrentStoredPower;float filled=active.CurrentStoredPower;
  active.Access=false;c.UpdateSurge();Need(c.gameplay.SurgeTicks==0 && c.block.CurrentStoredPower==original && active.CurrentStoredPower==filled,"ownership change stops further debit without refund");
  c.gameplay.RecoveryTicks=0;Drive(grid);MyAPIGateway.Multiplayer.IsServer=false;c.RequestSurge();c.RequestBurst();Need(c.gameplay.SurgeTicks==0 && c.gameplay.BurstTicks==0,"clients cannot start operations");MyAPIGateway.Multiplayer.IsServer=true;
  var stability=Module(grid,new Vector3I(0,2,0),"ArcanePower_EnergyStabilizer",Base6Directions.Direction.Down);
  var transfer=Module(grid,new Vector3I(0,0,2),"ArcanePower_EnergyTransfer",Base6Directions.Direction.Forward);
  c.UpdateBank();Need(SurgeDuration==300 && c.RecoveryDuration()==5400,"standard surge window and recovery");
  stability.BlockDefinition.SubtypeName+="Advanced";transfer.BlockDefinition.SubtypeName+="Advanced";
  c.UpdateBank();Need(SurgeDuration==300 && c.RecoveryDuration()==3600,"advanced surge window and recovery");
  var advanced=Drive(grid);c.RequestSurge();for(int i=0;i<30 && c.gameplay.SurgeTicks>0;i++){c.UpdateBank();c.UpdateSurge();}Need(advanced.CurrentStoredPower==3,"advanced surge fills in five seconds");
  c.gameplay.RecoveryTicks=0;c.RequestBurst();Near(c.outputLimit,(c.block.CurrentStoredPower-100)*2160,"burst respects energy-backed native interval bound");
  var left=Cell(grid,new Vector3I(-2,0,0),"ArcanePower_EnergyCapacity",10000,Base6Directions.Direction.Right);
  var right=Cell(grid,new Vector3I(2,0,0),"ArcanePower_EnergyCapacityAdvanced",100000,Base6Directions.Direction.Left);
  c.UpdateBank();Need(c.cells.Contains(right),"advanced burst includes supported expansion");float ceiling=0;foreach(var cell in c.cells)ceiling+=cell.outputLimit;Near(ceiling,2000000,"advanced burst allocates two TW across bank");
  left.Disconnect();original=left.block.CurrentStoredPower;left.UpdateUpkeep();Need(left.block.CurrentStoredPower<original && left.upkeepTier==0,"detached capacity still leaks at bare rate");
  Console.WriteLine("PASS gameplay: quadratic upkeep, stabilization, disabled loss, authority, surge debit/efficiency/reserve, target eligibility, shared recovery, reload/copy, burst limits and containment priority");
 }
}
