# Ship Core Framework API v4

API v4 separates process-local consumers by authority:

- `ShipCoreFrameworkServerApi`: authoritative server queries and runtime mutations.
- `ShipCoreFrameworkClientApi`: read-only queries backed by synchronized replicas on remote clients
  and local authority on a listen host or in single-player.

There is no generic client-to-server API. A future remote operation must use a dedicated secure packet
with player, permission, ownership, argument, and rate-limit validation.

## Install

Copy these files into the consuming mod:

- `Data/Scripts/ShipCoreFramework/API/ApiData.cs`
- `Data/Scripts/ShipCoreFramework/API/SCF_ModAPIClient.cs`

API v3 wrappers do not connect to v4. The transport is intentionally major-version breaking.

## Client replica example

```csharp
private readonly ShipCoreFrameworkClientApi _scf = new ShipCoreFrameworkClientApi();

public override void LoadData()
{
    _scf.Register();
}

protected override void UnloadData()
{
    _scf.Unregister();
}

public override void UpdateAfterSimulation()
{
    if (!_scf.ProviderReady || !_scf.ConfigReady || !_scf.RuntimeSnapshotReady)
        return;

    ApiReadResult<float> speed = _scf.TryGetMaxSpeed(_gridEntityId);
    if (!speed.Success)
        return;

    float maximumSpeed = speed.Value;
}
```

The client replica API can answer by grid entity ID even when that grid entity is not streamed locally,
provided its server runtime snapshot is present.

## Server authority example

```csharp
private readonly ShipCoreFrameworkServerApi _scf = new ShipCoreFrameworkServerApi();

public override void LoadData()
{
    _scf.Register();
}

protected override void UnloadData()
{
    _scf.Unregister();
}

private void DisableFriction(long gridEntityId)
{
    if (!_scf.ProviderReady || !_scf.RuntimeSnapshotReady)
        return;

    ApiReadResult<bool> result = _scf.TrySetFrictionEnabledForGroup(gridEntityId, false);
    if (!result.Success)
        MyLog.Default.WriteLine("[MyMod] SCF mutation failed: " + result.Error);
}
```

Server modifier profiles can override grid, speed, passive-defense, and active-defense values:

```csharp
_scf.TrySetGridModifiersOverrideForGroup(gridEntityId, gridModifiers);
_scf.TrySetSpeedModifiersOverrideForGroup(gridEntityId, speedModifiers);
_scf.TrySetPassiveDefenseModifiersOverrideForGroup(gridEntityId, passiveDefense);
_scf.TrySetActiveDefenseModifiersOverrideForGroup(gridEntityId, activeDefense);
```

Pass `null` to any setter to restore that category's core/upgrade profile. Overrides are runtime-only,
group-scoped, and remain authoritative through core and upgrade changes. Punishment gates still apply.

Register only the wrapper appropriate to the consumer role. Dedicated servers publish only the
server-local factory, remote clients publish only the client-replica factory, and listen hosts and
single-player publish both. The client surface remains read-only when it is backed by local authority.

## Readiness

Readiness exposes these states and diagnostics:

- `ProviderReady`: compatible factory received.
- `ConfigReady`: server-selected world config applied.
- `RuntimeSnapshotReady`: initial authority scan or complete client runtime snapshot applied.
- `ConfigurationError`: explains why configuration is unavailable, such as a missing content-pack
  no-core profile. An empty value means configuration is pending or valid.
- `TryGetRuntimeStateAvailability(gridId)`: runtime state exists for one grid.

`ConfigReceived` fires before the replacement runtime snapshot is requested. It therefore resets
`RuntimeSnapshotReady` to false. It fires only for a valid configuration. `RuntimeReady` fires after
the complete snapshot is applied.

## Result statuses

All `Try...` methods return `ApiReadResult<T>`:

- `Success`
- `ProviderNotReady`
- `ConfigPending`
- `ConfigurationUnavailable`
- `RuntimePending`
- `GridNotReplicated`
- `InvalidArgument`
- `Unsupported`
- `Error`

All queries return an `ApiReadResult<T>` so unavailable data cannot be confused with a real value.

## Query classification

Config-ready queries:

- `TryGetCoreBySubtypeId`
- `TryGetAllCoreConfigs`
- `TryGetNoCoreConfig`
- `TryGetFullConfig`
- `TryGetFrictionSpeedValueMode`

Runtime-ready queries:

- Grid core and block-limit state
- Grid and speed modifiers
- Base/effective speed and boost state
- Friction state and overrides
- Group deactivation

Grid-targeted methods accept only `long gridId`. Consumers that already have an `IMyCubeGrid`
should pass `grid.EntityId`.

`TryIsBlockAllowed` is authoritative on the server API and best-effort on the client replica API.
The replica answer uses synchronized counts and may become stale between server updates.

`BlockLimitData.BlockGroupNames` lists included reusable groups.
`BlockLimitData.ExcludedBlockGroupNames` lists groups subtracted from those matches; exclusions
take precedence when a block belongs to both.
`BlockLimitData.MaxCountPerDirection` exposes the optional six-way weighted cap, and
`BlockLimitData.LimitVisibility` exposes its HUD presentation policy. These fields require API v4.2;
older v4 consumers remain compatible and ignore the appended protobuf members.
`BlockLimitData.IgnoredByNpc` exposes the per-limit NPC exemption and requires API v4.3. Older v4
consumers remain compatible and treat the appended protobuf member as `false`.
`BlockLimitData.DirectionBudgets` exposes per-direction overrides as `DirectionBudgetData` entries
(`Direction`, `MaxCount`) and requires API v4.5. Missing directions inherit `MaxCountPerDirection`;
older v4 consumers ignore the appended field. Direction budgets share the limit's weighted counts.
`PunishmentTypeData.DeleteWithoutRefund` requires API v4.4.
`ApiReadStatusData.ConfigurationUnavailable` and `ApiReadinessData.ConfigurationError` also require
API v4.4; older v4 consumers remain wire-compatible but do not expose the diagnostic name or text.

Runtime mutations exist only on `ShipCoreFrameworkServerApi`.

`TryGetGroupMass(gridId)` is also server-only. It returns authoritative full-definition dry mass in
kilograms used by mass-limit enforcement. Inventory contents and construction progress are ignored.

## Events

Both wrappers expose:

- `CoreActivated` / `CoreDeactivated`
- `LimitsRecalculated` / `LimitsEnforced`
- `BoostActivated` / `BoostDeactivated`
- `ActiveDefenseActivated` / `ActiveDefenseDeactivated`
- `GridAddedToGroup` / `GridRemovedFromGroup`
- `ConfigReceived`
- `RuntimeReady`

Resolved event variants remain best-effort because the relevant entity might not be streamed locally.

## Security boundary

Space Engineers mod messages are process-local and provide no caller identity. Separate factories stop
remote client mods from receiving server mutation delegates. They cannot sandbox an untrusted native
plugin already executing inside a listen-server or dedicated-server process.
