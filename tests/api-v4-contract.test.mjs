import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const root = new URL("../ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/", import.meta.url);
const read = async path => readFile(new URL(path, root), "utf8");

const [
  data,
  provider,
  readiness,
  clientFactory,
  serverFactory,
  clientConfig,
  runtimeConsumer,
  wrapper,
] = await Promise.all([
  read("API/ApiData.cs"),
  read("API/ModAPI.cs"),
  read("API/ModAPI.Readiness.cs"),
  read("API/Client/ModAPI.ReplicaQueries.cs"),
  read("API/Server/ModAPI.ServerFactory.cs"),
  read("Client/Network/PresentationPacketHandlers.cs"),
  read("Session/Client/Session.RuntimeStateConsumer.cs"),
  read("API/SCF_ModAPIClient.cs"),
]);

assert.match(data, /API_MAJOR\s*=\s*4/);
assert.doesNotMatch(data, /API_MAJOR\s*=\s*3/);
assert.match(data, /GetApiMajor\(apiVersion\) == API_MAJOR/);
assert.match(data, /SERVER_LOCAL_API_ID/);
assert.match(data, /CLIENT_REPLICA_API_ID/);
assert.match(data, /EVENT_RUNTIME_SNAPSHOT_READY/);
assert.match(data, /ConfigurationUnavailable\s*=\s*8/);
assert.match(data, /ProtoMember\(5\)\]\s*public string ConfigurationError/);
assert.match(
  data,
  /ProtoMember\(9\)\]\s*public string\[\] ExcludedBlockGroupNames/,
);

assert.match(provider, /Session\.IsServer[\s\S]*SERVER_LOCAL_API_ID/);
assert.match(provider, /if \(Session\.IsClient\)[\s\S]*CLIENT_REPLICA_API_ID/);
assert.doesNotMatch(provider, /else if \(Session\.IsClient\)/);
assert.match(
  provider,
  /ExcludedBlockGroupNames\s*=\s*\(limit\.ExcludedBlockGroupsShortHand/,
);
assert.match(readiness, /MarkConfigUnavailable\(string reason\)/);
assert.match(readiness, /ApiReadStatusData\.ConfigurationUnavailable/);

assert.doesNotMatch(clientFactory, /case ApiMethodId\.SetFriction/);
assert.doesNotMatch(clientFactory, /case ApiMethodId\.ClearFriction/);
assert.match(clientFactory, /RuntimeStateStore\.TryGetByGrid/);
assert.match(
  clientFactory,
  /ClientReplicaMethodFactory\(methodId\)[\s\S]*clientRead == null[\s\S]*ServerMethodFactory\(methodId\)/,
);
assert.match(serverFactory, /case ApiMethodId\.SetFrictionEnabledForGroup/);
assert.match(serverFactory, /case ApiMethodId\.SetGridModifiersOverrideForGroup/);
assert.match(serverFactory, /case ApiMethodId\.SetSpeedModifiersOverrideForGroup/);
assert.match(serverFactory, /case ApiMethodId\.SetPassiveDefenseModifiersOverrideForGroup/);
assert.match(serverFactory, /case ApiMethodId\.SetActiveDefenseModifiersOverrideForGroup/);
assert.match(serverFactory, /ApiCapabilityData\.RuntimeMutations/);

assert.ok(
  clientConfig.indexOf("ModAPI.MarkConfigReady(true)") <
    clientConfig.indexOf("ModAPI.BroadcastConfigReceived()"),
  "config readiness must be updated before ConfigReceived is broadcast",
);
assert.match(runtimeConsumer, /ModAPI\.MarkRuntimeSnapshotReady\(sequence, snapshotRevision\)/);

assert.match(wrapper, /class ShipCoreFrameworkClientApi/);
assert.match(wrapper, /class ShipCoreFrameworkServerApi/);
assert.doesNotMatch(wrapper, /\[Obsolete/);
assert.doesNotMatch(wrapper, /class ShipCoreFrameworkClient\b/);
assert.doesNotMatch(wrapper, /Legacy(Value|Try|Command)/);
assert.doesNotMatch(
  wrapper,
  /public ApiReadResult<[^\r\n]*\([^\r\n]*IMyCubeGrid\b/,
);
assert.doesNotMatch(wrapper, /GetEntityId\s*\(\s*IMyCubeGrid\b/);
assert.match(wrapper, /!ApiConstants\.IsApiCompatible\(ProviderApiVersion\)/);
assert.notEqual((3 << 8) | 10, (4 << 8) | 0, "v3.10 must not match the v4 provider version");
assert.match(wrapper, /RuntimeSnapshotReady = false;[\s\S]*ConfigReceived/);

console.log("API v4 role/readiness contract checks passed.");
