using System;
using System.Collections.Generic;
using VRageMath;

namespace ArcanePower
{
    // A commissioned charge belongs to one sealed circuit, including its pipes.
    // Changes refill that circuit only. Reloads require fresh paid commissioning.
    public sealed class ThermalCommissioning
    {
        private readonly long grid;
        private readonly HashSet<long> machines = new HashSet<long>();
        public double Seconds;
        public ThermalCommissioning(long gridId, IList<ThermalUnit> units)
        {
            grid = gridId;
            foreach (var unit in units) machines.Add(unit.Id);
        }
        public bool Covers(long gridId, IList<ThermalUnit> units)
        {
            if (grid != gridId || units.Count != machines.Count) return false;
            foreach (var unit in units)
                if (!machines.Contains(unit.Id)) return false;
            return true;
        }
    }

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
