import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const root = new URL("../", import.meta.url);
const read = path => readFile(new URL(path, root), "utf8");

const [models, validation, bucket, gridLimits, gridBlocks, groupLimits, merge, evaluation, runtime,
  snapshot, replica, preview, statusHud, apiData, api, configurator, editorValidation, readme] = await Promise.all([
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Config/ModConfig.XmlModels.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Config/ModConfig.Validation.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Shared/Limits/LimitSupport.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Server/Components/GridComponent.Limits.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Server/Components/GridComponent.Blocks.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Server/Components/GroupComponent.Limits.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Server/Components/GroupComponent.MergeInterception.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Shared/Limits/LimitEvaluation.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Shared/Network/RuntimeStateContracts.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Server/Components/GroupComponent.Snapshot.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Client/Components/GroupComponent.Replica.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Client/UI/BuildPreviewHud.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Client/UI/CoreStatusHud.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/API/ApiData.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/API/ModAPI.cs"),
  read("docs/scf-configurator/app.js"),
  read("docs/scf-configurator/validation.js"),
  read("docs/ship-core-framework.md"),
]);

assert.match(models, /XmlElement\("MaxCountPerDirection"\)[\s\S]*= -1f/);
assert.match(
  configurator,
  /function numberOf\(parent, tag, fallback = 0\) \{[\s\S]*if \(!text\) return fallback;[\s\S]*Number\(text\)/,
);
assert.match(validation, /MaxCountPerDirection[\s\S]*no valid direction in <AllowedDirections> or a BlockGroups Directions attribute/);
assert.match(validation, /direction != DirectionType\.Any && Enum\.IsDefined/);
assert.match(models, /enum LimitVisibility[\s\S]*Always = 0[\s\S]*NearLimit = 1[\s\S]*Hidden = 2/);
assert.match(bucket, /double\[\] DirectionWeights = new double\[6\]/);

assert.match(gridLimits, /directionWeight \+ weight > directionMax/);
assert.match(gridLimits, /gridBucket\.DirectionWeights\[directionIndex\] \+= weight/);
assert.match(gridLimits, /groupBucket\.DirectionWeights\[directionIndex\] \+= weight/);
assert.match(gridLimits, /BuildLimitsSnapshot[\s\S]*DirectionWeights\[\(int\)facing\] \+= weight/);
assert.match(gridBlocks, /DirectionWeights\[directionIndex\] -= weight/);
assert.match(gridBlocks, /directionalTotal > directionMax/);
assert.match(groupLimits, /directionOver = directionTotals\[directionIndex\] - directionMax/);
assert.match(groupLimits, /CaptureDirectionReference\(GetDirectionLockReferenceBlock\(\)\)/);
assert.match(merge, /projected [\s\S]* directional limit/);

assert.match(runtime, /ProtoMember\(5\).*DirectionCounts/);
assert.match(snapshot, /Array\.Copy\(bucket\.DirectionWeights, directionCounts/);
assert.match(replica, /Array\.Copy\(runtime\.DirectionCounts, bucket\.DirectionWeights/);

assert.match(evaluation, /current \+ added <= directionMax\) continue;[\s\S]*Kind = LimitCheckKind\.DirectionCount/);
assert.match(evaluation, /NearLimitDisplayFraction = 0\.8d/);
assert.match(evaluation, /LimitVisibility\.Hidden[\s\S]*LimitVisibility\.Always/);
assert.match(preview, /DirectionCount[\s\S]*OVER/);
assert.match(preview, /_results\[i\]\.Pass \|\| !IsDisplayable\(_results\[i\]\)/);
assert.match(statusHud, /ShouldShowOnHud/);
assert.match(statusHud, /bool wroteHeader = false/);

assert.match(apiData, /API_MINOR\s*=\s*5/);
assert.match(apiData, /ProtoMember\(10\).*MaxCountPerDirection/);
assert.match(apiData, /ProtoMember\(11\).*LimitVisibility/);
assert.match(api, /MaxCountPerDirection = limit\.MaxCountPerDirection/);
assert.match(configurator, /data-action="limit-max-direction"/);
assert.match(configurator, /limit\.maxCountPerDirection = Number\(target\.value \|\| -1\)/);
assert.match(configurator, /MaxCountPerDirection requires a valid AllowedDirections value or per-group Directions override/);
assert.match(editorValidation, /text\(directions\)\.split\(","\)\.some\(isValidSpecificDirection\)/);
assert.match(configurator, /const DEFAULT_GRID_MODIFIERS = \{[\s\S]*AssemblerSpeed: -1[\s\S]*ThrusterForce: -1/);
assert.match(configurator, /core-modifier-grid"\) selectedCore\.modifiers\[target\.dataset\.m\] = Number\(target\.value \|\| -1\)/);
assert.match(configurator, /data-action="limit-visibility"/);
assert.match(configurator, /numberOf\(limitNode, "MaxCountPerDirection", -1\)/);
assert.match(configurator, /normalizeLimitVisibility\(textOf\(limitNode, "LimitVisibility"\)\)/);
assert.match(configurator, /<MaxCountPerDirection>/);
assert.match(configurator, /<LimitVisibility>/);
assert.match(configurator, /data-action="bt-primary-direction"/);
assert.match(configurator, /normalizePrimaryDirection\(textOf\(typeNode, "PrimaryDirection"\)\)/);
assert.match(configurator, /<PrimaryDirection>/);
assert.match(readme, /<MaxCountPerDirection>25<\/MaxCountPerDirection>/);
assert.match(readme, /`NearLimit` shows numeric rows at 80% usage/);

console.log("Directional block-limit cap and HUD visibility contract checks passed.");
