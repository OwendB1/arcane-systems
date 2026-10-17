using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Xml.Serialization;
using ArcanePower;
using VRageMath;

public static partial class ThermalRuntimeChecks
{
    private static int checks;
    private static void Check(bool condition, string message)
    { checks++; if (!condition) throw new Exception(message); }
    private static void Near(double a, double b, string message)
    { Check(Math.Abs(a - b) <= Math.Max(.00001, Math.Abs(b) * 1e-8), message + ": " + a + " != " + b); }

    private static void Registrations()
    {
        var channels = new Dictionary<ushort, string>();
        var owners = new Dictionary<string, List<string>>();
        var sessions = new HashSet<string>();
        foreach (var type in typeof(ThermalModels).Assembly.GetTypes())
        {
            foreach (var field in type.GetFields(BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly))
            {
                if (!field.IsLiteral || field.FieldType != typeof(ushort) || !field.Name.EndsWith("Channel")) continue;
                ushort channel = (ushort)field.GetRawConstantValue();
                string existing;
                Check(!channels.TryGetValue(channel, out existing), "multiplayer channel collision: " + existing + " / " + type.Name + "." + field.Name);
                channels.Add(channel, type.Name + "." + field.Name);
            }
            foreach (var attribute in type.GetCustomAttributesData())
            {
                if (attribute.AttributeType.Name == "MySessionComponentDescriptor") sessions.Add(type.Name);
                if (attribute.AttributeType.Name != "MyEntityComponentDescriptor" || attribute.ConstructorArguments.Count < 3) continue;
                string builder = ((Type)attribute.ConstructorArguments[0].Value).Name;
                foreach (var subtype in (IEnumerable<CustomAttributeTypedArgument>)attribute.ConstructorArguments[2].Value)
                {
                    string name = (string)subtype.Value;
                    List<string> registrations;
                    if (!owners.TryGetValue(name, out registrations)) owners[name] = registrations = new List<string>();
                    registrations.Add(builder);
                }
            }
        }
        Check(channels.Count >= 5, "reactor, core hazards, storage, rotor and flow channels are registered");
        foreach (var model in ThermalModels.All.Values)
        {
            List<string> registrations;
            string builder = model.Kind == ThermalKind.Reactor || model.Kind == ThermalKind.Train
                ? "MyObjectBuilder_Reactor" : "MyObjectBuilder_UpgradeModule";
            Check(owners.TryGetValue(model.Subtype, out registrations) && registrations.Count == 1 && registrations[0] == builder,
                "exactly one compatible game logic registration for " + model.Subtype);
        }
        foreach (string session in new[] { "ThermalSession", "ThermalBuildGuide", "VentSession", "EnergySession", "CoreHazards" })
            Check(sessions.Contains(session), "game loads session: " + session);
    }

    private static List<ThermalUnit> Bank(int heaters, int trains, int recovery, int coolers, int grade = 0)
    {
        var units = new List<ThermalUnit>(); long id = 1;
        foreach (var kind in new[] { ThermalKind.Heater, ThermalKind.Train, ThermalKind.Recuperator, ThermalKind.AirCooler })
        {
            int count = kind == ThermalKind.Heater ? heaters : kind == ThermalKind.Train ? trains : kind == ThermalKind.Recuperator ? recovery : coolers;
            for (int i = 0; i < count; i++) units.Add(new ThermalUnit { Id = id++, Kind = kind, Grade = grade, RatingMW = 100, CoolingMW = kind == ThermalKind.AirCooler ? 60 : 0 });
        }
        return units;
    }

    private static void Budgets()
    {
        Near(ThermalMath.Dispatch(100, 650, Bank(1, 1, 1, 1)).NetMW, 40, "starter");
        Near(ThermalMath.Dispatch(100, 2200, Bank(1, 1, 6, 1, 3)).NetMW, 78, "exotic recovery cap");
        Near(ThermalMath.Dispatch(100, 650, Bank(1, 1, 6, 1, 3)).NetMW, 55, "source temperature gate");
        Near(ThermalMath.Dispatch(200, 650, Bank(2, 2, 2, 2)).NetMW, 80, "two duty trains");
        Near(ThermalMath.Dispatch(200, 650, Bank(1, 2, 1, 1)).NetMW, 40, "extra train does not create heater capacity");
        foreach (int missing in new[] { 0, 1, 2, 3 })
        {
            var counts = new[] { 1, 1, 1, 1 }; counts[missing] = 0;
            Near(ThermalMath.Dispatch(100, 650, Bank(counts[0], counts[1], counts[2], counts[3])).NetMW, 0, "missing required function");
        }
        var redundant = Bank(3, 3, 3, 3);
        var plan = ThermalMath.Dispatch(200, 650, redundant);
        Check(plan.Trains.Count == 2 && plan.Standby == 1, "automatic standby");
        double worst = plan.NetMW;
        foreach (var module in redundant)
        {
            var remaining = new List<ThermalUnit>(redundant); remaining.Remove(module);
            worst = Math.Min(worst, ThermalMath.Dispatch(200, 650, remaining).NetMW);
        }
        Near(worst, 80, "steady-state single-module loss capacity");
        double previous = 0;
        foreach (double offered in new[] { 0.0, 1, 99, 100, 101, 110, 120, 200 })
        {
            double output = ThermalMath.Dispatch(offered, 650, redundant).NetMW;
            Check(output + .00001 >= previous, "demand must not reduce output"); previous = output;
        }
        var exotic = Bank(1, 1, 6, 1, 3);
        exotic.Add(new ThermalUnit { Id = 100, Kind = ThermalKind.Train, RatingMW = 100, Grade = 0 });
        Near(ThermalMath.Dispatch(100, 2200, exotic).NetMW, 78, "adding inferior equipment cannot lower dispatch");
        var oversized = Bank(1, 1, 4, 1);
        oversized.Add(new ThermalUnit { Id = 101, Kind = ThermalKind.Train, RatingMW = 10000, Grade = 3 });
        Near(ThermalMath.Dispatch(100, 650, oversized).NetMW, 55, "oversized spare must not dilute a smaller bank's recovery");
        exotic.Add(new ThermalUnit { Id = 101, Kind = ThermalKind.AirCooler, RatingMW = 100, CoolingMW = 60, ColdC = 200 });
        Near(ThermalMath.Dispatch(100, 2200, exotic).NetMW, 78, "warm extra cooler cannot worsen selected cold bank");
        Near(ThermalMath.AirCooling(60, 0), 0, "vacuum fan cooling");
        Near(ThermalMath.AirCooling(60, .2), 12, "thin atmosphere");
        Near(ThermalMath.RadiativeCooling(60, 0, -270.15), 0, "occluded radiator");
        Near(ThermalMath.RadiativeCooling(60, 1, 35), 0, "warm radiative sink");
        Near(ThermalMath.RadiativeCooling(60, 1, -270.15), 60, "space radiator");
        Check(ThermalMath.Efficiency(0, 1, 650, 80) < .4, "warm inlet derating");
        foreach (double invalid in new[] { -1.0, double.NaN, double.PositiveInfinity })
            Near(ThermalMath.Dispatch(invalid, 650, Bank(1, 1, 1, 1)).NetMW, 0, "invalid offered heat");
    }

    private static void Stores()
    {
        foreach (double eta in new[] { .20, .40, .78 })
        {
            var store = new ThermalStore { EntityId = 1, HotMJ = 40 };
            double admitted = 0, exported = 0, rejected = 0;
            for (int tick = 0; tick < 216000; tick++)
            {
                double demand = tick >= 200000 ? 0 : tick % 12000 < 6000 ? 8 : 2;
                // Exercise native float rounding against production limits.
                double output = (float)Math.Min(demand, ThermalMath.ExportLimit(store, 80, eta, 10, 1.0 / 60));
                Check(ThermalMath.Convert(store, output / 60, eta), "output must have paid heat");
                exported += output / 60;
                if (tick < 80000 || tick >= 80100) rejected += ThermalMath.Reject(store, .15, false);
                admitted += ThermalMath.AdmitHeat(store, 40, 10.0 / 60, 1000000);
                Check(store.Valid(1, 80), "finite bounded inventory");
                if (tick == 100000)
                {
                    var serializer = new XmlSerializer(typeof(ThermalStore));
                    var writer = new StringWriter(); serializer.Serialize(writer, store);
                    store = (ThermalStore)serializer.Deserialize(new StringReader(writer.ToString()));
                    Check(!store.Valid(2, 80), "pasted entity cannot inherit heat");
                }
                if (tick > 210000) Near(ThermalMath.AdmitHeat(store, 40, 1, 1000), 0, "full/no-demand inventory stops fuel use");
            }
            Near(40 + admitted, exported + rejected + store.HotMJ + store.WasteMJ, "one-hour energy conservation including cooling outage/reload");
        }
        var sender = new ThermalStore { EntityId = 1, HotMJ = 100 };
        var receiver = new ThermalStore { EntityId = 2, WasteMJ = 9 };
        Near(ThermalMath.Transfer(sender, receiver, 10, 100, false), 1, "receiver acceptance bounds transfer");
        Near(sender.HotMJ + receiver.HotMJ + receiver.WasteMJ, 109, "transfer conservation");
        Near(ThermalMath.Transfer(sender, sender, 200, 100, false), 0, "no self transfer");
        Near(ThermalMath.Transfer(sender, receiver, double.NaN, 100, false), 0, "invalid receiver capacity rejected");
        Check(!ThermalMath.Convert(receiver, 100, .4), "unfunded native output rejected");
        var lastFuel = new ThermalStore { EntityId = 3 };
        Near(ThermalMath.AdmitHeat(lastFuel, 100, 10, .0001), .0001, "last fuel quantum");
        Near(ThermalMath.AdmitHeat(lastFuel, 100, 10, 0), 0, "exhausted fuel cannot create heat");
        var corrupt = new ThermalStore { EntityId = 3, HotMJ = double.NaN };
        Check(!corrupt.Valid(3, 100), "invalid saved heat rejected");
    }

    private static void ModesAndStartup()
    {
        var state = new ThermalReactorState { Store = new ThermalStore { EntityId = 1 }, Requested = ThermalMode.Brayton };
        state.AdvanceManifolds(false, true, true, 1);
        Near(state.Deployment, 0, "hot interlock");
        state.AdvanceManifolds(true, false, true, 1);
        Near(state.Deployment, 0, "power interlock");
        state.AdvanceManifolds(true, true, false, 1);
        Near(state.Deployment, 0, "native rig interlock");
        for (int tick = 0; tick < 361; tick++) state.AdvanceManifolds(true, true, true, 1.0 / 60);
        Check(state.Settled && state.Mode == ThermalMode.Brayton, "fully deployed mode");
        state.Requested = ThermalMode.Standalone;
        for (int tick = 0; tick < 361; tick++) state.AdvanceManifolds(true, true, true, 1.0 / 60);
        Check(state.Settled && state.Mode == ThermalMode.Standalone, "fully stowed mode");
        Check(state.Valid(1) && !state.Valid(2), "saved mode identity");
        double starting = 0;
        for (int tick = 0; tick < 480; tick++) starting = ThermalMath.StartupSeconds(starting, 2, 0, 1.0 / 60);
        Near(starting, 0, "timer without native power");
        for (int tick = 0; tick < 480; tick++) starting = ThermalMath.StartupSeconds(starting, 2, 2, 1.0 / 60);
        Near(starting, 8, "eight paid startup seconds");
        Near(ThermalMath.StartupSeconds(starting, 2, 0, 1.0 / 60), 0, "blackout resets startup");
        Near(ThermalMath.CirculationPower(0, 0, 100), 0, "unpowered fans and circulation stop");
        Near(ThermalMath.CirculationPower(0, 2, 100), 1, "paid external circulation");
        Near(ThermalMath.CirculationPower(40, 0, 100), 1, "running auxiliaries deducted internally once");
        for (int bay = 0; bay < 4; bay++)
        {
            var anchor = new Vector3((bay < 2 ? 1 : -1) * 4.12f, -2.33f, bay % 2 == 0 ? -2.5f : 2.5f);
            foreach (string part in ThermalManifolds.Parts)
            {
                Check(ThermalManifolds.Pose(bay, part, 0) == Matrix.Identity, "stowed identity pose");
                Vector3 probe = part == "ConnectorTail" ? anchor + new Vector3(.345f, 0, 0) : new Vector3(6, -2, 2);
                Vector3 previous = Vector3.Transform(probe, ThermalManifolds.Pose(bay, part, 0));
                for (int sample = 0; sample <= 46; sample++)
                {
                    double deployment = sample / 46.0;
                    Matrix pose = ThermalManifolds.Pose(bay, part, deployment);
                    Check(pose.IsValid(), "finite manifold pose");
                    if (part == "ConnectorTail") Check(Vector3.Distance(Vector3.Transform(anchor, pose), anchor) < .00001f, "tail stays in fixed guide");
                    if (part == "Carriage" && deployment <= .45) Check(pose == Matrix.Identity, "pipes wait for covers");
                    Vector3 point = Vector3.Transform(probe, pose);
                    Check(Vector3.Distance(previous, point) < .2, "no manifold surface jump");
                    previous = point;
                }
            }
        }
    }

    public static ThermalEndpoint Node(long id, string subtype, Matrix pose)
    {
        var model = ThermalModels.All[subtype];
        var ports = new ThermalPort[model.Ports.Length];
        for (int i = 0; i < ports.Length; i++)
        {
            var p = model.Ports[i];
            ports[i] = new ThermalPort(p.Circuit, Vector3.Transform(p.Position, pose),
                Vector3.TransformNormal(p.Normal, pose), Vector3.TransformNormal(p.HotAxis, pose));
        }
        return new ThermalEndpoint { Id = id, GridId = 1, Healthy = true, Model = model, Ports = ports };
    }

    private static void Topology()
    {
        var layout = Layout();
        var reactor = layout.Find(n => n.Model.Kind == ThermalKind.Reactor);
        var plant = new ThermalNetwork(layout).Plant(reactor);
        Check(plant.Ready, "authored starter layout: " + plant.Diagnostic);
        Check(plant.Nodes.FindAll(n => n.Model.Kind == ThermalKind.Recuperator).Count == 1, "physical recovery path");
        var pipe = layout.Find(n => n.Model.Kind == ThermalKind.Pipe && n.Ports[0].Circuit == "PRIMARY" && n.Ports.Length == 2);
        pipe.GridId = 2;
        Check(!new ThermalNetwork(layout).Plant(reactor).Ready, "split cannot teleport across grids");
        pipe.GridId = 1;
        pipe.Ports[0].HotAxis = -pipe.Ports[0].HotAxis;
        Check(!new ThermalNetwork(layout).Plant(reactor).Ready, "hot/cold roll mismatch rejected");
        pipe.Ports[0].HotAxis = -pipe.Ports[0].HotAxis;
        pipe.Ports[0].Circuit = "CO2_HP";
        Check(!new ThermalNetwork(layout).Plant(reactor).Ready, "pressure type mismatch rejected");
        pipe.Ports[0].Circuit = "PRIMARY";
        var recovery = layout.Find(n => n.Model.Kind == ThermalKind.Recuperator);
        recovery.Healthy = false;
        Check(!new ThermalNetwork(layout).Plant(reactor).Ready, "failed inline recovery isolates generation");
        recovery.Healthy = true;
        var detached = Node(1000, recovery.Model.Subtype, Matrix.CreateTranslation(1000, 1000, 1000));
        layout.Add(detached);
        plant = new ThermalNetwork(layout).Plant(reactor);
        Check(plant.Ready && !plant.Nodes.Contains(detached), "detached module grants no capacity");
        reactor.Healthy = false;
        Check(!new ThermalNetwork(layout).Plant(reactor).Ready, "projected or incomplete source cannot run");
        Check(ThermalModels.All.Count == 31, "all model contracts generated");
    }

    private static void Rotors()
    {
        var cold = new ThermalRotorState { EntityId = 1 };
        for (int i = 0; i < 480; i++) ThermalRotors.Drive(cold, 0, 100, 650, 1, true, 1.0 / 60);
        Near(cold.Rpm, 0, "cold turbine cannot spin from compressor power");
        Check(cold.CompressorRpm > ThermalRotors.MaxCompressorRpm * .8, "paid cold start spools independent compressor");
        Near(cold.PressureMPa, 8, "cold loop has no estimated expansion pressure");
        var warm = new ThermalRotorState { EntityId = 1 };
        var hot = new ThermalRotorState { EntityId = 1 };
        var low = new ThermalRotorState { EntityId = 1 };
        for (int i = 0; i < 3600; i++)
        {
            ThermalRotors.Drive(warm, 50, 100, 650, 1, true, 1.0 / 60);
            ThermalRotors.Drive(hot, 50, 100, 2200, 1, true, 1.0 / 60);
            ThermalRotors.Drive(low, 50, 100, 2200, .25, true, 1.0 / 60);
            Check(hot.Valid(1) && warm.Valid(1) && low.Valid(1), "bounded rotor states and wrapped phases");
        }
        Check(hot.Rpm > warm.Rpm && hot.Rpm > low.Rpm && hot.Rpm > ThermalRotors.MaxRpm * .98,
            "heat and estimated pressure both increase shaft speed");
        Check(low.PressureMPa < hot.PressureMPa, "circulation controls operating pressure");
        double spinning = hot.Rpm;
        ThermalRotors.Drive(hot, 50, 100, 2200, 1, false, 1.0 / 60);
        Check(hot.Rpm > 0 && hot.Rpm < spinning && hot.TargetRpm == 0, "fault or valve closure coasts, never snaps");
        for (int i = 0; i < 7200; i++) ThermalRotors.Drive(hot, 50, 100, 2200, 0, false, 1.0 / 60);
        Near(hot.Rpm, 0, "shutdown reaches rest");
        Near(hot.PressureMPa, 8, "shutdown pressure equalizes");
        Check(!warm.Valid(2), "copied rotor identity rejected");
        var serializer = new XmlSerializer(typeof(ThermalStore));
        var store = new ThermalStore { EntityId = 1, Rotor = warm, HotMJ = 50 };
        var writer = new StringWriter(); serializer.Serialize(writer, store);
        var restored = (ThermalStore)serializer.Deserialize(new StringReader(writer.ToString()));
        Near(restored.Rotor.Phase, warm.Phase, "reload keeps rotor phase");
        Check(restored.Valid(1, 100) && !restored.Valid(2, 100), "rotor storage preserves heat/copy validation");
        foreach (double invalid in new[] { double.NaN, double.PositiveInfinity, -1.0 })
        {
            ThermalRotors.Drive(warm, invalid, 100, 650, 1, true, 1.0 / 60);
            Check(warm.Valid(1) && warm.TargetRpm == 0, "invalid drive input cannot accelerate");
        }
        double phase = warm.Phase;
        ThermalRotors.Advance(warm, double.NaN);
        Near(warm.Phase, phase, "invalid timestep ignored");
        warm.Rpm = double.NaN;
        Check(!warm.Valid(1), "nonfinite snapshot rejected");
        var a = new ThermalRotorState { TargetRpm = ThermalRotors.MaxRpm * .6 };
        var b = new ThermalRotorState { TargetRpm = ThermalRotors.MaxRpm * .6 };
        for (int i = 0; i < 600; i++) ThermalRotors.Advance(a, 1.0 / 60);
        for (int i = 0; i < 1200; i++) ThermalRotors.Advance(b, 1.0 / 120);
        Near(a.Rpm, b.Rpm, "spool rate independent of frame size");
        Near(a.Phase, b.Phase, "integrated phase independent of frame size");
        Check(ThermalRotors.CorrectPhase(6.27, .01) < .02, "network correction wraps shortest arc");
        Check(ThermalRotors.CorrectPhase(1, 4) > .91, "network correction cannot snap a shaft");
        for (int rotor = 0; rotor < 2; rotor++)
            foreach (double angle in new[] { 0.0, .5, 1.0, 2.5, 5.0 })
            {
                Matrix pose = ThermalRotors.Pose(rotor, angle);
                Check(pose.Translation == ThermalModels.RotorPivots[rotor], "native rotor pivot stays fixed");
                Vector3 local = new Vector3(0, 1, 0);
                Vector3 native = Vector3.Transform(local, pose) - pose.Translation;
                Check(Math.Abs(native.Y - Math.Cos(angle)) < .000001 && Math.Abs(native.Z + Math.Sin(angle)) < .000001,
                    "native shaft rotates around mapped Blender X");
            }
    }

    private static void Construction()
    {
        var layout = Layout();
        var source = layout.Find(n => n.Model.Kind == ThermalKind.Reactor);
        var report = ThermalConstruction.Inspect(layout, source.Id);
        Check(report.Verified && report.Open == 0 && report.Wrong == 0 && report.Pending == 0,
            "authored plant passes construction independently of operating mode");
        Check(report.Recovery == 1 && report.Cooling == 1, "only routed recovery/cooling earn construction credit");
        var recovery = layout.Find(n => n.Model.Kind == ThermalKind.Recuperator);
        recovery.Healthy = false;
        report = ThermalConstruction.Inspect(layout, source.Id);
        Check(!report.Verified && report.Pending == 1 && report.Nodes.Count == layout.Count,
            "unfinished block keeps visible topology but prevents verification");
        Check(!recovery.Healthy, "construction scan never mutates authoritative health");
        recovery.Healthy = true;
        var pipe = layout.Find(n => n.Model.Kind == ThermalKind.Pipe && n.Ports.Length == 2 && n.Ports[0].Circuit == "PRIMARY");
        var p = pipe.Ports[0];
        p.HotAxis = -p.HotAxis;
        report = ThermalConstruction.Inspect(layout, source.Id);
        Check(!report.Verified && report.Wrong == 2 && report.Nodes.Count == layout.Count,
            "roll fault identifies both ends and cannot hide downstream construction");
        Check(report.Joints.Exists(j => j.Status == ThermalJointStatus.Roll), "H/C fault is actionable");
        p.HotAxis = -p.HotAxis;
        p.Circuit = "CO2_HP";
        report = ThermalConstruction.Inspect(layout, source.Id);
        Check(!report.Verified && report.Joints.Exists(j => j.Status == ThermalJointStatus.Circuit), "wrong circuit diagnosed");
        p.Circuit = "PRIMARY";
        p.Normal = -p.Normal;
        report = ThermalConstruction.Inspect(layout, source.Id);
        Check(!report.Verified && report.Joints.Exists(j => j.Status == ThermalJointStatus.Facing), "wrong facing diagnosed");
        p.Normal = -p.Normal;
        layout.Remove(pipe);
        report = ThermalConstruction.Inspect(layout, source.Id);
        Check(!report.Verified && report.Open > 0, "missing pipe leaves a visible open route");
        layout.Add(pipe);
        pipe.GridId = 2;
        Check(!ThermalConstruction.Inspect(layout, source.Id).Verified, "no cross-grid construction approval");
        pipe.GridId = 1;
        var detached = Node(1000, recovery.Model.Subtype, Matrix.CreateTranslation(1000, 1000, 1000));
        detached.Healthy = false;
        layout.Add(detached);
        Check(ThermalConstruction.Inspect(layout, source.Id).Verified, "unrelated unfinished assembly does not block this plant");

        ThermalModel straight = null;
        foreach (var model in ThermalModels.All.Values)
            if (model.Kind == ThermalKind.Pipe && model.Subtype.EndsWith("PrimaryStraight")) straight = model;
        Check(straight != null, "standard pipe contract available");
        var neighbours = new List<ThermalEndpoint> {
            ThermalEndpoint.At(2, 1, straight, Matrix.Identity, new Vector3(2.5f, 0, 0), true),
            ThermalEndpoint.At(3, 1, straight, Matrix.Identity, new Vector3(-2.5f, 0, 0), true) };
        var axes = new[] { Vector3.UnitX, -Vector3.UnitX, Vector3.UnitY, -Vector3.UnitY, Vector3.UnitZ, -Vector3.UnitZ };
        int orientations = 0;
        foreach (var forward in axes)
            foreach (var up in axes)
            {
                if (Math.Abs(Vector3.Dot(forward, up)) > .01) continue;
                orientations++;
                Matrix current = Matrix.CreateWorld(Vector3.Zero, forward, up);
                var ghost = ThermalEndpoint.At(1, 1, straight, current, Vector3.Zero, false);
                Matrix suggestion = ThermalConstruction.Suggest(ghost, current, Vector3.Zero, neighbours);
                var corrected = ThermalEndpoint.At(1, 1, straight, suggestion, Vector3.Zero, false);
                Check(ThermalConstruction.Matches(corrected, neighbours) == 2, "orientation guide finds both mates from every grid orientation");
                if (ThermalConstruction.Matches(ghost, neighbours) == 2)
                    Check(suggestion == current, "already aligned preview stays stable");
                Check(!ghost.Healthy && ghost.Ports[0].HotAxis == Vector3.TransformNormal(straight.Ports[0].HotAxis, current),
                    "suggestion never changes preview geometry or build state");
            }
        Check(orientations == 24, "all proper grid rotations checked");
        var candidate = ThermalEndpoint.At(1, 1, straight, Matrix.Identity, Vector3.Zero, false);
        var peer = neighbours[0];
        var joint = new ThermalNetwork(new[] { candidate, peer }).Joints.Find(j => j.Status == ThermalJointStatus.Matched);
        Check(joint != null, "placement uses runtime matcher");
        var matchingPeer = new ThermalPort(joint.Port.Circuit, joint.Port.Position, -joint.Port.Normal, joint.Port.HotAxis);
        Check(ThermalNetwork.Match(candidate, joint.Port, peer, matchingPeer) == ThermalJointStatus.Matched, "valid exact mate");
        matchingPeer.Position += Vector3.UnitY * .17f;
        Check(ThermalNetwork.Match(candidate, joint.Port, peer, matchingPeer) == ThermalJointStatus.Open, "reactor offset cannot be hidden by a permissive snap");
        matchingPeer.Position = joint.Port.Position;
        matchingPeer.Normal.X = float.NaN;
        Check(ThermalNetwork.Match(candidate, joint.Port, peer, matchingPeer) != ThermalJointStatus.Matched, "invalid normals fail closed");
        var crowd = ThermalEndpoint.At(4, 1, straight, Matrix.Identity, new Vector3(2.5f, 0, 0), true);
        Check(ThermalConstruction.Matches(candidate, new[] { peer, crowd }) == 0, "overlapping peers cannot earn an aligned preview");
        report = ThermalConstruction.Inspect(new[] { candidate, peer, crowd }, candidate.Id);
        Check(report.Joints.Exists(j => j.Status == ThermalJointStatus.Crowded) && !report.Verified, "overlapping socket construction rejected");

        // A closed schematic route separates missing functions from open pipes.
        Func<string, int, int, ThermalPort> socket = (c, x, sign) => new ThermalPort(c, new Vector3(x, 0, 0), Vector3.UnitX * sign, Vector3.UnitY);
        var schematic = new List<ThermalEndpoint>();
        ThermalKind[] kinds = { ThermalKind.Reactor, ThermalKind.Heater, ThermalKind.Recuperator, ThermalKind.Train, ThermalKind.AirCooler };
        var ports = new[] {
            new[] { socket("PRIMARY", 0, 1) },
            new[] { socket("PRIMARY", 0, -1), socket("CO2_HP", 1, 1) },
            new[] { socket("CO2_HP", 1, -1), socket("CO2_HP", 2, 1), socket("CO2_LP", 3, -1), socket("CO2_LP", 4, 1) },
            new[] { socket("CO2_HP", 2, -1), socket("CO2_LP", 3, 1) },
            new[] { socket("CO2_LP", 4, -1) } };
        for (int i = 0; i < kinds.Length; i++)
            schematic.Add(new ThermalEndpoint { Id = i + 1, GridId = 1, Healthy = true,
                Model = new ThermalModel { Kind = kinds[i], Ports = ports[i] }, Ports = ports[i] });
        Check(ThermalConstruction.Inspect(schematic, 1).Verified, "closed functional schematic verified");
        schematic[4].Model.Kind = ThermalKind.Pipe;
        report = ThermalConstruction.Inspect(schematic, 1);
        Check(!report.Verified && report.Next.Contains("cooler"), "sealed LP without cooling gets a construction instruction");
        schematic[4].Model.Kind = ThermalKind.AirCooler;
        schematic[2].Model.Kind = ThermalKind.Pipe;
        report = ThermalConstruction.Inspect(schematic, 1);
        Check(!report.Verified && report.Next.Contains("recovery"), "closed route without recovery cannot pass");
    }

    private static void Flow(string evidence)
    {
        var snapshots = new List<string>();
        foreach (var layout in new[] { Layout(), RoomLayout() })
        {
            var observed = new Dictionary<long, byte[]>();
            var network = new ThermalNetwork(layout);
            var source = layout.Find(n => n.Model.Kind == ThermalKind.Reactor);
            Check(network.Plant(source).Ready, "authored circulation layout is closed: " + layout.Count + " blocks, " + network.Plant(source).Diagnostic);
            foreach (string circuit in new[] { "PRIMARY", "CO2_HP", "CO2_LP" })
            {
                ThermalKind from = circuit == "PRIMARY" ? ThermalKind.Reactor : circuit == "CO2_HP" ? ThermalKind.Heater : ThermalKind.Train;
                ThermalKind to = circuit == "PRIMARY" ? ThermalKind.Heater : circuit == "CO2_HP" ? ThermalKind.Train : ThermalKind.AirCooler;
                var starts = new HashSet<long>(); var ends = new HashSet<long>();
                foreach (var n in layout) { if (n.Model.Kind == from) starts.Add(n.Id); if (n.Model.Kind == to) ends.Add(n.Id); }
                var directions = network.FlowDirections(circuit, starts, ends);
                foreach (var item in directions)
                {
                    byte[] values;
                    if (!observed.TryGetValue(item.Key, out values)) observed[item.Key]=values=new byte[item.Value.Length];
                    for (int i=0; i<values.Length; i++) if (item.Value[i]!=0) values[i]=item.Value[i];
                }
                Check(directions.Count > 2, "authored circuit carries flow: " + circuit);
                foreach (var joint in network.Joints)
                {
                    byte[] ports;
                    if (!directions.TryGetValue(joint.Node.Id, out ports)) continue;
                    byte direction = ports[Array.IndexOf(joint.Node.Ports, joint.Port)];
                    if (direction == 0) continue;
                    Check(joint.Status == ThermalJointStatus.Matched, "flow uses matched sockets");
                    Check(joint.Node.Ports.Length > 1 || joint.Node.Model.Kind != ThermalKind.Pipe, "caps have no flow");
                    var mate = Array.FindIndex(joint.Peer.Ports, p => ThermalNetwork.Match(joint.Node, joint.Port, joint.Peer, p) == ThermalJointStatus.Matched);
                    Check(directions.ContainsKey(joint.Peer.Id) && directions[joint.Peer.Id][mate] == 3-direction,
                        "H enters exactly where its peer leaves; C reverses");
                }
            }
            var snapshot = new List<string>();
            foreach (var item in observed)
                snapshot.Add("{\"id\":"+item.Key+",\"ports\":["+string.Join(",",Array.ConvertAll(item.Value,p=>p.ToString()))+"]}");
            snapshots.Add("["+string.Join(",",snapshot)+"]");
            var pipe = layout.Find(n => n.Model.Kind == ThermalKind.Pipe && n.Ports.Length == 2 && n.Ports[0].Circuit == "PRIMARY");
            var a = new HashSet<long> { source.Id };
            var b = new HashSet<long> { layout.Find(n => n.Model.Kind == ThermalKind.Heater).Id };
            pipe.GridId = 2;
            Check(new ThermalNetwork(layout).FlowDirections("PRIMARY", a, b).Count == 0, "split stops room circulation");
            pipe.GridId = 1;
            var port = pipe.Ports[0];
            port.HotAxis = -port.HotAxis;
            Check(new ThermalNetwork(layout).FlowDirections("PRIMARY", a, b).Count == 0, "wrong H/C roll stops circulation");
            port.HotAxis = -port.HotAxis; port.Normal = -port.Normal;
            Check(new ThermalNetwork(layout).FlowDirections("PRIMARY", a, b).Count == 0, "wrong facing stops circulation");
            port.Normal = -port.Normal; port.Circuit = "CO2_HP";
            Check(new ThermalNetwork(layout).FlowDirections("PRIMARY", a, b).Count == 0, "wrong pressure type stops circulation");
        }
        if (evidence != null) File.WriteAllText(evidence,"{\"starter\":"+snapshots[0]+",\"room\":"+snapshots[1]+"}\n");
        Func<int, int, ThermalPort> socket = (x, sign) => new ThermalPort("PRIMARY", new Vector3(x, 0, 0), Vector3.UnitX*sign, Vector3.UnitY);
        Func<long, ThermalPort[], ThermalEndpoint> node = (id, ports) => new ThermalEndpoint {
            Id=id, GridId=1, Healthy=true, Model=new ThermalModel { Kind=ThermalKind.Pipe, Ports=ports }, Ports=ports };
        var branch = new List<ThermalEndpoint> {
            node(1,new[] {socket(0,1)}),
            node(2,new[] {socket(0,-1),socket(1,1),socket(2,1),socket(3,1)}),
            node(3,new[] {socket(1,-1)}), node(4,new[] {socket(2,-1)}), node(5,new[] {socket(3,-1)}) };
        var selected = new ThermalNetwork(branch).FlowDirections("PRIMARY",new HashSet<long> {1},new HashSet<long> {3});
        Check(selected.Count == 3 && !selected.ContainsKey(4) && !selected.ContainsKey(5),
            "standby and capped spurs stay motionless");
        selected = new ThermalNetwork(branch).FlowDirections("PRIMARY",new HashSet<long> {1},new HashSet<long> {3,4});
        Check(selected.Count == 4 && !selected.ContainsKey(5), "selected parallel branches both circulate");
        var diamond = new List<ThermalEndpoint> {
            node(1,new[] {socket(10,1),socket(11,1)}),
            node(2,new[] {socket(10,-1),socket(12,1)}),
            node(3,new[] {socket(11,-1),socket(13,1)}),
            node(4,new[] {socket(12,-1),socket(13,-1)}) };
        selected = new ThermalNetwork(diamond).FlowDirections("PRIMARY",new HashSet<long> {1},new HashSet<long> {4});
        Check(selected.Count == 4 && selected[1][0] == 2 && selected[1][1] == 2, "equal parallel physical routes both circulate");

        Check(ThermalFlowModels.All.Count == 31, "flow contract covers every model");
        foreach (var entry in ThermalFlowModels.All)
        {
            var spec = ThermalModels.All[entry.Key];
            var state = new ThermalFlowState {EntityId=1, Sequence=1, Mode=ThermalFlowMode.Pumping, Rate=1, Heat=.5, Internal=true, Ports=new byte[spec.Ports.Length]};
            for (int i=0; i<state.Ports.Length; i++) state.Ports[i]=1;
            Check(state.Valid(spec.Ports.Length), "valid authoritative flow state");
            foreach (var path in entry.Value)
            {
                Check(path.Length > 0 && ThermalMath.Finite(path.Length), "finite nonzero authored flow path");
                Check(path.Sample(-1) == path.Points[0] && Vector3.Distance(path.Sample(path.Length+1),path.Points[path.Points.Length-1]) < .00001f, "path clamps at tube ends");
                for (int i=1; i<path.Points.Length; i++)
                    Check(Vector3.Distance(path.Sample((path.Distances[i]+path.Distances[i-1])/2),
                        (path.Points[i]+path.Points[i-1])/2) < .0001f, "arc-length sampler stays on authored tube");
                int expected=path.Internal ? 1 : path.Hot ? 1 : -1;
                Check(path.Direction(state)==expected, "H and C counterflow follows socket direction");
                if (!path.Internal)
                {
                    state.Ports[path.Port]=2;
                    Check(path.Direction(state)==-expected, "reversed branch reverses visible flow");
                    state.Ports[path.Port]=1;
                }
                state.Mode=ThermalFlowMode.Ready; state.Rate=0;
                Check(path.Direction(state)==0, "idle network has no particles");
                state.Mode=ThermalFlowMode.Fault;
                Check(path.Direction(state)==0, "fault has no particles");
                state.Mode=ThermalFlowMode.Pumping; state.Rate=1;
            }
            state.Rate=double.NaN; Check(!state.Valid(spec.Ports.Length), "reject NaN flow");
            state.Rate=double.PositiveInfinity; Check(!state.Valid(spec.Ports.Length), "reject infinite flow");
            state.Rate=1; state.Mode=ThermalFlowMode.Ready; Check(!state.Valid(spec.Ports.Length), "reject pumping rate in idle packet");
            state.Rate=0; state.Ports[0]=3; Check(!state.Valid(spec.Ports.Length), "reject malformed port direction");
            state.Ports=new byte[spec.Ports.Length+1]; Check(!state.Valid(spec.Ports.Length), "reject mismatched port count");
        }
    }

    public static void Main(string[] args)
    {
        Registrations(); Budgets(); Stores(); ModesAndStartup(); Topology(); Rotors(); Construction(); Flow(args.Length > 0 ? args[0] : null);
        Console.WriteLine("Thermal runtime: " + checks + " checks passed (registrations/channels, budget, conservation, reload, modes, 47 manifold poses, heat/pressure rotors, construction/orientation guide and authored topology)");
    }
}
