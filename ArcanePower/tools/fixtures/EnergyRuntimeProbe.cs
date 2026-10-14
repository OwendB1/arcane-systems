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
  if(tick==240 || tick==480){var s=grid.GetCubeBlock(new Vector3I(0,4,0));var f=s==null?null:s.FatBlock as IMyFunctionalBlock;if(f!=null)f.Enabled=tick==480;}
  var blocks=new List<IMySlimBlock>();grid.GetBlocks(blocks);
  foreach(var slim in blocks){var b=slim.FatBlock as IMyBatteryBlock;if(b==null)continue;
   if(b.Position.Z>5)continue;
   b.RefreshCustomInfo();
   MyLog.Default.WriteLineAndConsole("ENERGY_VALIDATION tick="+tick+" id="+b.EntityId+" subtype="+b.BlockDefinition.SubtypeName+" position="+b.Position+" stored="+b.CurrentStoredPower+" capacity="+b.MaxStoredPower+" input="+b.CurrentInput+" output="+b.CurrentOutput+" maxinput="+b.MaxInput+" maxoutput="+b.MaxOutput+" mode="+b.ChargeMode+" info="+b.CustomInfo.Replace("\n"," | "));
  }
  if(tick>=720){MyLog.Default.WriteLineAndConsole("ENERGY_VALIDATION complete");finished=true;}
 }
}