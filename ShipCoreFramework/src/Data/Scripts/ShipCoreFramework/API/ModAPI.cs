using System;
using System.Collections.Generic;
using System.Linq;
using Sandbox.Game.Entities;
using Sandbox.ModAPI;
using VRage;
using VRage.Game.ModAPI;

// ReSharper disable InconsistentNaming
// ReSharper disable MemberCanBePrivate.Global

namespace ShipCoreFramework
{
    /// <summary>
    /// Ship Core Framework external API for other mods to interact with the system.
    ///
    /// API v4 publishes separate process-local factories for server authority and client replicas.
    /// Every method returns MyTuple&lt;int, object&gt; where Item1 is ApiReadStatusData and Item2 is
    /// a primitive, MyTuple, or serialized DTO byte[].
    ///
    /// IMPORTANT:
    /// Other mods should copy ApiData.cs and use the provided client wrapper (see below).
    /// </summary>
    public static partial class ModAPI
    {
        private static bool _isInitialized;

        /// <summary>
        /// Initializes the API and broadcasts it to other mods.
        /// Called internally by Session component during BeforeStart.
        /// </summary>
        internal static void Initialize()
        {
            if (_isInitialized) return;
            _isInitialized = true;

            try
            {
                if (Session.IsServer)
                {
                    MyTuple<int, int, Func<int, Func<object, object>>> serverPayload = MyTuple.Create(
                        ApiConstants.API_VERSION,
                        (int)ApiProviderRoleData.ServerLocalAuthority,
                        new Func<int, Func<object, object>>(ServerMethodFactory));
                    MyAPIGateway.Utilities.SendModMessage(ApiConstants.SERVER_LOCAL_API_ID, serverPayload);
                    Utils.Log("ModAPI v4: broadcast server-local authority factory.", 1);
                }
                if (Session.IsClient)
                {
                    MyTuple<int, int, Func<int, Func<object, object>>> clientPayload = MyTuple.Create(
                        ApiConstants.API_VERSION,
                        (int)ApiProviderRoleData.ClientLocalReplica,
                        new Func<int, Func<object, object>>(ClientMethodFactory));
                    MyAPIGateway.Utilities.SendModMessage(ApiConstants.CLIENT_REPLICA_API_ID, clientPayload);
                    Utils.Log("ModAPI v4: broadcast client-local replica factory.", 1);
                }
            }
            catch (Exception ex)
            {
                Utils.Log($"ModAPI: Failed to initialize API - {ex}", 3);
            }
        }

        /// <summary>
        /// Closes the API. Called during mod unload.
        /// </summary>
        internal static void Close()
        {
            _isInitialized = false;
            ResetReadiness();
        }

        // ===== Event Broadcasting Methods =====
        //
        // IMPORTANT:
        // Events must be cross-assembly safe.
        // Do NOT send custom event arg objects directly; other mods cannot cast them.
        // Instead, serialize to byte[] and let consumers deserialize locally.

        /// <summary>
        /// Broadcasts the CoreActivated event to all subscribed mods.
        /// </summary>
        internal static void BroadcastCoreActivated(long groupGridId, string coreSubtypeId, string coreName)
        {
            if (!_isInitialized) return;

            try
            {
                var eventData = new CoreActivatedEventArgs
                {
                    GroupGridId = groupGridId,
                    CoreSubtypeId = coreSubtypeId,
                    CoreName = coreName,
                    Timestamp = DateTime.UtcNow
                };

                var payload = MyAPIGateway.Utilities.SerializeToBinary(eventData);
                MyAPIGateway.Utilities.SendModMessage(ApiConstants.EVENT_CORE_ACTIVATED, payload);

                Utils.Log($"ModAPI Event: CoreActivated for grid Entity ID: {groupGridId}", 1);
            }
            catch (Exception ex)
            {
                Utils.Log($"ModAPI.BroadcastCoreActivated: Exception - {ex}", 3);
            }
        }

        /// <summary>
        /// Broadcasts the CoreDeactivated event to all subscribed mods.
        /// </summary>
        internal static void BroadcastCoreDeactivated(long groupGridId, string previousCoreSubtypeId, string previousCoreName)
        {
            if (!_isInitialized) return;

            try
            {
                var eventData = new CoreDeactivatedEventArgs
                {
                    GroupGridId = groupGridId,
                    PreviousCoreSubtypeId = previousCoreSubtypeId,
                    PreviousCoreName = previousCoreName,
                    Timestamp = DateTime.UtcNow
                };

                var payload = MyAPIGateway.Utilities.SerializeToBinary(eventData);
                MyAPIGateway.Utilities.SendModMessage(ApiConstants.EVENT_CORE_DEACTIVATED, payload);

                Utils.Log($"ModAPI Event: CoreDeactivated for grid Entity ID: {groupGridId}", 1);
            }
            catch (Exception ex)
            {
                Utils.Log($"ModAPI.BroadcastCoreDeactivated: Exception - {ex}", 3);
            }
        }

        /// <summary>
        /// Broadcasts the LimitsRecalculated event to all subscribed mods.
        /// </summary>
        internal static void BroadcastLimitsRecalculated(long groupGridId)
        {
            if (!_isInitialized) return;

            try
            {
                var eventData = new LimitsRecalculatedEventArgs
                {
                    GroupGridId = groupGridId,
                    Timestamp = DateTime.UtcNow
                };

                var payload = MyAPIGateway.Utilities.SerializeToBinary(eventData);
                MyAPIGateway.Utilities.SendModMessage(ApiConstants.EVENT_LIMITS_RECALCULATED, payload);

                Utils.Log("ModAPI Event: LimitsRecalculated for group", 1);
            }
            catch (Exception ex)
            {
                Utils.Log($"ModAPI.BroadcastLimitsRecalculated: Exception - {ex}", 3);
            }
        }

        /// <summary>
        /// Broadcasts the LimitsEnforced event to all subscribed mods.
        /// </summary>
        internal static void BroadcastLimitsEnforced(long groupGridId, int blocksPunished)
        {
            if (!_isInitialized) return;

            try
            {
                var eventData = new LimitsEnforcedEventArgs
                {
                    GroupGridId = groupGridId,
                    BlocksPunished = blocksPunished,
                    Timestamp = DateTime.UtcNow
                };

                var payload = MyAPIGateway.Utilities.SerializeToBinary(eventData);
                MyAPIGateway.Utilities.SendModMessage(ApiConstants.EVENT_LIMITS_ENFORCED, payload);

                Utils.Log($"ModAPI Event: LimitsEnforced, punished {blocksPunished} blocks", 1);
            }
            catch (Exception ex)
            {
                Utils.Log($"ModAPI.BroadcastLimitsEnforced: Exception - {ex}", 3);
            }
        }

        /// <summary>
        /// Broadcasts the BoostActivated event to all subscribed mods.
        /// </summary>
        internal static void BroadcastBoostActivated(long groupGridId)
        {
            if (!_isInitialized) return;

            try
            {
                var eventData = new BoostEventArgs
                {
                    GroupGridId = groupGridId,
                    Timestamp = DateTime.UtcNow
                };

                var payload = MyAPIGateway.Utilities.SerializeToBinary(eventData);
                MyAPIGateway.Utilities.SendModMessage(ApiConstants.EVENT_BOOST_ACTIVATED, payload);

                Utils.Log($"ModAPI Event: BoostActivated for grid Entity ID: {groupGridId}", 1);
            }
            catch (Exception ex)
            {
                Utils.Log($"ModAPI.BroadcastBoostActivated: Exception - {ex}", 3);
            }
        }

        /// <summary>
        /// Broadcasts the BoostDeactivated event to all subscribed mods.
        /// </summary>
        internal static void BroadcastBoostDeactivated(long groupGridId)
        {
            if (!_isInitialized) return;

            try
            {
                var eventData = new BoostEventArgs
                {
                    GroupGridId = groupGridId,
                    Timestamp = DateTime.UtcNow
                };

                var payload = MyAPIGateway.Utilities.SerializeToBinary(eventData);
                MyAPIGateway.Utilities.SendModMessage(ApiConstants.EVENT_BOOST_DEACTIVATED, payload);

                Utils.Log($"ModAPI Event: BoostDeactivated for grid Entity ID: {groupGridId}", 1);
            }
            catch (Exception ex)
            {
                Utils.Log($"ModAPI.BroadcastBoostDeactivated: Exception - {ex}", 3);
            }
        }

        /// <summary>
        /// Broadcasts the ActiveDefenseActivated event to all subscribed mods.
        /// </summary>
        internal static void BroadcastActiveDefenseActivated(long groupGridId)
        {
            if (!_isInitialized) return;

            try
            {
                var eventData = new ActiveDefenseEventArgs
                {
                    GroupGridId = groupGridId,
                    Timestamp = DateTime.UtcNow
                };

                var payload = MyAPIGateway.Utilities.SerializeToBinary(eventData);
                MyAPIGateway.Utilities.SendModMessage(ApiConstants.EVENT_ACTIVE_DEFENSE_ACTIVATED, payload);

                Utils.Log($"ModAPI Event: ActiveDefenseActivated for grid Entity ID: {groupGridId}", 1);
            }
            catch (Exception ex)
            {
                Utils.Log($"ModAPI.BroadcastActiveDefenseActivated: Exception - {ex}", 3);
            }
        }

        /// <summary>
        /// Broadcasts the ActiveDefenseDeactivated event to all subscribed mods.
        /// </summary>
        internal static void BroadcastActiveDefenseDeactivated(long groupGridId)
        {
            if (!_isInitialized) return;

            try
            {
                var eventData = new ActiveDefenseEventArgs
                {
                    GroupGridId = groupGridId,
                    Timestamp = DateTime.UtcNow
                };

                var payload = MyAPIGateway.Utilities.SerializeToBinary(eventData);
                MyAPIGateway.Utilities.SendModMessage(ApiConstants.EVENT_ACTIVE_DEFENSE_DEACTIVATED, payload);

                Utils.Log($"ModAPI Event: ActiveDefenseDeactivated for grid Entity ID: {groupGridId}", 1);
            }
            catch (Exception ex)
            {
                Utils.Log($"ModAPI.BroadcastActiveDefenseDeactivated: Exception - {ex}", 3);
            }
        }

        /// <summary>
        /// Broadcasts the GridAddedToGroup event to all subscribed mods.
        /// </summary>
        internal static void BroadcastGridAddedToGroup(long gridId)
        {
            if (!_isInitialized) return;

            try
            {
                var eventData = new GridGroupEventArgs
                {
                    GridId = gridId,
                    GroupGridId = gridId,
                    Timestamp = DateTime.UtcNow
                };

                var payload = MyAPIGateway.Utilities.SerializeToBinary(eventData);
                MyAPIGateway.Utilities.SendModMessage(ApiConstants.EVENT_GRID_ADDED_TO_GROUP, payload);

                Utils.Log($"ModAPI Event: GridAddedToGroup Entity ID: {gridId}", 1);
            }
            catch (Exception ex)
            {
                Utils.Log($"ModAPI.BroadcastGridAddedToGroup: Exception - {ex}", 3);
            }
        }

        /// <summary>
        /// Broadcasts the GridRemovedFromGroup event to all subscribed mods.
        /// </summary>
        internal static void BroadcastGridRemovedFromGroup(long gridId, long groupGridId)
        {
            if (!_isInitialized) return;

            try
            {
                var eventData = new GridGroupEventArgs
                {
                    GridId = gridId,
                    GroupGridId = groupGridId,
                    Timestamp = DateTime.UtcNow
                };

                var payload = MyAPIGateway.Utilities.SerializeToBinary(eventData);
                MyAPIGateway.Utilities.SendModMessage(ApiConstants.EVENT_GRID_REMOVED_FROM_GROUP, payload);

                Utils.Log($"ModAPI Event: GridRemovedFromGroup Entity ID: {gridId}", 1);
            }
            catch (Exception ex)
            {
                Utils.Log($"ModAPI.BroadcastGridRemovedFromGroup: Exception - {ex}", 3);
            }
        }

        /// <summary>
        /// Broadcasts the effective mod config after client receives synced world settings from server.
        /// </summary>
        internal static void BroadcastConfigReceived()
        {
            if (!_isInitialized) return;

            try
            {
                var eventData = new ConfigReceivedEventArgs
                {
                    Config = ConvertToModConfigData(Session.Config),
                    Timestamp = DateTime.UtcNow
                };

                var payload = MyAPIGateway.Utilities.SerializeToBinary(eventData);
                MyAPIGateway.Utilities.SendModMessage(ApiConstants.EVENT_CONFIG_RECEIVED, payload);

                Utils.Log("ModAPI Event: ConfigReceived", 1);
            }
            catch (Exception ex)
            {
                Utils.Log($"ModAPI.BroadcastConfigReceived: Exception - {ex}", 3);
            }
        }
        
        /// <summary>
        /// Gets the speed modifiers for a grid's active core.
        /// </summary>
        public static SpeedModifiersData GetSpeedModifiers(long gridId)
        {
            try
            {
                GroupComponent groupComponent;
                if (!TryGetGroupComponent(gridId, out groupComponent)) return ConvertToSpeedModifiersData(null);

                return ConvertToSpeedModifiersData(groupComponent.SpeedModifiers);
            }
            catch (Exception ex)
            {
                Utils.Log($"ModAPI.GetSpeedModifiers: Exception - {ex}");
                return ConvertToSpeedModifiersData(null);
            }
        }

        /// <summary>
        /// Gets BoostResistance from the grid's active core speed modifiers.
        /// NOTE: This is a legacy value; it maps to MaximumFrictionDeceleration for newer configs.
        /// </summary>
        public static float GetBoostResistance(long gridId)
        {
            var s = GetSpeedModifiers(gridId);
            return s?.BoostResistance ?? 0f;
        }


        /// <summary>
        /// Gets whether friction-based speed limiting is currently active for a logical grid group.
        /// </summary>
        public static bool GetFrictionEnabledForGroup(long gridId)
        {
            try
            {
                GroupComponent groupComponent;
                return TryGetGroupComponent(gridId, out groupComponent) && groupComponent.GetFrictionEnforcementEnabled();
            }
            catch (Exception ex)
            {
                Utils.Log($"ModAPI.GetFrictionEnabledForGroup: Exception - {ex}");
                return false;
            }
        }


        /// <summary>
        /// Gets the maximum friction deceleration override for a logical grid group (or -1 if none).
        /// </summary>
        public static float GetFrictionMaximumDecelerationForGroup(long gridId)
        {
            try
            {
                GroupComponent groupComponent;
                return TryGetGroupComponent(gridId, out groupComponent) ? groupComponent.GetFrictionMaximumDecelerationOverride() : -1f;
            }
            catch (Exception ex)
            {
                Utils.Log($"ModAPI.GetFrictionMaximumDecelerationForGroup: Exception - {ex}");
                return -1f;
            }
        }


        public static MyTuple<float, string> GetFrictionMinimumSpeedAbsoluteForGroup(long gridId)
        {
            if (Session.Config.FrictionSpeedValueMode != FrictionSpeedValueMode.Absolute)
                return MyTuple.Create(-1f, "World config uses modifier-based friction speeds; use GetFrictionMinimumSpeedModifierForGroup.");

            GroupComponent groupComponent;
            return !TryGetGroupComponent(gridId, out groupComponent) ? MyTuple.Create(-1f, "Could not resolve logical grid group for the provided grid.") : MyTuple.Create(groupComponent.GetMinimumFrictionSpeedAbsoluteOverride(), string.Empty);
        }

        public static MyTuple<float, string> GetFrictionMaximumSpeedAbsoluteForGroup(long gridId)
        {
            if (Session.Config.FrictionSpeedValueMode != FrictionSpeedValueMode.Absolute)
                return MyTuple.Create(-1f, "World config uses modifier-based friction speeds; use GetFrictionMaximumSpeedModifierForGroup.");

            GroupComponent groupComponent;
            return !TryGetGroupComponent(gridId, out groupComponent) ? MyTuple.Create(-1f, "Could not resolve logical grid group for the provided grid.") : MyTuple.Create(groupComponent.GetMaximumFrictionSpeedAbsoluteOverride(), string.Empty);
        }


        public static MyTuple<float, string> GetFrictionMinimumSpeedModifierForGroup(long gridId)
        {
            if (Session.Config.FrictionSpeedValueMode != FrictionSpeedValueMode.Modifier)
                return MyTuple.Create(-1f, "World config uses absolute friction speeds; use GetFrictionMinimumSpeedAbsoluteForGroup.");

            GroupComponent groupComponent;
            return !TryGetGroupComponent(gridId, out groupComponent) ? MyTuple.Create(-1f, "Could not resolve logical grid group for the provided grid.") : MyTuple.Create(groupComponent.GetMinimumFrictionSpeedModifierOverride(), string.Empty);
        }

        public static MyTuple<float, string> GetFrictionMaximumSpeedModifierForGroup(long gridId)
        {
            if (Session.Config.FrictionSpeedValueMode != FrictionSpeedValueMode.Modifier)
                return MyTuple.Create(-1f, "World config uses absolute friction speeds; use GetFrictionMaximumSpeedAbsoluteForGroup.");

            GroupComponent groupComponent;
            return !TryGetGroupComponent(gridId, out groupComponent) ? MyTuple.Create(-1f, "Could not resolve logical grid group for the provided grid.") : MyTuple.Create(groupComponent.GetMaximumFrictionSpeedModifierOverride(), string.Empty);
        }

        public static bool IsGroupDeactivated(long gridId)
        {
            try
            {
                GroupComponent groupComponent;
                return TryGetGroupComponent(gridId, out groupComponent) && groupComponent.Deactivated;
            }
            catch (Exception ex)
            {
                Utils.Log($"ModAPI.IsGroupDeactivated: Exception - {ex}");
                return false;
            }
        }

        private static bool TryGetGroupComponent(long gridId, out GroupComponent groupComponent)
        {
            groupComponent = null;

            try
            {
                if (Utils.TryFindByGridId(gridId, out groupComponent))
                    return true;

                if (!Session.IsGameThread)
                    return false;

                var grid = MyAPIGateway.Entities.GetEntityById(gridId) as MyCubeGrid;
                var groupData = MyAPIGateway.GridGroups.GetGridGroup(GridLinkTypeEnum.Mechanical, grid);
                return groupData != null && Session.GroupDict.TryGetValue(groupData, out groupComponent);
            }
            catch
            {
                groupComponent = null;
                return false;
            }
        }

        /// <summary>
        /// Gets base max speed in m/s without boost applied.
        /// </summary>
        public static float GetBaseMaxSpeed(long gridId)
        {
            var grid = MyAPIGateway.Entities.GetEntityById(gridId) as MyCubeGrid;
            if (grid == null) return 100f;

            try
            {
                var groupData = MyAPIGateway.GridGroups.GetGridGroup(GridLinkTypeEnum.Mechanical, grid);
                if (groupData == null) return 100f;

                GroupComponent groupComponent;
                if (!Session.GroupDict.TryGetValue(groupData, out groupComponent))
                    return 100f;

                if (Session.IsServer)
                    RefreshAuthoritativeSpeedState(groupComponent);
                return groupComponent.BaseSpeedLimitMetersPerSecond;
            }
            catch (Exception ex)
            {
                Utils.Log($"ModAPI.GetBaseMaxSpeed: Exception - {ex}");
                return 100f;
            }
        }

        /// <summary>
        /// Gets max boost multiplier for the grid's active core.
        /// </summary>
        public static float GetMaxBoostMultiplier(long gridId)
        {
            var s = GetSpeedModifiers(gridId);
            return s?.MaxBoost ?? 0f;
        }

        /// <summary>
        /// Gets boost duration in seconds for the grid's active core.
        /// </summary>
        public static float GetBoostDuration(long gridId)
        {
            var s = GetSpeedModifiers(gridId);
            return s?.BoostDuration ?? 0f;
        }

        /// <summary>
        /// Gets boost cooldown in seconds for the grid's active core.
        /// </summary>
        public static float GetBoostCooldown(long gridId)
        {
            var s = GetSpeedModifiers(gridId);
            return s?.BoostCoolDown ?? 0f;
        }

        // ===== Helper Methods =====

        private static ShipCoreData ConvertToShipCoreData(ShipCore core, bool isDeactivated = false,
            GroupComponent groupComponent = null)
        {
            if (core == null)
            {
                return new ShipCoreData
                {
                    SubtypeId = string.Empty,
                    UniqueName = "NoCore",
                    Modifiers = new GridModifiersData
                    {
                        AssemblerSpeed = 1,
                        DrillHarvestMultiplier = 1,
                        GyroEfficiency = 1,
                        GyroForce = 1,
                        PowerProducersOutput = 1,
                        RefineEfficiency = 1,
                        RefineSpeed = 1,
                        ThrusterEfficiency = 1,
                        ThrusterForce = 1
                    },
                    SpeedModifiers = new SpeedModifiersData
                    {
                        MaxSpeed = 0.0f,
                        MaxAngularVelocity = 0.0f,
                        MaxBoost = 0.0f,
                        BoostDuration = 10f,
                        BoostCoolDown = 60f,
                        BoostResistance = 0f,
                        MinimumFrictionSpeedAbsolute = 0f,
                        MaximumFrictionSpeedAbsolute = 0f,
                        MaximumFrictionDeceleration = 0f,
                        MinimumFrictionSpeedModifier = 0f,
                        MaximumFrictionSpeedModifier = 0f,
                        FrictionCurve = Array.Empty<FrictionCurveSegmentData>(),
                        CruiseFrictionMultiplier = 1f,
                        CruiseAccelerationThreshold = 0.05f,
                        AtmosphericFriction = null
                    },
                    ManifestGroupNames = Array.Empty<string>(),
                    ConnectorBlacklistCoreSubtypeIds = Array.Empty<string>(),
                    CoreSelectionPriority = 0,
                    CrossConnectorPunishmentWhitelisted = false,
                    MinFactionRank = FactionRankData.None,
                    SpeedOverrideMode = SpeedOverrideModeData.OnlyIfHeavier,
                    PowerOverclockMultiplier = 1f,
                    PowerOverclockDuration = 10f,
                    PowerOverclockCooldown = 60f,
                    MaxBackupCores = -1,
                    AllowedUpgradeModules = Array.Empty<UpgradeModuleAllowanceData>(),
                    SpeedLimitTypeData = SpeedLimitTypeData.Normal,
                    BlockLimits = Array.Empty<BlockLimitData>(),
                    ManifestGroupName = string.Empty,
                    ManifestGroupMaxCount = -1,
                    ManifestGroupCurrentCount = 0,
                    ManifestGroups = Array.Empty<ManifestGroupLimitData>(),
                    IsDeactivated = isDeactivated
                };
            }

            var manifestGroups = GetConfiguredManifestGroups(core)
                .Select(group => new ManifestGroupLimitData
                {
                    Name = group.Name,
                    MaxCount = group.MaxCount,
                    CurrentCount = GetManifestGroupCurrentCount(group.Name, groupComponent)
                })
                .ToArray();

            var primaryManifestGroup = manifestGroups.FirstOrDefault();

            return new ShipCoreData
            {
                SubtypeId = core.SubtypeId,
                UniqueName = core.UniqueName,
                ForceBroadCast = core.ForceBroadCast,
                ForceBroadCastRange = core.ForceBroadCastRange,
                MobilityTypeData = (MobilityTypeData)(int)core.MobilityType,
                MaxBlocks = core.MaxBlocks,
                MaxMass = core.MaxMass,
                MaxPCU = core.MaxPCU,
                MaxPerFaction = core.MaxPerFaction,
                MaxPerPlayer = core.MaxPerPlayer,
                MinPlayers = core.MinPlayers,
                MinBlocks = core.MinBlocks,
                MaxPlayers = core.MaxPlayers,
                FactionPlayersNeededPerCore = core.FactionPlayersNeededPerCore,
                ManifestGroupNames = core.ManifestGroupNames
                    .Where(name => !string.IsNullOrWhiteSpace(name))
                    .Distinct(StringComparer.OrdinalIgnoreCase)
                    .ToArray(),
                ConnectorBlacklistCoreSubtypeIds = core.ConnectorBlacklistCoreSubtypeIds
                    .Where(name => !string.IsNullOrWhiteSpace(name))
                    .OrderBy(name => name, StringComparer.OrdinalIgnoreCase)
                    .ToArray(),
                CoreSelectionPriority = core.CoreSelectionPriority,
                CrossConnectorPunishmentWhitelisted = core.CrossConnectorPunishmentWhitelisted,
                MinFactionRank = (FactionRankData)(int)core.MinFactionRank,
                MaxBackupCores = core.MaxBackupCores,
                AllowedUpgradeModules = (core.AllowedUpgradeModules ?? Array.Empty<UpgradeModuleAllowance>())
                    .Where(allowance => allowance != null)
                    .Select(ConvertToUpgradeModuleAllowanceData)
                    .ToArray(),
                SpeedLimitTypeData = (SpeedLimitTypeData)(int)core.SpeedLimitType,
                BlockLimits = (core.BlockLimits ?? Array.Empty<BlockLimit>())
                    .Where(limit => limit != null)
                    .Select(ConvertToBlockLimitData)
                    .ToArray(),
                ManifestGroupName = primaryManifestGroup?.Name ?? string.Empty,
                ManifestGroupMaxCount = primaryManifestGroup?.MaxCount ?? -1,
                ManifestGroupCurrentCount = primaryManifestGroup?.CurrentCount ?? 0,
                ManifestGroups = manifestGroups,
                Modifiers = ConvertToGridModifiersData(core.Modifiers),
                PassiveDefenseModifiers = ConvertToDefenseModifiersData(core.PassiveDefenseModifiers),
                SpeedBoostEnabled = core.SpeedBoostEnabled,
                SpeedOverrideMode = (SpeedOverrideModeData)(int)core.SpeedOverrideMode,
                SpeedOverridePriority = core.SpeedOverridePriority,
                EnableActiveDefenseModifiers = core.EnableActiveDefenseModifiers,
                ActiveDefenseModifiers = ConvertToDefenseModifiersData(core.ActiveDefenseModifiers),
                PowerOverclockEnabled = core.PowerOverclockEnabled,
                PowerOverclockMultiplier = core.PowerOverclockMultiplier,
                PowerOverclockDuration = core.PowerOverclockDuration,
                PowerOverclockCooldown = core.PowerOverclockCooldown,
                PowerOverclockDamagePerSecond = core.PowerOverclockDamagePerSecond,
                DynamicBoostEnabled = false,
                SpeedModifiers = ConvertToSpeedModifiersData(core.SpeedModifiers),
                IsDeactivated = isDeactivated
            };
        }

        private static int GetManifestGroupCurrentCount(string name, GroupComponent groupComponent)
        {
            if (groupComponent != null) return groupComponent.GetCurrentManifestCoreCount(name);
            return Session.IsServer
                ? GetAuthoritativeManifestGroupCount(name)
                : GetReplicatedManifestGroupCount(name);
        }

        private static IEnumerable<ManifestCoreGroup> GetConfiguredManifestGroups(ShipCore core)
        {
            if (core?.ManifestGroupNames == null)
                yield break;

            foreach (var groupName in core.ManifestGroupNames)
            {
                var group = Session.Config.GetManifestGroupByName(groupName);
                if (group != null)
                    yield return group;
            }
        }

        private static ModConfigData ConvertToModConfigData(ModConfig config)
        {
            if (config == null)
            {
                return new ModConfigData
                {
                    BlockDirectionalPlacementOnSubgrids = true,
                    CreativeCoreCountLimitsEnabled = true,
                    SpeedRampDownPercentage = 5f,
                    NoCoreGraceSeconds = 30,
                    MinimumBlocksGraceSeconds = 30,
                    IgnoredFactionTags = Array.Empty<string>(),
                    NoFlyZones = Array.Empty<NoFlyZoneData>(),
                    NoCoreConfigs = Array.Empty<ShipCoreData>(),
                    ShipCores = Array.Empty<ShipCoreData>(),
                    ManifestCoreGroups = Array.Empty<ManifestCoreGroupData>(),
                    UpgradeModules = Array.Empty<UpgradeModuleConfigData>(),
                    BlockGroups = Array.Empty<BlockGroupData>(),
                    SelectedNoCore = ConvertToShipCoreData(null)
                };
            }

            return new ModConfigData
            {
                IgnoreAiFactions = config.IgnoreAiFactions,
                IgnoredFactionTags = (config.IgnoredFactionTags ?? new List<string>())
                    .Where(tag => !string.IsNullOrWhiteSpace(tag))
                    .ToArray(),
                SelectedNoCoreUniqueName = config.SelectedNoCoreUniqueName ?? string.Empty,
                DebugMode = config.DebugMode,
                CombatLogging = config.CombatLogging,
                CombatLoggingBroadcastRangeMeters = config.CombatLoggingBroadcastRangeMeters,
                LogLevel = config.LogLevel,
                ClientOutputLogLevel = config.ClientOutputLogLevel,
                MaxPossibleSpeedMetersPerSecond = config.MaxPossibleSpeedMetersPerSecond,
                SpeedRampDownPercentage = config.SpeedRampDownPercentage,
                MassTypeMode = MassTypeModeData.Dry,
                FrictionSpeedValueMode = (FrictionSpeedValueModeData)(int)config.FrictionSpeedValueMode,
                BlockDirectionalPlacementOnSubgrids = config.BlockDirectionalPlacementOnSubgrids,
                AllowUnattachedUpgradeModules = config.AllowUnattachedUpgradeModules,
                CreativeCoreCountLimitsEnabled = config.CreativeCoreCountLimitsEnabled,
                NoCoreGraceSeconds = config.NoCoreGraceSeconds,
                MinimumBlocksGraceSeconds = config.MinimumBlocksGraceSeconds,
                NoFlyZones = config.NoFlyZones
                    .Where(zone => zone != null)
                    .Select(ConvertToNoFlyZoneData)
                    .ToArray(),
                NoCoreConfigs = config.NoCoreConfigs
                    .Where(core => core != null)
                    .Select(core => ConvertToShipCoreData(core))
                    .ToArray(),
                ShipCores = config.ShipCores
                    .Where(core => core != null)
                    .Select(core => ConvertToShipCoreData(core))
                    .ToArray(),
                ManifestCoreGroups = config.ManifestCoreGroups
                    .Where(group => group != null)
                    .Select(ConvertToManifestCoreGroupData)
                    .ToArray(),
                UpgradeModules = config.UpgradeModules
                    .Where(module => module != null)
                    .Select(ConvertToUpgradeModuleConfigData)
                    .ToArray(),
                BlockGroups = config.BlockGroups
                    .Where(group => group != null)
                    .Select(ConvertToBlockGroupData)
                    .ToArray(),
                SelectedNoCore = ConvertToShipCoreData(config.SelectedNoCore)
            };
        }

        private static ManifestCoreGroupData ConvertToManifestCoreGroupData(ManifestCoreGroup group)
        {
            if (group == null)
            {
                return new ManifestCoreGroupData
                {
                    Name = string.Empty,
                    CoreSubtypeIds = Array.Empty<string>()
                };
            }

            return new ManifestCoreGroupData
            {
                Name = group.Name ?? string.Empty,
                MaxCount = group.MaxCount,
                CoreSubtypeIds = group.CoreSubtypeIds
                    .Where(id => !string.IsNullOrWhiteSpace(id))
                    .OrderBy(id => id, StringComparer.OrdinalIgnoreCase)
                    .ToArray()
            };
        }

        private static NoFlyZoneData ConvertToNoFlyZoneData(Zones zone)
        {
            if (zone == null)
            {
                return new NoFlyZoneData
                {
                    AllowedCoresSubtype = Array.Empty<string>(),
                    Position = new Vector3DData()
                };
            }

            return new NoFlyZoneData
            {
                Id = zone.Id,
                Position = new Vector3DData
                {
                    X = zone.Position.X,
                    Y = zone.Position.Y,
                    Z = zone.Position.Z
                },
                Radius = zone.Radius,
                AllowedCoresSubtype = (zone.AllowedCoresSubtype ?? new List<string>())
                    .Where(id => !string.IsNullOrWhiteSpace(id))
                    .ToArray(),
                ForceOff = zone.ForceOff
            };
        }

        private static UpgradeModuleAllowanceData ConvertToUpgradeModuleAllowanceData(UpgradeModuleAllowance allowance)
        {
            if (allowance == null)
            {
                return new UpgradeModuleAllowanceData
                {
                    UniqueName = string.Empty,
                    TypeId = string.Empty,
                    SubtypeId = string.Empty
                };
            }

            return new UpgradeModuleAllowanceData
            {
                UniqueName = allowance.UniqueName ?? string.Empty,
                TypeId = allowance.TypeId ?? string.Empty,
                SubtypeId = allowance.SubtypeId ?? string.Empty,
                MaxCount = allowance.MaxCount
            };
        }

        private static UpgradeModuleConfigData ConvertToUpgradeModuleConfigData(UpgradeModuleConfig module)
        {
            if (module == null)
            {
                return new UpgradeModuleConfigData
                {
                    TypeId = string.Empty,
                    SubtypeId = string.Empty,
                    UniqueName = string.Empty,
                    Modifiers = Array.Empty<UpgradeStatModifierData>(),
                    BlockLimitModifiers = Array.Empty<BlockLimitModifierData>(),
                    CapacityModifiers = Array.Empty<CapacityModifierData>()
                };
            }

            return new UpgradeModuleConfigData
            {
                TypeId = module.TypeId ?? string.Empty,
                SubtypeId = module.SubtypeId ?? string.Empty,
                UniqueName = module.UniqueName ?? string.Empty,
                Modifiers = (module.Modifiers ?? Array.Empty<UpgradeStatModifier>())
                    .Where(modifier => modifier != null)
                    .Select(ConvertToUpgradeStatModifierData)
                    .ToArray(),
                BlockLimitModifiers = (module.BlockLimitModifiers ?? Array.Empty<BlockLimitModifier>())
                    .Where(modifier => modifier != null)
                    .Select(ConvertToBlockLimitModifierData)
                    .ToArray(),
                CapacityModifiers = (module.CapacityModifiers ?? Array.Empty<CapacityModifier>())
                    .Where(modifier => modifier != null)
                    .Select(ConvertToCapacityModifierData)
                    .ToArray()
            };
        }

        private static UpgradeStatModifierData ConvertToUpgradeStatModifierData(UpgradeStatModifier modifier)
        {
            if (modifier == null)
            {
                return new UpgradeStatModifierData
                {
                    Stat = string.Empty
                };
            }

            return new UpgradeStatModifierData
            {
                Stat = modifier.Stat ?? string.Empty,
                Value = modifier.Value,
                ModifierType = (UpgradeModifierOperationData)(int)modifier.ModifierType
            };
        }

        private static BlockLimitModifierData ConvertToBlockLimitModifierData(BlockLimitModifier modifier)
        {
            if (modifier == null)
            {
                return new BlockLimitModifierData
                {
                    BlockLimitName = string.Empty
                };
            }

            return new BlockLimitModifierData
            {
                BlockLimitName = modifier.BlockLimitName ?? string.Empty,
                Value = modifier.Value,
                ModifierType = (UpgradeModifierOperationData)(int)modifier.ModifierType
            };
        }

        private static CapacityModifierData ConvertToCapacityModifierData(CapacityModifier modifier)
        {
            if (modifier == null)
            {
                return new CapacityModifierData
                {
                    Stat = string.Empty
                };
            }

            return new CapacityModifierData
            {
                Stat = modifier.Stat ?? string.Empty,
                Value = modifier.Value,
                ModifierType = (UpgradeModifierOperationData)(int)modifier.ModifierType
            };
        }

        private static BlockLimitData ConvertToBlockLimitData(BlockLimit limit)
        {
            if (limit == null)
            {
                return new BlockLimitData
                {
                    Name = string.Empty,
                    BlockGroupNames = Array.Empty<string>(),
                    ExcludedBlockGroupNames = Array.Empty<string>(),
                    AllowedDirections = Array.Empty<DirectionTypeData>()
                };
            }

            return new BlockLimitData
            {
                Name = limit.Name ?? string.Empty,
                BlockGroupNames = (limit.BlockGroupsShortHand ?? Array.Empty<string>())
                    .Where(name => !string.IsNullOrWhiteSpace(name))
                    .ToArray(),
                ExcludedBlockGroupNames = (limit.ExcludedBlockGroupsShortHand ?? Array.Empty<string>())
                    .Where(name => !string.IsNullOrWhiteSpace(name))
                    .ToArray(),
                MaxCount = limit.MaxCount,
                MaxCountPerDirection = limit.MaxCountPerDirection,
                DirectionBudgets = (limit.DirectionBudgets ?? Array.Empty<DirectionBudget>())
                    .Where(budget => budget != null)
                    .Select(budget => new DirectionBudgetData
                    {
                        Direction = (DirectionTypeData)(int)budget.Direction,
                        MaxCount = budget.MaxCount
                    }).ToArray(),
                LimitVisibility = (LimitVisibilityData)(int)limit.LimitVisibility,
                CrossConnectorPunishment = limit.CrossConnectorPunishment,
                PunishByNoFlyZone = limit.PunishByNoFlyZone,
                PunishmentType = (PunishmentTypeData)(int)limit.PunishmentType,
                AllowedDirections = (limit.AllowedDirections ?? new List<DirectionType>())
                    .Select(direction => (DirectionTypeData)(int)direction)
                    .ToArray(),
                IsCriticalLimit = limit.IsCriticalLimit,
                IgnoredByNpc = limit.IgnoredByNpc
            };
        }

        private static BlockGroupData ConvertToBlockGroupData(BlockGroup group)
        {
            if (group == null)
            {
                return new BlockGroupData
                {
                    Name = string.Empty,
                    BlockTypes = Array.Empty<BlockTypeData>()
                };
            }

            return new BlockGroupData
            {
                Name = group.Name ?? string.Empty,
                BlockTypes = (group.BlockTypes ?? new List<BlockType>())
                    .Where(blockType => blockType != null)
                    .Select(ConvertToBlockTypeData)
                    .ToArray()
            };
        }

        private static BlockTypeData ConvertToBlockTypeData(BlockType blockType)
        {
            if (blockType == null)
            {
                return new BlockTypeData
                {
                    TypeId = string.Empty,
                    SubtypeId = string.Empty
                };
            }

            return new BlockTypeData
            {
                TypeId = blockType.TypeId ?? string.Empty,
                SubtypeId = blockType.SubtypeId ?? string.Empty,
                CountWeight = blockType.CountWeight,
                PrimaryDirection = (DirectionTypeData)(int)blockType.PrimaryDirection
            };
        }

        internal static GridModifiersData ConvertToGridModifiersData(GridModifiers modifiers)
        {
            if (modifiers == null)
            {
                return new GridModifiersData
                {
                    AssemblerSpeed = 1,
                    DrillHarvestMultiplier = 1,
                    GyroEfficiency = 1,
                    GyroForce = 1,
                    PowerProducersOutput = 1,
                    RefineEfficiency = 1,
                    RefineSpeed = 1,
                    ThrusterEfficiency = 1,
                    ThrusterForce = 1
                };
            }

            return new GridModifiersData
            {
                AssemblerSpeed = modifiers.AssemblerSpeed,
                DrillHarvestMultiplier = modifiers.DrillHarvestMultiplier,
                GyroEfficiency = modifiers.GyroEfficiency,
                GyroForce = modifiers.GyroForce,
                PowerProducersOutput = modifiers.PowerProducersOutput,
                RefineEfficiency = modifiers.RefineEfficiency,
                RefineSpeed = modifiers.RefineSpeed,
                ThrusterEfficiency = modifiers.ThrusterEfficiency,
                ThrusterForce = modifiers.ThrusterForce,
            };
        }
        
        internal static SpeedModifiersData ConvertToSpeedModifiersData(SpeedModifiers modifiers)
        {
            if (modifiers == null)
            {
                return new SpeedModifiersData
                {
                    MaxSpeed = 0.0f,
                    MaxAngularVelocity = 0.0f,
                    MaxBoost = 0.0f,
                    BoostDuration = 10f,
                    BoostCoolDown = 60f,
                    BoostResistance = 0f,
                    MinimumFrictionSpeedAbsolute = 0f,
                    MaximumFrictionSpeedAbsolute = 0f,
                    MaximumFrictionDeceleration = 0f,
                    MinimumFrictionSpeedModifier = 0f,
                    MaximumFrictionSpeedModifier = 0f,
                    FrictionCurve = Array.Empty<FrictionCurveSegmentData>(),
                    CruiseFrictionMultiplier = 1f,
                    CruiseAccelerationThreshold = 0.05f,
                    AtmosphericFriction = null
                };
            }

            return new SpeedModifiersData
            {
                MaxSpeed = modifiers.MaxSpeed,
                MaxAngularVelocity = modifiers.MaxAngularVelocity,
                MaxBoost = modifiers.MaxBoost,
                BoostDuration = modifiers.BoostDuration,
                BoostCoolDown = modifiers.BoostCoolDown,
                BoostResistance = modifiers.MaximumFrictionDeceleration,
                MinimumFrictionSpeedAbsolute = modifiers.MinimumFrictionSpeedAbsolute,
                MaximumFrictionSpeedAbsolute = modifiers.MaximumFrictionSpeedAbsolute,
                MaximumFrictionDeceleration = modifiers.MaximumFrictionDeceleration,
                MinimumFrictionSpeedModifier = modifiers.MinimumFrictionSpeedModifier,
                MaximumFrictionSpeedModifier = modifiers.MaximumFrictionSpeedModifier,
                FrictionCurve = ConvertToFrictionCurveData(modifiers.FrictionCurve),
                CruiseFrictionMultiplier = modifiers.CruiseFrictionMultiplier,
                CruiseAccelerationThreshold = modifiers.CruiseAccelerationThreshold,
                AtmosphericFriction = ConvertToAtmosphericFrictionData(modifiers.AtmosphericFriction)
            };
        }

        private static FrictionCurveSegmentData[] ConvertToFrictionCurveData(FrictionCurve curve)
        {
            if (curve?.Segments == null || curve.Segments.Length == 0)
                return Array.Empty<FrictionCurveSegmentData>();

            var segments = new List<FrictionCurveSegmentData>();
            for (var i = 0; i < curve.Segments.Length; i++)
            {
                var segment = curve.Segments[i];
                if (segment == null) continue;

                segments.Add(new FrictionCurveSegmentData
                {
                    StartSpeed = segment.StartSpeed,
                    EndSpeed = segment.EndSpeed,
                    StartDeceleration = segment.StartDeceleration,
                    EndDeceleration = segment.EndDeceleration
                });
            }

            return segments.ToArray();
        }

        private static AtmosphericFrictionData ConvertToAtmosphericFrictionData(AtmosphericFrictionSettings settings)
        {
            if (settings == null) return null;

            return new AtmosphericFrictionData
            {
                Enabled = settings.Enabled,
                FrictionCurve = ConvertToFrictionCurveData(settings.FrictionCurve),
                CruiseFrictionMultiplier = settings.CruiseFrictionMultiplier,
                CruiseAccelerationThreshold = settings.CruiseAccelerationThreshold,
                AirDensityThreshold = settings.AirDensityThreshold
            };
        }

        internal static GridDefenseModifiersData ConvertToDefenseModifiersData(GridDefenseModifiers modifiers)
        {
            if (modifiers == null)
            {
                return new GridDefenseModifiersData
                {
                    Bullet = 1f,
                    PostShield = 1f,
                    Duration = 0f,
                    Cooldown = 0f,
                    Rocket = 1f,
                    Explosion = 1f,
                    Environment = 1f,
                    Energy = 1f,
                    Kinetic = 1f
                };
            }

            return new GridDefenseModifiersData
            {
                Bullet = modifiers.Bullet,
                PostShield = modifiers.PostShield,
                Duration = modifiers.Duration,
                Cooldown = modifiers.Cooldown,
                Rocket = modifiers.Rocket,
                Explosion = modifiers.Explosion,
                Environment = modifiers.Environment,
                Energy = modifiers.Energy,
                Kinetic = modifiers.Kinetic
            };
        }

        internal static GridModifiers ConvertFromGridModifiersData(GridModifiersData modifiers)
        {
            if (modifiers == null) return null;

            return new GridModifiers
            {
                AssemblerSpeed = modifiers.AssemblerSpeed,
                DrillHarvestMultiplier = modifiers.DrillHarvestMultiplier,
                GyroEfficiency = modifiers.GyroEfficiency,
                GyroForce = modifiers.GyroForce,
                PowerProducersOutput = modifiers.PowerProducersOutput,
                RefineEfficiency = modifiers.RefineEfficiency,
                RefineSpeed = modifiers.RefineSpeed,
                ThrusterEfficiency = modifiers.ThrusterEfficiency,
                ThrusterForce = modifiers.ThrusterForce
            };
        }

        internal static SpeedModifiers ConvertFromSpeedModifiersData(SpeedModifiersData modifiers)
        {
            if (modifiers == null) return null;

            return new SpeedModifiers
            {
                MaxSpeed = modifiers.MaxSpeed,
                MaxAngularVelocity = modifiers.MaxAngularVelocity,
                MaxBoost = modifiers.MaxBoost,
                BoostDuration = modifiers.BoostDuration,
                BoostCoolDown = modifiers.BoostCoolDown,
                MinimumFrictionSpeedAbsolute = modifiers.MinimumFrictionSpeedAbsolute,
                MaximumFrictionSpeedAbsolute = modifiers.MaximumFrictionSpeedAbsolute,
                MinimumFrictionSpeedModifier = modifiers.MinimumFrictionSpeedModifier,
                MaximumFrictionSpeedModifier = modifiers.MaximumFrictionSpeedModifier,
                MaximumFrictionDeceleration = modifiers.MaximumFrictionDeceleration,
                CruiseFrictionMultiplier = modifiers.CruiseFrictionMultiplier,
                CruiseAccelerationThreshold = modifiers.CruiseAccelerationThreshold,
                FrictionCurve = ConvertFromFrictionCurveData(modifiers.FrictionCurve),
                AtmosphericFriction = ConvertFromAtmosphericFrictionData(modifiers.AtmosphericFriction)
            };
        }

        private static FrictionCurve ConvertFromFrictionCurveData(FrictionCurveSegmentData[] segments)
        {
            if (segments == null || segments.Length == 0) return null;

            var result = new FrictionCurve { Segments = new FrictionCurveSegment[segments.Length] };
            for (var i = 0; i < segments.Length; i++)
            {
                var segment = segments[i];
                if (segment == null) continue;
                result.Segments[i] = new FrictionCurveSegment
                {
                    StartSpeed = segment.StartSpeed,
                    EndSpeed = segment.EndSpeed,
                    StartDeceleration = segment.StartDeceleration,
                    EndDeceleration = segment.EndDeceleration
                };
            }
            return result;
        }

        private static AtmosphericFrictionSettings ConvertFromAtmosphericFrictionData(
            AtmosphericFrictionData settings)
        {
            if (settings == null) return null;

            return new AtmosphericFrictionSettings
            {
                Enabled = settings.Enabled,
                FrictionCurve = ConvertFromFrictionCurveData(settings.FrictionCurve),
                CruiseFrictionMultiplier = settings.CruiseFrictionMultiplier,
                CruiseAccelerationThreshold = settings.CruiseAccelerationThreshold,
                AirDensityThreshold = settings.AirDensityThreshold
            };
        }

        internal static GridDefenseModifiers ConvertFromDefenseModifiersData(
            GridDefenseModifiersData modifiers)
        {
            if (modifiers == null) return null;

            return new GridDefenseModifiers
            {
                Bullet = modifiers.Bullet,
                PostShield = modifiers.PostShield,
                Duration = modifiers.Duration,
                Cooldown = modifiers.Cooldown,
                Rocket = modifiers.Rocket,
                Explosion = modifiers.Explosion,
                Environment = modifiers.Environment,
                Energy = modifiers.Energy,
                Kinetic = modifiers.Kinetic
            };
        }

        // ===== Public API Methods =====
        //
        // NOTE:
        // These methods are still useful internally, and the factory wraps them.
        // Consumers should NOT call them directly across assemblies.

        public static ShipCoreData GetGridCore(long gridId)
        {
            var grid = MyAPIGateway.Entities.GetEntityById(gridId) as MyCubeGrid;
            if (grid == null) return ConvertToShipCoreData(Session.Config.SelectedNoCore);

            try
            {
                var groupData = MyAPIGateway.GridGroups.GetGridGroup(GridLinkTypeEnum.Mechanical, grid);
                if (groupData == null) return ConvertToShipCoreData(Session.Config.SelectedNoCore);

                GroupComponent groupComponent;
                return !Session.GroupDict.TryGetValue(groupData, out groupComponent) ? 
                    ConvertToShipCoreData(Session.Config.SelectedNoCore) : 
                    ConvertToShipCoreData(groupComponent.ShipCore ?? Session.Config.SelectedNoCore,
                        groupComponent.Deactivated, groupComponent);
            }
            catch (Exception ex)
            {
                Utils.Log($"ModAPI.GetGridCore: Exception - {ex}");
                return ConvertToShipCoreData(Session.Config.SelectedNoCore);
            }
        }

        public static ShipCoreData GetCoreBySubtypeId(string subtypeId)
        {
            if (string.IsNullOrEmpty(subtypeId)) return ConvertToShipCoreData(Session.Config.SelectedNoCore);

            try
            {
                return ConvertToShipCoreData(Session.Config.GetShipCoreByTypeId(subtypeId));
            }
            catch (Exception ex)
            {
                Utils.Log($"ModAPI.GetCoreBySubtypeId: Exception - {ex}");
                return ConvertToShipCoreData(Session.Config.SelectedNoCore);
            }
        }

        public static List<ShipCoreData> GetAllCoreConfigs()
        {
            try
            {
                return Session.Config.ShipCores.Select(core => ConvertToShipCoreData(core)).ToList();
            }
            catch (Exception ex)
            {
                Utils.Log($"ModAPI.GetAllCoreConfigs: Exception - {ex}");
                return new List<ShipCoreData>();
            }
        }

        /// <summary>
        /// Gets a snapshot of the full effective framework configuration.
        /// </summary>
        public static ModConfigData GetFullConfig()
        {
            try
            {
                return ConvertToModConfigData(Session.Config);
            }
            catch (Exception ex)
            {
                Utils.Log($"ModAPI.GetFullConfig: Exception - {ex}");
                return null;
            }
        }

        public static Dictionary<string, LimitStatusData> GetBlockLimitsStatus(long gridId)
        {
            var result = new Dictionary<string, LimitStatusData>();
            var grid = MyAPIGateway.Entities.GetEntityById(gridId) as MyCubeGrid;
            if (grid == null) return result;

            try
            {
                var groupData = MyAPIGateway.GridGroups.GetGridGroup(GridLinkTypeEnum.Mechanical, grid);
                if (groupData == null) return result;

                GroupComponent groupComponent;
                if (!Session.GroupDict.TryGetValue(groupData, out groupComponent))
                    return result;

                var shipCore = groupComponent.ShipCore ?? Session.Config.SelectedNoCore;
                var configuredLimits = shipCore?.BlockLimits ?? Array.Empty<BlockLimit>();
                foreach (var configuredLimit in configuredLimits)
                {
                    if (configuredLimit == null || string.IsNullOrWhiteSpace(configuredLimit.Name)) continue;
                    if (!groupComponent.ShouldEvaluateBlockLimit(configuredLimit)) continue;

                    var max = groupComponent.GetEffectiveMaxCount(configuredLimit);
                    result[configuredLimit.Name] = new LimitStatusData
                    {
                        Name = configuredLimit.Name,
                        Current = 0d,
                        Max = max,
                        IsOverLimit = false
                    };
                }

                foreach (var kvp in groupComponent.Limits)
                {
                    var limit = kvp.Key;
                    var bucket = kvp.Value;
                    if (limit == null || bucket == null || string.IsNullOrWhiteSpace(limit.Name)) continue;
                    if (!groupComponent.ShouldEvaluateBlockLimit(limit)) continue;

                    double totalWeight;
                    lock (bucket.BucketLock)
                    {
                        totalWeight = bucket.TotalWeight;
                    }

                    var max = groupComponent.GetEffectiveMaxCount(limit);
                    result[limit.Name] = new LimitStatusData
                    {
                        Name = limit.Name,
                        Current = totalWeight,
                        Max = max,
                        IsOverLimit = totalWeight > max
                    };
                }
            }
            catch (Exception ex)
            {
                Utils.Log($"ModAPI.GetBlockLimitsStatus: Exception - {ex}");
            }

            return result;
        }

        public static bool IsBlockAllowed(long gridId, string typeId, string subtypeId, int count)
        {
            var grid = MyAPIGateway.Entities.GetEntityById(gridId) as MyCubeGrid;
            if (grid == null || string.IsNullOrEmpty(typeId)) return true;

            try
            {
                var groupData = MyAPIGateway.GridGroups.GetGridGroup(GridLinkTypeEnum.Mechanical, grid);
                if (groupData == null) return true;

                GroupComponent groupComponent;
                if (!Session.GroupDict.TryGetValue(groupData, out groupComponent))
                    return true;

                // Per-block-type limits only (this API's contract), evaluated against the
                // upgrade-module-adjusted effective max instead of raw MaxCount. Allocation-free.
                var blockKey = new BlockKey(typeId, subtypeId ?? string.Empty);
                return !LimitEvaluation.WouldExceedCountLimits(groupComponent, blockKey, count);
            }
            catch (Exception ex)
            {
                Utils.Log($"ModAPI.IsBlockAllowed: Exception - {ex}");
                return true;
            }
        }

        public static GridModifiersData GetGridModifiers(long gridId)
        {
            var grid = MyAPIGateway.Entities.GetEntityById(gridId) as MyCubeGrid;
            if (grid == null) return ConvertToGridModifiersData(null);
            try
            {
                var groupData = MyAPIGateway.GridGroups.GetGridGroup(GridLinkTypeEnum.Mechanical, grid);
                if (groupData == null) return ConvertToGridModifiersData(null);

                GroupComponent groupComponent;
                return ConvertToGridModifiersData(!Session.GroupDict.TryGetValue(groupData, out groupComponent) ? null : groupComponent.Modifiers);
            }
            catch (Exception ex)
            {
                Utils.Log($"ModAPI.GetGridModifiers: Exception - {ex}");
                return ConvertToGridModifiersData(null);
            }
        }

        public static float GetMaxSpeed(long gridId)
        {
            var grid = MyAPIGateway.Entities.GetEntityById(gridId) as MyCubeGrid;
            if (grid == null) return 100f;

            try
            {
                var groupData = MyAPIGateway.GridGroups.GetGridGroup(GridLinkTypeEnum.Mechanical, grid);
                if (groupData == null) return 100f;

                GroupComponent groupComponent;
                if (!Session.GroupDict.TryGetValue(groupData, out groupComponent))
                    return 100f;

                if (Session.IsServer)
                    RefreshAuthoritativeSpeedState(groupComponent);
                return groupComponent.EffectiveSpeedLimitMetersPerSecond;
            }
            catch (Exception ex)
            {
                Utils.Log($"ModAPI.GetMaxSpeed: Exception - {ex}");
                return 100f;
            }
        }

        public static bool IsBoostActive(long gridId)
        {
            try
            {
                GroupComponent groupComponent;
                if (!TryGetGroupComponent(gridId, out groupComponent)) return false;

                if (Session.IsServer)
                    RefreshAuthoritativeSpeedState(groupComponent);
                lock (groupComponent.SpeedStateLock)
                {
                    return groupComponent.EffectiveBoostEnabled;
                }
            }
            catch (Exception ex)
            {
                Utils.Log($"ModAPI.IsBoostActive: Exception - {ex}");
                return false;
            }
        }

        public static ShipCoreData GetNoCoreConfig()
        {
            try
            {
                return ConvertToShipCoreData(Session.Config.SelectedNoCore ?? new ShipCore());
            }
            catch (Exception ex)
            {
                Utils.Log($"ModAPI.GetNoCoreConfig: Exception - {ex}");
                return ConvertToShipCoreData(null);
            }
        }
    }
}
