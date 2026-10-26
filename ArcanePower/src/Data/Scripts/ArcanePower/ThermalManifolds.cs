using System;
using VRageMath;

namespace ArcanePower
{
    public static class ThermalManifolds
    {
        public static readonly string[] Parts = { "Carriage", "Intermediate", "CoverMinus", "CoverPlus", "ConnectorTail", "ChamberVent" };
        public static string Name(int bay, string part) { return "Thermal_" + ThermalModels.ManifoldBays[bay] + "_" + part; }

        public static bool CompatibleRest(Matrix rest)
        {
            // Match the native import gate: FBX leaves sub-microradian roundoff.
            const float squared = 1e-10f;
            return Vector3.DistanceSquared(rest.Right, Vector3.Right) <= squared
                && Vector3.DistanceSquared(rest.Up, Vector3.Up) <= squared
                && Vector3.DistanceSquared(rest.Backward, Vector3.Backward) <= squared
                && rest.Translation.LengthSquared() <= squared
                && Math.Abs(rest.M14) <= 1e-5f && Math.Abs(rest.M24) <= 1e-5f
                && Math.Abs(rest.M34) <= 1e-5f && Math.Abs(rest.M44 - 1) <= 1e-5f;
        }

        // Native subpart meshes must be baked in reactor-local stowed space,
        // with identity root dummies. The casting/connector move in Carriage;
        // the long tail gets its own fixed-anchor nonuniform scale.
        public static Matrix Pose(int bay, string part, double deployment)
        {
            if (part == "ChamberVent")
            {
                double ventAngle = bay * Math.PI / 2;
                var hinge = new Vector3((float)(-4.70 * Math.Cos(ventAngle)), -1.270f, (float)(4.70 * Math.Sin(ventAngle)));
                var axis = new Vector3((float)Math.Sin(ventAngle), 0, (float)Math.Cos(ventAngle));
                return Matrix.CreateTranslation(-hinge)
                    * Matrix.CreateFromAxisAngle(axis, (float)(-Math.PI / 2 * ThermalMath.Span(deployment, .15, .90)))
                    * Matrix.CreateTranslation(hinge);
            }
            double pipes = ThermalMath.Span(deployment, .45, 1);
            int side = bay < 2 ? -1 : 1;
            if (part == "Carriage" || part == "Intermediate")
                return Matrix.CreateTranslation((float)(-side * 1.41 * pipes * (part == "Intermediate" ? .5 : 1)), 0, 0);
            if (part == "ConnectorTail")
            {
                Vector3 anchor = new Vector3(-side * 4.12f, -2.33f, bay % 2 == 0 ? -2.5f : 2.5f);
                return Matrix.CreateTranslation(-anchor) * Matrix.CreateScale((float)(1 + 1.41 / .345 * pipes), 1, 1)
                    * Matrix.CreateTranslation(anchor);
            }
            int half = part == "CoverMinus" ? -1 : 1;
            double turn = half * .155 * ThermalMath.Span(deployment, .15, .40);
            double inset = .36 * ThermalMath.Span(deployment, 0, .15);
            double angle = ThermalModels.ManifoldAngles[bay] + turn;
            Matrix pose = Matrix.CreateRotationY((float)turn);
            pose.Translation = new Vector3((float)(inset * Math.Cos(angle)), 0, (float)(-inset * Math.Sin(angle)));
            return pose;
        }
    }
}
