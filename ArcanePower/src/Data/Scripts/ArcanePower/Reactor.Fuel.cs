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
        private static readonly float[] PowerMW = { 10000f, 100000f, 1000000f };
        private MyReactor nativeReactor;
        private readonly List<IMyTerminalBlock> fuelSources = new List<IMyTerminalBlock>();
        private readonly List<MyInventoryItem> transferItems = new List<MyInventoryItem>();

        private void InitializeFuel()
        {
            nativeReactor = (MyReactor)Entity;
            // SE creates the empty-slot tooltip once from native FuelInfos. Merely
            // adding IDs leaves that tooltip describing the original empty filter.
            var constraint = new Sandbox.Game.MyInventoryConstraint(
                "Accepts Arcane Fuel I, Arcane Fuel II, Arcane Fuel III and Arcane Containment Tiles.\n"
                + "Refine ore before loading. Fuel use depends on attached containment controllers.");
            foreach (string fuel in Fuels)
                constraint.Add(new MyDefinitionId(typeof(MyObjectBuilder_Ingot), fuel));
            constraint.Add(new MyDefinitionId(typeof(MyObjectBuilder_Component), "ArcaneContainmentTile"));
            nativeReactor.BlockDefinition.InventoryConstraint = constraint;
            ((Sandbox.Game.MyInventory)reactor.GetInventory()).Constraint = constraint;
            ((VRage.Game.Entity.MyInventoryBase)reactor.GetInventory()).ContentsChanged += FuelChanged;
            reactor.PowerOutputMultiplier = PowerMW[Motion.Profile - 2] / PowerMW[0];
            RefreshFuelCapacity();
        }

        private void FuelChanged(VRage.Game.Entity.MyInventoryBase inventory)
        {
            if (MyAPIGateway.Multiplayer.IsServer) RefreshFuelCapacity();
        }

        private bool HasUsableFuel()
        {
            return Motion.Profile <= rings && (MyAPIGateway.Session.CreativeMode
                || reactor.GetInventory().GetItemAmount(MyItemType.MakeIngot(Fuels[Motion.Profile - 2])) > 0);
        }

        private void RefreshFuelCapacity()
        {
            if (nativeReactor == null) return;
            // Native inventory callbacks otherwise treat the empty FuelInfos
            // list as unlimited capacity. Our callback runs after theirs.
            float units = MyAPIGateway.Session.CreativeMode ? 1f
                : (float)reactor.GetInventory().GetItemAmount(MyItemType.MakeIngot(Fuels[Motion.Profile - 2]));
            // Native capacity uses MW-seconds / 3600, including its per-frame
            // output cap. One selected fuel unit stores sixty seconds of output.
            float rating = PowerMW[Motion.Profile - 2];
            bool generating = initializationFrames <= 2 && Motion.Core == CorePhase.Running && reactor.Enabled && !Motion.PowerPaused
                && (Motion.Vent == VentPhase.Idle || Motion.Vent == VentPhase.ShieldClosing);
            // Native source caps MW to Capacity * 3600 * 60. Keep the tier's
            // rated MaxOutput while the available electrical output ramps up.
            nativeReactor.Capacity = Motion.Profile <= rings && generating
                ? System.Math.Min(units * rating / (Motion.TileStarved ? 6000f : 60f), rating * (Motion.TileStarved ? Math.Min(Motion.PowerRamp, Motion.StarvedLoad * .1f) : Motion.PowerRamp) / 216000f) : 0;
        }

        private double FuelUnitsPerMinute()
        {
            bool failed = Motion.TileStarved && Motion.Core == CorePhase.Running && reactor.Enabled
                && !Motion.PowerPaused && (Motion.Vent == VentPhase.Idle || Motion.Vent == VentPhase.ShieldClosing);
            return failed ? Motion.StarvedLoad * 10.0 : reactor.CurrentOutput / (double)PowerMW[Motion.Profile - 2];
        }

        private void UpdateFuel()
        {
            if (nativeReactor == null) return;
            if (!MyAPIGateway.Multiplayer.IsServer)
            {
                float clientMultiplier = PowerMW[Motion.Profile - 2] / PowerMW[0];
                if (reactor.PowerOutputMultiplier != clientMultiplier) reactor.PowerOutputMultiplier = clientMultiplier;
                return;
            }
            var inventory = reactor.GetInventory();
            if (Motion.Core == CorePhase.Off && Motion.Vent == VentPhase.Idle && reactor.CurrentOutput <= 0)
            {
                int selected = -1;
                for (int i = 0; i < Fuels.Length; i++)
                    if (i + 2 <= rings && inventory.GetItemAmount(MyItemType.MakeIngot(Fuels[i])) > 0) selected = i;
                if (selected >= 0) Motion.Profile = selected + 2;
                else if (Motion.Profile > rings) Motion.Profile = rings;
            }
            float multiplier = PowerMW[Motion.Profile - 2] / PowerMW[0];
            if (reactor.PowerOutputMultiplier != multiplier) reactor.PowerOutputMultiplier = multiplier;
            if (initializationFrames == 0 && Motion.Profile > rings) reactor.Enabled = false;

            // Initial balance: one unit/minute at full tier-rated load. Fractional
            // debt avoids fixed-point rounding loss at low demand and is saved.
            bool starvedBurn = Motion.TileStarved && Motion.Core == CorePhase.Running && reactor.Enabled
                && !Motion.PowerPaused && (Motion.Vent == VentPhase.Idle || Motion.Vent == VentPhase.ShieldClosing);
            if (!MyAPIGateway.Session.CreativeMode && (reactor.CurrentOutput > 0 || starvedBurn))
            {
                Motion.FuelDebt += FuelUnitsPerMinute() / 3600;
                MyFixedPoint amount = (MyFixedPoint)Motion.FuelDebt;
                if (amount > 0)
                {
                    string fuel = Fuels[Motion.Profile - 2];
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
                        for (int i = 0; i <= rings - 2; i++)
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
