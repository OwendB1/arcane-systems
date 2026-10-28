using System;
using System.Collections.Generic;
using ProtoBuf;

namespace ArcanePower
{
    public enum ThermalMode { Standalone, Brayton }
    public enum ThermalKind { Reactor = 0, Train = 2, AirCooler = 4, Radiator = 5, Pipe = 6, RadiatorPanel = 7, HullRadiator = 8 }

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
        [ProtoMember(8)] public double Efficiency = ThermalMath.StandaloneEfficiency;
        [ProtoMember(9)] public int DutyTrains;
        // ProtoMember(10) was the retired standby-train count; never reuse.
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
        // ProtoMember(23) was duplicate full-load cooling telemetry; never reuse.

        public double PotentialCoolingMW
        {
            get { double total = Mode == ThermalMode.Standalone ? CoolingMW : 0;
                if (Mode == ThermalMode.Brayton && Loops != null)
                    foreach (var loop in Loops) if (loop != null) total += loop.PotentialCoolingMW;
                return total; }
        }

        public double RetainedHeatMJ
        {
            get { double total = Store.WasteMJ; if (Loops != null) foreach (var loop in Loops) if (loop != null) total += loop.ExcessMJ; return total; }
        }

        public void BeginFrame()
        {
            ProducedMW = NetOutputMW = RejectedMW = SupportedMW = 0;
            CoolingMW = RequiredCoolingMW = AttachedHeatMJ = 0;
            DutyTrains = 0;
            foreach (var loop in Loops)
                loop.OutputMW = loop.RejectedMW = 0;
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
                && ThermalMath.Finite(RetainedHeatMJ)
                && Efficiency >= 0 && Efficiency <= .800001 && DutyTrains >= 0
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
        public double RatingMW, CoolingMW;
    }

    public sealed class ThermalPlan
    {
        public double AcceptedMW, NetMW, CoolingMW;
        public double Efficiency { get { return ThermalMath.BraytonEfficiency; } }
        public double RequiredCoolingMW { get { return NetMW; } }
        public double SustainableMW { get { return Math.Min(NetMW, CoolingMW); } }
        public string Limit = "Connect reactor, turbine and cooling";
        public readonly List<ThermalUnit> Trains = new List<ThermalUnit>();
    }

    // A one-interval claim on paid source energy. Reservations never create heat;
    // only delivered electricity consumes fuel credit and creates cooling load.
    // Brayton cooling is a gameplay budget separate from fuel-energy accounting.
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
            // Native Capacity and CurrentOutput are floats. At 50 GW their
            // roundtrip can exceed a fixed 1 kW tolerance. Allow float rounding
            // inside the grant's 1 ppm headroom; the paid-MJ checks remain exact.
            double roundingMW = Math.Max(.001, MaximumMW * .00000025);
            if (!ThermalMath.Finite(outputMW) || outputMW < 0 || outputMW > MaximumMW + roundingMW
                || !ThermalMath.Finite(Efficiency) || Efficiency <= 0 || Efficiency >= 1) return false;
            double heat = outputMW / (60 * Efficiency);
            if (heat > HeatMJ || heat > Source.Store.HotMJ) return false;
            Source.Store.HotMJ -= heat;
            double waste = Source.Mode == ThermalMode.Brayton ? outputMW / 60
                : Math.Max(0, heat - outputMW / 60);
            Source.ProducedMW += heat * 60; Source.NetOutputMW += outputMW;
            Source.RequiredCoolingMW += waste * 60;
            if (Loop == null) Source.Store.WasteMJ += waste;
            else
            { Loop.ExcessMJ += waste; Loop.OutputMW += outputMW; }
            return true;
        }
    }

    // This is the design calculator's accounting, shared by the game adapter and
    // executable checks. Fuel conversion and cooling load are separate budgets;
    // the existing reactor supply owns containment and cooldown support.
    public static class ThermalMath
    {
        public const float CooldownHeat = .15f;
        public const double StandaloneEfficiency = .10;
        public const double BraytonEfficiency = .80;

        public static double FuelRatingMW(int tier)
        { return tier == 1 ? 5000 : tier == 2 ? 50000 : tier == 3 ? 250000 : 0; }

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
            foreach (var loop in state.Loops)
                level = Math.Max(level, loop.ExcessMJ / (ratingMW * .5));
            return Clamp(level, 0, 4);
        }

        internal static double CoreHeatResponse(double heat, double target, bool runaway)
        { return runaway ? 720 : target > heat ? 3600 : 1800; }

        public static double ApproachCoreHeat(double heat, double target, bool runaway)
        {
            double response = CoreHeatResponse(heat, target, runaway);
            double next = heat + (target - heat) / response;
            // Motion.Heat is a float. Finish settling once a response step is
            // smaller than its precision, instead of leaving a permanent warning
            // just above normal operating heat after successful cooling.
            return Clamp((float)next == (float)heat ? target : next, 0, 4);
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
            var plan = new ThermalPlan();
            if (!Finite(offeredMW) || offeredMW <= 0 || !Finite(hotC) || hotC < 650) return plan;
            ThermalUnit train = null;
            bool hasCooling = false;
            foreach (var unit in units)
            {
                if (unit.Kind == ThermalKind.Train)
                {
                    if (train != null) { plan.Limit = "Use exactly one turbine per manifold circuit"; return plan; }
                    train = unit;
                }
                if ((unit.Kind == ThermalKind.AirCooler || unit.Kind == ThermalKind.Radiator || unit.Kind == ThermalKind.HullRadiator)
                    && Finite(unit.CoolingMW) && unit.CoolingMW >= 0)
                { hasCooling = true; plan.CoolingMW += unit.CoolingMW; }
            }
            if (train == null || !hasCooling || train.Grade < 0 || train.Grade > 3
                || !Finite(train.RatingMW) || train.RatingMW <= 0) return plan;
            if (hotC >= 2200 && train.Grade < 3)
            { plan.Limit = "T3 Empyrean requires an upgraded Brayton turbine"; return plan; }
            plan.AcceptedMW = Math.Min(offeredMW, train.RatingMW);
            plan.NetMW = plan.AcceptedMW * BraytonEfficiency;
            plan.Limit = plan.CoolingMW + .000001 < plan.NetMW
                ? "Cooling capacity below output: cooling backlog will overheat the reactor"
                : plan.AcceptedMW + .000001 < offeredMW ? "Turbine rating limits this circuit" : "Circuit ready";
            plan.Trains.Add(train);
            return plan;
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
