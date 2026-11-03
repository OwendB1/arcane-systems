using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using ArcanePower;
using Sandbox.ModAPI;
using VRageMath;
using VRage.ModAPI;
using VRage.Game.Components;
using VRage.Game.ModAPI;
using VRage.Utils;

namespace VRage.ModAPI { public interface IMyEntity { bool Closed {get;} Vector3D GetPosition(); } }
namespace VRage.Game.ModAPI {
 public class IMyModel {}
 public class IMyPlayer {public ulong SteamUserId;public long IdentityId;public Vector3D Position;public Vector3D GetPosition(){return Position;}}
}
namespace VRage.Game.Components {
 public enum MyUpdateOrder {NoUpdate}
 public class MySessionComponentDescriptorAttribute:Attribute {public MySessionComponentDescriptorAttribute(MyUpdateOrder order){}}
 public class MySessionComponentBase {protected virtual void UnloadData(){}}
}
namespace VRage.Utils {public class MyLog {public static MyLog Default=new MyLog();public int Entries;public void WriteLine(string value){Entries++;}}}
namespace Sandbox.ModAPI {
 public class Block:IMyEntity {
  public long EntityId,Owner=1;public bool Closed{get;set;}public Vector3D Position;
  public float CurrentStoredPower=10,MaxStoredPower=100;
  public bool HasPlayerAccess(long id){return id==Owner;}public Vector3D GetPosition(){return Position;}public void RefreshCustomInfo(){}
 }
 public class SessionState {public int GameplayFrameCounter;public VRage.Game.ModAPI.IMyPlayer Player;public Settings SessionSettings=new Settings();}
 public class Settings {public double SyncDistance=3000;}
 public class PlayerGateway {
  public List<VRage.Game.ModAPI.IMyPlayer> All=new List<VRage.Game.ModAPI.IMyPlayer>();
  public void GetPlayers(List<VRage.Game.ModAPI.IMyPlayer> list,Func<VRage.Game.ModAPI.IMyPlayer,bool> filter=null){foreach(var p in All)if(filter==null||filter(p))list.Add(p);}
  public long TryGetIdentityId(ulong sender){foreach(var p in All)if(p.SteamUserId==sender)return p.IdentityId;return 0;}
 }
 public class EntityGateway {public Dictionary<long,IMyEntity> All=new Dictionary<long,IMyEntity>();public bool TryGetEntityById(long id,out IMyEntity e){return All.TryGetValue(id,out e);}}
 public class Delivery {public ushort Channel;public byte[] Bytes;public ulong Recipient;}
 public class MultiplayerGateway {
  public bool IsServer=true,Fail,Throw;public List<Delivery> Sent=new List<Delivery>();
  public bool SendMessageTo(ushort channel,byte[] bytes,ulong recipient){if(Throw)throw new Exception("transport unavailable");if(Fail)return false;Sent.Add(new Delivery{Channel=channel,Bytes=bytes,Recipient=recipient});return true;}
  public bool SendMessageToServer(ushort channel,byte[] bytes){return SendMessageTo(channel,bytes,0);}
 }
 public class UtilitiesGateway {
  public Queue<Action> Queued=new Queue<Action>();public int Serializations;
  private readonly ProtoBuf.Meta.RuntimeTypeModel wire=ProtoBuf.Meta.RuntimeTypeModel.Create();
  public byte[] SerializeToBinary<T>(T value){Serializations++;using(var s=new MemoryStream()){wire.Serialize(s,value);return s.ToArray();}}
  public T SerializeFromBinary<T>(byte[] value){using(var s=new MemoryStream(value))return (T)wire.Deserialize(s,null,typeof(T));}
  public void InvokeOnGameThread(Action action){Queued.Enqueue(action);}
  public void Drain(){while(Queued.Count>0)Queued.Dequeue()();}
 }
 public static class MyAPIGateway {
  public static SessionState Session=new SessionState();public static PlayerGateway Players=new PlayerGateway();
  public static MultiplayerGateway Multiplayer=new MultiplayerGateway();public static UtilitiesGateway Utilities=new UtilitiesGateway();public static EntityGateway Entities=new EntityGateway();
 }
}

// NETWORK_PRODUCTION

namespace Acceptance {
 class Reactor {
  public Block reactor=new Block();public Block Block{get{return reactor;}}public IMyEntity Entity{get{return reactor;}}public long Id{get{return reactor.EntityId;}}
  public MotionState Motion=new MotionState();internal bool receivedState;internal int stateAge,appearanceRefresh,Commands;
  static float[] PowerMW={1000,10000,100000};static int[] TileTypes=new int[3];
  public IMyModel restModel,manifoldModel;public bool manifoldReady;public Dictionary<string,Matrix> restPoses=new Dictionary<string,Matrix>();
  public void RequestVent(bool open){Commands++;}public void RequestVentShieldTest(){Commands++;}public void SetSecurityMode(bool enabled){Commands++;}public void RequestThermalMode(ThermalMode mode){Commands++;}
  public MotionState Snapshot(){return Motion;}
  // REACTOR_PRODUCTION
 }
 class VentSession {
  internal const ushort Channel=49371;internal static bool ready=true;
  internal static Dictionary<long,Reactor> Reactors=new Dictionary<long,Reactor>();
  // VENT_PRODUCTION
 }
 class EnergyCore {
  public Block Block=new Block();internal Block block{get{return Block;}}internal Block Entity{get{return Block;}}
  public bool Controller=true;public EnergyGameplayState gameplay=new EnergyGameplayState();public EnergyGameplayState Gameplay{get{return gameplay;}}
  internal EnergyBankState bankReplica;internal long bankSequence,bankControllerId;internal int replicaAge,upkeepTier,Commands;
  internal float replicatedStored,stored,capacity,transfer,chargeCeiling,reserve,inputLimit,outputLimit;internal bool emergencyEnabled,emergency;internal string status;
  public void RequestSurge(){Commands++;}public void RequestBurst(){Commands++;}public void SetPolicy(float? percent,bool? support){Commands++;}
  public void ApplyLimits(float input,float output){inputLimit=input;outputLimit=output;}
  public EnergyBankState CaptureBank(){return new EnergyBankState{Sequence=++bankSequence,Status="Online"};}
  // ENERGY_CORE_PRODUCTION
 }
 class EnergySession {
  internal const ushort Channel=49374;internal static bool ready=true;internal static Dictionary<long,EnergyCore> Cells=new Dictionary<long,EnergyCore>();
  internal static EnergyCore Find(long id){EnergyCore core;return Cells.TryGetValue(id,out core)?core:null;}internal static void Broadcast(EnergyCore core){}
  // ENERGY_PRODUCTION
 }
 class CoreHazards {
  internal const ushort Channel=49372;internal bool ready=true;
  internal List<CoreHazard> cores=new List<CoreHazard>();internal long snapshotSequence,receivedSequence=-1,pendingSequence=-1;
  internal List<CoreHazard>[] pendingBatches;internal Dictionary<ulong,HashSet<long>> knownShells=new Dictionary<ulong,HashSet<long>>();
  internal Dictionary<long,List<CoreShellPart>> shellData=new Dictionary<long,List<CoreShellPart>>();internal int snapshotAge,shellRetryAt,tick;
  // HAZARDS_PRODUCTION
 }
 static class Checks {
  static int checks;
  static void Need(bool value,string message){checks++;if(!value)throw new Exception(message);}
  static byte[] Raw<T>(T packet){return MyAPIGateway.Utilities.SerializeToBinary(packet);}
  static T Copy<T>(T packet){return MyAPIGateway.Utilities.SerializeFromBinary<T>(Raw(packet));}
  static void Reset(){
   typeof(PowerNetwork).GetMethod("UnloadData",BindingFlags.NonPublic|BindingFlags.Instance).Invoke(new PowerNetwork(),null);
   MyAPIGateway.Session=new SessionState();MyAPIGateway.Players=new PlayerGateway();MyAPIGateway.Multiplayer=new MultiplayerGateway();MyAPIGateway.Utilities=new UtilitiesGateway();MyAPIGateway.Entities=new EntityGateway();
   MyAPIGateway.Players.All.Add(new VRage.Game.ModAPI.IMyPlayer{SteamUserId=11,IdentityId=1});
   MyAPIGateway.Players.All.Add(new VRage.Game.ModAPI.IMyPlayer{SteamUserId=22,IdentityId=2,Position=new Vector3D(100,0,0)});
   MyAPIGateway.Players.All.Add(new VRage.Game.ModAPI.IMyPlayer{SteamUserId=33,IdentityId=3,Position=new Vector3D(10000,0,0)});
   VentSession.Reactors.Clear();EnergySession.Cells.Clear();
  }
  static CoreHazard Core(long id){return new CoreHazard{SourceId=1,CarrierId=id,Tier=1,Shell=new List<CoreShellPart>{new CoreShellPart{Subtype="ArcaneSpentRing1",Pose=Matrix.Identity}}};}
  static void Contracts(){
   Need(Raw(new CoreHazardSnapshot()).Length>0,"empty hazard snapshot keeps its envelope");
   Need(Copy(new CoreHazardSnapshot()).Cores.Count==0,"empty snapshot explicitly clears all hazards");
   var motion=Copy(new MotionState{EntityId=1,Sequence=1,Telemetry=new ReactorTelemetry{Fuel=17,TileQuartets=new[]{2,3,4},Residuum=9,Controllers=2,RingCapacity=4,AdvancedController=true,FuelReady=true}});
   Need(motion.Telemetry.Valid() && motion.Telemetry.TileQuartets.Length==3 && motion.Telemetry.TileQuartets[2]==4,"protobuf preserves exact inventory array cardinality");
   Need(Reactor.Valid(motion),"complete reactor snapshot is valid");
   var rig=new Reactor{restModel=new IMyModel()};
   for(int bay=0;bay<4;bay++)foreach(string part in ThermalManifolds.Parts)rig.restPoses[ThermalManifolds.Name(bay,part)]=Matrix.Identity;
   Need(rig.ManifoldRigReady,"server readiness uses model metadata without render subparts");
   rig.restModel=new IMyModel();rig.restPoses.Clear();Need(!rig.ManifoldRigReady,"construction-stage model replacement invalidates readiness");
   motion.Telemetry.Fuel=double.NaN;Need(!Reactor.Valid(motion),"nonfinite telemetry rejected");
   Need(Core(1).Valid(),"native hazard geometry is valid");
   var bad=Core(1);bad.Tier=4;Need(!bad.Valid(),"invalid tier rejected before rendering");bad=Core(1);bad.Shell[0].Subtype="UnrelatedModel";Need(!bad.Valid(),"shell model whitelist");
   bad=Core(1);bad.Shell[0].Pose=Matrix.CreateScale(1000);Need(!bad.Valid(),"oversized shell transform rejected");
   var energy=new EnergyGameplayState{EntityId=1};Need(Copy(energy).Valid(1),"energy roundtrip");energy.SurgeRate=float.NaN;Need(!energy.Valid(1),"nonfinite surge state rejected");
  }
  static void Transport(){
   Reset();var target=new Block();var packet=new VentPacket{EntityId=1,State=new MotionState()};
   int before=MyAPIGateway.Utilities.Serializations;PowerNetwork.Broadcast(49371,packet,target);
   Need(MyAPIGateway.Multiplayer.Sent.Count==2,"only two nearby clients receive state");Need(MyAPIGateway.Utilities.Serializations==before+1,"fanout serializes once");
   Need(!PowerNetwork.CanRequest(49371,99,1,target),"unregistered sender rejected");Need(!PowerNetwork.CanRequest(49371,33,1,target),"far snapshot request rejected");
   Need(PowerNetwork.CanRequest(49371,11,1,target),"first nearby request accepted");Need(!PowerNetwork.CanRequest(49371,11,1,target),"duplicate request throttled");
   for(int i=2;i<=64;i++)Need(PowerNetwork.CanRequest(49371,11,i,target),"distinct streamed entities bootstrap");
   Need(!PowerNetwork.CanRequest(49371,11,65,target),"per-peer rate bounded");MyAPIGateway.Session.GameplayFrameCounter=120;
   Need(PowerNetwork.CanRequest(49371,11,1,target),"request budget recovers");
   int errors=VRage.Utils.MyLog.Default.Entries;MyAPIGateway.Multiplayer.Fail=true;Need(!PowerNetwork.Send(49371,packet,11),"send failure propagated");
   MyAPIGateway.Multiplayer.Throw=true;Need(!PowerNetwork.Send(49371,packet,11),"send exception isolated");Need(VRage.Utils.MyLog.Default.Entries>=errors+2,"send failures logged");
   MyAPIGateway.Multiplayer.Fail=MyAPIGateway.Multiplayer.Throw=false;PowerNetwork.OnGameThread(()=>{throw new Exception("bad packet");});MyAPIGateway.Utilities.Drain();
  }
  static void Commands(){
   Reset();var r=new Reactor();r.reactor.EntityId=7;r.Motion.EntityId=7;VentSession.Reactors[7]=r;var receiver=new VentSession();
   receiver.Receive(49371,Raw(new VentPacket{EntityId=7,Command=VentCommand.Start}),11,false);
   Need(r.Commands==0,"network callback cannot mutate before game-thread dispatch");MyAPIGateway.Utilities.Drain();Need(r.Commands==1,"owner command applied once");
   receiver.Receive(49371,Raw(new VentPacket{EntityId=7,Command=VentCommand.Start}),22,false);MyAPIGateway.Utilities.Drain();Need(r.Commands==1,"nonowner command rejected");
   receiver.Receive(49371,Raw(new VentPacket{EntityId=7,Command=VentCommand.Start,State=new MotionState()}),11,false);MyAPIGateway.Utilities.Drain();Need(r.Commands==1,"client cannot submit state");
   r.reactor.Owner=2;receiver.Receive(49371,Raw(new VentPacket{EntityId=7,Command=VentCommand.Start}),11,false);MyAPIGateway.Utilities.Drain();Need(r.Commands==1,"ownership checked at execution time");
   MyAPIGateway.Session.Player=MyAPIGateway.Players.All[0];VentSession.SendCommand(7,VentCommand.Start);Need(r.Commands==1,"host UI cannot control another owner");
   VentSession.SendCommand(7,VentCommand.Start,true);Need(r.Commands==2,"listen-server timer does not inherit host identity");
   MyAPIGateway.Session.Player=null;VentSession.SendCommand(7,VentCommand.Start,true);Need(r.Commands==3,"dedicated-server native action executes");
   var cell=new EnergyCore();cell.Block.EntityId=8;cell.Block.Owner=2;EnergySession.Cells[8]=cell;
   MyAPIGateway.Session.Player=MyAPIGateway.Players.All[0];EnergySession.Send(8,EnergyCommand.Burst);Need(cell.Commands==0,"host energy UI checks access");
   EnergySession.Send(8,EnergyCommand.Burst,0,true);Need(cell.Commands==1,"listen-server native energy action executes");
   var er=new EnergySession();er.Receive(49374,Raw(new EnergyPacket{EntityId=8,Command=EnergyCommand.Burst}),11,false);MyAPIGateway.Utilities.Drain();Need(cell.Commands==1,"remote energy action cannot borrow native privilege");
   er.Receive(49374,Raw(new EnergyPacket{EntityId=8,Command=EnergyCommand.Burst}),22,false);MyAPIGateway.Utilities.Drain();Need(cell.Commands==2,"energy owner command succeeds");
   MyAPIGateway.Multiplayer.IsServer=false;VentSession.SendCommand(7,VentCommand.Start,true);Need(MyAPIGateway.Multiplayer.Sent[MyAPIGateway.Multiplayer.Sent.Count-1].Recipient==0,"client native action still goes through server authentication");
  }
  static void Replicas(){
   Reset();MyAPIGateway.Multiplayer.IsServer=false;var r=new Reactor();r.reactor.EntityId=7;r.Motion.EntityId=7;VentSession.Reactors[7]=r;var receiver=new VentSession();
   var state=new MotionState{EntityId=7,Sequence=5,Core=CorePhase.Running,Telemetry=new ReactorTelemetry{Controllers=2,RingCapacity=4,FuelReady=true}};
   var packet=new VentPacket{EntityId=7,State=state};receiver.Receive(49371,Raw(packet),11,false);MyAPIGateway.Utilities.Drain();Need(!r.receivedState,"peer cannot forge server snapshot");
   receiver.Receive(49371,Raw(packet),0,true);MyAPIGateway.Utilities.Drain();Need(r.receivedState && r.Motion.Sequence==5,"late join consumes server snapshot");
   state.Sequence=4;state.Core=CorePhase.Off;receiver.Receive(49371,Raw(packet),0,true);MyAPIGateway.Utilities.Drain();Need(r.Motion.Core==CorePhase.Running,"older reactor packet rejected");
   r.receivedState=false;r.stateAge=200;state.Sequence=5;state.Core=CorePhase.Running;receiver.Receive(49371,Raw(packet),0,true);MyAPIGateway.Utilities.Drain();Need(r.receivedState && r.stateAge==0,"equal authoritative baseline can recover stale prediction");
   var cell=new EnergyCore();cell.Block.EntityId=8;EnergySession.Cells[8]=cell;var er=new EnergySession();
   var ep=new EnergyPacket{EntityId=8,State=new EnergyGameplayState{EntityId=8},Stored=20,Bank=new EnergyBankState{Sequence=2,Status="Online",InputLimit=123,OutputLimit=456,Reserve=.3f,Emergency=true,Members=new[]{8L}}};
   er.Receive(49374,Raw(ep),0,true);MyAPIGateway.Utilities.Drain();Need(cell.inputLimit==123 && cell.outputLimit==456 && cell.emergency,"client mirrors server allocation and policy");
   ep.Bank.Sequence=1;ep.Bank.OutputLimit=1;ep.Stored=99;er.Receive(49374,Raw(ep),0,true);MyAPIGateway.Utilities.Drain();Need(cell.outputLimit==456 && cell.replicatedStored==20,"stale energy packet cannot partly update charge");
   ep.Bank.Sequence=3;ep.State.BurstTicks=-1;er.Receive(49374,Raw(ep),0,true);MyAPIGateway.Utilities.Drain();Need(cell.bankSequence==2,"malformed summary cannot advance allocation sequence");
  }
  static void Hazards(){
   Reset();var server=new CoreHazards();for(int i=1;i<=9;i++)server.cores.Add(Core(100+i));server.Broadcast();
   var first=new List<Delivery>(MyAPIGateway.Multiplayer.Sent.FindAll(d=>d.Recipient==11));Need(first.Count==3,"hazards split into bounded batches");
   foreach(var d in MyAPIGateway.Multiplayer.Sent)Need(d.Bytes.Length<=PowerNetwork.MaxPacketBytes && (d.Recipient!=33 || MyAPIGateway.Utilities.SerializeFromBinary<CoreHazardSnapshot>(d.Bytes).Cores.Count==0),"hazard interest and size bounds");
   var client=new CoreHazards();MyAPIGateway.Multiplayer.IsServer=false;
   client.Receive(49372,first[2].Bytes,0,true);client.Receive(49372,first[0].Bytes,0,true);MyAPIGateway.Utilities.Drain();Need(client.cores.Count==0,"partial/out-of-order snapshot is not published");
   client.Receive(49372,first[1].Bytes,0,true);MyAPIGateway.Utilities.Drain();Need(client.cores.Count==9 && client.cores[0].Shell.Count==1,"complete batch atomically publishes shell geometry");
   MyAPIGateway.Multiplayer.IsServer=true;MyAPIGateway.Multiplayer.Sent.Clear();server.Broadcast();var next=MyAPIGateway.Multiplayer.Sent.FindAll(d=>d.Recipient==11);
   Need(MyAPIGateway.Utilities.SerializeFromBinary<CoreHazardSnapshot>(next[0].Bytes).Cores[0].Shell==null,"steady snapshots omit immutable shell geometry");
   MyAPIGateway.Multiplayer.IsServer=false;foreach(var d in next)client.Receive(49372,d.Bytes,0,true);MyAPIGateway.Utilities.Drain();Need(client.cores[0].Shell.Count==1,"client retains shell metadata across compact updates");
   var rapid=new CoreHazards();foreach(var d in next)rapid.Receive(49372,d.Bytes,0,true);MyAPIGateway.Utilities.Drain();
   Need(rapid.cores[0].HasShell && rapid.cores[0].Shell==null && MyAPIGateway.Multiplayer.Sent.Exists(d=>d.Recipient==0),"rapid reconnect requests missing shell descriptors");
   MyAPIGateway.Multiplayer.IsServer=true;Need(PowerNetwork.CanRequest(49372,11,0),"prior connection consumed sync budget");
   var request=MyAPIGateway.Multiplayer.Sent.Find(d=>d.Recipient==0);MyAPIGateway.Multiplayer.Sent.Clear();server.Receive(49372,request.Bytes,11,false);MyAPIGateway.Utilities.Drain();
   Need(MyAPIGateway.Multiplayer.Sent.Count==0,"rapid reconnect initially shares prior cooldown");
   MyAPIGateway.Session.GameplayFrameCounter=120;rapid.tick=120;server.Broadcast();var retry=MyAPIGateway.Multiplayer.Sent.FindAll(d=>d.Recipient==11);
   MyAPIGateway.Multiplayer.IsServer=false;MyAPIGateway.Multiplayer.Sent.Clear();foreach(var d in retry)rapid.Receive(49372,d.Bytes,0,true);MyAPIGateway.Utilities.Drain();
   request=MyAPIGateway.Multiplayer.Sent.Find(d=>d.Recipient==0);Need(request!=null,"missing geometry retries while pose packets remain fresh");
   MyAPIGateway.Multiplayer.IsServer=true;MyAPIGateway.Multiplayer.Sent.Clear();server.Receive(49372,request.Bytes,11,false);MyAPIGateway.Utilities.Drain();var repaired=MyAPIGateway.Multiplayer.Sent.FindAll(d=>d.Recipient==11);
   MyAPIGateway.Multiplayer.IsServer=false;foreach(var d in repaired)rapid.Receive(49372,d.Bytes,0,true);MyAPIGateway.Utilities.Drain();Need(rapid.cores[0].Shell.Count==1,"rapid reconnect recovers full shell after cooldown");
   MyAPIGateway.Multiplayer.IsServer=true;MyAPIGateway.Multiplayer.Sent.Clear();server.cores.Clear();server.Broadcast();var empty=MyAPIGateway.Multiplayer.Sent.Find(d=>d.Recipient==11);
   MyAPIGateway.Multiplayer.IsServer=false;client.Receive(49372,empty.Bytes,0,true);MyAPIGateway.Utilities.Drain();Need(client.cores.Count==0 && client.shellData.Count==0,"last hazard removal clears state and geometry cache");
   foreach(var d in first)client.Receive(49372,d.Bytes,0,true);MyAPIGateway.Utilities.Drain();Need(client.cores.Count==0,"old packets cannot resurrect removed hazards");
   MyAPIGateway.Multiplayer.IsServer=true;server.cores.Add(Core(200));MyAPIGateway.Multiplayer.Sent.Clear();MyAPIGateway.Session.GameplayFrameCounter=240;
   server.Receive(49372,Raw(new CoreHazardSnapshot()),11,false);Need(MyAPIGateway.Multiplayer.Sent.Count==0,"hazard sync serialization waits for game thread");MyAPIGateway.Utilities.Drain();
   var reconnect=MyAPIGateway.Multiplayer.Sent.Find(d=>d.Recipient==11);Need(MyAPIGateway.Utilities.SerializeFromBinary<CoreHazardSnapshot>(reconnect.Bytes).Cores[0].Shell.Count==1,"reconnect resends initial shell data");
   MyAPIGateway.Players.All[0].Position=new Vector3D(10000,0,0);MyAPIGateway.Session.GameplayFrameCounter++;MyAPIGateway.Multiplayer.Sent.Clear();server.Broadcast();var away=MyAPIGateway.Multiplayer.Sent.Find(d=>d.Recipient==11);
   Need(MyAPIGateway.Utilities.SerializeFromBinary<CoreHazardSnapshot>(away.Bytes).Cores.Count==0,"leaving relevance explicitly clears old hazards");
   MyAPIGateway.Players.All[0].Position=Vector3D.Zero;MyAPIGateway.Session.GameplayFrameCounter++;MyAPIGateway.Multiplayer.Sent.Clear();server.Broadcast();var back=MyAPIGateway.Multiplayer.Sent.Find(d=>d.Recipient==11);
   Need(MyAPIGateway.Utilities.SerializeFromBinary<CoreHazardSnapshot>(back.Bytes).Cores[0].Shell.Count==1,"streaming back supplies geometry again");
  }
  static void Main(){Contracts();Transport();Commands();Replicas();Hazards();Console.WriteLine("PASS: "+checks+" production multiplayer transport/handler checks; two clients, listen/dedicated roles, authority, relevance, throttling, late join/reconnect/streaming, ordering, validation and final-hazard removal (engine doubles)");}
 }
}
