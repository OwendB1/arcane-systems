using System;
using System.Collections.Generic;
using Sandbox.Game.Entities;
using Sandbox.ModAPI;
using VRage.Game.ModAPI;

namespace ShipCoreFramework
{
    internal partial class GroupComponent
    {
        private bool FinalizeAuthoritativeGridInitialization()
        {
            if (MainCoreComponent == null)
                ScheduleMissingCoreRescan();

            InitializeDeactivationState();
            if (Deactivated) return true;

            SyncNoCoreLimitTracking();
            OnUpgradeModulesChanged();
            QueueConnectorNetworkRefresh();
            Utils.Log("InitGrids: initialized group " + GetGroupKey() + " with " +
                      GridDictionary.Count + " grids, " + CoreDictionary.Count + " cores, main core " +
                      (MainCoreComponent == null ? "<none>" : MainCoreComponent.SubtypeId) + ".", 2);
            return true;
        }

        private bool HasPotentialCoreBlocksInGroup()
        {
            var coreBlocks = new List<IMySlimBlock>();
            foreach (var grid in GridDictionary.Keys)
            {
                if (grid == null || grid.MarkedForClose || grid.Closed) continue;

                coreBlocks.Clear();
                ((IMyCubeGrid)grid).GetBlocks(coreBlocks, Utils.IsCoreBlock);
                if (coreBlocks.Count > 0) return true;
            }

            return false;
        }

        private bool IsCoreRecoveryGraceActive()
        {
            return (_coreRecoveryGraceActive || _coreRecoveryGraceStartTick != 0) &&
                   !_missingCoreConfirmedAbsent &&
                   MainCoreComponent == null &&
                   !Deactivated &&
                   !_closing &&
                   !Session.IsShuttingDown;
        }

        private void ScheduleCoreRecoveryGrace(string reason)
        {
            if (_missingCoreConfirmedAbsent || MainCoreComponent != null || Deactivated || _closing)
                return;

            if (!HasPotentialCoreBlocksInGroup())
                return;

            if (_coreRecoveryGraceActive || _coreRecoveryGraceStartTick != 0)
                return;

            _coreRecoveryGraceStartTick = Session.CurrentTick + CoreRecoveryGraceStartDelayTicks;
            _nextCoreRecoveryGraceNotificationTick = 0;
            _lastCoreRecoveryGraceNotificationSeconds = -1;
            Utils.Log("CoreRecoveryGrace: transient no-core guard scheduled for group " + GetGroupKey() +
                      ". Countdown starts at tick " + _coreRecoveryGraceStartTick +
                      ". Reason: " + reason, 1);
        }

        private void TryStartCoreRecoveryGraceCountdown(string reason)
        {
            if (_coreRecoveryGraceActive || _coreRecoveryGraceStartTick == 0) return;
            if (Session.CurrentTick < _coreRecoveryGraceStartTick) return;

            if (!HasPotentialCoreBlocksInGroup())
            {
                ClearCoreRecoveryGrace("core block absent before grace countdown", true);
                ApplyNoCoreStateAfterGraceExpired();
                return;
            }

            var graceTicks = SecondsToTicks(Session.Config == null ? 30 : Session.Config.NoCoreGraceSeconds);
            if (graceTicks <= 0)
            {
                ClearCoreRecoveryGrace("no-core grace disabled", true);
                ApplyNoCoreStateAfterGraceExpired();
                return;
            }

            _coreRecoveryGraceActive = true;
            _coreRecoveryGraceStartTick = 0;
            _coreRecoveryGraceExpireTick = Session.CurrentTick + graceTicks;
            _nextCoreRecoveryGraceNotificationTick = 0;
            _lastCoreRecoveryGraceNotificationSeconds = -1;

            Utils.Log("CoreRecoveryGrace: countdown started for group " + GetGroupKey() +
                      ". Expires at tick " + _coreRecoveryGraceExpireTick +
                      ". Reason: " + reason, 1);

            NotifyCoreRecoveryGraceCountdown(true);
        }

        private void NotifyCoreRecoveryGraceCountdown(bool force)
        {
            if (!_coreRecoveryGraceActive || _coreRecoveryGraceExpireTick == 0) return;

            var remainingSeconds = TicksToCeilingSeconds(_coreRecoveryGraceExpireTick - Session.CurrentTick);
            if (remainingSeconds <= 0) return;

            if (!force &&
                Session.CurrentTick < _nextCoreRecoveryGraceNotificationTick &&
                remainingSeconds == _lastCoreRecoveryGraceNotificationSeconds)
                return;

            _lastCoreRecoveryGraceNotificationSeconds = remainingSeconds;
            _nextCoreRecoveryGraceNotificationTick = Session.CurrentTick +
                                                     (remainingSeconds <= 10 ? TicksPerSecond : TicksPerSecond * 5);
            BroadcastGroupCountdown(GetCoreRecoveryGraceCountdownKey(), "No core reset in", remainingSeconds,
                _coreRecoveryGraceNotificationRecipients);
        }

        private string GetCoreRecoveryGraceCountdownKey()
        {
            return "no-core-grace:" + GetRepresentativeGridId();
        }

        private void ExpireCoreRecoveryGrace()
        {
            if (!_coreRecoveryGraceActive) return;

            ClearCoreRecoveryGrace("no-core grace countdown expired", true);
            ApplyNoCoreStateAfterGraceExpired();
        }

        private void ApplyNoCoreStateAfterGraceExpired()
        {
            if (_closing || Deactivated || MainCoreComponent != null || Session.IsShuttingDown) return;

            Utils.Log("CoreRecoveryGrace: applying no-core state after grace for group " +
                      GetGroupKey() + ".", 1);
            ClearMissingCoreRescan();
            RefreshPunishmentState();
            OnUpgradeModulesChanged();
        }

        private void ClearCoreRecoveryGrace(string reason, bool confirmedAbsent)
        {
            var wasActive = _coreRecoveryGraceActive || _coreRecoveryGraceStartTick != 0 ||
                            _coreRecoveryGraceExpireTick != 0;
            _coreRecoveryGraceActive = false;
            _coreRecoveryGraceStartTick = 0;
            _coreRecoveryGraceExpireTick = 0;
            _nextCoreRecoveryGraceNotificationTick = 0;
            _lastCoreRecoveryGraceNotificationSeconds = -1;
            if (confirmedAbsent)
            {
                _missingCoreConfirmedAbsent = true;
                SpeedEnforcementDeferred = false;
                InvalidateSpeedStateCache();
            }
            else if (MainCoreComponent != null)
                _missingCoreConfirmedAbsent = false;

            if (wasActive)
                BroadcastGroupCountdown(GetCoreRecoveryGraceCountdownKey(), string.Empty, 0,
                    _coreRecoveryGraceNotificationRecipients);

            if (wasActive || confirmedAbsent)
                Utils.Log("CoreRecoveryGrace: cleared for group " + GetGroupKey() +
                          ". ConfirmedAbsent=" + confirmedAbsent +
                          ". Reason: " + reason, 1);
        }

        internal void Activate(CoreComponent coreComponent)
        {
            if (!Session.IsServer) return;
            if (!HasSameOrientationAsMain(coreComponent))
            {
                coreComponent.IsMainCore = false;
                Utils.Log("Activate: rejected core " + coreComponent.SubtypeId +
                          " because its orientation differs from the active main core.", 1);
                return;
            }

            if (Deactivated)
            {
                coreComponent.IsMainCore = false;
                return;
            }

            var old = MainCoreComponent;
            var wasInactive = old == null;
            if (!ReferenceEquals(old, coreComponent))
            {
                if (old != null) old.IsMainCore = false;
                coreComponent.IsMainCore = true;
            }

            MainCoreComponent = coreComponent;
            SpeedEnforcementDeferred = false;
            ClearSpeedRampDown();
            if (PunishSpeed) BeginSpeedRampDown();
            Session.MarkRuntimeStateDirty(this);
            ClearCoreRecoveryGrace("main core activated", false);
            InvalidateGameThreadStateCache(true);
            InvalidateModifierStateCache();
            IncrementLimitGeneration();
            if (wasInactive || old.SubtypeId != coreComponent.SubtypeId)
                ClearPublishedLimitSnapshots();
            SyncBeaconComponents();
            InvalidateSpeedStateCache();
            Session.MarkPhysicalSpeedClusterSourceDirty(this);

            if (MainCoreComponent != null)
            {
                var grid = MainCoreComponent.GridComponent.Grid;
                var ownerId = coreComponent.CoreBlock.OwnerId == 0
                    ? coreComponent.CoreBlock.SlimBlock.BuiltBy
                    : coreComponent.CoreBlock.OwnerId;
                Utils.Log($"Activate: Activating logic for {((IMyCubeGrid)grid).CustomName}! Core={coreComponent.SubtypeId}, Owner={ownerId}, Grids={GridDictionary.Count}", 1);
            }

            if (wasInactive)
            {
                UnregisterNoCoreLimitTracking();
            }

            RegisterCoreLimitTracking();

            MyAPIGateway.Utilities.InvokeOnGameThread(() =>
            {
                if (_closing) return;
                OnUpgradeModulesChanged();
                QueueConnectorNetworkRefresh();

                if (wasInactive)
                    ModAPI.BroadcastCoreActivated(GetRepresentativeGridId(), ShipCore.SubtypeId, ShipCore.UniqueName);
            });
        }

        internal void ResetCore()
        {
            if (!Session.IsServer) return;
            var old = MainCoreComponent;
            if (old == null) return;
            if (!Session.IsGameThread)
            {
                MyAPIGateway.Utilities.InvokeOnGameThread(ResetCore);
                return;
            }

            old.IsMainCore = false;

            if (!Deactivated)
                BeginSpeedRampDown();

            var type = ShipCore.SubtypeId;
            // CoreBlock can already be gone when the core is reset because its block was
            // destroyed; the reset itself must still run, so only the logging degrades.
            var coreBlock = old.CoreBlock;
            var grid = coreBlock?.CubeGrid;
            Utils.Log($"Reset: Resetting logic for {grid?.CustomName ?? "<unknown grid>"}!", 2);

            UnregisterCoreLimitTracking();

            ModAPI.BroadcastCoreDeactivated(GetRepresentativeGridId(), type,
                coreBlock?.CustomName ?? string.Empty);

            MainCoreComponent = null;
            InvalidateGameThreadStateCache(true);
            InvalidateModifierStateCache();
            IncrementLimitGeneration();
            ClearPublishedLimitSnapshots();
            InvalidateSpeedStateCache();
            Session.MarkPhysicalSpeedClusterSourceDirty(this);
            SyncNoCoreLimitTracking();
            ScheduleMissingCoreRescan();
            SyncBeaconComponents();
            Session.MarkRuntimeStateDirty(this);

            if (_closing || !Session.HasStarted || Session.IsShuttingDown) return;
            OnUpgradeModulesChanged();
            QueueConnectorNetworkRefresh();
        }

        private void FinalizeAuthoritativeGridAdded(IMyCubeGrid grid)
        {
            if (MainCoreComponent == null)
                ScheduleMissingCoreRescan();
            Session.MarkRuntimeStateDirty(this);

            Utils.Log($"OnGridAdded: {grid.EntityId}, {OwnerId}, {grid.CustomName}", 2);
            MyAPIGateway.Utilities.InvokeOnGameThread(() =>
            {
                if (grid.MarkedForClose || grid.Closed) return;

                OnUpgradeModulesChanged();
                QueueConnectorNetworkRefresh();
                Session.RefreshPhysicalGroupLinkagesForGrid(grid);
                ModAPI.BroadcastGridAddedToGroup(grid.EntityId);
            });
        }

        private void FinalizeAuthoritativeGridRemoved(MyCubeGrid g, IMyCubeGrid grid,
            CoreComponent removedMain)
        {
            if (removedMain != null) MainCoreLeftGroup(removedMain);

            RemoveDefenseModifierCache(g.EntityId);

            if (GridCount == 0)
            {
                _closing = true;
                Session.RefreshPhysicalGroupLinkagesForGrid(grid);
                return;
            }

            RebuildConnectorPunishmentLinks();
            RefreshPunishmentState();
            QueueRecalculateAllLimits(true, ShouldForceLimitedBlocksOff(), true);
            QueueConnectorNetworkRefresh();
            Session.RefreshPhysicalGroupLinkagesForGrid(grid);
            Session.RefreshPhysicalGroupLinkagesForGrids(GridDictionary.Keys);
            ModAPI.BroadcastGridRemovedFromGroup(grid.EntityId, GetRepresentativeGridId());
            Session.MarkRuntimeStateDirty(this);
        }

        private void MainCoreLeftGroup(CoreComponent lost)
        {
            if (!Session.IsServer) return;
            if (!ReferenceEquals(lost, MainCoreComponent)) return;

            var oldType = lost.SubtypeId;
            var oldName = lost.CoreBlock?.CustomName ?? string.Empty;

            if (!Deactivated)
                BeginSpeedRampDown();
            MainCoreComponent = null;
            InvalidateGameThreadStateCache(true);
            InvalidateModifierStateCache();

            if (Deactivated)
            {
                ClearSpeedRampDown();
                SyncBeaconComponents();
                OnUpgradeModulesChanged();
                QueueConnectorNetworkRefresh();
                return;
            }

            var newMain = GetBestReplacementMainCoreCandidate(lost, false);
            if (newMain == null)
            {
                Utils.Log("MainCoreLeftGroup: no replacement core found after " + oldType +
                          " left group " + GetGroupKey() + ".", 1);
                UnregisterCoreLimitTracking();
                ModAPI.BroadcastCoreDeactivated(GetRepresentativeGridId(), oldType, oldName);
                ClearPublishedLimitSnapshots();
                InvalidateSpeedStateCache();
                Session.MarkPhysicalSpeedClusterSourceDirty(this);
                SyncNoCoreLimitTracking();
                ScheduleMissingCoreRescan();
            }
            else
            {
                MainCoreComponent = newMain;
                MainCoreComponent.IsMainCore = true;
                ClearSpeedRampDown();
                if (PunishSpeed) BeginSpeedRampDown();
                Utils.Log("MainCoreLeftGroup: switched main core from " + oldType + " to " +
                          MainCoreComponent.SubtypeId + " for group " + GetGroupKey() + ".", 1);
                InvalidateGameThreadStateCache(true);
                InvalidateModifierStateCache();
                if (!string.Equals(oldType, MainCoreComponent.SubtypeId, StringComparison.OrdinalIgnoreCase))
                    ClearPublishedLimitSnapshots();
                RegisterCoreLimitTracking();
                InvalidateSpeedStateCache();
                Session.MarkPhysicalSpeedClusterSourceDirty(this);
            }

            SyncBeaconComponents();
            Session.MarkRuntimeStateDirty(this);

            if (_closing || !Session.HasStarted || Session.IsShuttingDown) return;
            OnUpgradeModulesChanged();
            QueueConnectorNetworkRefresh();
        }

        private void CoreRemovedAuthoritative(CoreComponent lost)
        {
            if (!ReferenceEquals(lost, MainCoreComponent)) return;
            lost.IsMainCore = false;

            if (Deactivated)
            {
                MainCoreComponent = null;
                InvalidateGameThreadStateCache(true);
                InvalidateModifierStateCache();
                InvalidateSpeedStateCache();
                Session.MarkPhysicalSpeedClusterSourceDirty(this);
                SyncBeaconComponents();
                OnUpgradeModulesChanged();
                QueueConnectorNetworkRefresh();
                return;
            }

            var newMain = GetBestReplacementMainCoreCandidate(lost, false);
            if (newMain == null)
            {
                Utils.Log("CoreRemoved: main core " + lost.SubtypeId +
                          " removed with no replacement for group " + GetGroupKey() + ".", 1);
                ResetCore();
            }
            else
            {
                MainCoreComponent = newMain;
                MainCoreComponent.IsMainCore = true;
                Utils.Log("CoreRemoved: replaced main core " + lost.SubtypeId + " with " +
                          MainCoreComponent.SubtypeId + " for group " + GetGroupKey() + ".", 1);
                InvalidateGameThreadStateCache(true);
                InvalidateModifierStateCache();
                if (!string.Equals(lost.SubtypeId, MainCoreComponent.SubtypeId, StringComparison.OrdinalIgnoreCase))
                    ClearPublishedLimitSnapshots();
                RegisterCoreLimitTracking();
                InvalidateSpeedStateCache();
                Session.MarkPhysicalSpeedClusterSourceDirty(this);
                SyncBeaconComponents();
            }

            OnUpgradeModulesChanged();
            QueueConnectorNetworkRefresh();
        }

        internal void SyncBeaconComponents()
        {
            foreach (var gridComponent in GridDictionary.Values)
                gridComponent.SyncBeaconComponents();
        }

        private void OnConfigChangedAuthoritative()
        {
            InvalidateModifierStateCache();
            IncrementLimitGeneration();
            SyncNoCoreLimitTracking();
            if (MainCoreComponent == null)
                ScheduleMissingCoreRescan();
            OnUpgradeModulesChanged();
            QueueConnectorNetworkRefresh();
        }

        internal void ScheduleMissingCoreRescan()
        {
            if (!Session.IsServer) return;
            if (_closing || Deactivated || MainCoreComponent != null) return;
            if (!HasPotentialCoreBlocksInGroup())
            {
                ClearCoreRecoveryGrace("no potential core blocks in group", true);
                return;
            }

            _missingCoreConfirmedAbsent = false;
            ScheduleCoreRecoveryGrace("missing main core rescan scheduled");

            if (_nextMissingCoreRescanTick != 0) return;
            if (_missingCoreRescanAttempts >= MissingCoreRescanMaxAttempts && !IsCoreRecoveryGraceActive()) return;

            _nextMissingCoreRescanTick = Session.CurrentTick + MissingCoreRescanInitialDelayTicks;
        }

        internal void RunMissingCoreRescanTick()
        {
            if (!Session.IsServer) return;
            if (_closing || Deactivated)
            {
                ClearMissingCoreRescan();
                return;
            }

            if (MainCoreComponent != null)
            {
                ClearMissingCoreRescan();
                return;
            }

            TryStartCoreRecoveryGraceCountdown("main core still missing after transient guard");
            if (_missingCoreConfirmedAbsent)
                return;

            if (_coreRecoveryGraceActive)
            {
                NotifyCoreRecoveryGraceCountdown(false);
                if (_coreRecoveryGraceExpireTick != 0 && Session.CurrentTick >= _coreRecoveryGraceExpireTick)
                {
                    ExpireCoreRecoveryGrace();
                    return;
                }
            }

            if (_nextMissingCoreRescanTick == 0 || Session.CurrentTick < _nextMissingCoreRescanTick)
                return;

            if (!Session.IsGameThread)
            {
                MyAPIGateway.Utilities.InvokeOnGameThread(RunMissingCoreRescanTick);
                return;
            }

            _missingCoreRescanAttempts++;
            var foundCore = TryInitializeMissingCoreBlocks();
            if (MainCoreComponent != null)
            {
                ClearCoreRecoveryGrace("main core found during rescan", false);
                ClearMissingCoreRescan();
                return;
            }

            if (_missingCoreRescanAttempts >= MissingCoreRescanMaxAttempts)
            {
                if (IsCoreRecoveryGraceActive())
                {
                    _nextMissingCoreRescanTick = Session.CurrentTick + MissingCoreRescanRetryDelayTicks;
                    return;
                }

                _nextMissingCoreRescanTick = 0;
                if (foundCore)
                    Utils.Log("Missing core rescan found core blocks but none could become main for group " + GetGroupKey(), 1);
                ClearCoreRecoveryGrace(foundCore
                    ? "core blocks found but none could become main"
                    : "missing core rescan attempts exhausted", true);
                return;
            }

            _nextMissingCoreRescanTick = Session.CurrentTick + MissingCoreRescanRetryDelayTicks;
        }

        private bool TryInitializeMissingCoreBlocks()
        {
            if (_closing || Deactivated || MainCoreComponent != null) return false;

            var foundCore = false;
            BeginGridInitialization();
            try
            {
                foreach (var gridComponent in GridDictionary.Values)
                    if (gridComponent != null && gridComponent.InitializeCoreBlocks())
                        foundCore = true;
            }
            finally
            {
                EndGridInitialization();
            }

            if (foundCore)
            {
                InvalidateGameThreadStateCache(true);
                SyncNoCoreLimitTracking();
                OnUpgradeModulesChanged();
            }

            return foundCore;
        }

        private void ClearMissingCoreRescan()
        {
            _nextMissingCoreRescanTick = 0;
            _missingCoreRescanAttempts = 0;
        }


        private void CleanAuthoritativeStateBeforeGridCleanup()
        {
            if (Session.IsGameThread || Session.IsShuttingDown)
                RestoreConnectorShutOffBlocks(null);
            else
                MyAPIGateway.Utilities.InvokeOnGameThread(() => RestoreConnectorShutOffBlocks(null));
            try
            {
                if (MainCoreComponent != null)
                    UnregisterCoreLimitTracking();

                UnregisterNoCoreLimitTracking();
            }
            catch (Exception e)
            {
                Utils.Log("LOGGING EXCEPTION (most likely due to closure of world): " + e, 1);
            }

            ClearDefenseModifierCache();
            ClearPhysicalLinkedGroups();
        }

        private void CleanAuthoritativeStateAfterGridCleanup()
        {
            IncrementLimitGeneration();
        }

        private void SyncNoCoreLimitTracking()
        {
            if (Deactivated || MainCoreComponent != null)
            {
                UnregisterNoCoreLimitTracking();
                return;
            }

            RegisterNoCoreLimitTracking();
        }

        private void RegisterNoCoreLimitTracking()
        {
            RegisterNoCoreLimitTracking(OwnerId);
        }

        private void RegisterNoCoreLimitTracking(long ownerId)
        {
            var shipCore = ShipCore;
            var subtypeId = shipCore?.SubtypeId ?? string.Empty;
            if (string.IsNullOrWhiteSpace(subtypeId)) return;

            var factionId = GetFactionId(ownerId);
            if (_noCoreLimitsRegistered &&
                _registeredNoCoreLimitSubtypeId == subtypeId &&
                _registeredNoCoreLimitOwnerId == ownerId &&
                _registeredNoCoreLimitFactionId == factionId)
                return;

            UnregisterNoCoreLimitTracking();

            PerFactionManager.AddGridGroup(factionId, subtypeId);
            PerPlayerManager.AddGridGroup(ownerId, subtypeId);
            PerManifestGroupManager.AddGridGroup(subtypeId);

            Utils.Log("RegisterNoCoreLimitTracking: subtype=" + subtypeId + ", owner=" + ownerId +
                      ", faction=" + factionId + ", group=" + GetGroupKey() + ".", 2);

            _registeredNoCoreLimitSubtypeId = subtypeId;
            _registeredNoCoreLimitOwnerId = ownerId;
            _registeredNoCoreLimitFactionId = factionId;
            _noCoreLimitsRegistered = true;
            MarkRuntimeCountStatesDirty();
        }

        private void UnregisterNoCoreLimitTracking()
        {
            if (!_noCoreLimitsRegistered) return;

            var subtypeId = _registeredNoCoreLimitSubtypeId;
            if (!string.IsNullOrWhiteSpace(subtypeId))
            {
                PerFactionManager.RemoveGridGroup(_registeredNoCoreLimitFactionId, subtypeId);
                PerPlayerManager.RemoveGridGroup(_registeredNoCoreLimitOwnerId, subtypeId);
                PerManifestGroupManager.RemoveGridGroup(subtypeId);
                Utils.Log("UnregisterNoCoreLimitTracking: subtype=" + subtypeId +
                          ", owner=" + _registeredNoCoreLimitOwnerId +
                          ", faction=" + _registeredNoCoreLimitFactionId +
                          ", group=" + GetGroupKey() + ".", 2);
            }

            _registeredNoCoreLimitSubtypeId = string.Empty;
            _registeredNoCoreLimitOwnerId = 0;
            _registeredNoCoreLimitFactionId = -1;
            _noCoreLimitsRegistered = false;
            MarkRuntimeCountStatesDirty();
        }

        private void RegisterCoreLimitTracking()
        {
            RegisterCoreLimitTracking(OwnerId);
        }

        private void RegisterCoreLimitTracking(long ownerId)
        {
            var mainCore = MainCoreComponent;
            var subtypeId = mainCore?.SubtypeId ?? string.Empty;
            if (string.IsNullOrWhiteSpace(subtypeId)) return;

            var factionId = GetFactionId(ownerId);
            if (_coreLimitsRegistered &&
                _registeredCoreLimitSubtypeId == subtypeId &&
                _registeredCoreLimitOwnerId == ownerId &&
                _registeredCoreLimitFactionId == factionId)
                return;

            UnregisterCoreLimitTracking();

            PerFactionManager.AddGridGroup(factionId, subtypeId);
            PerPlayerManager.AddGridGroup(ownerId, subtypeId);
            PerManifestGroupManager.AddGridGroup(subtypeId);

            Utils.Log("RegisterCoreLimitTracking: subtype=" + subtypeId + ", owner=" + ownerId +
                      ", faction=" + factionId + ", group=" + GetGroupKey() + ".", 2);

            _registeredCoreLimitSubtypeId = subtypeId;
            _registeredCoreLimitOwnerId = ownerId;
            _registeredCoreLimitFactionId = factionId;
            _coreLimitsRegistered = true;
            MarkRuntimeCountStatesDirty();
        }

        private void UnregisterCoreLimitTracking()
        {
            if (!_coreLimitsRegistered) return;

            var subtypeId = _registeredCoreLimitSubtypeId;
            if (!string.IsNullOrWhiteSpace(subtypeId))
            {
                PerFactionManager.RemoveGridGroup(_registeredCoreLimitFactionId, subtypeId);
                PerPlayerManager.RemoveGridGroup(_registeredCoreLimitOwnerId, subtypeId);
                PerManifestGroupManager.RemoveGridGroup(subtypeId);
                Utils.Log("UnregisterCoreLimitTracking: subtype=" + subtypeId +
                          ", owner=" + _registeredCoreLimitOwnerId +
                          ", faction=" + _registeredCoreLimitFactionId +
                          ", group=" + GetGroupKey() + ".", 2);
            }

            _registeredCoreLimitSubtypeId = string.Empty;
            _registeredCoreLimitOwnerId = 0;
            _registeredCoreLimitFactionId = -1;
            _coreLimitsRegistered = false;
            MarkRuntimeCountStatesDirty();
        }

        private static void MarkRuntimeCountStatesDirty()
        {
            if (!Session.IsServer) return;
            foreach (var pair in Session.GroupDict)
                Session.MarkRuntimeStateDirty(pair.Value);
        }

        private void RefreshRegisteredLimitOwnership()
        {
            RefreshRegisteredLimitOwnership(OwnerId);
        }

        private void RefreshRegisteredLimitOwnership(long ownerId)
        {
            if (MainCoreComponent != null)
            {
                RegisterCoreLimitTracking(ownerId);
                return;
            }

            if (!_noCoreLimitsRegistered) return;
            UnregisterNoCoreLimitTracking();
            RegisterNoCoreLimitTracking(ownerId);
        }
    }
}
