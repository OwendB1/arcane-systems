using System;
using ProtoBuf;

namespace ArcanePower
{
    // Each validated circuit receives one quarter of the nominal reactor flow.
    // Heat inventories and metered pump power govern actual circulation.
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

        public bool Valid()
        {
            return ThermalMath.Finite(HeatMW) && HeatMW >= 0 && HeatMW <= 625000
                && ThermalMath.Finite(NetMW) && NetMW >= 0 && NetMW <= 487500
                && ThermalMath.Finite(CoolingMW) && CoolingMW >= 0
                && ThermalMath.Finite(RequiredCoolingMW) && RequiredCoolingMW >= 0 && RequiredCoolingMW <= 625000
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
                || state.Faulted || state.Loops == null || state.Loops.Length != Count) return 0;
            byte mask = 0;
            for (int i = 0; i < Count; i++)
                if (state.Loops[i] != null && state.Loops[i].Connected) mask |= (byte)(1 << i);
            return mask;
        }
    }
}
