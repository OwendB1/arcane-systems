import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { enabledBudgetDirections, validateDirectionBudgets, validateEditorConfig } from "../docs/scf-configurator/validation.js";

const limit = {
  maxCount: 100,
  maxCountPerDirection: 10,
  allowedDirections: ["Forward", "Backward", "Left", "Right"],
  blockGroups: ["Weapons"],
  directionBudgets: [
    { direction: "Forward", maxCount: 60 },
    { direction: "Backward", maxCount: 20 }
  ]
};
assert.deepEqual(validateDirectionBudgets(limit), { errors: [], total: 100 });
assert.match(validateDirectionBudgets({ ...limit, maxCount: 99 }).errors.join(" "), /exceeds MaxCount/);
assert.deepEqual(validateDirectionBudgets({ ...limit, maxCountPerDirection: -1 }), { errors: [], total: 80 });
assert.deepEqual(validateDirectionBudgets({ ...limit, directionBudgets: [] }), { errors: [], total: 40 });
assert.match(validateDirectionBudgets({ ...limit, directionBudgets: [], maxCount: 39 }).errors.join(" "), /exceeds MaxCount/);
assert.deepEqual(validateDirectionBudgets({ ...limit, directionBudgets: [], maxCountPerDirection: -1 }), { errors: [], total: null });
assert.equal(validateDirectionBudgets({ ...limit, allowedDirections: [] }).total, 120);
assert.equal(validateDirectionBudgets({ ...limit, allowedDirections: ["Any", "Forward"] }).total, 120);

// All selected groups share each direction's allocation. A group override replaces its default rule.
const groups = { ...limit, blockGroups: ["Weapons", "Tools"], blockGroupDirections: { Weapons: "0,4", Tools: "Forward,Right" } };
assert.deepEqual(enabledBudgetDirections(groups), ["Forward", "Left", "Right"]);
assert.equal(validateDirectionBudgets(groups).total, 100); // Retained Backward override still counts.
assert.equal(validateDirectionBudgets({ ...groups, blockGroupDirections: { Weapons: "Up", Tools: "Up" } }).total, 90);
assert.equal(validateDirectionBudgets({ ...limit, blockGroupDirections: { Weapons: "" } }).total, 120);
assert.equal(validateDirectionBudgets({ ...limit, blockGroupDirections: { Weapons: "nonsense" } }).total, 100);
assert.equal(validateDirectionBudgets({ ...limit, blockGroupDirections: { Unselected: "Any" } }).total, 100);

for (const maxCount of [-1, NaN, Infinity, 1e100, "", null]) {
  assert.ok(validateDirectionBudgets({ ...limit, maxCount }).errors.length);
  assert.ok(validateDirectionBudgets({ ...limit, directionBudgets: [{ direction: "Forward", maxCount }] }).errors.length);
}
for (const direction of ["Any", "Bogus", "", "0", "forward"]) {
  assert.match(validateDirectionBudgets({ ...limit, directionBudgets: [{ direction, maxCount: 1 }] }).errors.join(" "), /Invalid DirectionBudget/);
}
assert.match(validateDirectionBudgets({ ...limit, directionBudgets: [...limit.directionBudgets, limit.directionBudgets[0]] }).errors.join(" "), /Duplicate/);
for (const maxCountPerDirection of [-2, -0.5, NaN, Infinity])
  assert.ok(validateDirectionBudgets({ ...limit, maxCountPerDirection }).errors.length);
assert.deepEqual(validateDirectionBudgets({
  ...limit, maxCount: 0, maxCountPerDirection: 0, directionBudgets: [{ direction: "Forward", maxCount: 0 }]
}), { errors: [], total: 0 });
assert.deepEqual(validateDirectionBudgets({
  ...limit, maxCount: 1, maxCountPerDirection: 0.1,
  directionBudgets: [{ direction: "Forward", maxCount: 0.4 }, { direction: "Backward", maxCount: 0.4 }]
}), { errors: [], total: 1 });
assert.match(validateDirectionBudgets({ ...limit, maxCount: 99.99 }).errors.join(" "), /exceeds MaxCount/);

const result = validateEditorConfig({ noCoreCore: { blockLimits: [{ ...limit, maxCount: 99 }] } });
assert.ok(result.errors.some((error) => error.includes("exceeds MaxCount")));

const base = "ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/";
for (const path of ["Server/Components/GridComponent.Limits.cs", "Server/Components/GridComponent.Blocks.cs",
  "Server/Components/GroupComponent.Limits.cs", "Server/Components/GroupComponent.MergeInterception.cs",
  "Shared/Limits/LimitEvaluation.cs"]) {
  const source = await readFile(new URL(`../${base}${path}`, import.meta.url), "utf8");
  assert.match(source, /GetMaxCountForDirection\(/, path);
  assert.match(source, /HasDirectionalBudget/, path);
  assert.doesNotMatch(source, /limit\.MaxCountPerDirection/, path);
}
const snapshot = await readFile(new URL(`../${base}Server/Components/GroupComponent.Snapshot.cs`, import.meta.url), "utf8");
assert.match(snapshot, /directionCounts = limit\.HasDirectionalBudget/);
console.log("Direction budget allocation and enforcement integration checks passed.");
