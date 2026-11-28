using System;
using System.Text;
using Sandbox.Common.ObjectBuilders;
using Sandbox.ModAPI;
using VRage;
using VRage.Game;
using VRage.Game.Components;
using VRage.ModAPI;
using VRage.ObjectBuilders;
using VRageMath;

namespace ArcaneThrusters
{
    [MyEntityComponentDescriptor(typeof(MyObjectBuilder_Thrust), false,
        "ArcaneThrusters_DrivePriorityLG", "ArcaneThrusters_DrivePriorityLG_Hull")]
    public sealed class ThermalDrive : MyGameLogicComponent
    {
        private const double HeatMW = 1000, ForceN = 12000000, FullFlow = 5000;
        private IMyThrust engine;
        private EngineFeed feed;
        private double usedMJ;
        private int frames;
        private FieldReading reading;

        public override void Init(MyObjectBuilder_EntityBase builder) { NeedsUpdate = MyEntityUpdateEnum.BEFORE_NEXT_FRAME; }
        public override void UpdateOnceBeforeFrame()
        {
            engine = (IMyThrust)Entity;
            if (engine.CubeGrid.Physics == null) return;
            if (MyAPIGateway.Session == null) { NeedsUpdate |= MyEntityUpdateEnum.BEFORE_NEXT_FRAME; return; }
            engine.AppendingCustomInfo += Info;
            if (!MyAPIGateway.Multiplayer.IsServer) return;
            feed = new EngineFeed(engine, MyDefinitionId.Parse("GasProperties/Hydrogen"));
            Register(Burn);
            NeedsUpdate |= MyEntityUpdateEnum.EACH_FRAME;
        }

        private void Register(Func<double, double> callback)
        {
            MyAPIGateway.Utilities.SendModMessage(RecoveryCharger.HeatChannel,
                new MyTuple<IMyFunctionalBlock, Func<double, double>>(engine, callback));
        }

        private double Burn(double offeredMJ)
        {
            if (!engine.IsWorking || engine.MarkedForClose || engine.CubeGrid.Physics == null) return 0;
            double requested = Math.Min(offeredMJ, engine.ThrustOverridePercentage * HeatMW / 60);
            if (requested <= 0) return 0;
            double stored;
            long network;
            double litres = feed.Draw(requested * FullFlow / HeatMW, out stored, out network);
            double heat = Math.Min(requested, litres * HeatMW / FullFlow);
            if (heat <= 0) return 0;
            double thrust = heat * 60 * ForceN / HeatMW * engine.ThrustMultiplier;
            NozzleGimbal.ApplyAdditional(engine, thrust);
            DrivePlume.Record(engine, heat * 60 / HeatMW);
            usedMJ += heat;
            return heat;
        }

        public override void UpdateAfterSimulation()
        {
            if (++frames < 60) return;
            Register(Burn);
            var snapshot = new FieldReading { EntityId = engine.EntityId, Demand = (float)usedMJ,
                LitresPerSecond = usedMJ * FullFlow / HeatMW, ForceN = usedMJ * ForceN / HeatMW * engine.ThrustMultiplier };
            ShowReading(snapshot);
            FieldTelemetry.Send(engine, snapshot);
            usedMJ = 0;
            frames = 0;
        }

        internal void ShowReading(FieldReading snapshot)
        {
            reading = snapshot;
            if (!MyAPIGateway.Multiplayer.IsServer) DrivePlume.Record(engine, snapshot.Demand / HeatMW);
            if (engine != null) { engine.RefreshCustomInfo(); engine.SetDetailedInfoDirty(); }
        }

        private void Info(IMyTerminalBlock block, StringBuilder text)
        {
            text.AppendLine("Drive Priority follows thrust override on a running Brayton circuit.");
            if (reading != null) text.AppendFormat("Reactor heat: {0:N1} MW\nHydrogen: {1:N1} L/s\nThermal thrust: {2:N0} N",
                reading.Demand, reading.LitresPerSecond, reading.ForceN);
        }

        public override void Close()
        {
            if (engine != null) engine.AppendingCustomInfo -= Info;
            if (feed != null && MyAPIGateway.Session != null) Register(null);
        }
    }
}
