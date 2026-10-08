import assert from "node:assert/strict";
import { access, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";

const root = new URL(
  "../ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/",
  import.meta.url,
);
const read = path => readFile(new URL(path, root), "utf8");

const [config, loading, sessionRun, serverLifecycle, clientConfig, persistence, commands] =
  await Promise.all([
    read("Config/ModConfig.cs"),
    read("Config/ModConfig.Loading.cs"),
    read("Session/Session.Run.cs"),
    read("Session/Server/Session.ServerLifecycle.cs"),
    read("Client/Network/PresentationPacketHandlers.cs"),
    read("Config/Server/ModConfig.Persistence.cs"),
    read("Server/Commands/Commands.Administration.cs"),
  ]);

await assert.rejects(access(new URL("Config/DefaultNoCoreConfig.cs", root)));
assert.doesNotMatch(config, /DefaultNoCoreConfig|_defaultNoCore/);
assert.doesNotMatch(loading, /Falling back to default|_defaultNoCore/);
assert.match(loading, /internal bool ResolveSelectedNoCore\(bool logFailure = true\)/);
assert.match(loading, /RetiredDefaultNoCoreUniqueName = "DEFAULT-NO-CORE-ALL-GRID-TYPES"/);
assert.match(loading, /NoCoreConfigs\.Count == 1[\s\S]*SelectedNoCore = NoCoreConfigs\[0\]/);
assert.match(loading, /The retired built-in no-core profile is still selected/);
assert.match(loading, /No content-pack no-core profile is selected/);
assert.match(sessionRun, /if \(_runtimeInitialized \|\| Config\?\.SelectedNoCore == null\) return false/);
assert.doesNotMatch(sessionRun, /NotifyMissingNoCore/);
assert.match(serverLifecycle, /RegisterSecureMessageHandler[\s\S]*InitializeServerRuntimeData\(\)/);
assert.match(serverLifecycle, /_serverRuntimeDataLoaded \|\| Config\?\.SelectedNoCore == null/);
assert.match(clientConfig, /ResolveSelectedNoCore\(\)[\s\S]*TryInitializeRuntime\(\)/);
assert.match(persistence, /bool broadcast = true/);
assert.match(commands, /Session\.ApplyServerConfig\(\)/);
assert.doesNotMatch(commands, /Reload the world to start Ship Core Framework|Please save the world and reload/);
assert.match(commands, /if \(loadedConfig\.SelectedNoCore == null\)[\s\S]*Config reload rejected/);

// Execute the production resolver with game-independent stubs (requires mcs/mono).
const resolver = loading.match(/        internal bool ResolveSelectedNoCore\(bool logFailure = true\)\n        \{[\s\S]*?\n        \}/)?.[0];
assert.ok(resolver, "Production no-core resolver must exist");
const directory = await mkdtemp(join(tmpdir(), "scf-no-core-selection-"));
try {
  const program = join(directory, "Checks.cs");
  await writeFile(program, `
using System;
using System.Collections.Generic;
using System.Linq;
class ShipCore { public string UniqueName; }
static class Session { public static bool IsServer; }
static class Utils { public static void Log(string text, int priority, string category) {} }
class ModConfig {
    ${loading.match(/private const string RetiredDefaultNoCoreUniqueName = "[^"]+";/)[0]}
    public string SelectedNoCoreUniqueName;
    public ShipCore SelectedNoCore;
    public List<ShipCore> NoCoreConfigs = new List<ShipCore>();
    public bool Normalized;
    void NormalizeAndResolveSelectedNoCore() { Normalized = true; }
    string GetNoCoreConfigurationError() { return "No selection"; }
${resolver}
}
class Checks {
    static void Check(string selection, bool server, string[] names, string expected) {
        Session.IsServer = server;
        var config = new ModConfig { SelectedNoCoreUniqueName = selection };
        foreach (var name in names) config.NoCoreConfigs.Add(new ShipCore { UniqueName = name });
        if (config.ResolveSelectedNoCore(false) != (expected != null) ||
            config.SelectedNoCore?.UniqueName != expected || config.Normalized != (expected != null))
            throw new Exception("Incorrect resolution: " + selection + ", server=" + server + ", profiles=" + names.Length);
        if (config.SelectedNoCoreUniqueName != (expected ?? selection))
            throw new Exception("Selection must be retained for persistence");
    }
    static void Main() {
        foreach (var empty in new string[] { null, "", " \\t" }) {
            Check(empty, true, new[] { "Only" }, "Only");
            Check(empty, true, new string[0], null);
            Check(empty, true, new[] { "First", "Second" }, null);
            Check(empty, false, new[] { "Only" }, null);
        }
        Check("Missing", true, new[] { "Only" }, null);
        Check("", true, new[] { " " }, null);
        Check("oNlY", true, new[] { "Only" }, "Only");
        Check("Second", true, new[] { "First", "Second" }, "Second");
        Check("Only", false, new[] { "Only" }, "Only");
        Check("DEFAULT-NO-CORE-ALL-GRID-TYPES", true, new[] { "Only" }, "Only");
        Check("DEFAULT-NO-CORE-ALL-GRID-TYPES", true, new[] { "First", "Second" }, null);
        Console.WriteLine("No-core selection behavior checks passed.");
    }
}
`);
  const executable = join(directory, "Checks.exe");
  execFileSync("mcs", ["-langversion:6", `-out:${executable}`, program], { stdio: "pipe" });
  process.stdout.write(execFileSync("mono", [executable], { encoding: "utf8" }));
} finally {
  await rm(directory, { recursive: true, force: true });
}

console.log("Content-pack no-core requirement checks passed.");
