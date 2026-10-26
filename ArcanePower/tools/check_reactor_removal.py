"""Exercise actual reactor update/fuel/close methods through deferred deletion.

Small engine doubles deliberately invalidate native block resources before Close,
matching creative removal. Requires Mono and the installed native MyFixedPoint.
"""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'src/Data/Scripts/ArcanePower'
GAME = Path.home() / '.local/share/Steam/steamapps/common/SpaceEngineers/Bin64'


def member(file, signature):
    source = (SCRIPTS / file).read_text()
    start = source.index(signature)
    opening = source.index('{', start)
    depth, end = 1, opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end].replace('public override ', 'public ') + '\n'


methods = ''.join(member(file, signature) for file, signature in [
    ('Reactor.cs', '        private bool IsLive'),
    ('Reactor.cs', '        public override void UpdateOnceBeforeFrame()'),
    ('Reactor.cs', '        public override void UpdateBeforeSimulation()'),
    ('Reactor.cs', '        public override void Close()'),
    ('Reactor.Fuel.cs', '        private void FuelChanged('),
    ('Reactor.Fuel.cs', '        private bool HasUsableFuel()'),
    ('Reactor.Fuel.cs', '        private int FuelTierLimit'),
    ('Reactor.Fuel.cs', '        private float FuelFullLoadMinutes'),
    ('Reactor.Fuel.cs', '        private void RefreshFuelCapacity()'),
    ('Reactor.Fuel.cs', '        private double FuelUnitsPerMinute()'),
    ('Reactor.Fuel.cs', '        private void UpdateFuel()'),
    ('Reactor.Fuel.cs', '        private void PayFuel('),
    ('Reactor.Thermal.cs', '        internal bool ThermalVariant'),
    ('Reactor.Thermal.cs', '        private bool ThermalFuelModeReady'),
    ('Reactor.Thermal.cs', '        private void RefreshThermalCapacity()'),
    ('Reactor.Safety.cs', '        private bool CanOperate'),
])
source = r'''
using System;
using System.Text;
using System.Collections.Generic;
using VRage;
class GatewayRole { public bool IsServer=true; }
class GatewaySession { public bool CreativeMode; }
class GatewayUtilities { public bool IsDedicated=true; }
static class MyAPIGateway {
 public static GatewayRole Multiplayer=new GatewayRole();
 public static GatewaySession Session=new GatewaySession();
 public static GatewayUtilities Utilities=new GatewayUtilities();
 public static class TerminalActionsHelper { public static Terminal GetTerminalSystemForGrid(object g){return null;} }
}
class Terminal { public void GetBlocksOfType<T>(List<T> list,Func<T,bool> predicate){} }
class MyObjectBuilder_Ingot { public string SubtypeName; }
class MyItemType { public string Name; public static MyItemType MakeIngot(string name){return new MyItemType{Name=name};} }
class MyInventoryItem { public MyItemType Type; public MyFixedPoint Amount; }
namespace VRage.Game.Entity {
 class MyInventoryBase {
  public int Subscribers;
  public event Action<MyInventoryBase> ContentsChanged {add{Subscribers++;}remove{Subscribers--;}}
  public int Debits;
  public MyFixedPoint GetItemAmount(MyItemType type){return (MyFixedPoint)10;}
  public void RemoveItemsOfType(MyFixedPoint amount,MyObjectBuilder_Ingot item){Debits++;}
  public bool CanTransferItemTo(MyInventoryBase to,MyItemType type){return false;}
  public void GetItems(List<MyInventoryItem> items,Func<MyInventoryItem,bool> predicate){}
  public void TransferItemFrom(MyInventoryBase from,MyInventoryItem item,MyFixedPoint amount){}
 }
}
class IMyTerminalBlock {
 public bool HasInventory=true;
 public int InventoryCount=1;
 public long OwnerId,EntityId=1;
 public object CubeGrid=new object();
 public bool HasPlayerAccess(long id){return true;}
 public VRage.Game.Entity.MyInventoryBase Inventory=new VRage.Game.Entity.MyInventoryBase();
 public VRage.Game.Entity.MyInventoryBase GetInventory(int slot=0){return Inventory;}
}
class Slim {public float BuildLevelRatio=1;}
class Definition {public string SubtypeName="ArcanePower_ReactorPrototype";}
class IMyReactor : IMyTerminalBlock {
 public bool MarkedForClose,Closed,TornDown,Enabled=true,UseConveyorSystem;
 public bool IsFunctional {get{if(TornDown)throw new NullReferenceException("removed native block");return true;}}
 public Definition Definition=new Definition();
 public Definition BlockDefinition {get{if(TornDown)throw new NullReferenceException("removed definition");return Definition;}}
 public Slim SlimBlock=new Slim();
 public float CurrentOutput=10000,PowerOutputMultiplier=1;
 public event Action OnUpgradeValuesChanged;
 public event Action<IMyTerminalBlock> EnabledChanged;
 public event Action<IMyTerminalBlock,StringBuilder> AppendingCustomInfo;
 public void ClearSubscribers(){OnUpgradeValuesChanged=null;AppendingCustomInfo=null;}
}
class MyReactor : IMyReactor {
 public int CapacityWrites;
 float capacity;
 public float Capacity {get{return capacity;}set{if(TornDown)throw new NullReferenceException("removed native source");capacity=value;CapacityWrites++;}}
}
class MyLight {}
static class MyLights {public static int Removed;public static void RemoveLight(MyLight light){Removed++;}}
static class VentSession {public static int Removed;public static void Remove(Reactor r){Removed++;}}
static class ThermalSession {public static int Removed;public static void Remove(Reactor r){Removed++;}}
enum MyEntityUpdateEnum {NONE,EACH_FRAME}
enum CorePhase {Off,Starting,Running,Cooling,Stopping}
enum VentPhase {Idle,ShieldClosing,Ejecting}
enum ThermalMode {Standalone,Brayton}
class Credit {public double HotMJ;}
class ThermalState {public int LoopVersion;public double ProducedMW,FuelHeatMJ;public Credit Store=new Credit();public ThermalMode Mode,Requested;public bool Settled=true;}
static class ThermalMath {public static double ExportLimit(object store,double capacity,double efficiency,double ramp,double dt){return 100;}}
class State {
 public CorePhase Core=CorePhase.Running;
 public VentPhase Vent=VentPhase.Idle;
 public int FuelTier=1;
 public bool PowerPaused,TileStarved,VentReady=true,SecurityMode=true;
 public float PowerRamp=1,StarvedLoad;
 public long ResiduumMicroUnits;
 public double FuelDebt;
 public ThermalState Thermal=new ThermalState();
}
class Reactor {
 IMyReactor reactor;
 MyReactor nativeReactor=new MyReactor();
 bool closing;
 VRage.Game.Entity.MyInventoryBase fuelInventory;
 MyLight coreGlow=new MyLight();
 State Motion=new State();
 int initializationFrames,controllerRingCapacity=2,networkTick=1;
 float FuelEfficiency=.8f;
 class Grant {public double MaximumMW;}
 Grant standaloneGrant;
 bool ThermalCold=true,ThermalCanRun=true;
 double ThermalHeatMW=25000;
 float ElectricalRatingMW=10000;
 static string[] Fuels={"ArcaneFuelI","ArcaneFuelII","ArcaneFuelIII"};
 static float[] PowerMW={10000,100000,1000000};
 const long ResiduumScale=1000000;const int ResiduumPerCanister=10;
 void RecoverResiduum(){} void ExportResiduum(VRage.Game.Entity.MyInventoryBase target){}
 List<IMyTerminalBlock> fuelSources=new List<IMyTerminalBlock>();
 List<MyInventoryItem> transferItems=new List<MyInventoryItem>();
 MyEntityUpdateEnum NeedsUpdate=MyEntityUpdateEnum.EACH_FRAME;
 int steps,saves,soundStops;
 Reactor(bool thermal=false){reactor=nativeReactor;if(thermal)nativeReactor.Definition.SubtypeName="ArcanePower_Thermal_ReactorHousing";fuelInventory=reactor.Inventory;fuelInventory.ContentsChanged+=FuelChanged;}
 void CheckContainment(){steps++;}
 void InitializeMotion(){steps++;} void InitializeFuel(){steps++;} void InitializeThermalRuntime(){steps++;}
 void ThermalEnabledChanged(IMyTerminalBlock b){}
 void AppendInfo(IMyTerminalBlock b,StringBuilder s){}
 void RefreshRestPoses(){steps++;} void CheckVentRoute(){steps++;} void UpdatePower(){steps++;}
 void UpdateSafety(){steps++;} void UpdateThermalMode(){steps++;} void UpdateTiles(){steps++;}
 void UpdateMotion(){steps++;} void UpdateAppearance(){steps++;} void UpdateSound(){steps++;}
 void DrawMotion(){steps++;} void DrawVentOutlet(){steps++;}
 void CloseSound(){soundStops++;} void SaveMotion(){saves++;}
 void PullTiles(VRage.Game.Entity.MyInventoryBase source,VRage.Game.Entity.MyInventoryBase target){}
 bool HasAdvancedController(){return true;}
''' + methods + r'''
 static void Need(bool condition,string message){if(!condition)throw new Exception(message);}
 static void Main(){
  foreach(bool creative in new[]{true,false})foreach(bool thermal in new[]{false,true}) {
   MyAPIGateway.Session.CreativeMode=creative;
   var live=new Reactor(thermal);live.UpdateBeforeSimulation();
   Need(live.steps>0 && live.nativeReactor.CapacityWrites>0,"live running reactor must still update/generate");
   if(!creative && !thermal)Need(live.reactor.Inventory.Debits>0,"live survival fuel still consumed");
   foreach(string phase in new[]{"marked","closed","inventory","slim","cleanup"}) {
    var r=new Reactor(thermal);var subscribed=r.fuelInventory;
    if(phase=="marked")r.reactor.MarkedForClose=true;
    if(phase=="closed")r.reactor.Closed=true;
    if(phase=="inventory")r.reactor.Inventory=null;
    if(phase=="slim")r.reactor.SlimBlock=null;
    if(phase=="cleanup")r.Close();
    r.nativeReactor.TornDown=true;
    int steps=r.steps,writes=r.nativeReactor.CapacityWrites;
    r.UpdateOnceBeforeFrame();r.UpdateBeforeSimulation();
    r.UpdateFuel();r.RefreshFuelCapacity();r.RefreshThermalCapacity();r.FuelChanged(subscribed);
    Need(r.steps==steps && r.nativeReactor.CapacityWrites==writes,"late updates/callbacks cannot touch removed resources: "+phase);
    Need(!r.HasUsableFuel() && !r.ThermalVariant,"removed reactor must not advertise usable fuel or a thermal source");
    // The current inventory may disappear before GameLogic.Close. Unsubscribe
    // from the inventory that was actually registered, including repeated Close.
    r.reactor.Inventory=null;r.Close();r.Close();
    Need(subscribed.Subscribers==0 && r.fuelInventory==null,"original inventory callback removed exactly once");
    Need(r.saves==1 && r.soundStops==1 && r.NeedsUpdate==MyEntityUpdateEnum.NONE,"cleanup must be complete and idempotent");
   }
  }
  Console.WriteLine("PASS: creative/survival, prototype/thermal, deferred removal, late ticks and inventory callbacks, live fuel/capacity, cached cleanup and repeated Close");
 }
}
'''
with tempfile.TemporaryDirectory(prefix='arcane-removal-check-') as folder:
    path = Path(folder) / 'check.cs'
    path.write_text(source)
    exe = path.with_suffix('.exe')
    subprocess.run(['mcs', '-langversion:6', '-warn:0', '-r:/usr/lib/mono/4.5/Facades/netstandard.dll',
                    '-r:' + str(GAME / 'VRage.Library.dll'), '-out:' + str(exe), str(path)], check=True)
    subprocess.run(['mono', str(exe)], check=True, env={**os.environ, 'MONO_PATH': str(GAME)})
