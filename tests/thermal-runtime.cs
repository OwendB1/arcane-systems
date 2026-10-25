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

    private static IEnumerable<Matrix> Orientations()
    {
        var axes = new[] { Vector3.UnitX, -Vector3.UnitX, Vector3.UnitY, -Vector3.UnitY, Vector3.UnitZ, -Vector3.UnitZ };
        foreach (var forward in axes)
            foreach (var up in axes)
                if (Math.Abs(Vector3.Dot(forward, up)) < .1f)
                    yield return Matrix.CreateWorld(Vector3.Zero, forward, up);
    }

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

    private static List<ThermalUnit> Bank(int trains, int coolers, int grade = 0)
    {
        var units = new List<ThermalUnit>(); long id = 1;
        foreach (var kind in new[] { ThermalKind.Train, ThermalKind.AirCooler })
            for (int i = 0; i < (kind == ThermalKind.Train ? trains : coolers); i++)
                units.Add(new ThermalUnit { Id = id++, Kind = kind, Grade = grade, RatingMW = 100, CoolingMW = kind == ThermalKind.AirCooler ? 60 : 0 });
        return units;
    }

    private static void Budgets()
    {
        double[] temperatures = { 650, 1000, 1600, 2200 };
        double[] ceilings = { 40, 55, 66, 78 };
        for (int tier = 0; tier < 4; tier++)
            for (int count = 1; count <= 4; count++)
            {
                double net = 0;
                for (int circuit = 0; circuit < count; circuit++)
                {
                    var point = ThermalMath.Dispatch(ThermalLoops.Allocation(100), temperatures[tier], Bank(1, 2, tier));
                    Near(point.Efficiency, ceilings[tier] / 100, "surviving circuits preserve fuel/turbine efficiency");
                    net += point.NetMW;
                }
                Near(net, ceilings[tier] * count / 4, "capacity scales linearly across four fixed circuit allocations");
            }
        Near(ThermalMath.Dispatch(100, 650, Bank(1, 2, 3)).NetMW, 40, "source temperature gates higher tiers");
        Check(ThermalMath.Dispatch(200, 650, Bank(2, 2)).NetMW == 0, "two turbines cannot share one manifold circuit");
        var smallCooling = Bank(1, 1); smallCooling[1].CoolingMW = 30;
        var undersized = ThermalMath.Dispatch(100, 650, smallCooling);
        Near(undersized.NetMW, 40, "cooling shortage does not silently throttle away the heat hazard");
        Check(undersized.RequiredCoolingMW > undersized.CoolingMW && undersized.SustainableMW < undersized.NetMW,
            "undersized circuit exposes unsafe rejection");
        Near(ThermalMath.Dispatch(200, 650, Bank(1, 2)).NetMW, 40, "turbine rating still limits its own circuit");
        Near(ThermalMath.Dispatch(100, 650, Bank(0, 1)).NetMW, 0, "train required");
        Near(ThermalMath.Dispatch(100, 650, Bank(1, 0)).NetMW, 0, "cooler required");
        double previous = 0;
        foreach (double offered in new[] { 0.0, 1, 25, 50, 100, 200 })
        {
            double output = ThermalMath.Dispatch(offered, 650, Bank(1, 2)).NetMW;
            Check(output + .00001 >= previous, "demand must not reduce output"); previous = output;
        }
        var blockedT3 = ThermalMath.Dispatch(100, 2200, Bank(1, 2));
        Near(blockedT3.NetMW, 0, "standard hot section cannot bypass T3 gate");
        Check(blockedT3.Limit.Contains("upgraded"), "T3 gate reports required hardware");
        var exotic = Bank(1, 1, 3);
        Near(ThermalMath.Dispatch(100, 2200, exotic).NetMW, 78, "one exotic circuit retains its grade efficiency");
        exotic.Add(new ThermalUnit { Id = 101, Kind = ThermalKind.AirCooler, RatingMW = 100, CoolingMW = 60, ColdC = 200 });
        Near(ThermalMath.Dispatch(100, 2200, exotic).NetMW, 78, "warm extra cooling cannot worsen a cold circuit");
        Near(ThermalMath.AirCooling(60, 0, 1), 0, "vacuum fan cooling");
        Near(ThermalMath.AirCooling(60, .2, 1), 12, "thin atmosphere");
        Near(ThermalMath.AirCooling(60, 1, 1), 60, "unobstructed exhaust");
        Near(ThermalMath.AirCooling(60, 1, 0), 0, "sealed exhaust stops rejection");
        Near(ThermalMath.AirCooling(60, 1, .5), 15, "half-clear exhaust sharply derates shared plenum");
        Near(ThermalMath.AirCooling(60, .2, .5), 3, "density and backpressure combine");
        Near(ThermalMath.AirCooling(60, 4, 2), 60, "air cooling cannot exceed rating");
        Near(ThermalMath.AirCooling(60, 1, -1), 0, "negative clearance is blocked");
        Near(ThermalMath.AirCooling(60, 1, double.NaN), 0, "invalid clearance fails closed");
        Near(ThermalMath.AirCooling(double.PositiveInfinity, 1, 1), 0, "invalid rating fails closed");
        var blockedBank = Bank(1, 1);
        blockedBank[1].CoolingMW = ThermalMath.AirCooling(60, 1, 0);
        var blocked = ThermalMath.Dispatch(100, 650, blockedBank);
        Near(blocked.SustainableMW, 0, "blocked cooler cannot sustain generation");
        Check(blocked.AcceptedMW > 0 && blocked.RequiredCoolingMW > 0, "blocked exhaust leaves a dangerous running reaction");
        blockedBank[1].CoolingMW = ThermalMath.AirCooling(60, 1, 1);
        Check(ThermalMath.Dispatch(100, 650, blockedBank).NetMW > 0, "cleared exhaust restores dispatch");
        Check(ThermalModels.AirCoolerExhaustSamples.Length == 18, "both fan discs are sampled");
        foreach (var sample in ThermalModels.AirCoolerExhaustSamples)
        {
            Check(sample.Z < -3.06f && Math.Abs(sample.X) < 3.2f && Math.Abs(sample.Y) < 1.1f,
                "native exhaust probes are outside guards and inside fan discs");
            foreach (var rotation in Orientations())
            {
                var transformed = Vector3.TransformNormal(sample, rotation);
                var normal = Vector3.TransformNormal(Vector3.Forward, rotation);
                Check(Vector3.Dot(transformed, normal) > 3.06f, "exhaust follows block orientation");
            }
        }
        Near(ThermalMath.RadiativeCooling(60, 0, -270.15), 0, "occluded radiator");
        Near(ThermalMath.RadiativeCooling(60, 1, 35), 0, "warm radiative sink");
        Near(ThermalMath.RadiativeCooling(60, 1, -270.15), 60, "space radiator");
        Check(ThermalMath.Efficiency(0, 650, 80) < .4, "warm inlet derating");
        foreach (double invalid in new[] { -1.0, double.NaN, double.PositiveInfinity })
            Near(ThermalMath.Dispatch(invalid, 650, Bank(1, 1)).NetMW, 0, "invalid offered heat");
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

    private static void CoolingFailure()
    {
        // Run the paid-heat path at native tick rate. Cooling buffers may delay
        // the hazard, but cannot erase waste or turn an undersized loop safe.
        foreach (double rejectionMW in new[] { 60.0, 30.0, 0.0 })
            foreach (int response in new[] { 0, 1, 2 })
            {
                // Also prove that delayed restoration cannot undo a threshold
                // already crossed during the core's thermal response.
                if (response == 2 && rejectionMW != 0) continue;
                bool recover = response != 0;
                var source = new ThermalStore { EntityId = 1, HotMJ = 400 };
                var cooler = new ThermalStore { EntityId = 2 };
                var trains = new List<ThermalStore>();
                for (int i = 0; i < 4; i++) trains.Add(new ThermalStore { EntityId = 3 + i });
                double admitted = 0, exported = 0, rejected = 0;
                float heat = 0;
                bool critical = false, restored = false;
                for (int tick = 0; tick < 24000; tick++)
                {
                    // Restore cooling when the core warning appears, before
                    // crossing the irreversible threshold. Elapsed time alone
                    // is not a safe recovery guarantee for every shortfall.
                    restored |= recover && (heat >= 1 || (response == 1 && ThermalMath.WasteHeatLevel(source, 100) >= 1));
                    double cooling = restored ? 120 : rejectionMW;
                    foreach (var train in trains)
                    {
                        double delivered = (float)ThermalMath.ExportLimit(train, 800, .4, 10, 1.0 / 60) / 60;
                        Check(ThermalMath.Convert(train, delivered, .4), "overload output remains paid");
                        exported += delivered;
                    }
                    rejected += ThermalMath.Reject(cooler, cooling / 60, false);
                    foreach (var train in trains)
                        ThermalMath.Transfer(train, source, 800, 100.0 / 60, true);
                    // Increasing rejection also supplies the second unit's
                    // transport capacity, as the actual connected bank does.
                    if (cooling > 0)
                        ThermalMath.Transfer(source, cooler, 800, (cooling > 60 ? 200 : 100.0) / 60, true);
                    foreach (var train in trains)
                        ThermalMath.Transfer(source, train, 800, 25.0 / 60, false);
                    double fresh = ThermalMath.AdmitReactionHeat(source, 100, 100.0 / 60, 1e9);
                    admitted += fresh;
                    double target = Math.Max(fresh * 60 / 100, ThermalMath.WasteHeatLevel(source, 100));
                    heat = (float)ThermalMath.ApproachCoreHeat(heat, target, false);
                    critical |= heat >= 1.25;
                    Check(source.Valid(1, 800) && cooler.Valid(2, 800), "reactor/receiver remain bounded during cooling loss");
                    if (tick == 2400)
                    {
                        var saved = new ThermalReactorState { Mode = ThermalMode.Brayton, Requested = ThermalMode.Brayton,
                            Deployment = 1, Store = source, CoolingMW = cooling, RequiredCoolingMW = 60 };
                        var serializer = new XmlSerializer(typeof(ThermalReactorState));
                        var writer = new StringWriter(); serializer.Serialize(writer, saved);
                        var loaded = (ThermalReactorState)serializer.Deserialize(new StringReader(writer.ToString()));
                        Check(loaded.Valid(1), "cooling diagnostics and trapped heat survive reload");
                        Near(loaded.Store.WasteMJ, source.WasteMJ, "reload cannot discard waste");
                        Near(loaded.RequiredCoolingMW, 60, "cooling requirement survives reload");
                        source = loaded.Store;
                    }
                }
                double retained = source.HotMJ + source.WasteMJ + cooler.HotMJ + cooler.WasteMJ;
                foreach (var train in trains) { retained += train.HotMJ + train.WasteMJ; Check(train.Valid(train.EntityId, 800), "train stays bounded"); }
                Near(400 + admitted, exported + rejected + retained, "cooling failure/recovery conserves every paid MJ");
                if (rejectionMW >= 60 || response == 1)
                {
                    Check(!critical && heat <= 1.0001, "adequate/restored cooling avoids supercriticality: cooling="
                        + rejectionMW + ", heat=" + heat + ", restored=" + restored);
                    Near(source.WasteMJ, 0, "restored cooling drains returned waste");
                }
                else Check(critical, "persistent or belatedly restored cooling deficit must cross the existing 125% failure threshold: cooling="
                    + rejectionMW + ", heat=" + heat + ", hot=" + source.HotMJ + ", waste=" + source.WasteMJ);
            }
        var hot = new ThermalStore { EntityId = 1, WasteMJ = 800 };
        Near(ThermalMath.AdmitReactionHeat(hot, 100, 100, 100), 0, "full reactor stops fresh fuel without clearing heat");
        Check(ThermalMath.WasteHeatLevel(hot, 100) > 1.25, "full retained waste remains dangerous after fuel cutoff");
        var idle = new ThermalStore { EntityId = 1, HotMJ = 400 };
        Near(ThermalMath.AdmitReactionHeat(idle, 100, 100, 100), 0, "no-load hot reserve stops fuel use");
        Near(ThermalMath.WasteHeatLevel(idle, 100), 0, "ordinary warm inventory does not manufacture a cooling failure");
        Near(ThermalMath.AdmitReactionHeat(new ThermalStore(), 100, 100, 0), 0, "no unpaid reaction heat");
        var bad = new ThermalReactorState { Store = new ThermalStore { EntityId = 1 }, CoolingMW = double.NaN };
        Check(!bad.Valid(1), "invalid replicated cooling rejected");
        bad.CoolingMW = 0; bad.RequiredCoolingMW = double.PositiveInfinity;
        Check(!bad.Valid(1), "invalid cooling requirement rejected");
        foreach (double ceiling in new[] { .4, .55, .66, .78 })
            for (int count = 1; count <= 4; count++)
            {
                double eta = ceiling;
                double circulation = 1;
                for (int tick = 0; tick < 600; tick++)
                    circulation = ThermalMath.CirculationPower(100 * eta * circulation, eta, 0, 100);
                Near(circulation, 1, "every bank sustains circulation from internally paid auxiliaries at full demand");
            }
        Near(ThermalMath.CirculationPower(78, .78, 0, 100), 1, "four oversized trains use dispatched heat, not summed nameplate rating, for circulation");
        Near(ThermalMath.CirculationPower(4, .16, 0, 100), .625, "partial load uses actual paid conversion heat");
        foreach (double eta in new[] { 0, -1, 1, double.NaN, double.PositiveInfinity })
        {
            Near(ThermalMath.CirculationPower(40, eta, 0, 100), 0, "invalid efficiency cannot create internal power");
            Near(ThermalMath.CirculationPower(0, eta, 2, 100), 1, "external cooldown power remains metered without conversion");
        }
    }

    private static void ModesAndStartup()
    {
        // Actual native importer roundoff used to reject every manifold rig.
        Matrix nativeRest = Matrix.Identity;
        nativeRest.M12 = 8.742284e-8f; nativeRest.M13 = 3.89414367e-7f;
        nativeRest.M21 = -8.742278e-8f; nativeRest.M23 = -1.62920685e-7f;
        nativeRest.M31 = -3.894144e-7f; nativeRest.M32 = 1.62920657e-7f;
        Check(ThermalManifolds.CompatibleRest(nativeRest), "native manifold roundoff remains compatible");
        Matrix badRest = nativeRest; badRest.M41 = .001f;
        Check(!ThermalManifolds.CompatibleRest(badRest), "reject shifted manifold origins");
        badRest = nativeRest; badRest.M11 = float.NaN;
        Check(!ThermalManifolds.CompatibleRest(badRest), "reject invalid manifold transforms");
        Check(!ThermalManifolds.CompatibleRest(Matrix.CreateRotationY(.01f)), "reject genuinely rotated manifold rigs");
        var guideState = new ThermalReactorState();
        var guideCheck = new ThermalBuildCheck();
        Check(!ThermalConstruction.ShowReactorGuide(null, guideCheck), "no reactor guide without operating state");
        Check(!ThermalConstruction.ShowReactorGuide(guideState, guideCheck), "hide reactor connections in standalone");
        guideState.Requested = ThermalMode.Brayton;
        Check(!ThermalConstruction.ShowReactorGuide(guideState, guideCheck), "hide reactor guide while entering Brayton");
        guideState.Mode = ThermalMode.Brayton; guideState.Deployment = 1;
        Check(ThermalConstruction.ShowReactorGuide(guideState, guideCheck), "show incomplete Brayton connections");
        guideCheck.Verified = true;
        Check(!ThermalConstruction.ShowReactorGuide(guideState, guideCheck), "hide verified Brayton connection guide");
        guideCheck.Verified = false; guideState.Requested = ThermalMode.Standalone;
        Check(!ThermalConstruction.ShowReactorGuide(guideState, guideCheck), "hide reactor guide while leaving Brayton");
        var state = new ThermalReactorState { Store = new ThermalStore { EntityId = 1 }, Requested = ThermalMode.Brayton };
        Check(state.TransitionHint(true, true, false).Contains("incompatible"), "report missing manifold rig");
        Check(state.TransitionHint(false, true, true).Contains("trapped heat"), "report cooling interlock");
        Check(state.TransitionHint(true, false, true).Contains("controllers"), "report manifold motor power interlock");
        Check(state.TransitionHint(true, true, true).Contains("Deploying"), "report active deployment");
        state.AdvanceManifolds(false, true, true, 1);
        Near(state.Deployment, 0, "hot interlock");
        state.AdvanceManifolds(true, false, true, 1);
        Near(state.Deployment, 0, "power interlock");
        state.AdvanceManifolds(true, true, false, 1);
        Near(state.Deployment, 0, "native rig interlock");
        for (int tick = 0; tick < 361; tick++) state.AdvanceManifolds(true, true, true, 1.0 / 60);
        Check(state.Settled && state.Mode == ThermalMode.Brayton, "fully deployed mode");
        Check(state.TransitionHint(true, true, true) == null, "settled mode has no transition warning");
        state.Requested = ThermalMode.Standalone;
        Check(state.TransitionHint(true, true, true).Contains("Retracting"), "report active retraction");
        for (int tick = 0; tick < 361; tick++) state.AdvanceManifolds(true, true, true, 1.0 / 60);
        Check(state.Settled && state.Mode == ThermalMode.Standalone, "fully stowed mode");
        Check(state.Valid(1) && !state.Valid(2), "saved mode identity");
        Near(ThermalMath.CirculationPower(0, .4, 0, 100), 0, "unpowered fans and circulation stop");
        Near(ThermalMath.CirculationPower(0, .4, 2, 100), 1, "paid external circulation");
        Near(ThermalMath.CirculationPower(40, .4, 0, 100), 1, "running auxiliaries deducted internally once");
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
        Check(!plant.Ready, "legacy shared starter layout requires separate turbine/cooling circuits");
        Check(new ThermalNetwork(layout).Joints.Exists(j => j.Peer != null && j.Peer.Model.Kind == ThermalKind.Train), "legacy turbine geometry still mates");
        var turbine = layout.Find(n => n.Model.Kind == ThermalKind.Train);
        var pipe = new ThermalNetwork(layout).Joints.Find(j => j.Peer == turbine && j.Node.Model.Kind == ThermalKind.Pipe).Node;
        pipe.GridId = 2;
        Check(!new ThermalNetwork(layout).Plant(reactor).Ready, "split cannot teleport across grids");
        pipe.GridId = 1;
        pipe.Ports[0].HotAxis = -pipe.Ports[0].HotAxis;
        Check(!new ThermalNetwork(layout).Plant(reactor).Ready, "hot/cold roll mismatch rejected");
        pipe.Ports[0].HotAxis = -pipe.Ports[0].HotAxis;
        turbine.Healthy = false;
        Check(!new ThermalNetwork(layout).Plant(reactor).Ready, "failed turbine isolates generation");
        turbine.Healthy = true;
        var detached = Node(1000, turbine.Model.Subtype, Matrix.CreateTranslation(1000, 1000, 1000));
        layout.Add(detached);
        plant = new ThermalNetwork(layout).Plant(reactor);
        Check(!plant.Ready && !plant.Nodes.Contains(detached), "detached machinery cannot commission a legacy shared plant");
        reactor.Healthy = false;
        Check(!new ThermalNetwork(layout).Plant(reactor).Ready, "projected or incomplete source cannot run");
        Check(ThermalModels.All.Count == 55, "all model contracts generated");
    }

    private static void UniversalPipes()
    {
        int aliases = 0;
        foreach (var model in ThermalModels.All.Values)
        {
            if (model.Kind != ThermalKind.Pipe) continue;
            foreach (var port in model.Ports) Check(port.Circuit == "CO2", "every pipe ID is pressure-independent");
            if (!model.Subtype.Contains("CO2Hp") && !model.Subtype.Contains("CO2Lp")) continue;
            aliases++;
            var canonical = ThermalModels.All[model.Subtype.Replace("CO2Hp", "Primary").Replace("CO2Lp", "Primary")];
            Check(model.Cells == canonical.Cells && model.Ports.Length == canonical.Ports.Length, "legacy pipe preserves footprint");
            for (int i = 0; i < model.Ports.Length; i++)
                Check(model.Ports[i].Position == canonical.Ports[i].Position && model.Ports[i].Normal == canonical.Ports[i].Normal
                    && model.Ports[i].HotAxis == canonical.Ports[i].HotAxis, "legacy pipe preserves socket geometry");
            var paths = ThermalFlowModels.All[model.Subtype];
            var shared = ThermalFlowModels.All[canonical.Subtype];
            Check(paths.Length == shared.Length, "legacy flow uses canonical mesh paths");
            for (int i = 0; i < paths.Length; i++)
            {
                Check(paths[i].Circuit == "CO2" && paths[i].Points.Length == shared[i].Points.Length, "legacy flow is universal");
                for (int j = 0; j < paths[i].Points.Length; j++) Check(paths[i].Points[j] == shared[i].Points[j], "legacy flow remains inside shared glass");
            }
        }
        Check(aliases == 28, "all former HP/LP IDs retain runtime ownership");
        foreach (var layout in new[] { Layout(), BareLayout(), RoomLayout() })
        {
            foreach (var node in layout)
            {
                if (node.Model.Kind != ThermalKind.Pipe || node.Model.Subtype.Contains("ReactorAdapter")) continue;
                node.Model = ThermalModels.All[node.Model.Subtype.Replace("Primary", node.Id % 2 == 0 ? "CO2Hp" : "CO2Lp")];
            }
            var source = layout.Find(n => n.Model.Kind == ThermalKind.Reactor);
            Check(!new ThermalNetwork(layout).Plant(source).Ready, "legacy aliases cannot bypass independent circuit topology");
            Check(!ThermalConstruction.Inspect(layout, source.Id).Verified, "legacy shared layout requests independent circuit plumbing");
        }

        foreach (var model in ThermalModels.All.Values)
        {
            if (model.Kind == ThermalKind.Train) Check(model.Ports.Length == 1, "every turbine is a single-socket terminal, never an inline series stage");
            if (model.Subtype.Contains("Mirrored"))
            {
                var original = ThermalModels.All[model.Subtype.Replace("Mirrored", "")];
                Check(model.Cells == original.Cells && model.Grade == original.Grade && model.RatingMW == original.RatingMW,
                    "mirrored turbine keeps footprint and performance");
                var a = model.Ports[0]; var b = original.Ports[0];
                Check(a.Position == new Vector3(b.Position.X,b.Position.Y,-b.Position.Z)
                    && a.Normal == -b.Normal && a.HotAxis == b.HotAxis, "mirroring changes the socket side without swapping H/C");
            }
            var axes = new[] {Vector3.UnitX,-Vector3.UnitX,Vector3.UnitY,-Vector3.UnitY,Vector3.UnitZ,-Vector3.UnitZ};
            foreach (var forward in axes) foreach (var up in axes)
            {
                if (Math.Abs(Vector3.Dot(forward,up)) > .01) continue;
                var pose = Matrix.CreateWorld(Vector3.Zero,forward,up);
                var block = ThermalEndpoint.At(1,1,model,pose,Vector3.Zero,true);
                var peer = new ThermalEndpoint {Id=2,GridId=1,Model=new ThermalModel()};
                foreach (var port in block.Ports)
                {
                    peer.Model.Kind=port.ReactorOnly?ThermalKind.Reactor:ThermalKind.Pipe;
                    var other = new ThermalPort("CO2",port.Position,-port.Normal,port.HotAxis);
                    Check(ThermalNetwork.Match(block,port,peer,other) == ThermalJointStatus.Matched, "every rotated face accepts aligned H/C from an allowed peer");
                    other.HotAxis = -other.HotAxis;
                    Check(ThermalNetwork.Match(block,port,peer,other) == ThermalJointStatus.Roll, "every rotated face rejects exchanged hot and cold bores");
                }
            }
        }
        Func<int, int, ThermalPort> socket = (x, sign) => new ThermalPort("CO2",new Vector3(x,0,0),Vector3.UnitX*sign,Vector3.UnitY);
        Func<long, ThermalKind, ThermalPort[], ThermalEndpoint> nodeAt = (id, kind, ports) => new ThermalEndpoint {
            Id=id, GridId=1, Healthy=true, Model=new ThermalModel { Kind=kind, Ports=ports }, Ports=ports };
        var sourceNode = nodeAt(1,ThermalKind.Reactor,new[] {socket(0,1)});
        var tee = nodeAt(2,ThermalKind.Pipe,new[] {socket(0,-1),socket(4,1),socket(5,1)});
        var header = nodeAt(3,ThermalKind.Pipe,new[] {socket(4,-1),socket(1,1),socket(2,1),socket(3,1)});
        var first = nodeAt(4,ThermalKind.Train,new[] {socket(1,-1)});
        var second = nodeAt(5,ThermalKind.Train,new[] {socket(2,-1)});
        var third = nodeAt(6,ThermalKind.Train,new[] {socket(3,-1)});
        var cooler = nodeAt(7,ThermalKind.AirCooler,new[] {socket(5,-1)});
        var bank = new List<ThermalEndpoint> {sourceNode,tee,header,first,second,third,cooler};
        var network = new ThermalNetwork(bank);
        Check(!network.Plant(sourceNode).Ready, "multiple turbines on one manifold are rejected");
        var flow = network.FlowDirections(new HashSet<long> {1},new HashSet<long> {4,5,6,7});
        foreach (long id in new long[] {4,5,6,7}) Check(flow.ContainsKey(id) && flow[id][0] == 1, "supply enters each active terminal; paired return leaves");
        second.Healthy = false;
        network = new ThermalNetwork(bank);
        Check(!network.Plant(sourceNode).Ready, "damaged turbine breaches only its connected circuit");
        second.Healthy = true;
        bank.Remove(second);
        Check(!new ThermalNetwork(bank).Plant(sourceNode).Ready, "open terminal must be capped before recharging");
        var cap = nodeAt(8,ThermalKind.Pipe,new[] {socket(2,-1)}); bank.Add(cap);
        bank.Remove(third);
        var cap2 = nodeAt(12,ThermalKind.Pipe,new[] {socket(3,-1)}); bank.Add(cap2);
        network = new ThermalNetwork(bank);
        Check(network.Plant(sourceNode).Ready, "one turbine plus cooling and capped branches form a sealed circuit");
        Check(!network.FlowDirections(new HashSet<long> {1},new HashSet<long> {4,6,7}).ContainsKey(8), "capped branch stays motionless");
        var extraSource = nodeAt(9,ThermalKind.Reactor,new[] {socket(2,-1)});
        bank.Remove(cap); bank.Add(extraSource);
        Check(!new ThermalNetwork(bank).Plant(sourceNode).Ready, "separate reactors cannot share one plant");
        // Two single sockets can only terminate at each other, with no spare
        // inlet/outlet to attach a source. Trying a third socket is crowded.
        var serialA = nodeAt(10,ThermalKind.Train,new[] {socket(0,-1)});
        var serialB = nodeAt(11,ThermalKind.Train,new[] {socket(0,1)});
        network = new ThermalNetwork(new[] {sourceNode,serialA,serialB});
        Check(!network.Plant(sourceNode).Ready && network.Joints.TrueForAll(j => j.Status == ThermalJointStatus.Crowded),
            "single-socket turbines cannot form a series chain with a reactor");
    }

    private static void ReactorAdapters()
    {
        var reactor=ThermalModels.All["ArcanePower_Thermal_ReactorHousing"];
        var straight=ThermalModels.All["ArcanePower_Thermal_PrimaryStraight"];
        foreach(var suffix in new[]{"PrimaryReactorAdapter","PrimaryReactorAdapterBare"}){
            var model=ThermalModels.All["ArcanePower_Thermal_"+suffix];
            Check(Array.FindAll(model.Ports,p=>p.ReactorOnly).Length==1,"each adapter has exactly one authored reactor-only end");
            foreach(var rotation in Orientations()){
                var source=ThermalEndpoint.At(1,7,reactor,rotation,new Vector3(17.5f,-2.5f,12.5f),true);
                for(int bay=0;bay<4;bay++){
                    var turn=Matrix.CreateRotationY(bay<2?MathHelper.Pi:0)*rotation;
                    var local=Array.Find(model.Ports,p=>p.ReactorOnly);
                    var centre=source.Ports[bay].Position-Vector3.Transform(local.Position,turn);
                    var adapter=ThermalEndpoint.At(2,7,model,turn,centre,true);
                    var inlet=Array.Find(adapter.Ports,p=>p.ReactorOnly);
                    var outlet=Array.Find(adapter.Ports,p=>!p.ReactorOnly);
                    Check(ThermalNetwork.Match(adapter,inlet,source,source.Ports[bay])==ThermalJointStatus.Matched
                        && ThermalNetwork.Match(source,source.Ports[bay],adapter,inlet)==ThermalJointStatus.Matched,
                        "reactor-only role survives transforms at all four vessel manifolds");
                    var actual=new ThermalNetwork(new[]{source,adapter});
                    Check(actual.OpenPorts(source)==(1<<bay),"correct adapter opens only its own vessel joint");
                    foreach(var peerModel in new[]{straight,model}){
                        var peer=new ThermalEndpoint{Id=3,GridId=7,Healthy=true,Model=peerModel,
                            Ports=new[]{new ThermalPort("CO2",inlet.Position,-inlet.Normal,inlet.HotAxis)}};
                        Check(ThermalNetwork.Match(adapter,inlet,peer,peer.Ports[0])==ThermalJointStatus.ReactorOnly
                            && ThermalNetwork.Match(peer,peer.Ports[0],adapter,inlet)==ThermalJointStatus.ReactorOnly,
                            "reactor-only side rejects normal pipes and other adapters in either match direction");
                        var rejected=new ThermalNetwork(new[]{adapter,peer});
                        Check(rejected.OpenPorts(adapter)==0 && rejected.OpenPorts(peer)==0,
                            "forbidden adapter mate cannot open either connection");
                        Check(ThermalConstruction.Matches(adapter,new[]{peer})==0
                            && ThermalConstruction.Inspect(new[]{adapter,peer},adapter.Id).Wrong==1,
                            "placement and construction checks reject the same forbidden mate");
                    }
                    var pipe=new ThermalEndpoint{Id=4,GridId=7,Healthy=true,Model=straight,
                        Ports=new[]{new ThermalPort("CO2",outlet.Position,-outlet.Normal,outlet.HotAxis)}};
                    Check(ThermalNetwork.Match(adapter,outlet,pipe,pipe.Ports[0])==ThermalJointStatus.Matched,
                        "opposite adapter end remains a normal pipe connection");
                }
            }
        }
        Check(ThermalConstruction.JointHint(ThermalJointStatus.ReactorOnly).Contains("reactor vessel"),
            "forbidden peer has an actionable construction hint");
    }

    private static void BarePipes()
    {
        int variants = 0;
        foreach (var entry in ThermalModels.All)
        {
            if (!entry.Key.EndsWith("Bare")) continue;
            variants++;
            var bare = entry.Value;
            var framed = ThermalModels.All[entry.Key.Substring(0, entry.Key.Length - 4)];
            Check(bare.Kind == ThermalKind.Pipe && bare.Kind == framed.Kind && bare.Cells == framed.Cells
                && bare.Grade == framed.Grade && bare.Ports.Length == framed.Ports.Length, "bare pipe keeps physical grid and runtime role");
            Near(bare.RatingMW, framed.RatingMW, "bare pipe keeps capacity");
            for (int i = 0; i < bare.Ports.Length; i++)
            {
                var a = bare.Ports[i]; var b = framed.Ports[i];
                Check(a.Circuit == b.Circuit && a.Position == b.Position && a.Normal == b.Normal && a.HotAxis == b.HotAxis,
                    "bare fitting preserves socket, pressure type and H/C orientation");
            }
            var paths = ThermalFlowModels.All[entry.Key];
            var original = ThermalFlowModels.All[framed.Subtype];
            Check(paths.Length == original.Length, "bare pipe has every authored flow path");
            for (int i = 0; i < paths.Length; i++)
            {
                var a = paths[i]; var b = original[i];
                Check(a.Circuit == b.Circuit && a.Port == b.Port && a.Hot == b.Hot && a.Internal == b.Internal
                    && a.Radius == b.Radius && a.Points.Length == b.Points.Length, "bare flow uses the same pressure tube");
                for (int j = 0; j < a.Points.Length; j++) Check(a.Points[j] == b.Points[j], "bare flow stays inside unchanged glass");
            }
        }
        Check(variants == 22, "public and compatibility bare pipe contracts");
        var layout = BareLayout();
        var reactor = layout.Find(n => n.Model.Kind == ThermalKind.Reactor);
        Check(!new ThermalNetwork(layout).Plant(reactor).Ready, "bare pipes obey independent circuit rules on old shared layouts");
        int mixed = 0;
        foreach (var node in layout)
            if (node.Model.Kind == ThermalKind.Pipe && node.Id % 2 == 0)
            {
                node.Model = ThermalModels.All[node.Model.Subtype.Substring(0, node.Model.Subtype.Length - 4)];
                mixed++;
            }
        Check(mixed > 0 && !new ThermalNetwork(layout).Plant(reactor).Ready, "mixing framed and bare pipes cannot bypass circuit separation");
    }

    private static void Rotors()
    {
        var cold = new ThermalRotorState { EntityId = 1 };
        for (int i = 0; i < 480; i++) ThermalRotors.Drive(cold, 0, 100, 650, 1, true, 1.0 / 60);
        Near(cold.Rpm, 0, "cold turbine cannot spin from compressor power");
        Check(cold.CompressorRpm > ThermalRotors.MaxCompressorRpm * .8, "paid cold start spools independent compressor");
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
            "heat and circulation both increase shaft speed");
        Near(low.TargetRpm, hot.TargetRpm * .5, "quarter circulation gives half target speed without a pressure gate");
        double spinning = hot.Rpm;
        ThermalRotors.Drive(hot, 50, 100, 2200, 1, false, 1.0 / 60);
        Check(hot.Rpm > 0 && hot.Rpm < spinning && hot.TargetRpm == 0, "fault or valve closure coasts, never snaps");
        for (int i = 0; i < 7200; i++) ThermalRotors.Drive(hot, 50, 100, 2200, 0, false, 1.0 / 60);
        Near(hot.Rpm, 0, "shutdown reaches rest");
        Check(!warm.Valid(2), "copied rotor identity rejected");
        var serializer = new XmlSerializer(typeof(ThermalStore));
        var store = new ThermalStore { EntityId = 1, Rotor = warm, HotMJ = 50 };
        var writer = new StringWriter(); serializer.Serialize(writer, store);
        var restored = (ThermalStore)serializer.Deserialize(new StringReader(writer.ToString().Replace("</Rotor>", "<PressureMPa>11</PressureMPa></Rotor>")));
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
        var layout = IndependentLayout();
        var cache = new ThermalCircuitCache(layout);
        Check(cache.Matches(layout) && Array.TrueForAll(cache.Circuits, c => c.Ready), "physical circuit cache validates a cold assembly");
        var changed = layout[1];
        changed.Healthy = false;
        Check(!cache.Matches(layout), "damage and welding invalidate circuit results");
        changed.Healthy = true; changed.GridId++;
        Check(!cache.Matches(layout), "grid split invalidates circuit results");
        changed.GridId--; changed.Id++;
        Check(!cache.Matches(layout), "same-size replacement cannot reuse stale membership");
        changed.Id--; changed.Ports[0].HotAxis = -changed.Ports[0].HotAxis;
        Check(!cache.Matches(layout) && Array.TrueForAll(cache.Circuits, c => c.Ready),
            "H/C changes invalidate results without mutating the saved graph");
        changed.Ports[0].HotAxis = -changed.Ports[0].HotAxis;
        changed.Ports[0].ReactorOnly = !changed.Ports[0].ReactorOnly;
        Check(!cache.Matches(layout), "reactor-only socket roles participate in validation");
        changed.Ports[0].ReactorOnly = !changed.Ports[0].ReactorOnly;
        Check(cache.Matches(layout), "unchanged geometry and health reuse validation");
        var source = layout.Find(n => n.Model.Kind == ThermalKind.Reactor);
        var report = ThermalConstruction.Inspect(layout, source.Id);
        Check(report.Verified && report.Open == 0 && report.Wrong == 0 && report.Pending == 0,
            "authored plant passes construction independently of operating mode");
        Check(report.Trains == 4 && report.Cooling == 4, "only routed turbine/cooling earn construction credit");
        var capped = layout.Find(n => n.Model.Kind == ThermalKind.Pipe && n.Ports.Length == 1);
        layout.Remove(capped);
        report = ThermalConstruction.Inspect(layout, source.Id);
        Check(!report.Verified && report.Open > 0, "open junction must be capped before circuit verification");
        layout.Add(capped);
        var turbine = layout.Find(n => n.Model.Kind == ThermalKind.Train);
        turbine.Healthy = false;
        report = ThermalConstruction.Inspect(layout, source.Id);
        Check(!report.Verified && report.Pending == 1 && report.Nodes.Count == layout.Count,
            "unfinished block keeps visible topology but prevents verification");
        Check(!turbine.Healthy, "construction scan never mutates authoritative health");
        turbine.Healthy = true;
        var pipe = new ThermalNetwork(layout).Joints.Find(j => j.Peer == turbine && j.Node.Model.Kind == ThermalKind.Pipe).Node;
        var p = pipe.Ports[0];
        p.HotAxis = -p.HotAxis;
        report = ThermalConstruction.Inspect(layout, source.Id);
        Check(!report.Verified && report.Wrong == 1 && report.Nodes.Count == layout.Count,
            "roll fault counts one connection without hiding downstream construction");
        Check(report.Next.StartsWith("1 mismatched connection:")
            && report.Joints.FindAll(j => j.Status == ThermalJointStatus.Roll).Count == 2,
            "one mismatch message retains highlights on both ends");
        var second = layout.Find(n => n.Model.Kind == ThermalKind.AirCooler).Ports[0];
        second.HotAxis = -second.HotAxis;
        report = ThermalConstruction.Inspect(layout, source.Id);
        Check(report.Wrong == 2 && report.Next.StartsWith("2 mismatched connections:"),
            "two different faulty connections count separately");
        second.HotAxis = -second.HotAxis;
        p.HotAxis = -p.HotAxis;
        p.Normal = -p.Normal;
        report = ThermalConstruction.Inspect(layout, source.Id);
        Check(!report.Verified && report.Joints.Exists(j => j.Status == ThermalJointStatus.Facing), "wrong facing diagnosed");
        p.Normal = -p.Normal;
        layout.Remove(pipe);
        report = ThermalConstruction.Inspect(layout, source.Id);
        Check(!report.Verified && report.Open > 0, "missing turbine connection leaves a visible isolated route");
        layout.Add(pipe);
        pipe.GridId = 2;
        Check(!ThermalConstruction.Inspect(layout, source.Id).Verified, "no cross-grid construction approval");
        pipe.GridId = 1;
        var detached = Node(1000, turbine.Model.Subtype, Matrix.CreateTranslation(1000, 1000, 1000));
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
        ThermalKind[] kinds = { ThermalKind.Reactor, ThermalKind.Train, ThermalKind.AirCooler, ThermalKind.Pipe };
        var ports = new[] {
            new[] { socket("PRIMARY", 0, 1) },
            new[] { socket("CO2", 1, -1) },
            new[] { socket("CO2", 2, -1) },
            new[] { socket("CO2", 0, -1), socket("CO2", 1, 1), socket("CO2", 2, 1) } };
        for (int i = 0; i < kinds.Length; i++)
            schematic.Add(new ThermalEndpoint { Id = i + 1, GridId = 1, Healthy = true,
                Model = new ThermalModel { Kind = kinds[i], Ports = ports[i] }, Ports = ports[i] });
        Check(ThermalConstruction.Inspect(schematic, 1).Verified, "direct functional schematic verified");
        schematic[2].Model.Kind = ThermalKind.Pipe;
        report = ThermalConstruction.Inspect(schematic, 1);
        Check(!report.Verified && report.Next.Contains("cooling"), "sealed LP without cooling gets a construction instruction");
        schematic[2].Model.Kind = ThermalKind.AirCooler;
        schematic[1].Model.Kind = ThermalKind.Pipe;
        Check(!ThermalConstruction.Inspect(schematic, 1).Verified, "closed route without a turbine cannot pass");
    }

    private static void Flow(string evidence)
    {
        var snapshots = new List<string>();
        foreach (var layout in new[] { Layout(), RoomLayout() })
        {
            var observed = new Dictionary<long, byte[]>();
            var network = new ThermalNetwork(layout);
            var source = layout.Find(n => n.Model.Kind == ThermalKind.Reactor);
            Check(!network.Plant(source).Ready, "legacy circulation layout is safely rejected for reconfiguration");
            foreach (ThermalKind to in new[] {ThermalKind.Train,ThermalKind.AirCooler})
            {
                ThermalKind from = ThermalKind.Reactor;
                var starts = new HashSet<long>(); var ends = new HashSet<long>();
                foreach (var n in layout) { if (n.Model.Kind == from) starts.Add(n.Id); if (n.Model.Kind == to) ends.Add(n.Id); }
                var directions = network.FlowDirections(starts, ends);
                foreach (var item in directions)
                {
                    byte[] values;
                    if (!observed.TryGetValue(item.Key, out values)) observed[item.Key]=values=new byte[item.Value.Length];
                    for (int i=0; i<values.Length; i++) if (item.Value[i]!=0) values[i]=item.Value[i];
                }
                Check(directions.Count > 2, "shared network carries flow to " + to);
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
            var terminal = layout.Find(n => n.Model.Kind == ThermalKind.Train);
            var terminalJoint = network.Joints.Find(j => j.Peer == terminal && j.Node.Model.Kind == ThermalKind.Pipe);
            var pipe = terminalJoint.Node;
            var a = new HashSet<long> { source.Id };
            var b = new HashSet<long> { layout.Find(n => n.Model.Kind == ThermalKind.Train).Id };
            pipe.GridId = 2;
            Check(new ThermalNetwork(layout).FlowDirections( a, b).Count == 0, "split stops room circulation");
            pipe.GridId = 1;
            var port = terminalJoint.Port;
            port.HotAxis = -port.HotAxis;
            Check(new ThermalNetwork(layout).FlowDirections( a, b).Count == 0, "wrong H/C roll stops circulation");
            port.HotAxis = -port.HotAxis; port.Normal = -port.Normal;
            Check(new ThermalNetwork(layout).FlowDirections( a, b).Count == 0, "wrong facing stops circulation");
            port.Normal = -port.Normal;
            port.HotAxis.X = float.NaN;
            Check(new ThermalNetwork(layout).FlowDirections( a, b).Count == 0, "invalid channel orientation stops circulation");
        }
        if (evidence != null) File.WriteAllText(evidence,"{\"starter\":"+snapshots[0]+",\"room\":"+snapshots[1]+"}\n");
        Func<int, int, ThermalPort> socket = (x, sign) => new ThermalPort("PRIMARY", new Vector3(x, 0, 0), Vector3.UnitX*sign, Vector3.UnitY);
        Func<long, ThermalPort[], ThermalEndpoint> node = (id, ports) => new ThermalEndpoint {
            Id=id, GridId=1, Healthy=true, Model=new ThermalModel { Kind=ThermalKind.Pipe, Ports=ports }, Ports=ports };
        var branch = new List<ThermalEndpoint> {
            node(1,new[] {socket(0,1)}),
            node(2,new[] {socket(0,-1),socket(1,1),socket(2,1),socket(3,1)}),
            node(3,new[] {socket(1,-1)}), node(4,new[] {socket(2,-1)}), node(5,new[] {socket(3,-1)}) };
        var selected = new ThermalNetwork(branch).FlowDirections(new HashSet<long> {1},new HashSet<long> {3});
        Check(selected.Count == 3 && !selected.ContainsKey(4) && !selected.ContainsKey(5),
            "standby and capped spurs stay motionless");
        selected = new ThermalNetwork(branch).FlowDirections(new HashSet<long> {1},new HashSet<long> {3,4});
        Check(selected.Count == 4 && !selected.ContainsKey(5), "selected parallel branches both circulate");
        var diamond = new List<ThermalEndpoint> {
            node(1,new[] {socket(10,1),socket(11,1)}),
            node(2,new[] {socket(10,-1),socket(12,1)}),
            node(3,new[] {socket(11,-1),socket(13,1)}),
            node(4,new[] {socket(12,-1),socket(13,-1)}) };
        selected = new ThermalNetwork(diamond).FlowDirections(new HashSet<long> {1},new HashSet<long> {4});
        Check(selected.Count == 4 && selected[1][0] == 2 && selected[1][1] == 2, "equal parallel physical routes both circulate");

        foreach (var model in ThermalModels.All.Values)
            Check(ThermalFlowModels.All.ContainsKey(model.Subtype) == (model.Ports.Length > 0), "flow paths cover every socket-bearing model");
        foreach (var entry in ThermalFlowModels.All)
        {
            var spec = ThermalModels.All[entry.Key];
            var state = new ThermalFlowState {EntityId=1, Sequence=1, Mode=ThermalFlowMode.Pumping, Rate=1, Heat=.5, Internal=true, Ports=new byte[spec.Ports.Length], OpenConnectors=(byte)((1<<spec.Ports.Length)-1)};
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
                    byte connected = state.OpenConnectors;
                    state.OpenConnectors=0;
                    Check(path.Direction(state)==0,"auto-capped mouths suppress stale flow particles");
                    state.OpenConnectors=connected;
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

    private static List<ThermalEndpoint> IndependentLayout()
    {
        Func<int,int,ThermalPort> socket=(x,sign)=>new ThermalPort("CO2",new Vector3(x,0,0),Vector3.UnitX*sign,Vector3.UnitY);
        Func<long,ThermalKind,ThermalPort[],ThermalEndpoint> node=(id,kind,ports)=>new ThermalEndpoint {
            Id=id,GridId=1,Healthy=true,Model=new ThermalModel{Kind=kind,Ports=ports,
                Subtype=kind==ThermalKind.Train ? "ArcanePower_Thermal_BraytonTrain" : "test-circuit",
                RatingMW=100, CoolingMW=kind==ThermalKind.AirCooler ? 60 : 0},Ports=ports};
        var nodes=new List<ThermalEndpoint>();
        nodes.Add(node(1,ThermalKind.Reactor,new[]{socket(0,1),socket(100,1),socket(200,1),socket(300,1)}));
        for(int i=0;i<4;i++) {
            int x=i*100; long id=10+i*10;
            nodes.Add(node(id,ThermalKind.Pipe,new[]{socket(x,-1),socket(x+1,1)}));
            nodes.Add(node(id+1,ThermalKind.Pipe,new[]{socket(x+1,-1),socket(x+2,1),socket(x+3,1),socket(x+4,1)}));
            nodes.Add(node(id+2,ThermalKind.Train,new[]{socket(x+2,-1)}));
            nodes.Add(node(id+3,ThermalKind.AirCooler,new[]{socket(x+3,-1)}));
            nodes.Add(node(id+4,ThermalKind.Pipe,new[]{socket(x+4,-1)}));
        }
        return nodes;
    }

    private static void Isolation()
    {
        foreach(var rotation in Orientations()) {
            var nodes=IndependentLayout();
            foreach(var node in nodes) foreach(var port in node.Ports) {
                port.Position=Vector3.Transform(port.Position,rotation);
                port.Normal=Vector3.TransformNormal(port.Normal,rotation);
                port.HotAxis=Vector3.TransformNormal(port.HotAxis,rotation);
            }
            var source=nodes[0];
            var loops=new ThermalNetwork(nodes).Loops(source);
            Check(Array.TrueForAll(loops,l=>l.Ready),"four independent sealed circuits in every grid orientation");
            var wrongBranch=nodes.Find(n=>n.Id==10);
            wrongBranch.Ports[0].HotAxis=-wrongBranch.Ports[0].HotAxis;
            var healthyGuide=ThermalConstruction.Inspect(nodes,20);
            Check(healthyGuide.Verified && healthyGuide.Wrong==0 && healthyGuide.Trains==1 && healthyGuide.Cooling==1,
                "healthy selected circuit is not accused of mismatches in another vessel circuit");
            Check(!healthyGuide.Next.Contains("mismatch") && !healthyGuide.Next.Contains("red joints"),
                "healthy circuit does not show the phantom fix-red-joints prompt");
            var damagedGuide=ThermalConstruction.Inspect(nodes,10);
            Check(!damagedGuide.Verified && damagedGuide.Wrong==1 && damagedGuide.Next.Contains("H must meet H"),
                "selected faulty circuit reports the actual mismatch and correction");
            var vesselGuide=ThermalConstruction.Inspect(nodes,source.Id);
            Check(vesselGuide.Wrong==1 && vesselGuide.Next.Contains("mismatched connection") && !vesselGuide.Next.Contains("red joints"),
                "vessel inspection retains all-circuit faults without claiming markers are visible");
            wrongBranch.Ports[0].HotAxis=-wrongBranch.Ports[0].HotAxis;
            Check(ThermalConstruction.Inspect(nodes,10).Verified,"repair clears the selected circuit's mismatch prompt");
            for(int working=0;working<4;working++){
                var single=new List<ThermalEndpoint>(nodes);
                for(int i=0;i<4;i++)if(i!=working)single.Remove(nodes.Find(n=>n.Id==10+i*10));
                var network=new ThermalNetwork(single);
                var circuits=network.Loops(source);
                Check(circuits[working].Ready && Array.FindAll(circuits,l=>l.Ready).Length==1,
                    "any one complete circuit is independent of three incomplete circuits");
                var circuit=circuits[working];
                var valves=new ThermalReactorState{Mode=ThermalMode.Brayton,Requested=ThermalMode.Brayton,Deployment=1};
                for(int i=0;i<circuits.Length;i++)valves.Loops[i].Connected=circuits[i].Ready;
                Check(ThermalLoops.OpenValves(valves)==(1<<working) && valves.ConnectedLoops==1,
                    "a complete cold circuit is immediately available and opens its own valve");
                var circuitUnits=new List<ThermalUnit>();
                var sinks=new HashSet<long>();
                foreach(var member in circuit.Nodes)if(member!=source){
                    circuitUnits.Add(new ThermalUnit{Id=member.Id,Kind=member.Model.Kind,RatingMW=member.Model.RatingMW,CoolingMW=member.Model.CoolingMW});
                    if(member.Model.Kind==ThermalKind.Train || member.Model.Kind==ThermalKind.AirCooler)sinks.Add(member.Id);
                }
                var plan=ThermalMath.Dispatch(ThermalLoops.Allocation(400),650,circuitUnits);
                Near(plan.AcceptedMW,100,"one circuit accepts its fixed quarter heat allocation");
                Near(plan.NetMW,40,"one circuit retains normal tier conversion efficiency");
                var directions=network.FlowDirections(new HashSet<long>{source.Id},sinks);
                var states=new Dictionary<long,ThermalFlowState>();
                foreach(var member in single)states[member.Id]=new ThermalFlowState{
                    EntityId=member.Id,Sequence=1,Ports=new byte[member.Ports.Length],Mode=ThermalFlowMode.Unconnected};
                foreach(var member in circuit.Nodes){
                    byte[] ports;bool flowing=directions.TryGetValue(member.Id,out ports);
                    var observed=states[member.Id];observed.OpenConnectors=network.OpenPorts(member);
                    observed.ObserveCircuit(ports,.75,.5,member.Model.Kind!=ThermalKind.Pipe);
                    Check(observed.Mode==(flowing?ThermalFlowMode.Pumping:ThermalFlowMode.Ready),
                        "every valid circuit member clears the red warning independently of shortest flow paths");
                    Check(observed.Valid(member.Ports.Length),"per-circuit observations remain valid network packets");
                }
                var capState=states[14+working*10];
                Check(capState.Mode==ThermalFlowMode.Ready && capState.Rate==0 && Array.TrueForAll(capState.Ports,p=>p==0),
                    "valid capped spur restores normal colours without fabricated fluid flow");
                foreach(var member in single)if(!circuit.Nodes.Contains(member))
                    Check(states[member.Id].Mode==ThermalFlowMode.Unconnected,
                        "healthy circuit observations cannot clear warnings in incomplete circuits");
            }
            foreach(int failure in new[]{0,1,2,3,4,5}) {
                var damaged=new List<ThermalEndpoint>(nodes);
                var pipe=nodes.Find(n=>n.Id==10);
                var original=pipe.Ports[0].HotAxis;
                if(failure==0)damaged.Remove(pipe);
                if(failure==1)pipe.Healthy=false;
                if(failure==2)pipe.GridId=2;
                if(failure==3)pipe.Ports[0].HotAxis=-original;
                if(failure==4)damaged.Add(new ThermalEndpoint{Id=99,GridId=1,Healthy=true,Model=pipe.Model,Ports=new[]{pipe.Ports[0]}});
                if(failure==5)damaged.Remove(nodes.Find(n=>n.Id==14));
                loops=new ThermalNetwork(damaged).Loops(source);
                Check(!loops[0].Ready && loops[1].Ready && loops[2].Ready && loops[3].Ready,
                    "removed/damaged/split/misrolled/crowded/open-cap faults isolate exactly one circuit");
                pipe.Healthy=true;pipe.GridId=1;pipe.Ports[0].HotAxis=original;
            }
            for(int lost=0;lost<=4;lost++) {
                var remaining=new List<ThermalEndpoint>(nodes);
                for(int i=0;i<lost;i++)remaining.Remove(nodes.Find(n=>n.Id==10+i*10));
                loops=new ThermalNetwork(remaining).Loops(source);
                int ready=Array.FindAll(loops,l=>l.Ready).Length;
                Near(ready*ThermalLoops.Allocation(100),(4-lost)*25,"losses retain fixed surviving heat-flow allocations");
                var validated=new ThermalReactorState();
                for(int i=0;i<loops.Length;i++)validated.Loops[i].Connected=loops[i].Ready;
                Check(validated.ConnectedLoops==ready,
                    "every complete circuit is available regardless of isolated defect count");
            }
        }
        var layout=IndependentLayout(); var root=layout[0];
        var capA=layout.Find(n=>n.Id==14); var capB=layout.Find(n=>n.Id==24);
        layout.Remove(capA);layout.Remove(capB);
        layout.Add(new ThermalEndpoint{Id=99,GridId=1,Healthy=true,Model=capA.Model,
            Ports=new[]{capA.Ports[0],capB.Ports[0]}});
        var cross=new ThermalNetwork(layout).Loops(root);
        Check(!cross[0].Ready && !cross[1].Ready && cross[2].Ready && cross[3].Ready,
            "cross-connecting reactor outlets cannot duplicate coolant or cooling credit");
        layout=IndependentLayout();
        var cap=layout.Find(n=>n.Id==14);layout.Remove(cap);
        layout.Add(new ThermalEndpoint{Id=99,GridId=1,Healthy=true,Model=layout.Find(n=>n.Id==12).Model,Ports=cap.Ports});
        Check(!new ThermalNetwork(layout).Loops(layout[0])[0].Ready,"exactly one turbine per circuit");
        var state=new ThermalReactorState{Store=new ThermalStore{EntityId=1,HotMJ=100,WasteMJ=50},LoopVersion=1};
        state.Loops[0].Connected=true;
        Check(state.ConnectedLoops==1 && state.Valid(1),"one validated circuit is immediately available");
        for(int i=0;i<4;i++)state.Loops[i].Connected=true;
        Check(state.ConnectedLoops==4,"four complete circuits available without commissioning");
        for(int i=0;i<4;i++) {
            state.Loops[i].Connected=false;
            Check(state.ConnectedLoops==3-i,"availability follows validated topology");
            Near(state.Store.HotMJ+state.Store.WasteMJ,150,"circuit loss never erases or fabricates heat");
            Near(ThermalMath.WasteHeatLevel(state.Store,100),.25,"core heat normalization retains full reactor rating");
        }
        var xml=new XmlSerializer(typeof(ThermalReactorState));var writer=new StringWriter();xml.Serialize(writer,state);
        var restored=(ThermalReactorState)xml.Deserialize(new StringReader(writer.ToString().Replace("</ThermalLoopState>", "<Charge>0.5</Charge></ThermalLoopState>")));
        Near(restored.Store.HotMJ + restored.Store.WasteMJ, 150, "legacy charge fields are ignored without losing saved heat");
        Check(restored.Valid(1) && !restored.Valid(2),"loop snapshots remain identity-bound through save/reload");
        restored.Loops[0].HeatMW=double.NaN;Check(!restored.Valid(1),"nonfinite thermal diagnostics rejected");
        restored.Loops=ThermalLoops.Empty();restored.Loops[0]=null;Check(!restored.Valid(1),"missing circuit state rejected");
        restored.Loops=new ThermalLoopState[5];Check(!restored.Valid(1),"excess loop slots rejected");
        double opening=1;
        for(int i=0;i<21;i++)opening=ThermalIsolation.Step(opening,false,1.0/60);
        Near(opening,0,"reactor shut-off spring closes in 350 ms");
        for(int i=0;i<48;i++)opening=ThermalIsolation.Step(opening,true,1.0/60);
        Near(opening,1,"validated circuit opens smoothly over 800 ms");
        Near(ThermalIsolation.Step(double.NaN,true,1),0,"invalid animation fails closed");
        var flow=new ThermalFlowState{EntityId=1,Ports=new byte[2],OpenConnectors=4};
        Check(!flow.Valid(2),"reject excess connector bits in snapshot");
        flow.OpenConnectors=3;Check(flow.Valid(2),"connector state independent of stopped flow");
        for(int mask=0;mask<16;mask++){
            var valves=new ThermalReactorState{Mode=ThermalMode.Brayton,Requested=ThermalMode.Brayton,Deployment=1};
            for(int i=0;i<4;i++)valves.Loops[i].Connected=(mask&(1<<i))!=0;
            Check(ThermalLoops.OpenValves(valves)==mask,"valves follow checked circuits without fill state");
            valves.Requested=ThermalMode.Standalone;
            Check(ThermalLoops.OpenValves(valves)==mask,"deployed circuits remain open during powered cooldown before retraction");
            valves.Deployment=.5f;Check(ThermalLoops.OpenValves(valves)==0,"retracting manifold valves close");
            valves.Deployment=1;valves.Faulted=true;Check(ThermalLoops.OpenValves(valves)==0,"runtime isolation fails closed");
            valves.Faulted=false;valves.Mode=ThermalMode.Standalone;Check(ThermalLoops.OpenValves(valves)==0,"standalone valves remain closed");
        }
        Check(ThermalLoops.OpenValves(null)==0,"missing circuit state fails closed");
    }

    private static void LoopEnergy()
    {
        foreach(double eta in new[]{.4,.78}) {
            var core=new ThermalStore{EntityId=1,HotMJ=400};
            var trains=new ThermalStore[4];
            for(int i=0;i<4;i++)trains[i]=new ThermalStore{EntityId=10+i};
            double admitted=0,exported=0,rejected=0,pumping=0;
            // A single delivered interval can start circulation immediately.
            foreach(var train in trains) {
                double delivered=ThermalLoops.Allocation(100)*.02;
                Near(ThermalMath.CirculationPower(0,eta,delivered,25),1,"cold circulation needs no fill timer");
                train.WasteMJ+=delivered/60;pumping+=delivered/60;
            }
            for(int active=4;active>=0;active--) {
                double before=admitted;
                for(int tick=0;tick<1200;tick++) {
                    for(int i=0;i<active;i++) {
                        double allocation=ThermalLoops.Allocation(100);
                        ThermalMath.Transfer(core,trains[i],200,allocation/60,false);
                        double output=ThermalMath.ExportLimit(trains[i],200,eta,allocation*eta,1.0/60);
                        Check(output<=allocation*eta,"surviving turbines never inherit failed circuit allocations");
                        Check(ThermalMath.Convert(trains[i],output/60,eta),"each native grant consumes paid heat");
                        exported+=output/60;
                        ThermalMath.Transfer(trains[i],core,800,allocation/60,true);
                    }
                    rejected+=ThermalMath.Reject(core,(active>0 ? active*25*(1-eta) : 2)/60,false);
                    if(active>0)admitted+=ThermalMath.AdmitReactionHeat(core,100,active*25.0/60,1000000);
                    double retained=core.HotMJ+core.WasteMJ;
                    foreach(var train in trains)retained+=train.HotMJ+train.WasteMJ;
                    Near(400+admitted+pumping,exported+rejected+retained,"successive circuit losses conserve fuel, pump electricity, export, rejection and trapped MJ");
                    Check(core.Valid(1,800),"core store remains bounded while circuit availability changes");
                }
                if(active==0)Near(admitted,before,"last-loop shutdown admits no new reaction heat");
            }
            Check(core.HotMJ+core.WasteMJ>0,"shutdown preserves residual heat instead of resetting the reactor");
        }
    }

    private static void Radiators()
    {
        // Test the actual native row-matrix normal, under arbitrary grid orientation.
        for (int yaw = 0; yaw < 12; yaw++)
            for (int pitch = -4; pitch <= 4; pitch++)
            {
                Vector3D sun = Vector3D.Normalize(new Vector3D(Math.Cos(yaw), Math.Sin(pitch * .3), Math.Sin(yaw)));
                MatrixD grid = MatrixD.CreateFromYawPitchRoll(.7, .4, -.8);
                Vector3D local = Vector3D.TransformNormal(sun, MatrixD.Transpose(grid));
                double target = ThermalRadiators.Target(local, .2);
                MatrixD panel = ThermalRadiators.Pose(target) * grid;
                Check(Math.Abs(Vector3D.Dot(panel.Backward, sun)) < 1e-6, "radiator faces are edge-on in any grid orientation");
            }
        Near(ThermalRadiators.Target(Vector3D.Up, 1.2), 1.2, "sun parallel to tracking axis holds yaw");
        double angle = 0;
        for (int i = 0; i < 1800; i++) angle = ThermalRadiators.Step(angle, Math.PI / 2, 1.0 / 60);
        Near(angle, Math.PI / 2, "90 degree turn takes 30 seconds");
        Near(ThermalRadiators.Step(.3, .3 + Math.PI, 1), .3, "two-sided equivalent avoids unnecessary half turn");
        double wrap = ThermalRadiators.Step(Math.PI * 2 - .01, .01, 1);
        Near(wrap, .01, "tracking crosses zero on the short arc");
        Near(ThermalRadiators.Cooling(60, 1, -270.15, 0), 60, "edge-on keeps cooling rating");
        Near(ThermalRadiators.Cooling(60, 1, -270.15, .5), 45, "half solar exposure retains 75% cooling");
        Near(ThermalRadiators.Cooling(60, 1, -270.15, 1), 30, "full sun on one face retains 50% cooling");
        Near(ThermalRadiators.Cooling(60, 0, -270.15, 0), 0, "occluded tracked radiator cannot cool");
        Near(ThermalRadiators.Cooling(60, .5, -270.15, 0), 30, "solar shade does not undo obstructed radiating area");
        foreach (double cosine in new[] { -1.0, 1.0 })
        {
            Near(ThermalRadiators.SolarExposure(cosine, 1, 1, false), 1, "either face receives full solar load");
            Near(ThermalRadiators.SolarExposure(cosine, .5, 1, false), .5, "four of eight lit pivots give half exposure");
            Near(ThermalRadiators.SolarExposure(cosine, 1, .5, false), .5, "native weather attenuates solar load");
            Near(ThermalRadiators.SolarExposure(cosine, 0, 1, false), 0, "complete local shadow removes solar load");
            Near(ThermalRadiators.SolarExposure(cosine, 1, 1, true), 0, "planetary eclipse removes solar load");
            Near(ThermalRadiators.SolarExposure(cosine, 1, 0, false), 0, "zero weather sunlight removes solar load");
        }
        Near(ThermalRadiators.Cooling(60,1,-270.15,ThermalRadiators.SolarExposure(.5,.5,.5,false)),56.25,
            "oblique incidence, partial shade and weather multiply like solar panels");
        Near(ThermalRadiators.SolarExposure(0,1,1,false),0,"edge-on receives no solar load");
        Near(ThermalRadiators.SolarEfficiency(ThermalRadiators.SolarExposure(1,1,2,false)),.5,"enhanced weather cannot exceed 50% solar penalty");
        Near(ThermalRadiators.SolarExposure(double.NaN,1,1,false),1,"invalid sampled sun is conservatively fully exposed");
        Near(ThermalRadiators.Cooling(60,1,-270.15,double.NaN),0,"invalid solar state cannot grant cooling");
        foreach (var rotation in Orientations())
        {
            Vector3D sun=Vector3D.TransformNormal(Vector3D.UnitX,rotation);
            Func<Vector3D,Vector3D> rotate=v=>Vector3D.TransformNormal(v,rotation);
            Check(ThermalRadiators.PlanetShadow(rotate(new Vector3D(-2000,0,0)),1000,sun),"native planet shadow behind planet");
            Check(!ThermalRadiators.PlanetShadow(rotate(new Vector3D(2000,0,0)),1000,sun),"sunward side is outside planet shadow");
            Check(ThermalRadiators.PlanetShadow(rotate(new Vector3D(-20000,499,0)),1000,sun),"native 20-radius shadow and 500 m margin");
            Check(!ThermalRadiators.PlanetShadow(rotate(new Vector3D(-20001,0,0)),1000,sun),"shadow ends beyond native 20-radius reach");
            Check(!ThermalRadiators.PlanetShadow(rotate(new Vector3D(-2000,500,0)),1000,sun),"grazing sun clears native terrain margin");
            Check(ThermalRadiators.PlanetShadow(rotate(new Vector3D(-1000,449,0)),500,sun),"small planets use native 90% radius margin");
            Check(!ThermalRadiators.PlanetShadow(rotate(new Vector3D(-1000,450,0)),500,sun),"small planet shadow boundary");
        }
        double glow = 0;
        for (int i = 0; i < 600; i++) glow = ThermalRadiators.HeatGlow(glow, 60, 60, 1.0 / 60);
        Check(glow > .96 && glow < 1, "dissipated heat smoothly raises glow");
        for (int i = 0; i < 1800; i++) glow = ThermalRadiators.HeatGlow(glow, 0, 60, 1.0 / 60);
        Check(glow < .0001, "zero actual rejection fades glow to dark");
        var state = new ThermalRadiatorState { EntityId = 1, Angle = 1.2, Target = 2, Glow = .3, RejectedMW = 4000, Exposure = .75 };
        Check(state.Valid(1) && !state.Valid(2), "radiator state belongs to one entity");
        var store = new ThermalStore { EntityId = 1, Radiator = state, WasteMJ = 100 };
        var xml = new XmlSerializer(typeof(ThermalStore));
        var text = new StringWriter(); xml.Serialize(text, store);
        var restored = (ThermalStore)xml.Deserialize(new StringReader(text.ToString()));
        Check(restored.Valid(1, 200) && restored.Radiator.Angle == 1.2, "save preserves heat and radiator angle");
        state.RejectedMW = 300000; Check(state.Valid(1), "upgraded three-panel rejection survives state validation");
        state.RejectedMW = 300001; Check(!state.Valid(1), "radiator rejection remains bounded");
        state.RejectedMW = 4000;
        state.Angle = double.NaN; Check(!state.Valid(1), "reject invalid motion state");
        foreach(string suffix in new[]{"AtmosphericCooler","SpaceRadiator","RadiatorPanel"}) {
            var standard = ThermalModels.All["ArcanePower_Thermal_"+suffix];
            var upgraded = ThermalModels.All["ArcanePower_Thermal_"+suffix+"Upgraded"];
            Near(standard.CoolingMW,10000,"standard cooler/panel rejects 10 GW");
            Near(upgraded.CoolingMW,100000,"upgraded cooler/panel rejects 100 GW");
            Near(standard.RatingMW,25000,"standard saved thermal capacity preserved");
            Near(upgraded.RatingMW,250000,"upgraded cooler throughput scales with cooling");
            Check(standard.Cells==upgraded.Cells && standard.Ports.Length==upgraded.Ports.Length,"upgrades retain socket and footprint contract");
        }
        var model = ThermalModels.All["ArcanePower_Thermal_SpaceRadiator"];
        Check(model.Cells == new Vector3I(3, 3, 3), "reserved radiator sweep cells");
        Check(model.Ports.Length == 1, "one stationary duplex radiator port");
        var extension = ThermalModels.All["ArcanePower_Thermal_RadiatorPanel"];
        Check(extension.Cells == new Vector3I(3, 2, 3) && extension.Ports.Length == 0, "stack panel uses shared base plumbing");
        var frames = new List<MatrixD> { MatrixD.CreateFromYawPitchRoll(.7, .4, -.8) };
        foreach (var orientation in Orientations())
            frames.Add(MatrixD.CreateWorld(Vector3D.Zero, orientation.Forward, orientation.Up));
        foreach (MatrixD frame in frames)
        {
            MatrixD root = frame; root.Translation = new Vector3D(20, 30, -40);
            for (int index = 0; index < 3; index++)
                for (int placedYaw = 0; placedYaw < 4; placedYaw++)
                {
                    MatrixD child = MatrixD.CreateRotationY(placedYaw * Math.PI / 2) * root;
                    child.Translation = ThermalRadiators.ExtensionCentre(root, index);
                    Check(ThermalRadiators.FitsExtension(root, child, index) == (index < 2),
                        "all four placed yaws attach, but only two consecutive extensions");
                    if (index >= 2) continue;
                    for (int lowerYaw = 0; lowerYaw < (index == 0 ? 1 : 4); lowerYaw++)
                    {
                        MatrixD lowerBlock = index == 0 ? root : MatrixD.CreateRotationY(lowerYaw * Math.PI / 2) * root;
                        if (index > 0) lowerBlock.Translation = ThermalRadiators.ExtensionCentre(root, index - 1);
                        for (int sample = 0; sample <= 48; sample++)
                        {
                            double yaw = sample * Math.PI / 24;
                            MatrixD lower = ThermalRadiators.Pose(index == 0 ? yaw
                                : ThermalRadiators.PanelAngle(root, lowerBlock, yaw), index > 0) * lowerBlock;
                            MatrixD upper = ThermalRadiators.Pose(ThermalRadiators.PanelAngle(root, child, yaw), true) * child;
                            Check(Vector3D.DistanceSquared(lower.Right, upper.Right) < .000001
                                && Vector3D.DistanceSquared(lower.Backward, upper.Backward) < .000001,
                                "mixed placed yaws preserve world panel and solar-sampling orientation");
                            foreach (int side in new[] { -1, 1 })
                            {
                                Vector3D top = Vector3D.Transform(new Vector3D(side * 3.05, index == 0 ? 4.85 : 2.5, 0), lower);
                                Vector3D bottom = Vector3D.Transform(new Vector3D(side * 3.05, -2.5, 0), upper);
                                Check(Vector3D.DistanceSquared(top, bottom) < .000001,
                                    "hot/cold couplings stay joined for every mixed-yaw stack through full rotation");
                            }
                        }
                    }
                    child.Translation += root.Right * .1;
                    Check(!ThermalRadiators.FitsExtension(root, child, index), "offset panels cannot attach");
                    foreach (double tilt in new[] { Math.PI / 2, Math.PI })
                    {
                        child = MatrixD.CreateRotationX(tilt) * root;
                        child.Translation = ThermalRadiators.ExtensionCentre(root, index);
                        Check(!ThermalRadiators.FitsExtension(root, child, index), "sideways and upside-down panels cannot attach");
                    }
                }
            Check(!ThermalRadiators.FitsExtension(root, root, -1), "no extension below the base");
        }
        Near(3 * ThermalRadiators.Cooling(model.CoolingMW, 1, -270.15, 0), 30000, "three standard panels reject 30 GW");
        var upgrade = ThermalModels.All["ArcanePower_Thermal_RadiatorPanelUpgraded"];
        Near(3 * ThermalRadiators.Cooling(upgrade.CoolingMW,1,-270.15,0),300000,"three upgraded panels reject 300 GW");
        Near(ThermalRadiators.Cooling(model.CoolingMW,1,-270.15,0)+2*ThermalRadiators.Cooling(upgrade.CoolingMW,1,-270.15,0),210000,"mixed tier panels add individual cooling ratings");
        state.Angle = 0; state.Panels = 4;
        Check(!state.Valid(1), "reject excessive attached count");
        state.Panels = 1; state.ParentId = -1;
        Check(!state.Valid(1), "reject invalid parent identity");
    }

    public static void Main(string[] args)
    {
        Isolation(); Registrations(); Budgets(); Stores(); CoolingFailure(); ModesAndStartup(); Topology(); UniversalPipes(); ReactorAdapters(); BarePipes(); Rotors(); Radiators(); LoopEnergy(); Construction(); Flow(args.Length > 0 ? args[0] : null);
        Console.WriteLine("Thermal runtime: " + checks + " checks passed (registrations/channels, budget, conservation, reload, modes, 47 manifold poses, heat/circulation rotors, construction/orientation guide and authored topology)");
    }
}
