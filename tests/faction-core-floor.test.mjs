import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import vm from "node:vm";

const root = new URL("../ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/", import.meta.url);
const read = path => readFile(new URL(path, root), "utf8");
const [models, manager, api, provider, app] = await Promise.all([
  read("Config/ModConfig.XmlModels.cs"),
  read("Server/Managers/PerFactionManager.cs"),
  read("API/ApiData.cs"),
  read("API/ModAPI.cs"),
  readFile(new URL("../docs/scf-configurator/app.js", import.meta.url), "utf8"),
]);
const section = (source, start, end) => {
  const first = source.indexOf(start);
  const last = source.indexOf(end, first);
  assert.ok(first >= 0 && last > first, `Missing production section: ${start}`);
  return source.slice(first, last);
};

assert.match(api, /\[ProtoMember\(43\)\] public int MinPerFaction;/);
assert.match(provider, /MinPerFaction = core\.MinPerFaction/);

// Execute the actual configuration fields, allowance helpers, and enforcement method.
const production = `
using System;
using System.IO;
using System.Xml.Serialization;
public enum FactionRank { None }
public class ShipCore {
  ${section(models, '[XmlElement("MaxPerFaction")]', "[XmlIgnore]")}
}
public class IMyFaction { public long FactionId = 1; public int Players = 2; }
static class Session { public static bool CoreCountLimitsEnabled = true; }
static class Utils {
  public static void Log(string text, int level) {}
  public static void ShowChatMessage(string text, long playerEntityId) {}
}
static class Config {
  public static ShipCore Core;
  public static bool IsValidCoreType(string type) { return true; }
  public static ShipCore GetShipCoreByTypeId(string type) { return Core; }
}
static class PerFactionManager {
  public static int Count;
  static int GetCurrentCount(long id, string type) { return Count; }
  static int GetFactionPlayerCount(IMyFaction faction, long owner) { return faction == null ? 0 : faction.Players; }
  static int GetFactionMemberCount(IMyFaction faction) { return faction == null ? 0 : faction.Players; }
  ${section(manager, "internal static bool HasFactionCoreLimit(", "internal static int GetCurrentCount(")}
}
static class Checks {
  static void Equal(int actual, int expected) {
    if (actual != expected) throw new Exception("Expected " + expected + ", got " + actual);
  }
  static void Allowed(bool expected, IMyFaction faction) {
    if (PerFactionManager.IsGroupWithinFactionLimits(faction, 1, "Core", false) != expected)
      throw new Exception("Unexpected placement permission");
  }
  static ShipCore Parse(string fields) {
    return (ShipCore)new XmlSerializer(typeof(ShipCore)).Deserialize(new StringReader("<ShipCore>" + fields + "</ShipCore>"));
  }
  public static void Main() {
    var core = Parse("<FactionPlayersNeededPerCore>3</FactionPlayersNeededPerCore>");
    Equal(core.MinPerFaction, 0);
    Equal(PerFactionManager.GetEffectiveFactionCoreLimit(core, 2), 0);
    core.MinPerFaction = 1;
    for (int players = 0; players <= 12; players++)
      Equal(PerFactionManager.GetEffectiveFactionCoreLimit(core, players), players < 6 ? 1 : players / 3);
    core.MaxPerFaction = 2;
    Equal(PerFactionManager.GetEffectiveFactionCoreLimit(core, 12), 2);
    core.MinPerFaction = 5;
    Equal(PerFactionManager.GetEffectiveFactionCoreLimit(core, 2), 2);
    core.MaxPerFaction = 0;
    Equal(PerFactionManager.GetEffectiveFactionCoreLimit(core, 2), 0);
    core.FactionPlayersNeededPerCore = -1;
    core.MaxPerFaction = -1;
    Equal(PerFactionManager.GetEffectiveFactionCoreLimit(core, 2), -1);
    core.FactionPlayersNeededPerCore = 0;
    Equal(PerFactionManager.GetEffectiveFactionCoreLimit(core, 2), -1);
    core.FactionPlayersNeededPerCore = 3;
    core.MinPerFaction = -1;
    Equal(PerFactionManager.GetEffectiveFactionCoreLimit(core, 2), 0);
    Equal(PerFactionManager.GetEffectiveFactionCoreLimit(core, -1), 0);
    Equal(PerFactionManager.GetEffectiveFactionCoreLimit(null, 2), -1);
    Session.CoreCountLimitsEnabled = false;
    core.MinPerFaction = 1;
    Equal(PerFactionManager.GetEffectiveFactionCoreLimit(core, 2), -1);
    Session.CoreCountLimitsEnabled = true;
    Config.Core = core;
    var faction = new IMyFaction();
    PerFactionManager.Count = 1;
    faction.Players = 1;
    Allowed(true, faction);
    faction.Players = 2;
    Allowed(true, faction);
    Allowed(false, null);
    PerFactionManager.Count = 2;
    Allowed(false, faction);
    faction.Players = 6;
    Allowed(true, faction);
    core.MinPlayers = 7;
    Allowed(false, faction);
    core.MinPlayers = -1;
    core.MaxPlayers = 5;
    Allowed(false, faction);
    var writer = new StringWriter();
    new XmlSerializer(typeof(ShipCore)).Serialize(writer, core);
    Equal(((ShipCore)new XmlSerializer(typeof(ShipCore)).Deserialize(new StringReader(writer.ToString()))).MinPerFaction, 1);
    Console.WriteLine("Faction floor, hard caps, placement gates, and XML compatibility checks passed.");
  }
}
`;
const work = await mkdtemp(join(tmpdir(), "scf-faction-floor-"));
try {
  const path = join(work, "Checks.cs");
  const executable = join(work, "checks.exe");
  await writeFile(path, production);
  execFileSync("mcs", ["-langversion:6", `-out:${executable}`, path], { stdio: "pipe" });
  process.stdout.write(execFileSync("mono", [executable], { encoding: "utf8" }));
} finally {
  await rm(work, { recursive: true, force: true });
}

// Cloning is also the saved-draft restoration path. Preserve the old MinPlayers alias.
const context = vm.createContext({});
vm.runInContext(app.slice(0, app.indexOf('document.addEventListener("click"'))
  .replace(/^import[\s\S]*?from "[^"]+";\n/gm, ""), context);
const evaluate = code => vm.runInContext(code, context);
assert.equal(evaluate("createDefaultCore().minPerFaction"), 0);
assert.equal(evaluate("cloneShipCore({ minPerFaction: 3 }).minPlayers"), 3);
assert.equal(evaluate("cloneShipCore({ minPerFaction: 3 }).minPerFaction"), 0);
assert.equal(evaluate("cloneShipCore({ minPlayers: 7, minPerFaction: 1 }).minPlayers"), 7);
assert.equal(evaluate("cloneShipCore({ minPlayers: 7, minPerFaction: 1 }).minPerFaction"), 1);
assert.match(app, /minPerFaction: numberOf\(coreNode, "MinPerFaction", 0\)/);
assert.match(app, /minPlayers: numberOf\(coreNode, "MinPlayers", -1\)/);
for (const core of ["core", "state.noCoreCore"]) {
  assert.ok(app.includes(`<MinPerFaction>\${${core}.minPerFaction}</MinPerFaction>`));
  assert.ok(app.includes(`<MinPlayers>\${${core}.minPlayers}</MinPlayers>`));
}
console.log("Faction floor editor defaults, draft migration, and XML wiring checks passed.");
