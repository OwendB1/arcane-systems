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
            if (ready && !MyAPIGateway.Multiplayer.IsServer && HasMotion(block)) RequestRotor(block);
        }
        internal static void Remove(ThermalBlock block)
        {
            Blocks.Remove(block.Entity.EntityId);
            InvalidateCircuits(block.Block.CubeGrid.EntityId);
        }
        internal static void Remove(Reactor source) { circuitGraphs.Remove(source.Id); }

        private static void InvalidateCircuits(long gridId)
        {
            var stale = new List<long>();
            foreach (var entry in circuitGraphs)
                if (entry.Value.Nodes[0].GridId == gridId) stale.Add(entry.Key);
            foreach (long id in stale) circuitGraphs.Remove(id);
        }

        public override void BeforeStart()
        {
            MyAPIGateway.Multiplayer.RegisterSecureMessageHandler(RotorChannel, ReceiveRotor);
            InitializeFlow();
            ready = true;
            if (!MyAPIGateway.Multiplayer.IsServer)
                foreach (var block in Blocks.Values) if (HasMotion(block)) RequestRotor(block);
        }

        private static bool HasMotion(ThermalBlock block)
        { return block.Spec.Kind == ThermalKind.Train || block.IsRadiator; }

        private static ThermalRotorPacket MotionPacket(ThermalBlock block)
        { return new ThermalRotorPacket { EntityId = block.Entity.EntityId, State = block.Store.Rotor, Radiator = block.Store.Radiator }; }

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
                    if (!ready || !Blocks.TryGetValue(packet.EntityId, out block) || !HasMotion(block)) return;
                    if (MyAPIGateway.Multiplayer.IsServer)
                    {
                        // Clients may ask for a read-only pose; they can never
                        // submit drive, pressure, inventory or speed state.
                        if (fromServer || packet.State != null || packet.Radiator != null) return;
                        MyAPIGateway.Multiplayer.SendMessageTo(RotorChannel, MyAPIGateway.Utilities.SerializeToBinary(
                            MotionPacket(block)), sender);
                    }
                    else if (fromServer) { block.ReceiveRotor(packet.State); block.ReceiveRadiator(packet.Radiator); }
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
                foreach (var block in Blocks.Values) { block.SetOutput(0); block.StopStartup(); block.RotorCirculation = 0; block.RadiatorRejectedMW = 0; }
                foreach (var source in VentSession.All) if (source.ThermalVariant) source.FailThermalRuntime();
            }
            foreach (var block in Blocks.Values)
                if (block.Spec.Kind == ThermalKind.Radiator) block.AdvanceRadiator();
            foreach (var block in Blocks.Values)
            {
                block.AdvanceRotor();
                if (block.Spec.Kind != ThermalKind.Radiator) block.AdvanceRadiator();
                if (server && ready && tick % 30 == 0 && HasMotion(block))
                    MyAPIGateway.Multiplayer.SendMessageToOthers(RotorChannel, MyAPIGateway.Utilities.SerializeToBinary(
                        MotionPacket(block)));
            }
            UpdateFlow();
            if (++tick % 60 == 0 && server) SaveData();
        }

        private void AdvancePlant()
        {
            var machines = new List<ThermalBlock>(Blocks.Values);
            machines.Sort((a, b) => a.Entity.EntityId.CompareTo(b.Entity.EntityId));
            // Pay for the last native distribution interval before changing any
            // topology or output grant. A split cannot skip that withdrawal.
            foreach (var machine in machines)
            {
                machine.AccountOutput();
                machine.AccountStartup();
                machine.OutputGrantMW = 0;
                machine.RotorCirculation = 0;
                machine.RotorHotC = 45;
                machine.RadiatorRejectedMW = 0;
                if (machine.Healthy)
                {
                    var unit = machine.Unit();
                    if (unit.CoolingMW > 0 && machine.Spec.Kind == ThermalKind.Radiator)
                    {
                        double capacity = unit.CoolingMW / 60;
                        double rejected = ThermalMath.Reject(machine.Store, capacity, false);
                        rejected += ThermalMath.Reject(machine.Store, capacity - rejected, true);
                        machine.RadiatorRejectedMW = rejected * 60;
                    }
                }
            }
            var sources = new List<Reactor>();
            foreach (var reactor in VentSession.All) if (reactor.ThermalVariant) sources.Add(reactor);
            sources.Sort((a, b) => a.Id.CompareTo(b.Id));
            var claimed = new HashSet<long>();
            var startupHosts = new HashSet<long>();
            foreach (var source in sources)
            {
                if (!source.ThermalInitialized) continue;
                source.AccountThermalOutput();
                var state = source.Motion.Thermal;
                state.NetOutputMW = source.Block.CurrentOutput; state.StartupMW = 0;
                state.AttachedHeatMJ = 0;
                foreach (var machine in machines)
                {
                    if (machine.SourceId == source.Id && machine.Generator != null) state.NetOutputMW += machine.Generator.CurrentOutput;
                    if (machine.StartupOwner == source.Id) state.StartupMW += machine.StartupInputMW;
                    if (machine.SourceId == source.Id && machine.Block.CubeGrid == source.Block.CubeGrid)
                        state.AttachedHeatMJ += machine.Store.HotMJ + machine.Store.WasteMJ;
                }
                state.ProducedMW = 0; state.SupportedMW = 0;
                state.CoolingMW = state.RequiredCoolingMW = 0;
                state.DutyTrains = state.StandbyTrains = 0;
                if (state.Mode == ThermalMode.Standalone)
                {
                    if (state.ConnectedLoops > 0) state.Loops = ThermalLoops.Empty();
                    state.Efficiency = .20;
                    state.RejectedMW = ThermalMath.Reject(state.Store, source.ThermalHeatMW * .8 / 60, false) * 60;
                    // Integrated rejection also drains paid hot inventory on a
                    // cold shutdown; it never exports that energy as electricity.
                    if (!source.ThermalCanRun)
                        state.RejectedMW += ThermalMath.Reject(state.Store, source.ThermalHeatMW * .8 / 60, true) * 60;
                    state.Diagnostic = "Standalone / integrated cooling";
                    if (state.Settled && source.ThermalCanRun)
                    { state.SupportedMW = source.ThermalHeatMW * .20; source.ProduceThermal(source.ThermalHeatMW); }
                    CaptureInternalFlow(source);
                    continue;
                }
                // Emergency passive housing rejection is deliberately small.
                // Lost cooling preserves the remaining hot inventory and never
                // silently enables the standalone electrical conversion path.
                state.RejectedMW = 0;
                if (!source.ThermalCanRun)
                {
                    double budget = source.ThermalHeatMW * .02 / 60;
                    double rejected = ThermalMath.Reject(state.Store, budget, false);
                    rejected += ThermalMath.Reject(state.Store, budget - rejected, true);
                    state.RejectedMW = rejected * 60;
                }
                AdvanceLoops(source, sources, machines, claimed, startupHosts);
            }
            foreach (var source in sources)
                if (source.ThermalInitialized && !source.Motion.Thermal.Settled)
                    source.Motion.Thermal.Diagnostic = source.ThermalModeTransitionHint;
            foreach (var machine in machines)
            {
                if (!startupHosts.Contains(machine.Entity.EntityId)) machine.StopStartup();
                machine.SetOutput(machine.Healthy ? machine.OutputGrantMW : 0);
            }
        }

        public override VRage.Game.MyObjectBuilder_SessionComponent GetObjectBuilder() { SaveData(); return base.GetObjectBuilder(); }
        public override void SaveData() { foreach (var block in Blocks.Values) block.Save(); }
        protected override void UnloadData()
        {
            if (ready) MyAPIGateway.Multiplayer.UnregisterSecureMessageHandler(RotorChannel, ReceiveRotor);
            UnloadFlow();
            ready = false;
            Blocks.Clear(); circuitGraphs.Clear();
        }
    }
}
