using System;
using System.Collections.Generic;
using Sandbox.ModAPI;
using VRage;
using VRage.Game.ModAPI;
using VRage.ModAPI;
using VRage.Utils;

namespace ShipCoreFramework
{
    /// <summary>
    /// Shared API v4 consumer implementation. Use ShipCoreFrameworkClientApi on remote clients and
    /// ShipCoreFrameworkServerApi on server processes.
    /// </summary>
    public abstract class ShipCoreFrameworkApiBase
    {
        private readonly long _apiId;
        private readonly ApiProviderRoleData _expectedRole;
        private Func<int, Func<object, object>> _factory;

        public bool ProviderReady { get; private set; }
        public bool ConfigReady { get; private set; }
        public bool RuntimeSnapshotReady { get; private set; }
        public string ConfigurationError { get; private set; }
        public int ProviderApiVersion { get; private set; }
        public ApiProviderRoleData ProviderRole { get; private set; }
        public ApiCapabilityData Capabilities { get; private set; }

        public event Action<CoreActivatedEventArgs> CoreActivated;
        public event Action<CoreDeactivatedEventArgs> CoreDeactivated;
        public event Action<LimitsRecalculatedEventArgs> LimitsRecalculated;
        public event Action<LimitsEnforcedEventArgs> LimitsEnforced;
        public event Action<BoostEventArgs> BoostActivated;
        public event Action<BoostEventArgs> BoostDeactivated;
        public event Action<ActiveDefenseEventArgs> ActiveDefenseActivated;
        public event Action<ActiveDefenseEventArgs> ActiveDefenseDeactivated;
        public event Action<GridGroupEventArgs> GridAddedToGroup;
        public event Action<GridGroupEventArgs> GridRemovedFromGroup;
        public event Action<ConfigReceivedEventArgs> ConfigReceived;
        public event Action<RuntimeSnapshotReadyEventArgs> RuntimeReady;

        public event Action<CoreActivatedEventArgs, IMyCubeGrid, IMyGridGroupData> CoreActivatedResolved;
        public event Action<CoreDeactivatedEventArgs, IMyCubeGrid, IMyGridGroupData> CoreDeactivatedResolved;
        public event Action<LimitsRecalculatedEventArgs, IMyCubeGrid, IMyGridGroupData> LimitsRecalculatedResolved;
        public event Action<LimitsEnforcedEventArgs, IMyCubeGrid, IMyGridGroupData> LimitsEnforcedResolved;
        public event Action<BoostEventArgs, IMyCubeGrid, IMyGridGroupData> BoostActivatedResolved;
        public event Action<BoostEventArgs, IMyCubeGrid, IMyGridGroupData> BoostDeactivatedResolved;
        public event Action<ActiveDefenseEventArgs, IMyCubeGrid, IMyGridGroupData>
            ActiveDefenseActivatedResolved;
        public event Action<ActiveDefenseEventArgs, IMyCubeGrid, IMyGridGroupData>
            ActiveDefenseDeactivatedResolved;
        public event Action<GridGroupEventArgs, IMyCubeGrid, IMyCubeGrid, IMyGridGroupData>
            GridAddedToGroupResolved;
        public event Action<GridGroupEventArgs, IMyCubeGrid, IMyCubeGrid, IMyGridGroupData>
            GridRemovedFromGroupResolved;

        protected ShipCoreFrameworkApiBase(long apiId, ApiProviderRoleData expectedRole)
        {
            _apiId = apiId;
            _expectedRole = expectedRole;
        }

        public void Register()
        {
            MyAPIGateway.Utilities.RegisterMessageHandler(_apiId, OnApiPayloadReceived);
            MyAPIGateway.Utilities.RegisterMessageHandler(ApiConstants.EVENT_CORE_ACTIVATED, OnCoreActivated);
            MyAPIGateway.Utilities.RegisterMessageHandler(ApiConstants.EVENT_CORE_DEACTIVATED, OnCoreDeactivated);
            MyAPIGateway.Utilities.RegisterMessageHandler(ApiConstants.EVENT_LIMITS_RECALCULATED,
                OnLimitsRecalculated);
            MyAPIGateway.Utilities.RegisterMessageHandler(ApiConstants.EVENT_LIMITS_ENFORCED, OnLimitsEnforced);
            MyAPIGateway.Utilities.RegisterMessageHandler(ApiConstants.EVENT_BOOST_ACTIVATED, OnBoostActivated);
            MyAPIGateway.Utilities.RegisterMessageHandler(ApiConstants.EVENT_BOOST_DEACTIVATED,
                OnBoostDeactivated);
            MyAPIGateway.Utilities.RegisterMessageHandler(ApiConstants.EVENT_ACTIVE_DEFENSE_ACTIVATED,
                OnActiveDefenseActivated);
            MyAPIGateway.Utilities.RegisterMessageHandler(ApiConstants.EVENT_ACTIVE_DEFENSE_DEACTIVATED,
                OnActiveDefenseDeactivated);
            MyAPIGateway.Utilities.RegisterMessageHandler(ApiConstants.EVENT_GRID_ADDED_TO_GROUP,
                OnGridAddedToGroup);
            MyAPIGateway.Utilities.RegisterMessageHandler(ApiConstants.EVENT_GRID_REMOVED_FROM_GROUP,
                OnGridRemovedFromGroup);
            MyAPIGateway.Utilities.RegisterMessageHandler(ApiConstants.EVENT_CONFIG_RECEIVED, OnConfigReceived);
            MyAPIGateway.Utilities.RegisterMessageHandler(ApiConstants.EVENT_RUNTIME_SNAPSHOT_READY,
                OnRuntimeReady);
        }

        public void Unregister()
        {
            MyAPIGateway.Utilities.UnregisterMessageHandler(_apiId, OnApiPayloadReceived);
            MyAPIGateway.Utilities.UnregisterMessageHandler(ApiConstants.EVENT_CORE_ACTIVATED, OnCoreActivated);
            MyAPIGateway.Utilities.UnregisterMessageHandler(ApiConstants.EVENT_CORE_DEACTIVATED,
                OnCoreDeactivated);
            MyAPIGateway.Utilities.UnregisterMessageHandler(ApiConstants.EVENT_LIMITS_RECALCULATED,
                OnLimitsRecalculated);
            MyAPIGateway.Utilities.UnregisterMessageHandler(ApiConstants.EVENT_LIMITS_ENFORCED,
                OnLimitsEnforced);
            MyAPIGateway.Utilities.UnregisterMessageHandler(ApiConstants.EVENT_BOOST_ACTIVATED,
                OnBoostActivated);
            MyAPIGateway.Utilities.UnregisterMessageHandler(ApiConstants.EVENT_BOOST_DEACTIVATED,
                OnBoostDeactivated);
            MyAPIGateway.Utilities.UnregisterMessageHandler(ApiConstants.EVENT_ACTIVE_DEFENSE_ACTIVATED,
                OnActiveDefenseActivated);
            MyAPIGateway.Utilities.UnregisterMessageHandler(ApiConstants.EVENT_ACTIVE_DEFENSE_DEACTIVATED,
                OnActiveDefenseDeactivated);
            MyAPIGateway.Utilities.UnregisterMessageHandler(ApiConstants.EVENT_GRID_ADDED_TO_GROUP,
                OnGridAddedToGroup);
            MyAPIGateway.Utilities.UnregisterMessageHandler(ApiConstants.EVENT_GRID_REMOVED_FROM_GROUP,
                OnGridRemovedFromGroup);
            MyAPIGateway.Utilities.UnregisterMessageHandler(ApiConstants.EVENT_CONFIG_RECEIVED,
                OnConfigReceived);
            MyAPIGateway.Utilities.UnregisterMessageHandler(ApiConstants.EVENT_RUNTIME_SNAPSHOT_READY,
                OnRuntimeReady);
            Reset();
        }

        public ApiReadResult<ApiReadinessData> RefreshReadiness()
        {
            ApiReadResult<ApiReadinessData> result =
                InvokeBinary<ApiReadinessData>(ApiMethodId.GetReadiness_Binary, null);
            if (result.Success && result.Value != null)
            {
                ProviderRole = result.Value.Role;
                ConfigReady = result.Value.ConfigReady;
                RuntimeSnapshotReady = result.Value.RuntimeSnapshotReady;
                ConfigurationError = result.Value.ConfigurationError ?? string.Empty;
            }
            return result;
        }

        public ApiReadResult<bool> TryGetRuntimeStateAvailability(long gridId)
        {
            return InvokePrimitive<bool>(ApiMethodId.GetRuntimeStateAvailability, gridId);
        }

        public ApiReadResult<ShipCoreData> TryGetGridCore(long gridId)
        {
            return InvokeBinary<ShipCoreData>(ApiMethodId.GetGridCore_Binary, gridId);
        }

        public ApiReadResult<ShipCoreData> TryGetCoreBySubtypeId(string subtypeId)
        {
            return InvokeBinary<ShipCoreData>(ApiMethodId.GetCoreBySubtypeId_Binary, subtypeId);
        }

        public ApiReadResult<List<ShipCoreData>> TryGetAllCoreConfigs()
        {
            return InvokeBinary<List<ShipCoreData>>(ApiMethodId.GetAllCoreConfigs_Binary, null);
        }

        public ApiReadResult<Dictionary<string, LimitStatusData>> TryGetBlockLimitsStatus(long gridId)
        {
            return InvokeBinary<Dictionary<string, LimitStatusData>>(
                ApiMethodId.GetBlockLimitsStatus_Binary, gridId);
        }

        public ApiReadResult<bool> TryIsBlockAllowed(long gridId, string typeId, string subtypeId, int count)
        {
            return InvokePrimitive<bool>(ApiMethodId.IsBlockAllowed,
                MyTuple.Create(gridId, typeId, subtypeId, count));
        }

        public ApiReadResult<GridModifiersData> TryGetGridModifiers(long gridId)
        {
            return InvokeBinary<GridModifiersData>(ApiMethodId.GetGridModifiers_Binary, gridId);
        }

        public ApiReadResult<float> TryGetMaxSpeed(long gridId)
        {
            return InvokePrimitive<float>(ApiMethodId.GetMaxSpeed, gridId);
        }

        public ApiReadResult<bool> TryIsBoostActive(long gridId)
        {
            return InvokePrimitive<bool>(ApiMethodId.IsBoostActive, gridId);
        }

        public ApiReadResult<ShipCoreData> TryGetNoCoreConfig()
        {
            return InvokeBinary<ShipCoreData>(ApiMethodId.GetNoCoreConfig_Binary, null);
        }

        public ApiReadResult<ModConfigData> TryGetFullConfig()
        {
            return InvokeBinary<ModConfigData>(ApiMethodId.GetFullConfig_Binary, null);
        }

        public ApiReadResult<SpeedModifiersData> TryGetSpeedModifiers(long gridId)
        {
            return InvokeBinary<SpeedModifiersData>(ApiMethodId.GetSpeedModifiers_Binary, gridId);
        }

        public ApiReadResult<float> TryGetBoostResistance(long gridId)
        {
            return InvokePrimitive<float>(ApiMethodId.GetBoostResistance, gridId);
        }

        public ApiReadResult<float> TryGetBaseMaxSpeed(long gridId)
        {
            return InvokePrimitive<float>(ApiMethodId.GetBaseMaxSpeed, gridId);
        }

        public ApiReadResult<float> TryGetMaxBoostMultiplier(long gridId)
        {
            return InvokePrimitive<float>(ApiMethodId.GetMaxBoostMultiplier, gridId);
        }

        public ApiReadResult<float> TryGetBoostDuration(long gridId)
        {
            return InvokePrimitive<float>(ApiMethodId.GetBoostDuration, gridId);
        }

        public ApiReadResult<float> TryGetBoostCooldown(long gridId)
        {
            return InvokePrimitive<float>(ApiMethodId.GetBoostCooldown, gridId);
        }

        public ApiReadResult<bool> TryGetFrictionEnabledForGroup(long gridId)
        {
            return InvokePrimitive<bool>(ApiMethodId.GetFrictionEnabledForGroup, gridId);
        }

        public ApiReadResult<float> TryGetFrictionMaximumDecelerationForGroup(long gridId)
        {
            return InvokePrimitive<float>(ApiMethodId.GetFrictionMaximumDecelerationForGroup, gridId);
        }

        public ApiReadResult<int> TryGetFrictionSpeedValueMode()
        {
            return InvokePrimitive<int>(ApiMethodId.GetFrictionSpeedValueMode, null);
        }

        public ApiReadResult<float> TryGetFrictionMinimumSpeedAbsoluteForGroup(long gridId)
        {
            return InvokePrimitive<float>(ApiMethodId.GetFrictionMinimumSpeedAbsoluteForGroup, gridId);
        }

        public ApiReadResult<float> TryGetFrictionMaximumSpeedAbsoluteForGroup(long gridId)
        {
            return InvokePrimitive<float>(ApiMethodId.GetFrictionMaximumSpeedAbsoluteForGroup, gridId);
        }

        public ApiReadResult<float> TryGetFrictionMinimumSpeedModifierForGroup(long gridId)
        {
            return InvokePrimitive<float>(ApiMethodId.GetFrictionMinimumSpeedModifierForGroup, gridId);
        }

        public ApiReadResult<float> TryGetFrictionMaximumSpeedModifierForGroup(long gridId)
        {
            return InvokePrimitive<float>(ApiMethodId.GetFrictionMaximumSpeedModifierForGroup, gridId);
        }

        public ApiReadResult<bool> TryIsGroupDeactivated(long gridId)
        {
            return InvokePrimitive<bool>(ApiMethodId.IsGroupDeactivated, gridId);
        }

        protected ApiReadResult<bool> InvokeCommand(int methodId, object argument)
        {
            ApiReadStatusData status;
            object value;
            string error;
            if (!TryInvoke(methodId, argument, out status, out value, out error))
                return Result(status, false, error);
            if (!(value is MyTuple<bool, string>))
                return Result(ApiReadStatusData.Error, false, "Invalid command response.");
            MyTuple<bool, string> command = (MyTuple<bool, string>)value;
            return command.Item1
                ? Result(ApiReadStatusData.Success, true, string.Empty)
                : Result(ApiReadStatusData.Error, false, command.Item2);
        }

        private void OnApiPayloadReceived(object value)
        {
            try
            {
                MyTuple<int, int, Func<int, Func<object, object>>> payload =
                    (MyTuple<int, int, Func<int, Func<object, object>>>)value;
                ProviderApiVersion = payload.Item1;
                ProviderRole = (ApiProviderRoleData)payload.Item2;
                if (!ApiConstants.IsApiCompatible(ProviderApiVersion) || ProviderRole != _expectedRole)
                {
                    Reset();
                    return;
                }

                _factory = payload.Item3;
                ProviderReady = _factory != null;
                if (!ProviderReady) return;

                ApiReadResult<int> capabilities = InvokePrimitive<int>(ApiMethodId.GetCapabilities, null);
                if (capabilities.Success) Capabilities = (ApiCapabilityData)capabilities.Value;
                RefreshReadiness();
            }
            catch (Exception exception)
            {
                MyLog.Default.WriteLine("[SCF] API v4 payload failed: " + exception);
                Reset();
            }
        }

        protected ApiReadResult<T> InvokePrimitive<T>(int methodId, object argument)
        {
            ApiReadStatusData status;
            object value;
            string error;
            if (!TryInvoke(methodId, argument, out status, out value, out error))
                return Result(status, default(T), error);
            if (!(value is T))
                return Result(ApiReadStatusData.Error, default(T), "Invalid primitive response.");
            return Result(ApiReadStatusData.Success, (T)value, string.Empty);
        }

        private ApiReadResult<T> InvokeBinary<T>(int methodId, object argument) where T : class
        {
            ApiReadStatusData status;
            object value;
            string error;
            if (!TryInvoke(methodId, argument, out status, out value, out error))
                return Result(status, default(T), error);

            byte[] bytes = value as byte[];
            if (bytes == null || bytes.Length == 0)
                return Result(ApiReadStatusData.Error, default(T), "Invalid serialized response.");
            try
            {
                T result = MyAPIGateway.Utilities.SerializeFromBinary<T>(bytes);
                return result == null
                    ? Result(ApiReadStatusData.Error, default(T), "Response deserialization failed.")
                    : Result(ApiReadStatusData.Success, result, string.Empty);
            }
            catch (Exception exception)
            {
                return Result(ApiReadStatusData.Error, default(T), exception.Message);
            }
        }

        private bool TryInvoke(int methodId, object argument, out ApiReadStatusData status,
            out object value, out string error)
        {
            value = null;
            error = string.Empty;
            if (!ProviderReady || _factory == null)
            {
                status = ApiReadStatusData.ProviderNotReady;
                return false;
            }

            try
            {
                Func<object, object> method = _factory(methodId);
                if (method == null)
                {
                    status = ApiReadStatusData.Unsupported;
                    return false;
                }

                object raw = method.Invoke(argument);
                if (!(raw is MyTuple<int, object>))
                {
                    status = ApiReadStatusData.Error;
                    error = "Invalid API v4 response envelope.";
                    return false;
                }

                MyTuple<int, object> response = (MyTuple<int, object>)raw;
                status = (ApiReadStatusData)response.Item1;
                value = response.Item2;
                if (status == ApiReadStatusData.Success) return true;
                error = status.ToString();
                return false;
            }
            catch (Exception exception)
            {
                status = ApiReadStatusData.Error;
                error = exception.Message;
                return false;
            }
        }

        private static ApiReadResult<T> Result<T>(ApiReadStatusData status, T value, string error)
        {
            return new ApiReadResult<T>
            {
                Status = status,
                Value = value,
                Error = error ?? string.Empty
            };
        }

        private void Reset()
        {
            _factory = null;
            ProviderReady = false;
            ConfigReady = false;
            RuntimeSnapshotReady = false;
            ConfigurationError = string.Empty;
            ProviderApiVersion = 0;
            ProviderRole = ApiProviderRoleData.Unknown;
            Capabilities = ApiCapabilityData.None;
        }

        private static IMyCubeGrid ResolveGrid(long gridId)
        {
            IMyEntity entity;
            return gridId != 0 && MyAPIGateway.Entities.TryGetEntityById(gridId, out entity)
                ? entity as IMyCubeGrid
                : null;
        }

        private static IMyGridGroupData ResolveLogicalGroup(IMyCubeGrid grid)
        {
            return grid == null
                ? null
                : MyAPIGateway.GridGroups.GetGridGroup(GridLinkTypeEnum.Mechanical, grid);
        }

        private void OnCoreActivated(object value)
        {
            if (!ProviderReady) return;
            CoreActivatedEventArgs eventData = Deserialize<CoreActivatedEventArgs>(value);
            if (eventData == null) return;
            if (CoreActivated != null) CoreActivated(eventData);
            if (CoreActivatedResolved == null) return;
            IMyCubeGrid grid = ResolveGrid(eventData.GroupGridId);
            CoreActivatedResolved(eventData, grid, ResolveLogicalGroup(grid));
        }

        private void OnCoreDeactivated(object value)
        {
            if (!ProviderReady) return;
            CoreDeactivatedEventArgs eventData = Deserialize<CoreDeactivatedEventArgs>(value);
            if (eventData == null) return;
            if (CoreDeactivated != null) CoreDeactivated(eventData);
            if (CoreDeactivatedResolved == null) return;
            IMyCubeGrid grid = ResolveGrid(eventData.GroupGridId);
            CoreDeactivatedResolved(eventData, grid, ResolveLogicalGroup(grid));
        }

        private void OnLimitsRecalculated(object value)
        {
            if (!ProviderReady) return;
            LimitsRecalculatedEventArgs eventData = Deserialize<LimitsRecalculatedEventArgs>(value);
            if (eventData == null) return;
            if (LimitsRecalculated != null) LimitsRecalculated(eventData);
            if (LimitsRecalculatedResolved == null) return;
            IMyCubeGrid grid = ResolveGrid(eventData.GroupGridId);
            LimitsRecalculatedResolved(eventData, grid, ResolveLogicalGroup(grid));
        }

        private void OnLimitsEnforced(object value)
        {
            if (!ProviderReady) return;
            LimitsEnforcedEventArgs eventData = Deserialize<LimitsEnforcedEventArgs>(value);
            if (eventData == null) return;
            if (LimitsEnforced != null) LimitsEnforced(eventData);
            if (LimitsEnforcedResolved == null) return;
            IMyCubeGrid grid = ResolveGrid(eventData.GroupGridId);
            LimitsEnforcedResolved(eventData, grid, ResolveLogicalGroup(grid));
        }

        private void OnBoostActivated(object value)
        {
            if (!ProviderReady) return;
            BoostEventArgs eventData = Deserialize<BoostEventArgs>(value);
            if (eventData == null) return;
            if (BoostActivated != null) BoostActivated(eventData);
            if (BoostActivatedResolved == null) return;
            IMyCubeGrid grid = ResolveGrid(eventData.GroupGridId);
            BoostActivatedResolved(eventData, grid, ResolveLogicalGroup(grid));
        }

        private void OnBoostDeactivated(object value)
        {
            if (!ProviderReady) return;
            BoostEventArgs eventData = Deserialize<BoostEventArgs>(value);
            if (eventData == null) return;
            if (BoostDeactivated != null) BoostDeactivated(eventData);
            if (BoostDeactivatedResolved == null) return;
            IMyCubeGrid grid = ResolveGrid(eventData.GroupGridId);
            BoostDeactivatedResolved(eventData, grid, ResolveLogicalGroup(grid));
        }

        private void OnActiveDefenseActivated(object value)
        {
            if (!ProviderReady) return;
            ActiveDefenseEventArgs eventData = Deserialize<ActiveDefenseEventArgs>(value);
            if (eventData == null) return;
            if (ActiveDefenseActivated != null) ActiveDefenseActivated(eventData);
            if (ActiveDefenseActivatedResolved == null) return;
            IMyCubeGrid grid = ResolveGrid(eventData.GroupGridId);
            ActiveDefenseActivatedResolved(eventData, grid, ResolveLogicalGroup(grid));
        }

        private void OnActiveDefenseDeactivated(object value)
        {
            if (!ProviderReady) return;
            ActiveDefenseEventArgs eventData = Deserialize<ActiveDefenseEventArgs>(value);
            if (eventData == null) return;
            if (ActiveDefenseDeactivated != null) ActiveDefenseDeactivated(eventData);
            if (ActiveDefenseDeactivatedResolved == null) return;
            IMyCubeGrid grid = ResolveGrid(eventData.GroupGridId);
            ActiveDefenseDeactivatedResolved(eventData, grid, ResolveLogicalGroup(grid));
        }

        private void OnGridAddedToGroup(object value)
        {
            if (!ProviderReady) return;
            GridGroupEventArgs eventData = Deserialize<GridGroupEventArgs>(value);
            if (eventData == null) return;
            if (GridAddedToGroup != null) GridAddedToGroup(eventData);
            if (GridAddedToGroupResolved == null) return;
            IMyCubeGrid grid = ResolveGrid(eventData.GridId);
            IMyCubeGrid groupGrid = ResolveGrid(eventData.GroupGridId);
            GridAddedToGroupResolved(eventData, grid, groupGrid,
                ResolveLogicalGroup(groupGrid ?? grid));
        }

        private void OnGridRemovedFromGroup(object value)
        {
            if (!ProviderReady) return;
            GridGroupEventArgs eventData = Deserialize<GridGroupEventArgs>(value);
            if (eventData == null) return;
            if (GridRemovedFromGroup != null) GridRemovedFromGroup(eventData);
            if (GridRemovedFromGroupResolved == null) return;
            IMyCubeGrid grid = ResolveGrid(eventData.GridId);
            IMyCubeGrid groupGrid = ResolveGrid(eventData.GroupGridId);
            GridRemovedFromGroupResolved(eventData, grid, groupGrid,
                ResolveLogicalGroup(groupGrid ?? grid));
        }

        private void OnConfigReceived(object value)
        {
            if (!ProviderReady) return;
            ConfigReceivedEventArgs eventData = Deserialize<ConfigReceivedEventArgs>(value);
            if (eventData == null) return;
            ConfigReady = true;
            RuntimeSnapshotReady = false;
            ConfigurationError = string.Empty;
            if (ConfigReceived != null) ConfigReceived(eventData);
        }

        private void OnRuntimeReady(object value)
        {
            if (!ProviderReady) return;
            RuntimeSnapshotReadyEventArgs eventData = Deserialize<RuntimeSnapshotReadyEventArgs>(value);
            if (eventData == null) return;
            RuntimeSnapshotReady = true;
            if (RuntimeReady != null) RuntimeReady(eventData);
        }

        private static T Deserialize<T>(object value) where T : class
        {
            try
            {
                byte[] bytes = value as byte[];
                return bytes == null || bytes.Length == 0
                    ? null
                    : MyAPIGateway.Utilities.SerializeFromBinary<T>(bytes);
            }
            catch
            {
                return null;
            }
        }
    }

    /// <summary>
    /// Read-only API backed by synchronized replicas on remote clients and local authority on hosts.
    /// </summary>
    public class ShipCoreFrameworkClientApi : ShipCoreFrameworkApiBase
    {
        public ShipCoreFrameworkClientApi()
            : base(ApiConstants.CLIENT_REPLICA_API_ID, ApiProviderRoleData.ClientLocalReplica)
        {
        }
    }

    /// <summary>
    /// Authoritative API available only inside a server process.
    /// </summary>
    public sealed class ShipCoreFrameworkServerApi : ShipCoreFrameworkApiBase
    {
        public ShipCoreFrameworkServerApi()
            : base(ApiConstants.SERVER_LOCAL_API_ID, ApiProviderRoleData.ServerLocalAuthority)
        {
        }

        public ApiReadResult<bool> TrySetFrictionEnabledForGroup(long gridId, bool enabled)
        {
            return InvokeCommand(ApiMethodId.SetFrictionEnabledForGroup, MyTuple.Create(gridId, enabled));
        }

        public ApiReadResult<float> TryGetGroupMass(long gridId)
        {
            return InvokePrimitive<float>(ApiMethodId.GetGroupMass, gridId);
        }

        public ApiReadResult<bool> TrySetFrictionMaximumDecelerationForGroup(long gridId, float deceleration)
        {
            return InvokeCommand(ApiMethodId.SetFrictionMaximumDecelerationForGroup,
                MyTuple.Create(gridId, deceleration));
        }

        public ApiReadResult<bool> TryClearFrictionMaximumDecelerationForGroup(long gridId)
        {
            return InvokeCommand(ApiMethodId.ClearFrictionMaximumDecelerationForGroup, gridId);
        }

        public ApiReadResult<bool> TrySetFrictionMinimumSpeedAbsoluteForGroup(long gridId, float speed)
        {
            return InvokeCommand(ApiMethodId.SetFrictionMinimumSpeedAbsoluteForGroup,
                MyTuple.Create(gridId, speed));
        }

        public ApiReadResult<bool> TrySetFrictionMaximumSpeedAbsoluteForGroup(long gridId, float speed)
        {
            return InvokeCommand(ApiMethodId.SetFrictionMaximumSpeedAbsoluteForGroup,
                MyTuple.Create(gridId, speed));
        }

        public ApiReadResult<bool> TrySetFrictionMinimumSpeedModifierForGroup(long gridId, float modifier)
        {
            return InvokeCommand(ApiMethodId.SetFrictionMinimumSpeedModifierForGroup,
                MyTuple.Create(gridId, modifier));
        }

        public ApiReadResult<bool> TrySetFrictionMaximumSpeedModifierForGroup(long gridId, float modifier)
        {
            return InvokeCommand(ApiMethodId.SetFrictionMaximumSpeedModifierForGroup,
                MyTuple.Create(gridId, modifier));
        }

        /// <summary>
        /// Overrides effective grid modifiers. Pass null to restore the core/upgrade profile.
        /// </summary>
        public ApiReadResult<bool> TrySetGridModifiersOverrideForGroup(long gridId, GridModifiersData modifiers)
        {
            return InvokeCommand(ApiMethodId.SetGridModifiersOverrideForGroup,
                MyTuple.Create(gridId, modifiers));
        }

        /// <summary>
        /// Overrides effective speed modifiers. Pass null to restore the core/upgrade profile.
        /// </summary>
        public ApiReadResult<bool> TrySetSpeedModifiersOverrideForGroup(long gridId, SpeedModifiersData modifiers)
        {
            return InvokeCommand(ApiMethodId.SetSpeedModifiersOverrideForGroup,
                MyTuple.Create(gridId, modifiers));
        }

        /// <summary>
        /// Overrides effective passive defense modifiers. Pass null to restore the core/upgrade profile.
        /// </summary>
        public ApiReadResult<bool> TrySetPassiveDefenseModifiersOverrideForGroup(long gridId,
            GridDefenseModifiersData modifiers)
        {
            return InvokeCommand(ApiMethodId.SetPassiveDefenseModifiersOverrideForGroup,
                MyTuple.Create(gridId, modifiers));
        }

        /// <summary>
        /// Overrides effective active defense modifiers. Pass null to restore the core/upgrade profile.
        /// </summary>
        public ApiReadResult<bool> TrySetActiveDefenseModifiersOverrideForGroup(long gridId,
            GridDefenseModifiersData modifiers)
        {
            return InvokeCommand(ApiMethodId.SetActiveDefenseModifiersOverrideForGroup,
                MyTuple.Create(gridId, modifiers));
        }

    }
}
