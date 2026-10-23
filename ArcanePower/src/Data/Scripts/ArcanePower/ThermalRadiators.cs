using System;
using ProtoBuf;
using VRageMath;

namespace ArcanePower
{
    [ProtoContract]
    public sealed class ThermalRadiatorState
    {
        [ProtoMember(1)] public long EntityId;
        [ProtoMember(2)] public long Sequence;
        [ProtoMember(3)] public double Angle;
        [ProtoMember(4)] public double Target;
        [ProtoMember(5)] public double Glow;
        [ProtoMember(6)] public double RejectedMW;
        [ProtoMember(7)] public double Exposure;
        [ProtoMember(8)] public double SunIncidence;
        [ProtoMember(9)] public long ParentId;
        [ProtoMember(10)] public int Panels = 1;

        public bool Valid(long id)
        {
            return EntityId == id && Sequence >= 0
                && ThermalMath.Finite(Angle) && Angle >= 0 && Angle < Math.PI * 2
                && ThermalMath.Finite(Target) && Target >= 0 && Target < Math.PI * 2
                && ThermalMath.Finite(Glow) && Glow >= 0 && Glow <= 1
                && ThermalMath.Finite(RejectedMW) && RejectedMW >= 0 && RejectedMW <= 45000.001
                && ParentId >= 0 && Panels >= 1 && Panels <= 3
                && ThermalMath.Finite(Exposure) && Exposure >= 0 && Exposure <= 1
                && ThermalMath.Finite(SunIncidence) && SunIncidence >= 0 && SunIncidence <= 1;
        }
    }

    public static class ThermalRadiators
    {
        public const string Subpart = "Thermal_RadiatorPanels";
        public const double Speed = Math.PI / 60; // Three degrees per second.
        public static Vector3D ExtensionCentre(MatrixD root, int index)
        { return root.Translation + root.Up * (6.25 + 5 * index); }

        public static bool FitsExtension(MatrixD root, MatrixD panel, int index)
        {
            return index >= 0 && index < 2
                && Vector3D.DistanceSquared(panel.Translation, ExtensionCentre(root, index)) < .0001
                && Vector3D.Dot(root.Up, panel.Up) > .99999
                && Vector3D.Dot(root.Right, panel.Right) > .99999;
        }

        public static double Wrap(double angle) { return (angle % (Math.PI * 2) + Math.PI * 2) % (Math.PI * 2); }

        public static double Target(Vector3D localSun, double current)
        {
            // A two-sided vertical panel has identical cooling every half turn.
            // At the pole keep the current angle; every yaw is already edge-on.
            if (!ThermalMath.Finite(localSun.X) || !ThermalMath.Finite(localSun.Z)
                || localSun.X * localSun.X + localSun.Z * localSun.Z < 1e-10) return current;
            return Wrap(Math.Atan2(-localSun.Z, localSun.X));
        }

        public static double Step(double angle, double target, double seconds)
        {
            if (!ThermalMath.Finite(seconds) || seconds <= 0 || seconds > 1) return angle;
            double delta = Math.Atan2(Math.Sin(2 * (target - angle)), Math.Cos(2 * (target - angle))) / 2;
            return Wrap(angle + ThermalMath.Clamp(delta, -Speed * seconds, Speed * seconds));
        }

        public static Matrix Pose(double angle, bool extension = false)
        {
            Matrix pose = Matrix.CreateRotationY((float)angle);
            pose.Translation = extension ? Vector3.Zero : new Vector3(0, -1.1f, 0);
            return pose;
        }

        public static double Cooling(double rating, double exposure, double sinkC, double sunIncidence)
        {
            if (!ThermalMath.Finite(sunIncidence)) return 0;
            // Gameplay solar-load penalty: broadside loses 35%, edge-on keeps
            // rated rejection. Both faces still require a clear view of space.
            return ThermalMath.RadiativeCooling(rating, exposure, sinkC)
                * (1 - .35 * ThermalMath.Clamp(Math.Abs(sunIncidence), 0, 1));
        }

        public static double HeatGlow(double previous, double rejectedMW, double rating, double seconds)
        {
            double target = rating > 0 ? ThermalMath.Clamp(rejectedMW / rating, 0, 1) : 0;
            return target + (previous - target) * Math.Exp(-seconds / 3);
        }
    }
}
