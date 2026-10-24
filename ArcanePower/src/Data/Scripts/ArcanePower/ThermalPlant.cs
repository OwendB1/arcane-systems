using System;
using System.Collections.Generic;
using ProtoBuf;

namespace ArcanePower
{
    public enum ThermalMode { Standalone, Brayton }
    public enum ThermalKind { Reactor = 0, Train = 2, AirCooler = 4, Radiator = 5, Pipe = 6, RadiatorPanel = 7 }

    [ProtoContract]
    public sealed class ThermalStore
    {
        [ProtoMember(1)] public long EntityId;
        [ProtoMember(2)] public double HotMJ;
        [ProtoMember(3)] public double WasteMJ;
        [ProtoMember(4)] public string Fault;
        [ProtoMember(5)] public long SourceId;
        [ProtoMember(6)] public ThermalRotorState Rotor;
        [ProtoMember(7)] public ThermalRadiatorState Radiator;

        public bool Valid(long id, double capacity)
        {
            return EntityId == id && ThermalMath.Finite(HotMJ) && ThermalMath.Finite(WasteMJ)
                && HotMJ >= 0 && WasteMJ >= 0 && HotMJ + WasteMJ <= capacity + .001
                && (Fault == null || Fault.Length <= 256) && (Rotor == null || Rotor.Valid(id))
                && (Radiator == null || Radiator.Valid(id));
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
        [ProtoMember(16)] public bool Faulted;
        [ProtoMember(17)] public double AttachedHeatMJ;
        [ProtoMember(18)] public double CoolingMW;
        [ProtoMember(19)] public double RequiredCoolingMW;
        [ProtoMember(20)] public ThermalLoopState[] Loops = ThermalLoops.Empty();
        [ProtoMember(21)] public int LoopVersion;
        [ProtoMember(22)] public bool LoopTrip;

        public int AvailableLoops
        {
            get { int count = 0; if (Loops != null) foreach (var loop in Loops) if (loop != null && loop.Available) count++; return count; }
        }

        private bool ValidLoops()
        {
            if (LoopVersion < 0 || LoopVersion > 1) return false;
            if (Loops == null) return LoopVersion == 0;
            if (Loops.Length != ThermalLoops.Count) return false;
            foreach (var loop in Loops) if (loop == null || !loop.Valid()) return false;
            return true;
        }

        public bool Valid(long id)
        {
            return ValidLoops() && Mode >= ThermalMode.Standalone && Mode <= ThermalMode.Brayton
                && Requested >= ThermalMode.Standalone && Requested <= ThermalMode.Brayton
                && Deployment >= 0 && Deployment <= 1 && Store != null && Store.Valid(id, 2500000 * 8.0)
                && ThermalMath.Finite(FuelHeatMJ) && FuelHeatMJ >= 0 && FuelHeatMJ <= 2500000 * 8.0
                && ThermalMath.Finite(ProducedMW) && ProducedMW >= 0 && ProducedMW <= 2500000
                && ThermalMath.Finite(SupportedMW) && SupportedMW >= 0 && SupportedMW <= 1950000
                && ThermalMath.Finite(RejectedMW) && RejectedMW >= 0 && RejectedMW <= 2500000 * 10.0
                && ThermalMath.Finite(NetOutputMW) && NetOutputMW >= 0 && NetOutputMW <= 1950000.1
                && ThermalMath.Finite(StartupMW) && StartupMW >= 0 && StartupMW <= 50000.1
                && ThermalMath.Finite(AttachedHeatMJ) && AttachedHeatMJ >= 0
                && ThermalMath.Finite(CoolingMW) && CoolingMW >= 0
                && ThermalMath.Finite(RequiredCoolingMW) && RequiredCoolingMW >= 0 && RequiredCoolingMW <= 2500000
                && Efficiency >= 0 && Efficiency <= .780001 && DutyTrains >= 0 && StandbyTrains >= 0
                && Diagnostic != null && Diagnostic.Length <= 256;
        }

        public bool Settled
        {
            get { return Mode == Requested && Deployment == (Mode == ThermalMode.Brayton ? 1 : 0); }
        }

        public string TransitionHint(bool cold, bool powered, bool rigReady)
        {
            if (Settled) return null;
            if (!rigReady) return "Mode change blocked: native manifold parts or origins are incompatible";
            if (!cold) return "Mode change: shutting down and draining trapped heat before moving manifolds";
            if (!powered) return "Mode change paused: supply containment power through the two controllers";
            return Requested == ThermalMode.Brayton ? "Deploying Brayton manifolds" : "Retracting manifolds for standalone mode";
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
        public double AcceptedMW, NetMW, Efficiency, CoolingMW, SustainableMW;
        public double RequiredCoolingMW { get { return AcceptedMW * (1 - Efficiency); } }
        public string Limit = "Connect reactor, turbine and cooling";
        public readonly List<ThermalUnit> Trains = new List<ThermalUnit>();
    }

    // This is the design calculator's accounting, shared by the game adapter and
    // executable checks. Auxiliaries are deducted internally exactly once; only
    // cold starting draws external electricity through a native sink.
    public static class ThermalMath
    {
        private static readonly double[] Ceilings = { .40, .55, .66, .78 };
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

        public static double CirculationPower(double netMW, double efficiency, double externalMW, double designMW)
        {
            if (!Finite(netMW) || !Finite(externalMW) || !Finite(designMW) || designMW <= 0) return 0;
            // At least 5% of converted heat already pays for auxiliaries inside
            // net efficiency. Recover that heat from actual output and the bank's
            // efficiency; assuming the 78% ceiling would stall smaller banks.
            // External starting/cooldown power is independently metered.
            double internalMW = Finite(efficiency) && efficiency > 0 && efficiency < 1
                ? Math.Max(0, netMW) / efficiency * .05 : 0;
            return Clamp((internalMW + Math.Max(0, externalMW)) / (designMW * .02), 0, 1);
        }

        public static double AdmitHeat(ThermalStore store, double warmCapacityMJ, double maximumMJ, double paidFuelMJ)
        {
            if (store == null || !Finite(warmCapacityMJ) || !Finite(maximumMJ) || !Finite(paidFuelMJ)) return 0;
            double admitted = Math.Max(0, Math.Min(paidFuelMJ, Math.Min(maximumMJ,
                warmCapacityMJ - store.HotMJ - store.WasteMJ)));
            store.HotMJ += admitted;
            return admitted;
        }

        public static double AdmitReactionHeat(ThermalStore store, double ratingMW, double maximumMJ, double paidFuelMJ)
        {
            if (store == null || !Finite(ratingMW) || ratingMW <= 0) return 0;
            // Four seconds of useful hot reserve; a separate eight-second total
            // limit leaves room for returning waste. Full stores stop fuel use,
            // but retained waste still heats the core and can cause failure.
            return AdmitHeat(store, ratingMW * 8,
                Math.Min(maximumMJ, Math.Max(0, ratingMW * 4 - store.HotMJ)), paidFuelMJ);
        }

        public static double WasteHeatLevel(ThermalStore store, double ratingMW)
        {
            if (store == null || !Finite(ratingMW) || ratingMW <= 0 || !Finite(store.WasteMJ)) return 0;
            // Two seconds of rated reaction energy in unremoved waste is the
            // 100% warning level. This is below the free waste space beside the
            // normal four-second hot reserve, so intake saturation cannot make
            // a persistent cooling shortfall settle safely below critical heat.
            return Clamp(store.WasteMJ / (ratingMW * 2), 0, 4);
        }

        public static double ApproachCoreHeat(double heat, double target, bool runaway)
        {
            double response = runaway ? 720 : target > heat ? 3600 : 1800;
            double next = heat + (target - heat) / response;
            // Motion.Heat is a float. Finish settling once a response step is
            // smaller than its precision, instead of leaving a permanent warning
            // just above normal operating heat after successful cooling.
            return Clamp((float)next == (float)heat ? target : next, 0, 4);
        }

        public static double Efficiency(int grade, double hotC, double coldC)
        {
            if (grade < 0 || grade > 3
                || !Finite(hotC) || !Finite(coldC) || coldC < -273.15 || hotC < Temperatures[grade]) return 0;
            double reference = 1 - 318.15 / (Temperatures[grade] + 273.15);
            double factor = Clamp((1 - (coldC + 273.15) / (hotC + 273.15)) / reference, 0, 1);
            return Math.Max(0, (Ceilings[grade] + Auxiliaries[grade]) * factor - Auxiliaries[grade]);
        }

        public static double AirCooling(double rating, double density, double clearExhaust)
        {
            if (!Finite(rating) || !Finite(density) || !Finite(clearExhaust)) return 0;
            double airflow = Clamp(clearExhaust, 0, 1);
            return Math.Max(0, rating) * Clamp(density, 0, 1) * airflow * airflow;
        }

        public static double RadiativeCooling(double rating, double exposure, double sinkC)
        {
            if (!Finite(exposure) || !Finite(sinkC) || sinkC < -273.15) return 0;
            double panel = Math.Pow(308.15, 4);
            return Math.Max(0, rating) * Clamp(exposure, 0, 1)
                * Clamp((panel - Math.Pow(sinkC + 273.15, 4)) / (panel - 81), 0, 1);
        }

        // One turbine per independent circuit. The caller supplies that circuit's
        // fixed allocation; lost circuits never increase the remaining allocations.
        public static ThermalPlan Dispatch(double offeredMW, double hotC, IList<ThermalUnit> units)
        {
            var best = new ThermalPlan();
            if (!Finite(offeredMW) || offeredMW <= 0 || !Finite(hotC)) return best;
            ThermalUnit train = null;
            var coldPoints = new List<double>();
            foreach (var unit in units)
            {
                if (unit.Kind == ThermalKind.Train)
                {
                    if (train != null) { best.Limit = "Use exactly one turbine per manifold circuit"; return best; }
                    train = unit;
                }
                if ((unit.Kind == ThermalKind.AirCooler || unit.Kind == ThermalKind.Radiator)
                    && Finite(unit.CoolingMW) && unit.CoolingMW >= 0 && Finite(unit.ColdC)
                    && !coldPoints.Contains(unit.ColdC)) coldPoints.Add(unit.ColdC);
            }
            if (train == null || !Finite(train.RatingMW) || train.RatingMW <= 0) return best;
            if (hotC >= 2200 && train.Grade < 3)
            { best.Limit = "T3 Empyrean requires an upgraded Brayton turbine"; return best; }
            coldPoints.Sort();
            for (int grade = 0; grade <= Math.Min(3, train.Grade); grade++)
                foreach (double cold in coldPoints)
                {
                    double eta = Efficiency(grade, hotC, cold);
                    double flow = eta > 0 ? Math.Min(offeredMW, train.RatingMW) : 0;
                    if (flow * eta <= best.NetMW) continue;
                    double cooling = 0;
                    foreach (var unit in units)
                        if ((unit.Kind == ThermalKind.AirCooler || unit.Kind == ThermalKind.Radiator)
                            && unit.ColdC <= cold && Finite(unit.CoolingMW) && unit.CoolingMW > 0) cooling += unit.CoolingMW;
                    best = new ThermalPlan { AcceptedMW = flow, NetMW = flow * eta, Efficiency = eta,
                        CoolingMW = cooling,
                        SustainableMW = Math.Min(flow, cooling / (1 - eta)) * eta,
                        Limit = cooling + .000001 < flow * (1 - eta)
                            ? "Insufficient circuit cooling: retained waste will overheat the reactor"
                            : flow + .000001 < offeredMW ? "Turbine rating limits this circuit" : "Circuit ready" };
                    best.Trains.Add(train);
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
