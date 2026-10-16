using System;
using VRageMath;

namespace ArcanePower
{
    // Shared by reactor containment and battery storage: authored tilt, axial
    // spin and an independent secondary axis. Phases wrap at 36,000 unchanged.
    internal static class RingMotion
    {
        internal static float SecondaryRate(float primaryRate, double age)
        {
            return primaryRate * (float)(.65 + .20 * Math.Sin(age / 137.0)
                + .15 * Math.Sin(age / 311.0));
        }

        internal static Matrix Orientation(Matrix rest, int index, float tilt, double primaryPhase, double secondaryPhase)
        {
            var spec = AnimationGeometry.Rings[index];
            rest.Translation = Vector3.Zero;
            rest *= Matrix.CreateFromAxisAngle(spec.Axis, MathHelper.ToRadians(spec.Tilt) * tilt);
            rest *= Matrix.CreateFromAxisAngle(spec.Axis, MathHelper.ToRadians((float)(primaryPhase * spec.Speed % 360.0)));
            return rest * SecondaryRotation(index, secondaryPhase, 1);
        }

        internal static Matrix SecondaryRotation(int index, double phase, float settle)
        {
            Vector3 axis = Vector3.Normalize(Vector3.Cross(AnimationGeometry.Rings[index].Axis, Vector3.Up));
            double speed = (.07 + .02 * index) * (index % 2 == 0 ? -1 : 1);
            float angle = MathHelper.WrapAngle(MathHelper.ToRadians((float)(phase * speed % 360)));
            return Matrix.CreateFromAxisAngle(axis, angle * settle);
        }
    }
}
