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
        // ProtoMember(14) was the retired turbine pump draw; never reuse.
        [ProtoMember(16)] public bool Faulted;
        [ProtoMember(17)] public double AttachedHeatMJ;
        [ProtoMember(18)] public double CoolingMW;
        [ProtoMember(19)] public double RequiredCoolingMW;
        [ProtoMember(20)] public ThermalLoopState[] Loops = ThermalLoops.Empty();
        [ProtoMember(21)] public int LoopVersion;
        [ProtoMember(22)] public bool LoopTrip;
        [ProtoMember(23)] public double DesignCoolingMW;

        public double RetainedHeatMJ
        {
            get { double total = Store.WasteMJ; if (Loops != null) foreach (var loop in Loops) if (loop != null) total += loop.ExcessMJ; return total; }
        }

        public void BeginFrame()
        {
            ProducedMW = NetOutputMW = RejectedMW = SupportedMW = 0;
            CoolingMW = RequiredCoolingMW = DesignCoolingMW = AttachedHeatMJ = 0;
            DutyTrains = StandbyTrains = 0;
            foreach (var loop in Loops)
                loop.OutputMW = loop.ReactionMW = loop.RequiredCoolingMW = loop.RejectedMW = 0;
        }

        public void MigrateHeat()
        {
            if (LoopVersion >= 2) return;
            // Old hot inventories were already produced heat. Do not turn them
            // into new fuel credit or erase them when removing the flow model.
            double heat = Store.HotMJ + Store.WasteMJ;
            Store.HotMJ = 0;
            if (Mode == ThermalMode.Brayton)
            { foreach (var loop in Loops) loop.ExcessMJ += heat / ThermalLoops.Count; Store.WasteMJ = 0; }
            else Store.WasteMJ = heat;
            LoopVersion = 2;
        }

        public int ConnectedLoops
        {
            get { int count = 0; if (Loops != null) foreach (var loop in Loops) if (loop != null && loop.Connected) count++; return count; }
        }

        private bool ValidLoops()
        {
            if (LoopVersion < 0 || LoopVersion > 2) return false;
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
                && ThermalMath.Finite(AttachedHeatMJ) && AttachedHeatMJ >= 0
                && ThermalMath.Finite(CoolingMW) && CoolingMW >= 0
                && ThermalMath.Finite(RequiredCoolingMW) && RequiredCoolingMW >= 0 && RequiredCoolingMW <= 2500000
                && ThermalMath.Finite(DesignCoolingMW) && DesignCoolingMW >= 0 && DesignCoolingMW <= 2500000
                && ThermalMath.Finite(RetainedHeatMJ)
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

    // A one-interval claim on paid source energy. Reservations never create heat;
    // only electricity actually delivered by SE consumes fuel energy and emits waste.
    // The source's saved HotMJ retains unused credit across reloads. Claims are
    // rebuilt, never replayed, and the sum of claims cannot exceed that credit.
    public sealed class ThermalOutputGrant
    {
        public readonly ThermalReactorState Source;
        public readonly ThermalLoopState Loop;
        public readonly double HeatMJ, Efficiency, MaximumMW;
        private bool settled;
        public ThermalOutputGrant(ThermalReactorState source, ThermalLoopState loop, double heatMJ, double efficiency)
        {
            Source = source; Loop = loop; HeatMJ = heatMJ; Efficiency = efficiency;
            MaximumMW = heatMJ * efficiency * 60 * .999999;
        }
        public bool Settle(double outputMW)
        {
            if (settled) return false;
            settled = true;
            if (!ThermalMath.Finite(outputMW) || outputMW < 0 || outputMW > MaximumMW + .001
                || !ThermalMath.Finite(Efficiency) || Efficiency <= 0 || Efficiency >= 1) return false;
            double heat = outputMW / (60 * Efficiency);
            if (heat > HeatMJ || heat > Source.Store.HotMJ) return false;
            Source.Store.HotMJ -= heat;
            double waste = Math.Max(0, heat - outputMW / 60);
            Source.ProducedMW += heat * 60; Source.NetOutputMW += outputMW;
            Source.RequiredCoolingMW += waste * 60;
            if (Loop == null) Source.Store.WasteMJ += waste;
            else
            { Loop.ExcessMJ += waste; Loop.OutputMW += outputMW; Loop.ReactionMW += heat * 60; Loop.RequiredCoolingMW += waste * 60; }
            return true;
        }
    }

    // This is the design calculator's accounting, shared by the game adapter and
    // executable checks. Turbine auxiliaries are included in net efficiency;
    // the existing reactor supply owns containment and cooldown support.
    public static class ThermalMath
    {
        private static readonly double[] Ceilings = { .40, .55, .66, .78 };
        private static readonly double[] Auxiliaries = { .08, .07, .06, .05 };
        private static readonly double[] Temperatures = { 650, 1000, 1600, 2200 };

        public static bool Finite(double value) { return !double.IsNaN(value) && !double.IsInfinity(value); }
        public static double Clamp(double value, double low, double high) { return Math.Max(low, Math.Min(high, value)); }
        public static double Span(double value, double start, double end) { return Clamp((value - start) / (end - start), 0, 1); }

        public static double CoolCircuit(ThermalLoopState loop, double capacityMW)
        {
            if (loop == null || !Finite(capacityMW) || capacityMW < 0) return 0;
            double rejected = Math.Min(loop.ExcessMJ, capacityMW / 60);
            loop.ExcessMJ -= rejected; loop.RejectedMW += rejected * 60;
            return rejected * 60;
        }

        public static double AdmitHeat(ThermalStore store, double warmCapacityMJ, double maximumMJ, double paidFuelMJ)
        {
            if (store == null || !Finite(warmCapacityMJ) || !Finite(maximumMJ) || !Finite(paidFuelMJ)) return 0;
            double admitted = Math.Max(0, Math.Min(paidFuelMJ, Math.Min(maximumMJ,
                warmCapacityMJ - store.HotMJ - store.WasteMJ)));
            store.HotMJ += admitted;
            return admitted;
        }

        public static double WasteHeatLevel(ThermalReactorState state, double ratingMW)
        {
            if (state == null || !Finite(ratingMW) || ratingMW <= 0) return 0;
            double level = state.Store.WasteMJ / (ratingMW * 2);
            // A hot circuit cannot hide behind three cold ones.
            foreach (var loop in state.Loops) level = Math.Max(level, loop.ExcessMJ / (ratingMW * .5));
            return Clamp(level, 0, 4);
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

        public static double Reject(ThermalStore store, double maximumMJ, bool hot)
        {
            if (store == null || !Finite(maximumMJ) || maximumMJ <= 0) return 0;
            double rejected = Math.Min(maximumMJ, hot ? store.HotMJ : store.WasteMJ);
            if (hot) store.HotMJ -= rejected; else store.WasteMJ -= rejected;
            return rejected;
        }
    }
}
