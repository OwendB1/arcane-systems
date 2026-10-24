using System;
using ProtoBuf;
using VRageMath;

namespace ArcanePower
{
    [ProtoContract]
    public sealed class ThermalRotorState
    {
        [ProtoMember(1)] public long EntityId;
        [ProtoMember(2)] public long Sequence;
        [ProtoMember(3)] public double Phase;
        [ProtoMember(4)] public double CompressorPhase;
        [ProtoMember(5)] public double Rpm;
        [ProtoMember(6)] public double CompressorRpm;
        [ProtoMember(7)] public double TargetRpm;
        [ProtoMember(8)] public double CompressorTargetRpm;
        [ProtoMember(9)] public double PressureMPa;
        [ProtoMember(10)] public double HotC = 45;

        public bool Valid(long id)
        {
            return EntityId == id && Sequence >= 0
                && ThermalMath.Finite(Phase) && Phase >= 0 && Phase < Math.PI * 2
                && ThermalMath.Finite(CompressorPhase) && CompressorPhase >= 0 && CompressorPhase < Math.PI * 2
                && ThermalMath.Finite(Rpm) && Rpm >= 0 && Rpm <= ThermalRotors.MaxRpm
                && ThermalMath.Finite(TargetRpm) && TargetRpm >= 0 && TargetRpm <= ThermalRotors.MaxRpm
                && ThermalMath.Finite(CompressorRpm) && CompressorRpm >= 0 && CompressorRpm <= ThermalRotors.MaxCompressorRpm
                && ThermalMath.Finite(CompressorTargetRpm) && CompressorTargetRpm >= 0 && CompressorTargetRpm <= ThermalRotors.MaxCompressorRpm
                && ThermalMath.Finite(PressureMPa) && PressureMPa >= 0 && PressureMPa <= 22
                && ThermalMath.Finite(HotC) && HotC >= 45 && HotC <= 2200;
        }
    }

    // Cosmetic state only: this never grants power or consumes/creates MJ.
    // Pressure follows the authoritative circuit charge; visual inertia never grants MW.
    public static class ThermalRotors
    {
        // Cosmetic speeds keep the 64/56-blade rows below 24 blade passes/s.
        // Actual engineering shaft speeds are deliberately not simulated.
        public const double MaxRpm = 20, MaxCompressorRpm = 24;
        public static void Drive(ThermalRotorState state, double hotMJ, double ratingMW,
            double hotC, double circulation, bool running, double seconds, double charge = 1)
        {
            if (!ThermalMath.Finite(seconds) || seconds <= 0 || seconds > 1) return;
            bool valid = running && ThermalMath.Finite(hotMJ) && hotMJ >= 0
                && ThermalMath.Finite(ratingMW) && ratingMW > 0 && ThermalMath.Finite(hotC)
                && ThermalMath.Finite(circulation);
            double flow = valid ? ThermalMath.Clamp(circulation, 0, 1) : 0;
            double heat = valid ? ThermalMath.Clamp(hotMJ / (ratingMW * .5), 0, 1) : 0;
            state.HotC = 45 + (valid ? ThermalMath.Clamp(hotC, 45, 2200) - 45 : 0) * heat;
            double pressure = ThermalMath.Finite(charge) ? ThermalLoops.OperatingPressureMPa * ThermalMath.Clamp(charge, 0, 1) : 0;
            state.PressureMPa = pressure + (state.PressureMPa - pressure) * Math.Exp(-seconds / 2);
            state.TargetRpm = flow > 0 && heat > 0
                ? MaxRpm * Math.Sqrt(flow * ThermalMath.Span(state.PressureMPa, 8, 22) * ThermalMath.Span(state.HotC, 45, 2200)) : 0;
            // The independent electric compressor can spool during a paid cold start.
            state.CompressorTargetRpm = MaxCompressorRpm * Math.Sqrt(flow);
            Advance(state, seconds);
        }

        public static void Advance(ThermalRotorState state, double seconds)
        {
            if (!ThermalMath.Finite(seconds) || seconds <= 0 || seconds > 1) return;
            state.Phase = Integrate(ref state.Rpm, state.TargetRpm, state.Phase, seconds);
            state.CompressorPhase = Integrate(ref state.CompressorRpm, state.CompressorTargetRpm, state.CompressorPhase, seconds);
        }

        private static double Integrate(ref double rpm, double target, double phase, double seconds)
        {
            double tau = target > rpm ? 4 : 8;
            double decay = Math.Exp(-seconds / tau);
            double turns = (target * seconds + (rpm - target) * tau * (1 - decay)) / 60;
            rpm = target + (rpm - target) * decay;
            if (target == 0 && rpm < .001) rpm = 0;
            return (phase + turns * Math.PI * 2) % (Math.PI * 2);
        }

        public static double CorrectPhase(double local, double remote)
        {
            double delta = Math.Atan2(Math.Sin(remote - local), Math.Cos(remote - local));
            return (local + ThermalMath.Clamp(delta, -.08, .08) + Math.PI * 2) % (Math.PI * 2);
        }

        public static Matrix Pose(int rotor, double phase)
        {
            // Shaft-local mesh, identity-oriented dummy at the authored pivot.
            // Blender +X becomes native -X through SEUT's (-X,Z,Y) mapping.
            Matrix pose = Matrix.CreateRotationX((float)-phase);
            pose.Translation = ThermalModels.RotorPivots[rotor];
            return pose;
        }
    }
}
