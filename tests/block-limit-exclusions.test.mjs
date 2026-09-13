import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const root = new URL("../", import.meta.url);
const read = async path => readFile(new URL(path, root), "utf8");

const [models, loading, validation, noFly, configurator, readme] = await Promise.all([
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Config/ModConfig.XmlModels.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Config/ModConfig.Loading.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Config/ModConfig.Validation.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Server/Enforcement/NoFlyZoneEnforcement.cs"),
  read("docs/scf-configurator/app.js"),
  read("docs/ship-core-framework.md"),
]);

assert.match(models, /XmlElement\("ExcludedBlockGroups"\)/);
assert.match(models, /ExcludedBlockGroupsShortHand/);
assert.match(
  models,
  /FindMatchingBlockType\(ExcludedBlockGroups, key\) != null\)[\s\S]*return null;[\s\S]*FindMatchingBlockType\(BlockGroups, key\)/,
);

assert.match(loading, /ResolveBlockGroupReferences[\s\S]*ExcludedBlockGroupsShortHand/);
assert.match(validation, /includes and excludes BlockGroup\(s\)[\s\S]*exclusion wins/);

assert.match(noFly, /limit\.GetMatchingBlockType\(blockKey\) != null/);
assert.doesNotMatch(noFly, /SelectMany\(g => g\.BlockTypes\)/);

assert.match(configurator, /excludedBlockGroups/);
assert.match(configurator, /qselAll\(limitNode, "ExcludedBlockGroups"\)/);
assert.match(configurator, /<ExcludedBlockGroups>/);
assert.match(configurator, /limit-excluded-group-toggle/);

assert.match(readme, /\| `ExcludedBlockGroups` \|/);
assert.match(readme, /Exclusion wins/);

console.log("Block-limit exclusion contract checks passed.");
