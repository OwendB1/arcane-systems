using System;
using System.Collections.Generic;
using System.Text;
using Sandbox.Common.ObjectBuilders;
using Sandbox.Definitions;
using Sandbox.Game.EntityComponents;
using Sandbox.ModAPI;
using VRage;
using VRage.Game;
using VRage.Game.Components;
using VRage.ModAPI;
using VRage.ObjectBuilders;

namespace ArcaneThrusters
{
    [MyEntityComponentDescriptor(typeof(MyObjectBuilder_OxygenTank), false, "ArcaneThrusters_RecoveryChargerLG")]
    public sealed class RecoveryCharger : MyGameLogicComponent
    {
        internal const long HeatChannel = 0x41524350524f5001L;
        internal static readonly MyDefinitionId Plasma = MyDefinitionId.Parse("GasProperties/ArcaneThrusters_HydrogenPlasma");
        private const double HeatPerLitre = 1, PowerPerLitre = .02;
        private const float MaxMW = 5;
        private readonly List<IMyGasTank> destinations = new List<IMyGasTank>();
        private IMyGasTank feed;
        private MyResourceSinkComponent sink;
        private Func<float> native;
        private float initialMax, wanted;
        private int lastOffer = -1000, nextScan;
        private double produced;
        private FieldReading reading;
        private bool registered;

        public override void Init(MyObjectBuilder_EntityBase builder) { NeedsUpdate = MyEntityUpdateEnum.BEFORE_NEXT_FRAME; }

        public override void UpdateOnceBeforeFrame()
        {
            feed = (IMyGasTank)Entity;
            if (feed.CubeGrid.Physics == null) return;
            if (MyAPIGateway.Session == null || (sink = feed.Components.Get<MyResourceSinkComponent>()) == null)
            { NeedsUpdate |= MyEntityUpdateEnum.BEFORE_NEXT_FRAME; return; }
            feed.AppendingCustomInfo += Info;
            if (!MyAPIGateway.Multiplayer.IsServer) return;
            var power = MyResourceDistributorComponent.ElectricityId;
            initialMax = sink.MaxRequiredInputByType(power);
            native = sink.SetRequiredInputFuncByType(power, Demand);
            sink.SetMaxRequiredInputByType(power, initialMax + MaxMW);
            Register(ConvertHeat);
            registered = true;
            NeedsUpdate |= MyEntityUpdateEnum.EACH_10TH_FRAME | MyEntityUpdateEnum.EACH_100TH_FRAME;
        }

        private void Register(Func<double,double> convert)
        {
            MyAPIGateway.Utilities.SendModMessage(HeatChannel,
                new MyTuple<IMyFunctionalBlock,Func<double,double>>(feed, convert));
        }

        private float Demand() { return native() + (feed.Enabled && feed.IsFunctional ? wanted : 0); }
        public override void UpdateAfterSimulation100() { Register(ConvertHeat); }
        public override void UpdateAfterSimulation10()
        {
            if (MyAPIGateway.Session.GameplayFrameCounter - lastOffer > 1)
            { wanted = 0; produced = 0; }
            sink.Update();
            if (MyAPIGateway.Session.GameplayFrameCounter % 60 < 10)
            {
                var snapshot = new FieldReading { EntityId = feed.EntityId, Demand = wanted, LitresPerSecond = produced };
                ShowReading(snapshot);
                FieldTelemetry.Send(feed, snapshot);
            }
        }

        private bool Eligible(IMyGasTank t)
        {
            var definition = t.SlimBlock.BlockDefinition as MyGasTankDefinition;
            return !t.MarkedForClose && t.IsWorking && t.FilledRatio < 1 && t.HasInventory
                && definition != null && definition.StoredGasId == Plasma && t.HasPlayerAccess(feed.OwnerId)
                && feed.GetInventory().IsConnectedTo(t.GetInventory());
        }

        private double ConvertHeat(double offeredMJ)
        {
            lastOffer = MyAPIGateway.Session.GameplayFrameCounter;
            wanted = 0;
            produced = 0;
            if (feed.MarkedForClose || !feed.Enabled || !feed.IsFunctional || !feed.HasInventory
                || offeredMJ <= 0 || feed.FilledRatio <= 0) return 0;
            if (lastOffer >= nextScan)
            {
                destinations.Clear();
                var terminal = MyAPIGateway.TerminalActionsHelper.GetTerminalSystemForGrid(feed.CubeGrid);
                if (terminal != null) terminal.GetBlocksOfType(destinations, t => t != feed
                    && (t.SlimBlock.BlockDefinition as MyGasTankDefinition).StoredGasId == Plasma);
                nextScan = lastOffer + 60;
            }
            var power = MyResourceDistributorComponent.ElectricityId;
            double delivered = Math.Max(0, sink.CurrentInputByType(power) - native());
            double remaining = Math.Min(offeredMJ / HeatPerLitre, feed.Capacity * feed.FilledRatio);
            double consumed = 0, unallocated = remaining;
            foreach (var tank in destinations)
            {
                if (!Eligible(tank)) continue;
                double demand = Math.Min(remaining, (1 - tank.FilledRatio) * tank.Capacity);
                double requested = Math.Min(demand, unallocated);
                wanted = (float)Math.Min(MaxMW, wanted + requested * PowerPerLitre * 60);
                unallocated -= requested;
                double batch = Math.Min(demand, delivered / (60 * PowerPerLitre) - consumed);
                if (batch <= .000001) continue;
                double before = feed.FilledRatio;
                feed.ChangeFilledRatio(Math.Max(0, before - batch / feed.Capacity), true);
                double removed = Math.Max(0, (before - feed.FilledRatio) * feed.Capacity);
                double start = tank.FilledRatio;
                tank.ChangeFilledRatio(Math.Min(1, start + Math.Min(batch, removed) / tank.Capacity), true);
                double accepted = Math.Max(0, (tank.FilledRatio - start) * tank.Capacity);
                if (removed > accepted + .000001)
                    feed.ChangeFilledRatio(Math.Min(1, feed.FilledRatio + (removed - accepted) / feed.Capacity), true);
                consumed += accepted;
                remaining -= accepted;
                if (remaining <= .000001) break;
            }
            produced = consumed * 60;
            return Math.Min(offeredMJ, consumed * HeatPerLitre);
        }

        internal void ShowReading(FieldReading snapshot)
        {
            reading = snapshot;
            if (feed != null) { feed.RefreshCustomInfo(); feed.SetDetailedInfoDirty(); }
        }

        private void Info(IMyTerminalBlock block, StringBuilder text)
        {
            text.AppendLine("Duplex end: Brayton circuit. Conveyor end: hydrogen feed and plasma storage.");
            if (reading != null)
                text.AppendFormat("Plasma production: {0:N1} L/s\nIonizer demand: {1:N2} MW", reading.LitresPerSecond, reading.Demand);
        }

        public override void Close()
        {
            if (feed != null) feed.AppendingCustomInfo -= Info;
            if (registered && MyAPIGateway.Session != null) Register(null);
            if (native != null)
            {
                var power = MyResourceDistributorComponent.ElectricityId;
                sink.SetRequiredInputFuncByType(power, native);
                sink.SetMaxRequiredInputByType(power, initialMax);
            }
        }
    }
}
