using System;
using System.Collections.Generic;
using ProtoBuf;

namespace ArcanePower
{
    public enum ThermalMode { Standalone, Brayton }
    public enum ThermalKind { Reactor, Heater, Train, Recuperator, AirCooler, Radiator, Pipe }

    [ProtoContract]
    public sealed class ThermalStore
    {
        [ProtoMember(1)] public long EntityId;
        [ProtoMember(2)] public double HotMJ;
        [ProtoMember(3)] public double WasteMJ;
        [ProtoMember(4)] public string Fault;
        [ProtoMember(5)] public long SourceId;
        [ProtoMember(6)] public ThermalRotorState Rotor;

        public bool Valid(long id, double capacity)
        {
            return EntityId == id && ThermalMath.Finite(HotMJ) && ThermalMath.Finite(WasteMJ)
                && HotMJ >= 0 && WasteMJ >= 0 && HotMJ + WasteMJ <= capacity + .001
                && (Fault == null || Fault.Length <= 256) && (Rotor == null || Rotor.Valid(id));
        }
    }

    [ProtoContract]
    public sealed class ThermalReactorState
    {
        [ProtoMember(1)] public ThermalMode Mode;
        [ProtoMember(2)] public ThermalMode Requested;
        [ProtoMember(3)] public float Deployment;
        [ProtoMember(4)] public ThermalStore Store = new ThermalStore();
        [ProtoMember(5)] public double FuelHeatMJ;
        [ProtoMember(6)] public double ProducedMW;
        [ProtoMember(7)] public double SupportedMW;
        [ProtoMember(8)] public double Efficiency = .20;
        [ProtoMember(9)] public int DutyTrains;
        [ProtoMember(10)] public int StandbyTrains;
        [ProtoMember(11)] public string Diagnostic = "Standalone / integrated cooling";
        [ProtoMember(12)] public double RejectedMW;
        [ProtoMember(13)] public double NetOutputMW;
        [ProtoMember(14)] public double StartupMW;
        [ProtoMember(15)] public double RecoveryRatio;
        [ProtoMember(16)] public bool Faulted;
        [ProtoMember(17)] public double AttachedHeatMJ;

        public bool Valid(long id)
        {
            return Mode >= ThermalMode.Standalone && Mode <= ThermalMode.Brayton
                && Requested >= ThermalMode.Standalone && Requested <= ThermalMode.Brayton
                && Deployment >= 0 && Deployment <= 1 && Store != null && Store.Valid(id, 2500000 * 8.0)
                && ThermalMath.Finite(FuelHeatMJ) && FuelHeatMJ >= 0 && FuelHeatMJ <= 2500000 * 8.0
                && ThermalMath.Finite(ProducedMW) && ProducedMW >= 0 && ProducedMW <= 2500000
                && ThermalMath.Finite(SupportedMW) && SupportedMW >= 0 && SupportedMW <= 1950000
                && ThermalMath.Finite(RejectedMW) && RejectedMW >= 0 && RejectedMW <= 2500000 * 10.0
                && ThermalMath.Finite(NetOutputMW) && NetOutputMW >= 0 && NetOutputMW <= 1950000.1
                && ThermalMath.Finite(StartupMW) && StartupMW >= 0 && StartupMW <= 50000.1
                && ThermalMath.Finite(RecoveryRatio) && RecoveryRatio >= 0 && RecoveryRatio <= 1000000
                && ThermalMath.Finite(AttachedHeatMJ) && AttachedHeatMJ >= 0
                && Efficiency >= 0 && Efficiency <= .780001 && DutyTrains >= 0 && StandbyTrains >= 0
                && Diagnostic != null && Diagnostic.Length <= 256;
        }

        public bool Settled
        {
            get { return Mode == Requested && Deployment == (Mode == ThermalMode.Brayton ? 1 : 0); }
        }

        public void AdvanceManifolds(bool cold, bool powered, bool rigReady, double seconds)
        {
            if (!cold || !powered || !rigReady || !ThermalMath.Finite(seconds) || seconds <= 0) return;
            float target = Requested == ThermalMode.Brayton ? 1 : 0;
            float step = (float)Math.Min(1, seconds / 6);
            Deployment = target > Deployment ? Math.Min(target, Deployment + step) : Math.Max(target, Deployment - step);
            if (Deployment == target) Mode = Requested;
        }
    }

    public sealed class ThermalUnit
    {
        public long Id;
        public ThermalKind Kind;
        public int Grade;
        public double RatingMW, CoolingMW, ColdC = 45;
    }

    public sealed class ThermalPlan
    {
        public double AcceptedMW, NetMW, Efficiency, RecoveryRatio, DesignMW, CoolingMW;
        public int Standby;
        public string Limit = "Complete heater / train / recovery / cooling route required";
        public readonly List<ThermalUnit> Trains = new List<ThermalUnit>();
        public readonly List<long> Heaters = new List<long>();
    }

    // This is the design calculator's accounting, shared by the game adapter and
    // executable checks. Auxiliaries are deducted internally exactly once; only
    // cold starting draws external electricity through a native sink.
    public static class ThermalMath
    {
        private static readonly double[] Ceilings = { .55, .66, .74, .78 };
        private static readonly double[] Auxiliaries = { .08, .07, .06, .05 };
        private static readonly double[] Temperatures = { 650, 1000, 1600, 2200 };

        public static bool Finite(double value) { return !double.IsNaN(value) && !double.IsInfinity(value); }
        public static double Clamp(double value, double low, double high) { return Math.Max(low, Math.Min(high, value)); }
        public static double Span(double value, double start, double end) { return Clamp((value - start) / (end - start), 0, 1); }

        public static double StartupSeconds(double previous, double requiredMW, double deliveredMW, double seconds)
        {
            if (!Finite(previous) || !Finite(requiredMW) || !Finite(deliveredMW) || !Finite(seconds)
                || requiredMW <= 0 || deliveredMW < requiredMW * .999 || seconds <= 0 || seconds > 1) return 0;
            return Math.Min(8, Math.Max(0, previous) + seconds);
        }

        public static double CirculationPower(double netMW, double externalMW, double designMW)
        {
            if (!Finite(netMW) || !Finite(externalMW) || !Finite(designMW) || designMW <= 0) return 0;
            // The smallest internal auxiliary share across supported grades is
            // 5% / 78% of measured net export. It has already been deducted by
            // conversion efficiency. External starting/cooldown power is metered.
            return Clamp((Math.Max(0, netMW) * .05 / .78 + Math.Max(0, externalMW)) / (designMW * .02), 0, 1);
        }

        public static double AdmitHeat(ThermalStore store, double warmCapacityMJ, double maximumMJ, double paidFuelMJ)
        {
            if (store == null || !Finite(warmCapacityMJ) || !Finite(maximumMJ) || !Finite(paidFuelMJ)) return 0;
            double admitted = Math.Max(0, Math.Min(paidFuelMJ, Math.Min(maximumMJ,
                warmCapacityMJ - store.HotMJ - store.WasteMJ)));
            store.HotMJ += admitted;
            return admitted;
        }

        public static double Efficiency(int grade, double recovery, double hotC, double coldC)
        {
            if (grade < 0 || grade > 3 || !Finite(recovery) || recovery <= 0
                || !Finite(hotC) || !Finite(coldC) || coldC < -273.15 || hotC < Temperatures[grade]) return 0;
            double recovered = Math.Min(.78, .40 + .40 * (1 - Math.Pow(2, -Math.Max(0, recovery - 1))));
            double reference = 1 - 318.15 / (Temperatures[grade] + 273.15);
            double factor = Clamp((1 - (coldC + 273.15) / (hotC + 273.15)) / reference, 0, 1);
            return Math.Max(0, (Math.Min(Ceilings[grade], recovered) + Auxiliaries[grade]) * factor - Auxiliaries[grade]);
        }

        public static double AirCooling(double rating, double density)
        { return Finite(density) && density > 0 ? Math.Max(0, rating) * Math.Min(1, density) : 0; }

        public static double RadiativeCooling(double rating, double exposure, double sinkC)
        {
            if (!Finite(exposure) || !Finite(sinkC) || sinkC < -273.15) return 0;
            double panel = Math.Pow(308.15, 4);
            return Math.Max(0, rating) * Clamp(exposure, 0, 1)
                * Clamp((panel - Math.Pow(sinkC + 273.15, 4)) / (panel - 81), 0, 1);
        }

        public static ThermalPlan Dispatch(double offeredMW, double hotC, IList<ThermalUnit> units)
        {
            var best = new ThermalPlan();
            if (!Finite(offeredMW) || offeredMW <= 0 || !Finite(hotC)) return best;
            var coldPoints = new List<double>();
            int installedTrains = 0;
            foreach (var unit in units)
            {
                if (unit.CoolingMW > 0 && Finite(unit.CoolingMW) && Finite(unit.ColdC) && !coldPoints.Contains(unit.ColdC)) coldPoints.Add(unit.ColdC);
                if (unit.Kind == ThermalKind.Train && Finite(unit.RatingMW) && unit.RatingMW > 0) installedTrains++;
            }
            coldPoints.Sort();
            for (int grade = 0; grade < 4; grade++)
            {
                if (hotC < Temperatures[grade]) continue;
                double heaters = 0, recovery = 0;
                var trains = new List<ThermalUnit>();
                foreach (var unit in units)
                {
                    if (!Finite(unit.RatingMW) || unit.RatingMW <= 0 || unit.Grade < grade) continue;
                    if (unit.Kind == ThermalKind.Heater) heaters += unit.RatingMW;
                    if (unit.Kind == ThermalKind.Recuperator) recovery += unit.RatingMW;
                    if (unit.Kind == ThermalKind.Train) trains.Add(unit);
                }
                trains.Sort((a, b) => { int size = b.RatingMW.CompareTo(a.RatingMW); return size != 0 ? size : a.Id.CompareTo(b.Id); });
                // The authored family has two train ratings. Windows in rating
                // order cover their capacity combinations, including leaving an
                // oversized premium train idle beside a smaller efficient bank.
                for (int start = 0; start < trains.Count; start++)
                {
                  double design = 0;
                  for (int end = start; end < trains.Count; end++)
                  {
                    int duty = end - start + 1;
                    design += trains[end].RatingMW;
                    foreach (double cold in coldPoints)
                    {
                        double cooling = 0;
                        foreach (var unit in units) if (unit.ColdC <= cold && Finite(unit.CoolingMW) && unit.CoolingMW > 0) cooling += unit.CoolingMW;
                        double ratio = recovery / design;
                        double eta = Efficiency(grade, ratio, hotC, cold);
                        double flow = Math.Min(offeredMW, Math.Min(heaters, Math.Min(design, recovery)));
                        flow = eta > 0 ? Math.Min(flow, cooling / (1 - eta)) : 0;
                        double net = flow * eta;
                        if (net <= 0 || net < best.NetMW - .000001 || (Math.Abs(net - best.NetMW) <= .000001 && duty >= best.Trains.Count)) continue;
                        best = new ThermalPlan { AcceptedMW = flow, NetMW = net, Efficiency = eta,
                            RecoveryRatio = ratio, DesignMW = design, CoolingMW = cooling, Standby = installedTrains - duty,
                            Limit = flow + .000001 < offeredMW ? "Heat flow limited by heater, dispatched train, recovery or cooling capacity" : "Heat supply limits output" };
                        for (int i = start; i <= end; i++) best.Trains.Add(trains[i]);
                        foreach (var unit in units)
                            if (unit.Kind == ThermalKind.Heater && unit.Grade >= grade) best.Heaters.Add(unit.Id);
                    }
                    if (design >= Math.Min(offeredMW, Math.Min(heaters, recovery))) break;
                  }
                }
            }
            return best;
        }

        public static double Transfer(ThermalStore sender, ThermalStore receiver, double receiverCapacity, double maximumMJ, bool waste)
        {
            if (sender == null || receiver == null || sender == receiver || !Finite(receiverCapacity)
                || !Finite(maximumMJ) || maximumMJ <= 0 || !Finite(sender.HotMJ) || !Finite(sender.WasteMJ)
                || !Finite(receiver.HotMJ) || !Finite(receiver.WasteMJ)) return 0;
            double available = waste ? sender.WasteMJ : sender.HotMJ;
            double moved = Math.Max(0, Math.Min(maximumMJ, Math.Min(available, receiverCapacity - receiver.HotMJ - receiver.WasteMJ)));
            if (waste) { sender.WasteMJ -= moved; receiver.WasteMJ += moved; }
            else { sender.HotMJ -= moved; receiver.HotMJ += moved; }
            return moved;
        }

        public static double ExportLimit(ThermalStore store, double capacity, double efficiency, double ratingMW, double seconds)
        {
            if (store == null || !store.Valid(store.EntityId, capacity) || !Finite(ratingMW)
                || efficiency <= 0 || efficiency >= 1 || !Finite(efficiency) || !Finite(seconds) || seconds <= 0) return 0;
            // Conversion conserves total energy: the unexported fraction stays
            // in this block as waste heat, so conversion cannot overfill it.
            // Leave room for the native source's float rounding at the edge of
            // a double-precision MJ allocation.
            return Math.Max(0, Math.Min(ratingMW, store.HotMJ * efficiency / seconds)) * .999999;
        }

        public static bool Convert(ThermalStore store, double deliveredMJ, double efficiency)
        {
            if (store == null || !Finite(deliveredMJ) || deliveredMJ < 0 || !Finite(efficiency) || efficiency <= 0 || efficiency >= 1) return false;
            double consumed = deliveredMJ / efficiency;
            if (consumed > store.HotMJ + .000001) return false;
            consumed = Math.Min(consumed, store.HotMJ);
            store.HotMJ -= consumed;
            store.WasteMJ += consumed - deliveredMJ;
            return true;
        }

        public static double Reject(ThermalStore store, double maximumMJ, bool hot)
        {
            if (store == null || !Finite(maximumMJ) || maximumMJ <= 0) return 0;
            double rejected = Math.Min(maximumMJ, hot ? store.HotMJ : store.WasteMJ);
            if (hot) store.HotMJ -= rejected; else store.WasteMJ -= rejected;
            return rejected;
        }
    }
}
