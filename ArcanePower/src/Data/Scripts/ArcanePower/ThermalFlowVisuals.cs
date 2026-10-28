using System;
using System.Collections.Generic;
using ProtoBuf;
using Sandbox.ModAPI;
using VRage.Game;
using VRage.Game.Entity;
using VRage.ModAPI;
using VRage.Utils;
using VRageMath;

namespace ArcanePower
{
    [ProtoContract]
    public sealed class ThermalFlowPacket
    {
        [ProtoMember(1)] public ThermalFlowState[] States;
    }

    public sealed partial class ThermalSession
    {
        private const ushort FlowChannel = 49373;
        private bool captureFlow;
        private readonly Dictionary<long, FlowView> flows = new Dictionary<long, FlowView>();
        private readonly Dictionary<ulong, int> flowRequests = new Dictionary<ulong, int>();
        private readonly List<FlowView> visibleFlow = new List<FlowView>();
        private readonly MyStringId gasMaterial = MyStringId.GetOrCompute("ArcaneThermal_Gas");
        private readonly MyStringId flowMaterial = MyStringId.GetOrCompute("ArcaneThermal_Liquid");
        private sealed class FlowView
        {
            internal IMyEntity Entity;
            internal ThermalFlowState State;
            internal int Updated, ValveRetryAt;
            internal byte NextOpenConnectors;
            internal ThermalIsolationVisuals Valves;
            internal double Distance, Rate, CameraDistance;
        }
        private static ThermalModel FlowSpec(IMyEntity entity)
        {
            var block = entity as VRage.Game.ModAPI.IMyCubeBlock;
            ThermalModel spec;
            return block != null && ThermalModels.All.TryGetValue(block.BlockDefinition.SubtypeName, out spec) ? spec : null;
        }
        private void InitializeFlow()
        {
            MyAPIGateway.Multiplayer.RegisterSecureMessageHandler(FlowChannel, ReceiveFlow);
            if (!MyAPIGateway.Multiplayer.IsServer)
                MyAPIGateway.Multiplayer.SendMessageToServer(FlowChannel, MyAPIGateway.Utilities.SerializeToBinary(new ThermalFlowPacket()));
        }
        private void ReceiveFlow(ushort channel, byte[] bytes, ulong sender, bool fromServer)
        {
            if (bytes == null || bytes.Length == 0 || bytes.Length > 32768) return;
            try
            {
                var packet = MyAPIGateway.Utilities.SerializeFromBinary<ThermalFlowPacket>(bytes);
                if (packet == null || (packet.States != null && packet.States.Length > 64)) return;
                MyAPIGateway.Utilities.InvokeOnGameThread(() =>
                {
                    if (!ready) return;
                    if (MyAPIGateway.Multiplayer.IsServer)
                    {
                        if (fromServer || packet.States != null) return;
                        int previous, now = MyAPIGateway.Session.GameplayFrameCounter;
                        if (flowRequests.TryGetValue(sender, out previous) && now - previous < 120) return;
                        flowRequests[sender] = now;
                        SendFlow(sender);
                    }
                    else if (fromServer && packet.States != null)
                        foreach (var state in packet.States)
                        {
                            IMyEntity entity;
                            if (state == null || !MyAPIGateway.Entities.TryGetEntityById(state.EntityId, out entity)) continue;
                            var spec = FlowSpec(entity);
                            if (spec == null || !state.Valid(spec.Ports.Length)) continue;
                            FlowView view;
                            if (flows.TryGetValue(state.EntityId, out view) && state.Sequence <= view.State.Sequence) continue;
                            if (view == null) flows[state.EntityId] = view = new FlowView { Entity = entity };
                            view.State = state; view.Updated = MyAPIGateway.Session.GameplayFrameCounter;
                        }
                });
            }
            catch (Exception error) { MyLog.Default.WriteLine("ArcanePower: ignored invalid flow packet: " + error.Message); }
        }
        private void SendFlow(ulong recipient)
        {
            var batch = new List<ThermalFlowState>();
            foreach (var view in flows.Values)
            {
                batch.Add(view.State);
                if (batch.Count == 64) { SendFlowBatch(batch.ToArray(), recipient); batch.Clear(); }
            }
            if (batch.Count > 0) SendFlowBatch(batch.ToArray(), recipient);
        }
        private static void SendFlowBatch(ThermalFlowState[] states, ulong recipient)
        {
            byte[] bytes = MyAPIGateway.Utilities.SerializeToBinary(new ThermalFlowPacket { States = states });
            if (recipient == 0) MyAPIGateway.Multiplayer.SendMessageToOthers(FlowChannel, bytes);
            else MyAPIGateway.Multiplayer.SendMessageTo(FlowChannel, bytes, recipient);
        }
        private void ResetFlow(IMyEntity entity, bool healthy)
        {
            var spec = FlowSpec(entity);
            if (spec == null) return;
            FlowView view;
            if (!flows.TryGetValue(entity.EntityId, out view))
                flows[entity.EntityId] = view = new FlowView { Entity = entity };
            view.State = new ThermalFlowState { EntityId = entity.EntityId, Sequence = tick,
                Mode = healthy ? ThermalFlowMode.Unconnected : ThermalFlowMode.Fault, Ports = new byte[spec.Ports.Length],
                OpenConnectors = view.State == null ? (byte)0 : view.State.OpenConnectors };
            view.Updated = MyAPIGateway.Session.GameplayFrameCounter;
        }
        private void BeginFlowFrame()
        {
            if (MyAPIGateway.Multiplayer.IsServer)
                foreach (var view in flows.Values) view.NextOpenConnectors = 0;
            captureFlow = MyAPIGateway.Multiplayer.IsServer && tick % 30 == 0;
            if (!captureFlow) return;
            foreach (var block in Blocks.Values) ResetFlow(block.Entity, block.Healthy);
            foreach (var joint in ThermalPipeJoint.All)
                ResetFlow(joint, joint.IsFunctional && joint.SlimBlock.BuildLevelRatio >= 1);
            foreach (var source in VentSession.All)
                if (source.ThermalVariant) ResetFlow(source.Entity, source.ThermalInitialized && !source.Motion.Thermal.Faulted);
        }
        private void CaptureInternalFlow(Reactor source)
        {
            if (!captureFlow) return;
            FlowView view;
            if (!flows.TryGetValue(source.Id, out view)) return;
            if (view.State.Mode == ThermalFlowMode.Fault) return;
            view.State.Rate = Math.Max(source.ThermalVisualLoad, source.Motion.Thermal.RejectedMW > .001 ? .1 : 0);
            view.State.Heat = Math.Max(source.ThermalVisualLoad, ThermalMath.WasteHeatLevel(source.Motion.Thermal, source.ThermalHeatMW) / 4)
                * ThermalMath.Span(source.ThermalHotC, 45, 2200);
            view.State.Internal = true;
            view.State.Mode = view.State.Rate > 0 ? ThermalFlowMode.Pumping : ThermalFlowMode.Ready;
        }
        private void CapturePlantFlow(Reactor source, ThermalNetwork network, List<ThermalEndpoint> endpoints,
            List<ThermalBlock> bank, ThermalPlan plan, double load)
        {
            if (!captureFlow) return;
            var trains = new HashSet<long>();
            var coolers = new HashSet<long>();
            foreach (var train in plan.Trains) trains.Add(train.Id);
            foreach (var block in bank) if (block.Unit().CoolingMW > 0) coolers.Add(block.Entity.EntityId);
            // One supply/return pair reaches every dispatched terminal branch.
            // H flows from the reactor to active machines; C follows it back.
            trains.UnionWith(coolers);
            var oriented = network.FlowDirections(new HashSet<long> { source.Id }, trains);
            double heat = ThermalMath.Clamp(load, 0, 1) * ThermalMath.Span(source.ThermalHotC, 45, 2200);
            foreach (var endpoint in endpoints)
            {
                byte[] ports; FlowView view;
                if (!flows.TryGetValue(endpoint.Id, out view)) continue;
                oriented.TryGetValue(endpoint.Id, out ports);
                view.State.ObserveCircuit(ports, load, heat, endpoint.Model.Kind != ThermalKind.Pipe);
                ThermalBlock radiator;
                if (Blocks.TryGetValue(endpoint.Id, out radiator) && radiator.Spec.Kind == ThermalKind.Radiator)
                    foreach (var panel in radiator.RadiatorPanels)
                    {
                        FlowView linked;
                        if (!flows.TryGetValue(panel.Entity.EntityId, out linked)) continue;
                        linked.State.Rate = view.State.Rate;
                        linked.State.Heat = view.State.Heat;
                        linked.State.Mode = view.State.Mode;
                        linked.State.Internal = true;
                    }
            }
        }
        private void UpdateFlow()
        {
            if (MyAPIGateway.Multiplayer.IsServer) ApplyIsolation();
            if ((captureFlow || isolationChanged) && ready) SendFlow(0);
            isolationChanged = false;
            int now = MyAPIGateway.Session.GameplayFrameCounter;
            foreach (long id in new List<long>(flows.Keys))
            {
                var view = flows[id];
                if (view.Entity == null || view.Entity.Closed) { if (view.Valves != null) view.Valves.Close(); flows.Remove(id); continue; }
                bool current = now - view.Updated <= 90;
                double target = current && view.State.Mode == ThermalFlowMode.Pumping ? view.State.Rate : 0;
                view.Rate = target > 0 ? view.Rate + (target - view.Rate) * .12 : 0;
                view.Distance = (view.Distance + view.Rate * 1.25 / 60) % 768;
                if (MyAPIGateway.Utilities.IsDedicated) continue;
                if (tick % 15 != 0) { UpdateIsolation(view, current); continue; }
                var entity = view.Entity as MyEntity;
                if (entity == null) continue;
                var mode = current ? view.State.Mode : ThermalFlowMode.Unconnected;
                var spec = FlowSpec(view.Entity);
                bool pipeFault = current && spec != null && spec.Kind == ThermalKind.Pipe
                    && (mode == ThermalFlowMode.Unconnected || mode == ThermalFlowMode.Fault);
                Color status = pipeFault ? Color.Red : mode == ThermalFlowMode.Fault ? new Color(255, 65, 40)
                    : mode == ThermalFlowMode.Pumping ? new Color(45, 230, 140)
                    : mode == ThermalFlowMode.Ready ? new Color(255, 185, 55) : new Color(35, 50, 60);
                var source = spec != null && spec.Kind == ThermalKind.Reactor ? VentSession.Find(id) : null;
                if (current && source != null)
                {
                    if (source.Motion.Critical || source.Motion.Vent != VentPhase.Idle) status = Color.Red;
                    else if (source.Motion.ThermalWarning) status = Color.Yellow;
                    else if (mode == ThermalFlowMode.Ready) status = new Color(35, 175, 220);
                }
                float statusIntensity = pipeFault ? .325f : .65f;
                if (source != null && source.Motion.Critical)
                    statusIntensity *= now % 60 < 30 ? 1f : 0f;
                entity.SetEmissiveParts("ThermalStatus", status, current ? statusIntensity : 0);
                entity.SetEmissivePartsForSubparts("ThermalStatus", status, current ? statusIntensity : 0);
                float intensity = pipeFault ? statusIntensity : (float)(.08 + view.Rate * .65);
                Color hot = Color.Lerp(new Color(50, 150, 220), new Color(255, 130, 40), (float)view.State.Heat);
                foreach (string material in new[] { "ThermalHot", "ThermalCold" })
                {
                    Color color = pipeFault ? Color.Red : material == "ThermalHot" ? hot : new Color(35, 175, 220);
                    entity.SetEmissiveParts(material, color, current ? intensity : 0);
                    entity.SetEmissivePartsForSubparts(material, color, current ? intensity : 0);
                }
                UpdateIsolation(view, current);
            }
        }
        public override void Draw()
        {
            if (MyAPIGateway.Utilities.IsDedicated || MyAPIGateway.Session == null || MyAPIGateway.Session.Camera == null) return;
            Vector3D camera = MyAPIGateway.Session.Camera.WorldMatrix.Translation;
            visibleFlow.Clear();
            int now = MyAPIGateway.Session.GameplayFrameCounter;
            foreach (var view in flows.Values)
            {
                if (view.Entity == null || view.Entity.Closed || view.Rate <= .001 || now - view.Updated > 90) continue;
                view.CameraDistance = Vector3D.DistanceSquared(view.Entity.GetPosition(), camera);
                if (view.CameraDistance < 80 * 80) visibleFlow.Add(view);
            }
            visibleFlow.Sort((a, b) => a.CameraDistance.CompareTo(b.CameraDistance));
            int remaining = 768;
            foreach (var view in visibleFlow)
            {
                var spec = FlowSpec(view.Entity); ThermalFlowPath[] paths;
                if (spec == null || !ThermalFlowModels.All.TryGetValue(spec.Subtype, out paths)) continue;
                MatrixD world = view.Entity.WorldMatrix;
                foreach (var path in paths)
                {
                    int sign = path.Direction(view.State);
                    if (sign == 0) continue;
                    bool chamber = path.Circuit == "CHAMBER";
                    if (chamber)
                    {
                        var source = VentSession.Find(view.Entity.EntityId);
                        if (source == null || source.Motion.Thermal.Mode != ThermalMode.Brayton
                            || !source.Motion.Thermal.Settled) continue;
                    }
                    double spacing = chamber ? .125 : .50;
                    double phase = view.Distance * sign % spacing;
                    if (phase < 0) phase += spacing;
                    for (double at = phase; at < path.Length; at += spacing)
                    {
                        float fade = (float)Math.Min(1, Math.Min(at, path.Length - at) / Math.Min(.20, path.Length * .25));
                        if (fade <= .01f) continue;
                        Vector3D point = Vector3D.Transform(path.Sample(at), world);
                        // Supply/return colours are deliberately readable even at low load.
                        Vector4 color = (path.Hot ? Color.Lerp(new Color(255, 190, 75), new Color(255, 105, 40), (float)view.State.Heat)
                            : new Color(40, 205, 255)).ToVector4();
                        color *= fade * (float)(chamber ? .10 + .18 * view.Rate : .50 + .30 * view.Rate);
                        // Brighter gas and liquid emission without increasing opacity.
                        color *= new Vector4(1.5f, 1.5f, 1.5f, 1f);
                        if (chamber)
                        {
                            if (remaining-- <= 0) return;
                            MyTransparentGeometry.AddPointBillboard(gasMaterial, color, point,
                                .025f + .065f * (float)(at / path.Length), (float)(at * .7 + view.Distance));
                        }
                        else
                        {
                            // One texture per glob; splitting at path vertices shrinks
                            // and repeats the texture on densely sampled curves.
                            double end = Math.Min(path.Length, at + .30);
                            Vector3D tip = Vector3D.Transform(path.Sample(end), world);
                            Vector3D delta = tip - point;
                            if (delta.LengthSquared() > .000001)
                            {
                                if (remaining-- <= 0) return;
                                MyTransparentGeometry.AddLineBillboard(flowMaterial, color, point,
                                    (Vector3)Vector3D.Normalize(delta), (float)delta.Length(), Math.Min(.11f, path.Radius * .50f));
                            }
                        }
                    }
                }
            }
        }
        private void UnloadFlow()
        {
            MyAPIGateway.Multiplayer.UnregisterSecureMessageHandler(FlowChannel, ReceiveFlow);
            foreach (var view in flows.Values) if (view.Valves != null) view.Valves.Close();
            flows.Clear(); flowRequests.Clear(); visibleFlow.Clear();
        }
    }
}
