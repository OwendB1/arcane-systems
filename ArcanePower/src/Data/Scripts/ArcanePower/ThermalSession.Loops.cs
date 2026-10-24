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
            int previous = state.AvailableLoops;
            bool running = source.ThermalCanRun;
            var endpoints = new List<ThermalEndpoint> { source.ThermalEndpoint() };
            foreach (var machine in machines)
                if (!machine.Block.Closed && machine.Block.CubeGrid == source.Block.CubeGrid)
                    endpoints.Add(machine.Endpoint(source.Block.OwnerId));
            foreach (var other in sources)
                if (other != source && other.ThermalInitialized && other.Block.CubeGrid == source.Block.CubeGrid)
                    endpoints.Add(other.ThermalEndpoint());
            var network = new ThermalNetwork(endpoints);
            var circuits = network.Loops(endpoints[0]);
            ThermalCommissioning[] charges;
            if (!starts.TryGetValue(source.Id, out charges))
                starts[source.Id] = charges = new ThermalCommissioning[ThermalLoops.Count];
            double allocation = ThermalLoops.Allocation(source.ThermalHeatMW);
            double freshMW = 0, availableHeatMW = 0;
            byte valves = 0;
            bool filling = false;
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
                    loop.Connected = false; loop.Charge = 0; charges[index] = null;
                    continue;
                }
                foreach (var machine in bank)
                { claimed.Add(machine.Entity.EntityId); machine.SourceId = source.Id; }
                if (charges[index] == null || !charges[index].Covers(source.Block.CubeGrid.EntityId, units))
                    charges[index] = new ThermalCommissioning(source.Block.CubeGrid.EntityId, units);
                var charge = charges[index];
                bool hasHeat = state.Store.HotMJ + state.Store.WasteMJ > .001;
                foreach (var machine in bank) hasHeat |= machine.Store.HotMJ + machine.Store.WasteMJ > .001;
                bool fill = charge.Seconds < 8;
                double delivered = 0;
                if ((running && (fill || host.Store.HotMJ <= .001)) || (!running && hasHeat))
                {
                    delivered = host.RequestStartup(source.Id, plan.AcceptedMW * .02);
                    startupHosts.Add(host.Entity.EntityId);
                }
                if (fill && (running || hasHeat))
                    charge.Seconds = ThermalMath.StartupSeconds(charge.Seconds, plan.AcceptedMW * .02, delivered, 1.0 / 60);
                loop.Charge = charge.Seconds / 8;
                host.RotorCharge = loop.Charge;
                double net = host.Generator == null ? 0 : host.Generator.CurrentOutput;
                double circulation = ThermalMath.CirculationPower(net, plan.Efficiency, delivered, plan.AcceptedMW);
                // A depressurized circuit cannot circulate core energy. Powered
                // filling still deposits its actual startup electricity as heat.
                circulation *= loop.Charge;
                host.RotorCirculation = circulation; host.RotorHotC = source.ThermalHotC;
                state.RejectedMW += DrainLoop(source, bank, allocation * circulation / 60, circulation);
                loop.CoolingMW = plan.CoolingMW * circulation;
                state.CoolingMW += loop.CoolingMW;
                if (loop.Available || (fill && delivered > 0)) valves |= (byte)(1 << index);
                if (!loop.Available)
                {
                    filling |= running || hasHeat;
                    loop.Diagnostic = "CO2 filling/compression: " + charge.Seconds.ToString("0.0") + " / 8 s powered";
                }
                else
                {
                    loop.HeatMW = plan.AcceptedMW;
                    loop.NetMW = plan.NetMW;
                    loop.RequiredCoolingMW = plan.RequiredCoolingMW * source.Motion.PowerRamp;
                    loop.Diagnostic = plan.Limit;
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
                }
                // Restrict flow tracing to this circuit. Keeping the full root
                // port array preserves the existing four-port network packet.
                CapturePlantFlow(source, new ThermalNetwork(circuit.Nodes), circuit.Nodes, bank, plan, circulation);
            }
            CaptureIsolation(network, endpoints, valves);
            int active = state.AvailableLoops;
            state.DutyTrains = active;
            state.Efficiency = availableHeatMW > 0 ? state.SupportedMW / availableHeatMW : 0;
            if (ThermalLoops.LastLoopLost(previous, active, running)) source.StopForLoopLoss();
            if (source.ThermalCanRun && active > 0) state.LoopTrip = false;
            source.ProduceThermal(freshMW);
            state.Diagnostic = state.LoopTrip && !source.Block.Enabled
                ? "All operating circuits lost: shutdown latched; retain cooldown power, repair/refill and restart manually"
                : active + "/4 circuits ready / " + (active * 25) + "% maximum reactor allocation"
                    + (filling ? " / commissioning circuits with delivered power" : "");
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
