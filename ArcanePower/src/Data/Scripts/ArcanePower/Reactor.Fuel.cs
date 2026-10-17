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
        private static readonly float[] PowerMW = { 10000f, 100000f, 1000000f };
        private const float FuelUnitsPerCanister = 10f;
        private static readonly float[] ControllerEfficiencies = { .80f, .90f, .99f };
        private float FuelEfficiency { get { return ControllerEfficiencies[Motion.RingCount - 2]; } }
        private MyReactor nativeReactor;
        private readonly List<IMyTerminalBlock> fuelSources = new List<IMyTerminalBlock>();
        private readonly List<MyInventoryItem> transferItems = new List<MyInventoryItem>();

        private void InitializeFuel()
        {
            nativeReactor = (MyReactor)Entity;
            // SE creates the empty-slot tooltip once from native FuelInfos. Merely
            // adding IDs leaves that tooltip describing the original empty filter.
            var constraint = new Sandbox.Game.MyInventoryConstraint(
                "Accepts " + string.Join(", ", FuelNames) + " fuels and Standard, Reinforced or Advanced Containment Tiles.\n"
                + "Refine ore before loading. Fuel use depends on attached containment controllers.");
            foreach (string fuel in Fuels)
                constraint.Add(new MyDefinitionId(typeof(MyObjectBuilder_Ingot), fuel));
            foreach (string tile in TileSubtypes)
                constraint.Add(new MyDefinitionId(typeof(MyObjectBuilder_Component), tile));
            nativeReactor.BlockDefinition.InventoryConstraint = constraint;
            var inventory = (Sandbox.Game.MyInventory)reactor.GetInventory();
            inventory.Constraint = constraint;
            inventory.MaxVolume = (MyFixedPoint)(2f * MyAPIGateway.Session.BlocksInventorySizeMultiplier);
            ((VRage.Game.Entity.MyInventoryBase)reactor.GetInventory()).ContentsChanged += FuelChanged;
            reactor.PowerOutputMultiplier = ElectricalRatingMW / PowerMW[0];
            RefreshFuelCapacity();
        }

        private void FuelChanged(VRage.Game.Entity.MyInventoryBase inventory)
        {
            if (MyAPIGateway.Multiplayer.IsServer) RefreshFuelCapacity();
        }

        private bool HasUsableFuel()
        {
            return Motion.FuelTier + 1 <= controllerRingCapacity && (MyAPIGateway.Session.CreativeMode
                || reactor.GetInventory().GetItemAmount(MyItemType.MakeIngot(Fuels[Motion.FuelTier - 1])) > 0);
        }

        private void RefreshFuelCapacity()
        {
            if (nativeReactor == null) return;
            if (ThermalVariant) { RefreshThermalCapacity(); return; }
            // Native inventory callbacks otherwise treat the empty FuelInfos
            // list as unlimited capacity. Our callback runs after theirs.
            float units = MyAPIGateway.Session.CreativeMode ? 1f
                : (float)reactor.GetInventory().GetItemAmount(MyItemType.MakeIngot(Fuels[Motion.FuelTier - 1]));
            // Native capacity uses MW-seconds / 3600, including its per-frame
            // output cap. Each canister stores 10 minutes at its ideal rating;
            // controller efficiency determines the usable fraction.
            float rating = PowerMW[Motion.FuelTier - 1];
            bool generating = CanOperate && initializationFrames <= 2 && Motion.Core == CorePhase.Running && reactor.Enabled && !Motion.PowerPaused
                && (Motion.Vent == VentPhase.Idle || Motion.Vent == VentPhase.ShieldClosing);
            // Native source caps MW to Capacity * 3600 * 60. Keep the tier's
            // rated MaxOutput while the available electrical output ramps up.
            nativeReactor.Capacity = Motion.FuelTier + 1 <= controllerRingCapacity && generating
                ? System.Math.Min(units * FuelUnitsPerCanister * rating * FuelEfficiency / (Motion.TileStarved ? 6000f : 60f), rating * (Motion.TileStarved ? Math.Min(Motion.PowerRamp, Motion.StarvedLoad * .1f) : Motion.PowerRamp) / 216000f) : 0;
        }

        private double FuelUnitsPerMinute()
        {
            if (ThermalVariant && Motion.Thermal != null)
                return Motion.Thermal.ProducedMW / ThermalHeatMW / (FuelEfficiency * FuelUnitsPerCanister);
            bool failed = Motion.TileStarved && Motion.Core == CorePhase.Running && reactor.Enabled
                && !Motion.PowerPaused && (Motion.Vent == VentPhase.Idle || Motion.Vent == VentPhase.ShieldClosing);
            return (failed ? Motion.StarvedLoad * 10.0 : reactor.CurrentOutput / (double)PowerMW[Motion.FuelTier - 1]) / (FuelEfficiency * FuelUnitsPerCanister);
        }

        private void UpdateFuel()
        {
            if (nativeReactor == null) return;
            if (!MyAPIGateway.Multiplayer.IsServer)
            {
                float clientMultiplier = ElectricalRatingMW / PowerMW[0];
                if (reactor.PowerOutputMultiplier != clientMultiplier) reactor.PowerOutputMultiplier = clientMultiplier;
                return;
            }
            var inventory = reactor.GetInventory();
            if (Motion.Core == CorePhase.Off && Motion.Vent == VentPhase.Idle && reactor.CurrentOutput <= 0 && (!ThermalVariant || ThermalCold))
            {
                int selected = -1;
                for (int i = 0; i < Fuels.Length; i++)
                    if (i + 2 <= controllerRingCapacity && inventory.GetItemAmount(MyItemType.MakeIngot(Fuels[i])) > 0) selected = i;
                if (selected >= 0) Motion.FuelTier = selected + 1;
                else if (Motion.FuelTier + 1 > controllerRingCapacity) Motion.FuelTier = controllerRingCapacity - 1;
            }
            float multiplier = ElectricalRatingMW / PowerMW[0];
            if (reactor.PowerOutputMultiplier != multiplier) reactor.PowerOutputMultiplier = multiplier;
            if (initializationFrames == 0 && Motion.FuelTier + 1 > controllerRingCapacity) reactor.Enabled = false;

            // Ideal burn is one canister/10 minutes at full rated load, divided by
            // controller efficiency. The saved signed remainder retains debt or
            // rounding credit, avoiding fixed-point rounding loss at low demand.
            bool starvedBurn = Motion.TileStarved && Motion.Core == CorePhase.Running && reactor.Enabled
                && !Motion.PowerPaused && (Motion.Vent == VentPhase.Idle || Motion.Vent == VentPhase.ShieldClosing);
            if (ThermalVariant && Motion.Thermal != null)
            {
                if (!MyAPIGateway.Session.CreativeMode)
                    Motion.FuelDebt += Motion.Thermal.FuelHeatMJ / (ThermalHeatMW * 600 * FuelEfficiency);
                Motion.Thermal.FuelHeatMJ = 0;
            }
            if (!MyAPIGateway.Session.CreativeMode && (reactor.CurrentOutput > 0 || starvedBurn || (ThermalVariant && Motion.FuelDebt > 0)))
            {
                if (!ThermalVariant) Motion.FuelDebt += FuelUnitsPerMinute() / 3600;
                else if (starvedBurn) Motion.FuelDebt += Motion.StarvedLoad * 10.0 / (FuelEfficiency * FuelUnitsPerCanister * 3600);
                MyFixedPoint amount = (MyFixedPoint)Motion.FuelDebt;
                if (amount > 0)
                {
                    string fuel = Fuels[Motion.FuelTier - 1];
                    amount = MyFixedPoint.Min(amount, inventory.GetItemAmount(MyItemType.MakeIngot(fuel)));
                    if (amount > 0)
                    {
                        inventory.RemoveItemsOfType(amount, new MyObjectBuilder_Ingot { SubtypeName = fuel });
                        Motion.FuelDebt -= (double)amount;
                    }
                    else Motion.FuelDebt = 0;
                }
            }
            RefreshFuelCapacity();
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
                        PullTiles(source, inventory);
                        for (int i = 0; i <= controllerRingCapacity - 2; i++)
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


    }
}
