import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const root = new URL("../", import.meta.url);
const read = path => readFile(new URL(path, root), "utf8");

const [models, ownership, sharedCache, serverCache, gridLimits, gridBlocks, groupLimits,
  merge, evaluation, noFlyZone, statusHud, lcd, runtime, snapshot, apiData, api, clientApi, configurator,
  readme, apiUsage] = await Promise.all([
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Config/ModConfig.XmlModels.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Server/Components/GroupComponent.Ownership.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Shared/Components/GroupComponent.CachedState.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Server/Components/GroupComponent.CachedState.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Server/Components/GridComponent.Limits.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Server/Components/GridComponent.Blocks.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Server/Components/GroupComponent.Limits.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Server/Components/GroupComponent.MergeInterception.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Shared/Limits/LimitEvaluation.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Server/Enforcement/NoFlyZoneEnforcement.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Client/UI/CoreStatusHud.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Client/UI/CoreTypeLCDScript.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Shared/Network/RuntimeStateContracts.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Server/Components/GroupComponent.Snapshot.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/API/ApiData.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/API/ModAPI.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/API/Client/ModAPI.ReplicaQueries.cs"),
  read("docs/configurator/app.js"),
  read("README.md"),
  read("ShipCoreFramework/src/API_USAGE.md"),
]);

assert.match(models, /XmlElement\("IgnoredByNpc"\)[\s\S]*public bool IgnoredByNpc;/);

assert.match(ownership, /private bool IsNpcGroup\(\)[\s\S]*return GridDictionary\.Keys\.Any\(grid => grid\.IsNpcGrid\(\)\);/);
assert.doesNotMatch(ownership, /mainGrid\?\.IsNpcSpawnedGrid\s*\?\?/);
assert.match(ownership, /return Session\.Config\.IgnoreAiFactions && IsNpcGroup\(\);/);
assert.match(ownership, /return limit == null \|\| !limit\.IgnoredByNpc \|\| !IsNpcGroupThreadSafe\(\);/);
assert.match(sharedCache, /private bool _cachedIsNpcGroup;/);
assert.match(sharedCache, /internal bool GetCachedIsNpcGroup\(\)/);
assert.match(serverCache, /wasNpcGroup[\s\S]*_cachedIsNpcGroup = IsNpcGroup\(\)[\s\S]*wasNpcGroup != _cachedIsNpcGroup[\s\S]*MarkRuntimeStateDirty[\s\S]*if \(wasNpcGroup\)[\s\S]*EnforceGroupPunishment\(\)/);

assert.match(gridLimits, /var evaluateLimit = GroupComponent\.ShouldEvaluateBlockLimit\(limit\);/);
assert.match(gridLimits, /if \(evaluateLimit && directionReferenceBlock/);
assert.match(gridLimits, /if \(evaluateLimit && localWeight \+ weight > effectiveMaxCount\)/);
assert.match(gridLimits, /groupBucket\.TotalWeight \+= weight;/);
assert.match(gridBlocks, /if \(!groupComponent\.ShouldEvaluateBlockLimit\(limit\)\) continue;/);
assert.match(groupLimits, /if \(!ShouldEvaluateBlockLimit\(limit\)\) continue;/);
assert.match(groupLimits, /ShouldEvaluateBlockLimit\(punishment\.Limit\)/);
assert.equal((evaluation.match(/ShouldEvaluateBlockLimit\(limit\)/g) || []).length, 3);
assert.match(merge, /if \(!groups\.Any\(group => group\.ShouldEvaluateBlockLimit\(limit\)\)\) continue;/);
assert.match(noFlyZone, /if \(!groupComponent\.ShouldEvaluateBlockLimit\(limit\)\) continue;/);
assert.match(statusHud, /if \(!group\.ShouldEvaluateBlockLimit\(limit\)\) continue;/);
assert.match(lcd, /if \(!group\.ShouldEvaluateBlockLimit\(limit\)\) continue;/);
assert.match(runtime, /ProtoMember\(6\).*EvaluationDisabled/);
assert.match(snapshot, /EvaluationDisabled = !ShouldEvaluateBlockLimit\(limit\)/);

assert.match(apiData, /API_MINOR\s*=\s*5/);
assert.match(apiData, /ProtoMember\(12\).*IgnoredByNpc/);
assert.match(api, /IgnoredByNpc = limit\.IgnoredByNpc/);
assert.match(api, /if \(!groupComponent\.ShouldEvaluateBlockLimit\(configuredLimit\)\) continue;/);
assert.match(clientApi, /limit == null \|\| limit\.EvaluationDisabled/);
assert.match(clientApi, /if \(runtime\.EvaluationDisabled\) break;/);

assert.match(configurator, /ignoredByNpc: false/);
assert.match(configurator, /ignoredByNpc: Boolean\(limit\.ignoredByNpc\)/);
assert.match(configurator, /data-action="limit-ignore-npc"/);
assert.equal((configurator.match(/ignoredByNpc: boolOf\(limitNode, "IgnoredByNpc", false\)/g) || []).length, 2);
assert.match(configurator, /<IgnoredByNpc>\$\{Boolean\(limit\.ignoredByNpc\)\}<\/IgnoredByNpc>/);
assert.match(configurator, /selectedCore\.blockLimits\[limitIndex\]\.ignoredByNpc = inputElement\.checked;/);
assert.match(readme, /`IgnoredByNpc`[\s\S]*recognized as NPC/);
assert.match(apiUsage, /BlockLimitData\.IgnoredByNpc[\s\S]*API v4\.3/);

console.log("NPC-ignored block-limit contract checks passed.");
