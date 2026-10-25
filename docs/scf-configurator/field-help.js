// Configuration help is keyed by the editor's existing field actions, so repeated
// controls and partial rerenders share the same explanation.
const FIELD_HELP = {
  "bt-type": "Space Engineers block TypeId to match, such as Thrust or MyObjectBuilder_Thrust. Use the definition's actual type; SubtypeId narrows the match within it. Each matching block contributes CountWeight to limits that include this group.",
  "bt-subtype": "Exact block subtype within TypeId. An empty value matches only the empty/base subtype; enter any to match every subtype of this type. A named subtype matches that definition only. Matching is case-sensitive except for the any keyword.",
  "bt-weight": "Weighted cost of one matching block in each limit using this group. For example, weight 2 consumes two units of MaxCount, while 0.5 consumes half a unit. This is not a physical block count or mass; directional budgets use this weight too.",
  "bt-primary-direction": "Block-local axis treated as this block's facing for directional restrictions and budgets. Forward is the default. Choose Up, for example, when a weapon's practical firing axis is its local up axis. Runtime compares this axis with the main core's orientation.",
  "group-name": "Unique reusable block-group name, referenced by included and excluded groups in block limits. A group classifies blocks; it does not impose a cap until a core limit references it. Keep names distinct to avoid ambiguous references.",
  "manifest-name": "Name of a shared core-count group in ShipCoreConfig_Manifest.xml. Assign core profiles to it to make them share its MaxCount allowance. This is separate from reusable block groups, which classify individual block types.",
  "manifest-max": "Non-negative maximum simultaneous cores in this manifest group, shared across its member profiles. Group counts are global across loaded mods/configs. Assign member profiles under Ship cores → Docking & shared caps. Zero allows none; negative values are invalid here, unlike optional ship capacity caps.",
  "core-manifest-group-toggle": "Assign this core to the named shared manifest group. Its cores count toward that group's MaxCount alongside other assigned core profiles. Membership is stored on the core's manifest entry, not inside its ShipCore XML file.",
  "core-selection-priority": "Connector blacklist ranking only. Higher numbers outrank lower numbers regardless of ship size; omitted values default to 0. Equal priorities compare total mechanical-group block count. If both match, neither group outranks the other. The winner must also blacklist the other main core's SubtypeId to count its blocks against the winner's non-critical limits; imported overflow is shut off. Example: carrier 10 outranks fighter 0 even if the fighter is larger. Works across a transitive connector network. Does not select the main/backup core within a mechanical group or determine the speed source (SpeedOverridePriority).",
  "core-manifest-blacklist-toggle": "Blacklist this core subtype when it is in the same connected connector network. This core must outrank that group by CoreSelectionPriority, then group block count. Matching blocks from the lower-ranked group consume this core's non-critical limits; imported overflow is shut off. Priority alone does not activate a blacklist, and critical limits never import these blocks.",
  "core-cross-connector-punishment-whitelist-toggle": "Exempt this core from importing blocks from directly connected no-core groups through CrossConnectorPunishment limits. Stored as CrossConnectorPunishmentWhitelist in the manifest. This does not exempt docked ships from manifest core blacklist enforcement.",
  "core-subtype": "Actual beacon block SubtypeId identifying this core profile. Required for normal cores and used by runtime core lookup and manifest blacklist entries. The No Core profile supplies defaults for groups without an active configured core and has no physical core block.",
  "core-unique": "Friendly configuration name used in commands, selection, and UI. Give every core profile a distinct name. This is separate from the block's SubtypeId, which identifies the physical core definition.",
  "core-output-directory": "Relative output folder for this core's XML, such as Data/Cores/Combat/. Generated manifest paths follow this folder. Keep it inside the mod's Data directory. No Core always writes ShipCoreConfig_No_Core.xml at the configuration root, so its folder cannot be edited.",
  "core-mobility": "Allowed grid state: Static for stations, Mobile for ships, or Both. A mismatch activates speed and modifier punishment gates. This restricts valid operation; it does not automatically convert a station into a ship or vice versa.",
  "core-maxblocks": "Maximum total physical block count across this mechanical group. Negative disables the cap. New blocks that would exceed it are removed, and reaching/exceeding the capacity threshold can trigger capacity punishment. Upgrade capacity modifiers can adjust the effective cap.",
  "core-minblocks": "Minimum total blocks needed to keep non-critical limited blocks enabled. Negative disables this requirement. Falling below the minimum forces those blocks off; reaching the minimum clears the gate. Critical limits are exempt from this group-wide shutoff, but still enforce their own rules.",
  "core-maxmass": "Maximum mechanical-group dry mass in kilograms, using full block-definition mass. Inventory contents and construction progress do not change this tracked mass. Negative disables the cap. New blocks exceeding it are removed; capacity upgrade modules can change the effective cap.",
  "core-maxpcu": "Maximum total tracked PCU across the mechanical group, summed from block definitions. Negative disables the cap. New blocks that exceed it are removed. This is independent of MaxBlocks and weighted block limits; capacity upgrade modules can adjust it.",
  "core-maxbackupcores": "Maximum additional backup cores beyond the active main core in this mechanical group. Negative disables the cap. Backups use the group's permitted core subtype and must satisfy orientation requirements. CoreSelectionPriority does not choose which backup becomes main.",
  "core-maxpp": "Maximum number of groups using this core profile that one player may own. Negative disables the player cap. This is an ownership/placement limit, independent of the faction and shared manifest-group caps.",
  "core-maxpf": "Fixed maximum groups using this core profile that one faction may own. -1 disables the fixed faction cap. When FactionPlayersNeededPerCore is also enabled, runtime applies the lower of the fixed and member-scaled allowances.",
  "core-minpf": "Minimum core allowance when FactionPlayersNeededPerCore is positive. Default 0 adds no floor; use 1 with three players per core to allow small factions their first core. MaxPerFaction remains the hard ceiling. Other faction, player, rank, and manifest requirements still apply.",
  "core-faction-players-needed": "Faction member scaling: a positive N allows one core of this profile per N faction members. For example, 10 members with N=5 allow two. A negative value disables scaling. MinPerFaction sets a floor on this allowance. When MaxPerFaction is also set, the lower allowance applies.",
  "core-min-faction-rank": "Minimum faction rank of the grid's majority owner required to place this core: None disables the rank requirement; Member, Leader, and Founder impose increasing requirements. Invalid placement is rejected and refunded before the core activates or consumes faction allowance.",
  "core-minplayers": "Minimum faction member count required for this core profile. Negative disables the requirement. When enabled, an owner without a faction cannot satisfy it. This checks faction size, not the number of currently online players.",
  "core-maxplayers": "Maximum faction member count permitted for this core profile. Negative disables the requirement. A faction larger than this fails the applicable placement/punishment gates. This is faction membership, not online player count or a maximum number of ships.",
  "core-fb": "Require beacon broadcasting for this core. When enabled, missing or broken required beacon broadcasting becomes a punishment gate. BroadcastRange sets the forced radius. Serialized using the framework's ForceBroadCast tag spelling.",
  "core-fbr": "Forced beacon broadcasting radius in metres when ForceBroadcast is enabled. Default 2000. This controls the broadcast requirement's range, not the ship's speed, connector detection radius, or a block-limit distance.",
  "core-speedboost": "Enable the core's temporary speed boost ability. MaxBoost is a multiplier of the world's maximum-speed baseline, and BoostDuration/BoostCoolDown are seconds. Enabling the ability does not activate a boost automatically.",
  "core-enable-active-defense": "Enable the active-defense ability. While it runs, Active Defense Modifiers replace the passive defense profile; Duration and Cooldown in that profile control the base timers. The passive profile is used outside the active period.",
  "core-speed-limit-type": "Normal enforces a direct speed cap with post-boost ramp-down. Friction applies deceleration over the configured friction speeds/curve, providing a soft cap. Friction units depend on the world FrictionSpeedValueMode; atmospheric settings can override that profile.",
  "core-speed-override-mode": "Select the speed-source tier for physically linked groups. Tiers rank Any above Priority above OnlyIfHeavier above None. Only the highest present tier competes; Priority first compares SpeedOverridePriority. Otherwise candidates compare dry mass, then explicit-core presence and grid ID. If all are None, mass still chooses a fallback source so physics retains a cap.",
  "core-speed-override-priority": "Integer used to rank speed-source candidates when the winning SpeedOverrideMode tier is Priority. Higher wins, then dry mass breaks ties. Has no effect in other tiers and is separate from CoreSelectionPriority, which ranks connector blacklist groups.",
  "core-power-overclock-enabled": "Enable the core's power overclock hotbar action. Activation temporarily boosts reactor output and can apply reactor wear. Multiplier, Duration, Cooldown, and Damage/second configure the effect; enabling it does not activate it automatically.",
  "core-power-overclock-multiplier": "Reactor output multiplier while power overclock is active, applied after base and upgrade-module power modifiers. 1 is neutral; 2 doubles the resulting output. Duration limits the active period and Damage/second optionally adds wear.",
  "core-power-overclock-duration": "Power overclock active duration in seconds. Default 10. During this time the output multiplier and configured reactor integrity wear apply; Cooldown begins after the active period ends.",
  "core-power-overclock-cooldown": "Power overclock cooldown in seconds after the active effect expires. Default 60. The action cannot be used again during this recovery period; this is separate from boost and active-defense cooldowns.",
  "core-power-overclock-damage": "Integrity damage applied to each affected reactor per second while power overclock is active. 0 disables wear. This is direct reactor wear, not a multiplier of incoming damage or a reduction in fuel consumption.",
  "core-upgrade-type": "Block TypeId allowed by this upgrade-module allowance. With a SubtypeId and no type, the legacy default is UpgradeModule. Pair TypeId with SubtypeId for an explicit definition identity, or use a module config's UniqueName.",
  "core-upgrade-subtype": "Allowed module block SubtypeId, paired with TypeId (default UpgradeModule). Definition identity is checked before UniqueName when supplied. Only functional, enabled modules attached to the current main core contribute effects.",
  "core-upgrade-unique": "Allowed module configuration UniqueName, useful for modules with a non-default block type. Definition identity from SubtypeId takes precedence when supplied. The module must be attached to the current main core, functional, enabled, and within MaxCount.",
  "core-upgrade-max": "Maximum modules permitted by this allowance on the current main core. Extra modules are removed as invalid; 0 allows none. This is not the number of available module definitions or a faction-wide cap.",
  "limit-name": "Name of this weighted block limit. Upgrade modules target this exact name through BlockLimitName. Use a descriptive, stable name so module references continue to resolve when profiles are edited.",
  "limit-max": "Maximum combined CountWeight of blocks matching the included groups after exclusions. For example, a cap of 10 allows five blocks of weight 2. Directional caps are additional constraints, and allocated directional budgets must fit this total. Imported connector weight shares the aggregate capacity.",
  "limit-max-direction": "Default maximum weighted usage facing any one of the six main-core-relative directions. Negative disables this default directional cap. Uses each matched BlockType's PrimaryDirection; an explicit direction budget overrides the default for that direction. Connector-imported weight remains aggregate-only.",
  "limit-visibility": "HUD and placement-preview visibility only: Always shows the limit, NearLimit shows numeric usage at 80% and directional rules when violated, Hidden suppresses its HUD elements. Enforcement remains active for every choice; commands and LCD reports still include hidden limits.",
  "limit-cross-connector": "Import matching blocks from directly connected no-core groups into this non-critical limit. A manifest CrossConnectorPunishmentWhitelist entry for this core disables that path. Manifest blacklist imports from other cored groups are separate and use all non-critical limits regardless of this checkbox.",
  "limit-punish": "Apply this limit's punishment inside a configured no-fly zone. Used when the zone is not forcing everything off. Zone geometry and allowed core types are world settings; this field only opts this limit into zone punishment.",
  "limit-critical": "Exempt this limit from both connector import paths and group-wide limited-block shutoff gates such as MinBlocks. This does not disable the limit: normal local overflow, directional checks, and opted-in no-fly-zone punishment still apply.",
  "limit-ignore-npc": "Suspend this limit's enforcement while the active group is recognized as NPC. Counts remain tracked and enforcement resumes when it no longer qualifies. Projected merges involving a non-NPC group still evaluate the limit. Default false.",
  "limit-type": "Local violation punishment: ShutOff disables the block; Damage damages it; Delete removes it and refunds built components; Explode destroys it explosively; DeleteWithoutRefund removes it without returning components. Group-wide limited-block gates and imported connector overflow use ShutOff regardless of this setting.",
  "limit-direction-toggle": "Allow blocks to face this direction relative to the main core, using their configured PrimaryDirection axis. A direction mismatch is punishable even below MaxCount. No selected directions means no limit-wide directional lock; per-group Directions can override it. Subgrid checks also depend on the world's BlockDirectionalPlacementOnSubgrids setting.",
  "limit-direction-budget": "Explicit weighted cap for this core-relative direction. Leave empty to inherit MaxCountPerDirection; a negative default means unlimited. Explicit budgets plus inherited caps for all enabled directions must not exceed MaxCount. Zero permits no weighted usage here. Connector imports do not consume directional budgets.",
  "limit-group-toggle": "Include this reusable group's matching blocks in the limit. CountWeight determines their contribution and PrimaryDirection determines facing. Excluded groups take precedence. The optional Directions input overrides this limit's allowed directions for blocks matched through this group.",
  "limit-excluded-group-toggle": "Exclude blocks matched by this reusable group from this limit, even if an included group also matches. Excluded blocks contribute no weight or directional usage here. The excluded group's CountWeight is not subtracted numerically; its matching blocks are removed from membership.",
  "limit-group-directions": "Optional per-group directional override. Enter comma-separated Forward=0, Backward=1, Up=2, Down=3, Left=4, Right=5, or Any=6, using names or integers. An empty input inherits the limit's AllowedDirections. A non-empty override replaces that lock for blocks matched through this group; PrimaryDirection still defines their facing axis.",
  "limit-group-search": "Filter the included reusable-group checklist by name. This is an editor search only and is not exported to XML. Filtering hides unmatched rows without changing which groups are selected.",
  "limit-excluded-group-search": "Filter the excluded reusable-group checklist by name. This search changes only visible editor rows; it does not remove exclusions or change generated XML. Selected exclusions still apply while filtered out.",
  "core-atmospheric-friction-enabled": "Enable the optional atmospheric friction profile when local air density exceeds AirDensityThreshold. Its curve and cruise settings override normal friction in atmosphere. When disabled or outside the threshold, normal friction applies; an empty atmospheric curve reuses the normal curve.",
  "upgrade-type": "Actual block TypeId for this module configuration. Defaults to UpgradeModule; the MyObjectBuilder_ prefix is accepted. TypeId and SubtypeId together identify the block for early runtime tracking. They must be unique across module configs.",
  "upgrade-subtype": "Required block SubtypeId for this upgrade-module configuration, paired with Module Type. This must match the physical module definition. A core must allow that definition identity or configuration name before the attached module can contribute.",
  "upgrade-unique": "Friendly module configuration name. Runtime falls back to SubtypeId if omitted. Core allowances can refer to this UniqueName, especially for modules using a non-default TypeId; it is separate from the physical block identity.",
  "upgrade-mod-stat": "Runtime stat changed by this module on the current main core. Choose a recognized grid, speed, or defense stat. Unknown names are accepted by the framework but do nothing. Only allowed, functional, enabled modules attached to the main core contribute.",
  "upgrade-mod-value": "Amount applied to the selected stat per contributing module. Additive adds Value; Multiplicative multiplies by Value (1 is neutral, 1.2 increases by 20%, 0.8 decreases by 20%). Damage multipliers work in the opposite benefit direction: lower means less incoming damage.",
  "upgrade-mod-type": "Additive computes current stat + Value; Multiplicative computes current stat × Value. For example, a baseline 2 with additive 0.5 becomes 2.5; multiplicative 0.5 becomes 1. Choose Value in the units of the target stat when adding.",
  "upgrade-limit-name": "Target core Block Limit Name, not a reusable block-group name. Must match a named block limit on the receiving core. Suggestions list names currently in this editor. The modifier changes that limit's effective MaxCount.",
  "upgrade-limit-value": "Change to the targeted limit's weighted MaxCount per contributing module. Additive 2 adds two units of capacity; Multiplicative 1.5 scales capacity by 50%. This targets the named limit, rather than physical MaxBlocks or an individual block's CountWeight.",
  "upgrade-limit-type": "How Value changes the named limit's MaxCount: Additive adds the amount; Multiplicative scales by it. Additive is the default for block-limit modifiers. Multiplicative 1 is neutral; 0 scales the cap to zero.",
  "upgrade-cap-stat": "Group capacity changed by this module: MaxBlocks is physical block count, MaxMass is dry mass in kilograms, and MaxPCU is definition-based PCU. These are separate from named weighted block limits. Effects apply through allowed modules attached to the main core.",
  "upgrade-cap-value": "Capacity change per contributing module. With Additive, units are blocks, kilograms, or PCU according to Stat. With Multiplicative, Value is a factor such as 1.25 for 25% more capacity. This modifies the effective cap used by capacity checks.",
  "upgrade-cap-type": "Apply Value to the selected capacity by addition or multiplication. Additive is the default. For example, MaxBlocks 100 plus additive 20 becomes 120; multiplicative 1.5 becomes 150. Choose the value's units to match the selected operation."
};

const GRID_HELP = {
  AssemblerSpeed: "Assembler production-speed multiplier.",
  DrillHarvestMultiplier: "Drill material-harvest multiplier.",
  GyroEfficiency: "Gyro power efficiency. Consumption is divided by this value, so 2 halves power demand. Use a positive value when enabled; zero is not a valid efficiency divisor.",
  GyroForce: "Gyro strength/torque multiplier.",
  PowerProducersOutput: "Reactor power-output multiplier. Active power overclock multiplies the resulting reactor output again.",
  RefineEfficiency: "Refinery material yield/effectiveness multiplier, applied after block-definition and attached-upgrade effects.",
  RefineSpeed: "Refinery productivity/speed multiplier, applied after block-definition and attached-upgrade effects.",
  ThrusterEfficiency: "Thruster efficiency. Power/fuel consumption is divided by this value, so 2 halves consumption. Use a positive value when enabled; zero is not a valid efficiency divisor.",
  ThrusterForce: "Thruster force multiplier, affecting available acceleration."
};

const SPEED_HELP = {
  MaxSpeed: "Base top-speed multiplier of world MaxPossibleSpeedMetersPerSecond. For example, 0.3 with a 300 m/s world baseline gives 90 m/s. This is a ratio, not a speed in m/s.",
  MaxAngularVelocity: "Maximum angular velocity in radians per second. Values <= 0 disable this cap; default 0. For reference, approximately 6.283 rad/s is one complete rotation per second.",
  MaxBoost: "Boost top-speed multiplier of world MaxPossibleSpeedMetersPerSecond. For example, 0.5 with a 300 m/s baseline gives 150 m/s. Used when SpeedBoostEnabled permits an active boost; it is not an additive speed bonus.",
  BoostDuration: "Boost duration in seconds. Also used for post-boost speed ramp timing in Normal speed-limit mode. SpeedBoostEnabled must be enabled to use the boost ability.",
  BoostCoolDown: "Boost recovery time in seconds. Separate from boost Duration and from active-defense/power-overclock cooldowns. Controls when the boost ability becomes available again.",
  MinimumFrictionSpeedAbsolute: "Legacy linear-friction start speed in metres per second. Used when the world's FrictionSpeedValueMode is Absolute and no explicit curve replaces it. Pair with MaximumFrictionSpeedAbsolute and MaximumFrictionDeceleration.",
  MaximumFrictionSpeedAbsolute: "Legacy linear-friction maximum-deceleration speed in metres per second. Used in world Absolute mode without an explicit curve. Deceleration rises from the minimum friction speed toward MaximumFrictionDeceleration at this speed.",
  MinimumFrictionSpeedModifier: "Legacy friction start speed as a multiplier of world maximum speed. Used in world Modifier mode without an explicit curve. For example, 0.3 with a 300 m/s baseline starts friction at 90 m/s.",
  MaximumFrictionSpeedModifier: "Legacy friction maximum-deceleration speed as a multiplier of world maximum speed. Used in world Modifier mode without an explicit curve. For example, 0.8 with a 300 m/s baseline corresponds to 240 m/s.",
  MaximumFrictionDeceleration: "Maximum legacy linear-friction deceleration in m/s². Used to synthesize friction when no FrictionCurve segments are configured. Explicit segments specify their own deceleration instead.",
  CruiseFrictionMultiplier: "Friction multiplier while above friction speed and not accelerating beyond CruiseAccelerationThreshold. Default 1; values below 1 reduce coasting decay and values above 1 increase it. Atmospheric friction has a separate override.",
  CruiseAccelerationThreshold: "Acceleration threshold in m/s² used to detect cruising for CruiseFrictionMultiplier. Default 0.05. Atmospheric friction has its own threshold, used when that profile is active.",
  AirDensityThreshold: "Minimum local air-density threshold for the atmospheric friction override, on the game's density scale. Default 0.05. Enabled must also be true; below the threshold, the normal friction profile applies."
};

const SEGMENT_HELP = {
  StartSpeed: "Beginning of this friction segment. Units follow world FrictionSpeedValueMode: m/s in Absolute mode, or a world maximum-speed ratio in Modifier mode. Segments define the curve in speed order; deceleration interpolates between their endpoints.",
  EndSpeed: "End of this friction segment, in m/s for world Absolute mode or a world maximum-speed ratio for Modifier mode. Keep it above StartSpeed. Above the final segment, that segment's EndDeceleration continues to apply.",
  StartDeceleration: "Friction deceleration at this segment's StartSpeed in m/s², regardless of speed-value mode. Runtime interpolates toward EndDeceleration as speed approaches EndSpeed. Use non-negative values.",
  EndDeceleration: "Friction deceleration at this segment's EndSpeed in m/s². Interpolated from StartDeceleration within the segment. The last segment's ending deceleration continues above its EndSpeed. Use non-negative values."
};

const STATIC_HELP = {
  groupsXmlFile: "Choose ShipCoreConfig_Groups.xml containing reusable block classifications. Then use Load Uploaded XML. Uploads are read locally; they do not update the original files. Use Open Mod/Data Folder and Update Open Folder for in-place editing.",
  manifestXmlFile: "Choose ShipCoreConfig_Manifest.xml to load shared groups, core/module paths, blacklist entries, and selection priorities. Include the referenced core/module files in the import so their full profiles can be edited.",
  noCoreXmlFile: "Choose ShipCoreConfig_No_Core.xml, the default ShipCore profile for groups without an active core. It uses the same settings as regular profiles but has no physical core block and always outputs at the configuration root.",
  coreXmlFiles: "Select one or more ShipCore or UpgradeModule XML configuration files referenced by the manifest. Each recognized profile becomes editable after Load Uploaded XML. Unknown XML tags are ignored rather than preserved as editable settings.",
  folderUpload: "Read an entire mod or Data folder for import. Load Uploaded XML loads recognized configs and keeps other uploaded files for Download all files. This picker does not grant write access to the original folder; use Open Mod/Data Folder for updates in place.",
  zipUpload: "Choose a ZIP containing your mod/Data configuration. Load Uploaded XML extracts recognized profiles and retains passthrough files for the combined ZIP download. Import reads the archive locally and does not modify the original ZIP.",
  upgradeModuleSbcFiles: "Import upgrade-module SBC definitions alongside XML configs. UpgradeModule config roots are parsed as profiles; block definitions supply module-definition information. Select the files first, then use Load Uploaded XML.",
  legacyModConfigFile: "Choose an older ModConfig XML with DefaultGridClass and GridClasses. Migrate Legacy ModConfig converts its supported settings into No Core, core profiles, and reusable groups. Review generated XML and validation before saving the migrated result.",
  legacyLimitMergeMode: "Strict merges legacy limit classifications only when TypeId, SubtypeId, and CountWeight match. Block types only ignores CountWeight when merging, which can consolidate groups with different costs. Review weighted limits after using that less strict migration mode.",
  selectedGroup: "Choose which reusable block group to edit. Groups define block matching and weights; individual core limits decide which groups to include or exclude. Switching the selection keeps your current edits.",
  selectedManifestGroup: "Choose the shared manifest core-count group to edit. Its MaxCount is shared by assigned core profiles and is independent of reusable block-group limits. Switching the selection keeps your edits.",
  selectedCore: "Choose the single core profile to edit across Overview, Block limits, Performance, Abilities, and Docking & shared caps. Entry 0 is No Core, the fallback profile for groups without an active configured core. Other entries describe physical core types. Changes update XML previews and the local browser autosave draft.",
  selectedUpgradeModule: "Choose the upgrade-module configuration to edit. Modules can modify stats, named block limits, and group capacity when allowed and attached to the current main core. Switching profiles keeps the edits already made."
};

function defenseHelp(field, active) {
  const profile = active ? "Active defense" : "Passive defense";
  if (field === "Duration" || field === "Cooldown") {
    return active
      ? `${field === "Duration" ? "Active-defense duration" : "Recovery time after active defense"} in seconds. EnableActiveDefense must be enabled. Live timers use this base core value; ActiveDefenseDuration/ActiveDefenseCooldown upgrade stats currently change the modifier cache but not those live timers.`
      : `${field} is present in the passive profile's schema but is mainly relevant to active defense. Set the active profile's Duration and Cooldown to configure that ability's timers; this passive field does not enable an ability.`;
  }
  if (!["Bullet", "PostShield", "Rocket", "Explosion", "Environment", "Energy", "Kinetic"].includes(field)) return "";
  return `${profile} incoming ${field === "PostShield" ? "post-shield" : field.toLowerCase()} damage multiplier. 1 is neutral; 0.5 halves incoming damage; values above 1 increase it. ${active ? "Replaces the passive profile while the enabled active-defense ability runs." : "Used outside active-defense periods."}${field === "Bullet" ? " Current caveat: live bullet routing uses other damage channels, so bullet-specific values do not currently change gameplay as the name suggests." : ""}`;
}

export function getFieldHelp({ id, dataset = {}, value } = {}) {
  const action = dataset.action;
  const field = dataset.field || dataset.m;
  if (action === "core-modifier-grid") {
    return GRID_HELP[field] ? `${GRID_HELP[field]} Baseline multiplier: 1 is neutral, 2 doubles the stat, and -1 leaves the game's value unchanged. Allowed upgrade modules can further modify the baseline.` : "";
  }
  if (action === "core-modifier-speed") return SPEED_HELP[field] || "";
  if (action === "core-modifier-passive-defense" || action === "core-modifier-active-defense")
    return defenseHelp(field, action === "core-modifier-active-defense");
  if (action === "core-atmospheric-friction-field")
    return SPEED_HELP[field] ? `Atmospheric override: ${SPEED_HELP[field]} Used only when the atmospheric profile is enabled and local air density exceeds its threshold.` : "";
  if (action === "core-friction-segment-field" || action === "core-atmospheric-friction-segment-field")
    return SEGMENT_HELP[field] ? `${action.includes("atmospheric") ? "Atmospheric override. " : ""}${SEGMENT_HELP[field]}` : "";
  if (action === "upgrade-mod-stat") {
    const detail = GRID_HELP[value] || SPEED_HELP[value]
      || (/^(Passive|Active).+Damage$/.test(value || "") ? defenseHelp(value.replace(/^(Passive|Active)/, "").replace(/Damage$/, ""), value.startsWith("Active")) : "")
      || (value === "ActiveDefenseDuration" ? defenseHelp("Duration", true) : "")
      || (value === "ActiveDefenseCooldown" ? defenseHelp("Cooldown", true) : "")
      || (value?.startsWith("Atmospheric") ? SPEED_HELP[value.slice("Atmospheric".length)] : "");
    return `${FIELD_HELP[action]}${detail ? ` Selected stat: ${detail}` : ""}`;
  }
  return FIELD_HELP[action] || STATIC_HELP[id] || "";
}

export function installFieldHelp(doc) {
  const fields = "input, select, textarea";
  const tooltip = doc.createElement("div");
  tooltip.className = "field-tooltip";
  tooltip.setAttribute("role", "tooltip");
  tooltip.hidden = true;
  doc.body.append(tooltip);
  let anchor = null;
  let hovered = null;
  let focused = null;
  let dismissed = null;
  let hoverTimer;

  function describe(field) {
    const help = getFieldHelp(field);
    if (!help) return;
    field.setAttribute("aria-description", help);
    // Replace the few old native titles to avoid a second tooltip over this one.
    field.removeAttribute("title");
    // Native labels.length can scan the whole document. Most fields wrap in a label.
    if (!field.hasAttribute("aria-label") && field.closest("label")?.control !== field && !field.labels?.length)
      field.setAttribute("aria-label", field.placeholder || field.dataset.action || field.id);
  }

  function describeTree(node) {
    if (node.nodeType !== 1) return;
    if (node.matches(fields)) describe(node);
    node.querySelectorAll(fields).forEach(describe);
  }

  function targetField(target) {
    if (!target?.closest) return null;
    const field = target.closest(fields) || target.closest("label")?.querySelector(fields);
    return field?.hasAttribute("aria-description") ? field : null;
  }

  function show() {
    anchor = hovered || focused;
    if (!anchor?.isConnected || anchor === dismissed) {
      tooltip.hidden = true;
      return;
    }
    tooltip.textContent = anchor.getAttribute("aria-description");
    tooltip.hidden = false;
    const rect = (anchor.closest("label") || anchor).getBoundingClientRect();
    const width = doc.documentElement.clientWidth;
    const height = doc.documentElement.clientHeight;
    tooltip.style.left = `${Math.max(8, Math.min(rect.left, width - tooltip.offsetWidth - 8))}px`;
    const below = rect.bottom + 6;
    tooltip.style.top = `${Math.max(8, below + tooltip.offsetHeight <= height - 8 ? below : rect.top - tooltip.offsetHeight - 6)}px`;
  }

  doc.querySelectorAll(fields).forEach(describe);
  // The editor replaces entire panels and individual checklists independently.
  // Observe inserted fields once, without coupling every render path to help UI.
  new MutationObserver((records) => {
    for (const record of records) record.addedNodes.forEach(describeTree);
    if (anchor && !anchor.isConnected) {
      hovered = focused = anchor = null;
      tooltip.hidden = true;
    }
  }).observe(doc.body, { childList: true, subtree: true });

  doc.addEventListener("pointerover", (event) => {
    if (tooltip.contains(event.target)) {
      clearTimeout(hoverTimer);
      return;
    }
    const field = targetField(event.target);
    if (!field) return;
    clearTimeout(hoverTimer);
    hovered = field;
    if (hovered !== dismissed) dismissed = null;
    show();
  });
  doc.addEventListener("pointerout", (event) => {
    if (tooltip.contains(event.relatedTarget)) return;
    const next = targetField(event.relatedTarget);
    if (next === hovered) return;
    clearTimeout(hoverTimer);
    hoverTimer = setTimeout(() => {
      hovered = next;
      if (hovered !== dismissed && focused !== dismissed) dismissed = null;
      show();
    }, 150);
  });
  doc.addEventListener("focusin", (event) => {
    clearTimeout(hoverTimer);
    hovered = null;
    focused = targetField(event.target);
    dismissed = null;
    show();
  });
  doc.addEventListener("focusout", (event) => {
    focused = targetField(event.relatedTarget);
    show();
  });
  doc.addEventListener("change", (event) => {
    if (event.target.matches(fields)) describe(event.target);
    if (event.target === anchor) show();
  });
  doc.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      dismissed = anchor;
      tooltip.hidden = true;
    }
  });
  doc.addEventListener("scroll", (event) => {
    if (tooltip.contains(event.target)) return;
    hovered = null;
    show();
  }, true);
  doc.defaultView.addEventListener("resize", show);
}
