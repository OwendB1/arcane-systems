using System;
using VRageMath;

namespace ArcanePower
{
    public static class ThermalManifolds
    {
        public static readonly string[] Parts = { "Carriage", "Intermediate", "CoverMinus", "CoverPlus", "ConnectorTail" };
        public static string Name(int bay, string part) { return "Thermal_" + ThermalModels.ManifoldBays[bay] + "_" + part; }

        // Native subpart meshes must be baked in reactor-local stowed space,
        // with identity root dummies. The casting/connector move in Carriage;
        // the long tail gets its own fixed-anchor nonuniform scale.
        public static Matrix Pose(int bay, string part, double deployment)
        {
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
