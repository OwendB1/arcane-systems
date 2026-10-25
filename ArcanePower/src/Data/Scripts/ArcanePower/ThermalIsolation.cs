using System;
using VRageMath;

namespace ArcanePower
{
    public static class ThermalIsolation
    {
        public const float BoreOffset = .46f, Recess = .30f;
        public static double Step(double opening, bool connected, double seconds)
        {
            if (!ThermalMath.Finite(opening) || !ThermalMath.Finite(seconds) || seconds < 0) return 0;
            double delta = seconds / (connected ? .8 : .35);
            return ThermalMath.Clamp(opening + (connected ? delta : -delta), 0, 1);
        }
        public static Matrix Gate(double opening)
        {
            float angle = (float)(Math.PI * .5 * ThermalMath.Clamp(opening, 0, 1));
            return Matrix.CreateRotationY(angle);
        }
        public static Matrix Seat(ThermalPort port, int bore)
        {
            return Matrix.CreateWorld(port.Position - port.Normal * Recess + port.HotAxis * (bore * BoreOffset),
                -port.Normal, port.HotAxis);
        }
    }
}
