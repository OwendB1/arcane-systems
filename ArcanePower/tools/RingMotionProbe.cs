using System;
using ArcanePower;
using VRageMath;

class RingMotionProbe
{
    static void Same(Matrix a, Matrix b, string label, float tolerance = .00005f)
    {
        foreach (var axis in new[] { Vector3.Right, Vector3.Up, Vector3.Forward })
            if (Vector3.Distance(Vector3.TransformNormal(axis, a), Vector3.TransformNormal(axis, b)) > tolerance)
                throw new Exception(label);
        if (a.Translation != b.Translation) throw new Exception(label + " pivot");
    }

    static void Main()
    {
        // Preserve the reactor's original rate curve and use that same curve for
        // the battery, including its cosmetic clock wrap and stopped state.
        foreach (float rate in new[] { 0f, .35f, 2f, 3f, 9f })
        foreach (double age in new[] { 0, 1, 137, 311, 7199, 7200, 7201, 36000 })
        {
            float original = rate * (float)(.65 + .20 * Math.Sin(age / 137.0)
                + .15 * Math.Sin(age / 311.0));
            if (Math.Abs(RingMotion.SecondaryRate(rate, age) - original) > .000001f)
                throw new Exception("Shared secondary rate changed reactor motion");
        }
        if (Math.Abs(RingMotion.SecondaryRate(2, 7201) - RingMotion.SecondaryRate(2, 7200)) > .01f)
            throw new Exception("Battery modulation jumps at cosmetic clock wrap");
        Matrix rest = Matrix.CreateFromYawPitchRoll(.31f, -.17f, .2f);
        rest.Translation = new Vector3(2, 3, 4);
        for (int i = 0; i < 4; i++)
        foreach (float tilt in new[] { 0f, .5f, 1f })
        foreach (double phase in new[] { 0, 127.25, 35999.9 })
        {
            var spec = AnimationGeometry.Rings[i];
            // Frozen pre-refactor reactor transform, including startup tilt.
            Matrix previous = rest; previous.Translation = Vector3.Zero;
            previous *= Matrix.CreateFromAxisAngle(spec.Axis, MathHelper.ToRadians(spec.Tilt) * tilt);
            previous *= Matrix.CreateFromAxisAngle(spec.Axis, MathHelper.ToRadians((float)(phase * spec.Speed % 360)));
            var axis = Vector3.Normalize(Vector3.Cross(spec.Axis, Vector3.Up));
            double speed = (.07 + .02 * i) * (i % 2 == 0 ? -1 : 1);
            float angle = MathHelper.WrapAngle(MathHelper.ToRadians((float)(phase * .37 * speed % 360)));
            previous *= Matrix.CreateFromAxisAngle(axis, angle);
            var shared = RingMotion.Orientation(rest, i, tilt, phase, phase * .37);
            Same(previous, shared, "Reactor transform changed");
            Same(shared, RingMotion.Orientation(rest, i, tilt, phase + 36000, phase * .37 + 36000), "Phase wrap jumps");
            foreach (float settle in new[] { 0f, .25f, 1f })
                Same(Matrix.CreateFromAxisAngle(axis, angle * settle),
                    RingMotion.SecondaryRotation(i, phase * .37, settle), "Shutdown secondary transform changed");
        }
        Console.WriteLine("PASS shared reactor/battery ring motion: variable secondary rate, startup tilt, dual axes, shutdown settling and phase wrapping");
    }
}
