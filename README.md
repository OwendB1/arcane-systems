# Ship Core System

Ship Core System is a Space Engineers project centered on core-driven ship rules. Instead of relying only on vanilla block limits or Torch-side plugins, it lets a grid group inherit limits, modifiers, speed behavior, defense tuning, placement rules, and upgrade-module effects from a selected ship core or no-core profile.

This repository contains:

- `ShipCoreFramework/`
  - Main framework mod package.
- `ArcaneShipCores/`
  - Additional core content built on top of the framework.
- `docs/`
  - Static XML configurator for authoring and updating config files.

Developer guidance for the runtime client/server boundary is in
[`docs/authority-layout.md`](docs/authority-layout.md).

## Feature overview

- Per-core and no-core profiles.
- Placement caps by player, faction, faction size, and manifest group.
- Shared `BlockGroup` definitions for reusable block-limit buckets.
- Weighted block limits with per-limit punishment types.
- Capacity gates for blocks, PCU, mass, beacon requirement, mobility type, and faction size.
- Speed enforcement with normal hard-cap mode or friction soft-cap mode.
- Boost, active-defense, and reactor power-overclock abilities.
- Upgrade modules that modify grid stats, speed values, defense values, and block-limit counts.
- No-fly zones with either full force-off or limit-specific punishment.
- Connector-aware limit behavior:
  - `CrossConnectorPunishment` imports blocks from connected no-core grids.
  - Manifest blacklist imports lower-ranked core-group blocks into the winning core's limits.
- Critical limits that stay exempt from connector imports and minimum-block total limited-block shutoff.
- Minimum-block limited-block gate with periodic recheck.
- Live Core HUD for piloted or aimed friendly grids, with a persistent configurable toggle key.
- External mod API.

## Config file map

The framework reads configuration from several XML entry points.

| File | Shape | Purpose |
| --- | --- | --- |
| `ShipCoreConfig_World.xml` | `<ModConfig>` | World settings, ignored factions, no-fly zones, selected no-core profile, world max speed. |
| `Data/ShipCoreConfig_Groups.xml` | XML list of `BlockGroup` entries | Reusable block classifications for block limits. |
| `Data/ShipCoreConfig_Manifest.xml` | `<CoreManifest>` | Lists core files, upgrade-module files, manifest groups, connector blacklist entries. |
| `Data/ShipCoreConfig_No_Core.xml` | `<ShipCore>` | Required no-core profile supplied by a content pack. |
| Per-core XML files from manifest | `<ShipCore>` | Actual ship-core definitions. |
| Per-upgrade-module XML files from manifest | `<UpgradeModule>` | Upgrade-module definitions. |

Load behavior:

- `SelectedNoCoreUniqueName` picks one loaded no-core profile by `UniqueName`.
- SCF has no built-in no-core fallback. If the selected profile is missing or invalid, runtime
  initialization stays disabled while admin commands remain available to select a profile for the
  next world load.
- Worlds that still select the retired `DEFAULT-NO-CORE-ALL-GRID-TYPES` profile automatically
  migrate when exactly one content-pack profile is loaded. If several are loaded, use
  `/core select <name>` to choose one, then reload the world.
- The server synchronizes authoritative world settings with a revision.
- Clients retry initial synchronization every five seconds until it succeeds. Configuration changes
  and `/core reloadconfig` broadcast a new revision immediately.
- Manifest groups are global across all loaded manifest files.
- Duplicate core names, subtype IDs, manifest group names, and upgrade module `TypeId`/`SubtypeId` pairs are rejected during load.

## Conventions and behavior notes

- Most optional caps use a negative value to mean "disabled". Use the notes below for field-specific behavior.
- `UniqueName` is the friendly/config name shown in commands and some UI.
- `SubtypeId` is the actual block definition subtype used for core identity and default `UpgradeModule` upgrade-module identity.
- Logical groups are mechanical groups. Connectors, rotors, pistons, and similar subgrids can end up in one group depending on the game link graph.
- Many punishment gates do not remove the core. They shut off modifiers, speed, or limited blocks instead.
- `MinBlocks` is no longer only a one-time startup check. It also drives a limited-block punishment gate:
  - falling below minimum immediately forces non-critical limited blocks off
  - once the group reaches minimum again, the limited-block gate clears
  - the group is still periodically rechecked so stale state is corrected
- Connector limit punishment uses the active higher-ranked core's limits.
  - `CrossConnectorPunishment` only imports blocks from directly connected no-core groups into marked, non-critical limits.
  - `CrossConnectorPunishmentWhitelist` disables only that no-core import behavior for listed core `SubtypeId` values.
  - Manifest blacklist compares connected core groups by `CoreSelectionPriority`, then block count, and imports matching blocks from the lower-ranked blacklisted group into every non-critical limit of the winning group.
  - Local blocks retain their configured punishment. Imported connector blocks over remaining capacity are shut off.
- Mechanical groups only allow one configured core subtype. Main-core selection is only backup/failover selection within that subtype and does not use `CoreSelectionPriority`.

## World config reference (`ShipCoreConfig_World.xml`)

Root tag: `<ModConfig>`

### World fields

| Tag | Type | Meaning | Notes |
| --- | --- | --- | --- |
| `IgnoreAiFactions` | `bool` | Ignores grids recognized as NPCs for core placement/enforcement. | Uses the game's NPC-spawned flag or an NPC identity in `BigOwners`, unless any big owner is a player. Does not replace `IgnoredFactionTags`; it is a separate skip path. |
| `IgnoredFactionTags` | `List<string>` | Faction tags to skip for enforcement and punishment. | Useful for admin, event, or NPC factions. |
| `SelectedNoCoreUniqueName` | `string` | Chooses which loaded no-core profile governs coreless grids. | Required; must match a loaded content-pack no-core `UniqueName`. |
| `DebugMode` | `bool` | Enables debug-oriented behavior. | Also changes some player-count checks to count identities more aggressively. |
| `CombatLogging` | `bool` | Enables combat logging behavior exposed by the framework. | Runtime toggle also exists through commands. |
| `CombatLoggingBroadcastRangeMeters` | `double` | Maximum distance from a combat-log event at which players receive its notification. | Default is `20000` (20 km). |
| `LOG_LEVEL` | `int` | Server/framework log verbosity. | `0` = essential only, `3` = debug; default is `2`. |
| `CLIENT_OUTPUT_LOG_LEVEL` | `int` | Client-side log verbosity. | `0` = essential only, `3` = debug; default is `2`. |
| `MaxPossibleSpeedMetersPerSecond` | `float` | World top-speed baseline in m/s. | Core `SpeedModifiers.MaxSpeed` and `MaxBoost` multiply against this value. |
| `SpeedRampDownPercentage` | `float` | Percentage used to derive linear speed-cap interpolation after core loss or `PunishSpeed` activation. | Accepts `0`–`100`; default `5`. Cached internally as 12 five-tick steps. Set to `0` to apply the target cap immediately. |
| `FrictionSpeedValueMode` | `Modifier` or `Absolute` | Chooses how friction min/max speed fields are interpreted. | In `Modifier` mode they scale against world max speed; in `Absolute` mode they are m/s values. |
| `BlockDirectionalPlacementOnSubgrids` | `bool` | Controls whether directional block limits treat subgrid placement as invalid. | Default is `true`. When `true`, a limited block with `AllowedDirections` cannot be placed on a different grid than the main core. When `false`, subgrids bypass the directional lock. |
| `CreativeCoreCountLimitsEnabled` | `bool` | Enforces faction and player core count caps in creative worlds. | Default is `true`. Admins can change it with `/core corecountlimits on\|off`. Survival worlds always enforce these caps. When disabled, players see a persistent top-right reminder. |
| `NoFlyZones` | `List<Zones>` | World no-fly zones. | See nested fields below. |

### No-fly zone fields

Each entry uses `<Zones>`.

| Tag | Type | Meaning | Notes |
| --- | --- | --- | --- |
| `ID` | `int` | Unique zone ID. | Used by admin commands and logging. |
| `Position` | `Vector3D` | Center of the zone. | Space Engineers XML vector format. |
| `Radius` | `double` | Radius in meters. | Punishment starts when a grid position is inside radius. |
| `AllowedCoresSubtype` | `List<string>` | Cores allowed inside the zone. | Runtime currently compares against the core `UniqueName`, despite the tag name saying subtype. |
| `OverideBlockLimitsForceShutOff` | `bool` | Forces all blocks off inside the zone. | Tag spelling is intentionally the current shipped spelling. If `false`, only limits with `PunishByNoFlyZone=true` are punished. |

## Manifest reference (`Data/ShipCoreConfig_Manifest.xml`)

Root tag: `<CoreManifest>`

### Manifest groups

`<ManifestGroups>` contains repeated `<Group>` entries.

| Tag | Type | Meaning | Notes |
| --- | --- | --- | --- |
| `Name` | `string` | Shared manifest group name. | Referenced by ship-core manifest entries. |
| `MaxCount` | `int` | Maximum simultaneous cores in this manifest group. | Must be non-negative. Group counts are global across loaded mods/configs. |

### No-core cross connector punishment whitelist

Repeated `<CrossConnectorPunishmentWhitelist>` entries under `<CoreManifest>` list core `SubtypeId` values. If the active core type is listed, `CrossConnectorPunishment` limits on that core do not pull blocks from connected no-core groups.

### Manifest ship-core entries

Repeated `<ShipCore>` entries under `<CoreManifest>`.

| Tag | Type | Meaning | Notes |
| --- | --- | --- | --- |
| `Filename` | `string` | Path to the `<ShipCore>` XML file in the mod. | Required. |
| `Group` | `List<string>` | Manifest group membership for this core file. | Repeat the tag once per group membership. |
| `CoreSelectionPriority` | `int` | Priority used only by manifest connector blacklist ranking. | Higher wins. Default `0`; equal priorities fall back to size. |
| `BlacklistedCoreSubtypeId` | `List<string>` | Core subtype IDs this core blacklists when connected by connector. | Repeat the tag once per blacklisted subtype. |

Blacklist behavior:

- Applies across all core groups in the same transitive connector network.
- Connector traversal uses actual connected connector pairs, including trading-enabled connectors.
- The higher `CoreSelectionPriority` group is treated as the blacklisting side.
- If priorities match, the bigger group by block count is treated as the blacklisting side.
- The winning group's main core checks its blacklist against the losing group's main core `SubtypeId`.
- If matched, blocks from the losing group count against every matching non-critical limit on the winning group.
- Imported blocks beyond the winning group's remaining limit capacity are shut off; local overflow keeps its configured punishment type.
- If priority and block count both match, neither side outranks the other for blacklist punishment.

### Manifest upgrade-module entries

Repeated `<UpgradeModule>` entries under `<CoreManifest>`.

| Tag | Type | Meaning | Notes |
| --- | --- | --- | --- |
| `Filename` | `string` | Path to the `<UpgradeModule>` XML file in the mod. | Required. |

## Block-group reference (`Data/ShipCoreConfig_Groups.xml`)

This file is an XML list of `BlockGroup` entries. `BlockGroup` definitions let multiple limits reuse the same block classification list.

### `BlockGroup`

| Tag | Type | Meaning | Notes |
| --- | --- | --- | --- |
| `Name` | `string` | Reusable block-group name. | Referenced by `BlockLimit.BlockGroups`. |
| `BlockTypes` | `List<BlockType>` | Block matching rules inside the group. | A block limit can reference multiple named groups. |

### `BlockType`

| Tag | Type | Meaning | Notes |
| --- | --- | --- | --- |
| `TypeId` | `string` | Space Engineers block type ID. | Required for a useful match. |
| `SubtypeId` | `string` | Specific subtype ID. | Empty means any subtype under that type. `any` also works as wildcard. |
| `CountWeight` | `float` | Weight contributed by a matching block. | Use fractions or larger weights for weighted caps. |
| `PrimaryDirection` | `DirectionType` | Block-local axis used for directional locking. | Optional. Defaults to `Forward`; use values like `Up` for blocks whose practical facing is not their forward axis. |

## Ship-core and no-core reference (`Data/ShipCoreConfig_No_Core.xml` and per-core XML files)

Root tag: `<ShipCore>`

The no-core file and normal core files use the same schema. Manifest groups and connector blacklist membership are assigned in the manifest, not inside the core XML itself.

### Identity and placement fields

| Tag | Type | Meaning | Notes |
| --- | --- | --- | --- |
| `SubtypeId` | `string` | Block subtype ID for this core. | Required for normal cores. |
| `UniqueName` | `string` | Friendly/config name for this core. | Used by commands, selection, and some UI. |
| `MaxBackupCores` | `int` | Max backup cores allowed in the same logical group. | Intended as extra cores beyond the active main core. Use negative to disable. |
| `ForceBroadCast` | `bool` | Requires beacon-based broadcasting for the core. | Missing or broken beacon becomes a punishment gate. |
| `ForceBroadCastRange` | `float` | Beacon radius forced onto tracked beacons. | Used when `ForceBroadCast=true`. |
| `MobilityType` | `Static`, `Mobile`, `Both` | Allowed grid mobility type for the group. | Mismatch punishes both speed and modifiers. |
| `MaxBlocks` | `int` | Maximum allowed total blocks in the logical group. | New blocks are removed if they exceed this. At/over cap also triggers capacity punishment. Negative disables. |
| `MinBlocks` | `int` | Minimum blocks required to keep limited blocks enabled. | Falling below this immediately forces non-critical limited blocks off; reaching the minimum clears the gate. Negative disables. |
| `MaxMass` | `float` | Maximum allowed total group mass. | Uses full-definition dry block mass; inventory and construction progress are ignored. New blocks are removed if they exceed this. Negative disables. |
| `MaxPCU` | `int` | Maximum allowed total group PCU. | New blocks are removed if they exceed this. Negative disables. |
| `MaxPerFaction` | `int` | Fixed cap on how many groups of this core a faction may own. | `-1` disables fixed faction cap. |
| `FactionPlayersNeededPerCore` | `int` | Player-scaled faction cap. | `N` means one allowed core per `N` faction members. If combined with `MaxPerFaction`, runtime uses the lower of the two caps. |
| `MinFactionRank` | `None`, `Member`, `Leader`, `Founder` | Minimum grid majority-owner faction rank required to place this core. | Optional, defaults to `None`. Invalid placement is rejected and refunded before the core activates or counts against faction limits. |
| `MaxPerPlayer` | `int` | Cap on how many groups of this core a single player may own. | Negative disables. |
| `MinPlayers` | `int` | Minimum faction member count required for this core. | If set and owner has no faction, placement is rejected. Negative disables. |
| `MaxPlayers` | `int` | Maximum faction member count allowed for this core. | If faction is larger than this, placement/punishment gates fail. Negative disables. |

### Upgrade-module allowance field

Repeated `<AllowedUpgradeModules>` entries inside `<ShipCore>`.

| Tag | Type | Meaning | Notes |
| --- | --- | --- | --- |
| `TypeId` | `string` | Allowed upgrade-module block type. | Optional. If omitted with `SubtypeId`, defaults to `UpgradeModule` for legacy entries. |
| `SubtypeId` | `string` | Allowed upgrade-module subtype. | Legacy/default path: matches `UpgradeModule/<SubtypeId>`. If set, this identity is checked before `UniqueName`. |
| `UniqueName` | `string` | Allowed upgrade-module config name. | Use this for upgrade modules whose config defines a non-default `TypeId`. |
| `MaxCount` | `int` | Maximum attached modules for that allowance on this main core. | Exceeding modules are removed as invalid. |

Upgrade-module application rules:

- Module definition or `UniqueName` must be listed here.
- Module must be attached to the current main core.
- Module must be functional and enabled.
- Only modules attached to the current main core contribute effects.

### Grid modifier fields (`<Modifiers>`)

These are multiplicative stat baselines unless modified by upgrade modules.

| Tag | Meaning |
| --- | --- |
| `AssemblerSpeed` | Assembler speed multiplier. |
| `DrillHarvestMultiplier` | Drill harvest multiplier. |
| `GyroEfficiency` | Gyro power-efficiency multiplier. |
| `GyroForce` | Gyro force multiplier. |
| `PowerProducersOutput` | Power output multiplier. |
| `RefineEfficiency` | Refinery material-yield/effectiveness multiplier. Applied after block definition and attached upgrade modules. |
| `RefineSpeed` | Refinery productivity/speed multiplier. Applied after block definition and attached upgrade modules. |
| `ThrusterEfficiency` | Thruster efficiency multiplier. |
| `ThrusterForce` | Thruster force multiplier. |

### Passive defense fields (`<PassiveDefenseModifiers>`)

All values are multipliers. `1` is neutral, below `1` reduces incoming damage, above `1` increases it.

| Tag | Meaning |
| --- | --- |
| `Bullet` | Bullet damage multiplier. |
| `PostShield` | Post-shield damage multiplier. |
| `Rocket` | Rocket damage multiplier. |
| `Explosion` | Explosion damage multiplier. |
| `Environment` | Environmental damage multiplier. |
| `Energy` | Energy damage multiplier. |
| `Kinetic` | Kinetic damage multiplier. |
| `Duration` | Present in schema but mainly relevant for active defense. |
| `Cooldown` | Present in schema but mainly relevant for active defense. |

### Speed fields

| Tag | Type | Meaning | Notes |
| --- | --- | --- | --- |
| `SpeedBoostEnabled` | `bool` | Enables boost ability for the core. | Boost top speed uses `SpeedModifiers.MaxBoost`. |
| `SpeedLimitType` | `Normal` or `Friction` | Selects hard-cap or friction soft-cap speed enforcement. | `Normal` uses direct cap with post-boost ramp down. `Friction` applies deceleration between configured friction speeds. |

### Speed modifier fields (`<SpeedModifiers>`)

| Tag | Meaning | Notes |
| --- | --- | --- |
| `MaxSpeed` | Base speed multiplier. | Multiplies against world `MaxPossibleSpeedMetersPerSecond`. |
| `MaxAngularVelocity` | Maximum angular velocity in radians per second. | Values less than or equal to `0` disable the angular velocity cap. Default `0`. |
| `MaxBoost` | Boost speed multiplier. | Also multiplies against world max speed. |
| `BoostDuration` | Boost duration in seconds. | Also used for post-boost ramp timing in normal speed mode. |
| `BoostCoolDown` | Boost cooldown in seconds. | |
| `MinimumFrictionSpeedAbsolute` | Friction start speed in m/s. | Used only when world `FrictionSpeedValueMode=Absolute`. |
| `MaximumFrictionSpeedAbsolute` | Friction max speed in m/s. | Used only when world `FrictionSpeedValueMode=Absolute`. |
| `MinimumFrictionSpeedModifier` | Friction start speed as world-speed multiplier. | Used only when world `FrictionSpeedValueMode=Modifier`. |
| `MaximumFrictionSpeedModifier` | Friction max speed as world-speed multiplier. | Used only when world `FrictionSpeedValueMode=Modifier`. |
| `MaximumFrictionDeceleration` | Max friction deceleration in m/s². | Used by legacy linear friction when no `FrictionCurve` is configured. |
| `CruiseFrictionMultiplier` | Multiplier applied to friction while the grid is above friction speed but not accelerating beyond the threshold. | Default `1`. Values below `1` make coasting decay slower. |
| `CruiseAccelerationThreshold` | Acceleration threshold in m/s² for cruise friction detection. | Default `0.05`. |
| `FrictionCurve` | Optional ordered list of friction curve `Segment` entries. | If missing, the old linear curve is synthesized from the min/max friction fields and `MaximumFrictionDeceleration`. Segment speeds use the world `FrictionSpeedValueMode`. |
| `AtmosphericFriction` | Optional atmosphere-only override profile. | When present, `Enabled=true`, and local air density is above `AirDensityThreshold`, its curve/cruise fields override normal friction. Outside atmosphere or when disabled, normal friction is used. |

`FrictionCurve` segment fields:

| Tag | Meaning |
| --- | --- |
| `StartSpeed` | Segment start speed. Interpreted as m/s in `Absolute` mode or as a world max-speed multiplier in `Modifier` mode. |
| `EndSpeed` | Segment end speed. Interpreted the same way as `StartSpeed`. Above the last segment, the last segment's `EndDeceleration` continues. |
| `StartDeceleration` | Deceleration in m/s² at `StartSpeed`. |
| `EndDeceleration` | Deceleration in m/s² at `EndSpeed`. |

Example absolute-speed curve with 20 m/s² from 100-200 m/s and 60 m/s² from 200 m/s upward:

```xml
<SpeedModifiers>
  <MaxSpeed>1</MaxSpeed>
  <MaxAngularVelocity>1.5</MaxAngularVelocity>
  <MaxBoost>1</MaxBoost>
  <BoostDuration>10</BoostDuration>
  <BoostCoolDown>60</BoostCoolDown>
  <MinimumFrictionSpeedAbsolute>100</MinimumFrictionSpeedAbsolute>
  <MaximumFrictionSpeedAbsolute>300</MaximumFrictionSpeedAbsolute>
  <MinimumFrictionSpeedModifier>0.3</MinimumFrictionSpeedModifier>
  <MaximumFrictionSpeedModifier>1</MaximumFrictionSpeedModifier>
  <MaximumFrictionDeceleration>1</MaximumFrictionDeceleration>
  <CruiseFrictionMultiplier>0.25</CruiseFrictionMultiplier>
  <CruiseAccelerationThreshold>0.05</CruiseAccelerationThreshold>
  <FrictionCurve>
    <Segment>
      <StartSpeed>100</StartSpeed>
      <EndSpeed>200</EndSpeed>
      <StartDeceleration>20</StartDeceleration>
      <EndDeceleration>20</EndDeceleration>
    </Segment>
    <Segment>
      <StartSpeed>200</StartSpeed>
      <EndSpeed>300</EndSpeed>
      <StartDeceleration>60</StartDeceleration>
      <EndDeceleration>60</EndDeceleration>
    </Segment>
  </FrictionCurve>
  <AtmosphericFriction>
    <Enabled>true</Enabled>
    <CruiseFrictionMultiplier>1</CruiseFrictionMultiplier>
    <CruiseAccelerationThreshold>0.05</CruiseAccelerationThreshold>
    <AirDensityThreshold>0.05</AirDensityThreshold>
  </AtmosphericFriction>
</SpeedModifiers>
```

### Active defense fields

| Tag | Type | Meaning | Notes |
| --- | --- | --- | --- |
| `EnableActiveDefenseModifiers` | `bool` | Enables active-defense mode for the core. | When active, the runtime uses `ActiveDefenseModifiers`. |
| `ActiveDefenseModifiers` | `GridDefenseModifiers` | Defense multipliers while active defense is running. | Uses the same nested tags as passive defense, including `Duration` and `Cooldown`. |

### Power overclock fields

| Tag | Type | Meaning | Notes |
| --- | --- | --- | --- |
| `PowerOverclockEnabled` | `bool` | Enables the core hotbar action. | Disabled by default. |
| `PowerOverclockMultiplier` | `float` | Multiplies reactor output while active. | Applied after base and upgrade-module power modifiers. |
| `PowerOverclockDuration` | `float` | Active duration in seconds. | Default `10`. |
| `PowerOverclockCooldown` | `float` | Cooldown after expiry in seconds. | Default `60`. |
| `PowerOverclockDamagePerSecond` | `float` | Integrity damage dealt to each affected reactor per active second. | `0` disables wear. |

### Block-limit fields (`<BlockLimits>`)

Each entry uses `<BlockLimit>`.

| Tag | Type | Meaning | Notes |
| --- | --- | --- | --- |
| `Name` | `string` | Limit name. | Referenced by upgrade-module `BlockLimitModifiers`. |
| `BlockGroups` | `BlockGroupReference[]` | Names of `BlockGroup` definitions included in this limit. | Optional `Directions` attribute accepts comma-separated direction names or enum integers and overrides this limit's `AllowedDirections` for blocks matched through that group. |
| `ExcludedBlockGroups` | `string[]` | Names of `BlockGroup` definitions subtracted from this limit. | Exclusion wins when a block matches both an included and excluded group. |
| `MaxCount` | `float` | Maximum allowed total weight for this limit. | Weight comes from matched `BlockType.CountWeight`. |
| `MaxCountPerDirection` | `float` | Maximum allowed weight facing any one of the six core-relative directions. | Optional; negative values disable it. Uses each matched `BlockType.PrimaryDirection`. Connector-imported weight remains aggregate-only. |
| `DirectionBudgets` | `DirectionBudget[]` | Per-direction weighted cap overrides (`Direction`, `MaxCount` attributes). | Overrides plus inherited caps for enabled directions must total no more than `MaxCount`; invalid allocation rejects config loading. |
| `LimitVisibility` | `Always`, `NearLimit`, or `Hidden` | Controls this limit's placement-preview and Core Status HUD elements. | Defaults to `Always`. `NearLimit` uses the 80% threshold; `Hidden` affects presentation only, never enforcement. |
| `CrossConnectorPunishment` | `bool` | Pulls blocks from connected no-core groups into this limit's bucket. | Only affects non-critical limits on this core. Manifest blacklist imports use all non-critical limits regardless of this flag. |
| `PunishByNoFlyZone` | `bool` | Applies this limit's punishment inside no-fly zones. | Only used when the zone itself is not forcing everything off. |
| `IsCriticalLimit` | `bool` | Exempts this limit from connector imports and total limited-block shutoff gates. | Minimum-block shutoff and both connector import paths skip this limit. Normal local overflow, directional checks, and no-fly-zone punishment still work normally. |
| `IgnoredByNpc` | `bool` | Disables this limit while the active grid group is recognized as NPC. | Defaults to `false`. Counts remain tracked so enforcement becomes active when the group no longer qualifies as NPC, and projected merges involving a non-NPC group still evaluate the limit. |
| `PunishmentType` | `ShutOff`, `Damage`, `Delete`, `Explode`, `DeleteWithoutRefund` | Punishment for blocks in this limit when the limit is violated. | `Delete` refunds built components; `DeleteWithoutRefund` does not. Limited-block gate punishment always uses `ShutOff`, regardless of this setting. |
| `AllowedDirections` | `List<DirectionType>` | Directional lock for this limit. | If set, mismatched blocks are punished even if count is under cap. Directions are relative to the main core and compare the matched `BlockType.PrimaryDirection` axis. Subgrid behavior is controlled by world setting `BlockDirectionalPlacementOnSubgrids`. |

Reusable groups can be combined as set subtraction without changing their definitions. For example,
the following limit counts every block in `AllHydrogenEngines` except blocks classified by
`SpecialHydrogenEngine`:

```xml
<BlockLimits>
  <Name>General Hydrogen Engines</Name>
  <BlockGroups>AllHydrogenEngines</BlockGroups>
  <ExcludedBlockGroups>SpecialHydrogenEngine</ExcludedBlockGroups>
  <MaxCount>10</MaxCount>
</BlockLimits>
```

`ExcludedBlockGroups` only determines membership. Its `CountWeight` and `PrimaryDirection` values are
not subtracted; an excluded block contributes nothing to this limit. Existing limits without exclusions
keep their current behavior.

NPC-only loadouts can share a player core profile by opting individual limits out while the group remains
recognized as NPC:

```xml
<BlockLimits>
  <Name>Restricted NPC Weapons</Name>
  <BlockGroups>RestrictedNpcWeapons</BlockGroups>
  <MaxCount>0</MaxCount>
  <IgnoredByNpc>true</IgnoredByNpc>
  <PunishmentType>Delete</PunishmentType>
</BlockLimits>
```

A player in `BigOwners`, including an offline player, makes a grid non-NPC even when the game's
`IsNpcSpawnedGrid` flag is set or other big owners are NPCs. Otherwise, a grid qualifies as NPC when
that flag is set or any nonzero identity in `BigOwners` is an NPC. `SmallOwners` do not affect this
check. This also recognizes NPC-owned MES grids without requiring a MES API integration. SCF does
not change the game's flag. A mechanical group qualifies if any of its grids qualifies.

The limit becomes active when no grid in the group qualifies as NPC. A projected merge is exempt only
when every participating group qualifies as NPC, preventing a non-NPC group from importing the restricted blocks.

Directional count caps share the normal limit's weighted points while keeping six independent buckets:

```xml
<BlockLimits>
  <Name>RCS Thrusters</Name>
  <BlockGroups>RCS</BlockGroups>
  <MaxCount>150</MaxCount>
  <MaxCountPerDirection>25</MaxCountPerDirection>
  <LimitVisibility>NearLimit</LimitVisibility>
</BlockLimits>
```

This permits up to 150 total RCS points, but no more than 25 points facing Forward, Backward, Up,
Down, Left, or Right. A placement reaching exactly 25 stays valid; the placement preview adds a
directional overflow line only when the proposed placement would exceed 25. Mechanical-subgrid
behavior follows `BlockDirectionalPlacementOnSubgrids`, matching `AllowedDirections`.

Different direction budgets can be assigned within the same limit:

```xml
<BlockLimits>
  <Name>Directional Weapons</Name>
  <BlockGroups>Weapons</BlockGroups>
  <MaxCount>100</MaxCount>
  <MaxCountPerDirection>10</MaxCountPerDirection>
  <DirectionBudgets>
    <DirectionBudget Direction="Forward" MaxCount="60" />
    <DirectionBudget Direction="Backward" MaxCount="20" />
  </DirectionBudgets>
  <AllowedDirections>Forward</AllowedDirections>
  <AllowedDirections>Backward</AllowedDirections>
  <AllowedDirections>Left</AllowedDirections>
  <AllowedDirections>Right</AllowedDirections>
</BlockLimits>
```

Forward gets 60 points, Backward 20, and Left/Right inherit 10 each. Validation enforces
`sum(DirectionBudgets) + enabled non-overridden direction count * MaxCountPerDirection <= MaxCount`.
A disabled fallback (negative/missing `MaxCountPerDirection`) contributes zero to the allocation;
unassigned directions then have no directional cap, but still consume the aggregate `MaxCount`.
This allocation check also applies to scalar-only directional limits. Existing configs whose six-way
allocation exceeds `MaxCount` must reduce their caps, restrict directions, or raise `MaxCount`.

Direction names are `Forward`, `Backward`, `Up`, `Down`, `Left`, and `Right`. Override budgets must be
finite and non-negative; zero allows no weighted usage. Duplicate directions, `Any` entries, missing
attributes, and invalid numbers reject config loading and editor downloads. With overrides configured,
the fallback must be `-1` or finite and non-negative. Empty/`Any` allowed directions enable all six.
Per-group `Directions` rules determine the union of enabled directions; each direction is counted once.
Explicit overrides retained for disabled directions still count in the allocation. Budgets never enable
forbidden directions, and all included block groups share each direction's budget. Upgrade modifiers
continue to affect aggregate capacity only. Connector-imported weight remains aggregate-only.

The XML editor shows per-direction inputs, inherited values, and the allocation total. Clear an input to
restore inheritance. Imported overrides survive duplication and XML export.

`LimitVisibility` applies only to HUD presentation. `Always` preserves the original behavior,
`NearLimit` shows numeric rows at 80% usage and direction rules when violated, and `Hidden` suppresses
the limit's HUD text, arrows, and violation outline. Chat commands and LCD reports remain complete.

Included groups can override the limit-wide directional lock:

```xml
<BlockLimits>
  <Name>Tools</Name>
  <BlockGroups Directions="Forward,Backward">Welders</BlockGroups>
  <BlockGroups>Grinders</BlockGroups>
  <AllowedDirections>Up</AllowedDirections>
  <MaxCount>10</MaxCount>
</BlockLimits>
```

Here, welders may face forward or backward, while grinders use the limit-wide `Up` direction.
`Directions="0,1"` is equivalent to `Directions="Forward,Backward"`. An omitted attribute falls
back to `AllowedDirections`; an explicit empty attribute or `Any` allows every direction.

### Direction values

`AllowedDirections` may use:

- `Forward` (`0`)
- `Backward` (`1`)
- `Up` (`2`)
- `Down` (`3`)
- `Left` (`4`)
- `Right` (`5`)
- `Any` (`6`)

## Upgrade-module reference (per-upgrade XML files)

Root tag: `<UpgradeModule>`

### Upgrade module fields

| Tag | Type | Meaning | Notes |
| --- | --- | --- | --- |
| `TypeId` | `string` | Upgrade-module block type ID. | Optional; defaults to `UpgradeModule`. Used with `SubtypeId` for early runtime tracking. |
| `SubtypeId` | `string` | Upgrade-module subtype ID. | Required. |
| `UniqueName` | `string` | Friendly/config name. | Falls back to `SubtypeId` if omitted. |
| `Modifiers` | `List<UpgradeStatModifier>` | Stat modifiers applied to the main core. | See recognized stats below. |
| `BlockLimitModifiers` | `List<BlockLimitModifier>` | Per-limit max-count modifiers. | References block-limit `Name`. |

### `UpgradeStatModifier`

| Tag | Type | Meaning | Notes |
| --- | --- | --- | --- |
| `Stat` | `string` | Runtime stat key. | Unknown names load but do nothing. |
| `Value` | `float` | Modifier value. | Interpreted by `ModifierType`. |
| `ModifierType` | `Additive` or `Multiplicative` | How `Value` is applied. | Default is multiplicative. |

### Recognized `Stat` values

Grid/system stats:

- `AssemblerSpeed`
- `DrillHarvestMultiplier`
- `GyroEfficiency`
- `GyroForce`
- `PowerProducersOutput`
- `RefineEfficiency`
- `RefineSpeed`
- `ThrusterEfficiency`
- `ThrusterForce`

Speed stats:

- `MaxSpeed`
- `MaxAngularVelocity`
- `MaxBoost`
- `BoostDuration`
- `BoostCoolDown`
- `MinimumFrictionSpeedAbsolute`
- `MaximumFrictionSpeedAbsolute`
- `MinimumFrictionSpeedModifier`
- `MaximumFrictionSpeedModifier`
- `MaximumFrictionDeceleration`
- `CruiseFrictionMultiplier`
- `CruiseAccelerationThreshold`
- `AtmosphericCruiseFrictionMultiplier`
- `AtmosphericCruiseAccelerationThreshold`
- `AtmosphericAirDensityThreshold`

Defense stats:

- `PassiveBulletDamage`
- `ActiveBulletDamage`
- `PassiveRocketDamage`
- `ActiveRocketDamage`
- `PassiveExplosionDamage`
- `ActiveExplosionDamage`
- `PassiveEnvironmentDamage`
- `ActiveEnvironmentDamage`
- `PassivePostShieldDamage`
- `ActivePostShieldDamage`
- `PassiveEnergyDamage`
- `ActiveEnergyDamage`
- `PassiveKineticDamage`
- `ActiveKineticDamage`
- `ActiveDefenseDuration`
- `ActiveDefenseCooldown`

### `BlockLimitModifier`

| Tag | Type | Meaning | Notes |
| --- | --- | --- | --- |
| `BlockLimitName` | `string` | Target block-limit `Name`. | Required. |
| `Value` | `float` | Modifier value. | Interpreted by `ModifierType`. |
| `ModifierType` | `Additive` or `Multiplicative` | How `Value` is applied to the limit max count. | Default is additive. |

### Current caveats

- `ActiveDefenseDuration` and `ActiveDefenseCooldown` are parsed and applied to the defense modifier cache, but live active-defense timers still use the base core values.
- `PassiveBulletDamage` and `ActiveBulletDamage` are parsed, but live bullet damage routing currently goes through other damage channels, so bullet-specific entries do not presently change gameplay the way the name suggests.
- Unknown `Stat` values are not rejected by validation. They load successfully and then do nothing at runtime.

## Commands

The framework exposes chat and admin commands under `/core`. Common ones include:

- `/core help`
- `/core info`
- `/core mass` (per-grid and per-block dry mass breakdown)
- `/core listcores`
- `/core listnocores`
- `/core select <NoCoreName|Subtype>`
- `/core coreinfo <UniqueName>`
- `/core reloadconfig`
- `/core listnfzs`
- `/core createnfz ...`
- `/core deletenfz <id>`
- `/core debug on|off`
- `/core combatlog on|off`
- `/core loglevel ...`
- `/core setworldspeed <m/s>`
- `/core ignoretags ...`
- `/core ignoreai`

Use `/core help` in-game for current command text.

## External API

The framework includes a mod API for other mods.

- Usage guide: [ShipCoreFramework/src/API_USAGE.md](ShipCoreFramework/src/API_USAGE.md)
- DTOs/constants: `ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/API/ApiData.cs`
- Sample client wrapper: `ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/API/SCF_ModAPIClient.cs`

Recommended integration path:

- copy `ApiData.cs`
- copy `SCF_ModAPIClient.cs`
- use `ShipCoreFrameworkClientApi` for synchronized read-only client data
- use `ShipCoreFrameworkServerApi` for authoritative server queries and mutations
- wait for config/runtime readiness and inspect `ApiReadResult<T>` instead of trusting fallback values

## XML configurator

A static configurator lives under `docs/` and helps build or update:

- world config
- block-group config
- manifest config
- per-core config
- manifest connector blacklist entries

### Local preview

```bash
python3 -m http.server 8080 --directory docs
```

Then open `http://localhost:8080/` (it redirects to `configurator/`).

## License

This project is licensed under the GNU General Public License v3.0 (`GPL-3.0-or-later`).
If you distribute modified versions, you must also provide the corresponding source code under the same GPL terms.
