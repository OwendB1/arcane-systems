using System;
using Sandbox.ModAPI;
using Sandbox.ModAPI.Interfaces;
using VRage.Game.Components;
using VRage.ModAPI;
using VRage.Utils;
using VRageMath;

[MySessionComponentDescriptor(MyUpdateOrder.AfterSimulation)]
public class LandingProbe : MySessionComponentBase
{
    const long BaseId = 880056000000000;
    const string Api = "ArcaneGimbal.";
    int frame;
    bool finished, steered;
    Vector3D start;
    double lastSpeed, lastAngle, lastDrift, lastGap;

    T Get<T>(int n) where T : class
    {
        IMyEntity entity;
        return MyAPIGateway.Entities.TryGetEntityById(BaseId + n, out entity) ? entity as T : null;
    }

    void Log(string message) { MyLog.Default.WriteLineAndConsole("LANDING " + frame + " " + message); }

    public override void UpdateAfterSimulation()
    {
        if (finished || !MyAPIGateway.Multiplayer.IsServer) return;
        frame++;
        var engine = Get<IMyThrust>(1);
        var helm = Get<IMyRemoteControl>(4);
        var pb = Get<IMyProgrammableBlock>(5);
        if (frame < 60) return;
        if (engine == null || helm == null || pb == null || engine.CubeGrid != helm.CubeGrid || engine.CubeGrid != pb.CubeGrid)
        {
            Log("FAIL incomplete lander"); finished = true; return;
        }
        var grid = engine.CubeGrid;
        var physics = grid.Physics;
        if (frame == 60)
        {
            engine.SetValue<float>(Api + "PitchTrim", 30);
            engine.SetValue<float>(Api + "YawTrim", float.NaN);
            engine.SetValue<float>(Api + "TravelLimit", 20);
        }
        if (frame == 65 || frame == 200)
        {
            Log("CHECK limit=" + engine.GetValue<float>(Api + "TravelLimit") +
                " pitch=" + engine.GetValue<float>(Api + "AppliedPitch") + " yaw=" + engine.GetValue<float>(Api + "AppliedYaw") +
                " idleN=" + engine.GetValue<Vector3D>(Api + "DeliveredForce").Length());
            if (engine.GetValue<float>(Api + "TravelLimit") != 2 ||
                engine.GetValue<float>(Api + "AppliedPitch") != (frame == 65 ? 2 : 0) ||
                engine.GetValue<float>(Api + "AppliedYaw") != 0 || engine.GetValue<Vector3D>(Api + "DeliveredForce") != Vector3D.Zero)
            { Log("FAIL trim/expiry/idle force"); finished = true; return; }
        }
        if (frame < 240) return;
        if (frame == 240)
        {
            double tilt = MathHelper.ToRadians(4f);
            grid.Teleport(MatrixD.CreateWorld(new Vector3D(261018, 0, 0),
                new Vector3D(-Math.Cos(tilt), -Math.Sin(tilt), 0), Vector3D.UnitZ));
            physics.ClearSpeed();
            physics.LinearVelocity = new Vector3(-2, 0, 0);
            helm.DampenersOverride = false;
            start = physics.CenterOfMassWorld;
            pb.Run(pb.CustomName.EndsWith("on") ? "on" : "off");
            Log("RELEASE " + pb.CustomName + " mass=" + physics.Mass + " compileErrors=" + pb.HasCompileErrors);
        }
        var force = engine.GetValue<Vector3D>(Api + "DeliveredForce");
        var gravity = helm.GetNaturalGravity();
        double speed = physics.LinearVelocity.X;
        double angle = Math.Acos(MathHelper.Clamp(Vector3D.Dot(helm.WorldMatrix.Up,
            -Vector3D.Normalize(gravity)), -1, 1)) * 180 / Math.PI;
        var displacement = physics.CenterOfMassWorld - start;
        double drift = Math.Sqrt(displacement.Y * displacement.Y + displacement.Z * displacement.Z);
        // Lowest corner of either skid, measured from the pad's upper surface.
        var basis = grid.WorldMatrix;
        double gap = basis.Translation.X - 261001.25 - 6.25 * Math.Abs(basis.Right.X)
            - 1.25 * Math.Abs(basis.Up.X) - 3.75 * basis.Backward.X;
        if (frame == 240 && (pb.HasCompileErrors || Math.Abs(angle - 4) > .03 || gravity.Length() < 9.7 ||
            Math.Abs(gap - 12.57) > .03 || Math.Abs(speed + 2) > .01 ||
            (pb.CustomName != "Test assist on" && pb.CustomName != "Test assist off")))
        { Log("FAIL release conditions"); finished = true; return; }
        if (Math.Abs(engine.GetValue<float>(Api + "AppliedYaw")) > 0.01f) steered = true;
        if (frame % 60 == 0)
            Log("SAMPLE clearance=" + gap + " tilt=" + angle + " drift=" + drift + " vx=" + speed +
                " thrust=" + engine.CurrentThrust + " vectorN=" + force.Length() +
                " yaw=" + engine.GetValue<float>(Api + "AppliedYaw") + " PB=" + pb.DetailedInfo);
        // Confirm a collision impulse at deck height. Use the last airborne
        // sample to avoid reporting the attitude already changed by impact.
        if (frame > 245 && lastGap < 0.20 && lastGap > -0.20 && speed - lastSpeed > 0.25)
        {
            if (steered != pb.CustomName.EndsWith("on") || !pb.IsWorking || pb.HasCompileErrors || force.LengthSquared() < 1)
            { Log("FAIL steering or power at contact"); finished = true; return; }
            Log("TOUCHDOWN " + pb.CustomName + " tiltDeg=" + lastAngle + " lateralM=" + lastDrift +
                " descentMps=" + -lastSpeed + " clearanceM=" + lastGap + " impactDeltaV=" + (speed - lastSpeed));
            pb.Run("off"); engine.ThrustOverridePercentage = 0; finished = true; return;
        }
        if (frame > 1200) { Log("FAIL no touchdown"); finished = true; return; }
        // Both runs use this vertical-speed governor. Only the PB steers.
        double acceleration = Math.Max(0, -gravity.X + 2 * (-2 - speed));
        double vertical = Math.Max(.5, engine.WorldMatrix.Backward.X);
        if (engine.MaxEffectiveThrust > 0)
            engine.ThrustOverridePercentage = (float)Math.Min(1, physics.Mass * acceleration / (vertical * engine.MaxEffectiveThrust));
        lastSpeed = speed; lastAngle = angle; lastDrift = drift; lastGap = gap;
    }
}
