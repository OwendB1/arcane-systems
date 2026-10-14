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
        private static readonly string[] TileSubtypes = {
            "ArcaneContainmentTile", "ArcaneReinforcedContainmentTile", "ArcaneAdvancedContainmentTile"
        };
        private static readonly string[] TileNames = { "Standard", "Reinforced", "Advanced" };
        private static readonly float[] TileLifetimes = { 1, 10, 100 };
        private static readonly MyItemType[] TileTypes = {
            MyItemType.MakeComponent(TileSubtypes[0]), MyItemType.MakeComponent(TileSubtypes[1]),
            MyItemType.MakeComponent(TileSubtypes[2])
        };

        private static bool ValidTileGrades(int[] grades)
        {
            if (grades == null || grades.Length != 20) return false;
            foreach (int grade in grades) if (grade < 0 || grade >= TileTypes.Length) return false;
            return true;
        }

        private int InstalledTileGrade(int batch)
        {
            return Motion.TileGrades[batch];
        }

        private int[] SpareTileQuartets()
        {
            var inventory = reactor.GetInventory();
            var stock = new int[TileTypes.Length];
            for (int grade = 0; grade < stock.Length; grade++)
                stock[grade] = (int)((double)inventory.GetItemAmount(TileTypes[grade]) / 4);
            return stock;
        }

        private static int BestTileGrade(int[] stock)
        {
            for (int grade = stock.Length - 1; grade >= 0; grade--)
                if (stock[grade] > 0) return grade;
            return -1;
        }

        private int NeededTileQuartets()
        {
            return (80 - Motion.InstalledTiles + 3) / 4
                + (Motion.InstalledTiles > 0 && Motion.TileWear >= 1 ? 1 : 0);
        }

        private void DiscardTiles()
        {
            Motion.InstalledTiles = 0;
            Array.Clear(Motion.TileGrades, 0, Motion.TileGrades.Length);
            Motion.TileWear = 0;
            Motion.TileStarved = false;
            Motion.StarvedLoad = 0;
            Motion.MaintenanceTick = -1;
        }

        private void ConsumeTileQuartets(int[] counts)
        {
            if (MyAPIGateway.Session.CreativeMode) return;
            for (int grade = 0; grade < counts.Length; grade++)
                if (counts[grade] > 0)
                    reactor.GetInventory().RemoveItemsOfType((MyFixedPoint)(counts[grade] * 4),
                        new MyObjectBuilder_Component { SubtypeName = TileSubtypes[grade] });
        }

        private bool PrepareTiles()
        {
            bool creative = MyAPIGateway.Session.CreativeMode;
            int[] stock = creative ? new[] { 20, 0, 0 } : SpareTileQuartets();
            int[] grades = (int[])Motion.TileGrades.Clone();
            int[] consumed = new int[TileTypes.Length];
            int missing = (80 - Motion.InstalledTiles + 3) / 4;
            int needed = NeededTileQuartets();
            // Plan the complete reservation before removing anything. Each quartet
            // shares one grade; different quartets may use different grades.
            for (int i = 0; i < needed; i++)
            {
                int grade = BestTileGrade(stock);
                if (grade < 0) { Motion.TileStarved = true; return false; }
                stock[grade]--;
                consumed[grade]++;
                int batch = i < missing ? 20 - missing + i : Motion.MaintenanceBatch;
                grades[batch] = grade;
            }
            ConsumeTileQuartets(consumed);
            Motion.TileGrades = grades;
            Motion.InstalledTiles = 80;
            if (Motion.TileWear >= 1) Motion.TileWear = 0;
            Motion.TileStarved = false;
            Motion.StarvedLoad = 0;
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
            if (Motion.InstalledTiles == 80 && Motion.TileWear >= 1 && Motion.MaintenanceTick < 0
                && Motion.Vent == VentPhase.Idle)
            {
                int grade = MyAPIGateway.Session.CreativeMode ? 0 : BestTileGrade(SpareTileQuartets());
                if (grade >= 0)
                {
                    var consumed = new int[TileTypes.Length];
                    consumed[grade] = 1;
                    ConsumeTileQuartets(consumed);
                    Motion.TileGrades[Motion.MaintenanceBatch] = grade;
                    Motion.TileWear = 0;
                    Motion.TileStarved = false;
                    Motion.StarvedLoad = 0;
                    Motion.MaintenanceTick = 0;
                    RefreshFuelCapacity();
                    PublishMotion();
                }
            }
            if (Motion.Core != CorePhase.Running || !reactor.Enabled || !reactor.IsFunctional || Motion.PowerPaused
                || (Motion.Vent != VentPhase.Idle && Motion.Vent != VentPhase.ShieldClosing)
                || MyAPIGateway.Session.CreativeMode || Motion.TileStarved || Motion.MaintenanceTick >= 0) return;
            Motion.TileWear = Math.Min(1, Motion.TileWear + TileWearRate() / 3600f);
            if (Motion.TileWear < 1) return;
            // Latch the operating load before failed maintenance lowers output.
            if (BestTileGrade(SpareTileQuartets()) < 0)
            {
                Motion.StarvedLoad = MathHelper.Clamp(reactor.CurrentOutput / PowerMW[Motion.FuelTier - 1], 0, 1);
                Motion.TileStarved = true;
                RefreshFuelCapacity();
                PublishMotion();
            }
        }

        private float BaseTileWearRate()
        {
            // Quartets/minute: quadratic thermal wear is 4x at 100% heat.
            return (1 << (Motion.FuelTier - 1)) * (.2f + .8f * Motion.Load) * (1 + 3 * Motion.Heat * Motion.Heat);
        }

        private float TileWearRate()
        {
            return BaseTileWearRate() / TileLifetimes[InstalledTileGrade(Motion.MaintenanceBatch)];
        }

        private double TileReserveSeconds()
        {
            // Installed quartets are serviced in order. Forecast until loose stock
            // is exhausted, using each installed and replacement quartet's grade.
            int[] stock = SpareTileQuartets();
            int[] grades = (int[])Motion.TileGrades.Clone();
            int batch = Motion.MaintenanceTick >= 0 ? (Motion.MaintenanceBatch + 1) % 20 : Motion.MaintenanceBatch;
            double life = (Motion.MaintenanceTick >= 0 ? 1 : 1 - Motion.TileWear) * TileLifetimes[grades[batch]];
            for (int grade = BestTileGrade(stock); grade >= 0; grade = BestTileGrade(stock))
            {
                stock[grade]--;
                grades[batch] = grade;
                batch = (batch + 1) % 20;
                life += TileLifetimes[grades[batch]];
            }
            return life / BaseTileWearRate() * 60;
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
            // Keep one shell reserve of each supplied grade (480 L total). A full Standard
            // reserve must not prevent conveyor delivery of better tiles.
            for (int grade = TileTypes.Length - 1; grade >= 0; grade--)
            {
                MyItemType type = TileTypes[grade];
                MyFixedPoint wanted = (MyFixedPoint)80 - inventory.GetItemAmount(type);
                if (wanted <= 0 || !source.CanTransferItemTo(inventory, type)) continue;
                transferItems.Clear();
                source.GetItems(transferItems, item => item.Type == type);
                foreach (var item in transferItems)
                {
                    inventory.TransferItemFrom(source, item, MyFixedPoint.Min(wanted, item.Amount));
                    wanted = (MyFixedPoint)80 - inventory.GetItemAmount(type);
                    if (wanted <= 0) break;
                }
            }
        }
    }
}
