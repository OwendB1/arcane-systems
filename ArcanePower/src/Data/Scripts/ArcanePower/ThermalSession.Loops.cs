using System;
using System.Collections.Generic;

namespace ArcanePower
{
    public sealed partial class ThermalSession
    {
        private void AdvanceLoops(Reactor source, List<Reactor> sources, List<ThermalBlock> machines,
            HashSet<long> claimed)
        {
            var state = source.Motion.Thermal;
            if (state.Faulted) source.StopForLoopLoss();
            bool running = source.ThermalCanRun;
            var endpoints = new List<ThermalEndpoint> { source.ThermalEndpoint() };
            foreach (var machine in machines)
                if (!machine.Block.Closed && machine.Block.CubeGrid == source.Block.CubeGrid)
                    endpoints.Add(machine.Endpoint(source.Block.OwnerId));
            foreach (var other in sources)
                if (other != source && other.ThermalInitialized && other.Block.CubeGrid == source.Block.CubeGrid)
                    endpoints.Add(other.ThermalEndpoint());
            ThermalCircuitCache graph;
            bool rebuilt = !circuitGraphs.TryGetValue(source.Id, out graph) || !graph.Matches(endpoints);
            var previous = graph;
            if (rebuilt)
                circuitGraphs[source.Id] = graph = new ThermalCircuitCache(endpoints);
            endpoints = graph.Nodes;
            var network = graph.Network;
            var circuits = graph.Circuits;
            // Fault flags are runtime results, not topology inputs. Retry only
            // when this circuit's physical members changed (or on first load),
            // so a recurring accounting fault cannot reset itself every tick.
            if (rebuilt)
                for (int index = 0; index < circuits.Length; index++)
                    if (circuits[index].Ready && graph.CircuitChanged(previous, index))
                    {
                        source.RecheckThermalFault();
                        foreach (var endpoint in circuits[index].Nodes)
                        {
                            ThermalBlock machine;
                            if (!Blocks.TryGetValue(endpoint.Id, out machine)) continue;
                            machine.RecheckCircuitFault();
                            foreach (var panel in machine.RadiatorPanels) panel.RecheckCircuitFault();
                        }
                    }
            double allocation = ThermalLoops.Allocation(source.ThermalHeatMW);
            double availableHeatMW = 0;
            for (int index = 0; index < circuits.Length; index++)
            {
                var circuit = circuits[index];
                var loop = state.Loops[index];
                loop.NetMW = loop.CoolingMW = loop.PotentialCoolingMW = 0;
                loop.Connected = circuit.Ready;
                loop.Diagnostic = circuit.Diagnostic ?? "Circuit ready";
                var bank = new List<ThermalBlock>();
                var units = new List<ThermalUnit>();
                ThermalBlock host = null;
                if (loop.Connected)
                    foreach (var endpoint in circuit.Nodes)
                    {
                        ThermalBlock machine;
                        if (!Blocks.TryGetValue(endpoint.Id, out machine)) continue;
                        if (claimed.Contains(endpoint.Id))
                        { loop.Connected = false; loop.Diagnostic = "Circuit machinery is allocated to another source"; break; }
                        if (machine.Fault != null)
                        { loop.Connected = false; loop.Diagnostic = machine.Spec.Kind + " fault: " + machine.Fault; break; }
                        foreach (var panel in machine.RadiatorPanels)
                            if (panel.Fault != null)
                            { loop.Connected = false; loop.Diagnostic = "Radiator panel fault: " + panel.Fault; break; }
                        if (!loop.Connected) break;
                        bank.Add(machine); units.Add(machine.Unit());
                        foreach (var panel in machine.RadiatorPanels) units.Add(panel.Unit());
                        if (machine.Spec.Kind == ThermalKind.Train) host = machine;
                    }
                var plan = ThermalMath.Dispatch(allocation, source.ThermalHotC, units);
                if (!loop.Connected || host == null || plan.AcceptedMW <= 0)
                {
                    if (loop.Connected) loop.Diagnostic = plan.Limit;
                    loop.Connected = false;
                    continue;
                }
                foreach (var machine in bank)
                {
                    claimed.Add(machine.Entity.EntityId); machine.SourceId = source.Id;
                    // Once attached, fold old distributed inventories into this
                    // circuit. Clearing the old store makes migration idempotent.
                    MigrateMachineHeat(machine, loop);
                    foreach (var panel in machine.RadiatorPanels) MigrateMachineHeat(panel, loop);
                }
                loop.NetMW = plan.NetMW;
                state.SupportedMW += loop.NetMW;
                availableHeatMW += plan.AcceptedMW;
                host.RotorLoad = plan.NetMW > 0 ? ThermalMath.Clamp(loop.OutputMW / plan.NetMW, 0, 1) : 0;
                host.RotorHotC = source.ThermalHotC;
                // Environmental capacity never depends on electrical load.
                // Turbine auxiliaries are included in net efficiency. During
                // cooldown the existing containment supply supports active fans.
                foreach (var cooler in bank)
                {
                    bool air = cooler.Spec.Kind == ThermalKind.AirCooler;
                    if (!air && cooler.Spec.Kind != ThermalKind.Radiator) continue;
                    cooler.CoolingConnected = true;
                    cooler.CoolingPowered = !air || source.ThermalAuxiliaryReady;
                    double potential = cooler.Unit().CoolingMW;
                    loop.PotentialCoolingMW += potential;
                    if (cooler.CoolingPowered) loop.CoolingMW += potential;
                }
                double rejected = ThermalMath.CoolCircuit(loop, loop.CoolingMW);
                state.CoolingMW += loop.CoolingMW;
                state.RejectedMW += rejected;
                foreach (var cooler in bank)
                    if (cooler.CoolingConnected && cooler.CoolingPowered)
                        cooler.CoolingRejectedMW = loop.CoolingMW > 0
                            ? rejected * cooler.Unit().CoolingMW / loop.CoolingMW : 0;
                loop.Diagnostic = loop.CoolingMW <= 0 && bank.Exists(machine => machine.Spec.Kind == ThermalKind.AirCooler && !machine.CoolingPowered)
                    ? "Active coolers waiting for reactor auxiliary power"
                    : loop.CoolingMW + .001 < loop.RequiredCoolingMW
                    ? "Cooling below output; cooling backlog is accumulating"
                    : loop.CoolingMW + .001 < loop.NetMW
                    ? "Ready at current load; cooling below maximum output" : plan.Limit;
                if (running)
                {
                    host.OutputGrant = source.ReserveThermalOutput(loop, plan.AcceptedMW, plan.Efficiency);
                    host.OutputGrantMW = host.OutputGrant == null ? 0 : host.OutputGrant.MaximumMW;
                }
                if (captureFlow)
                    CapturePlantFlow(source, new ThermalNetwork(circuit.Nodes), circuit.Nodes, bank, plan, Math.Max(host.RotorLoad, rejected > .001 ? .1 : 0));
            }
            // Checked, sealed circuits open even while cold or off.
            CaptureIsolation(network, endpoints, ThermalLoops.OpenValves(state));
            int active = state.ConnectedLoops;
            if (rebuilt && active > 0) state.LoopTrip = false;
            state.DutyTrains = active;
            state.Efficiency = availableHeatMW > 0 ? state.SupportedMW / availableHeatMW : 0;
            source.CheckLoopSafety();
            if (!state.Faulted)
                state.Diagnostic = active == 0
                    ? (state.LoopTrip ? "Startup blocked / " : "0/4 circuits ready / ") + state.Loops[0].Diagnostic
                    : active + "/4 circuits ready / " + (active * 25) + "% maximum reactor allocation";
        }

        private static void MigrateMachineHeat(ThermalBlock machine, ThermalLoopState loop)
        {
            loop.ExcessMJ += machine.Store.HotMJ + machine.Store.WasteMJ;
            machine.Store.HotMJ = machine.Store.WasteMJ = 0;
        }
    }
}
