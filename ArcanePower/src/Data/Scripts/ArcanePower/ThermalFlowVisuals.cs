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
        private readonly MyStringId liquidMaterial = MyStringId.GetOrCompute("ArcaneThermal_Liquid");
        private sealed class FlowView
        {
            internal IMyEntity Entity;
            internal ThermalFlowState State;
            internal int Updated;
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
                Mode = healthy ? ThermalFlowMode.Unconnected : ThermalFlowMode.Fault, Ports = new byte[spec.Ports.Length] };
            view.Updated = MyAPIGateway.Session.GameplayFrameCounter;
        }
        private void BeginFlowFrame()
        {
            captureFlow = MyAPIGateway.Multiplayer.IsServer && tick % 30 == 0;
            if (!captureFlow) return;
            foreach (var block in Blocks.Values) ResetFlow(block.Entity, block.Healthy);
            foreach (var source in VentSession.All)
                if (source.ThermalVariant) ResetFlow(source.Entity, source.ThermalInitialized && !source.Motion.Thermal.Faulted);
        }
        private void CaptureInternalFlow(Reactor source)
        {
            if (!captureFlow) return;
            FlowView view;
            if (!flows.TryGetValue(source.Id, out view)) return;
            if (view.State.Mode == ThermalFlowMode.Fault) return;
            view.State.Rate = source.ThermalInternalCirculation;
            view.State.Heat = ThermalMath.Clamp(source.Motion.Thermal.Store.HotMJ / (source.ThermalHeatMW * .5), 0, 1)
                * ThermalMath.Span(source.ThermalHotC, 45, 2200);
            view.State.Internal = true;
            view.State.Mode = view.State.Rate > 0 ? ThermalFlowMode.Pumping : ThermalFlowMode.Ready;
        }
        private void CapturePlantFlow(Reactor source, ThermalNetwork network, List<ThermalEndpoint> endpoints,
            List<ThermalBlock> bank, ThermalPlan plan, double circulation)
        {
            if (!captureFlow) return;
            var heaters = new HashSet<long>(plan.Heaters);
            var trains = new HashSet<long>();
            var coolers = new HashSet<long>();
            foreach (var train in plan.Trains) trains.Add(train.Id);
            foreach (var block in bank) if (block.Unit().CoolingMW > 0) coolers.Add(block.Entity.EntityId);
            var oriented = new Dictionary<long, byte[]>();
            foreach (var route in new[] {
                network.FlowDirections("PRIMARY", new HashSet<long> { source.Id }, heaters),
                network.FlowDirections("CO2_HP", heaters, trains),
                network.FlowDirections("CO2_LP", trains, coolers) })
                foreach (var entry in route)
                {
                    byte[] ports;
                    if (!oriented.TryGetValue(entry.Key, out ports)) oriented[entry.Key] = ports = new byte[entry.Value.Length];
                    for (int i = 0; i < ports.Length; i++) if (entry.Value[i] != 0) ports[i] = entry.Value[i];
                }
            double heat = ThermalMath.Clamp((source.Motion.Thermal.Store.HotMJ + source.Motion.Thermal.ProducedMW / 60)
                / (source.ThermalHeatMW * .5), 0, 1) * ThermalMath.Span(source.ThermalHotC, 45, 2200);
            foreach (var endpoint in endpoints)
            {
                byte[] ports; FlowView view;
                if (!oriented.TryGetValue(endpoint.Id, out ports) || !flows.TryGetValue(endpoint.Id, out view)) continue;
                view.State.Ports = ports;
                view.State.Rate = ThermalMath.Clamp(circulation, 0, 1);
                view.State.Heat = heat;
                view.State.Internal = endpoint.Model.Kind != ThermalKind.Pipe;
                view.State.Mode = circulation > 0 ? ThermalFlowMode.Pumping : ThermalFlowMode.Ready;
            }
        }
        private void UpdateFlow()
        {
            if (captureFlow && ready) SendFlow(0);
            int now = MyAPIGateway.Session.GameplayFrameCounter;
            foreach (long id in new List<long>(flows.Keys))
            {
                var view = flows[id];
                if (view.Entity == null || view.Entity.Closed) { flows.Remove(id); continue; }
                bool current = now - view.Updated <= 90;
                double target = current && view.State.Mode == ThermalFlowMode.Pumping ? view.State.Rate : 0;
                view.Rate = target > 0 ? view.Rate + (target - view.Rate) * .12 : 0;
                view.Distance = (view.Distance + view.Rate * 1.25 / 60) % 768;
                if (MyAPIGateway.Utilities.IsDedicated || tick % 15 != 0) continue;
                var entity = view.Entity as MyEntity;
                if (entity == null) continue;
                var mode = current ? view.State.Mode : ThermalFlowMode.Unconnected;
                Color status = mode == ThermalFlowMode.Fault ? new Color(255, 65, 40)
                    : mode == ThermalFlowMode.Pumping ? new Color(45, 230, 140)
                    : mode == ThermalFlowMode.Ready ? new Color(255, 185, 55) : new Color(35, 50, 60);
                entity.SetEmissiveParts("ThermalStatus", status, current ? .65f : 0);
                entity.SetEmissivePartsForSubparts("ThermalStatus", status, current ? .65f : 0);
                float intensity = (float)(.08 + view.Rate * .65);
                Color hot = Color.Lerp(new Color(50, 150, 220), new Color(255, 130, 40), (float)view.State.Heat);
                foreach (string material in new[] { "ThermalHot", "ThermalCold" })
                {
                    Color color = material == "ThermalHot" ? hot : new Color(35, 175, 220);
                    entity.SetEmissiveParts(material, color, current ? intensity : 0);
                    entity.SetEmissivePartsForSubparts(material, color, current ? intensity : 0);
                }
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
                    double spacing = path.Circuit == "CHAMBER" ? .125 : .75;
                    double phase = view.Distance * sign % spacing;
                    if (phase < 0) phase += spacing;
                    for (double at = phase; at < path.Length; at += spacing)
                    {
                        if (remaining-- <= 0) return;
                        float fade = (float)Math.Min(1, Math.Min(at, path.Length - at) / Math.Min(.20, path.Length * .25));
                        if (fade <= .01f) continue;
                        Vector3D point = Vector3D.Transform(path.Sample(at), world);
                        Vector3D delta = Vector3D.TransformNormal(path.Sample(Math.Min(path.Length, at + .20)) - path.Sample(at), world);
                        if (delta.LengthSquared() < .000001) continue;
                        Vector4 color = (path.Hot ? Color.Lerp(new Color(60, 165, 225), new Color(255, 145, 55), (float)view.State.Heat)
                            : new Color(45, 195, 230)).ToVector4();
                        color *= fade * (float)(.10 + .18 * view.Rate);
                        if (path.Circuit == "PRIMARY")
                            MyTransparentGeometry.AddLineBillboard(liquidMaterial, color, point,
                                (Vector3)Vector3D.Normalize(delta), (float)delta.Length(), Math.Min(.035f, path.Radius * .18f));
                        else MyTransparentGeometry.AddPointBillboard(gasMaterial, color, point,
                            path.Circuit == "CHAMBER" ? .025f + .065f * (float)(at / path.Length)
                                : Math.Min(.11f, path.Radius * .52f), (float)(at * .7 + view.Distance));
                    }
                }
            }
        }
        private void UnloadFlow()
        {
            MyAPIGateway.Multiplayer.UnregisterSecureMessageHandler(FlowChannel, ReceiveFlow);
            flows.Clear(); flowRequests.Clear(); visibleFlow.Clear();
        }
    }
}
