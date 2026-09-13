# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**SE Ship Core Framework** is a Space Engineers mod that provides an alternative block limit system. It uses "Ship Cores" (beacons) to define grid classes with customizable:
- Block limits by type/group
- Grid modifiers (thrusters, refineries, assemblers, gyros, etc.)
- Speed limits and boost mechanics
- Defense modifiers (passive/active damage reduction)
- Per-faction and per-player core limits
- No-fly zones with enforcement

**Ownership**: Exclusive rights belong to Blues-Hailfire and ODB-Tech. Not for redistribution or Steam Workshop uploading.

**Main branch**: `main`

## Building and Testing

### Build Commands
- Always run `dotnet build arcane-systems.sln` before finalizing any code change. Treat build failures as blockers.
- Run relevant automated tests as well; use `node --test tests/*.test.mjs docs/scf-configurator/*.test.mjs` for the full contract suite.
- In-game integration is still required to validate runtime behavior that compilation and contract tests cannot exercise.

### Important Build Notes
- Target framework: .NET Framework 4.8 (`net48`)
- Language version: C# 6
- Platform: x64 only
- References Space Engineers DLLs from: `C:\Program Files (x86)\Steam\steamapps\common\SpaceEngineers\Bin64\`
- The mod must be deployed to Space Engineers' mod directory for testing in-game

## Architecture Overview

### Core Component Hierarchy

**Session (`Session/`)**
- Singleton session component (`MySessionComponentBase`)
- Entry point for the mod, manages lifecycle (LoadData, BeforeStart, UpdateAfterSimulation, UnloadData)
- Owns the `GroupDict`: a concurrent dictionary mapping `IMyGridGroupData` to `GroupComponent`
- Handles grid group events (creation/destruction)
- Runs parallel updates every tick for speed enforcement, boost timers, and no-fly zones
- Manages Nexus API integration for multi-server support
- Modifies game definitions on load (max ship speed, ammo speeds)

**GroupComponent (`Shared/Components/GroupComponent.cs` plus role partials)**
- Represents a logical grid group (connected by pistons, rotors, connectors, etc.)
- Tracks:
  - `MainCoreComponent`: The active core for the group (deterministic failover on core destruction)
  - `CoreDictionary`: All cores in the group
  - `GridDictionary`: All `MyCubeGrid` → `GridComponent` mappings
  - `Limits`: Block limit buckets aggregated from all grids
- Responsibilities:
  - Core activation/deactivation and failover
  - Limit recalculation and enforcement (punishes over-limit blocks)
  - Applying grid modifiers (thruster force, refinery speed, etc.)
  - Managing boost and active defense timers
  - Speed punishment when over-capacity

**GridComponent (`Shared/Components/GridComponent.cs` plus role partials)**
- Represents a single `MyCubeGrid` within a group
- Tracks blocks on the grid and their contribution to block limits
- Recalculates limits when blocks are added/removed
- Handles block refunds when punishment type is "Delete"

**CoreComponent (`Shared/Components/CoreComponent.cs` plus role partials)**
- Represents a single Ship Core block (`IMyBeacon`)
- Init logic:
  - Validates core placement (owner must match grid owner, no duplicate core types on grid)
  - Checks per-faction and per-player limits (scheduled checks after 30 ticks)
  - Persists "IsMainCore" state to block storage
  - Registers for upgrade value changes (for cores with upgrade modules)
- On destruction: triggers group failover to another core in the group

### Configuration System (Config/ModConfig.cs)

**ModConfig** loads from multiple sources:
1. **World storage**: `ShipCoreConfig_World.xml` (global settings: debug mode, max speed, no-fly zones)
2. **Sandbox storage**: Per-world data for ignored factions and selected "NoCore" config
3. **Mod files**: Each mod can provide:
   - `Data/ShipCoreConfig_Manifest.xml`: List of ship core config files
   - `Data/ShipCoreConfig_Groups.xml`: Block group definitions (shortcuts for block limits)
   - `Data/ShipCoreConfig_No_Core.xml`: Default config for grids without a core
   - Individual ship core XML files referenced in the manifest

**ShipCore class** defines a core type:
- `SubtypeId`: Block subtype identifier
- `UniqueName`: Human-readable name
- `MaxBlocks`, `MaxMass`, `MaxPCU`: Hard caps (punish if exceeded)
- `MaxPerFaction`, `MaxPerPlayer`: Ownership limits
- `Modifiers`: Grid performance multipliers
- `PassiveDefenseModifiers`, `ActiveDefenseModifiers`: Damage reduction
- `BlockLimits[]`: Array of per-block-type/group limits with punishment rules
- `SpeedBoostEnabled`, `EnableActiveDefenseModifiers`: Feature flags

### Managers (`Server/Managers/`)

**GridsPerFactionManager** and **GridsPerPlayerManager**:
- Track which grid groups belong to which faction/player
- Enforce `MaxPerFaction` and `MaxPerPlayer` limits
- Used during core initialization to reject cores that would exceed limits

**LimitsNexusSync**:
- Syncs block limit state across Nexus servers (for multi-server environments)
- Broadcasts snapshots of faction/player grid counts
- Only active when Nexus API is enabled

### Key Systems

**CubeGridModifiers**:
- Applies grid modifiers to individual blocks (thrusters, refineries, assemblers, gyros, power producers, drills)
- Maintains a dictionary of defense modifiers per grid entity ID
- Called by `GroupComponent.ApplyModifiers()` when core changes or limits are recalculated

**SpeedEnforcement**:
- Enforces max speed per core type (relative to block count ratios)
- Uses boost multiplier if boost is active
- Punishes over-speed grids by applying deceleration

**NoFlyZones**:
- Defined in world config as spheres (Position, Radius, AllowedCoresSubtype, ForceOff)
- Enforces every 10 ticks, punishes every 60 ticks
- Can override block limits and force blocks off in restricted zones
- Zones are drawn as transparent spheres when camera is near the edge

**BlockLimit Enforcement**:
- Each `BlockLimit` has a `MaxCount`, `PunishmentType`, and optional `AllowedDirections`
- `PunishmentType`: ShutOff (default), Damage, Delete (with refund), Explode, DeleteWithoutRefund
- `AllowedDirections`: Restricts block placement direction relative to core orientation (e.g., "Forward" only for certain weapons)
- Enforcement runs in `GroupComponent.EnforceGroupPunishment()`

### Networking (`Shared/Network/`, `Client/Network/`, `Server/Network/`)

**Networking (`Shared/Network/Networking.cs`)**:
- Handles client-server packet communication
- Registered handlers for each packet type
- Uses `PacketBase` for serialization

**Commands**:
- Chat commands processed via `OnChatCommand`
- Server receives secure messages from clients via `ServerMessageHandler`
- Commands include: boost activation, active defense, core management

## Development Guidelines

### Code Style
- C# 6 syntax only (no newer features like pattern matching, tuple deconstruction, etc.)
- Use explicit types, avoid `var` where possible (legacy codebase style)
- Avoid LINQ where performance-critical (prefer manual loops for hot paths)

### Threading Model
- Main tick runs on game thread (`UpdateAfterSimulation`)
- Heavy operations (grid group iteration) run via `MyAPIGateway.Parallel.StartBackground()`
- Always use `MyAPIGateway.Utilities.InvokeOnGameThread()` when modifying game objects from background threads
- Use `ConcurrentDictionary` for data shared across threads

### Common Pitfalls
- **Grid group changes**: Grid groups can split/merge at any time. Always handle `removedFrom` and `addedTo` parameters in group events.
- **Block destruction during iteration**: Use `GetBlocksCopy()` when iterating blocks that might be removed during iteration.
- **Null checks**: Space Engineers API can return null unexpectedly, especially during shutdown (`IsShuttingDown` flag)
- **Alt-F4 crashes**: UnloadData must handle exceptions gracefully (see try-catch in grid group unsubscribe)

### Key Files to Modify for Common Tasks

**Adding a new grid modifier:**
1. Add field to `GridModifiers` class in `ModConfig.cs`
2. Update `CubeGridModifiers.ApplyModifiers()` to apply the new modifier
3. Update XML serialization in config files

**Adding a new block limit:**
1. Define new `BlockGroup` in `Data/ShipCoreConfig_Groups.xml`
2. Reference the group in a core's `BlockLimits` array
3. Ensure `BlockLimit.GetWeight()` handles the new group

**Adding a new command:**
1. Add local input or presentation under `Client/UI/`
2. Add validation and authoritative execution under `Server/Commands/`
3. Add packet contracts under `Shared/Network/` and the receive handler under the applicable role

**Modifying core behavior:**
- Core activation logic: `GroupComponent.Activate()` and `CoreComponent.Init()`
- Failover logic: `GroupComponent.RebuildGroupState()`
- Persistence: `CoreComponent.SaveCoreState()` (uses block storage with GUID)

## Debugging

**Logging:**
- Use `Utils.Log(message, logLevel)` for server-side logs
- Log levels: 0 = always, 1 = info, 2 = verbose, 3 = debug
- Client output log level controlled by `Config.ClientOutputLogLevel`

**In-Game Testing:**
- Deploy mod to `%AppData%\SpaceEngineers\Mods\` or workshop mods folder
- Enable "Ship Core Framework" in world settings
- Use admin commands to adjust configs in-game
- Check `%AppData%\SpaceEngineers\Storage\` for world-specific config files

**Common Debug Scenarios:**
- Core not activating: Check `IsMainCore` persistence in block storage
- Block limits not enforcing: Verify `BlockGroups` loaded correctly in `ModConfig.LoadConfig()`
- Speed enforcement failing: Check `SpeedEnforcement.EnforceSpeedLimit()` and verify `PunishSpeed` flag
- Modifiers not applying: Verify `ApplyModifiers()` is called after core activation

## NexusAPI Integration

- Nexus support is optional (multi-server grid sync)
- Enabled via callback in `OnNexusEnabled()`
- `LimitsNexusSync` broadcasts snapshots every 5 seconds
- Only runs on server with `IsServer` flag set
