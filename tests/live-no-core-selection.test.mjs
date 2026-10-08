// Executes production activation, selection and persistence code with game API stubs.
// Requires mcs and mono, like npc-detection.test.mjs.
import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";

const root = new URL("../ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/", import.meta.url);
const paths = ["Session/Session.Run.cs", "Session/Server/Session.ServerLifecycle.cs",
  "Session/Server/Session.FactionEvents.cs", "Session/Server/Session.ServerFields.cs",
  "Server/Commands/Commands.Administration.cs", "Config/ModConfig.Loading.cs",
  "Config/Server/ModConfig.Persistence.cs", "Session/Server/Session.ServerServices.cs",
  "Server/Commands/Commands.Dispatch.cs"];
const [run, lifecycle, factions, fields, commands, loading, persistence, services, dispatch] =
  await Promise.all(paths.map(path => readFile(new URL(path, root), "utf8")));
function method(source, name) {
  const match = source.match(new RegExp(`        (?:public|private|internal)[^\\n]+ ${name}\\([^\\n]*\\)\\n        \\{[\\s\\S]*?\\n        \\}`));
  assert.ok(match, `Production method ${name} must exist`);
  return match[0];
}
assert.match(dispatch, /!Session\.IsGameThread[\s\S]*InvokeOnGameThread\(\(\) => ServerCommandSwitch/);
assert.match(dispatch, /case "select":[\s\S]*CheckIfAdmin\(playerId\)[\s\S]*Select\(args\)/);

const directory = await mkdtemp(join(tmpdir(), "scf-live-selection-"));
try {
  const program = join(directory, "Checks.cs");
  await writeFile(program, `
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading;
enum GridLinkTypeEnum { Mechanical, Physical }
class IMyGridGroupData { public GridLinkTypeEnum LinkType; }
class GridGroupsApi {
    public event Action<IMyGridGroupData> OnGridGroupCreated, OnGridGroupDestroyed;
    public int Subscriptions { get { return OnGridGroupCreated.GetInvocationList().Length; } }
    public int Enumerations;
    public void GetGridGroups(GridLinkTypeEnum type, List<IMyGridGroupData> groups) {
        Enumerations++; groups.Add(new IMyGridGroupData { LinkType = type });
    }
}
class FactionsApi {
    public event Action FactionStateChanged, FactionCreated, FactionEdited;
    public int Subscriptions { get { return FactionCreated == null ? 0 : FactionCreated.GetInvocationList().Length; } }
}
class DamageApi { public int Registrations; public void RegisterBeforeDamageHandler(int priority, Action handler) { Registrations++; } }
class WorldApi {
    public event Action OnSessionReady;
    public FactionsApi Factions = new FactionsApi();
    public DamageApi DamageSystem = new DamageApi();
    public void Ready() { if (OnSessionReady != null) OnSessionReady(); }
}
class MultiplayerApi {
    public void RegisterSecureMessageHandler(ushort id, Action handler) {}
    public void UnregisterSecureMessageHandler(ushort id, Action handler) {}
}
class UtilitiesApi {
    public bool FailSave;
    public string Saved;
    public int Writes;
    public TextWriter WriteFileInWorldStorage(string name, Type type) {
        if (FailSave) throw new IOException("disk full");
        return new StoreWriter(this);
    }
    public string SerializeToXML(ModConfig config) { return config.SelectedNoCoreUniqueName; }
    class StoreWriter : StringWriter {
        UtilitiesApi owner;
        public StoreWriter(UtilitiesApi owner) { this.owner = owner; }
        public override void Close() { owner.Saved = ToString(); owner.Writes++; base.Close(); }
    }
}
class ParallelApi { public void ForEach<T>(IEnumerable<T> values, Action<T> action) { foreach (var value in values) action(value); } }
class PacketRequestConfig {}
class Networking { public void SendToServer(PacketRequestConfig packet, bool onlyToServer) {} }
static class MyAPIGateway {
    public static WorldApi Session;
    public static GridGroupsApi GridGroups;
    public static MultiplayerApi Multiplayer = new MultiplayerApi();
    public static UtilitiesApi Utilities;
    public static ParallelApi Parallel = new ParallelApi();
}
static class MyExplosions { public static event Action OnExplosion; public static int Subscriptions { get { return OnExplosion == null ? 0 : OnExplosion.GetInvocationList().Length; } } }
static class CubeGridModifiers { public static void HandleLightningExplosions() {} public static void GridCoreDamageHandler() {} }
static class Utils { public static void Log(string text, int priority = 0, string category = "") {} }
class NexusAPI {
    public static NexusAPI Current;
    public bool Enabled;
    Action callback;
    public NexusAPI(Action callback) { Current = this; this.callback = callback; }
    public void Enable() { Enabled = true; callback(); }
    public void Unload() { Enabled = false; }
}
static class LimitsNexusSync { public static int Starts; public static void Start(NexusAPI api) { Starts++; } public static void BroadcastSnapshot() {} public static void Stop() {} }
static class PerFactionManager { public static int Initializations; public static void InitializeIdentityCache() { Initializations++; } public static void Reset() {} }
static class PerPlayerManager { public static void Reset() {} }
static class PerManifestGroupManager { public static void Reset() {} }
static class ModAPI {
    public static bool ConfigReady, SnapshotReady;
    public static void Initialize() {}
    public static void MarkConfigReady(bool pending = false) { ConfigReady = true; if (pending) SnapshotReady = false; }
    public static void MarkRuntimeSnapshotReady() { SnapshotReady = true; }
    public static void MarkConfigUnavailable(string error) { ConfigReady = SnapshotReady = false; }
}
class ShipCore { public string UniqueName, SubtypeId; }
class ModConfig {
    ${loading.match(/private const string RetiredDefaultNoCoreUniqueName = "[^"]+";/)[0]}
    const string GlobalConfigFileName = "world.xml";
    public static ModConfig NextConfig;
    public string SelectedNoCoreUniqueName;
    public ShipCore SelectedNoCore;
    public List<ShipCore> NoCoreConfigs = new List<ShipCore>();
    public void LoadConfig() { NoCoreConfigs.AddRange(NextConfig.NoCoreConfigs); SelectedNoCoreUniqueName = NextConfig.SelectedNoCoreUniqueName; ResolveSelectedNoCore(); }
    void NormalizeAndResolveSelectedNoCore() {}
    void EnsurePersistedWorldSettings() {}
    void RemoveLegacySandboxSettings(bool show) {}
${method(loading, "ResolveSelectedNoCore")}
${method(loading, "GetNoCoreConfigurationError")}
${method(persistence, "SaveConfig")}
}
class SessionBase { public virtual void BeforeStart() {} }
class Session : SessionBase {
    public static bool IsServer = true, MpActive = true, IsInitialGroupScan;
    public static ModConfig Config;
    public static Networking Networking = new Networking();
    const ushort CommandsSyncId = 1;
    static bool _runtimeInitialized;
    public static bool RuntimeInitialized { get { return _runtimeInitialized; } }
    public static int Scans, Refreshes, Broadcasts, Definitions;
    public static List<GridLinkTypeEnum> ScanOrder = new List<GridLinkTypeEnum>();
${fields.split("\n").filter(line => /private (static )?bool |private int _serverSimulationBatchRunning|private static NexusAPI |internal static bool HasStarted/.test(line)).join("\n")}
    public void Load() { LoadServerData(); }
    public void Unload() { UnloadServerData(); _runtimeInitialized = false; }
    static void ApplyConfigToDefinitions() { Definitions++; }
    static void RefreshGroupsAfterConfigChanged() { Refreshes++; }
    public static void BroadcastConfigToClients() { if (!RuntimeInitialized || !ModAPI.SnapshotReady) throw new Exception("Premature broadcast"); Broadcasts++; }
    static void GridGroupsOnOnGridGroupCreated(IMyGridGroupData group) { Scans++; ScanOrder.Add(group.LinkType); }
    static void GridGroupsOnOnGridGroupDestroyed(IMyGridGroupData group) {}
    static void FactionStateChanged() {} static void FactionCreated() {} static void FactionEdited() {}
    static void UntrackAllPhysicalGridGroups() {} static void ResetRuntimeStateSync() {}
${method(run, "BeforeStart")}
${method(run, "TryInitializeRuntime")}
${["LoadServerData", "InitializeServerRuntimeData", "ApplyServerConfig", "UnloadServerData", "AppendInitialPhysicalGroups"].map(name => method(lifecycle, name)).join("\n")}
${method(factions, "SessionReady")}
${method(factions, "InitializeServerReadyData")}
${method(services, "OnNexusEnabled")}
}
static class Commands {
    public static void ServerMessageHandler() {}
    public static string Choose(string name) { return Select(new[] { "select", name }); }
    public static string Reload() { return ReloadConfig(); }
${method(commands, "Select")}
${method(commands, "ReloadConfig")}
}
class Checks {
    static void Check(bool value, string message) { if (!value) throw new Exception(message); }
    static ModConfig Profiles(string selected = null) {
        var config = new ModConfig { SelectedNoCoreUniqueName = selected };
        config.NoCoreConfigs.Add(new ShipCore { UniqueName = "First", SubtypeId = "FirstSubtype" });
        config.NoCoreConfigs.Add(new ShipCore { UniqueName = "Second", SubtypeId = "SecondSubtype" });
        config.ResolveSelectedNoCore(false); return config;
    }
    static Session Start(string selected = null) {
        MyAPIGateway.Session = new WorldApi(); MyAPIGateway.GridGroups = new GridGroupsApi(); MyAPIGateway.Utilities = new UtilitiesApi();
        ModAPI.ConfigReady = ModAPI.SnapshotReady = false;
        Session.Config = Profiles(selected); Session.Scans = Session.Refreshes = Session.Broadcasts = Session.Definitions = 0; Session.ScanOrder.Clear();
        var session = new Session(); session.Load(); return session;
    }
    static void Main() {
        var session = Start(); session.BeforeStart(); MyAPIGateway.Session.Ready(); NexusAPI.Current.Enable();
        Check(!Session.RuntimeInitialized && Session.Scans == 0 && MyAPIGateway.Session.DamageSystem.Registrations == 0, "Unconfigured runtime must stay stopped");
        var reply = Commands.Choose("FirstSubtype");
        Check(reply.Contains("Selection saved") && MyAPIGateway.Utilities.Saved == "First", "Selection must persist without a world save");
        Check(Session.RuntimeInitialized && ModAPI.ConfigReady && ModAPI.SnapshotReady, "Late activation must restore API readiness");
        Check(Session.Scans == 2 && Session.ScanOrder.SequenceEqual(new[] { GridLinkTypeEnum.Mechanical, GridLinkTypeEnum.Physical }), "Must scan mechanical groups before physical clusters");
        Check(MyAPIGateway.Session.DamageSystem.Registrations == 1 && MyExplosions.Subscriptions == 1 && PerFactionManager.Initializations == 1 && LimitsNexusSync.Starts == 1, "Late activation must recover server-ready services and Nexus handshake");
        Check(Session.Broadcasts == 1, "Clients must receive the initialized configuration once");
        Commands.Choose("Second"); Commands.Choose("Second"); MyAPIGateway.Session.Ready();
        Check(MyAPIGateway.Utilities.Saved == "Second" && Session.Refreshes == 2 && Session.Scans == 2, "Live changes must refresh tracked groups");
        Check(MyAPIGateway.GridGroups.Subscriptions == 1 && MyAPIGateway.Session.Factions.Subscriptions == 1 && MyAPIGateway.Session.DamageSystem.Registrations == 1 && MyExplosions.Subscriptions == 1, "Repeated selection must not duplicate handlers or scans");
        int writes = MyAPIGateway.Utilities.Writes;
        Commands.Choose("Missing"); Check(MyAPIGateway.Utilities.Writes == writes && Session.Config.SelectedNoCoreUniqueName == "Second", "Unknown selection must not change config");
        MyAPIGateway.Utilities.FailSave = true;
        Check(Commands.Choose("First").Contains("could not be saved") && Session.Config.SelectedNoCoreUniqueName == "First", "Save failure must be reported while applying live selection");
        MyAPIGateway.Utilities.FailSave = false;
        ModConfig.NextConfig = Profiles("Missing"); var active = Session.Config;
        Check(Commands.Reload().Contains("rejected") && Session.Config == active, "Invalid reload must preserve running configuration");
        session.Unload(); Check(MyAPIGateway.Session.Factions.Subscriptions == 0 && MyExplosions.Subscriptions == 0, "Unload must remove handlers");

        session = Start(); session.BeforeStart(); MyAPIGateway.Session.Ready();
        ModConfig.NextConfig = Profiles("Second");
        Check(!Commands.Reload().Contains("rejected") && Session.RuntimeInitialized && Session.Scans == 2 && MyAPIGateway.Session.DamageSystem.Registrations == 1, "Reload must also activate an unconfigured world");
        session.Unload();

        session = Start("First"); session.BeforeStart();
        Check(Session.Scans == 2 && MyAPIGateway.Session.DamageSystem.Registrations == 0, "Normal startup must wait for session-ready services");
        MyAPIGateway.Session.Ready(); MyAPIGateway.Session.Ready();
        Check(MyAPIGateway.Session.DamageSystem.Registrations == 1 && MyExplosions.Subscriptions == 1, "Normal startup services must remain idempotent");
        session.Unload();
        Console.WriteLine("Live no-core activation, grid enumeration, persistence and lifecycle checks passed.");
    }
}
`);
  const executable = join(directory, "Checks.exe");
  execFileSync("mcs", ["-langversion:6", `-out:${executable}`, program], { stdio: "pipe" });
  process.stdout.write(execFileSync("mono", [executable], { encoding: "utf8" }));
} finally {
  await rm(directory, { recursive: true, force: true });
}
