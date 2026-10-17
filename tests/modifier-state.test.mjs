import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const root = new URL("../ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/", import.meta.url);
const read = path => readFile(new URL(path, root), "utf8");
const [models, abilities, shared, grid, cleanup, limits, events, cache] = await Promise.all([
  read("Config/ModConfig.XmlModels.cs"),
  read("Server/Components/GroupComponent.Abilities.cs"),
  read("Shared/Components/GroupComponent.Abilities.cs"),
  read("Shared/Components/GridComponent.cs"),
  read("Shared/Components/GridComponent.Cleanup.cs"),
  read("Server/Components/GroupComponent.Limits.cs"),
  read("Session/Server/Session.FactionEvents.cs"),
  read("Server/Components/GroupComponent.CachedState.cs"),
]);
const section = (source, start, end) => {
  const first = source.indexOf(start);
  const last = source.indexOf(end, first);
  assert.ok(first >= 0 && last > first, `Missing production section: ${start}`);
  return source.slice(first, last);
};

// Subscription lifetime and notification wiring complement the executed production checks below.
for (const event of ["OnBlockOwnershipChanged", "OnStaticChanged"]) {
  assert.ok(grid.includes(`${event} +=`));
  assert.ok(cleanup.includes(`${event} -=`));
}
for (const [start, end] of [
  ["internal void OnBlockAddedToGroup(", "internal void OnBlockRemovedFromGroup("],
  ["internal void OnBlockRemovedFromGroup(", "internal void OnBlockPcuChanged("],
  ["internal void OnBlockPcuChanged(", "internal void RunLimitedBlockPunishmentTick("],
]) assert.ok(section(limits, start, end).includes("QueuePunishmentStateRefresh()"));
assert.ok(section(events, "private static void FactionEdited(", "private static void SessionReady(")
  .includes("EnforceOverCapacityForGroups"));

const production = `
using System;
using System.Collections.Generic;
using System.Xml.Serialization;
using Sandbox.ModAPI;
namespace ShipCoreFramework {
  ${section(models, "public class GridModifiers", '[XmlRoot("BlockLimit")]')}
  ${section(models, "public class GridDefenseModifiers", '[XmlRoot("MobilityType")]')}
  internal partial class GroupComponent {
    ${section(cache, "internal void RefreshGameThreadStateCache()", "internal void OnNoCoreDirectionReferencePropertiesChanged()")}
    ${section(abilities, "private GridDefenseModifiers GetCurrentDefenseModifiers()", "private bool HasWorkingBeacon()")}
    ${section(shared, "internal GridDefenseModifiers GetActiveDefenseModifiers()", "\n    }\n}")}
  }
}
`;
const work = await mkdtemp(join(tmpdir(), "scf-modifier-state-"));
try {
  const path = join(work, "Production.cs");
  const executable = join(work, "checks.exe");
  await writeFile(path, production);
  execFileSync("mcs", ["-langversion:6", `-out:${executable}`, path,
    fileURLToPath(new URL("Shared/Modifiers/CubeGridModifiers.State.cs", root)),
    fileURLToPath(new URL("Shared/Components/GridComponent.Modifiers.cs", root)),
    fileURLToPath(new URL("Server/Components/GroupComponent.RuleChanges.cs", root)),
    fileURLToPath(new URL("modifier-state.cs", import.meta.url)),
  ], { stdio: "pipe" });
  process.stdout.write(execFileSync("mono", [executable], { encoding: "utf8" }));
} finally {
  await rm(work, { recursive: true, force: true });
}
