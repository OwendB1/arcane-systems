import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const root = new URL("../", import.meta.url);
const read = path => readFile(new URL(path, root), "utf8");

const [models, validation, groupLimits, gridLimits, evaluation, api, configurator, readme] =
  await Promise.all([
    read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Config/ModConfig.XmlModels.cs"),
    read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Config/ModConfig.Validation.cs"),
    read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Server/Components/GroupComponent.Limits.cs"),
    read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Server/Components/GridComponent.Limits.cs"),
    read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Shared/Limits/LimitEvaluation.cs"),
    read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/API/ApiData.cs"),
    read("docs/scf-configurator/app.js"),
    read("docs/ship-core-framework.md"),
  ]);

assert.match(models, /XmlElement\("BlockGroups"\)[\s\S]*BlockGroupReference\[\]/);
assert.match(models, /XmlText[\s\S]*string Name/);
assert.match(models, /XmlAttribute\("Directions"\)/);
assert.match(
  models,
  /HasDirectionsOverride[\s\S]*string\.Equals\(reference\.Name, matchedGroup\.Name[\s\S]*return reference\.AllowedDirections;[\s\S]*return AllowedDirections;/,
);

assert.match(validation, /directions\.Split\(','\)/);
assert.match(validation, /Enum\.TryParse\(token, true, out direction\)/);
assert.match(validation, /Enum\.IsDefined\(typeof\(DirectionType\), direction\)/);
assert.match(validation, /BlockGroupsShortHand = normalizedReferences\.Select/);

assert.match(groupLimits, /limit\.GetAllowedDirections\(blockKey\)/);
assert.match(gridLimits, /limit\.GetAllowedDirections\(blockKey\)/);
assert.match(evaluation, /allowedDirections = limit\.GetAllowedDirections\(block\.Key\)/);
assert.match(groupLimits, /allowedDirections\.Contains\(DirectionType\.Any\)/);
assert.match(api, /Any = 6/);

assert.match(configurator, /hasAttribute\("Directions"\)/);
assert.match(configurator, /<BlockGroups\$\{attribute\}>/);
assert.match(configurator, /data-action="limit-group-directions"/);
assert.match(readme, /Directions="0,1"/);
assert.match(readme, /overrides this limit's `AllowedDirections`/);

console.log("Block-group direction override contract checks passed.");
