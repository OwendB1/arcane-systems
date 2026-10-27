using System;
using ProtoBuf;

namespace ArcanePower
{
    // Each circuit owns its quarter allocation and retained waste independently.
    [ProtoContract]
    public sealed class ThermalLoopState
    {
        // ProtoMember(1) was CO2 charge; retired, never reuse.
        [ProtoMember(2)] public bool Connected;
        [ProtoMember(3)] public double HeatMW;
        [ProtoMember(4)] public double NetMW;
        [ProtoMember(5)] public double CoolingMW;
        [ProtoMember(6)] public double RequiredCoolingMW;
        [ProtoMember(7)] public string Diagnostic = "Connect one turbine and cooling; cap unused pipe mouths";
        [ProtoMember(8)] public double ExcessMJ;
        [ProtoMember(9)] public double OutputMW;
        [ProtoMember(10)] public double ReactionMW;
        [ProtoMember(11)] public double DesignCoolingMW;
        [ProtoMember(12)] public double RejectedMW;
        [ProtoMember(13)] public double PotentialCoolingMW;

        public bool Valid()
        {
            return ThermalMath.Finite(HeatMW) && HeatMW >= 0 && HeatMW <= 625000
                && ThermalMath.Finite(NetMW) && NetMW >= 0 && NetMW <= 487500
                && ThermalMath.Finite(CoolingMW) && CoolingMW >= 0
                && ThermalMath.Finite(RequiredCoolingMW) && RequiredCoolingMW >= 0 && RequiredCoolingMW <= 625000
                && ThermalMath.Finite(ExcessMJ) && ExcessMJ >= 0
                && ThermalMath.Finite(OutputMW) && OutputMW >= 0 && OutputMW <= 487500.1
                && ThermalMath.Finite(ReactionMW) && ReactionMW >= 0 && ReactionMW <= 625000.1
                && ThermalMath.Finite(DesignCoolingMW) && DesignCoolingMW >= 0 && DesignCoolingMW <= 625000
                && ThermalMath.Finite(RejectedMW) && RejectedMW >= 0
                && ThermalMath.Finite(PotentialCoolingMW) && PotentialCoolingMW >= 0
                && Diagnostic != null && Diagnostic.Length <= 256;
        }
    }

    public static class ThermalLoops
    {
        public const int Count = 4;
        public static ThermalLoopState[] Empty()
        {
            var loops = new ThermalLoopState[Count];
            for (int i = 0; i < loops.Length; i++) loops[i] = new ThermalLoopState();
            return loops;
        }
        public static double Allocation(double ratingMW)
        { return ThermalMath.Finite(ratingMW) ? Math.Max(0, ratingMW) / Count : 0; }

        public static byte OpenValves(ThermalReactorState state)
        {
            if (state == null || state.Mode != ThermalMode.Brayton || state.Deployment != 1
                || state.Loops == null || state.Loops.Length != Count) return 0;
            byte mask = 0;
            for (int i = 0; i < Count; i++)
                if (state.Loops[i] != null && state.Loops[i].Connected) mask |= (byte)(1 << i);
            return mask;
        }
    }
}
