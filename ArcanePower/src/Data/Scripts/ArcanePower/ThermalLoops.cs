using System;
using ProtoBuf;

namespace ArcanePower
{
    // Working-fluid charge is separate from the MJ inventories on real blocks.
    // Each sealed circuit receives one quarter of the nominal reactor flow.
    [ProtoContract]
    public sealed class ThermalLoopState
    {
        [ProtoMember(1)] public double Charge;
        [ProtoMember(2)] public bool Connected;
        [ProtoMember(3)] public double HeatMW;
        [ProtoMember(4)] public double NetMW;
        [ProtoMember(5)] public double CoolingMW;
        [ProtoMember(6)] public double RequiredCoolingMW;
        [ProtoMember(7)] public string Diagnostic = "Connect one turbine and cooling; cap unused pipe mouths";
        public double PressureMPa { get { return Charge * ThermalLoops.OperatingPressureMPa; } }
        public bool Available { get { return Connected && Charge >= 1; } }

        public bool Valid()
        {
            return ThermalMath.Finite(Charge) && Charge >= 0 && Charge <= 1
                && (Connected || Charge == 0)
                && ThermalMath.Finite(HeatMW) && HeatMW >= 0 && HeatMW <= 625000
                && ThermalMath.Finite(NetMW) && NetMW >= 0 && NetMW <= 487500
                && ThermalMath.Finite(CoolingMW) && CoolingMW >= 0
                && ThermalMath.Finite(RequiredCoolingMW) && RequiredCoolingMW >= 0 && RequiredCoolingMW <= 625000
                && Diagnostic != null && Diagnostic.Length <= 256;
        }
    }

    public static class ThermalLoops
    {
        public const int Count = 4;
        public const double OperatingPressureMPa = 22;
        public static ThermalLoopState[] Empty()
        {
            var loops = new ThermalLoopState[Count];
            for (int i = 0; i < loops.Length; i++) loops[i] = new ThermalLoopState();
            return loops;
        }
        public static double Allocation(double ratingMW)
        { return ThermalMath.Finite(ratingMW) ? Math.Max(0, ratingMW) / Count : 0; }
        public static bool LastLoopLost(int previous, int current, bool running)
        { return running && previous > 0 && current == 0; }
    }
}
