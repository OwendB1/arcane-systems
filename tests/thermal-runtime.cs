using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Xml.Serialization;
using ArcanePower;
using VRageMath;

public static partial class ThermalRuntimeChecks
{
    [ProtoBuf.ProtoContract]
    private sealed class LegacyCircuitTelemetry
    {
        [ProtoBuf.ProtoMember(3)] public double HeatMW = 999;
        [ProtoBuf.ProtoMember(6)] public double RequiredCoolingMW = 123;
        [ProtoBuf.ProtoMember(8)] public double ExcessMJ = 75;
        [ProtoBuf.ProtoMember(9)] public double OutputMW = 20;
        [ProtoBuf.ProtoMember(10)] public double ReactionMW = 999;
        [ProtoBuf.ProtoMember(11)] public double DesignCoolingMW = 999;
    }
    [ProtoBuf.ProtoContract]
    private sealed class LegacyRadiatorConnections
    {
        [ProtoBuf.ProtoMember(1)] public long EntityId = 42;
        [ProtoBuf.ProtoMember(11)] public int RequiredPorts = 31;
        [ProtoBuf.ProtoMember(12)] public int RequiredPanels = 3;
    }
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
                ? "MyObjectBuilder_Reactor" : model.Rotary
                ? (model.Subtype.EndsWith("Head") ? "MyObjectBuilder_MotorAdvancedRotor" : "MyObjectBuilder_MotorAdvancedStator")
                : "MyObjectBuilder_UpgradeModule";
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
        TurbineRatings();
        double[] temperatures = { 650, 1000, 2200 };
        double[] ceilings = { 80, 80, 80 };
        for (int tier = 0; tier < 3; tier++)
            for (int count = 1; count <= 4; count++)
            {
                double net = 0;
                for (int circuit = 0; circuit < count; circuit++)
                {
                    var point = ThermalMath.Dispatch(ThermalLoops.Allocation(100), temperatures[tier], Bank(1, 2, tier == 2 ? 3 : 0));
                    Near(point.Efficiency, ceilings[tier] / 100, "surviving circuits preserve fuel/turbine efficiency");
                    net += point.NetMW;
                }
                Near(net, ceilings[tier] * count / 4, "capacity scales linearly across four fixed circuit allocations");
            }
        Near(ThermalMath.Dispatch(100, 650, Bank(1, 2, 3)).NetMW, 80, "flat conversion applies to every eligible fuel");
        Check(ThermalMath.Dispatch(200, 650, Bank(2, 2)).NetMW == 0, "two turbines cannot share one manifold circuit");
        var smallCooling = Bank(1, 1); smallCooling[1].CoolingMW = 30;
        var undersized = ThermalMath.Dispatch(100, 650, smallCooling);
        Near(undersized.NetMW, 80, "cooling shortage does not silently throttle away the heat hazard");
        Check(undersized.RequiredCoolingMW > undersized.CoolingMW && undersized.SustainableMW < undersized.NetMW,
            "undersized circuit exposes unsafe rejection");
        Near(ThermalMath.Dispatch(200, 650, Bank(1, 2)).NetMW, 80, "turbine rating still limits its own circuit");
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
        Near(ThermalMath.Dispatch(100, 2200, exotic).NetMW, 80, "one exotic circuit retains its grade efficiency");
        exotic.Add(new ThermalUnit { Id = 101, Kind = ThermalKind.AirCooler, RatingMW = 100, CoolingMW = 60 });
        Near(ThermalMath.Dispatch(100, 2200, exotic).NetMW, 80, "extra cooling does not change fuel conversion");
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
        Near(ThermalMath.StandaloneEfficiency, .1, "standalone fuel conversion");
        Near(ThermalMath.BraytonEfficiency, .8, "flat Brayton fuel conversion");
        foreach (double invalid in new[] { -1.0, double.NaN, double.PositiveInfinity })
            Near(ThermalMath.Dispatch(invalid, 650, Bank(1, 1)).NetMW, 0, "invalid offered heat");
    }

    private static void TurbineRatings()
    {
        foreach (var model in ThermalModels.All.Values)
        {
            if (model.Kind != ThermalKind.Train) continue;
            bool upgraded = model.Grade == 3;
            double maximumMW = upgraded ? 50000 : 3500;
            var cooler = ThermalModels.All["ArcanePower_Thermal_AtmosphericCooler" + (upgraded ? "Upgraded" : "")];
            var units = new List<ThermalUnit> {
                new ThermalUnit { Kind = ThermalKind.Train, Grade = model.Grade, RatingMW = model.RatingMW },
                new ThermalUnit { Kind = ThermalKind.AirCooler, CoolingMW = cooler.CoolingMW }
            };
            Near(model.RatingMW * ThermalMath.BraytonEfficiency, maximumMW,
                "native theoretical electrical ceiling: " + model.Subtype);
            var maximum = ThermalMath.Dispatch(model.RatingMW * 2, upgraded ? 2200 : 1000, units);
            Near(maximum.NetMW, maximumMW, "excess heat cannot exceed the turbine ceiling");
            Near(maximum.SustainableMW, maximumMW, "one matching atmospheric cooler sustains theoretical output");
            double[] heat = { 5000, 50000, 250000 };
            double[] hot = { 650, 1000, 2200 };
            double[] eta = { .8, .8, .8 };
            for (int tier = 0; tier < heat.Length; tier++)
            {
                var plan = ThermalMath.Dispatch(ThermalLoops.Allocation(heat[tier]), hot[tier], units);
                if (tier == 2 && !upgraded)
                {
                    Near(plan.NetMW, 0, "Empyrean still requires upgraded turbines");
                    continue;
                }
                Near(plan.AcceptedMW, Math.Min(heat[tier] / 4, model.RatingMW), "fuel allocation and turbine limit bound fuel throughput");
                Near(plan.Efficiency, eta[tier], "fuel determines net efficiency at either turbine tier");
                Near(plan.NetMW, Math.Min(heat[tier] * eta[tier] / 4, maximumMW), "per-circuit fuel and turbine-limited electricity");
                Near(plan.RequiredCoolingMW, plan.NetMW, "cooling load equals electrical output");
                Near(plan.SustainableMW, plan.NetMW, "one matching atmospheric cooler sustains full fuel output");
            }
            Check(new ThermalStore { EntityId = 1, HotMJ = upgraded ? 20000000 : 200000 }.Valid(1, model.CapacityMJ),
                "pre-rebalance turbine heat remains valid");
        }
    }

    private static void Stores()
    {
        var legacyWire = ProtoBuf.Meta.RuntimeTypeModel.Create();
        using (var stream = new MemoryStream())
        {
            legacyWire.Serialize(stream, new LegacyCircuitTelemetry()); stream.Position = 0;
            var circuit = (ThermalLoopState)legacyWire.Deserialize(stream, null, typeof(ThermalLoopState));
            Check(circuit.Valid(), "retired telemetry tags do not invalidate old circuit snapshots");
            Near(circuit.ExcessMJ, 75, "saved cooling backlog survives without rescaling");
            Near(circuit.RequiredCoolingMW, 20, "cooling load derives from output instead of stale saved duplicates");
        }
        var standalone = new ThermalReactorState { Store = new ThermalStore { EntityId = 1, HotMJ = 100 } };
        var standaloneGrant = new ThermalOutputGrant(standalone, null, 100, ThermalMath.StandaloneEfficiency);
        Check(standaloneGrant.Settle(standaloneGrant.MaximumMW), "standalone output stays fuel-backed");
        Near(standalone.Store.HotMJ + standalone.Store.WasteMJ + standalone.NetOutputMW / 60, 100,
            "standalone retains integrated cooling and its original energy accounting");
        foreach (double eta in new[] { .80 })
            foreach (double load in new[] { 0.0, .01, .1, .25, .5, 1.0 })
            {
                var state = new ThermalReactorState { Mode = ThermalMode.Brayton, Store = new ThermalStore { EntityId = 1, HotMJ = 100 }, LoopVersion = 2 };
                var loop = state.Loops[0];
                var grant = new ThermalOutputGrant(state, loop, 100, eta);
                double output = (float)(grant.MaximumMW * load);
                Check(grant.Settle(output), "native float output is paid");
                Near(state.ProducedMW, output / eta, "reaction is linear in delivered power");
                Near(loop.RequiredCoolingMW, output, "cooling load is equal to delivered power");
                Near(100, state.Store.HotMJ + output / (60 * eta), "every reserved fuel MJ is accounted for");
                Near(loop.ExcessMJ, output / 60, "every delivered electrical MJ creates one cooling-load unit");
                Near(state.NetOutputMW, output, "actual output telemetry");
                Check(!grant.Settle(output), "an interval cannot be charged twice");
            }
        // Reproduce SE's float Capacity -> MW roundtrip across the T2 ramp.
        for (int step = 1; step <= 100000; step++)
        {
            double heat = (50000.0 * step / 100000) / (.8 * 60);
            var state = new ThermalReactorState { Mode = ThermalMode.Brayton, Store = new ThermalStore { EntityId = 1, HotMJ = heat } };
            var grant = new ThermalOutputGrant(state, state.Loops[0], heat, .8);
            double output = (float)((float)(grant.MaximumMW / 216000.0) * 216000f);
            Check(grant.Settle(output), "T2 native float roundtrip must not spuriously isolate runtime");
            Near(heat, state.Store.HotMJ + output / (.8 * 60), "rounded native output remains fully paid");
            Near(state.Loops[0].ExcessMJ, output / 60, "rounded native output creates matching cooling load");
            var unpaid = new ThermalReactorState { Mode = ThermalMode.Brayton, Store = new ThermalStore { EntityId = 1, HotMJ = heat } };
            Check(!new ThermalOutputGrant(unpaid, unpaid.Loops[0], heat, .8).Settle(heat * .8 * 60 * 1.000001),
                "rounding tolerance never admits output beyond allocated paid heat");
        }
        foreach (double output in new[] { -1.0, double.NaN, double.PositiveInfinity, 1000 })
        {
            var state = new ThermalReactorState { Store = new ThermalStore { EntityId = 1, HotMJ = 1 } };
            Check(!new ThermalOutputGrant(state, state.Loops[0], 1, .80).Settle(output), "invalid or unfunded output rejected");
            Near(state.Store.HotMJ, 1, "rejection does not lose credit");
        }
        var legacy = new ThermalReactorState { Mode = ThermalMode.Brayton, LoopVersion = 1,
            Store = new ThermalStore { EntityId = 1, HotMJ = 200, WasteMJ = 100 }, FuelHeatMJ = 12, Faulted = true };
        legacy.MigrateHeat(); legacy.MigrateHeat();
        Near(legacy.RetainedHeatMJ, 300, "migration retains all old heat exactly once");
        Near(legacy.Store.HotMJ, 0, "old heat is not spendable fuel credit");
        Near(legacy.FuelHeatMJ, 12, "migration preserves pending fuel bill");
        Check(legacy.Faulted && legacy.LoopVersion == 2, "migration preserves isolation");
        var serializer = new XmlSerializer(typeof(ThermalReactorState));
        var writer = new StringWriter(); serializer.Serialize(writer, legacy);
        var restored = (ThermalReactorState)serializer.Deserialize(new StringReader(writer.ToString()));
        Check(restored.Valid(1) && !restored.Valid(2), "new saved state keeps identity validation");
        Near(restored.RetainedHeatMJ, 300, "per-circuit heat survives reload");
        restored.BeginFrame(); Near(restored.RetainedHeatMJ, 300, "telemetry reset never clears accumulated heat");
        restored.Loops[0].ExcessMJ = double.NaN; Check(!restored.Valid(1), "invalid circuit heat rejected");
        var fuel = new ThermalStore();
        Near(ThermalMath.AdmitHeat(fuel, 100, 10, .0001), .0001, "last fuel quantum bounds reserve");
        Near(ThermalMath.AdmitHeat(fuel, 100, 10, 0), 0, "empty fuel cannot create credit");
    }

    private static void CoolingFailure()
    {
        foreach (double capacity in new[] { 20.0, 10, 0 })
            foreach (bool recover in new[] { false, true })
            {
                var state = new ThermalReactorState { Mode = ThermalMode.Brayton, LoopVersion = 2 };
                float heat = 0; bool critical = false, restored = false;
                double paid = 0, exported = 0, rejected = 0;
                for (int tick = 0; tick < 24000; tick++)
                {
                    state.BeginFrame();
                    paid += ThermalMath.AdmitHeat(state.Store, 100.0 / 60, 100.0 / 60, 1000000);
                    foreach (var loop in state.Loops)
                    {
                        var grant = new ThermalOutputGrant(state, loop, 25.0 / 60, .8);
                        Check(grant.Settle(grant.MaximumMW), "load remains paid during cooling loss");
                        exported += grant.MaximumMW / 60;
                    }
                    restored |= recover && ThermalMath.WasteHeatLevel(state, 100) >= 1;
                    for (int i = 0; i < 4; i++)
                        rejected += ThermalMath.CoolCircuit(state.Loops[i], i == 0 ? (restored ? 30 : capacity) : 1000) / 60;
                    heat = (float)ThermalMath.ApproachCoreHeat(heat, Math.Max(1, ThermalMath.WasteHeatLevel(state, 100)), false);
                    critical |= heat >= 1.25;
                    Near(state.Loops[1].ExcessMJ, 0, "healthy circuit cannot absorb another circuit's waste");
                }
                Near(paid, exported / .8 + state.Store.HotMJ, "failure/recovery preserves paid fuel credit");
                Near(exported, rejected + state.RetainedHeatMJ, "failure/recovery preserves every cooling-load unit");
                Check(critical == (capacity < 20 && !recover), "persistent shortage reaches failure; early repair prevents it");
                if (capacity >= 20 || recover) Near(state.RetainedHeatMJ, 0, "adequate cooling clears excess");
            }
        var stopped = new ThermalReactorState { LoopVersion = 2 };
        stopped.Loops[0].ExcessMJ = 100;
        stopped.BeginFrame(); ThermalMath.CoolCircuit(stopped.Loops[0], 60);
        Near(stopped.Loops[0].ExcessMJ, 99, "shutdown cooling needs no electrical generation");
        Near(stopped.ProducedMW, 0, "cooldown never produces new reaction heat");
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
        Check(ThermalConstruction.ShowReactorGuide(guideState, guideCheck), "show runtime unavailability even when layout is verified");
        guideState.Loops[0].Connected = true;
        Check(!ThermalConstruction.ShowReactorGuide(guideState, guideCheck), "hide verified Brayton connection guide");
        guideState.Faulted = true;
        Check(ThermalConstruction.ShowReactorGuide(guideState, guideCheck), "runtime isolation cannot be hidden behind a layout OK");
        guideState.Faulted = false;
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
        for (int bay = 0; bay < 4; bay++)
        {
            double ventAngle = bay * Math.PI / 2;
            var ventHinge = new Vector3((float)(-4.70 * Math.Cos(ventAngle)), -1.270f, (float)(4.70 * Math.Sin(ventAngle)));
            var closedVentCentre = new Vector3((float)(-4.45 * Math.Cos(ventAngle)), -1.270f, (float)(4.45 * Math.Sin(ventAngle)));
            Matrix openVent = ThermalManifolds.Pose(bay, "ChamberVent", 1);
            Check(Vector3.Distance(Vector3.Transform(ventHinge, openVent), ventHinge) < .00001f, "vent hinge stays on floor mount");
            Vector3 openVentCentre = Vector3.Transform(closedVentCentre, openVent);
            Near(openVentCentre.Y, -1.520, "open vent folds below the floor");
            Check(Vector2.Distance(new Vector2(openVentCentre.X, openVentCentre.Z), new Vector2(ventHinge.X, ventHinge.Z)) < .00001f,
                "open vent leaves its aperture clear");
            Check(ThermalManifolds.Pose(bay, "ChamberVent", .15) == Matrix.Identity, "vent remains closed before deployment clearance");
            var anchor = new Vector3((bay < 2 ? 1 : -1) * 4.12f, -2.33f, bay % 2 == 0 ? -2.5f : 2.5f);
            foreach (string part in ThermalManifolds.Parts)
            {
                Check(ThermalManifolds.Pose(bay, part, 0) == Matrix.Identity, "stowed identity pose");
                Vector3 probe = part == "ChamberVent" ? closedVentCentre : part == "ConnectorTail" ? anchor + new Vector3(.345f, 0, 0) : new Vector3(6, -2, 2);
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
                Vector3.TransformNormal(p.Normal, pose), Vector3.TransformNormal(p.HotAxis, pose), p.ReactorOnly, p.HullOnly, p.SelfSealing);
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
        Check(ThermalModels.All.Count == 59, "all model contracts generated");
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
                    peer.Model.Kind=port.ReactorOnly?ThermalKind.Reactor:port.HullOnly?ThermalKind.HullRadiator:ThermalKind.Pipe;
                    var other = new ThermalPort("CO2",port.Position,-port.Normal,port.HotAxis, hullOnly:port.HullOnly);
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
        var startingLoaded = new ThermalRotorState { EntityId = 1 };
        for (int i = 1; i <= 300; i++)
        {
            ThermalRotors.Drive(cold, 0, 650, true, 1.0 / 60);
            ThermalRotors.Drive(startingLoaded, 1, 650, true, 1.0 / 60);
            if (i == 60 || i == 150 || i == 300)
            {
                Near(cold.Rpm, i * .4 / 60.0, "unloaded startup reaches 0.4, 1 and 2 RPM at 1, 2.5 and 5 seconds");
                Near(cold.CompressorRpm, cold.Rpm, "both shafts share the idle startup ramp");
                Near(startingLoaded.Rpm, 50 * (1 - Math.Exp(-i / 240.0)),
                    "existing load immediately uses the normal response toward its target");
                Near(startingLoaded.CompressorRpm, startingLoaded.Rpm, "both shafts share the loaded response");
            }
        }
        Near(cold.Rpm, 2, "healthy enabled turbine idles at 2 RPM without generating power");
        Near(cold.CompressorRpm, 2, "both shafts share the idle speed");
        var interrupted = new ThermalRotorState { EntityId = 1 };
        for (int i = 0; i < 150; i++) ThermalRotors.Drive(interrupted, 0, 650, true, 1.0 / 60);
        ThermalRotors.Drive(interrupted, 0, 650, false, 1);
        double coast = interrupted.Rpm;
        Check(coast > 0 && coast < 1 && interrupted.TargetRpm == 0, "turning off during startup immediately coasts");
        ThermalRotors.Drive(interrupted, 0, 650, true, 1);
        Near(interrupted.Rpm, coast + .4, "restarting resumes the idle ramp from the current speed");
        double beforeLoad = interrupted.Rpm;
        ThermalRotors.Drive(interrupted, .5, 650, true, 1);
        Near(interrupted.Rpm, 26 + (beforeLoad - 26) * Math.Exp(-.25),
            "load arriving during idle startup immediately takes over without waiting for 2 RPM");
        var idleA = new ThermalRotorState { Rpm = 1.72, TargetRpm = 2 };
        var idleB = new ThermalRotorState { Rpm = 1.72, TargetRpm = 2 };
        ThermalRotors.Advance(idleA, 1);
        for (int i = 0; i < 60; i++) ThermalRotors.Advance(idleB, 1.0 / 60);
        Near(idleA.Rpm, idleB.Rpm, "idle ramp settles identically across frame sizes");
        Near(idleA.Phase, idleB.Phase, "idle-boundary phase integration is independent of frame size");
        var warm = new ThermalRotorState { EntityId = 1 };
        var hot = new ThermalRotorState { EntityId = 1 };
        var low = new ThermalRotorState { EntityId = 1 };
        for (int i = 0; i < 3600; i++)
        {
            ThermalRotors.Drive(warm, 1, 650, true, 1.0 / 60);
            ThermalRotors.Drive(hot, 1, 2200, true, 1.0 / 60);
            ThermalRotors.Drive(low, .25, 2200, true, 1.0 / 60);
            Check(hot.Valid(1) && warm.Valid(1) && low.Valid(1), "bounded rotor states and wrapped phases");
        }
        Check(hot.Rpm == warm.Rpm && hot.Rpm > low.Rpm && hot.Rpm > ThermalRotors.MaxRpm * .98,
            "load drives shaft speed independently of fuel temperature");
        Near(low.TargetRpm, 14, "quarter utilization gives 2 plus one quarter of the 48 RPM range");
        Near(hot.TargetRpm, 50, "full utilization targets 50 RPM");
        Near(hot.CompressorTargetRpm, hot.TargetRpm, "compressor and turbine share the load response");
        ThermalRotors.Drive(low, .5, 650, true, 1.0 / 60);
        Near(low.TargetRpm, 26, "half utilization targets 26 RPM");
        ThermalRotors.Drive(low, 2, 650, true, 1.0 / 60);
        Near(low.TargetRpm, 50, "overload cannot exceed maximum RPM");
        ThermalRotors.Drive(low, 0, 650, true, 1.0 / 60);
        Near(low.TargetRpm, 2, "load removal returns to idle without stopping");
        double spinning = hot.Rpm;
        ThermalRotors.Drive(hot, 1, 2200, false, 1.0 / 60);
        Check(hot.Rpm > 0 && hot.Rpm < spinning && hot.TargetRpm == 0, "disabled or faulted turbine coasts, never snaps");
        for (int i = 0; i < 7800; i++) ThermalRotors.Drive(hot, 0, 2200, false, 1.0 / 60);
        Near(hot.Rpm, 0, "shutdown reaches rest");
        Check(!warm.Valid(2), "copied rotor identity rejected");
        var serializer = new XmlSerializer(typeof(ThermalStore));
        var store = new ThermalStore { EntityId = 1, Rotor = warm, HotMJ = 50 };
        var writer = new StringWriter(); serializer.Serialize(writer, store);
        var restored = (ThermalStore)serializer.Deserialize(new StringReader(writer.ToString().Replace("</Rotor>", "<PressureMPa>11</PressureMPa></Rotor>")));
        Near(restored.Rotor.Phase, warm.Phase, "reload keeps rotor phase");
        Check(restored.Valid(1, 100) && !restored.Valid(2, 100), "rotor storage preserves heat/copy validation");
        restored.Rotor.Rpm = restored.Rotor.TargetRpm = 4000;
        restored.Rotor.CompressorRpm = restored.Rotor.CompressorTargetRpm = 2050;
        writer = new StringWriter(); serializer.Serialize(writer, restored);
        restored = (ThermalStore)serializer.Deserialize(new StringReader(writer.ToString()));
        Check(!restored.Rotor.Valid(1), "old RPM range is rejected by live snapshot validation");
        restored.Rotor.MigrateSavedRpm(1);
        Check(restored.Valid(1, 100), "old RPM save migrates without isolating heat inventory");
        Near(restored.HotMJ, 50, "RPM migration preserves stored heat");
        Near(restored.Rotor.Phase, warm.Phase, "RPM migration preserves shaft pose");
        Near(restored.Rotor.Rpm, 50, "saved turbine speed clamps to the new maximum");
        Near(restored.Rotor.CompressorRpm, 50, "saved compressor speed clamps to the new maximum");
        Near(restored.Rotor.TargetRpm, 50, "saved turbine target clamps to the new maximum");
        Near(restored.Rotor.CompressorTargetRpm, 50, "saved compressor target clamps to the new maximum");
        foreach (double invalid in new[] { double.NaN, double.PositiveInfinity, -1.0, 4001.0 })
        {
            var invalidSaved = new ThermalRotorState { EntityId = 1, Rpm = invalid };
            invalidSaved.MigrateSavedRpm(1);
            Check(!invalidSaved.Valid(1), "RPM migration cannot repair invalid saved speeds");
        }
        var copied = new ThermalRotorState { EntityId = 2, Rpm = 4000 };
        copied.MigrateSavedRpm(1);
        Near(copied.Rpm, 4000, "RPM migration cannot repair copied rotor identity");
        foreach (double invalid in new[] { double.NaN, double.PositiveInfinity, -1.0 })
        {
            ThermalRotors.Drive(warm, invalid, 650, true, 1.0 / 60);
            Check(warm.Valid(1) && warm.TargetRpm == 0, "invalid drive input cannot accelerate");
        }
        double phase = warm.Phase;
        ThermalRotors.Advance(warm, double.NaN);
        Near(warm.Phase, phase, "invalid timestep ignored");
        warm.Rpm = double.NaN;
        Check(!warm.Valid(1), "nonfinite snapshot rejected");
        var a = new ThermalRotorState { TargetRpm = ThermalRotors.MaxRpm * .6 };
        var b = new ThermalRotorState { TargetRpm = ThermalRotors.MaxRpm * .6 };
        for (int i = 0; i < 1800; i++) ThermalRotors.Advance(a, 1.0 / 60);
        for (int i = 0; i < 3600; i++) ThermalRotors.Advance(b, 1.0 / 120);
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
                if (path.Circuit != "CHAMBER")
                    for (double at = 0; at < path.Length; at += .025)
                    {
                        double end = Math.Min(path.Length, at + .30);
                        Vector3 start = path.Sample(at), finish = path.Sample(end);
                        float width = Math.Min(.11f, path.Radius * .50f);
                        for (int i = 1; i < path.Distances.Length; i++)
                        {
                            double vertex = path.Distances[i];
                            if (vertex <= at || vertex >= end) continue;
                            Vector3 chord = Vector3.Lerp(start, finish, (float)((vertex - at) / (end - at)));
                            Check(Vector3.Distance(chord, path.Points[i]) + width < path.Radius,
                                "continuous 30 cm glob fits the curved bore: " + entry.Key);
                        }
                    }
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
                Near(plan.NetMW,80,"one circuit retains normal tier conversion efficiency");
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
            Near(ThermalMath.WasteHeatLevel(state,100),.25,"core heat normalization retains full reactor rating");
        }
        var xml=new XmlSerializer(typeof(ThermalReactorState));var writer=new StringWriter();xml.Serialize(writer,state);
        var restored=(ThermalReactorState)xml.Deserialize(new StringReader(writer.ToString().Replace("</ThermalLoopState>", "<Charge>0.5</Charge></ThermalLoopState>")));
        Near(restored.Store.HotMJ + restored.Store.WasteMJ, 150, "legacy charge fields are ignored without losing saved heat");
        Check(restored.Valid(1) && !restored.Valid(2),"loop snapshots remain identity-bound through save/reload");
        restored.Loops[0].NetMW=double.NaN;Check(!restored.Valid(1),"nonfinite thermal diagnostics rejected");
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
            valves.Deployment=1;valves.Faulted=true;Check(ThermalLoops.OpenValves(valves)==mask,"generation isolation preserves intact cooling valves");
            valves.Faulted=false;valves.Mode=ThermalMode.Standalone;Check(ThermalLoops.OpenValves(valves)==0,"standalone valves remain closed");
        }
        Check(ThermalLoops.OpenValves(null)==0,"missing circuit state fails closed");
    }

    private static void LoopEnergy()
    {
        foreach (double eta in new[] { .80 })
        {
            var state = new ThermalReactorState { Mode = ThermalMode.Brayton, LoopVersion = 2 };
            double paid = 0, exported = 0, rejected = 0;
            for (int active = 4; active >= 0; active--)
                foreach (double load in new[] { 0.0, .1, .4, 1.0, .2, 0.0 })
                    for (int tick = 0; tick < 600; tick++)
                    {
                        state.BeginFrame();
                        paid += ThermalMath.AdmitHeat(state.Store, 100.0 / 60, active * 25.0 / 60, 1000000);
                        for (int i = 0; i < active; i++)
                        {
                            var grant = new ThermalOutputGrant(state, state.Loops[i], 25.0 / 60, eta);
                            double output = (float)(grant.MaximumMW * load);
                            Check(grant.Settle(output), "available circuits retain their fixed quarter allocation");
                            exported += output / 60;
                        }
                        foreach (var loop in state.Loops) rejected += ThermalMath.CoolCircuit(loop, 60) / 60;
                        Near(state.ProducedMW, state.NetOutputMW / eta, "demand steps preserve linear reaction");
                        Near(paid, exported / eta + state.Store.HotMJ, "load/loss/no-load fuel-credit balance");
                        Near(exported, rejected + state.RetainedHeatMJ, "load/loss/no-load cooling budget");
                    }
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
        Near(ThermalRadiators.Cooling(60, 1, 0, 0), 60, "edge-on keeps cooling rating");
        Near(ThermalRadiators.Cooling(60, 1, 0, .5), 45, "half solar exposure retains 75% cooling");
        Near(ThermalRadiators.Cooling(60, 1, 0, 1), 30, "full sun on one face retains 50% cooling");
        Near(ThermalRadiators.Cooling(60, 0, 0, 0), 0, "occluded tracked radiator cannot cool");
        Near(ThermalRadiators.Cooling(60, .5, 0, 0), 30, "solar shade does not undo obstructed radiating area");
        double atmosphericFactor = ThermalMath.RadiativeCooling(1, 1, 25);
        Near(ThermalRadiators.AmbientEfficiency(0), 1, "vacuum has no atmospheric radiator penalty");
        Near(ThermalRadiators.AmbientEfficiency(1), atmosphericFactor, "full atmosphere retains reference sink");
        Check(ThermalRadiators.AmbientEfficiency(.0011) > .999,
            "trace atmosphere no longer switches to the full atmospheric penalty");
        double previousCooling = double.MaxValue;
        for (int i = 0; i <= 1000; i++)
        {
            double density = i / 1000.0;
            double cooling = ThermalRadiators.Cooling(100000, 1, density, 0);
            Check(cooling <= previousCooling && cooling >= 100000 * atmosphericFactor - .000001,
                "radiator atmosphere transition is continuous and bounded");
            if (i > 0) Check(previousCooling - cooling < 100, "no atmosphere threshold cliff");
            previousCooling = cooling;
        }
        Near(ThermalRadiators.Cooling(100000, 1, double.NaN, 0), 0, "invalid density cannot grant cooling");
        Near(ThermalRadiators.Cooling(100000, 1, double.PositiveInfinity, 0), 0, "infinite density fails closed");
        foreach (double cosine in new[] { -1.0, 1.0 })
        {
            Near(ThermalRadiators.SolarExposure(cosine, 1, 1, false), 1, "either face receives full solar load");
            Near(ThermalRadiators.SolarExposure(cosine, .5, 1, false), .5, "four of eight lit pivots give half exposure");
            Near(ThermalRadiators.SolarExposure(cosine, 1, .5, false), .5, "native weather attenuates solar load");
            Near(ThermalRadiators.SolarExposure(cosine, 0, 1, false), 0, "complete local shadow removes solar load");
            Near(ThermalRadiators.SolarExposure(cosine, 1, 1, true), 0, "planetary eclipse removes solar load");
            Near(ThermalRadiators.SolarExposure(cosine, 1, 0, false), 0, "zero weather sunlight removes solar load");
        }
        Near(ThermalRadiators.Cooling(60,1,0,ThermalRadiators.SolarExposure(.5,.5,.5,false)),56.25,
            "oblique incidence, partial shade and weather multiply like solar panels");
        Near(ThermalRadiators.SolarExposure(0,1,1,false),0,"edge-on receives no solar load");
        Near(ThermalRadiators.SolarEfficiency(ThermalRadiators.SolarExposure(1,1,2,false)),.5,"enhanced weather cannot exceed 50% solar penalty");
        Near(ThermalRadiators.SolarExposure(double.NaN,1,1,false),1,"invalid sampled sun is conservatively fully exposed");
        Near(ThermalRadiators.Cooling(60,1,0,double.NaN),0,"invalid solar state cannot grant cooling");
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
            bool active = suffix == "AtmosphericCooler";
            Near(standard.CoolingMW,active ? 5000 : suffix == "SpaceRadiator" ? 0 : 2000,"cooler and panels provide cooling; the rotor base provides none");
            Near(upgraded.CoolingMW,active ? 50000 : suffix == "SpaceRadiator" ? 0 : 20000,"upgraded rotor bases do not add a fourth panel's cooling");
            Near(standard.RatingMW,25000,"standard saved thermal capacity preserved");
            Near(upgraded.RatingMW,250000,"upgraded saved thermal capacity preserved");
            Check(standard.Cells==upgraded.Cells && standard.Ports.Length==upgraded.Ports.Length,"upgrades retain socket and footprint contract");
            if (active)
                foreach (var cooler in new[] { standard, upgraded })
                {
                    Near(ThermalMath.AirCooling(cooler.CoolingMW,0,1),0,"actual cooler has zero vacuum capacity");
                    Near(ThermalMath.AirCooling(cooler.CoolingMW,.5,1),cooler.CoolingMW*.5,"actual cooler scales at half atmosphere");
                    Near(ThermalMath.AirCooling(cooler.CoolingMW,1,1),cooler.CoolingMW,"actual cooler reaches rating at one atmosphere");
                    Near(ThermalMath.AirCooling(cooler.CoolingMW,2,1),cooler.CoolingMW,"dense atmosphere cannot exceed cooler rating");
                    Near(ThermalMath.AirCooling(cooler.CoolingMW,1,0),0,"blocked upgraded fans cannot reject heat");
                }
        }
        var model = ThermalModels.All["ArcanePower_Thermal_SpaceRadiator"];
        Check(model.Cells == new Vector3I(1, 1, 1), "airtight rotor base fits one hull cell");
        Check(model.Ports.Length == 1, "one stationary duplex radiator port");
        var extension = ThermalModels.All["ArcanePower_Thermal_RadiatorPanel"];
        Check(extension.Cells == new Vector3I(3, 2, 3) && extension.Ports.Length == 0, "stack panel uses shared base plumbing");
        var frames = new List<MatrixD> { MatrixD.CreateFromYawPitchRoll(.7, .4, -.8) };
        foreach (var orientation in Orientations())
            frames.Add(MatrixD.CreateWorld(Vector3D.Zero, orientation.Forward, orientation.Up));
        foreach (MatrixD frame in frames)
        {
            MatrixD root = frame; root.Translation = new Vector3D(20, 30, -40);
            for (int index = 0; index < 4; index++)
                for (int placedYaw = 0; placedYaw < 4; placedYaw++)
                {
                    MatrixD child = MatrixD.CreateRotationY(placedYaw * Math.PI / 2) * root;
                    child.Translation = ThermalRadiators.ExtensionCentre(root, index);
                    Check(ThermalRadiators.FitsExtension(root, child, index) == (index < 3),
                        "all four placed yaws attach for three consecutive panels; a fourth is rejected");
                    if (index >= 3) continue;
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
                                double x = index == 0 ? 0 : side * 3.05;
                                Vector3D top = Vector3D.Transform(new Vector3D(x, index == 0 ? .25 : 2.5, 0), lower);
                                Vector3D bottom = Vector3D.Transform(new Vector3D(x, -2.5, 0), upper);
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
        Near(ThermalRadiators.Cooling(model.CoolingMW, 1, 0, 0), 0, "empty rotor base cannot reject heat");
        Near(3 * ThermalRadiators.Cooling(extension.CoolingMW, 1, 0, 0), 6000, "three standard panels reject 6 GW");
        var upgrade = ThermalModels.All["ArcanePower_Thermal_RadiatorPanelUpgraded"];
        Near(3 * ThermalRadiators.Cooling(upgrade.CoolingMW,1,0,0),60000,"three upgraded panels reject 60 GW");
        Near(6 * ThermalRadiators.Cooling(upgrade.CoolingMW,1,0,0),120000,"two complete upgraded stacks reject 120 GW in vacuum");
        Near(ThermalRadiators.Cooling(extension.CoolingMW,1,0,0)+2*ThermalRadiators.Cooling(upgrade.CoolingMW,1,0,0),42000,"mixed tier panels add individual cooling ratings");
        state.Angle = 0; state.Panels = 0;
        Check(state.Valid(1), "empty rotor base state survives save and replication");
        state.Angle = 0; state.Panels = 4;
        Check(!state.Valid(1), "reject excessive attached count");
        state.Panels = 1; state.ParentId = -1;
        Check(!state.Valid(1), "reject invalid parent identity");
    }

    private static ThermalForecast Forecast(double heat, double target, ThermalReactorState state = null,
        bool generating = true, bool runaway = false)
    {
        var forecast = new ThermalForecast();
        for (int i = 0; i < 300; i++) forecast.Update(heat, target, runaway, state, 100, generating);
        return forecast;
    }

    private static void CooldownForecasts()
    {
        foreach (double initial in new[] { .2, .8, 1.0, 1.1 })
        foreach (var mode in new[] { ThermalMode.Standalone, ThermalMode.Brayton })
        foreach (double stored in new[] { 0.0, 20.0, 100.0 })
        foreach (double capacity in new[] { 0.0, 10.0, 50.0 })
        {
            var state = new ThermalReactorState { Mode = mode, CoolingMW = capacity };
            if (mode == ThermalMode.Standalone) state.Store.WasteMJ = stored;
            else { state.Loops[0].ExcessMJ = stored; state.Loops[0].CoolingMW = capacity; }
            var forecast = new ThermalForecast();
            forecast.Update(initial, 0, false, state, 100, false);
            Near(state.RetainedHeatMJ, stored, "cooldown forecasting cannot consume saved heat");
            float actual = (float)initial;
            double elapsed = 0;
            while (actual > ThermalMath.CooldownHeat && actual < 1.25 && elapsed < 3600)
            {
                if (mode == ThermalMode.Standalone) ThermalMath.Reject(state.Store, capacity / 60, false);
                else
                {
                    ThermalMath.CoolCircuit(state.Loops[0], capacity);
                    // One reactor-wide passive budget, after active rejection.
                    state.Loops[0].ExcessMJ = Math.Max(0, state.Loops[0].ExcessMJ - 100 * .02 / 60);
                }
                actual = (float)ThermalMath.ApproachCoreHeat(actual, ThermalMath.WasteHeatLevel(state, 100), false);
                elapsed += 1.0 / 60;
            }
            if (actual >= 1.25 || actual > ThermalMath.CooldownHeat)
                Check(forecast.CooldownSeconds < 0, "unstable or unbounded cooldown cannot advertise a countdown");
            else Check(Math.Abs(forecast.CooldownSeconds - elapsed) < 1,
                "cooldown estimate matches per-frame cooling within one second");
        }
        var clean = new ThermalForecast(); clean.Update(1, 0, false, null, 100, false);
        Check(clean.CooldownSeconds > 56 && clean.CooldownSeconds < 58, "full healthy core reaches 15% in about 57 seconds despite zero reaction heat");
        clean.Update(ThermalMath.CooldownHeat, 0, false, null, 100, true);
        Check(clean.CooldownSeconds < 0, "generating reactor has no shutdown countdown");
        clean.Update(1, 4, true, null, 100, false);
        Check(clean.CooldownSeconds < 0, "runaway containment has no safe cooldown estimate");
        var trapped = new ThermalReactorState { Mode = ThermalMode.Brayton };
        trapped.Store.HotMJ = 10000; trapped.Loops[0].ExcessMJ = 100;
        var passive = new ThermalForecast(); passive.Update(.8, 0, false, trapped, 100, false);
        Check(passive.CooldownSeconds < 0, "paid fuel credit consumes the shared passive drain budget before trapped loop heat");
        Near(trapped.Store.HotMJ, 10000, "cooldown estimate preserves unused paid fuel credit");
        var motion = new MotionState { CooldownStartHeat = .8f, ForecastCooldownSeconds = 50 };
        var wire = ProtoBuf.Meta.RuntimeTypeModel.Create();
        using (var stream = new MemoryStream())
        {
            wire.Serialize(stream, motion); stream.Position = 0;
            var restored = (MotionState)wire.Deserialize(stream, null, typeof(MotionState));
            Near(restored.CooldownStartHeat, .8f, "shutdown baseline reaches clients unchanged");
            Near(restored.ForecastCooldownSeconds, 50, "server cooldown ETA survives replication");
        }
    }

    private static void ThermalForecasts()
    {
        foreach (double initial in new[] { 0.0, .5, .85, 1.0 })
            Check(Forecast(initial, 1).PeakHeat <= 1, "normal full-load warmup never forecasts overheating");
        Near(Forecast(1.1, 0, null, false).PeakHeat, 1.1, "cooling residual heat has no predicted rise");
        Check(Forecast(.2, 2.5, null, true, true).Warning, "failed containment immediately warns");
        foreach (double initial in new[] { .2, .8, 1.0, 1.1 })
            foreach (double retained in new[] { 0.0, 20.0, 100.0 })
                foreach (double rate in new[] { -5.0, 0.0, .01, .5, 5.0 })
                {
                    var state = new ThermalReactorState { Mode = ThermalMode.Brayton, ProducedMW = 80, RequiredCoolingMW = 20 };
                    var loop = state.Loops[0]; loop.Connected = true;
                    loop.ExcessMJ = retained; loop.OutputMW = 20; loop.CoolingMW = 20 - rate;
                    // Rejection is what this interval actually removed; spare
                    // capacity must still be available to the future forecast.
                    loop.RejectedMW = state.RejectedMW = Math.Min(20 + retained * 60, loop.CoolingMW);
                    var forecast = Forecast(initial, .8, state);
                    float actual = (float)initial; double peak = actual, waste = retained;
                    double overheat = -1, meltdown = -1;
                    for (int frame = 1; frame <= 3600; frame++)
                    {
                        waste = Math.Max(0, waste + rate / 60.0);
                        bool critical = actual >= 1.25;
                        actual = (float)ThermalMath.ApproachCoreHeat(actual,
                            Math.Max(critical ? 4 : .8, Math.Min(4, waste / 50)), critical);
                        peak = Math.Max(peak, actual);
                        if (overheat < 0 && actual > 1.001) overheat = frame / 60.0;
                        if (meltdown < 0 && actual >= 1.25) meltdown = frame / 60.0;
                    }
                    Check(Math.Abs(forecast.PeakHeat - peak) < .02, "projection matches independent live integration");
                    Check((forecast.PeakHeat > Math.Max(initial, 1) + .001) == (peak > Math.Max(initial, 1) + .001),
                        "projection detects the same rising overheat risk");
                    Check((forecast.OverheatSeconds < 0) == (overheat < 0)
                        && (overheat < 0 || Math.Abs(forecast.OverheatSeconds - overheat) < .3), "overheat ETA agrees with live integration");
                    Check((forecast.MeltdownSeconds < 0) == (meltdown < 0)
                        && (meltdown < 0 || Math.Abs(forecast.MeltdownSeconds - meltdown) < .3), "critical ETA agrees with live integration");
                    Near(loop.ExcessMJ, retained, "forecast never changes physical heat inventories");
                }
        var balanced = new ThermalReactorState { Mode = ThermalMode.Brayton, ProducedMW = 80, RequiredCoolingMW = 20 };
        var first = balanced.Loops[0]; first.Connected = true; first.OutputMW = first.CoolingMW = 20;
        var stable = Forecast(.8, .8, balanced);
        first.CoolingMW = 18.3;
        for (int i = 1; i <= 120; i++)
        {
            stable.Update(.8, .8, false, balanced, 100, true);
            Check(stable.PeakHeat > 1.001 && stable.MeltdownSeconds < 0, "moderate deficit is an ordinary overheat prediction");
            Check(stable.Warning == (i == 120), "ordinary warning needs two continuous seconds");
        }
        first.CoolingMW = 20;
        for (int i = 1; i <= 300; i++)
        {
            stable.Update(.8, .8, false, balanced, 100, true);
            Check(stable.Warning == (i < 300), "safe forecast must persist for five seconds before clearing");
        }
        first.CoolingMW = 25;
        for (int i = 0; i < 12; i++)
        {
            balanced.ProducedMW = 100; first.OutputMW = balanced.RequiredCoolingMW = 60;
            first.ExcessMJ += 35.0 / 60;
            stable.Update(.8, 1, false, balanced, 100, true);
            Check(!stable.Warning && stable.PeakHeat <= 1, "200 ms load spike is not projected for a full minute");
        }
        balanced.ProducedMW = 80; first.OutputMW = balanced.RequiredCoolingMW = 20;
        for (int i = 0; i < 300; i++)
        {
            first.ExcessMJ = Math.Max(0, first.ExcessMJ - 5.0 / 60);
            stable.Update(.8, .8, false, balanced, 100, true);
            Check(!stable.Warning, "brief spike clears within spare cooling without a delayed flash");
        }
        first.CoolingMW = 0;
        stable.Update(.8, .8, false, balanced, 100, true);
        Check(stable.Warning && stable.MeltdownSeconds > 0 && stable.Circuit == 1,
            "cooler loss immediately recomputes the forecast and bypasses confirmation for critical risk");
        first.Connected = false;
        stable.Update(.8, 0, false, balanced, 100, false);
        Check(stable.PeakHeat <= .8 && stable.MeltdownSeconds < 0,
            "shutdown and circuit isolation stop projected production immediately despite recent load");
        var isolated = new ThermalReactorState { Mode = ThermalMode.Brayton, ProducedMW = 80, RequiredCoolingMW = 40 };
        isolated.Loops[0].Connected = isolated.Loops[1].Connected = true;
        isolated.Loops[0].OutputMW = isolated.Loops[1].OutputMW = 20;
        isolated.Loops[0].CoolingMW = 100; isolated.Loops[1].CoolingMW = 0;
        var hot = Forecast(.8, .8, isolated);
        Check(hot.Warning && hot.Circuit == 2 && hot.MeltdownSeconds > 0, "cold circuit surplus cannot mask circuit 2");
        var standalone = new ThermalReactorState { ProducedMW = 100, RequiredCoolingMW = 80, CoolingMW = 80 };
        standalone.Store.HotMJ = 1000000;
        Check(!Forecast(1, 1, standalone).Warning, "balanced standalone and paid fuel credit never warn");
        var cooling = new ThermalReactorState { Mode = ThermalMode.Brayton };
        cooling.Loops[0].ExcessMJ = cooling.Loops[1].ExcessMJ = 50;
        var passive = Forecast(.8, 0, cooling, false);
        Check(passive.PeakHeat <= 1 && !passive.Warning, "shared passive cooldown cannot manufacture heat");
        Near(cooling.Loops[0].ExcessMJ + cooling.Loops[1].ExcessMJ, 100, "cooldown projection preserves real retained energy");
        var invalid = new ThermalForecast(); invalid.Update(double.NaN, 0, false, null, 100, false);
        Check(invalid.Warning && invalid.PeakHeat == 4, "invalid forecast inputs fail visibly");
        var motion = new MotionState { Core = CorePhase.Running, Heat = .8f, ForecastPeakHeat = 1.1f };
        var warning = typeof(MotionState).GetProperty("ThermalWarning", BindingFlags.Instance | BindingFlags.NonPublic);
        Check(!(bool)warning.GetValue(motion, null), "unconfirmed peak cannot light client emissives");
        motion.ForecastWarning = true;
        Check((bool)warning.GetValue(motion, null), "server-confirmed warning drives all presentation");
        motion.ForecastPeakHeat = motion.Heat;
        Check((bool)warning.GetValue(motion, null), "recovery hold survives safe forecast replication");
        motion.Critical = true;
        Check(!(bool)warning.GetValue(motion, null), "armed meltdown retains critical red priority");
    }

    private static void MeltdownCountdown()
    {
        Type hazards = typeof(CoreHazard).Assembly.GetType("ArcanePower.CoreHazards");
        var secondsMethod = hazards.GetMethod("Seconds", BindingFlags.Static | BindingFlags.NonPublic);
        var advanceMethod = hazards.GetMethod("AdvanceFuse", BindingFlags.Static | BindingFlags.NonPublic);
        Func<CoreHazard, float> seconds = core => (float)secondsMethod.Invoke(null, new object[] { core });
        Action<CoreHazard> advance = core => advanceMethod.Invoke(null, new object[] { core });
        var serializer = new XmlSerializer(typeof(CoreHazard));
        Func<CoreHazard, CoreHazard> reload = core => {
            using (var writer = new StringWriter())
            {
                serializer.Serialize(writer, core);
                return (CoreHazard)serializer.Deserialize(new StringReader(writer.ToString()));
            }
        };
        foreach (float heat in new[] { 1.25f, 1.5f, 2f, 3f, 4f })
        {
            var core = new CoreHazard { SourceId = 1, Tier = 3, Critical = true, Heat = heat, PeakHeat = heat, FuseVersion = 1 };
            Near(seconds(core), 60, "new meltdown allows sixty seconds at every heat level");
            for (int frame = 0; frame < 3599; frame++)
            {
                float before = seconds(core);
                advance(core);
                Check(seconds(core) > 0 && seconds(core) < before, "countdown advances monotonically without premature detonation");
                if (frame == 299)
                {
                    Check(Math.Abs(seconds(core) - 55f) < .01, "normal five-second ejection leaves a useful response window");
                    core.CarrierId = 123; core.Heat = 0;
                    Near(seconds(reload(core)), seconds(core), "ejection and cooling do not reset the countdown");
                }
                if (frame == 1799)
                {
                    float saved = seconds(core); core = reload(core);
                    Near(seconds(core), saved, "reload preserves the exact remaining countdown");
                    core.CarrierId = 0; core.Heat = core.PeakHeat = 4;
                }
            }
            Check(seconds(core) <= .04, "sixty-second timer reaches its last simulation frame");
            advance(core); advance(core);
            Near(seconds(core), 0, "expired countdown is clamped to zero");
            advance(core); Near(seconds(core), 0, "expired cores cannot gain a new countdown");
        }
        foreach (float heat in new[] { 1.25f, 1.5f, 2f, 3f, 4f })
        {
            var legacy = (CoreHazard)serializer.Deserialize(new StringReader(
                "<CoreHazard><Critical>true</Critical><Fuse>45</Fuse><PeakHeat>" + heat.ToString(System.Globalization.CultureInfo.InvariantCulture) + "</PeakHeat></CoreHazard>"));
            double remaining = 45 / (1 + 4 * Math.Max(0, heat - 1.25));
            Near(seconds(legacy), remaining, "legacy fuse is interpreted as its saved remaining time");
            advance(legacy);
            Near(seconds(legacy), remaining - 1.0 / 60, "legacy migration retains remaining seconds without granting fresh time");
            Check(legacy.FuseVersion == 1, "legacy fuse migrates once");
            legacy = reload(legacy); legacy.PeakHeat = 4;
            advance(legacy);
            Near(seconds(legacy), remaining - 2.0 / 60, "migrated timer never reapplies heat acceleration after reload");
        }
        var wire = ProtoBuf.Meta.RuntimeTypeModel.Create();
        foreach (float remaining in new[] { 0f, 17f, 60f })
            using (var buffer = new MemoryStream())
            {
                var core = new CoreHazard { Critical = true, FuseVersion = 1, Fuse = remaining, PeakHeat = 4 };
                wire.Serialize(buffer, core); buffer.Position = 0;
                var received = (CoreHazard)wire.Deserialize(buffer, null, typeof(CoreHazard));
                Near(seconds(received), remaining, "wire roundtrip preserves expired, partial and fresh timers despite the constructor default");
                Check(received.FuseVersion == 1 && received.Critical, "wire retains irreversible countdown semantics");
            }
        var motion = new MotionState { Critical = true, CriticalSeconds = 60 };
        var valid = typeof(CoreHazard).Assembly.GetType("ArcanePower.Reactor").GetMethod("Valid", BindingFlags.Static | BindingFlags.NonPublic);
        Check((bool)valid.Invoke(null, new object[] { motion }), "sixty-second countdown survives motion packet/save validation");
        motion.CriticalSeconds = 60.1f;
        Check(!(bool)valid.Invoke(null, new object[] { motion }), "countdown validation remains bounded");
        motion.CriticalSeconds = 60; motion.ForecastPeakHeat = 4;
        Check((bool)valid.Invoke(null, new object[] { motion }), "bounded heat forecast survives save/packet validation");
        foreach (float bad in new[] { -.1f, 4.1f, float.NaN, float.PositiveInfinity })
        {
            motion.ForecastPeakHeat = bad;
            Check(!(bool)valid.Invoke(null, new object[] { motion }), "invalid heat forecasts are rejected");
        }
    }

    private static void PipeRotors()
    {
        // Replace the first circuit's adapter/tee connection with a rotary
        // union. Grid-local coordinates deliberately differ across the joint.
        var nodes = IndependentLayout();
        var adapter = nodes.Find(n => n.Id == 10);
        var tee = nodes.Find(n => n.Id == 11);
        var stator = new ThermalEndpoint { Id = 1000, GridId = 1, Healthy = true,
            Model = ThermalModels.All["ArcanePower_Thermal_PipeRotor"],
            Ports = new[] { new ThermalPort("CO2", new Vector3(1,0,0), -Vector3.UnitX, Vector3.UnitY) }, RotaryPeerId = 1001 };
        var head = new ThermalEndpoint { Id = 1001, GridId = 2, Healthy = true,
            Model = ThermalModels.All["ArcanePower_Thermal_PipeRotorHead"],
            Ports = new[] { new ThermalPort("CO2", new Vector3(1,0,0), Vector3.UnitX, Vector3.UnitY) }, RotaryPeerId = 1000 };
        foreach (var node in nodes) if (node.Id >= 11 && node.Id <= 14) node.GridId = 2;
        nodes.Add(stator); nodes.Add(head);
        var source = nodes[0];
        for (int pose = 0; pose < 72; pose++)
        {
            // Independent grid coordinate frames may rotate/translate arbitrarily.
            var network = new ThermalNetwork(nodes);
            Check(network.Loops(source)[0].Ready, "rotary union preserves H/C through independent grid coordinate frames");
            Check(network.PhysicalComponent(tee).Contains(source), "construction crosses native rotary union");
            Check(ThermalConstruction.Inspect(nodes,tee.Id).Verified, "subgrid construction verifies connected source");
            Check(network.FlowDirections(new HashSet<long>{source.Id},new HashSet<long>{12})[head.Id][0] != 0,
                "cosmetic flow traverses the rotary union");
            Check(ThermalNetwork.Match(stator,stator.Ports[0],head,head.Ports[0]) == ThermalJointStatus.Open,
                "coincident socket coordinates on different grids never create ordinary joints");
            // Move the complete subgrid frame; the rotary joint remains by ID.
            foreach (var node in nodes) if (node.GridId == 2)
                foreach (var port in node.Ports)
                {
                    var turn = Matrix.CreateRotationY(.123f);
                    port.Position = Vector3.Transform(port.Position, turn) + new Vector3(10,7,-3);
                    port.Normal = Vector3.TransformNormal(port.Normal, turn);
                    port.HotAxis = Vector3.TransformNormal(port.HotAxis, turn);
                }
        }
        var rotary = new List<ThermalEndpoint>{stator,head};
        Check(ThermalNetwork.ConnectedGrids(1,rotary).SetEquals(new[]{1L,2L}), "only reciprocal healthy union admits subgrid");
        var cache = new ThermalCircuitCache(nodes);
        head.RotaryPeerId = 0;
        Check(!cache.Matches(nodes), "detachment invalidates cached circuits");
        Check(!new ThermalNetwork(nodes).Loops(source)[0].Ready, "one-sided attachment is isolated");
        Check(!ThermalNetwork.ConnectedGrids(1,rotary).Contains(2), "detachment removes grid admission");
        head.RotaryPeerId = stator.Id;
        Check(new ThermalNetwork(nodes).Loops(source)[0].Ready, "reattachment restores circuit");
        foreach (var broken in rotary)
        {
            broken.Healthy = false;
            Check(!new ThermalNetwork(nodes).Loops(source)[0].Ready, "damage, incomplete weld or denied access breaks union");
            broken.Healthy = true;
        }
        head.RotaryPeerId = 9999;
        Check(!new ThermalNetwork(nodes).Loops(source)[0].Ready, "foreign head cannot bridge union");
        head.RotaryPeerId = stator.Id;
        head.GridId = stator.GridId;
        Check(!new ThermalNetwork(nodes).RotaryConnected(stator), "merged same-grid attachment is rejected");
        head.GridId = 2;
        var originalModel = head.Model;
        head.Model = adapter.Model;
        Check(!new ThermalNetwork(nodes).RotaryConnected(stator), "ordinary pipe cannot impersonate native union");
        head.Model = originalModel;
        stator.Revision++;
        Check(!cache.Matches(nodes), "attachment/repair events invalidate even after a quick restore");
        head.RotaryPeerId = 0;
        var circuits = new ThermalNetwork(nodes).Loops(source);
        Check(!circuits[0].Ready && circuits[1].Ready && circuits[2].Ready && circuits[3].Ready,
            "one detached union does not trip independent manifold circuits");
    }

    private static void HullRadiators()
    {
        var wire=ProtoBuf.Meta.RuntimeTypeModel.Create();
        using(var stream=new MemoryStream())
        {
            wire.Serialize(stream,new LegacyRadiatorConnections());stream.Position=0;
            var restored=(ThermalRadiatorState)wire.Deserialize(stream,null,typeof(ThermalRadiatorState));
            Check(restored.Valid(42) && restored.RequiredPanels==3,"retired hull socket history is ignored without losing stack state");
        }
        using(var reader=new StringReader("<ThermalRadiatorState><EntityId>42</EntityId><RequiredPorts>31</RequiredPorts><RequiredPanels>3</RequiredPanels></ThermalRadiatorState>"))
        {
            var restored=(ThermalRadiatorState)new XmlSerializer(typeof(ThermalRadiatorState)).Deserialize(reader);
            Check(restored.Valid(42) && restored.RequiredPanels==3,"old XML hull history cannot latch a self-sealing socket open");
        }
        var model=ThermalModels.All["ArcanePower_Thermal_HullRadiator"];
        var upgraded=ThermalModels.All[model.Subtype+"Upgraded"];
        Check(model.Cells==new Vector3I(3,2,1) && model.Ports.Length==5,"fixed hull footprint and five duplex unions");
        Near(model.CoolingMW,1000,"single-face standard radiator rating");
        Near(upgraded.CoolingMW,10000,"single-face upgraded radiator rating");
        foreach(var rotation in Orientations())
        {
            var nodes=new List<ThermalEndpoint>();
            var centre=ThermalEndpoint.At(10,1,model,rotation,Vector3.Zero,true);
            var rear=centre.Ports[0];
            Func<ThermalPort,ThermalPort> reverse=p=>new ThermalPort("CO2",p.Position,-p.Normal,p.HotAxis);
            var inlet=new ThermalPort("CO2",rear.Position+rear.Normal*2.5f,rear.Normal,rear.HotAxis);
            var turbinePort=new ThermalPort("CO2",rear.Position+Vector3.Cross(rear.Normal,rear.HotAxis)*2.5f,
                Vector3.Cross(rear.Normal,rear.HotAxis),rear.HotAxis);
            var source=new ThermalEndpoint{Id=1,GridId=1,Healthy=true,Model=new ThermalModel{Kind=ThermalKind.Reactor},Ports=new[]{reverse(inlet)}};
            var hub=new ThermalEndpoint{Id=2,GridId=1,Healthy=true,Model=new ThermalModel{Kind=ThermalKind.Pipe},Ports=new[]{reverse(rear),inlet,turbinePort}};
            var train=new ThermalEndpoint{Id=3,GridId=1,Healthy=true,Model=ThermalModels.All["ArcanePower_Thermal_BraytonTrain"],Ports=new[]{reverse(turbinePort)}};
            nodes.Add(source);nodes.Add(hub);nodes.Add(train);nodes.Add(centre);
            foreach(var offset in new[]{new Vector3(7.5f,0,0),new Vector3(-7.5f,0,0),new Vector3(0,5,0),new Vector3(0,-5,0)})
                nodes.Add(ThermalEndpoint.At(nodes.Count+10,1,model,rotation,Vector3.TransformNormal(offset,rotation),true));
            var net=new ThermalNetwork(nodes);
            var circuit=net.Loops(source)[0];
            Check(circuit.Ready && circuit.Nodes.Count==8,"one rear feed supplies all four hull edges in every block orientation");
            Check(net.OpenPorts(centre)==31,"four edge unions and the rear socket open only when actually mated");
            Check(ThermalConstruction.Inspect(nodes,centre.Id).Verified,"sealed unused sockets do not create guide faults");
            var units=new List<ThermalUnit>{new ThermalUnit{Kind=ThermalKind.Train,RatingMW=4375}};
            foreach(var node in circuit.Nodes)if(node.Model.Kind==ThermalKind.HullRadiator)
                units.Add(new ThermalUnit{Kind=node.Model.Kind,CoolingMW=node.Model.CoolingMW});
            Near(ThermalMath.Dispatch(4375,1200,units).CoolingMW,5000,"daisy-chain cooling adds each radiator once");
            var last=nodes[nodes.Count-1];
            var flow=net.FlowDirections(new HashSet<long>{source.Id},new HashSet<long>{last.Id});
            Check(flow.ContainsKey(last.Id),"coolant flow reaches a radiator through its edge");
            foreach(var neighbor in nodes.FindAll(n=>n!=centre && n.Model.Kind==ThermalKind.HullRadiator))
            {
                nodes.Remove(neighbor);net=new ThermalNetwork(nodes);circuit=net.Loops(source)[0];
                Check(circuit.Ready && circuit.Nodes.Count==7,"removing a radiator on any edge leaves the remaining array sealed");
                Check(net.Joints.Exists(j=>j.Node==centre && j.Status==ThermalJointStatus.Closed),"lost neighbor is visibly self-sealed");
                Check(ThermalConstruction.Inspect(nodes,centre.Id).Verified,"self-sealed removal is not a construction fault");
                var remaining=new List<ThermalUnit>{units[0]};
                foreach(var node in circuit.Nodes)if(node.Model.Kind==ThermalKind.HullRadiator)
                    remaining.Add(new ThermalUnit{Kind=node.Model.Kind,CoolingMW=node.Model.CoolingMW});
                Near(ThermalMath.Dispatch(4375,1200,remaining).CoolingMW,4000,"removed radiator no longer contributes cooling");
                var valves=new ThermalReactorState{Mode=ThermalMode.Brayton,Deployment=1};valves.Loops[0].Connected=circuit.Ready;
                Check(ThermalLoops.OpenValves(valves)==1,"sealed array loss keeps the reactor valve open");
                nodes.Add(neighbor);
            }
            last.Healthy=false;
            Check(!new ThermalNetwork(nodes).Loops(source)[0].Ready,"inaccessible attached radiator cannot join the circuit");last.Healthy=true;
            Check(new ThermalNetwork(nodes).Loops(source)[0].Ready,"replacing a radiator reconnects the array");
            var joint=new ThermalNetwork(nodes).Joints.Find(j=>j.Node==last && j.Peer==centre);
            joint.Port.HotAxis=-joint.Port.HotAxis;
            Check(!new ThermalNetwork(nodes).Loops(source)[0].Ready,"reversed H/C cannot auto-seal a bad connection");joint.Port.HotAxis=-joint.Port.HotAxis;
            var saved=last.Model;last.Model=hub.Model;
            Check(ThermalNetwork.Match(last,joint.Port,centre,centre.Ports[4])!=ThermalJointStatus.Matched,"normal pipes cannot impersonate radiator edges");
            Check(!new ThermalNetwork(nodes).Loops(source)[0].Ready,"incompatible edge peer faults the circuit");last.Model=saved;
            var crowd=new ThermalEndpoint{Id=99,GridId=1,Healthy=true,Model=model,Ports=last.Ports};nodes.Add(crowd);
            Check(!new ThermalNetwork(nodes).Loops(source)[0].Ready,"crowded edge is never automatically capped");nodes.Remove(crowd);
            var other=new ThermalEndpoint{Id=98,GridId=1,Healthy=true,Model=source.Model,Ports=new[]{reverse(last.Ports[0])}};nodes.Add(other);
            Check(!new ThermalNetwork(nodes).Loops(source)[0].Ready,"two reactors cannot share a radiator array");nodes.Remove(other);
            last.GridId=2;circuit=new ThermalNetwork(nodes).Loops(source)[0];
            Check(circuit.Ready && !circuit.Nodes.Contains(last),"grid split self-seals the array and excludes detached cooling");last.GridId=1;
            nodes.Remove(centre);
            Check(!new ThermalNetwork(nodes).Loops(source)[0].Ready,"removing the rear-fed radiator still exposes the ordinary feed pipe");
            nodes.Add(centre);
            var cache=new ThermalCircuitCache(nodes);centre.Ports[0].SelfSealing=false;
            Check(!cache.Matches(nodes),"cache includes self-sealing socket behavior");centre.Ports[0].SelfSealing=true;
        }
        Check(ThermalModels.HullRadiatorSamples.Length==32,"front exposure samples cover the existing tile face");
        foreach(var sample in ThermalModels.HullRadiatorSamples)
            Check(sample.Z < -1.25 && Math.Abs(sample.X)<3 && Math.Abs(sample.Y)<2,"samples lie outside only the radiating front face");
    }

    public static void Main(string[] args)
    {
        PipeRotors(); HullRadiators();
        Isolation(); Registrations(); Budgets(); Stores(); CoolingFailure(); ModesAndStartup(); Topology(); UniversalPipes(); ReactorAdapters(); BarePipes(); Rotors(); Radiators(); LoopEnergy(); Construction(); ThermalForecasts(); CooldownForecasts(); MeltdownCountdown(); Flow(args.Length > 0 ? args[0] : null);
        Console.WriteLine("Thermal runtime: " + checks + " checks passed (registrations/channels, budget, conservation, reload, modes, 47 manifold poses, linear load rotors, construction/orientation guide and authored topology)");
    }
}
