using System;
using VRage;

namespace ShipCoreFramework
{
    public static partial class ModAPI
    {
        private static Func<object, object> ServerMethodFactory(int methodId)
        {
            switch (methodId)
            {
                case ApiMethodId.GetApiVersion:
                    return ignored => Success(ApiConstants.API_VERSION);
                case ApiMethodId.GetCapabilities:
                    return ignored => Success((int)(ApiCapabilityData.ConfigQueries |
                                                     ApiCapabilityData.RuntimeQueries |
                                                     ApiCapabilityData.RuntimeMutations |
                                                     ApiCapabilityData.Authoritative |
                                                     ApiCapabilityData.BestEffortPlacementChecks));
                case ApiMethodId.GetReadiness_Binary:
                    return ignored => SerializedSuccess(
                        GetReadiness(ApiProviderRoleData.ServerLocalAuthority));
                case ApiMethodId.GetRuntimeStateAvailability:
                    return ServerRuntimeStateAvailability;
                case ApiMethodId.GetGridCore_Binary:
                    return argument => AuthorityRuntime(argument,
                        gridId => SerializedSuccess(GetGridCore(gridId)));
                case ApiMethodId.GetCoreBySubtypeId_Binary:
                    return ServerGetCoreBySubtypeId;
                case ApiMethodId.GetAllCoreConfigs_Binary:
                    return ignored => ConfigResult(() => SerializedSuccess(GetAllCoreConfigs()));
                case ApiMethodId.GetBlockLimitsStatus_Binary:
                    return argument => AuthorityRuntime(argument,
                        gridId => SerializedSuccess(GetBlockLimitsStatus(gridId)));
                case ApiMethodId.IsBlockAllowed:
                    return ServerIsBlockAllowed;
                case ApiMethodId.GetGridModifiers_Binary:
                    return argument => AuthorityRuntime(argument,
                        gridId => SerializedSuccess(GetGridModifiers(gridId)));
                case ApiMethodId.GetMaxSpeed:
                    return argument => AuthorityRuntime(argument, gridId => Success(GetMaxSpeed(gridId)));
                case ApiMethodId.IsBoostActive:
                    return argument => AuthorityRuntime(argument, gridId => Success(IsBoostActive(gridId)));
                case ApiMethodId.GetNoCoreConfig_Binary:
                    return ignored => ConfigResult(() => SerializedSuccess(GetNoCoreConfig()));
                case ApiMethodId.GetSpeedModifiers_Binary:
                    return argument => AuthorityRuntime(argument,
                        gridId => SerializedSuccess(GetSpeedModifiers(gridId)));
                case ApiMethodId.GetBoostResistance:
                    return argument => AuthorityRuntime(argument, gridId => Success(GetBoostResistance(gridId)));
                case ApiMethodId.GetBaseMaxSpeed:
                    return argument => AuthorityRuntime(argument, gridId => Success(GetBaseMaxSpeed(gridId)));
                case ApiMethodId.GetMaxBoostMultiplier:
                    return argument => AuthorityRuntime(argument,
                        gridId => Success(GetMaxBoostMultiplier(gridId)));
                case ApiMethodId.GetBoostDuration:
                    return argument => AuthorityRuntime(argument, gridId => Success(GetBoostDuration(gridId)));
                case ApiMethodId.GetBoostCooldown:
                    return argument => AuthorityRuntime(argument, gridId => Success(GetBoostCooldown(gridId)));
                case ApiMethodId.SetFrictionEnabledForGroup:
                    return ServerSetFrictionEnabled;
                case ApiMethodId.GetFrictionEnabledForGroup:
                    return argument => AuthorityRuntime(argument,
                        gridId => Success(GetFrictionEnabledForGroup(gridId)));
                case ApiMethodId.SetFrictionMaximumDecelerationForGroup:
                    return ServerSetFrictionMaximumDeceleration;
                case ApiMethodId.ClearFrictionMaximumDecelerationForGroup:
                    return argument => AuthorityCommand(argument, ClearFrictionMaximumDecelerationForGroup);
                case ApiMethodId.GetFrictionMaximumDecelerationForGroup:
                    return argument => AuthorityRuntime(argument,
                        gridId => Success(GetFrictionMaximumDecelerationForGroup(gridId)));
                case ApiMethodId.GetFrictionSpeedValueMode:
                    return ignored => ConfigResult(() => Success((int)Session.Config.FrictionSpeedValueMode));
                case ApiMethodId.SetFrictionMinimumSpeedAbsoluteForGroup:
                    return argument => ServerSetFrictionValue(argument,
                        SetFrictionMinimumSpeedAbsoluteForGroup);
                case ApiMethodId.SetFrictionMaximumSpeedAbsoluteForGroup:
                    return argument => ServerSetFrictionValue(argument,
                        SetFrictionMaximumSpeedAbsoluteForGroup);
                case ApiMethodId.GetFrictionMinimumSpeedAbsoluteForGroup:
                    return argument => ServerGetFrictionValue(argument,
                        GetFrictionMinimumSpeedAbsoluteForGroup);
                case ApiMethodId.GetFrictionMaximumSpeedAbsoluteForGroup:
                    return argument => ServerGetFrictionValue(argument,
                        GetFrictionMaximumSpeedAbsoluteForGroup);
                case ApiMethodId.SetFrictionMinimumSpeedModifierForGroup:
                    return argument => ServerSetFrictionValue(argument,
                        SetFrictionMinimumSpeedModifierForGroup);
                case ApiMethodId.SetFrictionMaximumSpeedModifierForGroup:
                    return argument => ServerSetFrictionValue(argument,
                        SetFrictionMaximumSpeedModifierForGroup);
                case ApiMethodId.GetFrictionMinimumSpeedModifierForGroup:
                    return argument => ServerGetFrictionValue(argument,
                        GetFrictionMinimumSpeedModifierForGroup);
                case ApiMethodId.GetFrictionMaximumSpeedModifierForGroup:
                    return argument => ServerGetFrictionValue(argument,
                        GetFrictionMaximumSpeedModifierForGroup);
                case ApiMethodId.IsGroupDeactivated:
                    return argument => AuthorityRuntime(argument,
                        gridId => Success(IsGroupDeactivated(gridId)));
                case ApiMethodId.GetFullConfig_Binary:
                    return ignored => ConfigResult(() => SerializedSuccess(GetFullConfig()));
                case ApiMethodId.GetGroupMass:
                    return argument => AuthorityRuntime(argument,
                        gridId => Success(GetAuthoritativeGroupMass(gridId)));
                case ApiMethodId.SetGridModifiersOverrideForGroup:
                    return ServerSetGridModifiersOverride;
                case ApiMethodId.SetSpeedModifiersOverrideForGroup:
                    return ServerSetSpeedModifiersOverride;
                case ApiMethodId.SetPassiveDefenseModifiersOverrideForGroup:
                    return ServerSetPassiveDefenseModifiersOverride;
                case ApiMethodId.SetActiveDefenseModifiersOverrideForGroup:
                    return ServerSetActiveDefenseModifiersOverride;
                default:
                    return null;
            }
        }

        private static object ConfigResult(Func<object> action)
        {
            object failure = CheckConfigReady();
            return failure ?? action();
        }

        private static object AuthorityRuntime(object argument, Func<long, object> action)
        {
            object failure = CheckRuntimeReady();
            if (failure != null) return failure;

            long gridId;
            if (!TryGetLong(argument, out gridId)) return Failure(ApiReadStatusData.InvalidArgument);

            GroupComponent group;
            if (!TryGetGroupComponent(gridId, out group) || group == null)
                return Failure(ApiReadStatusData.GridNotReplicated);

            try
            {
                return action(gridId);
            }
            catch (Exception exception)
            {
                Utils.Log("ModAPI v4 server query failed: " + exception, 3);
                return Failure(ApiReadStatusData.Error);
            }
        }

        private static object ServerRuntimeStateAvailability(object argument)
        {
            object failure = CheckRuntimeReady();
            if (failure != null) return failure;

            long gridId;
            if (!TryGetLong(argument, out gridId)) return Failure(ApiReadStatusData.InvalidArgument);
            GroupComponent group;
            return Success(TryGetGroupComponent(gridId, out group) && group != null);
        }

        private static object ServerGetCoreBySubtypeId(object argument)
        {
            object failure = CheckConfigReady();
            if (failure != null) return failure;
            string subtypeId = argument as string;
            if (string.IsNullOrWhiteSpace(subtypeId)) return Failure(ApiReadStatusData.InvalidArgument);
            return SerializedSuccess(GetCoreBySubtypeId(subtypeId));
        }

        private static object ServerIsBlockAllowed(object argument)
        {
            if (!(argument is MyTuple<long, string, string, int>))
                return Failure(ApiReadStatusData.InvalidArgument);
            MyTuple<long, string, string, int> values =
                (MyTuple<long, string, string, int>)argument;
            if (string.IsNullOrWhiteSpace(values.Item2) || values.Item4 < 1)
                return Failure(ApiReadStatusData.InvalidArgument);
            return AuthorityRuntime(values.Item1,
                gridId => Success(IsBlockAllowed(gridId, values.Item2, values.Item3, values.Item4)));
        }

        private static object ServerSetFrictionEnabled(object argument)
        {
            if (!(argument is MyTuple<long, bool>)) return Failure(ApiReadStatusData.InvalidArgument);
            MyTuple<long, bool> values = (MyTuple<long, bool>)argument;
            return AuthorityCommand(values.Item1,
                gridId => SetFrictionEnabledForGroup(gridId, values.Item2));
        }

        private static object ServerSetFrictionMaximumDeceleration(object argument)
        {
            if (!(argument is MyTuple<long, float>)) return Failure(ApiReadStatusData.InvalidArgument);
            MyTuple<long, float> values = (MyTuple<long, float>)argument;
            if (values.Item2 < 0f) return Failure(ApiReadStatusData.InvalidArgument);
            return AuthorityCommand(values.Item1,
                gridId => SetFrictionMaximumDecelerationForGroup(gridId, values.Item2));
        }

        private static object AuthorityCommand(object argument, Func<long, bool> action)
        {
            long gridId;
            if (!TryGetLong(argument, out gridId)) return Failure(ApiReadStatusData.InvalidArgument);
            return AuthorityCommand(gridId, action);
        }

        private static object AuthorityCommand(long gridId, Func<long, bool> action)
        {
            return AuthorityRuntime(gridId, resolvedGridId =>
            {
                bool success = action(resolvedGridId);
                return Success(MyTuple.Create(success,
                    success ? string.Empty : "Server rejected the requested mutation."));
            });
        }

        private static object ServerSetFrictionValue(object argument,
            Func<long, float, MyTuple<bool, string>> action)
        {
            if (!(argument is MyTuple<long, float>)) return Failure(ApiReadStatusData.InvalidArgument);
            MyTuple<long, float> values = (MyTuple<long, float>)argument;
            return AuthorityRuntime(values.Item1, gridId => Success(action(gridId, values.Item2)));
        }

        private static object ServerGetFrictionValue(object argument,
            Func<long, MyTuple<float, string>> action)
        {
            return AuthorityRuntime(argument, gridId =>
            {
                MyTuple<float, string> result = action(gridId);
                return string.IsNullOrEmpty(result.Item2)
                    ? Success(result.Item1)
                    : Failure(ApiReadStatusData.InvalidArgument);
            });
        }

        private static object ServerSetGridModifiersOverride(object argument)
        {
            if (!(argument is MyTuple<long, GridModifiersData>))
                return Failure(ApiReadStatusData.InvalidArgument);
            MyTuple<long, GridModifiersData> values = (MyTuple<long, GridModifiersData>)argument;
            return AuthorityCommand(values.Item1,
                gridId => SetGridModifiersOverrideForGroup(gridId, values.Item2));
        }

        private static object ServerSetSpeedModifiersOverride(object argument)
        {
            if (!(argument is MyTuple<long, SpeedModifiersData>))
                return Failure(ApiReadStatusData.InvalidArgument);
            MyTuple<long, SpeedModifiersData> values = (MyTuple<long, SpeedModifiersData>)argument;
            return AuthorityCommand(values.Item1,
                gridId => SetSpeedModifiersOverrideForGroup(gridId, values.Item2));
        }

        private static object ServerSetPassiveDefenseModifiersOverride(object argument)
        {
            if (!(argument is MyTuple<long, GridDefenseModifiersData>))
                return Failure(ApiReadStatusData.InvalidArgument);
            MyTuple<long, GridDefenseModifiersData> values = (MyTuple<long, GridDefenseModifiersData>)argument;
            return AuthorityCommand(values.Item1,
                gridId => SetPassiveDefenseModifiersOverrideForGroup(gridId, values.Item2));
        }

        private static object ServerSetActiveDefenseModifiersOverride(object argument)
        {
            if (!(argument is MyTuple<long, GridDefenseModifiersData>))
                return Failure(ApiReadStatusData.InvalidArgument);
            MyTuple<long, GridDefenseModifiersData> values = (MyTuple<long, GridDefenseModifiersData>)argument;
            return AuthorityCommand(values.Item1,
                gridId => SetActiveDefenseModifiersOverrideForGroup(gridId, values.Item2));
        }
    }
}
