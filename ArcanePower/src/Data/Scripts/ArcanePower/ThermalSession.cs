using System;
using System.Collections.Generic;
using Sandbox.ModAPI;
using ProtoBuf;
using VRage.Game.Components;

namespace ArcanePower
{
    [ProtoContract]
    public sealed class ThermalRotorPacket
    {
        [ProtoMember(1)] public long EntityId;
        [ProtoMember(2)] public ThermalRotorState State;
        [ProtoMember(3)] public ThermalRadiatorState Radiator;
        [ProtoMember(4)] public ThermalCoolingState Cooling;
    }

    [MySessionComponentDescriptor(MyUpdateOrder.AfterSimulation)]
    public sealed partial class ThermalSession : MySessionComponentBase
    {
        private static readonly Dictionary<long, ThermalBlock> Blocks = new Dictionary<long, ThermalBlock>();
        private static readonly Dictionary<long, ThermalCircuitCache> circuitGraphs = new Dictionary<long, ThermalCircuitCache>();
        private int tick;
        private const ushort RotorChannel = 49375;
        private static bool ready;
        internal static void Add(ThermalBlock block)
        {
            Blocks[block.Entity.EntityId] = block;
            InvalidateCircuits(block.Block.CubeGrid.EntityId);
            if (ready && !MyAPIGateway.Multiplayer.IsServer && HasTelemetry(block)) RequestRotor(block);
        }
        internal static void Remove(ThermalBlock block)
        {
            if (MyAPIGateway.Session != null && MyAPIGateway.Multiplayer.IsServer)
            { block.AccountOutput(); block.OutputGrant = null; block.SetOutput(0); }
            Blocks.Remove(block.Block.EntityId);
            if (block.Block.CubeGrid != null) InvalidateCircuits(block.Block.CubeGrid.EntityId);
        }
        internal static void Remove(Reactor source)
        {
            if (MyAPIGateway.Session != null && MyAPIGateway.Multiplayer.IsServer && source.Motion != null && source.Motion.Thermal != null)
            {
                if (source.ThermalInitialized) source.AccountThermalOutput();
                foreach (var block in Blocks.Values)
                    if (block.OutputGrant != null && block.OutputGrant.Source == source.Motion.Thermal)
                    { block.AccountOutput(); block.OutputGrant = null; block.SetOutput(0); }
            }
            circuitGraphs.Remove(source.Id);
        }

        private static void InvalidateCircuits(long gridId)
        {
            foreach (var entry in circuitGraphs)
                if (entry.Value.Nodes.Exists(node => node.GridId == gridId)) entry.Value.Invalidated = true;
        }

        public override void BeforeStart()
        {
            MyAPIGateway.Multiplayer.RegisterSecureMessageHandler(RotorChannel, ReceiveRotor);
            InitializeFlow();
            ready = true;
            if (!MyAPIGateway.Multiplayer.IsServer)
                foreach (var block in Blocks.Values) if (HasTelemetry(block)) RequestRotor(block);
        }

        private static bool HasTelemetry(ThermalBlock block)
        { return block.Spec.Kind == ThermalKind.Train || block.IsCooling; }

        private static ThermalRotorPacket MotionPacket(ThermalBlock block)
        { return new ThermalRotorPacket { EntityId = block.Entity.EntityId, State = block.Store.Rotor,
            Radiator = block.Store.Radiator, Cooling = block.CaptureCooling() }; }

        private static void RequestRotor(ThermalBlock block)
        {
            MyAPIGateway.Multiplayer.SendMessageToServer(RotorChannel, MyAPIGateway.Utilities.SerializeToBinary(
                new ThermalRotorPacket { EntityId = block.Entity.EntityId }));
        }

        private void ReceiveRotor(ushort channel, byte[] bytes, ulong sender, bool fromServer)
        {
            if (bytes == null || bytes.Length == 0 || bytes.Length > 1024) return;
            try
            {
                var packet = MyAPIGateway.Utilities.SerializeFromBinary<ThermalRotorPacket>(bytes);
                if (packet == null) return;
                MyAPIGateway.Utilities.InvokeOnGameThread(() =>
                {
                    ThermalBlock block;
                    if (!ready || !Blocks.TryGetValue(packet.EntityId, out block) || !HasTelemetry(block)) return;
                    if (MyAPIGateway.Multiplayer.IsServer)
                    {
                        // Clients may ask for a read-only pose; they can never
                        // submit drive, pressure, inventory or speed state.
                        if (fromServer || packet.State != null || packet.Radiator != null || packet.Cooling != null) return;
                        MyAPIGateway.Multiplayer.SendMessageTo(RotorChannel, MyAPIGateway.Utilities.SerializeToBinary(
                            MotionPacket(block)), sender);
                    }
                    else if (fromServer) { block.ReceiveRotor(packet.State); block.ReceiveRadiator(packet.Radiator); block.ReceiveCooling(packet.Cooling); }
                });
            }
            catch (Exception error) { VRage.Utils.MyLog.Default.WriteLine("ArcanePower: ignored invalid rotor packet: " + error.Message); }
        }

        public override void UpdateAfterSimulation()
        {
            if (MyAPIGateway.Session == null) return;
            bool server = MyAPIGateway.Multiplayer.IsServer;
            BeginFlowFrame();
            try { if (server) { LinkRadiators(); AdvancePlant(); } }
            catch (Exception error)
            {
                VRage.Utils.MyLog.Default.WriteLine("ArcanePower: thermal runtime isolated after fault: " + error);
                // Keep outstanding grants to settle the last native interval.
                // Discarding them would falsely fault every turbine next tick.
                foreach (var block in Blocks.Values) { block.SetOutput(0); block.RotorLoad = 0; block.CoolingRejectedMW = 0; }
                foreach (var source in VentSession.All) if (source.ThermalVariant) source.FailThermalRuntime();
            }
            foreach (var block in Blocks.Values)
                if (block.Spec.Kind == ThermalKind.Radiator) block.AdvanceRadiator();
            foreach (var block in Blocks.Values)
            {
                block.AdvanceRotor();
                if (block.Spec.Kind != ThermalKind.Radiator) block.AdvanceRadiator();
                if (server && ready && tick % 30 == 0 && HasTelemetry(block))
                {
                    MyAPIGateway.Multiplayer.SendMessageToOthers(RotorChannel, MyAPIGateway.Utilities.SerializeToBinary(
                        MotionPacket(block)));
                    if (block.IsCooling) block.Block.RefreshCustomInfo();
                }
            }
            UpdateFlow();
            if (++tick % 60 == 0 && server) SaveData();
        }

        private void AdvancePlant()
        {
            var machines = new List<ThermalBlock>(Blocks.Values);
            machines.Sort((a, b) => a.Entity.EntityId.CompareTo(b.Entity.EntityId));
            var sources = new List<Reactor>();
            foreach (var reactor in VentSession.All)
                if (reactor.ThermalInitialized) { sources.Add(reactor); reactor.BeginThermalFrame(); }
            sources.Sort((a, b) => a.Id.CompareTo(b.Id));
            // Settle last interval against its original source/circuit BEFORE
            // topology changes. A split, shutdown or repair cannot skip payment.
            foreach (var machine in machines)
            {
                machine.AccountOutput();
                machine.OutputGrantMW = 0;
                machine.RotorLoad = 0; machine.RotorHotC = 45;
                machine.CoolingRejectedMW = 0;
                machine.CoolingConnected = false; machine.CoolingPowered = true;
            }
            var claimed = new HashSet<long>();
            foreach (var source in sources)
            {
                source.AccountThermalOutput();
                var state = source.Motion.Thermal;
                if (state.Mode == ThermalMode.Standalone)
                {
                    foreach (var loop in state.Loops) loop.Connected = false;
                    state.Efficiency = ThermalMath.StandaloneEfficiency;
                    state.CoolingMW = source.ThermalHeatMW * (1 - ThermalMath.StandaloneEfficiency);
                    state.RejectedMW = ThermalMath.Reject(state.Store, state.CoolingMW / 60, false) * 60;
                    if (!source.ThermalCanRun)
                        state.RejectedMW += ThermalMath.Reject(state.Store,
                            Math.Max(0, state.CoolingMW - state.RejectedMW) / 60, true) * 60;
                    state.Diagnostic = "Standalone / integrated cooling";
                    if (state.Settled && source.ThermalCanRun) state.SupportedMW = source.ThermalHeatMW * ThermalMath.StandaloneEfficiency;
                    source.GrantStandaloneOutput();
                    CaptureInternalFlow(source);
                }
                else
                {
                    AdvanceLoops(source, sources, machines, claimed);
                    if (!source.ThermalCanRun) CoolHousing(source);
                }
                ThermalCircuitCache assembly;
                circuitGraphs.TryGetValue(source.Id, out assembly);
                foreach (var machine in machines)
                    if (machine.SourceId == source.Id && (machine.Block.CubeGrid == source.Block.CubeGrid
                        || (state.Mode == ThermalMode.Brayton && assembly != null
                            && assembly.Nodes.Exists(node => node.Id == machine.Entity.EntityId))))
                        state.AttachedHeatMJ += machine.Store.HotMJ + machine.Store.WasteMJ;
                if (!state.Settled) state.Diagnostic = source.ThermalModeTransitionHint;
                // Forecast only a completed interval: settled production and
                // current circuit cooling/topology must describe the same frame.
                source.UpdateThermalForecast();
            }
            foreach (var machine in machines)
            {
                // Unattached old radiator inventories can still radiate locally.
                // New operation stores no heat in machinery or pipe blocks.
                if (!claimed.Contains(machine.Entity.EntityId) && machine.Healthy
                    && (machine.Spec.Kind == ThermalKind.Radiator || machine.Spec.Kind == ThermalKind.HullRadiator))
                {
                    double capacity = machine.Unit().CoolingMW / 60;
                    double rejected = ThermalMath.Reject(machine.Store, capacity, false);
                    rejected += ThermalMath.Reject(machine.Store, capacity - rejected, true);
                    machine.CoolingRejectedMW = rejected * 60;
                }
                machine.SetOutput(machine.Healthy ? machine.OutputGrantMW : 0);
            }
        }

        private static void CoolHousing(Reactor source)
        {
            var state = source.Motion.Thermal;
            double budget = source.ThermalHeatMW * .02 / 60;
            double rejected = ThermalMath.Reject(state.Store, budget, false);
            rejected += ThermalMath.Reject(state.Store, budget - rejected, true);
            foreach (var loop in state.Loops)
            {
                double amount = Math.Min(loop.ExcessMJ, Math.Max(0, budget - rejected));
                loop.ExcessMJ -= amount; loop.RejectedMW += amount * 60; rejected += amount;
            }
            state.RejectedMW += rejected * 60;
        }

        public override VRage.Game.MyObjectBuilder_SessionComponent GetObjectBuilder() { SaveData(); return base.GetObjectBuilder(); }
        public override void SaveData() { foreach (var block in Blocks.Values) block.Save(); }
        protected override void UnloadData()
        {
            if (ready) MyAPIGateway.Multiplayer.UnregisterSecureMessageHandler(RotorChannel, ReceiveRotor);
            UnloadFlow();
            ThermalPipeJoint.Unload();
            ready = false;
            Blocks.Clear(); circuitGraphs.Clear();
        }
    }
}
