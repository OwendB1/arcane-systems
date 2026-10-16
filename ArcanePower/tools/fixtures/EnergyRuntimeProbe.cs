using System;using System.Collections.Generic;using Sandbox.ModAPI;using VRage.Game.Components;using VRage.Utils;using VRage.Game.ModAPI;using VRageMath;
[MySessionComponentDescriptor(MyUpdateOrder.BeforeSimulation)]
public class EnergyValidation:MySessionComponentBase {
 int tick;IMyCubeGrid grid;bool finished;
 public override void UpdateBeforeSimulation(){
  if(finished || MyAPIGateway.Session==null || !MyAPIGateway.Multiplayer.IsServer)return;
  tick++;
  if(tick%120!=0)return;
  VRage.ModAPI.IMyEntity entity;
  if(grid==null && MyAPIGateway.Entities.TryGetEntityById(880000000000100,out entity))grid=entity as IMyCubeGrid;
  if(grid==null){MyLog.Default.WriteLineAndConsole("ENERGY_VALIDATION missing rig");return;}
  var blocks=new List<IMySlimBlock>();grid.GetBlocks(blocks);
  if(tick==240 || tick==480)foreach(var slim in blocks){
   var f=slim.FatBlock as IMyFunctionalBlock;
   if(f!=null && f.Position.Z<=5 && f.BlockDefinition.SubtypeName.StartsWith("ArcanePower_EnergyStabilizer"))f.Enabled=tick==480;
  }
  foreach(var slim in blocks){
   var upgrade=slim.FatBlock as IMyUpgradeModule;
   if(upgrade!=null && upgrade.Position.Z<=5)
    MyLog.Default.WriteLineAndConsole("ENERGY_VALIDATION native_socket tick="+tick+" subtype="+upgrade.BlockDefinition.SubtypeName+" connections="+upgrade.Connections);
   if(upgrade!=null && upgrade.BlockDefinition.SubtypeName.Contains("EnergyStabilizer")){
    var model=(VRage.Game.Entity.MyEntity)upgrade;
    for(int i=1;i<=3;i++){
     VRage.Game.Entity.MyEntitySubpart fan;
     if(model.Subparts.TryGetValue("EnergyFan"+i,out fan))
      MyLog.Default.WriteLineAndConsole("ENERGY_VALIDATION fan tick="+tick+" index="+i+" entity="+fan.EntityId+" pivot="+fan.PositionComp.LocalMatrixRef.Translation+" right="+fan.PositionComp.LocalMatrixRef.Right+" up="+fan.PositionComp.LocalMatrixRef.Up);
    }
   }
   var b=slim.FatBlock as IMyBatteryBlock;if(b==null)continue;
   if(b.Position.Z>5)continue;
   if(b.EntityId==880000000001217){
    var model=(VRage.Game.Entity.MyEntity)b;
    for(int i=1;i<=2;i++){
     VRage.Game.Entity.MyEntitySubpart ring;
     if(model.Subparts.TryGetValue("EnergyRing"+i,out ring))
      MyLog.Default.WriteLineAndConsole("ENERGY_VALIDATION ring tick="+tick+" index="+i+" right="+ring.PositionComp.LocalMatrixRef.Right+" up="+ring.PositionComp.LocalMatrixRef.Up);
    }
   }
   b.RefreshCustomInfo();
   MyLog.Default.WriteLineAndConsole("ENERGY_VALIDATION tick="+tick+" id="+b.EntityId+" subtype="+b.BlockDefinition.SubtypeName+" position="+b.Position+" stored="+b.CurrentStoredPower+" capacity="+b.MaxStoredPower+" input="+b.CurrentInput+" output="+b.CurrentOutput+" maxinput="+b.MaxInput+" maxoutput="+b.MaxOutput+" mode="+b.ChargeMode+" info="+b.CustomInfo.Replace("\n"," | "));
  }
  if(tick>=720){MyLog.Default.WriteLineAndConsole("ENERGY_VALIDATION complete");finished=true;}
 }
}
