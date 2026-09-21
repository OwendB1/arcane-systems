using Sandbox.Common.ObjectBuilders;
using Sandbox.ModAPI;
using VRage;
using VRage.Game;
using VRage.Game.ModAPI;
using VRage.Game.ModAPI.Ingame;
using System;
using System.Text;
using VRageMath;

namespace ArcanePower
{
    public sealed partial class Reactor
    {
        private static readonly MyItemType TileType = MyItemType.MakeComponent("ArcaneContainmentTile");

        private bool PrepareTiles()
        {
            int needed = 80 - Motion.InstalledTiles + (Motion.TileWear >= 1 ? 4 : 0);
            var inventory = reactor.GetInventory();
            if (!MyAPIGateway.Session.CreativeMode && inventory.GetItemAmount(TileType) < needed)
            {
                Motion.TileStarved = true;
                return false;
            }
            if (!MyAPIGateway.Session.CreativeMode && needed > 0)
                inventory.RemoveItemsOfType((MyFixedPoint)needed, new MyObjectBuilder_Component { SubtypeName = "ArcaneContainmentTile" });
            Motion.InstalledTiles = 80;
            if (Motion.TileWear >= 1) Motion.TileWear = 0;
            Motion.TileStarved = false;
            SaveMotion();
            return true;
        }

        private void UpdateTiles()
        {
            if (!MyAPIGateway.Multiplayer.IsServer) return;
            if (Motion.Vent == VentPhase.Idle && (Motion.Core == CorePhase.Starting || Motion.Core == CorePhase.Running)
                && Motion.InstalledTiles < 80 && !PrepareTiles())
            {
                reactor.Enabled = false;
                BeginShutdown();
                return;
            }
            // A failed maintenance quartet can be replaced during cooling too.
            if (Motion.TileWear >= 1 && Motion.MaintenanceTick < 0 && Motion.Vent == VentPhase.Idle
                && (MyAPIGateway.Session.CreativeMode || reactor.GetInventory().GetItemAmount(TileType) >= 4))
            {
                if (!MyAPIGateway.Session.CreativeMode)
                    reactor.GetInventory().RemoveItemsOfType((MyFixedPoint)4,
                        new MyObjectBuilder_Component { SubtypeName = "ArcaneContainmentTile" });
                Motion.TileWear = 0;
                Motion.TileStarved = false;
                Motion.StarvedLoad = 0;
                Motion.MaintenanceTick = 0;
                RefreshFuelCapacity();
                PublishMotion();
            }
            if (Motion.Core != CorePhase.Running || !reactor.Enabled || !reactor.IsFunctional || Motion.PowerPaused
                || (Motion.Vent != VentPhase.Idle && Motion.Vent != VentPhase.ShieldClosing)
                || MyAPIGateway.Session.CreativeMode || Motion.TileStarved) return;
            Motion.TileWear = Math.Min(1, Motion.TileWear + TileWearRate() / 3600f);
            if (Motion.TileWear < 1 || Motion.MaintenanceTick >= 0) return;
            // The last quartet has worn out. Latch its operating load before
            // lowering electrical output, otherwise the failure would save fuel.
            if (reactor.GetInventory().GetItemAmount(TileType) < 4)
            {
                Motion.StarvedLoad = MathHelper.Clamp(reactor.CurrentOutput / PowerMW[Motion.Profile - 2], 0, 1);
                Motion.TileStarved = true;
                RefreshFuelCapacity();
                PublishMotion();
            }
        }

        private float TileWearRate()
        {
            // Quartets/minute: quadratic thermal wear is 4x at 100% heat.
            return (1 << (Motion.Profile - 2)) * (.2f + .8f * Motion.Load) * (1 + 3 * Motion.Heat * Motion.Heat);
        }

        private Matrix MaintenancePose(TilePose tile, Matrix installed)
        {
            float tick = Motion.MaintenanceTick;
            if (tick < 18)
            {
                Vector3 position = installed.Translation;
                installed.Translation = Vector3.Zero;
                installed *= Matrix.CreateScale(Math.Max(.001f, 1 - Span(tick, 0, 18)));
                installed.Translation = position;
                return installed;
            }
            // Launch from the fixed pillar dispenser, then join the moving shell.
            // Do not apply the field's rotation to the dispenser or launch path.
            Matrix start = Rest(tile.Name);
            Matrix pose = Matrix.CreateFromQuaternion(Quaternion.Slerp(
                Quaternion.CreateFromRotationMatrix(start), Quaternion.CreateFromRotationMatrix(installed), Span(tick, 30, 90)));
            pose *= Matrix.CreateScale(Math.Max(.001f, Span(tick, 18, 24)));
            if (tick < 30) pose.Translation = Vector3.Lerp(start.Translation, tile.Exit, Span(tick, 24, 30));
            else if (tick < 54) pose.Translation = Vector3.Lerp(tile.Exit, tile.Staging, Span(tick, 30, 54));
            else pose.Translation = Vector3.Lerp(tile.Staging, installed.Translation, Span(tick, 54, 90));
            return pose;
        }

        private void PullTiles(VRage.Game.ModAPI.IMyInventory source, VRage.Game.ModAPI.IMyInventory inventory)
        {
            MyFixedPoint wanted = (MyFixedPoint)160 - inventory.GetItemAmount(TileType);
            if (wanted <= 0 || !source.CanTransferItemTo(inventory, TileType)) return;
            transferItems.Clear();
            source.GetItems(transferItems, item => item.Type == TileType);
            foreach (var item in transferItems)
            {
                inventory.TransferItemFrom(source, item, MyFixedPoint.Min(wanted, item.Amount));
                wanted = (MyFixedPoint)160 - inventory.GetItemAmount(TileType);
                if (wanted <= 0) break;
            }
        }
    }
}
