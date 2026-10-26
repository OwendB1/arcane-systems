using System;
using Sandbox.Common.ObjectBuilders;
using Sandbox.Game.Entities;
using Sandbox.ModAPI;
using System.Collections.Generic;
using VRage;
using VRage.Game;
using VRage.Game.ModAPI.Ingame;

namespace ArcanePower
{
    public sealed partial class Reactor
    {
        private static readonly string[] Fuels = { "ArcaneFuelI", "ArcaneFuelII", "ArcaneFuelIII" };
        private static readonly string[] FuelNames = { "Aether", "Helion", "Empyrean" };
        private static readonly float[] PowerMW = { 1f, 10f, 100f };
        // Ideal full-load endurance; controller efficiency scales usable energy.
        private float FuelFullLoadMinutes { get { return Motion.FuelTier == 1 ? 2.5f : 10f; } }
        private const string ResiduumSubtype = "ArcaneAetherResiduum";
        private const long ResiduumScale = 1000000L;
        private const int ResiduumPerCanister = 10;
        private static readonly float[] ControllerEfficiencies = { .80f, .90f, .99f };
        private int FuelTierLimit
        {
            get { return ThermalVariant && (Motion.Thermal == null || Motion.Thermal.Mode != ThermalMode.Brayton
                || Motion.Thermal.Requested != ThermalMode.Brayton) ? 1 : controllerRingCapacity - 1; }
        }
        private float FuelEfficiency { get { return ControllerEfficiencies[Motion.RingCount - 2]; } }
        private MyReactor nativeReactor;
        private VRage.Game.Entity.MyInventoryBase fuelInventory;
        private readonly List<IMyTerminalBlock> fuelSources = new List<IMyTerminalBlock>();
        private readonly List<MyInventoryItem> transferItems = new List<MyInventoryItem>();

        private void InitializeFuel()
        {
            nativeReactor = (MyReactor)Entity;
            // SE creates the empty-slot tooltip once from native FuelInfos. Merely
            // adding IDs leaves that tooltip describing the original empty filter.
            var constraint = new Sandbox.Game.MyInventoryConstraint(
                "Accepts " + string.Join(", ", FuelNames) + " fuels and Standard, Reinforced or Advanced Containment Tiles.\n"
                + "Standalone uses Aether only. Helion and Empyrean require Brayton mode and compatible controllers. Aether recovers 10 Aether Residuum per consumed canister.");
            foreach (string fuel in Fuels)
                constraint.Add(new MyDefinitionId(typeof(MyObjectBuilder_Ingot), fuel));
            foreach (string tile in TileSubtypes)
                constraint.Add(new MyDefinitionId(typeof(MyObjectBuilder_Component), tile));
            constraint.Add(new MyDefinitionId(typeof(MyObjectBuilder_Component), ResiduumSubtype));
            nativeReactor.BlockDefinition.InventoryConstraint = constraint;
            var inventory = (Sandbox.Game.MyInventory)reactor.GetInventory();
            inventory.Constraint = constraint;
            inventory.MaxVolume = (MyFixedPoint)(2f * MyAPIGateway.Session.BlocksInventorySizeMultiplier);
            fuelInventory = inventory;
            fuelInventory.ContentsChanged += FuelChanged;
            reactor.PowerOutputMultiplier = ElectricalRatingMW / PowerMW[0];
            RefreshFuelCapacity();
        }

        private void FuelChanged(VRage.Game.Entity.MyInventoryBase inventory)
        {
            if (IsLive && MyAPIGateway.Multiplayer.IsServer) RefreshFuelCapacity();
        }

        private bool HasUsableFuel()
        {
            return IsLive && Motion.FuelTier <= FuelTierLimit && (!ThermalVariant || ThermalFuelModeReady)
                && (MyAPIGateway.Session.CreativeMode
                || reactor.GetInventory().GetItemAmount(MyItemType.MakeIngot(Fuels[Motion.FuelTier - 1])) > 0
                || (ThermalVariant && Motion.Thermal != null && Motion.Thermal.LoopVersion >= 2
                    && Motion.Thermal.Store.HotMJ > .001));
        }

        private void RefreshFuelCapacity()
        {
            if (!IsLive || nativeReactor == null) return;
            if (ThermalVariant) { RefreshThermalCapacity(); return; }
            // Native inventory callbacks otherwise treat the empty FuelInfos
            // list as unlimited capacity. Our callback runs after theirs.
            float units = MyAPIGateway.Session.CreativeMode ? 1f
                : (float)reactor.GetInventory().GetItemAmount(MyItemType.MakeIngot(Fuels[Motion.FuelTier - 1]));
            // Native capacity uses MW-seconds / 3600, including its per-frame
            // output cap. Canister endurance depends on the selected fuel;
            // controller efficiency determines the usable fraction.
            float rating = PowerMW[Motion.FuelTier - 1];
            bool generating = CanOperate && initializationFrames <= 2 && Motion.Core == CorePhase.Running && reactor.Enabled && !Motion.PowerPaused
                && (Motion.Vent == VentPhase.Idle || Motion.Vent == VentPhase.ShieldClosing);
            // Native source caps MW to Capacity * 3600 * 60. Keep the tier's
            // rated MaxOutput while the available electrical output ramps up.
            nativeReactor.Capacity = Motion.FuelTier + 1 <= controllerRingCapacity && generating
                ? System.Math.Min(units * FuelFullLoadMinutes * rating * FuelEfficiency / (Motion.TileStarved ? 6000f : 60f), rating * (Motion.TileStarved ? Math.Min(Motion.PowerRamp, Motion.StarvedLoad * .1f) : Motion.PowerRamp) / 216000f) : 0;
        }

        private double FuelUnitsPerMinute()
        {
            if (ThermalVariant && Motion.Thermal != null)
                return Motion.Thermal.ProducedMW / ThermalHeatMW / (FuelEfficiency * FuelFullLoadMinutes);
            bool failed = Motion.TileStarved && Motion.Core == CorePhase.Running && reactor.Enabled
                && !Motion.PowerPaused && (Motion.Vent == VentPhase.Idle || Motion.Vent == VentPhase.ShieldClosing);
            return (failed ? Motion.StarvedLoad * 10.0 : reactor.CurrentOutput / (double)PowerMW[Motion.FuelTier - 1]) / (FuelEfficiency * FuelFullLoadMinutes);
        }

        private void UpdateFuel()
        {
            if (!IsLive || nativeReactor == null) return;
            if (!MyAPIGateway.Multiplayer.IsServer)
            {
                float clientMultiplier = ElectricalRatingMW / PowerMW[0];
                if (reactor.PowerOutputMultiplier != clientMultiplier) reactor.PowerOutputMultiplier = clientMultiplier;
                return;
            }
            var inventory = reactor.GetInventory();
            // Keep the old tier until retained heat and its billable fuel debit
            // have cleared. A mode switch must not reprice already-produced heat.
            if (Motion.Core == CorePhase.Off && Motion.Vent == VentPhase.Idle && reactor.CurrentOutput <= 0
                && (!ThermalVariant || (ThermalCold && Motion.Thermal.FuelHeatMJ == 0
                    && Motion.FuelDebt < (double)MyFixedPoint.SmallestPossibleValue * .5)))
            {
                int selected = -1;
                for (int i = 0; i < Fuels.Length; i++)
                    if (i < FuelTierLimit && inventory.GetItemAmount(MyItemType.MakeIngot(Fuels[i])) > 0) selected = i;
                if (selected >= 0) Motion.FuelTier = selected + 1;
                else if (Motion.FuelTier > FuelTierLimit) Motion.FuelTier = FuelTierLimit;
            }
            float multiplier = ElectricalRatingMW / PowerMW[0];
            if (reactor.PowerOutputMultiplier != multiplier) reactor.PowerOutputMultiplier = multiplier;
            if (initializationFrames == 0 && (Motion.FuelTier > FuelTierLimit
                || (ThermalVariant && !ThermalFuelModeReady))) reactor.Enabled = false;

            bool starvedBurn = Motion.TileStarved && Motion.Core == CorePhase.Running && reactor.Enabled
                && !Motion.PowerPaused && (Motion.Vent == VentPhase.Idle || Motion.Vent == VentPhase.ShieldClosing);
            PayFuel(starvedBurn);
            RefreshFuelCapacity();
            RecoverResiduum();
            if (reactor.UseConveyorSystem && networkTick % 100 == 0)
            {
                fuelSources.Clear();
                var terminal = MyAPIGateway.TerminalActionsHelper.GetTerminalSystemForGrid(reactor.CubeGrid);
                if (terminal == null) return;
                terminal.GetBlocksOfType<IMyTerminalBlock>(fuelSources, b => b.HasInventory && b != reactor
                    && !(b is IMyReactor) && b.HasPlayerAccess(reactor.OwnerId));
                // Public inventory transfers check the real conveyor path and
                // item filters; no teleportation or private conveyor API calls.
                foreach (var block in fuelSources)
                {
                    for (int slot = 0; slot < block.InventoryCount; slot++)
                    {
                        var source = block.GetInventory(slot);
                        ExportResiduum(source);
                        PullTiles(source, inventory);
                        for (int i = 0; i < FuelTierLimit; i++)
                        {
                            MyItemType type = MyItemType.MakeIngot(Fuels[i]);
                            MyFixedPoint wanted = (MyFixedPoint)10 - inventory.GetItemAmount(type);
                            if (wanted <= 0 || !source.CanTransferItemTo(inventory, type)) continue;
                            transferItems.Clear();
                            source.GetItems(transferItems, item => item.Type == type);
                            foreach (var item in transferItems)
                            {
                                inventory.TransferItemFrom(source, item, MyFixedPoint.Min(wanted, item.Amount));
                                wanted = (MyFixedPoint)10 - inventory.GetItemAmount(type);
                                if (wanted <= 0) break;
                            }
                        }
                    }
                }
            }
        }


        private void PayFuel(bool starvedBurn)
        {
            var inventory = reactor.GetInventory();
            // Flush reservations before exposing native output. The signed
            // remainder preserves fixed-point rounding credit at tiny loads.
            if (ThermalVariant && Motion.Thermal != null)
            {
                if (!MyAPIGateway.Session.CreativeMode)
                    Motion.FuelDebt += Motion.Thermal.FuelHeatMJ / (ThermalHeatMW * FuelFullLoadMinutes * 60 * FuelEfficiency);
                Motion.Thermal.FuelHeatMJ = 0;
            }
            if (!MyAPIGateway.Session.CreativeMode && (reactor.CurrentOutput > 0 || starvedBurn || (ThermalVariant && Motion.FuelDebt > 0)))
            {
                if (!ThermalVariant) Motion.FuelDebt += FuelUnitsPerMinute() / 3600;
                else if (starvedBurn) Motion.FuelDebt += Motion.StarvedLoad * 10.0 / (FuelEfficiency * FuelFullLoadMinutes * 3600);
                MyFixedPoint amount = (MyFixedPoint)Motion.FuelDebt;
                if (amount > 0)
                {
                    string fuel = Fuels[Motion.FuelTier - 1];
                    amount = MyFixedPoint.Min(amount, inventory.GetItemAmount(MyItemType.MakeIngot(fuel)));
                    if (amount > 0)
                    {
                        inventory.RemoveItemsOfType(amount, new MyObjectBuilder_Ingot { SubtypeName = fuel });
                        Motion.FuelDebt -= (double)amount;
                        // Integer carry makes many tiny burns identical to a canister.
                        if (ThermalVariant && Motion.FuelTier == 1)
                            Motion.ResiduumMicroUnits += (long)Math.Round((double)amount * ResiduumScale) * ResiduumPerCanister;
                    }
                    else Motion.FuelDebt = 0;
                }
            }
        }

        private void RecoverResiduum()
        {
            if (!IsLive || !MyAPIGateway.Multiplayer.IsServer) return;
            var inventory = reactor.GetInventory();
            var id = new MyDefinitionId(typeof(MyObjectBuilder_Component), ResiduumSubtype);
            var type = MyItemType.MakeComponent(ResiduumSubtype);
            // Full inventory retains saved credit. Bounded batches release a
            // backlog when space becomes available, without stalling simulation.
            for (int i = 0; i < 10 && Motion.ResiduumMicroUnits >= ResiduumScale; i++)
            {
                if (!inventory.CanItemsBeAdded((MyFixedPoint)1, id)) return;
                MyFixedPoint before = inventory.GetItemAmount(type);
                inventory.AddItems((MyFixedPoint)1, new MyObjectBuilder_Component { SubtypeName = ResiduumSubtype });
                long added = (long)Math.Round((double)(inventory.GetItemAmount(type) - before) * ResiduumScale);
                if (added <= 0) return;
                Motion.ResiduumMicroUnits -= Math.Min(Motion.ResiduumMicroUnits, added);
            }
        }

        private void ExportResiduum(VRage.Game.ModAPI.IMyInventory target)
        {
            var inventory = reactor.GetInventory();
            var type = MyItemType.MakeComponent(ResiduumSubtype);
            if (!inventory.CanTransferItemTo(target, type)) return;
            transferItems.Clear();
            inventory.GetItems(transferItems, item => item.Type == type);
            foreach (var item in transferItems) target.TransferItemFrom(inventory, item);
        }
    }
}
