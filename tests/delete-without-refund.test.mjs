import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const root = new URL("../", import.meta.url);
const read = path => readFile(new URL(path, root), "utf8");

const [models, worldSettings, blockActions, gridLimits, apiData, app, validation, readme] =
  await Promise.all([
    read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Config/ModConfig.XmlModels.cs"),
    read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Config/ModConfig.WorldSettings.cs"),
    read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Server/Enforcement/Utils.BlockActions.cs"),
    read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Server/Components/GridComponent.Limits.cs"),
    read("ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/API/ApiData.cs"),
    read("docs/scf-configurator/app.js"),
    read("docs/scf-configurator/validation.js"),
    read("docs/ship-core-framework.md"),
  ]);

assert.doesNotMatch(models, /DisableDeletePunishmentRefunds|RefundDeletePunishments/);
assert.doesNotMatch(worldSettings, /DisableDeletePunishmentRefunds|RefundDeletePunishments/);
assert.match(models, /enum PunishmentType[\s\S]*Delete,[\s\S]*Explode,[\s\S]*DeleteWithoutRefund/);
assert.match(apiData, /API_MINOR\s*=\s*5/);
assert.match(apiData, /DeleteWithoutRefund = 4/);
assert.match(blockActions, /RemoveAndRefund\(this IMySlimBlock block, bool refundComponents = true\)/);
assert.match(blockActions, /RemoveAndRefund\(capturedBlock, refundComponents\)/);
assert.match(blockActions, /case PunishmentType\.Delete:[\s\S]*RemoveAndRefund\(\)/);
assert.match(blockActions, /case PunishmentType\.DeleteWithoutRefund:[\s\S]*RemoveAndRefund\(false\)/);
assert.equal((gridLimits.match(/PunishmentType\.DeleteWithoutRefund/g) || []).length, 2);
assert.match(app, /"DeleteWithoutRefund"/);
assert.match(validation, /VALID_PUNISHMENT_TYPES[^\n]*"DeleteWithoutRefund"/);
assert.match(readme, /`DeleteWithoutRefund` does not/);

console.log("DeleteWithoutRefund contract checks passed.");
