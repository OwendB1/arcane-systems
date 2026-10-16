using System;
using System.Collections.Generic;
using ArcanePower;
using VRageMath;

namespace Sandbox.Common.ObjectBuilders { class MyObjectBuilder_UpgradeModule { } }
namespace VRage.ObjectBuilders { public class MyObjectBuilder_EntityBase { } }
namespace VRage.ModAPI { [Flags] public enum MyEntityUpdateEnum { NONE=0, BEFORE_NEXT_FRAME=1, EACH_FRAME=2 } }
namespace VRage.Game.Components {
 public class MyEntityComponentDescriptor:Attribute { public MyEntityComponentDescriptor(Type t,bool b,params string[] s){} }
 public class MyGameLogicComponent {
  public VRage.Game.Entity.MyEntity Entity;public VRage.ModAPI.MyEntityUpdateEnum NeedsUpdate;
  public virtual void Init(VRage.ObjectBuilders.MyObjectBuilder_EntityBase b){}
  public virtual void UpdateOnceBeforeFrame(){} public virtual void UpdateBeforeSimulation(){}
 }
}
namespace VRage.Game.ModAPI {
 public interface IMyCubeBlock { Orientation Orientation{get;} Grid CubeGrid{get;} Vector3I Position{get;} Logic GameLogic{get;} }
 public class Orientation { public Base6Directions.Direction Forward=Base6Directions.Direction.Forward; }
 public class Logic { public EnergyCore Value;public T GetAs<T>() where T:class{return Value as T;} }
 public class Slim {public IMyCubeBlock FatBlock;}
 public class Grid {public Slim Core;public Slim GetCubeBlock(Vector3I p){return p==new Vector3I(0,0,-2)?Core:null;} }
}
namespace VRage.Game.Entity {
 public class MyEntity {public Color EmissiveColor;public float EmissiveStrength;public Dictionary<string,MyEntitySubpart> Subparts=new Dictionary<string,MyEntitySubpart>();public Vector3D GetPosition(){return Vector3D.Zero;}public void SetEmissiveParts(string material,Color color,float strength){if(material!="EnergyStatus")throw new Exception(material);EmissiveColor=color;EmissiveStrength=strength;} }
 public class MyEntitySubpart {public Position PositionComp=new Position();}
 public class Position {public Matrix LocalMatrixRef;public void SetLocalMatrix(ref Matrix m){LocalMatrixRef=m;} }
}
namespace Sandbox.ModAPI {
 public class Session {public Camera Camera=new Camera();}
 public class Camera {public Vector3D Position;}
 public class Utilities {public bool IsDedicated;}
 public static class MyAPIGateway {public static Session Session;public static Utilities Utilities=new Utilities();}
}
namespace ArcanePower {public class EnergyCore {public bool Active;public Color VisualColor=new Color(40,185,255);public bool IsModuleRunning(VRage.Game.ModAPI.IMyCubeBlock b){return Active;} } }
class FanBlock:VRage.Game.Entity.MyEntity,VRage.Game.ModAPI.IMyCubeBlock {
 public VRage.Game.ModAPI.Orientation Orientation{get;set;}=new VRage.Game.ModAPI.Orientation();
 public VRage.Game.ModAPI.Grid CubeGrid{get;set;}=new VRage.Game.ModAPI.Grid();
 public Vector3I Position{get;set;}
 public VRage.Game.ModAPI.Logic GameLogic{get;set;}=new VRage.Game.ModAPI.Logic();
}
class EnergyFanProbe {
 static void Need(bool ok,string message){if(!ok)throw new Exception(message);}
 static void Same(Matrix a,Matrix b,string label){
  Need(Vector3.Distance(a.Right,b.Right)<.0001f && Vector3.Distance(a.Up,b.Up)<.0001f && Vector3.Distance(a.Backward,b.Backward)<.0001f,label+" axes");
  Need(a.Translation==b.Translation,label+" pivot");
 }
 static void Main(){
  var block=new FanBlock();var component=new EnergyModule{Entity=block};component.Init(null);component.UpdateOnceBeforeFrame();
  Need(component.NeedsUpdate==VRage.ModAPI.MyEntityUpdateEnum.BEFORE_NEXT_FRAME,"session retry");
  Sandbox.ModAPI.MyAPIGateway.Session=new Sandbox.ModAPI.Session();Sandbox.ModAPI.MyAPIGateway.Utilities.IsDedicated=true;component.UpdateOnceBeforeFrame();
  Need(component.NeedsUpdate==VRage.ModAPI.MyEntityUpdateEnum.NONE,"no dedicated visual work");
  Sandbox.ModAPI.MyAPIGateway.Utilities.IsDedicated=false;component.UpdateOnceBeforeFrame();
  var core=new EnergyCore{Active=true};var owner=new FanBlock();owner.GameLogic.Value=core;block.CubeGrid.Core=new VRage.Game.ModAPI.Slim{FatBlock=owner};
  Matrix rest=Matrix.CreateFromYawPitchRoll(.4f,.2f,-.3f);rest.Translation=new Vector3(0,2.3f,.61f);
  var part=new VRage.Game.Entity.MyEntitySubpart();part.PositionComp.LocalMatrixRef=rest;block.Subparts["EnergyFan1"]=part;
  float step=MathHelper.TwoPi*.75f/60f,phase=0;
  for(int i=0;i<170;i++){phase=(phase+step)%MathHelper.TwoPi;component.UpdateBeforeSimulation();Matrix expected=Matrix.CreateRotationZ(phase)*rest;expected.Translation=rest.Translation;Same(part.PositionComp.LocalMatrixRef,expected,"local shaft rotation across wrap");}
  Need(block.EmissiveColor==core.VisualColor && block.EmissiveStrength==.35f,"module follows bank status color");
  core.Active=false;Matrix stopped=part.PositionComp.LocalMatrixRef;for(int i=0;i<20;i++)component.UpdateBeforeSimulation();Same(part.PositionComp.LocalMatrixRef,stopped,"inactive phase freezes");
  Need(block.EmissiveStrength==0,"inactive module dark");
  block.Subparts.Clear();component.UpdateBeforeSimulation();
  var replacement=new VRage.Game.Entity.MyEntitySubpart();Matrix fresh=Matrix.CreateRotationY(.7f);fresh.Translation=new Vector3(0,-2.3f,.61f);replacement.PositionComp.LocalMatrixRef=fresh;block.Subparts["EnergyFan1"]=replacement;component.UpdateBeforeSimulation();
  Matrix repaired=Matrix.CreateRotationZ(phase)*fresh;repaired.Translation=fresh.Translation;Same(replacement.PositionComp.LocalMatrixRef,repaired,"model replacement captures new rest");
  Sandbox.ModAPI.MyAPIGateway.Session.Camera.Position=new Vector3D(1000,0,0);core.Active=true;component.UpdateBeforeSimulation();Same(replacement.PositionComp.LocalMatrixRef,repaired,"distant render gate");phase=(phase+step)%MathHelper.TwoPi;
  Sandbox.ModAPI.MyAPIGateway.Session.Camera.Position=Vector3D.Zero;component.UpdateBeforeSimulation();phase=(phase+step)%MathHelper.TwoPi;
  repaired=Matrix.CreateRotationZ(phase)*fresh;repaired.Translation=fresh.Translation;Same(replacement.PositionComp.LocalMatrixRef,repaired,"offscreen phase continues");
  block.Subparts.Clear();for(int i=0;i<10;i++)component.UpdateBeforeSimulation();Need(block.EmissiveStrength==.35f,"transfer module without fan lights");
  block.CubeGrid.Core=null;for(int i=0;i<10;i++)component.UpdateBeforeSimulation();Need(block.EmissiveStrength==0,"detached module dark");
  Console.WriteLine("PASS module visuals: local fan shaft, fixed pivots, wrapping, freeze, replacement, range gate, dedicated lifecycle, status color, transfer and detach");
 }
}
