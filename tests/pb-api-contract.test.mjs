import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const root = new URL(
  "../ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/",
  import.meta.url,
);
const read = path => readFile(new URL(path, root), "utf8");

const [pbApi, sessionRun, docs] = await Promise.all([
  read("API/PbAPI.cs"),
  read("Session/Session.Run.cs"),
  readFile(new URL("../docs/ship-core-framework.md", import.meta.url), "utf8"),
]);

// PB GetProperty only sees controls added to the block type's factory list, not
// CustomControlGetter injections, so properties must go through AddControl.
assert.match(pbApi, /CreateProperty<T, IMyProgrammableBlock>\(Prefix \+ name\)/);
assert.match(pbApi, /AddControl<IMyProgrammableBlock>\(property\)/);
assert.doesNotMatch(pbApi, /CustomControlGetter/);

// Registration must wait for a PB to exist so vanilla PB controls are created first,
// and must not be gated to clients: PB scripts run on the dedicated server.
assert.match(
  pbApi,
  /\[MyEntityComponentDescriptor\(typeof\(MyObjectBuilder_MyProgrammableBlock\), false\)\]/,
);
assert.match(pbApi, /UpdateOnceBeforeFrame\(\)\s*\{\s*PbAPI\.RegisterOnce\(\);/);
assert.doesNotMatch(pbApi, /LocalPlayer|IsClient/);
assert.match(sessionRun, /PbAPI\.Unload\(\)/);

// Read-only: setters are no-ops.
assert.match(pbApi, /property\.Setter = \(block, value\) => \{ \};/);

// Every registered property is documented with the SCF. prefix.
const names = [...pbApi.matchAll(/(?:Add|AddCollection)\("([A-Za-z]+)"/g)].map(m => m[1]);
assert.ok(names.includes("MaxSpeed"));
for (const name of names)
  assert.match(docs, new RegExp("`SCF\\." + name + "`"), `undocumented PB property SCF.${name}`);

// Ability timers are stored in ticks; the PB API reports seconds.
assert.match(pbApi, /TicksPerSecond = 60f/);

console.log("Programmable block API contract checks passed.");
