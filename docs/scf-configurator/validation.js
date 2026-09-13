export const VALID_DIRECTIONS = ["Forward", "Backward", "Up", "Down", "Left", "Right"];
export const VALID_ALLOWED_DIRECTIONS = [...VALID_DIRECTIONS, "Any"];

const VALID_MOBILITY_TYPES = ["Static", "Mobile", "Both"];
const VALID_SPEED_LIMIT_TYPES = ["Normal", "Friction"];
const VALID_SPEED_OVERRIDE_MODES = ["None", "OnlyIfHeavier", "Priority", "Any"];
const VALID_FACTION_RANKS = ["None", "Member", "Leader", "Founder"];
const VALID_PUNISHMENT_TYPES = ["ShutOff", "Damage", "Delete", "Explode", "DeleteWithoutRefund"];
const VALID_LIMIT_VISIBILITIES = ["Always", "NearLimit", "Hidden"];

const asArray = (value) => Array.isArray(value) ? value : [];
const text = (value) => String(value ?? "");
const trimmed = (value) => text(value).trim();

export function normalizeBlockTypeId(typeId) {
  return trimmed(typeId).replace(/^MyObjectBuilder_/i, "");
}

function isValidDirectionToken(value) {
  const token = trimmed(value);
  return VALID_ALLOWED_DIRECTIONS.some((direction) => direction.toLowerCase() === token.toLowerCase())
    || /^[0-6]$/.test(token);
}

export function isValidSpecificDirection(value) {
  const token = trimmed(value);
  return VALID_DIRECTIONS.some((direction) => direction.toLowerCase() === token.toLowerCase())
    || /^[0-5]$/.test(token);
}

export function limitNeedsDirectionWarning(limit) {
  if (Number(limit?.maxCountPerDirection) < 0) return false;
  if (asArray(limit?.allowedDirections).some(isValidSpecificDirection)) return false;

  const selectedGroups = new Set(asArray(limit?.blockGroups));
  return !Object.entries(limit?.blockGroupDirections || {}).some(([groupName, directions]) =>
    selectedGroups.has(groupName) && text(directions).split(",").some(isValidSpecificDirection));
}

export function enabledBudgetDirections(limit) {
  const directions = new Set();
  const add = (allowed) => {
    const values = asArray(allowed);
    if (!values.length || values.includes("Any")) VALID_DIRECTIONS.forEach((value) => directions.add(value));
    else values.filter((value) => VALID_DIRECTIONS.includes(value)).forEach((value) => directions.add(value));
  };
  const included = asArray(limit?.blockGroups);
  if (!included.length) add(limit?.allowedDirections);
  included.forEach((groupName) => {
    const override = limit?.blockGroupDirections?.[groupName];
    if (override == null) return add(limit?.allowedDirections);
    const tokens = text(override).split(",").map(trimmed).filter(Boolean);
    const allowed = tokens.map((token) => VALID_ALLOWED_DIRECTIONS.find((value) =>
      value.toLowerCase() === token.toLowerCase()) || (/^[0-6]$/.test(token) ? VALID_ALLOWED_DIRECTIONS[Number(token)] : null))
      .filter(Boolean);
    // Runtime discards an override containing only invalid tokens; an empty override means Any.
    add(tokens.length && !allowed.length ? limit?.allowedDirections : allowed);
  });
  return VALID_DIRECTIONS.filter((direction) => directions.has(direction));
}

export function validateDirectionBudgets(limit) {
  const budgets = asArray(limit?.directionBudgets);
  const errors = [];
  const fallback = Number(limit?.maxCountPerDirection ?? -1);
  if (!budgets.length && fallback < 0) return { errors, total: null };
  const finiteCap = (value) => value != null && trimmed(value) !== "" &&
    Number.isFinite(Math.fround(Number(value))) && Number(value) >= 0;
  if (!finiteCap(limit?.maxCount))
    errors.push("DirectionBudgets requires a finite, non-negative MaxCount.");
  if (fallback !== -1 && !finiteCap(fallback))
    errors.push("MaxCountPerDirection must be -1 or finite and non-negative.");
  const byDirection = new Map();
  budgets.forEach((budget) => {
    if (!VALID_DIRECTIONS.includes(budget?.direction))
      errors.push(`Invalid DirectionBudget direction '${text(budget?.direction)}'; use one of the six specific directions.`);
    if (byDirection.has(budget?.direction))
      errors.push(`Duplicate DirectionBudget for ${budget?.direction}.`);
    byDirection.set(budget?.direction, budget?.maxCount);
    if (!finiteCap(budget?.maxCount))
      errors.push(`DirectionBudget for ${budget?.direction} must be finite and non-negative.`);
  });
  const directions = new Set([...enabledBudgetDirections(limit), ...byDirection.keys()]);
  let total = 0;
  directions.forEach((direction) => {
    const cap = byDirection.has(direction) ? Number(byDirection.get(direction)) : fallback;
    if (cap >= 0) total += Math.fround(cap);
  });
  total = Math.fround(total);
  if (total > Math.fround(Number(limit?.maxCount)))
    errors.push(`DirectionBudgets total (including inherited caps) ${total} exceeds MaxCount ${limit?.maxCount}.`);
  return { errors, total };
}

function duplicateValues(items, keyOf, caseInsensitive = false) {
  const counts = new Map();
  asArray(items).forEach((item) => {
    const rawKey = text(keyOf(item));
    const key = caseInsensitive ? rawKey.toLowerCase() : rawKey;
    const current = counts.get(key) || { value: rawKey, count: 0 };
    current.count += 1;
    counts.set(key, current);
  });
  return Array.from(counts.values()).filter((entry) => entry.count > 1);
}

function coreLabel(core, index, isNoCore) {
  return trimmed(core?.uniqueName) || trimmed(core?.subtypeId) || (isNoCore ? "No Core" : `ShipCore ${index + 1}`);
}

function validateEnum(errors, label, field, value, allowed) {
  if (!allowed.includes(value))
    errors.push(`${label} has invalid <${field}> value '${text(value)}'.`);
}

export function validateEditorConfig(config = {}) {
  const errors = [];
  const warnings = [];
  const blockGroups = asArray(config.blockGroups);
  const manifestGroups = asArray(config.manifestGroups);
  const shipCores = asArray(config.shipCores);
  const upgradeModules = asArray(config.upgradeModules);
  const allCores = [
    ...(config.noCoreCore ? [{ core: config.noCoreCore, isNoCore: true, index: 0 }] : []),
    ...shipCores.map((core, index) => ({ core, isNoCore: false, index }))
  ];

  duplicateValues(blockGroups, (group) => trimmed(group?.name)).forEach((duplicate) =>
    errors.push(`Found duplicate BlockGroup Name '${duplicate.value}' (${duplicate.count} entries).`));

  manifestGroups.forEach((group, index) => {
    const name = trimmed(group?.name);
    if (!name) errors.push(`Manifest group ${index + 1} is missing <Name>.`);
    if (Number(group?.maxCount) < 0)
      errors.push(`Manifest group '${name || index + 1}' is missing a valid non-negative <MaxCount>.`);
  });
  duplicateValues(manifestGroups, (group) => trimmed(group?.name), true).forEach((duplicate) =>
    errors.push(`Duplicate manifest group '${duplicate.value}' (${duplicate.count} entries).`));

  duplicateValues(shipCores, (core) => text(core?.uniqueName)).forEach((duplicate) =>
    errors.push(`Found duplicate ShipCore UniqueName '${duplicate.value}' (${duplicate.count} entries).`));

  const manifestGroupNames = new Set(manifestGroups
    .map((group) => trimmed(group?.name).toLowerCase())
    .filter(Boolean));
  const blockGroupNames = new Set(blockGroups
    .map((group) => trimmed(group?.name).toLowerCase())
    .filter(Boolean));

  allCores.forEach(({ core, isNoCore, index }) => {
    const label = `ShipCore '${coreLabel(core, index, isNoCore)}'`;
    validateEnum(errors, label, "MobilityType", core?.mobilityType, VALID_MOBILITY_TYPES);
    validateEnum(errors, label, "SpeedLimitType", core?.speedLimitType, VALID_SPEED_LIMIT_TYPES);
    validateEnum(errors, label, "SpeedOverrideMode", core?.speedOverrideMode, VALID_SPEED_OVERRIDE_MODES);
    validateEnum(errors, label, "MinFactionRank", core?.minFactionRank, VALID_FACTION_RANKS);

    if (!isNoCore) {
      asArray(core?.manifestGroups).forEach((groupName) => {
        if (!manifestGroupNames.has(trimmed(groupName).toLowerCase()))
          errors.push(`${label} references unknown manifest group '${trimmed(groupName)}'.`);
      });
    }

    const allowanceDefinitions = new Set();
    const allowanceNames = new Set();
    asArray(core?.allowedUpgradeModules).forEach((allowance) => {
      const subtypeId = trimmed(allowance?.subtypeId);
      const uniqueName = trimmed(allowance?.uniqueName);
      if (subtypeId) {
        const typeId = normalizeBlockTypeId(allowance?.typeId) || "UpgradeModule";
        const identity = `${typeId}/${subtypeId}`;
        const key = identity.toLowerCase();
        if (allowanceDefinitions.has(key))
          errors.push(`${label} has duplicate AllowedUpgradeModules entry for '${identity}'.`);
        allowanceDefinitions.add(key);
      } else if (uniqueName) {
        const key = uniqueName.toLowerCase();
        if (allowanceNames.has(key))
          errors.push(`${label} has duplicate AllowedUpgradeModules entry for '${uniqueName}'.`);
        allowanceNames.add(key);
      }
    });

    asArray(core?.blockLimits).forEach((limit, limitIndex) => {
      const limitName = trimmed(limit?.name) || `BlockLimit ${limitIndex + 1}`;
      const limitLabel = `${label} limit '${limitName}'`;
      validateDirectionBudgets(limit).errors.forEach((error) => errors.push(`${limitLabel}: ${error}`));
      validateEnum(errors, limitLabel, "LimitVisibility", limit?.limitVisibility, VALID_LIMIT_VISIBILITIES);
      validateEnum(errors, limitLabel, "PunishmentType", limit?.punishmentType, VALID_PUNISHMENT_TYPES);

      asArray(limit?.allowedDirections).forEach((direction) => {
        if (!VALID_ALLOWED_DIRECTIONS.includes(direction))
          errors.push(`${limitLabel} has invalid <AllowedDirections> value '${text(direction)}'.`);
      });

      const included = asArray(limit?.blockGroups);
      const excluded = asArray(limit?.excludedBlockGroups);
      included.forEach((groupName) => {
        if (!blockGroupNames.has(trimmed(groupName).toLowerCase()))
          warnings.push(`${limitLabel} references unknown BlockGroup '${trimmed(groupName)}' in <BlockGroups>.`);
      });
      excluded.forEach((groupName) => {
        if (!blockGroupNames.has(trimmed(groupName).toLowerCase()))
          warnings.push(`${limitLabel} references unknown BlockGroup '${trimmed(groupName)}' in <ExcludedBlockGroups>.`);
      });

      const excludedNames = new Set(excluded.map((name) => trimmed(name).toLowerCase()));
      const overlaps = included.filter((name) => excludedNames.has(trimmed(name).toLowerCase()));
      if (overlaps.length)
        warnings.push(`${limitLabel} includes and excludes BlockGroup(s) ${overlaps.join(", ")}; exclusion wins.`);

      const includedNames = new Set(included);
      Object.entries(limit?.blockGroupDirections || {}).forEach(([groupName, directions]) => {
        if (!includedNames.has(groupName)) return;
        const invalid = text(directions).split(",")
          .map((token) => token.trim())
          .filter((token) => token && !isValidDirectionToken(token));
        if (invalid.length)
          warnings.push(`${limitLabel} has invalid Directions value(s) ${invalid.join(", ")} on BlockGroup '${groupName}'; invalid values are ignored.`);
      });

      if (limitNeedsDirectionWarning(limit))
        warnings.push(`${limitLabel} has <MaxCountPerDirection> enabled but no valid direction in <AllowedDirections> or a BlockGroups Directions attribute.`);
    });
  });

  upgradeModules.forEach((module, index) => {
    const subtypeId = trimmed(module?.subtypeId);
    const label = `UpgradeModuleConfig '${subtypeId || index + 1}'`;
    if (!subtypeId) errors.push(`UpgradeModuleConfig ${index + 1} is missing <SubtypeId>.`);
    if (asArray(module?.modifiers).some((modifier) => !trimmed(modifier?.stat)))
      errors.push(`${label} has a modifier with no <Stat>.`);
    if (asArray(module?.blockLimitModifiers).some((modifier) => !trimmed(modifier?.blockLimitName)))
      errors.push(`${label} has a block limit modifier with no <BlockLimitName>.`);
  });

  duplicateValues(
    upgradeModules.filter((module) => trimmed(module?.subtypeId)),
    (module) => `${normalizeBlockTypeId(module?.typeId) || "UpgradeModule"}/${trimmed(module?.subtypeId)}`
  ).forEach((duplicate) =>
    errors.push(`Found duplicate UpgradeModule TypeId/SubtypeId '${duplicate.value}' (${duplicate.count} entries).`));

  return { errors, warnings };
}
