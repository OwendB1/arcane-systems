using System;
using System.Collections.Generic;
using System.Linq;
using Sandbox.ModAPI;

namespace ShipCoreFramework
{
    internal partial class GroupComponent
    {
        private IEnumerable<UpgradeModuleComponent> GetUpgradeModules()
        {
            return GridDictionary.Values.SelectMany(gridComponent => gridComponent.GetUpgradeModuleComponentsCopy());
        }

        private static void MarkInvalidUpgradeModule(Dictionary<UpgradeModuleComponent, string> invalidModules,
            UpgradeModuleComponent module, string reason)
        {
            if (invalidModules == null || module == null) return;
            if (!invalidModules.ContainsKey(module))
                invalidModules[module] = reason;
        }

        private IEnumerable<UpgradeModuleComponent> GetMainCoreUpgradeModules(bool requireFunctionalForEffects)
        {
            var mainCore = MainCoreComponent;
            if (mainCore == null) yield break;

            foreach (var module in GetAllowedUpgradeModulesForCore(ShipCore, GetUpgradeModules()
                         .Where(module => module != null && ReferenceEquals(module.ParentCoreComponent, mainCore))))
            {
                if (requireFunctionalForEffects && !module.IsFunctionalForEffects()) continue;
                yield return module;
            }
        }

        internal IEnumerable<UpgradeModuleComponent> GetEffectiveUpgradeModules(bool requireFunctionalForEffects)
        {
            var mainCore = MainCoreComponent;
            if (mainCore != null)
            {
                foreach (var module in GetMainCoreUpgradeModules(requireFunctionalForEffects))
                    yield return module;

                yield break;
            }

            if (Deactivated) yield break;
            if (Session.Config == null || !Session.Config.AllowUnattachedUpgradeModules) yield break;

            foreach (var module in GetAllowedUpgradeModulesForCore(ShipCore, GetUpgradeModules()
                         .Where(module => module != null && module.ParentCoreComponent == null)))
            {
                if (requireFunctionalForEffects && !module.IsFunctionalForEffects(false)) continue;
                yield return module;
            }
        }

        private static IEnumerable<UpgradeModuleComponent> GetAllowedUpgradeModulesForCore(ShipCore shipCore,
            IEnumerable<UpgradeModuleComponent> modules)
        {
            if (shipCore == null || modules == null) yield break;

            foreach (var definitionGroup in modules
                         .Where(module => module != null)
                         .GroupBy(module => shipCore.GetUpgradeModuleAllowanceKey(module.UniqueName, module.TypeId, module.SubtypeId),
                             StringComparer.OrdinalIgnoreCase))
            {
                var firstModule = definitionGroup.FirstOrDefault();
                if (firstModule == null) continue;

                int maxAllowed;
                if (!shipCore.TryGetAllowedUpgradeModuleCount(firstModule.UniqueName, firstModule.TypeId, firstModule.SubtypeId,
                        out maxAllowed) ||
                    maxAllowed <= 0)
                    continue;

                foreach (var module in definitionGroup.OrderBy(module => module.ModuleBlock.EntityId).Take(maxAllowed))
                    yield return module;
            }
        }

        internal void OnUpgradeModulesChanged(bool rebuildConnectorLimits = false)
        {
            if (!Session.IsServer) return;
            if (_closing || _refreshingUpgradeModules || IsInitializingGrids) return;
            IncrementLimitGeneration();
            InvalidateGameThreadStateCache(true);
            InvalidateModifierStateCache();

            if (!Session.IsGameThread)
            {
                MyAPIGateway.Utilities.InvokeOnGameThread(() => OnUpgradeModulesChanged(rebuildConnectorLimits));
                return;
            }

            InvalidateSpeedStateCache();
            _refreshingUpgradeModules = true;
            try
            {
                RefreshGroupStateAndEnforce(rebuildConnectorLimits);
            }
            finally
            {
                _refreshingUpgradeModules = false;
                Session.MarkRuntimeStateDirty(this);
            }
        }

        private void RefreshGroupStateAndEnforce(bool rebuildConnectorLimits)
        {
            RefreshUpgradeModules();

            if (IsCoreRecoveryGraceActive())
            {
                ClearCoreRecoveryGracePunishmentState();
                RefreshGridStateCache();
                RefreshNoCoreDirectionLockReferenceCache();
                DefenseValuesChanged();
                QueueRecalculateAllLimits(false, false, rebuildConnectorLimits);
                Utils.Log("RefreshGroupStateAndEnforce: skipped no-core enforcement during core recovery grace for group " +
                          GetGroupKey() + ".", 2);
                return;
            }

            if (Deactivated || IsIgnoredByAiOrFactionTagThreadSafe())
            {
                ClearDeactivatedLimitState();
                RefreshModifierStateCache();
                ApplyModifiers(Modifiers);
                DefenseValuesChanged();
                return;
            }

            RefreshMinimumBlocksLimitedBlockGateState();
            RefreshLimitedBlockPunishmentState();
            RefreshPunishmentState();
            RefreshGridStateCache();
            RefreshNoCoreDirectionLockReferenceCache();
            RefreshModifierStateCacheIfNeeded();
            ApplyModifiers(Modifiers);
            DefenseValuesChanged();

            if (IsLimitPunishmentDeferred())
            {
                QueueRecalculateAllLimits(false, false, rebuildConnectorLimits);
                return;
            }

            QueueRecalculateAllLimits(true, ShouldForceLimitedBlocksOff(), rebuildConnectorLimits);
        }

        private void RefreshUpgradeModules()
        {
            var modules = GetUpgradeModules().OrderBy(module => module.ModuleBlock.EntityId).ToList();
            foreach (var module in modules) module.RefreshParentCore();

            var invalidModules = new Dictionary<UpgradeModuleComponent, string>();
            var coredNotAllowedReason = "This upgrade module is not allowed for this core.";
            var coredOverflowReason = "This upgrade module exceeds the allowed amount for this core.";
            var noCoreNotAllowedReason = "This upgrade module is not allowed for this no-core profile.";
            var noCoreOverflowReason = "This upgrade module exceeds the allowed amount for this no-core profile.";

            if (MainCoreComponent != null)
                foreach (var module in modules.Where(module => module.ParentCoreComponent == null))
                    MarkInvalidUpgradeModule(invalidModules, module, coredNotAllowedReason);

            foreach (var perCoreModules in modules
                         .Where(module => module.ParentCoreComponent != null)
                         .GroupBy(module => module.ParentCoreComponent))
            {
                var core = perCoreModules.Key;
                var shipCore = Session.Config.GetShipCoreByTypeId(core.SubtypeId);
                if (shipCore == null)
                {
                    foreach (var module in perCoreModules)
                        MarkInvalidUpgradeModule(invalidModules, module, coredNotAllowedReason);
                    continue;
                }

                foreach (var definitionGroup in perCoreModules.GroupBy(
                             module => shipCore.GetUpgradeModuleAllowanceKey(module.UniqueName, module.TypeId, module.SubtypeId),
                             StringComparer.OrdinalIgnoreCase))
                {
                    var firstModule = definitionGroup.FirstOrDefault();
                    if (firstModule == null) continue;

                    int maxAllowed;
                    if (!shipCore.TryGetAllowedUpgradeModuleCount(firstModule.UniqueName, firstModule.TypeId, firstModule.SubtypeId,
                            out maxAllowed) ||
                        maxAllowed <= 0)
                    {
                        foreach (var module in definitionGroup)
                            MarkInvalidUpgradeModule(invalidModules, module, coredNotAllowedReason);
                        continue;
                    }

                    var overflow = definitionGroup
                        .OrderBy(module => module.ModuleBlock.EntityId)
                        .Skip(maxAllowed);
                    foreach (var module in overflow)
                        MarkInvalidUpgradeModule(invalidModules, module, coredOverflowReason);
                }
            }

            if (!Deactivated && MainCoreComponent == null &&
                Session.Config != null && Session.Config.AllowUnattachedUpgradeModules)
            {
                var noCoreConfig = ShipCore;
                foreach (var definitionGroup in modules
                             .Where(module => module.ParentCoreComponent == null)
                             .GroupBy(module => noCoreConfig == null
                                     ? module.DefinitionId
                                     : noCoreConfig.GetUpgradeModuleAllowanceKey(module.UniqueName, module.TypeId, module.SubtypeId),
                                 StringComparer.OrdinalIgnoreCase))
                {
                    var firstModule = definitionGroup.FirstOrDefault();
                    if (firstModule == null) continue;

                    int maxAllowed;
                    if (noCoreConfig == null ||
                        !noCoreConfig.TryGetAllowedUpgradeModuleCount(firstModule.UniqueName, firstModule.TypeId, firstModule.SubtypeId,
                            out maxAllowed) ||
                        maxAllowed <= 0)
                    {
                        foreach (var module in definitionGroup)
                            MarkInvalidUpgradeModule(invalidModules, module, noCoreNotAllowedReason);
                        continue;
                    }

                    var overflow = definitionGroup
                        .OrderBy(module => module.ModuleBlock.EntityId)
                        .Skip(maxAllowed);
                    foreach (var module in overflow)
                        MarkInvalidUpgradeModule(invalidModules, module, noCoreOverflowReason);
                }
            }

            foreach (var invalidModule in invalidModules)
                invalidModule.Key.RemoveInvalidModule(invalidModule.Value);
        }
    }
}
