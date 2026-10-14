using System;
using System.Collections.Generic;
using VRageMath;
using MyDefinitionId=System.Int32;
enum ChargeMode { Auto, Recharge, Discharge }
class Slim { public float BuildLevelRatio=1; public IMyCubeBlock FatBlock; }
class Definition { public string SubtypeName; }
class Orientation { public Base6Directions.Direction Forward=Base6Directions.Direction.Forward, Up=Base6Directions.Direction.Up; }
class Logic { public object Value; public T GetAs<T>() where T:class {return Value as T;} }
class Grid { public Dictionary<Vector3I,Slim> Blocks=new Dictionary<Vector3I,Slim>(); public Slim GetCubeBlock(Vector3I p){Slim s;return Blocks.TryGetValue(p,out s)?s:null;} }
class IMyCubeBlock { public bool Closed,IsFunctional=true;public Slim SlimBlock=new Slim();public Definition BlockDefinition=new Definition();public Orientation Orientation=new Orientation();public Vector3I Position;public Grid CubeGrid;public Logic GameLogic=new Logic(); }
class IMyFunctionalBlock:IMyCubeBlock {public bool Enabled=true;}
class IMyTerminalBlock:IMyFunctionalBlock { public bool Access=true;public long OwnerId=1;public bool HasPlayerAccess(long id){return Access;} }
class IMyBatteryBlock:IMyTerminalBlock {public float CurrentStoredPower,MaxStoredPower;public ChargeMode ChargeMode; public MyResourceSourceComponent SourceComp=new MyResourceSourceComponent();public Sink ResourceSink=new Sink();}
class IMyReactor:IMyTerminalBlock {}
class Reactor {public bool NeedsStorageSupport;}
class Sink {public float Max;public void SetMaxRequiredInputByType(int type,float n){Max=n;}public void Update(){} }
class MyResourceSourceComponent { public float Max;public event Action<int,float,MyResourceSourceComponent> MaxOutputChanged;public float MaxOutputUnlimitedByCapacity(int type){return Max;}public void SetMaxOutputByType(int type,float n){float old=Max;Max=n;if(old!=n && MaxOutputChanged!=null)MaxOutputChanged(type,old,this);} }
class Terminal {public List<IMyReactor> Items=new List<IMyReactor>();public void GetBlocksOfType(List<IMyReactor> list,Func<IMyReactor,bool> filter){foreach(var r in Items)if(filter(r))list.Add(r);} }
class Multi {public bool IsServer=true;}
class Helper {public Terminal Terminal=new Terminal();public Terminal GetTerminalSystemForGrid(Grid g){return Terminal;} }
static class MyAPIGateway {public static Multi Multiplayer=new Multi();public static Helper TerminalActionsHelper=new Helper();}
class EnergyCore {
 const string CoreSubtype="ArcanePower_EnergyCore";const int Electricity=0;
 IMyBatteryBlock block,battery;bool initialized=true,emergencyEnabled=true,emergency,changingLimit;
 float reserve=.1f,outputLimit,inputLimit,stored,capacity,transfer;int tick=1;string status;
 List<EnergyCore> cells=new List<EnergyCore>(),previousCells=new List<EnergyCore>();List<IMyReactor> reactors=new List<IMyReactor>();
 void ReadSettings(){}
 // METHODS
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
    cap.block.Orientation.Up=Base6Directions.GetDirection(-uv);pc.UpdateBank();Need(pc.cells.Count==1,"upside-down pillar rejected");cap.block.Orientation.Up=u;
    cap.block.BlockDefinition.SubtypeName="ArcanePower_EnergyCapacityAdvanced";pc.UpdateBank();Need(pc.cells.Count==1,"compact and pillar banks cannot mix");cap.block.BlockDefinition.SubtypeName+="_Pillar";
    g.Blocks.Remove(fv*2);st.Position=uv*2;g.Blocks[st.Position]=new Slim{FatBlock=st};pc.UpdateBank();Need(pc.cells.Count==1,"pillar stabilizer belongs on front, not roof");
   }
  Console.WriteLine("PASS energy bank: tiers, allocation, native clamp, reserve boundary, emergency/modes, orientation, access, construction, detach/split, charge preservation");
 }
}
