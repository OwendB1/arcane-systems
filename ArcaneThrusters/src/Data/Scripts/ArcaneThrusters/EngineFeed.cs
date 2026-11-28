using System;
using System.Collections.Generic;
using Sandbox.Definitions;
using Sandbox.Game;
using Sandbox.ModAPI;
using VRage.Game;
using VRage.Game.Entity;
using VRageMath;

namespace ArcaneThrusters
{
    // IsConnectedTo uses the inventory owner's real conveyor endpoint. Engines
    // get a zero-volume anchor with no transfer flags. All gas stays in native tanks.
    internal sealed class EngineFeed
    {
        private readonly IMyThrust engine;
        private readonly MyDefinitionId gas;
        private readonly List<IMyGasTank> tanks = new List<IMyGasTank>();
        private int nextScan;

        internal EngineFeed(IMyThrust block, MyDefinitionId gasType)
        {
            engine = block;
            gas = gasType;
            if (!engine.HasInventory)
                engine.Components.Add<MyInventoryBase>(new MyInventory(0f, Vector3.Zero, (MyInventoryFlags)0));
        }

        internal double Draw(double litres, out double stored, out long network)
        {
            int frame = MyAPIGateway.Session.GameplayFrameCounter;
            if (frame >= nextScan)
            {
                tanks.Clear();
                var terminal = MyAPIGateway.TerminalActionsHelper.GetTerminalSystemForGrid(engine.CubeGrid);
                if (terminal != null) terminal.GetBlocksOfType(tanks, t =>
                    ((MyGasTankDefinition)t.SlimBlock.BlockDefinition).StoredGasId == gas);
                nextScan = frame + 60;
            }
            double used = 0;
            stored = 0;
            network = 0;
            foreach (var tank in tanks)
            {
                if (tank.MarkedForClose || !tank.IsWorking || tank.Stockpile || !tank.HasPlayerAccess(engine.OwnerId)
                    || !tank.GetInventory().IsConnectedTo(engine.GetInventory())) continue;
                network ^= tank.EntityId;
                if (used < litres && tank.FilledRatio > 0)
                {
                    double before = tank.FilledRatio;
                    tank.ChangeFilledRatio(Math.Max(0, before - (litres - used) / tank.Capacity), true);
                    used += Math.Max(0, (before - tank.FilledRatio) * tank.Capacity);
                }
                stored += tank.Capacity * tank.FilledRatio;
            }
            return Math.Min(used, litres);
        }
    }
}
