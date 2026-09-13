import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const root = new URL("../", import.meta.url);
const read = path => readFile(new URL(path, root), "utf8");

const [connectors, limits, gridLimits, gridBlocks, upgrades, evaluation, bucket, runtime, replica, sharedLimits, tick, readme] = await Promise.all([
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Server/Components/GroupComponent.Connectors.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Server/Components/GroupComponent.Limits.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Server/Components/GridComponent.Limits.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Server/Components/GridComponent.Blocks.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Server/Components/GroupComponent.Upgrades.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Shared/Limits/LimitEvaluation.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Shared/Limits/LimitSupport.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Shared/Network/RuntimeStateContracts.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Client/Components/GroupComponent.Replica.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Shared/Components/GroupComponent.Limits.cs"),
  read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Session/Server/Session.ServerTick.cs"),
  read("docs/ship-core-framework.md"),
]);

assert.match(connectors, /ApplyConnectorLimitContributions/);
assert.match(connectors, /!limit\.IsCriticalLimit/);
assert.match(connectors, /otherComp\.TryGetConnectedBlacklistingGroup\(out owner\)/);
assert.match(connectors, /ReferenceEquals\(owner, this\)/);
assert.match(connectors, /ConnectorWeight \+= weight/);
assert.match(connectors, /ConnectorMembers\.Add\(block\)/);
assert.match(connectors, /UpdateConnectedLimitContributions/);
assert.match(connectors, /UpdateConnectorLimitContribution\(this, block, added\)/);
assert.match(connectors, /CopyConnectorLimitContributions/);
assert.match(connectors, /OnUpgradeModulesChanged\(true\)/);
assert.doesNotMatch(limits, /QueueConnectedLimitRefresh/);
assert.doesNotMatch(upgrades, /RebuildConnectorPunishmentLinks\(\)/);
assert.match(limits, /rebuildConnectorLimits[\s\S]*ApplyConnectorLimitContributions\(groupLimits\)[\s\S]*CopyConnectorLimitContributions\(groupLimits\)/);
assert.match(gridBlocks, /CubeGridModifiers\.ApplyModifiers\(functionalBlock, groupComponent\.Modifiers\)/);
assert.doesNotMatch(gridBlocks, /groupComponent\.ApplyModifiers\(groupComponent\.Modifiers\)/);

assert.match(bucket, /double ConnectorWeight/);
assert.match(bucket, /HashSet<IMySlimBlock> ConnectorMembers/);
assert.match(limits, /connectorOver = connectorTotal - connectorCapacity/);
assert.match(limits, /candidate\.Key, PunishmentType\.ShutOff/);
assert.match(limits, /alreadyShutOffConnectorWeight \+= weight/);
assert.match(limits, /if \(!functionalBlock\.Enabled\)/);
assert.match(limits, /PunishLimitedBlocks = IsMinimumBlocksLimitedBlockGateTriggered\(\)/);
assert.match(gridLimits, /TotalWeight - groupBucket\.ConnectorWeight/);
assert.match(evaluation, /bucket\.TotalWeight - bucket\.ConnectorWeight/);
assert.match(runtime, /ProtoMember\(4\).*ConnectorCount/);
assert.match(replica, /ConnectorWeight = runtime\.ConnectorCount/);
assert.doesNotMatch(sharedLimits, /TryGetConnectedBlacklistingGroup/);
assert.match(tick, /EnforceConnectorLimitPunishment\(\)/);

assert.match(readme, /Imported connector blocks over remaining capacity are shut off/);
assert.match(readme, /both connector import paths skip this limit/);

console.log("Connector limit aggregation contract checks passed.");
