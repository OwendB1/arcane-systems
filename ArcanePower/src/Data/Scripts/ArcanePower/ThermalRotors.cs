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
        // ProtoMember(9) was cosmetic pressure; retired, never reuse.
        [ProtoMember(10)] public double HotC = 45;

        public bool Valid(long id)
        {
            return Valid(id, ThermalRotors.MaxRpm);
        }

        public void MigrateSavedRpm(long id)
        {
            // Accept the former 4000 RPM save range without weakening packet validation.
            if (!Valid(id, 4000)) return;
            Rpm = Math.Min(Rpm, ThermalRotors.MaxRpm);
            CompressorRpm = Math.Min(CompressorRpm, ThermalRotors.MaxCompressorRpm);
            TargetRpm = Math.Min(TargetRpm, ThermalRotors.MaxRpm);
            CompressorTargetRpm = Math.Min(CompressorTargetRpm, ThermalRotors.MaxCompressorRpm);
        }

        private bool Valid(long id, double maximumRpm)
        {
            return EntityId == id && Sequence >= 0
                && ThermalMath.Finite(Phase) && Phase >= 0 && Phase < Math.PI * 2
                && ThermalMath.Finite(CompressorPhase) && CompressorPhase >= 0 && CompressorPhase < Math.PI * 2
                && ThermalMath.Finite(Rpm) && Rpm >= 0 && Rpm <= maximumRpm
                && ThermalMath.Finite(TargetRpm) && TargetRpm >= 0 && TargetRpm <= maximumRpm
                && ThermalMath.Finite(CompressorRpm) && CompressorRpm >= 0 && CompressorRpm <= maximumRpm
                && ThermalMath.Finite(CompressorTargetRpm) && CompressorTargetRpm >= 0 && CompressorTargetRpm <= maximumRpm
                && ThermalMath.Finite(HotC) && HotC >= 45 && HotC <= 2200;
        }
    }

    // Cosmetic state only: this never grants power or consumes/creates MJ.
    // Electrical load drives the shafts; visual inertia never grants MW.
    public static class ThermalRotors
    {
        public const double IdleRpm = 10, MaxRpm = 200, MaxCompressorRpm = MaxRpm;
        private const double IdleRampSeconds = 5;
        public static void Drive(ThermalRotorState state, double load, double hotC, bool running, double seconds)
        {
            if (!ThermalMath.Finite(seconds) || seconds <= 0 || seconds > 1) return;
            bool valid = running && ThermalMath.Finite(load) && load >= 0 && ThermalMath.Finite(hotC);
            double demand = valid ? ThermalMath.Clamp(load, 0, 1) : 0;
            state.HotC = 45 + (valid ? ThermalMath.Clamp(hotC, 45, 2200) - 45 : 0) * demand;
            state.TargetRpm = valid ? IdleRpm + (MaxRpm - IdleRpm) * demand : 0;
            state.CompressorTargetRpm = state.TargetRpm;
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
            double turns = 0;
            if (rpm < IdleRpm && target == IdleRpm)
            {
                // Unloaded startup takes five seconds to idle. Any load uses
                // the normal response immediately, with no idle-speed gate.
                double acceleration = IdleRpm / IdleRampSeconds;
                double startupSeconds = Math.Min(seconds, (IdleRpm - rpm) / acceleration);
                double next = Math.Min(IdleRpm, rpm + acceleration * startupSeconds);
                turns = (rpm + next) * .5 * startupSeconds / 60;
                rpm = next;
                seconds -= startupSeconds;
            }
            double tau = target > rpm ? 4 : 8;
            double decay = Math.Exp(-seconds / tau);
            turns += (target * seconds + (rpm - target) * tau * (1 - decay)) / 60;
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
