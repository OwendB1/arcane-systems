using System;
using System.Collections.Generic;
using System.Threading;
using Sandbox.ModAPI;
using VRage.Game.ModAPI;
using ModEntity = VRage.ModAPI.IMyEntity;
using MyCubeGrid = Sandbox.Game.Entities.MyCubeGrid;

namespace ShipCoreFramework
{
    internal partial class GroupComponent
    {
        private void RefreshAuthoritativeDirectionLockReference()
        {
            if (!Session.IsGameThread) return;
            RefreshGridStateCacheIfNeeded(false);
            RefreshNoCoreDirectionLockReferenceCacheIfNeeded();
        }

        private void InvalidateModifierStateCache()
        {
            _modifierStateCacheDirty = true;
        }

        internal void RefreshGameThreadStateCache()
        {
            if (!Session.IsServer) return;
            if (_closing || Session.IsShuttingDown) return;
            RefreshGridStateCacheIfNeeded(true);
            var directionReferenceChanged = RefreshNoCoreDirectionLockReferenceCacheIfNeeded();
            if (_modifierStateCacheDirty)
            {
                RefreshModifierStateCacheIfNeeded();
                ApplyModifiers(Modifiers);
                RefreshDefenseModifierCache();
            }
            RefreshIgnoredStateCacheIfNeeded(true);

            if (directionReferenceChanged)
                RevalidateNoCoreDirectionLock();
        }


        internal void OnNoCoreDirectionReferencePropertiesChanged()
        {
            if (!Session.IsServer) return;
            if (_closing || Deactivated || MainCoreComponent != null || IsInitializingGrids) return;

            if (!Session.IsGameThread)
            {
                MyAPIGateway.Utilities.InvokeOnGameThread(OnNoCoreDirectionReferencePropertiesChanged);
                return;
            }

            RefreshGridStateCache();
            if (!RefreshNoCoreDirectionLockReferenceCache()) return;

            OnUpgradeModulesChanged();
        }

        internal void RefreshModifierStateCache()
        {
            if (!Session.IsServer) return;
            if (!Session.IsGameThread || _closing || Session.IsShuttingDown) return;

            _cachedActiveGridModifiers = CubeGridModifiers.GetActiveModifiers(this);
            _cachedActiveSpeedModifiers = CubeGridModifiers.GetActiveSpeedModifiers(this);
            _cachedPassiveDefenseModifiers = ComputePassiveDefenseModifiers();
            _cachedActiveDefenseModifiers = ComputeActiveDefenseModifiers();
            RefreshEffectiveLimitCache();
            _modifierStateCacheDirty = false;
        }

        private bool RefreshNoCoreDirectionLockReferenceCache()
        {
            if (!Session.IsGameThread || _closing || Session.IsShuttingDown) return false;

            var previousReference = _cachedNoCoreDirectionLockReferenceBlock;

            if (MainCoreComponent != null || Deactivated)
            {
                _cachedNoCoreDirectionLockReferenceBlock = null;
                _directionReferenceCacheDirty = false;
                return !ReferenceEquals(previousReference, _cachedNoCoreDirectionLockReferenceBlock);
            }

            var representativeGrid = GetNoCoreDirectionLockReferenceGrid();
            _cachedNoCoreDirectionLockReferenceBlock = GetMainShipController(representativeGrid);
            _directionReferenceCacheDirty = false;
            return !ReferenceEquals(previousReference, _cachedNoCoreDirectionLockReferenceBlock);
        }

        private static bool IsRefreshDue(int currentTick, int nextRefreshTick)
        {
            return nextRefreshTick == 0 || currentTick >= nextRefreshTick;
        }

        private void RefreshGridStateCacheIfNeeded(bool allowPeriodicRefresh)
        {
            if (!Session.IsGameThread || _closing || Session.IsShuttingDown) return;

            var tick = Session.CurrentTick;
            if (!_gridStateCacheDirty &&
                (!allowPeriodicRefresh || !IsRefreshDue(tick, _nextGridStateCacheRefreshTick)))
                return;

            RefreshGridStateCache();
        }

        private bool RefreshNoCoreDirectionLockReferenceCacheIfNeeded()
        {
            if (!Session.IsGameThread || _closing || Session.IsShuttingDown) return false;

            var referenceBlock = _cachedNoCoreDirectionLockReferenceBlock;
            var referenceInvalid = referenceBlock != null &&
                                   (referenceBlock.MarkedForClose || referenceBlock.Closed ||
                                    referenceBlock.CubeGrid == null);

            if (!_directionReferenceCacheDirty && !referenceInvalid)
                return false;

            return RefreshNoCoreDirectionLockReferenceCache();
        }

        private void RefreshModifierStateCacheIfNeeded()
        {
            if (!_modifierStateCacheDirty) return;
            RefreshModifierStateCache();
        }

        private void RefreshIgnoredStateCacheIfNeeded(bool allowPeriodicRefresh)
        {
            if (!Session.IsGameThread || _closing || Session.IsShuttingDown) return;

            var tick = Session.CurrentTick;
            if (!_ignoredStateCacheDirty &&
                (!allowPeriodicRefresh || !IsRefreshDue(tick, _nextIgnoredStateCacheRefreshTick)))
                return;

            var wasNpcGroup = _cachedIsNpcGroup;
            var wasIgnoredByAiOrFactionTag = _cachedIsIgnoredByAiOrFactionTag;
            _cachedIsNpcGroup = IsNpcGroup();
            _cachedIsIgnoredByAiOrFactionTag = IsIgnoredByAiOrFactionTag();
            _cachedIsIgnoredGroup = ComputeIsIgnoredGroup();
            _ignoredStateCacheDirty = false;
            _nextIgnoredStateCacheRefreshTick = tick + IgnoredStateCacheRefreshIntervalTicks;

            if (wasIgnoredByAiOrFactionTag != _cachedIsIgnoredByAiOrFactionTag)
            {
                InvalidateModifierStateCache();
                QueuePunishmentStateRefresh();
            }

            if (wasNpcGroup != _cachedIsNpcGroup)
            {
                Session.MarkRuntimeStateDirty(this);
                if (wasNpcGroup)
                    EnforceGroupPunishment();
            }
        }

        private void RevalidateNoCoreDirectionLock()
        {
            if (_closing || Deactivated || MainCoreComponent != null || IsInitializingGrids || _refreshingUpgradeModules)
                return;

            OnUpgradeModulesChanged();
        }

        private MyCubeGrid GetNoCoreDirectionLockReferenceGrid()
        {
            var representativeGridId = GetCachedRepresentativeGridId();
            MyCubeGrid fallbackGrid = null;
            var fallbackBlocks = -1;

            foreach (var kvp in GridDictionary)
            {
                var grid = kvp.Key;
                if (grid == null || grid.MarkedForClose || grid.Closed) continue;

                if (representativeGridId != 0L && grid.EntityId == representativeGridId)
                    return grid;

                var blocks = grid.BlocksCount;
                if (fallbackGrid == null || blocks > fallbackBlocks ||
                    blocks == fallbackBlocks && grid.EntityId < fallbackGrid.EntityId)
                {
                    fallbackGrid = grid;
                    fallbackBlocks = blocks;
                }
            }

            return fallbackGrid;
        }

        private IMyCubeBlock GetMainShipController(MyCubeGrid grid)
        {
            if (grid == null || grid.MarkedForClose || grid.Closed) return null;

            GridComponent gridComponent;
            if (!GridDictionary.TryGetValue(grid, out gridComponent)) return null;

            IMyShipController fallbackController = null;
            var shipControllers = gridComponent.GetShipControllersCopy();
            foreach (var controller in shipControllers)
            {
                if (controller == null || controller.MarkedForClose || controller.Closed) continue;
                if (controller.CubeGrid == null || controller.CubeGrid.EntityId != grid.EntityId) continue;

                if (controller.IsMainCockpit)
                    return controller;

                if (fallbackController == null || controller.EntityId < fallbackController.EntityId)
                    fallbackController = controller;
            }

            return fallbackController;
        }

        private MyCubeGrid GetMobilityReferenceGrid()
        {
            var mainGrid = MainCoreComponent?.CoreBlock?.CubeGrid as MyCubeGrid;
            if (mainGrid != null) return mainGrid;

            MyCubeGrid bestGrid = null;
            var bestBlocks = -1;
            foreach (var kvp in GridDictionary)
            {
                var grid = kvp.Key;
                if (grid == null || grid.MarkedForClose || grid.Closed) continue;

                var blocks = grid.BlocksCount;
                if (bestGrid == null || blocks > bestBlocks ||
                    blocks == bestBlocks && grid.EntityId < bestGrid.EntityId)
                {
                    bestGrid = grid;
                    bestBlocks = blocks;
                }
            }

            return bestGrid;
        }

        private void RefreshGridStateCache()
        {
            var capacity = Math.Max(_cachedGridStates?.Length ?? 0,
                DefaultGridStateCacheCapacity);
            var representativeGridId = 0L;
            var representativeBlocks = -1;
            var movableGrids = new List<MyCubeGrid>(capacity);
            var mechanicalGridIds = new List<long>(capacity);
            var gridStates = new List<CachedGridState>(capacity);

            var mainGrid = MainCoreComponent?.GridComponent?.Grid;
            if (mainGrid != null && !mainGrid.MarkedForClose && !mainGrid.Closed)
                representativeGridId = mainGrid.EntityId;

            foreach (var kvp in GridDictionary)
            {
                var grid = kvp.Key;
                if (grid == null || grid.MarkedForClose || grid.Closed) continue;

                mechanicalGridIds.Add(grid.EntityId);
                IMyCubeGrid apiGrid = grid;
                ModEntity entity = grid;
                gridStates.Add(new CachedGridState
                {
                    EntityId = grid.EntityId,
                    CustomName = apiGrid.CustomName ?? string.Empty,
                    Position = entity.GetPosition(),
                    FirstOwnerId = grid.BigOwners == null || grid.BigOwners.Count == 0 ? 0 : grid.BigOwners[0]
                });

                if (!grid.IsStatic)
                    movableGrids.Add(grid);

                if (representativeGridId != 0) continue;
                var blocks = grid.BlocksCount;
                if (blocks > representativeBlocks || blocks == representativeBlocks && grid.EntityId < representativeGridId)
                {
                    representativeBlocks = blocks;
                    representativeGridId = grid.EntityId;
                }
            }

            Interlocked.Exchange(ref _cachedRepresentativeGridId, representativeGridId);
            _cachedMovableGrids = movableGrids.ToArray();
            _cachedMechanicalGridIds = mechanicalGridIds.ToArray();
            _cachedGridStates = gridStates.ToArray();
            _gridStateCacheDirty = false;
            _nextGridStateCacheRefreshTick = Session.CurrentTick + GridStateCacheRefreshIntervalTicks;
        }

    }
}
