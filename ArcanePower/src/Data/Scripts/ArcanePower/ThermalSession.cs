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
    }

    [MySessionComponentDescriptor(MyUpdateOrder.AfterSimulation)]
    public sealed partial class ThermalSession : MySessionComponentBase
    {
        private static readonly Dictionary<long, ThermalBlock> Blocks = new Dictionary<long, ThermalBlock>();
        private readonly Dictionary<long, BankStart> starts = new Dictionary<long, BankStart>();
        private int tick;
        private const ushort RotorChannel = 49375;
        private static bool ready;
        private sealed class BankStart
        {
            internal string Signature;
            internal double Seconds;
        }

        internal static void Add(ThermalBlock block)
        {
            Blocks[block.Entity.EntityId] = block;
            if (ready && !MyAPIGateway.Multiplayer.IsServer && block.Spec.Kind == ThermalKind.Train) RequestRotor(block);
        }
        internal static void Remove(ThermalBlock block) { Blocks.Remove(block.Entity.EntityId); }

        public override void BeforeStart()
        {
            MyAPIGateway.Multiplayer.RegisterSecureMessageHandler(RotorChannel, ReceiveRotor);
            InitializeFlow();
            ready = true;
            if (!MyAPIGateway.Multiplayer.IsServer)
                foreach (var block in Blocks.Values) if (block.Spec.Kind == ThermalKind.Train) RequestRotor(block);
        }

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
                    if (!ready || !Blocks.TryGetValue(packet.EntityId, out block) || block.Spec.Kind != ThermalKind.Train) return;
                    if (MyAPIGateway.Multiplayer.IsServer)
                    {
                        // Clients may ask for a read-only pose; they can never
                        // submit drive, pressure, inventory or speed state.
                        if (fromServer || packet.State != null) return;
                        MyAPIGateway.Multiplayer.SendMessageTo(RotorChannel, MyAPIGateway.Utilities.SerializeToBinary(
                            new ThermalRotorPacket { EntityId = packet.EntityId, State = block.Store.Rotor }), sender);
                    }
                    else if (fromServer) block.ReceiveRotor(packet.State);
                });
            }
            catch (Exception error) { VRage.Utils.MyLog.Default.WriteLine("ArcanePower: ignored invalid rotor packet: " + error.Message); }
        }

        public override void UpdateAfterSimulation()
        {
            if (MyAPIGateway.Session == null) return;
            bool server = MyAPIGateway.Multiplayer.IsServer;
            BeginFlowFrame();
            try { if (server) AdvancePlant(); }
            catch (Exception error)
            {
                VRage.Utils.MyLog.Default.WriteLine("ArcanePower: thermal runtime isolated after fault: " + error);
                foreach (var block in Blocks.Values) { block.SetOutput(0); block.StopStartup(); block.RotorCirculation = 0; }
                foreach (var source in VentSession.All) if (source.ThermalVariant) source.FailThermalRuntime();
            }
            foreach (var block in Blocks.Values)
            {
                block.AdvanceRotor();
                if (server && ready && tick % 30 == 0 && block.Spec.Kind == ThermalKind.Train)
                    MyAPIGateway.Multiplayer.SendMessageToOthers(RotorChannel, MyAPIGateway.Utilities.SerializeToBinary(
                        new ThermalRotorPacket { EntityId = block.Entity.EntityId, State = block.Store.Rotor }));
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
                if (machine.Healthy)
                {
                    var unit = machine.Unit();
                    if (unit.CoolingMW > 0 && machine.Spec.Kind == ThermalKind.Radiator)
                    {
                        double capacity = unit.CoolingMW / 60;
                        capacity -= ThermalMath.Reject(machine.Store, capacity, false);
                        ThermalMath.Reject(machine.Store, capacity, true);
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
                state.RecoveryRatio = 0;
                state.DutyTrains = state.StandbyTrains = 0;
                if (state.Mode == ThermalMode.Standalone)
                {
                    starts.Remove(source.Id);
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
                state.RejectedMW = ThermalMath.Reject(state.Store, source.ThermalHeatMW * .02 / 60, false) * 60;
                if (!source.ThermalCanRun)
                    state.RejectedMW += ThermalMath.Reject(state.Store, source.ThermalHeatMW * .02 / 60, true) * 60;
                var endpoints = new List<ThermalEndpoint> { source.ThermalEndpoint() };
                foreach (var machine in machines)
                    if (!machine.Block.Closed && machine.Block.CubeGrid == source.Block.CubeGrid)
                        endpoints.Add(machine.Endpoint(source.Block.OwnerId));
                // Include other thermal sources so a shared supply is rejected,
                // rather than awarding the same machinery to multiple reactors.
                foreach (var other in sources)
                    if (other != source && other.ThermalInitialized && other.Block.CubeGrid == source.Block.CubeGrid)
                        endpoints.Add(other.ThermalEndpoint());
                var network = new ThermalNetwork(endpoints);
                var connections = network.Plant(endpoints[0]);
                if (!connections.Ready)
                { state.Diagnostic = connections.Diagnostic; starts.Remove(source.Id); continue; }
                var bank = new List<ThermalBlock>();
                bool shared = false;
                foreach (var endpoint in connections.Nodes)
                {
                    ThermalBlock machine;
                    if (!Blocks.TryGetValue(endpoint.Id, out machine)) continue;
                    if (claimed.Contains(endpoint.Id)) shared = true;
                    bank.Add(machine);
                }
                if (shared) { state.Diagnostic = "Thermal hardware is already allocated to another source"; starts.Remove(source.Id); continue; }
                foreach (var machine in bank) { claimed.Add(machine.Entity.EntityId); machine.SourceId = source.Id; }
                var units = new List<ThermalUnit>();
                foreach (var machine in bank) units.Add(machine.Unit());
                var plan = ThermalMath.Dispatch(source.ThermalHeatMW, source.ThermalHotC, units);
                state.Efficiency = plan.Efficiency; state.SupportedMW = plan.NetMW;
                state.RecoveryRatio = plan.RecoveryRatio;
                state.DutyTrains = plan.Trains.Count; state.StandbyTrains = plan.Standby;
                state.Diagnostic = plan.Limit;
                ThermalBlock host = null;
                foreach (var machine in bank)
                    if (plan.Heaters.Contains(machine.Entity.EntityId) && (host == null || machine.Entity.EntityId < host.Entity.EntityId)) host = machine;
                if (host != null && !source.ThermalCanRun && state.AttachedHeatMJ > .001)
                {
                    host.RequestStartup(source.Id, plan.DesignMW * .02);
                    startupHosts.Add(host.Entity.EntityId);
                }
                double circulation = ThermalMath.CirculationPower(state.NetOutputMW,
                    host != null && host.StartupOwner == source.Id ? host.StartupInputMW : 0, plan.DesignMW);
                CapturePlantFlow(source, network, endpoints, bank, plan, circulation);
                foreach (var cooler in bank)
                {
                    if (cooler.Spec.Kind != ThermalKind.AirCooler) continue;
                    double capacity = cooler.Unit().CoolingMW * circulation / 60;
                    capacity -= ThermalMath.Reject(cooler.Store, capacity, false);
                    ThermalMath.Reject(cooler.Store, capacity, true);
                }
                // Drain every reachable machine, including idle/standby hot
                // inventory, before admitting new reaction heat.
                var coolerFlow = new Dictionary<long, double>();
                foreach (var cooler in bank)
                    if (cooler.Unit().CoolingMW > 0) coolerFlow[cooler.Entity.EntityId] = cooler.Spec.RatingMW * circulation / 60;
                foreach (var sender in bank)
                    foreach (var cooler in bank)
                    {
                        var unit = cooler.Unit();
                        if (sender == cooler || unit.CoolingMW <= 0) continue;
                        double flow = Math.Min(sender.Spec.RatingMW / 60, coolerFlow[cooler.Entity.EntityId]);
                        double budget = flow;
                        flow -= ThermalMath.Transfer(sender.Store, cooler.Store, cooler.Spec.CapacityMJ, flow, true);
                        if (!source.ThermalCanRun || (sender.Spec.Kind == ThermalKind.Train
                            && !plan.Trains.Exists(t => t.Id == sender.Entity.EntityId)))
                            flow -= ThermalMath.Transfer(sender.Store, cooler.Store, cooler.Spec.CapacityMJ, flow, false);
                        coolerFlow[cooler.Entity.EntityId] -= budget - flow;
                    }
                if (!source.ThermalCanRun || !state.Settled || plan.AcceptedMW <= 0)
                { starts.Remove(source.Id); continue; }
                foreach (var selected in plan.Trains)
                {
                    ThermalBlock train;
                    if (Blocks.TryGetValue(selected.Id, out train))
                    { train.RotorCirculation = circulation; train.RotorHotC = source.ThermalHotC; }
                }
                if (host == null) continue;
                var ids = new List<long>();
                foreach (var machine in bank) ids.Add(machine.Entity.EntityId);
                ids.Sort();
                string signature = source.Block.CubeGrid.EntityId + ":" + string.Join(",", ids)
                    + ":" + string.Join(",", plan.Trains.ConvertAll(t => t.Id));
                BankStart startup;
                if (!starts.TryGetValue(source.Id, out startup) || startup.Signature != signature)
                    starts[source.Id] = startup = new BankStart { Signature = signature };
                if (startup.Seconds < 8)
                {
                    double demand = plan.DesignMW * .02;
                    double delivered = host.RequestStartup(source.Id, demand);
                    startupHosts.Add(host.Entity.EntityId);
                    // AccountStartup already stored all delivered electricity
                    // as heat, including the last interval after cancellation.
                    startup.Seconds = ThermalMath.StartupSeconds(startup.Seconds, demand, delivered, 1.0 / 60);
                    // The reactor synthesizes its own sealed CO2 working charge.
                    // This paid phase includes filling, compression and cooling;
                    // reload or a changed bank requires a new commissioning pass.
                    state.Diagnostic = "Internal CO2 generation / loop pressurization: " + startup.Seconds.ToString("0.0") + " / 8 s of delivered grid power";
                    continue;
                }
                bool warmTrain = false;
                foreach (var selected in plan.Trains)
                {
                    ThermalBlock candidate;
                    if (Blocks.TryGetValue(selected.Id, out candidate) && candidate.Store.HotMJ > .001) warmTrain = true;
                }
                if (!warmTrain)
                {
                    // Keep the paid circulation alive long enough for the first
                    // heat packet to reach a train. Afterwards stored heat can
                    // meet new electrical demand without an idle grid load.
                    host.RequestStartup(source.Id, plan.DesignMW * .02);
                    startupHosts.Add(host.Entity.EntityId);
                }
                if (circulation <= 0) state.Diagnostic = "Circulation unpowered; paid heat retained / external power required for a cold train";
                var heaterFlow = new Dictionary<long, double>();
                foreach (var machine in bank)
                    if (plan.Heaters.Contains(machine.Entity.EntityId)) heaterFlow[machine.Entity.EntityId] = machine.Spec.RatingMW / 60;
                foreach (var selected in plan.Trains)
                {
                    ThermalBlock train;
                    if (!Blocks.TryGetValue(selected.Id, out train)) continue;
                    train.Efficiency = plan.Efficiency;
                    train.SourceId = source.Id;
                    double share = selected.RatingMW / plan.DesignMW;
                    // Every admission is bounded by the receiver's free store.
                    // Pipes are ideal pass-through links in this prototype;
                    // all MJ reside on real source/machine entities, never on
                    // a second, duplicated aggregate network reservoir.
                    double remaining = plan.AcceptedMW * share * circulation / 60;
                    foreach (var heater in bank)
                    {
                        if (!heaterFlow.ContainsKey(heater.Entity.EntityId)) continue;
                        double flow = Math.Min(heaterFlow[heater.Entity.EntityId], remaining);
                        ThermalMath.Transfer(state.Store, heater.Store, heater.Spec.CapacityMJ, flow, false);
                        double passed = ThermalMath.Transfer(heater.Store, train.Store, train.Spec.CapacityMJ, flow, false);
                        remaining -= passed;
                        heaterFlow[heater.Entity.EntityId] -= flow;
                    }
                    train.OutputGrantMW = ThermalMath.ExportLimit(train.Store, train.Spec.CapacityMJ, plan.Efficiency,
                        plan.NetMW * share * source.Motion.PowerRamp, 1.0 / 60);
                }
                source.ProduceThermal(plan.AcceptedMW * circulation);
            }
            foreach (var machine in machines)
            {
                if (!startupHosts.Contains(machine.Entity.EntityId)) machine.StopStartup();
                machine.SetOutput(machine.Healthy ? machine.OutputGrantMW : 0);
            }
            var active = new HashSet<long>();
            foreach (var source in sources) active.Add(source.Id);
            foreach (long id in new List<long>(starts.Keys)) if (!active.Contains(id)) starts.Remove(id);
        }

        public override VRage.Game.MyObjectBuilder_SessionComponent GetObjectBuilder() { SaveData(); return base.GetObjectBuilder(); }
        public override void SaveData() { foreach (var block in Blocks.Values) block.Save(); }
        protected override void UnloadData()
        {
            if (ready) MyAPIGateway.Multiplayer.UnregisterSecureMessageHandler(RotorChannel, ReceiveRotor);
            UnloadFlow();
            ready = false;
            Blocks.Clear(); starts.Clear();
        }
    }
}
