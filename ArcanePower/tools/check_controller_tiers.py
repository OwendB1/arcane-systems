"""Focused offline proof of shipped controller deployment/fuel logic; requires Mono.

Extracts actual C# methods; stand-ins supply inventories, upgrades and native output.
"""
from pathlib import Path
import os
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
GAME = Path.home() / ".local/share/Steam/steamapps/common/SpaceEngineers/Bin64"
SCRIPTS = ROOT / "src/Data/Scripts/ArcanePower"
motion = (SCRIPTS / "Reactor.Motion.cs").read_text()
fuel = (SCRIPTS / "Reactor.Fuel.cs").read_text()
reactor = (SCRIPTS / "Reactor.cs").read_text()


def method(source, signature):
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


state = motion[motion.index("    public enum CorePhase"):motion.index("    public sealed partial class Reactor")]
fuel_fields = fuel[fuel.index("        private static readonly string[] Fuels"):fuel.index("        private MyReactor nativeReactor;")]
methods = "\n".join([
    method(reactor, "        private void CheckContainment()"),
    method(motion, "        private void AdvanceMotion()"),
    method(motion, "        private void AdvanceSpin()"),
    method(motion, "        private void BeginDismantling()"),
    method(motion, "        private void BeginShutdown()"),
    method(motion, "        internal static bool Valid("),
    method(fuel, "        private bool HasUsableFuel()"),
    method(fuel, "        private void RefreshFuelCapacity()"),
    method(fuel, "        private double FuelUnitsPerMinute()"),
    method(fuel, "        private void UpdateFuel()"),
    method((SCRIPTS / "Reactor.Tiles.cs").read_text(), "        private static bool ValidTileGrades("),
])
safety = (SCRIPTS / "Reactor.Safety.cs").read_text()
methods += safety[safety.index("        private bool CanOperate"):safety.index("        private bool NeedsAutoEjection")]
STUBS = r'''
using System;
using System.Collections.Generic;
using System.IO;
using System.Xml.Serialization;
using ProtoBuf;
using Sandbox.Common.ObjectBuilders;
using Sandbox.ModAPI;
using VRage;
using VRage.Utils;
using VRage.Game.ModAPI.Ingame;
namespace Sandbox.Common.ObjectBuilders { public class MyObjectBuilder_Ingot { public string SubtypeName; } }
namespace VRage.Utils {
    public class MyLog {
        public static MyLog Default=new MyLog();
        public void WriteLineAndConsole(string text) {}
    }
}
namespace VRage.Game.ModAPI.Ingame {
    public struct MyItemType {
        public string Id;
        public static MyItemType MakeIngot(string id) { return new MyItemType{Id=id}; }
        public static bool operator ==(MyItemType a,MyItemType b) { return a.Id==b.Id; }
        public static bool operator !=(MyItemType a,MyItemType b) { return a.Id!=b.Id; }
        public override bool Equals(object o) { return o is MyItemType && this==(MyItemType)o; }
        public override int GetHashCode() { return Id.GetHashCode(); }
    }
    public struct MyInventoryItem { public MyItemType Type; public MyFixedPoint Amount; }
    public class Inventory {
        public Dictionary<string,double> Stock=new Dictionary<string,double>();
        public double Count(string id) { return Stock.ContainsKey(id)?Stock[id]:0; }
        public MyFixedPoint GetItemAmount(MyItemType type) { return (MyFixedPoint)Count(type.Id); }
        public void RemoveItemsOfType(MyFixedPoint amount,MyObjectBuilder_Ingot item) { Stock[item.SubtypeName]=Count(item.SubtypeName)-(double)amount; }
        public bool CanTransferItemTo(Inventory target,MyItemType type) { return true; }
        public void GetItems(List<MyInventoryItem> items,Func<MyInventoryItem,bool> filter) {}
        public void TransferItemFrom(Inventory source,MyInventoryItem item,MyFixedPoint amount) {}
    }
    public class IMyTerminalBlock {
        public bool HasInventory=true;
        public int InventoryCount=1;
        public long OwnerId,EntityId=1;
        public object CubeGrid;
        public bool HasPlayerAccess(long owner) { return true; }
        public Inventory Inventory=new Inventory();
        public Inventory GetInventory(int slot=0) { return Inventory; }
    }
    public class Slim { public float BuildLevelRatio=1; }
    public class IMyReactor : IMyTerminalBlock {
        public bool Enabled=true,IsFunctional=true,UseConveyorSystem;
        public Slim SlimBlock=new Slim();
        public float CurrentOutput,PowerOutputMultiplier=1;
        public Dictionary<string,float> UpgradeValues=new Dictionary<string,float>();
        public void RefreshCustomInfo() {}
    }
}
namespace Sandbox.ModAPI {
    public static class MyAPIGateway {
        public static class Session { public static bool CreativeMode; }
        public static class Multiplayer { public static bool IsServer=true; }
        public static class TerminalActionsHelper {
            public static Terminal GetTerminalSystemForGrid(object grid) { return null; }
        }
    }
    public class Terminal {
        public void GetBlocksOfType<T>(List<T> blocks,Func<T,bool> predicate) {}
    }
}
namespace ArcanePower {
    class NativeReactor { public float Capacity; }
    public sealed partial class Reactor {
        IMyReactor reactor=new IMyReactor();
        NativeReactor nativeReactor=new NativeReactor();
        MotionState Motion=new MotionState();
        int controllerRingCapacity=2,initializationFrames,networkTick=1,appearanceRefresh;
        float previousControllers=-1;
        bool receivedState=true,restoreLegacyHardware;
        static int[] TileTypes=new int[3];
        const float CooldownHeat=.15f;
        List<IMyTerminalBlock> fuelSources=new List<IMyTerminalBlock>();
        List<MyInventoryItem> transferItems=new List<MyInventoryItem>();
        long Id { get { return reactor.EntityId; } }
        void DiscardTiles() {}
        void PullTiles(Inventory source,Inventory target) {}
'''
CHECKS = r'''
        static void Need(bool ok,string message) { if(!ok)throw new Exception(message); }
        static void Near(double actual,double expected,string message,double tolerance=.00001) { Need(Math.Abs(actual-expected)<=tolerance*Math.Max(1,Math.Abs(expected)),message+": "+actual+" != "+expected); }
        void Hardware(int capacity,int count=2) {
            reactor.UpgradeValues["ArcaneContainment"]=capacity;
            reactor.UpgradeValues["ArcaneControllerCount"]=count;
            CheckContainment();
        }
        static void Main() {
            // Native conversion rounds up; the former floor-based double hid this regression.
            Need((double)(MyFixedPoint).0000006==.000001,"native millionth rounding");
            for(int rings=2;rings<=4;rings++) {
                foreach(float load in new[]{.000001f,.0001f,.00026955022f,.4f,1f}) {
                    var r=new Reactor();r.Hardware(rings);
                    r.reactor.Inventory.Stock[Fuels[0]]=100;
                    r.Motion.Core=CorePhase.Running;r.Motion.VentReady=true;r.Motion.PowerRamp=1;
                    r.reactor.CurrentOutput=PowerMW[0]*load;
                    double expected=0;int credits=0,reloads=0;
                    // Smaller canister debits need longer to cross a native
                    // millionth at tiny loads and exercise rounding credits.
                    int ticks=Math.Max(20000,(int)Math.Ceiling(.000002/(r.FuelUnitsPerMinute()/3600)));
                    for(int tick=0;tick<ticks;tick++) {
                        expected+=r.FuelUnitsPerMinute()/3600;
                        r.UpdateFuel();
                        Need(Valid(r.Motion),"every native-rounded running snapshot remains valid");
                        if(r.Motion.FuelDebt<0) {
                            credits++;
                            if(reloads<10) {
                                var roundtripSerializer=new XmlSerializer(typeof(MotionState));var roundtripXml=new StringWriter();
                                roundtripSerializer.Serialize(roundtripXml,r.Motion);
                                r.Motion=(MotionState)roundtripSerializer.Deserialize(new StringReader(roundtripXml.ToString()));
                                Need(Valid(r.Motion) && r.Motion.FuelDebt<0,"reload preserves rounding credit");
                                reloads++;
                            }
                        }
                    }
                    Need(credits>0 && reloads==10,"exercise negative credits at every load and controller tier");
                    Near(100-r.reactor.Inventory.Count(Fuels[0])+r.Motion.FuelDebt,expected,"accounting across repeated low/full-load reloads",1e-8);
                }
            }
            Console.WriteLine("PASS: native fixed-point rounding, per-tick save validity and exact accounting through repeated reloads at five loads and all controller tiers");
            for(int rings=2;rings<=4;rings++) {
                double efficiency=new double[]{.8,.9,.99}[rings-2];
                for(int tier=1;tier<rings;tier++) {
                    var r=new Reactor();r.Hardware(rings);
                    r.reactor.Inventory.Stock[Fuels[tier-1]]=10;
                    r.UpdateFuel();
                    Need(r.Motion.FuelTier==tier && r.Motion.RingCount==rings,"idle selects compatible fuel independently of hardware");
                    Near(r.reactor.PowerOutputMultiplier,PowerMW[tier-1]/PowerMW[0],"fuel determines output rating");
                    r.Motion.Core=CorePhase.Starting;r.Motion.CoreTick=320;
                    r.AdvanceMotion();
                    Near(r.Motion.CoreTick+r.Motion.CoreSubtick,320+rings*.5,"controller determines deployment speed for every fuel");
                    int ticks=1;
                    while(r.Motion.CoreTick<1038) { r.AdvanceMotion();ticks++; }
                    Need(ticks==(int)Math.Ceiling(718/(rings*.5)),"complete assembly duration depends on hardware");
                    r.Motion.Core=CorePhase.Running;r.Motion.PowerRamp=1;r.Motion.VentReady=true;
                    r.reactor.CurrentOutput=PowerMW[tier-1];
                    Near(r.FuelUnitsPerMinute(),.1/efficiency,"full-load canister consumption");
                    Near(1/r.FuelUnitsPerMinute(),10*efficiency,"one canister lasts 8/9/9.9 minutes");
                    double before=r.reactor.Inventory.Count(Fuels[tier-1]);
                    for(int i=0;i<3600;i++)r.UpdateFuel();
                    Near(before-r.reactor.Inventory.Count(Fuels[tier-1])+r.Motion.FuelDebt,.1/efficiency,"one-minute canister debit");
                    Near(r.nativeReactor.Capacity,PowerMW[tier-1]/216000,"efficiency preserves fuel-rated maximum output");
                    r.Motion.VentReady=false;r.Motion.SecurityMode=false;r.RefreshFuelCapacity();
                    Near(r.nativeReactor.Capacity,PowerMW[tier-1]/216000,"warning mode preserves running output with broken vents");
                    r.reactor.SlimBlock.BuildLevelRatio=.99f;r.RefreshFuelCapacity();
                    Need(r.nativeReactor.Capacity==0,"grinding below full build blocks generation even in warning mode");
                    r.reactor.SlimBlock.BuildLevelRatio=1;r.RefreshFuelCapacity();
                    Near(r.nativeReactor.Capacity,PowerMW[tier-1]/216000,"restored full build restores eligible output");
                    r.Motion.SecurityMode=true;r.RefreshFuelCapacity();
                    Need(r.nativeReactor.Capacity==0,"security mode blocks output with broken vents");
                    r.Motion.VentReady=true;
                    r.reactor.CurrentOutput*=.4f;
                    Near(r.FuelUnitsPerMinute(),.04/efficiency,"partial-load efficiency");
                    r.Motion.MaintenanceTick=0;r.AdvanceMotion();
                    Near(r.Motion.MaintenanceTick,rings*.5,"controller determines replacement speed");
                    r.reactor.Inventory.Stock[Fuels[tier-1]]=.000001;
                    r.RefreshFuelCapacity();
                    Near(r.nativeReactor.Capacity,.00001*PowerMW[tier-1]*efficiency/60,"near-empty canister capacity",.0000001);
                    r.Motion.TileStarved=true;r.Motion.StarvedLoad=.4f;
                    Near(r.FuelUnitsPerMinute(),.4/efficiency,"starvation efficiency");
                    r.RefreshFuelCapacity();
                    Near(r.nativeReactor.Capacity,.00001*PowerMW[tier-1]*efficiency/6000,"starvation near-empty canister capacity",.0000001);
                    r.reactor.Inventory.Stock[Fuels[tier-1]]=10;r.RefreshFuelCapacity();
                    Near(r.nativeReactor.Capacity,PowerMW[tier-1]*.04/216000,"starvation caps actual output without changing rating");
                }
            }
            var advanced=new Reactor();advanced.Hardware(4);
            advanced.reactor.Inventory.Stock[Fuels[0]]=10;advanced.UpdateFuel();
            Need(advanced.Motion.FuelTier==1 && advanced.Motion.RingCount==4,"Aether uses all four advanced rings");
            advanced.Motion.Core=CorePhase.Starting;advanced.Motion.CoreTick=320;
            advanced.reactor.Inventory.Stock[Fuels[2]]=10;advanced.UpdateFuel();
            Need(advanced.Motion.FuelTier==1 && advanced.Motion.RingCount==4,"fuel/deployment lock during operation");
            advanced.Motion.Core=CorePhase.Running;advanced.Motion.Heat=.5f;
            advanced.Hardware(2);advanced.BeginShutdown();
            Need(!advanced.reactor.Enabled && advanced.Motion.RingCount==4,"hardware change shuts down without losing deployed rings");
            Need(advanced.Motion.Core==CorePhase.Cooling,"hardware shutdown cools a hot running core");
            advanced.Motion.MaintenanceTick=0;
            advanced.Hardware(2);advanced.AdvanceMotion();
            Need(advanced.Motion.RingCount==4 && advanced.Motion.MaintenanceTick==2,"cooldown preserves deployed replacement rate");
            advanced.Motion.Core=CorePhase.Stopping;advanced.Hardware(2);
            Need(advanced.Motion.RingCount==4,"dismantling preserves deployed rings");
            advanced.Motion.Core=CorePhase.Off;advanced.Motion.Vent=VentPhase.Ejecting;advanced.Hardware(2);
            Need(advanced.Motion.RingCount==4,"ejection preserves deployed rings");
            advanced.Motion.Vent=VentPhase.Idle;advanced.Hardware(2);
            Need(advanced.Motion.RingCount==2,"next idle cycle adopts new hardware");
            var restored=new Reactor();restored.Motion.RingCount=4;restored.Motion.Core=CorePhase.Running;
            restored.initializationFrames=120;restored.Hardware(2);
            Need(restored.reactor.Enabled && restored.Motion.RingCount==4,"restore waits for native controller connections");
            restored.initializationFrames=0;restored.Hardware(2);
            Need(!restored.reactor.Enabled && restored.Motion.RingCount==4,"restored hardware mismatch forces shutdown");
            var single=new Reactor();single.Hardware(2,1);
            Need(!single.reactor.Enabled,"one advanced controller cannot satisfy interlock");
            var removed=new Reactor();removed.Hardware(4);removed.Motion.Core=CorePhase.Running;removed.Motion.Heat=.5f;
            removed.Hardware(2,0);removed.BeginShutdown();
            Need(!removed.reactor.Enabled && removed.Motion.Core==CorePhase.Cooling && removed.Motion.RingCount==4,"removing controllers preserves the cooling field");
            var client=new Reactor();MyAPIGateway.Multiplayer.IsServer=false;
            client.Motion.RingCount=4;client.Motion.FuelTier=1;client.Hardware(2);client.UpdateFuel();
            Need(client.Motion.RingCount==4 && client.reactor.Enabled,"clients retain synchronized deployment");
            MyAPIGateway.Multiplayer.IsServer=true;
            var saved=new MotionState{FuelTier=1,RingCount=4,SecurityMode=false,ControllersReady=true};
            var serializer=new XmlSerializer(typeof(MotionState));var xml=new StringWriter();serializer.Serialize(xml,saved);
            var copy=(MotionState)serializer.Deserialize(new StringReader(xml.ToString()));
            Need(Valid(copy) && copy.FuelTier==1 && copy.RingCount==4 && !copy.SecurityMode && copy.ControllersReady,"XML preserves distinct tiers and security settings");
            var model=ProtoBuf.Meta.RuntimeTypeModel.Create();var packet=new MemoryStream();model.Serialize(packet,saved);packet.Position=0;
            copy=(MotionState)model.Deserialize(packet,null,typeof(MotionState));
            Need(Valid(copy) && copy.FuelTier==1 && copy.RingCount==4 && !copy.SecurityMode && copy.ControllersReady,"protobuf preserves distinct tiers and warning mode");
            saved.SecurityMode=true;packet=new MemoryStream();model.Serialize(packet,saved);packet.Position=0;
            copy=(MotionState)model.Deserialize(packet,null,typeof(MotionState));
            Need(copy.SecurityMode,"protobuf preserves default security-on mode");
            saved.FuelDebt=-2.288216908615642E-07;packet=new MemoryStream();model.Serialize(packet,saved);packet.Position=0;
            copy=(MotionState)model.Deserialize(packet,null,typeof(MotionState));
            Need(Valid(copy) && copy.FuelDebt==saved.FuelDebt,"network packet preserves valid negative rounding credit");
            copy.FuelTier=0;Need(!Valid(copy),"invalid fuel tier rejected");copy.FuelTier=1;
            copy.RingCount=1;Need(!Valid(copy),"invalid ring count rejected");copy.RingCount=5;Need(!Valid(copy),"excess rings rejected");
            Console.WriteLine("PASS: all compatible fuel/controller pairs, deployment and maintenance speed, efficiency/debit/capacity, hardware change/removal/restore, client state, XML/protobuf validation");
        }
    }
}
'''
with tempfile.TemporaryDirectory(prefix="arcane-controller-check-") as folder:
    source = Path(folder) / "check.cs"
    source.write_text(STUBS.replace("namespace ArcanePower {", "namespace ArcanePower {\n" + state)
                      + fuel_fields + methods + CHECKS)
    exe = source.with_suffix(".exe")
    subprocess.run(["mcs", "-warn:0", "-r:/usr/lib/mono/4.5/Facades/netstandard.dll",
                    "-r:" + str(GAME / "ProtoBuf.Net.Core.dll"), "-r:" + str(GAME / "ProtoBuf.Net.dll"),
                    "-r:" + str(GAME / "VRage.Library.dll"),
                    "-out:" + str(exe), str(source)], check=True)
    subprocess.run(["mono", str(exe)], check=True, env={**os.environ, "MONO_PATH": str(GAME)})

# Presentation and physical payload must use the same saved deployed hardware.
assert "i < Motion.RingCount && alive > 0" in method(motion, "        private void DrawMotion()")
failure = (SCRIPTS / "Reactor.Failure.cs").read_text()
assert "for (int i = 0; i < Motion.RingCount; i++)" in failure
assert "Motion.RingCount = controllerRingCapacity;" in method(motion, "        private void UpdateMotion()")
assert not re.search(r"\bMotion\.Profile\b", "\n".join(p.read_text() for p in SCRIPTS.glob("Reactor*.cs")))
print("PASS: visible/ejected rings use saved hardware, startup latches controller capacity")
