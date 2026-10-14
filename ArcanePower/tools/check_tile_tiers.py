"""Focused offline check of shipped tile accounting and save state; requires Mono.

Recording stand-ins exercise the actual C# methods without loading a world.
"""
from pathlib import Path
import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
GAME = Path.home() / ".local/share/Steam/steamapps/common/SpaceEngineers/Bin64"
tiles = (ROOT / "src/Data/Scripts/ArcanePower/Reactor.Tiles.cs").read_text()
motion = (ROOT / "src/Data/Scripts/ArcanePower/Reactor.Motion.cs").read_text()
state = motion[motion.index("    public enum CorePhase"):motion.index("    public sealed partial class Reactor")]
validation = motion[motion.index("        internal static bool Valid("):motion.index("        internal void ReceiveState(")]
accounting = tiles[tiles.index("        private static readonly string[] TileSubtypes"):tiles.index("        private Matrix MaintenancePose(")]
pull = tiles[tiles.index("        private void PullTiles("):tiles.rindex("    }")]
STUBS = r'''
using System;
using System.Collections.Generic;
using System.IO;
using System.Xml.Serialization;
using ProtoBuf;
using Sandbox.Common.ObjectBuilders;
using Sandbox.ModAPI;
using VRage;
using VRage.Game.ModAPI.Ingame;
using VRageMath;
namespace Sandbox.Common.ObjectBuilders { public class MyObjectBuilder_Component { public string SubtypeName; } }
namespace Sandbox.ModAPI {
    public static class MyAPIGateway {
        public static class Session { public static bool CreativeMode; }
        public static class Multiplayer { public static bool IsServer=true; }
    }
}
namespace VRageMath { public static class MathHelper { public static float Clamp(float n,float lo,float hi) { return Math.Max(lo,Math.Min(hi,n)); } } }
namespace VRage.Game.ModAPI.Ingame {
    public struct MyItemType {
        public string Id;
        public static MyItemType MakeComponent(string id) { return new MyItemType{Id=id}; }
        public static bool operator ==(MyItemType a,MyItemType b) { return a.Id==b.Id; }
        public static bool operator !=(MyItemType a,MyItemType b) { return a.Id!=b.Id; }
        public override bool Equals(object o) { return o is MyItemType && this==(MyItemType)o; }
        public override int GetHashCode() { return Id.GetHashCode(); }
    }
    public struct MyInventoryItem { public MyItemType Type; public MyFixedPoint Amount; }
}
namespace VRage.Game.ModAPI {
    public class IMyInventory {
        public Dictionary<string,int> Stock=new Dictionary<string,int>();
        public int Removed;
        public int Count(string id) { return Stock.ContainsKey(id)?Stock[id]:0; }
        public MyFixedPoint GetItemAmount(MyItemType type) { return (MyFixedPoint)Count(type.Id); }
        public void RemoveItemsOfType(MyFixedPoint amount,MyObjectBuilder_Component item) {
            int n=(int)(double)amount;
            if(n>Count(item.SubtypeName))throw new Exception("over-consumption");
            Stock[item.SubtypeName]=Count(item.SubtypeName)-n;Removed+=n;
        }
        public bool CanTransferItemTo(IMyInventory target,MyItemType type) { return true; }
        public void GetItems(List<MyInventoryItem> items,Func<MyInventoryItem,bool> predicate) {
            foreach(var pair in Stock){var item=new MyInventoryItem{Type=MyItemType.MakeComponent(pair.Key),Amount=(MyFixedPoint)pair.Value};if(predicate(item))items.Add(item);}
        }
        public void TransferItemFrom(IMyInventory source,MyInventoryItem item,MyFixedPoint amount) {
            int n=(int)(double)amount;source.Stock[item.Type.Id]-=n;Stock[item.Type.Id]=Count(item.Type.Id)+n;
        }
    }
}
namespace ArcanePower {
'''
CHECKS = r'''
    class FakeReactor {
        public VRage.Game.ModAPI.IMyInventory Inventory=new VRage.Game.ModAPI.IMyInventory();
        public bool Enabled=true,IsFunctional=true;
        public float CurrentOutput=10000;
        public VRage.Game.ModAPI.IMyInventory GetInventory() { return Inventory; }
    }
    public sealed partial class Reactor {
        FakeReactor reactor=new FakeReactor();
        MotionState Motion=new MotionState();
        float[] PowerMW={10000,100000,1000000};
        List<MyInventoryItem> transferItems=new List<MyInventoryItem>();
        void SaveMotion() {}
        void BeginShutdown() {}
        void RefreshFuelCapacity() {}
        void PublishMotion() {}
        static void Need(bool ok,string message) { if(!ok)throw new Exception(message); }
        void Stock(int grade,int n) { reactor.Inventory.Stock[TileSubtypes[grade]]=n; }
        static void Main() {
            var r=new Reactor();r.Stock(2,40);r.Stock(1,40);
            Need(r.PrepareTiles(),"mixed-grade shell starts");
            Need(TileNames[2]=="Advanced","grade labels");
            Need(r.reactor.Inventory.Removed==80 && r.Motion.InstalledTiles==80,"exact 80-tile debit");
            for(int i=0;i<20;i++)Need(r.InstalledTileGrade(i)==(i<10?2:1),"highest-grade allocation");
            Need(r.PrepareTiles() && r.reactor.Inventory.Removed==80,"normal restart preserves installed tiles");
            for(int fuel=1;fuel<=3;fuel++) {
                r.Motion.FuelTier=fuel;r.Motion.Load=1;r.Motion.Heat=1;
                r.Motion.TileGrades[0]=0;float rate=r.TileWearRate();
                r.Motion.TileGrades[0]=1;Need(Math.Abs(rate/r.TileWearRate()-10)<.001,"10x life for every fuel");
                r.Motion.TileGrades[0]=2;Need(Math.Abs(rate/r.TileWearRate()-100)<.001,"100x life for every fuel");
            }
            var shortStock=new Reactor();shortStock.Stock(2,76);
            Need(!shortStock.PrepareTiles() && shortStock.reactor.Inventory.Removed==0,"short startup must consume nothing");
            shortStock.Stock(0,3);shortStock.Stock(1,1);
            Need(!shortStock.PrepareTiles(),"quartet cannot silently mix different grades");
            var existing=new Reactor();existing.Motion.InstalledTiles=80;existing.Motion.TileWear=.5f;
            Need(existing.InstalledTileGrade(0)==0 && Valid(existing.Motion),"new shell state has explicit Standard grades");
            existing.Stock(2,80);Need(existing.PrepareTiles(),"installed shell restarts");
            Need(existing.InstalledTileGrade(0)==0 && existing.Motion.TileWear==.5f && existing.reactor.Inventory.Removed==0,"stock cannot upgrade installed tiles for free");
            existing.Motion.TileWear=1;existing.Motion.TileStarved=true;existing.Motion.Core=CorePhase.Cooling;
            existing.UpdateTiles();
            Need(existing.InstalledTileGrade(0)==2 && existing.reactor.Inventory.Removed==4,"cooldown repair consumes best quartet");
            Need(!existing.Motion.TileStarved && existing.Motion.TileWear==0 && existing.Motion.MaintenanceTick==0,"repair clears starvation and starts animation");
            var starvation=new Reactor();starvation.Motion.Core=CorePhase.Running;starvation.Motion.InstalledTiles=80;
            starvation.Motion.TileWear=.99999f;starvation.UpdateTiles();
            Need(starvation.Motion.TileStarved && starvation.Motion.StarvedLoad==1,"missing quartet captures load on failure");
            starvation.Stock(1,4);starvation.UpdateTiles();
            Need(!starvation.Motion.TileStarved && starvation.reactor.Inventory.Removed==4,"Reinforced resupply recovers failure");
            var reserve=new Reactor();reserve.Motion.InstalledTiles=80;reserve.Motion.Load=1;
            Need(Math.Abs(reserve.TileReserveSeconds()-60)<.01,"Standard reserve prediction");
            reserve.Motion.TileGrades=new int[20];for(int i=0;i<20;i++)reserve.Motion.TileGrades[i]=2;
            Need(Math.Abs(reserve.TileReserveSeconds()-6000)<.01,"Advanced reserve prediction");
            reserve.Motion.TileGrades[1]=1;reserve.Stock(0,4);
            Need(Math.Abs(reserve.TileReserveSeconds()-6600)<.01,"mixed installed-grade prediction");
            reserve.Motion.MaintenanceTick=0;reserve.Stock(0,0);
            Need(Math.Abs(reserve.TileReserveSeconds()-600)<.01,"paid replacement forecasts next quartet");
            var serializer=new XmlSerializer(typeof(MotionState));var xml=new StringWriter();serializer.Serialize(xml,r.Motion);
            var restored=(MotionState)serializer.Deserialize(new StringReader(xml.ToString()));
            Need(Valid(restored) && restored.TileGrades[10]==1,"save roundtrip preserves mixed grades");
            var model=ProtoBuf.Meta.RuntimeTypeModel.Create();
            var packet=new MemoryStream();model.Serialize(packet,r.Motion);packet.Position=0;
            var snapshot=(MotionState)model.Deserialize(packet,null,typeof(MotionState));
            Need(Valid(snapshot) && snapshot.TileGrades[10]==1,"network roundtrip preserves mixed grades");
            restored.TileGrades=null;Need(!Valid(restored),"missing grade state rejected");
            restored.TileGrades=new int[19];Need(!Valid(restored),"malformed ledger rejected");
            restored.TileGrades=new int[20];restored.TileGrades[0]=3;Need(!Valid(restored),"invalid grade rejected");
            r.DiscardTiles();Need(r.Motion.TileGrades[0]==0 && r.Motion.InstalledTiles==0 && r.Motion.TileWear==0,"vent/detonation discard grade ledger");
            MyAPIGateway.Session.CreativeMode=true;
            Need(r.PrepareTiles() && r.reactor.Inventory.Removed==80,"creative has free compatible shell");
            MyAPIGateway.Session.CreativeMode=false;
            var source=new VRage.Game.ModAPI.IMyInventory();source.Stock[TileSubtypes[2]]=100;
            var conveyor=new Reactor();conveyor.Stock(0,80);conveyor.PullTiles(source,conveyor.reactor.Inventory);
            Need(conveyor.reactor.Inventory.Count(TileSubtypes[2])==80 && source.Count(TileSubtypes[2])==20,"better tiles pull despite full Standard reserve");
            Console.WriteLine("PASS: mixed reservation, all fuels, 10x/100x life, restart, explicit grade state, starvation/recovery, forecast, validation, discard, creative, conveyors");
        }
'''
with tempfile.TemporaryDirectory(prefix="arcane-tile-check-") as folder:
    source = Path(folder) / "check.cs"
    source.write_text(STUBS + state + CHECKS + accounting + validation + pull + "}}")
    exe = source.with_suffix(".exe")
    subprocess.run(["mcs", "-r:/usr/lib/mono/4.5/Facades/netstandard.dll", "-r:" + str(GAME / "VRage.Library.dll"), "-r:" + str(GAME / "ProtoBuf.Net.Core.dll"), "-r:" + str(GAME / "ProtoBuf.Net.dll"), "-out:" + str(exe), str(source)], check=True)
    subprocess.run(["mono", str(exe)], check=True, env={**os.environ, "MONO_PATH": str(GAME)})

components = ET.parse(ROOT / "src/Data/ContainmentTiles.sbc").findall("Components/Component")
recipes = ET.parse(ROOT / "src/Data/ContainmentTileBlueprints.sbc").findall("Blueprints/Blueprint")
assert len(components) == len(recipes) == 3
for component, recipe, factor in zip(components, recipes, (1, 10, 100)):
    assert recipe.find("Result").get("SubtypeId") == component.findtext("Id/SubtypeId")
    assert recipe.find("Result").get("Amount") == "4"
    assert float(recipe.findtext("BaseProductionTimeInSeconds")) == 10 * factor
    inputs = {(n.get("TypeId"), n.get("SubtypeId")): float(n.get("Amount")) for n in recipe.findall("Prerequisites/Item")}
    base = {("Ingot", "Iron"): 20, ("Ingot", "Cobalt"): 8, ("Ingot", "Silver"): 4,
            ("Ingot", "Platinum"): 2, ("Component", "Superconductor"): 4,
            ("Component", "Computer"): 4, ("Component", "Detector"): 1, ("Component", "MetalGrid"): 4}
    assert inputs == {key: amount * factor for key, amount in base.items()}
    assert float(component.findtext("Volume")) == 2
inventory = ET.parse(ROOT / "src/Data/CubeBlocks/ArcanePower_ReactorPrototype.sbc").find("CubeBlocks/Definition/InventorySize")
assert tuple(float(inventory.findtext(axis)) for axis in "XYZ") == (2, 1, 1)
print("PASS: three recipes with 1x/10x/100x costs and times, 2,000 L inventory")
