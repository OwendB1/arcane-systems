import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const components = join(root, "ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Server/Components");
const limits = await readFile(join(components, "GroupComponent.Limits.cs"), "utf8");
const connectors = await readFile(join(components, "GroupComponent.Connectors.cs"), "utf8");

// Compile the production selection, execution, and restoration code with small game API stubs.
// This exercises Enabled writes, including transient re-enables during repeated checks.
const section = (start, end) => {
  const first = limits.indexOf(start);
  const last = limits.indexOf(end, first);
  assert.ok(first >= 0 && last > first, `Missing production section: ${start}`);
  return limits.slice(first, last);
};
const production = `
using System;
using System.Collections.Generic;
using Sandbox.ModAPI;
using VRage.Game.ModAPI;
using VRageMath;
namespace ShipCoreFramework { internal partial class GroupComponent {
${section("private sealed class PendingBlockPunishment", "private sealed class GridLimitSnapshot")}
${section("internal void EnforceConnectorLimitPunishment()", "internal bool DoesBlockViolateAllowedDirection(")}
${section("private void ExecutePendingPunishments(", "private float ComputeEffectiveMaxCount(")}
} }
`;

// Connector events only enqueue recalculation; restoration belongs to the evaluated result.
assert.doesNotMatch(connectors, /RestoreConnectorShutOffBlocks|\.Enabled\s*=\s*true/);

const work = await mkdtemp(join(tmpdir(), "scf-connector-restoration-"));
try {
  const source = join(work, "Enforcement.cs");
  const executable = join(work, "checks.exe");
  await writeFile(source, production);
  execFileSync("mcs", ["-langversion:6", `-out:${executable}`, source,
    join(components, "GroupComponent.ConnectorPunishment.cs"),
    join(root, "tests/connector-punishment-restoration.cs")], { stdio: "pipe" });
  process.stdout.write(execFileSync("mono", [executable], { encoding: "utf8" }));
} finally {
  await rm(work, { recursive: true, force: true });
}
