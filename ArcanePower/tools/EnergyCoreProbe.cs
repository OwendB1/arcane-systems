using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
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
 float reserve=.1f,outputLimit,inputLimit,stored,capacity,transfer;int tick=1;string status;
 List<EnergyCore> cells=new List<EnergyCore>(),previousCells=new List<EnergyCore>();List<IMyReactor> reactors=new List<IMyReactor>();
 bool IsController {get {return BaseSubtype(block)==CoreSubtype;}}
 IMyTerminalBlock Entity {get {return block;}}
 int stabilizationTier,upkeepTier,surgeDuration=600;float upkeepMW,replicatedStored=float.NaN;double upkeepDebt;
 EnergyGameplayState gameplay=new EnergyGameplayState();JumpDriveSurge activeDrive;List<IMyJumpDrive> jumpDrives=new List<IMyJumpDrive>();
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
  c.UpdateBank();Near(c.transfer,10000,"base 10GW");Near(c.capacity,1000,"base capacity");
  var left=Cell(grid,new Vector3I(-2,0,0),"ArcanePower_EnergyCapacity",10000,Base6Directions.Direction.Right);
  var right=Cell(grid,new Vector3I(2,0,0),"ArcanePower_EnergyCapacityAdvanced",100000,Base6Directions.Direction.Left);
  c.UpdateBank();Need(c.cells.Count==1,"modules require stabilizer");
  var stable=Module(grid,new Vector3I(0,2,0),"ArcanePower_EnergyStabilizer",Base6Directions.Direction.Down);
  var transfer=Module(grid,new Vector3I(0,0,2),"ArcanePower_EnergyTransfer",Base6Directions.Direction.Forward);
  c.UpdateBank();Need(c.cells.Count==2,"standard stabilizer accepts only standard capacity");Near(c.capacity,11000,"fixed capacities aggregate");Near(c.transfer,100000,"transfer tier independent of capacity");
  stable.BlockDefinition.SubtypeName+="Advanced";transfer.BlockDefinition.SubtypeName+="Advanced";
  c.UpdateBank();Need(c.cells.Count==3,"advanced supports both capacity tiers");Near(c.capacity,111000,"mixed bank capacity");Near(c.transfer,1000000,"advanced transfer");
  float input=0,output=0;foreach(var cell in c.cells){input+=cell.inputLimit;output+=cell.outputLimit;}
  Near(input,1000000,"sum input limits equals bank limit");Need(output<=1000000.2f,"output cannot exceed bank ceiling");
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
    g.Blocks.Remove(fv*2);st.Position=uv*2;g.Blocks[st.Position]=new Slim{FatBlock=st};pc.UpdateBank();Need(pc.cells.Count==1,"pillar stabilizer belongs on front, not roof");
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
  CheckGameplay();
  Console.WriteLine("PASS energy bank: tiers, allocation, native clamp, reserve boundary, emergency/modes, orientation, access, construction, detach/split, charge preservation");
 }
 static IMyJumpDrive Drive(Grid grid){
  var d=new IMyJumpDrive{CubeGrid=grid};var logic=new JumpDriveSurge{Entity=d};d.GameLogic.Value=logic;
  logic.Init(null);logic.UpdateOnceBeforeFrame();MyAPIGateway.Entities.Items[d.EntityId]=d;
  MyAPIGateway.TerminalActionsHelper.Terminal.Drives.Add(d);return d;
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
  c.RequestSurge(drive.EntityId);Need(c.gameplay.SurgeTicks==600,"base surge ten seconds");Need(!c.Ready,"surge starts bank recovery");
  Need(!drive.GameLogic.GetAs<JumpDriveSurge>().Claim(999),"drive cooldown blocks another bank");
  float start=c.block.CurrentStoredPower;
  for(int i=0;i<60 && c.gameplay.SurgeTicks>0;i++){c.UpdateBank();c.UpdateSurge();}
  Need(drive.CurrentStoredPower==3,"surge fills native drive within ten seconds: "+drive.CurrentStoredPower.ToString("R")+" "+c.gameplay.Result);
  Need(start-c.block.CurrentStoredPower>=drive.CurrentStoredPower,"surge cannot create energy");
  Need(Math.Abs((start-c.block.CurrentStoredPower)*.9f-3)<.005,"surge has 90 percent efficiency");
  Need(c.block.CurrentStoredPower>=100,"surge protects reserve");
  c.gameplay.RecoveryTicks=0;drive.CurrentStoredPower=0;c.RequestSurge(drive.EntityId);Need(c.gameplay.SurgeTicks==0,"drive recovery prevents changing bank");
  for(int i=0;i<7800;i++)drive.GameLogic.GetAs<JumpDriveSurge>().UpdateBeforeSimulation();
  var other=Drive(new Grid());c.RequestSurge(other.EntityId);Need(c.gameplay.SurgeTicks==0,"cross-grid target rejected");
  drive.Access=false;c.RequestSurge(drive.EntityId);Need(c.gameplay.SurgeTicks==0,"foreign target rejected");drive.Access=true;
  drive.Recharge=false;c.RequestSurge(drive.EntityId);Need(c.gameplay.SurgeTicks==0,"recharge-disabled drive rejected");drive.Recharge=true;
  drive.Status=MyJumpDriveStatus.Jumping;c.RequestSurge(drive.EntityId);Need(c.gameplay.SurgeTicks==0,"jumping drive rejected");drive.Status=MyJumpDriveStatus.Charging;
  c.block.ChargeMode=ChargeMode.Recharge;c.RequestSurge(drive.EntityId);Need(c.gameplay.SurgeTicks==0,"Recharge bank cannot surge");c.block.ChargeMode=ChargeMode.Auto;
  c.block.CurrentStoredPower=100;c.RequestSurge(drive.EntityId);Need(c.gameplay.SurgeTicks==0,"reserve cannot fund surge");
  c.UpdateUpkeep();Need(c.block.CurrentStoredPower<100,"reserve does not bypass passive loss");
  c.block.CurrentStoredPower=500;c.RequestSurge(drive.EntityId);Need(c.gameplay.SurgeTicks>0,"second surge after recovery");
  drive.CubeGrid=new Grid();original=c.block.CurrentStoredPower;c.UpdateSurge();Need(c.gameplay.SurgeTicks==0 && c.block.CurrentStoredPower==original,"split cancels surge without spending");drive.CubeGrid=grid;
  var saved=drive.Storage[JumpDriveSurge.RecoveryKey];var restored=new JumpDriveSurge{Entity=drive};restored.Init(null);restored.UpdateOnceBeforeFrame();Need(!restored.Claim(999),"drive recovery survives reload");
  drive.Storage[JumpDriveSurge.RecoveryKey]="999:7200";var copied=new JumpDriveSurge{Entity=drive};copied.Init(null);copied.UpdateOnceBeforeFrame();Need(copied.Claim(999),"copied identity does not inherit cooldown");copied.Release(999);drive.Storage[JumpDriveSurge.RecoveryKey]=saved;
  c.gameplay.RecoveryTicks=0;c.RequestBurst();Need(c.gameplay.BurstTicks==600,"burst lasts ten seconds");Near(c.outputLimit,20000,"burst doubles base discharge");Near(c.inputLimit,10000,"burst leaves charge ceiling unchanged");
  c.RequestSurge(drive.EntityId);Need(c.gameplay.SurgeTicks==0,"burst and surge share recovery");
  c.SaveGameplay();var state=c.block.Storage[GameplayKey];c.gameplay=new EnergyGameplayState();c.InitializeGameplay(true);Need(c.gameplay.BurstTicks==600 && c.gameplay.RecoveryTicks>0,"bank recovery and burst survive reload");
  for(int i=0;i<600;i++)c.UpdateRecovery();Near(c.outputLimit,10000,"burst ends at normal ceiling");Need(c.gameplay.RecoveryTicks>0,"recovery continues after burst");
  c.gameplay.RecoveryTicks=0;c.RequestBurst();c.block.Enabled=false;c.UpdateRecovery();Need(c.gameplay.BurstTicks==0,"offline cancels burst");Near(c.outputLimit,0,"offline bank supplies nothing");c.block.Enabled=true;
  c.gameplay.RecoveryTicks=0;c.block.CurrentStoredPower=500;c.UpdateBank();
  var r=new IMyReactor{CubeGrid=grid};r.GameLogic.Value=new Reactor{NeedsStorageSupport=true};MyAPIGateway.TerminalActionsHelper.Terminal.Items.Add(r);
  c.RequestBurst();Need(c.gameplay.BurstTicks==0,"containment takes priority over burst");c.RequestSurge(drive.EntityId);Need(c.gameplay.SurgeTicks==0,"containment takes priority over surge");
  MyAPIGateway.TerminalActionsHelper.Terminal.Items.Clear();
  c.InitializeGameplay(false);Need(c.gameplay.EntityId==c.block.EntityId && c.gameplay.RecoveryTicks==0 && c.gameplay.BurstTicks==0,"new identity resets saved operations");
  c.block.CurrentStoredPower=500;c.block.CurrentOutput=10000;c.UpdateBank();
  var saturated=Drive(grid);c.RequestSurge(saturated.EntityId);original=c.block.CurrentStoredPower;c.UpdateSurge();Need(c.gameplay.SurgeTicks==0 && c.block.CurrentStoredPower==original,"saturated native grid cannot double spend transfer");
  c.block.CurrentOutput=0;c.gameplay.RecoveryTicks=0;
  var active=Drive(grid);c.RequestSurge(active.EntityId);c.UpdateSurge();original=c.block.CurrentStoredPower;float filled=active.CurrentStoredPower;
  active.Access=false;c.UpdateSurge();Need(c.gameplay.SurgeTicks==0 && c.block.CurrentStoredPower==original && active.CurrentStoredPower==filled,"ownership change stops further debit without refund");
  c.gameplay.RecoveryTicks=0;var clientDrive=Drive(grid);MyAPIGateway.Multiplayer.IsServer=false;c.RequestSurge(clientDrive.EntityId);c.RequestBurst();Need(c.gameplay.SurgeTicks==0 && c.gameplay.BurstTicks==0,"clients cannot start operations");MyAPIGateway.Multiplayer.IsServer=true;
  var stability=Module(grid,new Vector3I(0,2,0),"ArcanePower_EnergyStabilizer",Base6Directions.Direction.Down);
  var transfer=Module(grid,new Vector3I(0,0,2),"ArcanePower_EnergyTransfer",Base6Directions.Direction.Forward);
  c.UpdateBank();Need(c.surgeDuration==450 && c.RecoveryDuration()==5400,"standard speed and recovery");
  stability.BlockDefinition.SubtypeName+="Advanced";transfer.BlockDefinition.SubtypeName+="Advanced";
  c.UpdateBank();Need(c.surgeDuration==300 && c.RecoveryDuration()==3600,"advanced speed and recovery");
  var advanced=Drive(grid);c.RequestSurge(advanced.EntityId);for(int i=0;i<30 && c.gameplay.SurgeTicks>0;i++){c.UpdateBank();c.UpdateSurge();}Need(advanced.CurrentStoredPower==3,"advanced surge fills in five seconds");
  c.gameplay.RecoveryTicks=0;c.RequestBurst();Near(c.outputLimit,(c.block.CurrentStoredPower-100)*2160,"burst respects energy-backed native interval bound");
  var left=Cell(grid,new Vector3I(-2,0,0),"ArcanePower_EnergyCapacity",10000,Base6Directions.Direction.Right);
  var right=Cell(grid,new Vector3I(2,0,0),"ArcanePower_EnergyCapacityAdvanced",100000,Base6Directions.Direction.Left);
  c.UpdateBank();Need(c.cells.Contains(right),"advanced burst includes supported expansion");float ceiling=0;foreach(var cell in c.cells)ceiling+=cell.outputLimit;Near(ceiling,2000000,"advanced burst allocates two TW across bank");
  left.Disconnect();original=left.block.CurrentStoredPower;left.UpdateUpkeep();Need(left.block.CurrentStoredPower<original && left.upkeepTier==0,"detached capacity still leaks at bare rate");
  Console.WriteLine("PASS gameplay: quadratic upkeep, stabilization, disabled loss, authority, surge debit/efficiency/reserve, target eligibility, shared recovery, reload/copy, burst limits and containment priority");
 }
}
