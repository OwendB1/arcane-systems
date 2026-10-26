using System;
using Sandbox.ModAPI;
using VRage.Game;
using VRage.Game.Entity;
using VRage.ModAPI;
using VRage.ObjectBuilders;
using VRageMath;

namespace ArcanePower
{
    // Shared native valve meshes, attached like normal SE model subparts. No
    // collision, inventory, save data or independently simulated fluid entities.
    internal sealed class ThermalIsolationVisuals
    {
        internal const string Model = "Models/Cubes/large/Thermal/Isolation/ArcaneIsolationSeat.mwm";
        private readonly MyEntity parent;
        private readonly MyEntitySubpart[] seats;
        private readonly double[] opening;
        internal ThermalIsolationVisuals(MyEntity entity, int ports)
        { parent = entity; seats = new MyEntitySubpart[ports * 2]; opening = new double[ports]; }

        private static string Key(int index) { return "ArcaneIsolation" + index; }
        internal void Update(string modPath, ThermalModel spec, byte connected, double deployment)
        {
            for (int i = 0; i < opening.Length; i++)
            {
                bool open = (connected & (1 << i)) != 0;
                opening[i] = ThermalIsolation.Step(opening[i], open, 1.0 / 60);
                for (int side = 0; side < 2; side++)
                {
                    int index = i * 2 + side;
                    var seat = seats[index];
                    if (seat == null || seat.Closed || seat.MarkedForClose)
                    {
                        seat = new MyEntitySubpart();
                        seats[index] = seat;
                        seat.Init(null, modPath + "/" + Model, parent, null);
                        seat.Render.NeedsDrawFromParent = false;
                        seat.Render.PersistentFlags = parent.Render.PersistentFlags & ~MyPersistentEntityFlags2.InScene;
                        parent.Subparts[Key(index)] = seat;
                        if (parent.InScene) seat.OnAddedToScene(parent);
                        seat.Flags &= ~EntityFlags.IsGamePrunningStructureObject;
                    }
                    Matrix pose = ThermalIsolation.Seat(spec.Ports[i], side == 0 ? -1 : 1);
                    pose.Translation += ThermalManifolds.Pose(i, "Carriage", deployment).Translation
                        - ThermalManifolds.Pose(i, "Carriage", 1).Translation;
                    seat.PositionComp.SetLocalMatrix(ref pose);
                    MyEntitySubpart gate;
                    if (seat.Subparts.TryGetValue("Gate", out gate))
                    {
                        Matrix turn = ThermalIsolation.Gate(opening[i]);
                        gate.PositionComp.SetLocalMatrix(ref turn);
                        gate.SetEmissiveParts("ThermalStatus", open ? new Color(45, 230, 140) : new Color(35, 175, 220), .35f);
                    }
                }
            }
        }
        internal void Close()
        {
            for (int i = 0; i < seats.Length; i++)
            {
                var seat = seats[i];
                if (seat == null) continue;
                MyEntitySubpart owned;
                if (parent.Subparts != null && parent.Subparts.TryGetValue(Key(i), out owned) && owned == seat)
                    parent.Subparts.Remove(Key(i));
                if (!seat.Closed && !seat.MarkedForClose)
                { parent.Hierarchy.RemoveChild(seat); seat.Close(); }
                seats[i] = null;
            }
        }
    }

    public sealed partial class ThermalSession
    {
        private bool isolationChanged;
        private void CaptureIsolation(ThermalNetwork network, System.Collections.Generic.List<ThermalEndpoint> endpoints, byte reactorPorts)
        {
            foreach (var node in endpoints)
            {
                FlowView view;
                if (!flows.TryGetValue(node.Id, out view)) continue;
                // Several reactors can inspect one grid with different access
                // rights. Union their permitted joints before publishing once.
                view.NextOpenConnectors |= node == endpoints[0] ? reactorPorts
                    : node.Model.Kind == ThermalKind.Reactor ? (byte)0 : network.OpenPorts(node);
            }
        }
        private void ApplyIsolation()
        {
            foreach (var view in flows.Values)
            {
                if (view.State.OpenConnectors == view.NextOpenConnectors) continue;
                view.State.OpenConnectors = view.NextOpenConnectors;
                view.State.Sequence = tick;
                view.Updated = MyAPIGateway.Session.GameplayFrameCounter;
                isolationChanged = true;
            }
        }
        private void UpdateIsolation(FlowView view, bool current)
        {
            if (MyAPIGateway.Utilities.IsDedicated) return;
            var block = view.Entity as Sandbox.ModAPI.IMyFunctionalBlock;
            var camera = MyAPIGateway.Session.Camera;
            bool nearby = camera != null && Vector3D.DistanceSquared(view.Entity.GetPosition(), camera.Position) < 100 * 100;
            if (block == null || !block.IsFunctional || block.SlimBlock.BuildLevelRatio < 1 || !nearby)
            { if (view.Valves != null) { view.Valves.Close(); view.Valves = null; } return; }
            if (tick < view.ValveRetryAt) return;
            var spec = FlowSpec(view.Entity);
            if (spec == null || spec.Kind != ThermalKind.Reactor)
            { if (view.Valves != null) { view.Valves.Close(); view.Valves = null; } return; }
            var source = VentSession.Find(view.Entity.EntityId);
            if (source == null || source.Motion.Thermal == null) return;
            try
            {
                if (view.Valves == null) view.Valves = new ThermalIsolationVisuals((MyEntity)view.Entity, spec.Ports.Length);
                view.Valves.Update(ModContext.ModPath, spec, current ? view.State.OpenConnectors : (byte)0, source.Motion.Thermal.Deployment);
            }
            catch (Exception error)
            {
                if (view.Valves != null) view.Valves.Close();
                view.Valves = null; view.ValveRetryAt = tick + 120;
                VRage.Utils.MyLog.Default.WriteLine("ArcanePower: valve visual unavailable: " + error.Message);
            }
        }
    }
}
