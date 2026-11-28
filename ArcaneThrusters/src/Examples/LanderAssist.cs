// Paste into an SE1 programmable block. Tag one upright controller and each
// participating lift engine with [Lander Assist]. Run "on" to level in gravity.
const string Tag = "[Lander Assist]";
const string Api = "ArcaneGimbal.";
readonly List<IMyShipController> controllers = new List<IMyShipController>();
readonly List<IMyThrust> engines = new List<IMyThrust>();

public void Main(string argument, UpdateType source)
{
    if (argument.Equals("off", StringComparison.OrdinalIgnoreCase))
    {
        foreach (var engine in engines)
            if (Eligible(engine)) SetTrim(engine, 0, 0);
        Runtime.UpdateFrequency = UpdateFrequency.None;
        Echo("Assist off");
        return;
    }
    if (argument.Equals("on", StringComparison.OrdinalIgnoreCase))
        Runtime.UpdateFrequency = UpdateFrequency.Update10;
    if (Runtime.UpdateFrequency == UpdateFrequency.None)
    {
        Echo("Run on to engage");
        return;
    }

    GridTerminalSystem.GetBlocksOfType(controllers, c => c.CubeGrid == Me.CubeGrid
        && c.IsWorking && c.CustomName.Contains(Tag));
    GridTerminalSystem.GetBlocksOfType(engines, Eligible);
    var seat = controllers.Count == 1 ? controllers[0] : null;
    var gravity = seat == null ? Vector3D.Zero : seat.GetNaturalGravity();
    bool canLevel = gravity.LengthSquared() > 0.01;
    var correction = Vector3D.Zero;
    if (canLevel)
    {
        var up = seat.WorldMatrix.Up;
        var rate = seat.GetShipVelocities().AngularVelocity;
        // Reject spin about the vertical. Gains produce trim in degrees.
        correction = 80 * Vector3D.Cross(up, -Vector3D.Normalize(gravity))
            - 70 * (rate - up * Vector3D.Dot(rate, up));
    }

    int active = 0;
    foreach (var engine in engines)
    {
        float pitch = 0, yaw = 0;
        var basis = engine.WorldMatrix;
        if (canLevel && engine.IsWorking && Vector3D.Dot(basis.Backward, seat.WorldMatrix.Up) > 0.99
            && engine.GetValue<Vector3D>(Api + "DeliveredForce").LengthSquared() > 1)
        {
            var lever = engine.GetPosition() - seat.CenterOfMass;
            if (lever.LengthSquared() > 0.01)
            {
                var side = Vector3D.Cross(correction, Vector3D.Normalize(lever));
                float limit = engine.GetValue<float>(Api + "TravelLimit");
                pitch = MathHelper.Clamp((float)-Vector3D.Dot(side, basis.Up), -limit, limit);
                yaw = MathHelper.Clamp((float)Vector3D.Dot(side, basis.Right), -limit, limit);
                active++;
            }
        }
        SetTrim(engine, pitch, yaw);
    }
    Echo(seat == null ? "Tag exactly one working controller" :
        !canLevel ? "Standing by for gravity" : "Level assist: " + active + " powered lift engines");
}

bool Eligible(IMyThrust engine)
{
    return engine != null && engine.CubeGrid == Me.CubeGrid && engine.CustomName.Contains(Tag)
        && GridTerminalSystem.CanAccess(engine) && engine.GetProperty(Api + "TravelLimit") != null
        && engine.GetValue<float>(Api + "TravelLimit") > 0;
}

void SetTrim(IMyThrust engine, float pitch, float yaw)
{
    engine.SetValue<float>(Api + "PitchTrim", pitch);
    engine.SetValue<float>(Api + "YawTrim", yaw);
}
