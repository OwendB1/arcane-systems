"""Exercise the shipped assembly-marker code against native MWM sockets and rotated grids."""
from pathlib import Path
import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src/Data/Scripts/ArcanePower'
GAME = Path.home() / '.local/share/Steam/steamapps/common/SpaceEngineers/Bin64'
definitions = ET.parse(ROOT / 'src/Data/CubeBlocks/ArcanePower_Thermal.sbc')
model = next(d.findtext('Model') for d in definitions.findall('CubeBlocks/Definition')
             if d.findtext('Id/SubtypeId') == 'ArcanePower_Thermal_ReactorHousing')
status = (SRC / 'Reactor.Status.cs').read_text()
types = status[status.index('    internal sealed class StatusRow'):]
fixture = r'''
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using VRageMath;
using VRageRender.Import;
using VRage.Game.ModAPI;
using Sandbox.Game.Entities;
namespace VRage.ModAPI { public interface IMyEntity { Model Model {get;} } }
namespace VRage.Game.ModAPI {
 public interface IMyModelDummy { Matrix Matrix {get;} }
 public class Dummy:IMyModelDummy { public Matrix Matrix {get;set;} }
 public class Model {
  public Dictionary<string,IMyModelDummy> Dummies=new Dictionary<string,IMyModelDummy>();
  public void GetDummies(Dictionary<string,IMyModelDummy> to){foreach(var p in Dummies)to.Add(p.Key,p.Value);}
 }
 public class Grid {
  public object Physics=new object(); public float GridSize=2.5f; public MatrixD WorldMatrix;
  public Dictionary<Vector3I,IMySlimBlock> Blocks=new Dictionary<Vector3I,IMySlimBlock>();
  public IMySlimBlock GetCubeBlock(Vector3I cell){IMySlimBlock b;return Blocks.TryGetValue(cell,out b)?b:null;}
  public Vector3D GridIntegerToWorld(Vector3I cell){return Vector3D.Transform((Vector3D)cell*GridSize,WorldMatrix);}
 }
 public class Id { public string SubtypeName; }
 public class Definition { public Id Id=new Id(); public string SubtypeName {get{return Id.SubtypeName;}} }
 public class IMySlimBlock {
  public IMyCubeBlock FatBlock;public float BuildLevelRatio=1;
  public Grid CubeGrid {get{return FatBlock.CubeGrid;}} public Definition BlockDefinition {get{return FatBlock.BlockDefinition;}}
 }
 public class Logic { public object Component;public T GetAs<T>() where T:class{return Component as T;} }
 public class IMyCubeBlock:VRage.ModAPI.IMyEntity {
  public Model Model {get;set;} public Grid CubeGrid; public Vector3I Position;
  public MyBlockOrientation Orientation=MyBlockOrientation.Identity;
  public IMySlimBlock SlimBlock;public bool IsFunctional=true,Closed; public Logic GameLogic=new Logic();
  public Definition BlockDefinition=new Definition();public MatrixD WorldMatrix {get{return CubeGrid.WorldMatrix;}}
  public Vector3D GetPosition(){return CubeGrid.GridIntegerToWorld(Position);}
 }
}
namespace Sandbox.Game.Entities {
 public class Attachment {public bool Compatible=true;public MyCubeBlock Block;}
 public class MyCubeBlock:IMyCubeBlock {public Dictionary<int,Attachment> CurrentAttachedUpgradeModules=new Dictionary<int,Attachment>();}
}
namespace ArcanePower {
 class ContainmentController {}
 class Reactor {
  internal MyCubeBlock Block;internal State Motion=new State();internal StatusReport Report=new StatusReport{State="TEST",Tone="white",Fuel="Aether"};
  internal StatusReport ReadAssemblyGuide(){return Report;}
 }
 class State {public object Thermal;public bool VentReady;}
 static class VentSession {internal static List<Reactor> All=new List<Reactor>();}
 static class ThermalConstruction {public static bool ShowReactorGuide(object state,object check){return false;}}
 static class ReactorDashboard {internal static Color Tone(string tone){return Color.White;}}
 public sealed partial class ThermalBuildGuide {
  bool active;Grid grid;object selected=new object();Check check=new Check();StringBuilder text=new StringBuilder();
  class Check {public string Next="CHECK";}
  struct Marker {public Vector3D At;public double Radius;public Vector4 Color;}
  List<Marker> markers=new List<Marker>();string summary;
  void Ring(Vector3D at,Vector3D up,Vector3D across,double radius,Vector4 color){
   Need(Math.Abs(up.Length()-1)<.0001 && Math.Abs(across.Length()-1)<.0001,"marker axes stay orthonormal");
   markers.Add(new Marker{At=at,Radius=radius,Color=color});
  }
  void Present(string value){summary=value;}
  static void Need(bool ok,string message){if(!ok)throw new Exception(message);}
  static MyCubeBlock Add(Grid grid,Vector3I cell,string subtype){
   var b=new MyCubeBlock{CubeGrid=grid,Position=cell,Model=new Model()};b.BlockDefinition.Id.SubtypeName=subtype;
   b.SlimBlock=new IMySlimBlock{FatBlock=b};grid.Blocks[cell]=b.SlimBlock;return b;
  }
  static bool Green(Marker m){return m.Color.Y>m.Color.X*2 && m.Color.Y>m.Color.Z*2;}
  static void Main(string[] args){
   var importer=new MyModelImporter();
   using(var reader=new BinaryReader(File.OpenRead(args[0])))
    typeof(MyModelImporter).GetMethod("LoadTagData",BindingFlags.Instance|BindingFlags.NonPublic)
     .Invoke(importer,new object[]{reader,new[]{"Dummies"}});
   var dummies=(Dictionary<string,MyModelDummy>)importer.GetTagData()["Dummies"];
   var axes=new[]{Vector3.UnitX,-Vector3.UnitX,Vector3.UnitY,-Vector3.UnitY,Vector3.UnitZ,-Vector3.UnitZ};
   int rotations=0;
   foreach(var forward in axes)foreach(var up in axes){
    if(Math.Abs(Vector3.Dot(forward,up))>.1)continue;
    var grid=new Grid{WorldMatrix=MatrixD.CreateWorld(new Vector3D(100,20,-50),forward,up)};
    var source=Add(grid,Vector3I.Zero,"ArcanePower_Thermal_ReactorHousing");
    foreach(var p in dummies)source.Model.Dummies.Add(p.Key,new Dummy{Matrix=p.Value.Matrix});
    Need(source.Model.Dummies.Count(p=>p.Key.StartsWith("detector_upgrade"))==2,"shipped model provides both controller sockets");
    var r=new Reactor{Block=source};VentSession.All.Clear();VentSession.All.Add(r);
    var guide=new ThermalBuildGuide{grid=grid};guide.ShowReactorAssembly(source.SlimBlock,r);guide.DrawAssemblyMarkers();
    Need(guide.active && guide.summary=="Reactor: TEST" && guide.text.ToString().Contains("ASSEMBLY GUIDE"),"standalone look-at guide remains available");
    Need(guide.markers.Count(m=>m.Radius==.60)==2 && guide.markers.Count(m=>m.Radius==.45)==2,"two controller targets and both side supply hatches use shipped dummies");
    Need(!guide.markers.Any(Green),"empty assembly cannot show a ready connection");
    var controller=Add(grid,new Vector3I(3,-1,0),"ArcanePower_ContainmentController");
    controller.GameLogic.Component=new ContainmentController();source.CurrentAttachedUpgradeModules.Add(0,new Attachment{Block=controller});
    guide.markers.Clear();guide.DrawAssemblyMarkers();
    Need(guide.markers.Count(m=>m.Radius==.60 && Green(m))==1,"one attached controller marks only its own socket ready");
    controller.SlimBlock.BuildLevelRatio=.9f;guide.markers.Clear();guide.DrawAssemblyMarkers();
    Need(!guide.markers.Any(Green),"unfinished controller cannot show ready");controller.SlimBlock.BuildLevelRatio=1;
    Need(AssemblyVessel(controller.SlimBlock)==source.SlimBlock,"aiming at attached controller resolves its own reactor");
    var duct=Add(grid,new Vector3I(0,2,0),"ArcanePower_VentDuct");
    guide.markers.Clear();guide.DrawAssemblyMarkers();var vent=guide.markers.Single(m=>m.Radius==1.05);
    Need(Vector3D.Distance(vent.At,grid.GridIntegerToWorld(new Vector3I(0,3,0))-grid.WorldMatrix.Up*1.21)<.0001,"vent marker advances to next duct/outlet connection on rotated grids");
    var outlet=Add(grid,new Vector3I(0,3,0),"ArcanePower_VentOutlet");r.Motion.VentReady=true;
    guide.markers.Clear();guide.DrawAssemblyMarkers();Need(Green(guide.markers.Single(m=>m.Radius==1.05)),"complete confirmed vent route is ready");
    outlet.Orientation=new MyBlockOrientation(Base6Directions.Direction.Forward,Base6Directions.Direction.Down);
    guide.markers.Clear();guide.DrawAssemblyMarkers();Need(!Green(guide.markers.Single(m=>m.Radius==1.05)),"misaligned outlet never shows ready even with a stale server snapshot");
    Need(AssemblyVessel(duct.SlimBlock)==source.SlimBlock,"aiming along vent route resolves source reactor");
    var unrelated=Add(grid,new Vector3I(0,6,0),"ArcanePower_VentOutlet");
    Need(AssemblyVessel(unrelated.SlimBlock)==unrelated.SlimBlock,"detached vents beyond a gap or terminal outlet cannot select the wrong reactor");
    grid.Physics=null;guide.markers.Clear();guide.DrawAssemblyMarkers();Need(!guide.markers.Any(Green),"projection highlights do not imply physical readiness");
    guide.ShowReactorAssembly(source.SlimBlock,r);Need(guide.text.ToString().Contains("Projection only"),"projection status is explicit");
    rotations++;
   }
   Need(rotations==24,"all grid orientations covered");
   foreach(var name in new[]{"ArcanePower_ContainmentController","ArcanePower_AdvancedContainmentController","ArcanePower_VentDuct","ArcanePower_VentOutlet"})
    Need(ReactorHardware(name),"hardware previews retain vessel guidance");
   Need(!ReactorHardware("UnrelatedBlock"),"unrelated previews retain their normal behavior");
   Console.WriteLine("PASS: native MWM sockets, per-controller readiness, vent progression, projections and hardware targeting across 24 grid orientations");
  }
 }
}
'''
with tempfile.TemporaryDirectory(prefix='arcane-reactor-guide-') as folder:
    target = Path(folder) / 'check.cs'
    target.write_text(fixture + 'namespace ArcanePower {\n' + types)
    exe = target.with_suffix('.exe')
    subprocess.run(['mcs', '-warn:0', '-langversion:6', '-out:' + str(exe),
                    '-r:/usr/lib/mono/4.5/Facades/netstandard.dll',
                    *['-r:' + str(GAME / (name + '.dll')) for name in ('VRage.Render', 'VRage.Math', 'VRage.Library')],
                    str(target), str(SRC / 'ThermalBuildGuide.Reactor.cs')], check=True)
    subprocess.run(['mono', str(exe), str(ROOT / 'src' / model.replace('\\', '/'))],
                   check=True, env={**os.environ, 'MONO_PATH': str(GAME)})
