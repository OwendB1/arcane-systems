import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { validateEditorConfig } from "../docs/scf-configurator/validation.js";

const root = new URL("../", import.meta.url);
const [app, html] = await Promise.all([
  readFile(new URL("docs/scf-configurator/app.js", root), "utf8"),
  readFile(new URL("docs/scf-configurator/index.html", root), "utf8")
]);

const validCore = {
  uniqueName: "Core A",
  subtypeId: "CoreA",
  mobilityType: "Both",
  speedLimitType: "Normal",
  speedOverrideMode: "OnlyIfHeavier",
  minFactionRank: "None",
  manifestGroups: ["Fleet"],
  allowedUpgradeModules: [
    { typeId: "UpgradeModule", subtypeId: "ModuleA", uniqueName: "", maxCount: 1 }
  ],
  blockLimits: [{
    name: "Weapons",
    maxCount: 2,
    maxCountPerDirection: 2,
    limitVisibility: "Always",
    punishmentType: "ShutOff",
    allowedDirections: ["Forward"],
    blockGroups: ["Weapons"],
    blockGroupDirections: {},
    excludedBlockGroups: []
  }]
};

const valid = validateEditorConfig({
  blockGroups: [{ name: "Weapons", blockTypes: [] }],
  manifestGroups: [{ name: "Fleet", maxCount: 2 }],
  shipCores: [validCore],
  upgradeModules: [{
    typeId: "UpgradeModule",
    subtypeId: "ModuleA",
    modifiers: [{ stat: "GyroForce" }],
    blockLimitModifiers: [{ blockLimitName: "Weapons" }]
  }]
});
assert.deepEqual(valid, { errors: [], warnings: [] });

const deleteWithoutRefund = validateEditorConfig({
  blockGroups: [{ name: "Weapons", blockTypes: [] }],
  manifestGroups: [],
  shipCores: [{
    ...validCore,
    manifestGroups: [],
    allowedUpgradeModules: [],
    blockLimits: [{ ...validCore.blockLimits[0], punishmentType: "DeleteWithoutRefund" }]
  }],
  upgradeModules: []
});
assert.deepEqual(deleteWithoutRefund, { errors: [], warnings: [] });

const invalid = validateEditorConfig({
  blockGroups: [{ name: "Weapons" }, { name: " Weapons " }],
  manifestGroups: [
    { name: "", maxCount: -1 },
    { name: "Fleet", maxCount: 1 },
    { name: "fleet", maxCount: 2 }
  ],
  shipCores: [
    {
      ...validCore,
      mobilityType: "Invalid",
      manifestGroups: ["Missing Fleet"],
      allowedUpgradeModules: [
        { typeId: "MyObjectBuilder_UpgradeModule", subtypeId: "ModuleA" },
        { typeId: "UpgradeModule", subtypeId: "modulea" },
        { uniqueName: "Named" },
        { uniqueName: "named" }
      ],
      blockLimits: [
        {
          name: "Invalid directions",
          maxCountPerDirection: -1,
          limitVisibility: "Invalid",
          punishmentType: "Invalid",
          allowedDirections: ["Bogus"],
          blockGroups: ["Weapons", "Missing Group"],
          blockGroupDirections: { Weapons: "Forward,Bad,9" },
          excludedBlockGroups: ["weapons", "Missing Exclusion"]
        },
        {
          name: "Missing direction",
          maxCountPerDirection: 3,
          limitVisibility: "Always",
          punishmentType: "ShutOff",
          allowedDirections: [],
          blockGroups: ["Weapons"],
          blockGroupDirections: {},
          excludedBlockGroups: []
        }
      ]
    },
    { ...validCore }
  ],
  upgradeModules: [
    { typeId: "UpgradeModule", subtypeId: "", modifiers: [{ stat: "" }], blockLimitModifiers: [{ blockLimitName: "" }] },
    { typeId: "MyObjectBuilder_UpgradeModule", subtypeId: "Duplicate", modifiers: [], blockLimitModifiers: [] },
    { typeId: "UpgradeModule", subtypeId: "Duplicate", modifiers: [], blockLimitModifiers: [] }
  ]
});

const errors = invalid.errors.join("\n");
const warnings = invalid.warnings.join("\n");
assert.match(errors, /duplicate BlockGroup Name/);
assert.match(errors, /Manifest group 1 is missing <Name>/);
assert.match(errors, /non-negative <MaxCount>/);
assert.match(errors, /Duplicate manifest group 'Fleet'/);
assert.match(errors, /duplicate ShipCore UniqueName 'Core A'/);
assert.match(errors, /invalid <MobilityType>/);
assert.match(errors, /unknown manifest group 'Missing Fleet'/);
assert.match(errors, /duplicate AllowedUpgradeModules entry for 'UpgradeModule\/modulea'/i);
assert.match(errors, /invalid <AllowedDirections>/);
assert.match(errors, /invalid <LimitVisibility>/);
assert.match(errors, /invalid <PunishmentType>/);
assert.match(errors, /UpgradeModuleConfig 1 is missing <SubtypeId>/);
assert.match(errors, /modifier with no <Stat>/);
assert.match(errors, /block limit modifier with no <BlockLimitName>/);
assert.match(errors, /duplicate UpgradeModule TypeId\/SubtypeId 'UpgradeModule\/Duplicate'/);

assert.match(warnings, /unknown BlockGroup 'Missing Group'/);
assert.match(warnings, /unknown BlockGroup 'Missing Exclusion'/);
assert.match(warnings, /includes and excludes BlockGroup\(s\) Weapons/);
assert.match(warnings, /invalid Directions value\(s\) Bad, 9/);
assert.match(warnings, /MaxCountPerDirection.*no valid direction/);

assert.match(html, /id="validationStatus"/);
assert.match(app, /const validation = renderEditorValidation\(\)/);
assert.match(app, /function generateValidatedXml/);
assert.match(app, /xml\.validation\.errors\.length === 0/);
assert.match(app, /ids\(id\)\.disabled = blocked/);
assert.match(app, /\$\{escapeXml\(groupName\)\} \(unknown\)/);
assert.doesNotMatch(app, /Pruned .*missing BlockGroup/);

console.log("Config editor framework validation parity checks passed.");
