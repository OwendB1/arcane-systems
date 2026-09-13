import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const root = new URL(
  "../ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/",
  import.meta.url,
);
const read = path => readFile(new URL(path, root), "utf8");

const [enforcement, lifecycle, abilities, speedState, state, sessionRun, config, worldSettings, definitions, commands,
  apiData, api, snapshot, contracts, replica, clientTick, modifiers, presentation, configurator, readme] =
  await Promise.all([
    read("Server/Enforcement/SpeedEnforcement.cs"),
    read("Server/Components/GroupComponent.Lifecycle.cs"),
    read("Server/Components/GroupComponent.Abilities.cs"),
    read("Server/Components/GroupComponent.SpeedState.cs"),
    read("Server/Components/GroupComponent.State.cs"),
    read("Session/Session.Run.cs"),
    read("Config/ModConfig.XmlModels.cs"),
    read("Config/ModConfig.WorldSettings.cs"),
    read("Session/Session.Definitions.cs"),
    read("Server/Commands/Commands.Administration.cs"),
    read("API/ApiData.cs"),
    read("API/ModAPI.cs"),
    read("Server/Components/GroupComponent.Snapshot.cs"),
    read("Shared/Network/RuntimeStateContracts.cs"),
    read("Client/Components/GroupComponent.Replica.cs"),
    read("Session/Client/Session.ClientTick.cs"),
    read("Server/Modifiers/CubeGridModifiers.Authority.cs"),
    read("Client/UI/Commands.Presentation.cs"),
    readFile(new URL("../docs/scf-configurator/app.js", import.meta.url), "utf8"),
    readFile(new URL("../docs/ship-core-framework.md", import.meta.url), "utf8"),
  ]);

const mechanicalGroupScan = sessionRun.indexOf("Parallel.ForEach(initialMechanicalGroups");
const physicalGroupScan = sessionRun.indexOf("Parallel.ForEach(initialPhysicalGroups");
assert.ok(mechanicalGroupScan >= 0, "startup must initialize mechanical groups");
assert.ok(
  physicalGroupScan > mechanicalGroupScan,
  "startup must initialize physical speed clusters after every mechanical group is registered",
);
assert.match(sessionRun, /AppendInitialPhysicalGroups\(initialPhysicalGroups\)/);
assert.doesNotMatch(sessionRun, /AppendInitialPhysicalGroups\(initialMechanicalGroups\)/);

assert.match(state, /SpeedEnforcementDeferred = true/);
assert.match(lifecycle, /MainCoreComponent = coreComponent;[\s\S]*SpeedEnforcementDeferred = false/);
assert.match(lifecycle, /confirmedAbsent[\s\S]*SpeedEnforcementDeferred = false/);
assert.match(enforcement, /if \(context\.SourceGroup\.SpeedEnforcementDeferred\) return/);
assert.match(enforcement, /baseMaxSpeed = worldSpeedLimit/);

assert.ok((lifecycle.match(/BeginSpeedRampDown\(\)/g)?.length ?? 0) >= 2);
assert.match(speedState, /SpeedRampDownCap = currentCap/);
assert.ok(
  (enforcement.match(/RampDownSpeedCap\(/g)?.length ?? 0) >= 3,
  "boost and core-loss paths must share the extracted ramp helper",
);
assert.match(enforcement, /SpeedRampDownIntervalTicks = 5/);
assert.match(enforcement, /_speedRampDownLerpStep = speedRampDownPercentage \/ 12f \* 0\.01f/);
assert.match(enforcement, /if \(sourceGroup\.SpeedRampDownActive\)/);
assert.doesNotMatch(enforcement, /MainCoreComponent == null && sourceGroup\.SpeedRampDownActive/);
assert.match(speedState, /private void BeginSpeedRampDown\(\)/);
assert.match(
  abilities,
  /if \(!previousPunishSpeed && PunishSpeed\)\s*BeginSpeedRampDown\(\)/,
);
assert.match(abilities, /ChainPunishmentGate\(ref punishments, HasBrokenMainCore\(\), GroupPunishmentFlags\.Both\)/);
assert.match(enforcement, /MathHelper\.Lerp\(currentCap, targetCap, lerpAmount\)/);
assert.doesNotMatch(enforcement, /Math\.Pow\(1f - percentage, elapsedPeriods\)/);
assert.match(definitions, /CacheSpeedRampDownStep\(Config\.SpeedRampDownPercentage\)/);
assert.match(commands, /ReloadConfig\(\)[\s\S]*ApplyConfigToDefinitions\(\)/);

assert.match(enforcement, /internal static float InterpolateSpeedRampDownCap/);
assert.match(enforcement, /if \(nextCap >= currentCap\)[\s\S]*return targetCap/);
assert.match(enforcement, /SpeedRampDownActive = speedRampDownActive/);
assert.match(enforcement, /EffectiveSpeedRampDownActive = context\.SpeedRampDownActive/);
assert.match(enforcement, /EffectiveSpeedRampDownTargetCap = context\.SpeedRampDownTarget/);
assert.match(
  enforcement,
  /rampStateChanged \|\| otherSpeedStateChanged \|\|\s*effectiveSpeedChanged && !context\.SpeedRampDownActive/,
  "cap-only ramp steps must not dirty the full runtime state",
);
assert.match(contracts, /ProtoMember\(57\)\]\s*internal bool SpeedRampDownActive/);
assert.match(contracts, /ProtoMember\(58\)\]\s*internal float SpeedRampDownTarget/);
assert.match(snapshot, /SpeedRampDownActive = speedRampDownActive/);
assert.match(snapshot, /SpeedRampDownTarget = speedRampDownTarget/);
assert.match(replica, /SpeedEnforcement\.InterpolateSpeedRampDownCap\(/);
assert.match(replica, /_runtimeSpeedRampDownLastTick = Session\.CurrentTick/);
assert.match(clientTick, /CurrentTick % SpeedEnforcement\.SpeedRampDownIntervalTicks == 0/);
assert.match(clientTick, /RunRuntimeSpeedRampDownTick\(\)/);

assert.match(config, /XmlElement\("SpeedRampDownPercentage"\)/);
assert.match(worldSettings, /SpeedRampDownPercentage < 0f \|\| import\.SpeedRampDownPercentage > 100f/);
assert.match(apiData, /ProtoMember\(23\)\]\s*public float SpeedRampDownPercentage/);
assert.match(api, /SpeedRampDownPercentage = config\.SpeedRampDownPercentage/);

assert.match(config, /XmlElement\("MaxAngularVelocity"\)[\s\S]*MaxAngularVelocity = 0f/);
assert.match(enforcement, /MaxAngularVelocity = speedModifiers != null && speedModifiers\.MaxAngularVelocity > 0f/);
assert.ok(
  enforcement.indexOf("float angularSpeedSq = angularVelocity.LengthSquared()") <
    enforcement.indexOf("if (speedSq < 0.0001f)"),
  "pure rotation must be capped before stationary linear velocity exits",
);
assert.match(enforcement, /angularVelocity \/ angularSpeed \* maxAngularVelocity/);
assert.match(enforcement, /if \(linearVelocityCapped \|\| angularVelocityCapped\)[\s\S]*physics\.SetSpeeds\(constrainedLinearVelocity, constrainedAngularVelocity\)/);
assert.match(enforcement, /if \(maxAngularVelocity > 0f\)/);
assert.match(modifiers, /case "MaxAngularVelocity"[\s\S]*ApplyUpgradeModifier\(modifiers\.MaxAngularVelocity/);
assert.match(modifiers, /MaxAngularVelocity = modifiers\.MaxAngularVelocity/);
assert.match(apiData, /ProtoMember\(15\)\]\s*public float MaxAngularVelocity/);
assert.ok((api.match(/MaxAngularVelocity = (0\.0f|modifiers\.MaxAngularVelocity)/g)?.length ?? 0) >= 3);
assert.match(replica, /MaxAngularVelocity = value\.MaxAngularVelocity/);
assert.match(presentation, /Max Angular Vel:[^\n]*MaxAngularVelocity[^\n]*rad\/s/);
assert.match(configurator, /MaxAngularVelocity: 0/);
assert.match(configurator, /"MaxAngularVelocity"/);
assert.match(readme, /`MaxAngularVelocity`[^\n]*radians per second[^\n]*less than or equal to `0` disable/);

console.log("Speed enforcement transition contract checks passed.");
