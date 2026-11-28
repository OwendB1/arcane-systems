using System;
using System.Text;
using Sandbox.Common.ObjectBuilders;
using Sandbox.ModAPI;
using VRage.Game.Components;
using VRage.ModAPI;
using VRage.ObjectBuilders;
using VRageMath;

namespace ArcaneThrusters
{
    [MyEntityComponentDescriptor(typeof(MyObjectBuilder_Thrust), false,
        "ArcaneThrusters_DualModeThrusterSG", "ArcaneThrusters_DualModeThrusterSG_Hull",
        "ArcaneThrusters_DualModeThrusterLG", "ArcaneThrusters_DualModeThrusterLG_Hull")]
    public sealed class PlasmaDrive : MyGameLogicComponent
    {
        // A litre supplies 480 N.s of additional impulse. A saturated native burn
        // gets up to 50% extra thrust without writing the ship core's multipliers.
        private const double ImpulsePerLitre = 480;
        private EngineFeed feed;
        private IMyThrust engine;
        private int sample;
        private double consumed, lastStored;
        private long lastNetwork;
        private bool sampled;
        internal FieldReading Reading;

        public override void Init(MyObjectBuilder_EntityBase builder) { NeedsUpdate = MyEntityUpdateEnum.BEFORE_NEXT_FRAME; }

        public override void UpdateOnceBeforeFrame()
        {
            engine = (IMyThrust)Entity;
            if (engine.CubeGrid.Physics == null) return;
            if (MyAPIGateway.Session == null) { NeedsUpdate |= MyEntityUpdateEnum.BEFORE_NEXT_FRAME; return; }
            engine.AppendingCustomInfo += Info;
            if (!MyAPIGateway.Multiplayer.IsServer) return;
            feed = new EngineFeed(engine, RecoveryCharger.Plasma);
            NeedsUpdate |= MyEntityUpdateEnum.EACH_FRAME;
        }

        public override void UpdateAfterSimulation()
        {
            var physics = engine.CubeGrid.Physics;
            // Extra force only above the native controller's fully demanded range.
            // Partial dampener corrections retain vanilla precision near zero speed.
            double measured = engine.IsWorking && physics != null ? engine.CurrentThrust : 0;
            double demand = Math.Max(0, measured - .9 * engine.MaxEffectiveThrust) * 5 / (60 * ImpulsePerLitre);
            bool publish = ++sample >= 60;
            if (demand <= 0 && !publish) return;
            double stored;
            long network;
            double used = feed.Draw(demand, out stored, out network);
            if (used > 0)
            {
                NozzleGimbal.ApplyAdditional(engine, used * ImpulsePerLitre * 60);
                RecordBoost(used * ImpulsePerLitre * 60);
            }
            consumed += used;
            if (!publish) return;
            // Net withdrawal includes live charging and the other engines sharing these tanks.
            double withdrawal = lastStored - stored;
            double seconds = consumed <= .00001 || !sampled || network != lastNetwork ? -1
                : withdrawal > .00001 ? stored / withdrawal : -2;
            var snapshot = new FieldReading { EntityId = engine.EntityId, State = consumed > .00001 ? "Plasma boost" : "Hydrogen",
                BurnSeconds = seconds, LitresPerSecond = consumed, ForceN = consumed * ImpulsePerLitre };
            ShowReading(snapshot);
            FieldTelemetry.Send(engine, snapshot);
            lastNetwork = network;
            lastStored = stored;
            sampled = true;
            sample = 0;
            consumed = 0;
        }

        internal static string Endurance(FieldReading r)
        {
            return r.BurnSeconds == -2 ? "sustained" : r.BurnSeconds < 0 ? "—" : Math.Ceiling(r.BurnSeconds) + " s";
        }

        private void RecordBoost(double force)
        {
            if (engine.MaxEffectiveThrust > 0) DrivePlume.Record(engine, force / (.5 * engine.MaxEffectiveThrust));
        }

        internal void ShowReading(FieldReading snapshot)
        {
            Reading = snapshot;
            if (engine == null) return;
            if (!MyAPIGateway.Multiplayer.IsServer) RecordBoost(snapshot.ForceN);
            engine.SetEmissiveParts("ArcanePlasmaBell", new Color(42, 152, 255), snapshot.ForceN > 0 ? 1f : .12f);
            engine.SetEmissivePartsForSubparts("ArcanePlasmaBell", new Color(42, 152, 255), snapshot.ForceN > 0 ? 1f : .12f);
            engine.RefreshCustomInfo();
            engine.SetDetailedInfoDirty();
        }

        private void Info(IMyTerminalBlock block, StringBuilder text)
        {
            if (Reading != null) text.AppendFormat("{0}\nAdditional thrust: {1:N0} N\nPlasma: {2:N1} L/s\nBurn remaining: {3}",
                Reading.State, Reading.ForceN, Reading.LitresPerSecond, Endurance(Reading));
        }

        public override void Close() { if (engine != null) engine.AppendingCustomInfo -= Info; }
    }
}
