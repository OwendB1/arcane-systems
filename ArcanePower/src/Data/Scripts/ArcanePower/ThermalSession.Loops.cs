using System;
using System.Collections.Generic;

namespace ArcanePower
{
    public sealed partial class ThermalSession
    {
        private void AdvanceLoops(Reactor source, List<Reactor> sources, List<ThermalBlock> machines,
            HashSet<long> claimed, HashSet<long> startupHosts)
        {
            var state = source.Motion.Thermal;
            bool running = source.ThermalCanRun;
            var endpoints = new List<ThermalEndpoint> { source.ThermalEndpoint() };
            foreach (var machine in machines)
                if (!machine.Block.Closed && machine.Block.CubeGrid == source.Block.CubeGrid)
                    endpoints.Add(machine.Endpoint(source.Block.OwnerId));
            foreach (var other in sources)
                if (other != source && other.ThermalInitialized && other.Block.CubeGrid == source.Block.CubeGrid)
                    endpoints.Add(other.ThermalEndpoint());
            ThermalCircuitCache graph;
            if (!circuitGraphs.TryGetValue(source.Id, out graph) || !graph.Matches(endpoints))
                circuitGraphs[source.Id] = graph = new ThermalCircuitCache(endpoints);
            endpoints = graph.Nodes;
            var network = graph.Network;
            var circuits = graph.Circuits;
            double allocation = ThermalLoops.Allocation(source.ThermalHeatMW);
            double freshMW = 0, availableHeatMW = 0;
            for (int index = 0; index < circuits.Length; index++)
            {
                var circuit = circuits[index];
                var loop = state.Loops[index];
                loop.HeatMW = loop.NetMW = loop.CoolingMW = loop.RequiredCoolingMW = 0;
                loop.Connected = circuit.Ready;
                loop.Diagnostic = circuit.Diagnostic ?? "Circuit ready";
                var bank = new List<ThermalBlock>();
                var units = new List<ThermalUnit>();
                ThermalBlock host = null;
                if (circuit.Ready)
                    foreach (var endpoint in circuit.Nodes)
                    {
                        ThermalBlock machine;
                        if (!Blocks.TryGetValue(endpoint.Id, out machine)) continue;
                        if (claimed.Contains(endpoint.Id))
                        { loop.Connected = false; loop.Diagnostic = "Circuit machinery is allocated to another source"; break; }
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
                { claimed.Add(machine.Entity.EntityId); machine.SourceId = source.Id; }
                bool hasHeat = state.Store.HotMJ + state.Store.WasteMJ > .001;
                foreach (var machine in bank) hasHeat |= machine.Store.HotMJ + machine.Store.WasteMJ > .001;
                double delivered = 0;
                bool needsPump = (running && host.Store.HotMJ <= .001) || (!running && hasHeat);
                // Bootstrap a cold turbine and keep hot shutdown circulation
                // powered. Running auxiliaries are already paid by conversion.
                if (needsPump)
                {
                    delivered = host.RequestStartup(source.Id, plan.AcceptedMW * .02);
                    startupHosts.Add(host.Entity.EntityId);
                }
                double net = host.Generator == null ? 0 : host.Generator.CurrentOutput;
                double circulation = ThermalMath.CirculationPower(net, plan.Efficiency, delivered, plan.AcceptedMW);
                host.RotorCirculation = circulation; host.RotorHotC = source.ThermalHotC;
                state.RejectedMW += DrainLoop(source, bank, allocation * circulation / 60, circulation);
                loop.CoolingMW = plan.CoolingMW * circulation;
                state.CoolingMW += loop.CoolingMW;
                loop.HeatMW = plan.AcceptedMW;
                loop.NetMW = plan.NetMW;
                loop.RequiredCoolingMW = plan.RequiredCoolingMW * source.Motion.PowerRamp;
                loop.Diagnostic = circulation <= 0 && needsPump
                    ? (running ? "Waiting for compressor power" : "Cooldown waiting for circulation power") : plan.Limit;
                state.SupportedMW += loop.NetMW;
                state.RequiredCoolingMW += loop.RequiredCoolingMW;
                availableHeatMW += loop.HeatMW;
                host.Efficiency = plan.Efficiency;
                if (running)
                {
                    ThermalMath.Transfer(state.Store, host.Store, host.Spec.CapacityMJ,
                        plan.AcceptedMW * circulation / 60, false);
                    host.OutputGrantMW = ThermalMath.ExportLimit(host.Store, host.Spec.CapacityMJ, plan.Efficiency,
                        plan.NetMW * source.Motion.PowerRamp, 1.0 / 60);
                    freshMW += plan.AcceptedMW * circulation;
                }
                // Restrict flow tracing to this circuit. Keeping the full root
                // port array preserves the existing four-port network packet.
                if (captureFlow)
                    CapturePlantFlow(source, new ThermalNetwork(circuit.Nodes), circuit.Nodes, bank, plan, circulation);
            }
            // Checked, sealed circuits open even while cold or off.
            CaptureIsolation(network, endpoints, ThermalLoops.OpenValves(state));
            int active = state.ConnectedLoops;
            state.DutyTrains = active;
            state.Efficiency = availableHeatMW > 0 ? state.SupportedMW / availableHeatMW : 0;
            source.CheckLoopSafety();
            source.ProduceThermal(freshMW);
            state.Diagnostic = state.LoopTrip && !source.Block.Enabled
                ? "Startup blocked: all four circuits defective; repair at least one and restart manually"
                : active + "/4 circuits ready / " + (active * 25) + "% maximum reactor allocation";
        }

        private static double DrainLoop(Reactor source, List<ThermalBlock> bank, double coreBudgetMJ, double circulation)
        {
            var state = source.Motion.Thermal;
            double rejectedMJ = 0;
            foreach (var machine in bank)
            {
                if (machine.Spec.Kind == ThermalKind.Radiator) rejectedMJ += machine.RadiatorRejectedMW / 60;
                if (machine.Spec.Kind != ThermalKind.AirCooler) continue;
                double budget = machine.Unit().CoolingMW * circulation / 60;
                double rejected = ThermalMath.Reject(machine.Store, budget, false);
                rejected += ThermalMath.Reject(machine.Store, budget - rejected, true);
                rejectedMJ += rejected;
            }
            foreach (var sender in bank)
                if (sender.Spec.Kind == ThermalKind.Train)
                    ThermalMath.Transfer(sender.Store, state.Store, source.ThermalHeatMW * 8,
                        sender.Spec.RatingMW * circulation / 60, true);
            foreach (var cooler in bank)
            {
                if (cooler.Unit().CoolingMW <= 0) continue;
                double flow = cooler.EffectiveRatingMW * circulation / 60;
                double coreFlow = Math.Min(flow, coreBudgetMJ);
                double moved = ThermalMath.Transfer(state.Store, cooler.Store, cooler.Spec.CapacityMJ, coreFlow, true);
                if (!source.ThermalCanRun)
                    moved += ThermalMath.Transfer(state.Store, cooler.Store, cooler.Spec.CapacityMJ, coreFlow - moved, false);
                coreBudgetMJ -= moved; flow -= moved;
                foreach (var sender in bank)
                {
                    if (sender == cooler || flow <= 0) continue;
                    double budget = Math.Min(sender.Spec.RatingMW * circulation / 60, flow);
                    double transfer = ThermalMath.Transfer(sender.Store, cooler.Store, cooler.Spec.CapacityMJ, budget, true);
                    if (!source.ThermalCanRun)
                        transfer += ThermalMath.Transfer(sender.Store, cooler.Store, cooler.Spec.CapacityMJ, budget - transfer, false);
                    flow -= transfer;
                }
            }
            return rejectedMJ * 60;
        }
    }
}
