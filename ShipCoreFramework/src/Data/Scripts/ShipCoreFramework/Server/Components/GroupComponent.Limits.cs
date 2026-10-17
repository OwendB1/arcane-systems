using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using Sandbox.ModAPI;
using VRage.Game.ModAPI;
using VRageMath;

namespace ShipCoreFramework
{
    internal partial class GroupComponent
    {
        internal static bool IsValidDirection(IMyCubeBlock directionReferenceBlock, IMySlimBlock block,
            List<DirectionType> allowedDirections, bool showNotification = true,
            DirectionType primaryDirection = DirectionType.Forward)
        {
            if (directionReferenceBlock?.Orientation == null || block?.Orientation == null ||
                allowedDirections == null || allowedDirections.Count == 0)
                return true;
            if (allowedDirections.Contains(DirectionType.Any)) return true;

            if (directionReferenceBlock.CubeGrid != block.CubeGrid)
                return Session.Config != null && !Session.Config.BlockDirectionalPlacementOnSubgrids;

            DirectionType xyDirection;
            if (!TryResolveBlockFacing(directionReferenceBlock, block, primaryDirection, out xyDirection))
                return true;
            var isValid = allowedDirections.Contains(xyDirection);
            if (!isValid && showNotification)
                Utils.ShowNotification(
                    Utils.GetLocalizedBlockName(block) + ": the direction " + xyDirection + " is invalid",
                    directionReferenceBlock.SlimBlock.BuiltBy);

            return isValid;
        }

        internal static DirectionReferenceSnapshot CaptureDirectionReference(IMyCubeBlock referenceBlock)
        {
            if (referenceBlock?.Orientation == null || referenceBlock.CubeGrid == null)
                return new DirectionReferenceSnapshot();

            return new DirectionReferenceSnapshot
            {
                Grid = referenceBlock.CubeGrid,
                Forward = Base6Directions.GetVector(referenceBlock.Orientation.Forward),
                Up = Base6Directions.GetVector(referenceBlock.Orientation.Up)
            };
        }

        internal static bool TryResolveBlockFacing(IMyCubeBlock referenceBlock, IMySlimBlock block,
            DirectionType primaryDirection, out DirectionType facing)
        {
            return TryResolveBlockFacing(CaptureDirectionReference(referenceBlock), block, primaryDirection,
                out facing);
        }

        internal static bool TryResolveBlockFacing(DirectionReferenceSnapshot reference, IMySlimBlock block,
            DirectionType primaryDirection, out DirectionType facing)
        {
            facing = DirectionType.Forward;
            if (!reference.IsValid || block?.Orientation == null || block.CubeGrid != reference.Grid)
                return false;

            var primaryAxis = GetBlockPrimaryDirectionVector(block, primaryDirection);
            facing = ResolveFacing(reference.Forward, reference.Up, primaryAxis);
            return facing != DirectionType.Any;
        }

        internal static bool HasAllowedDirectionRule(BlockLimit limit, BlockKey key)
        {
            var allowed = limit?.GetAllowedDirections(key);
            return allowed != null && allowed.Count > 0 && !allowed.Contains(DirectionType.Any);
        }

        internal static bool IsDirectionalSubgridBlocked(IMyCubeBlock referenceBlock, IMySlimBlock block,
            BlockLimit limit, BlockKey key)
        {
            if (referenceBlock?.CubeGrid == null || block?.CubeGrid == null ||
                referenceBlock.CubeGrid == block.CubeGrid)
                return false;
            if (limit == null || !limit.HasDirectionalBudget && !HasAllowedDirectionRule(limit, key))
                return false;
            return Session.Config == null || Session.Config.BlockDirectionalPlacementOnSubgrids;
        }

        internal static Vector3 GetBlockPrimaryDirectionVector(IMySlimBlock block, DirectionType primaryDirection)
        {
            var forward = Base6Directions.GetVector(block.Orientation.Forward);
            var up = Base6Directions.GetVector(block.Orientation.Up);

            switch (primaryDirection)
            {
                case DirectionType.Backward:
                    return Base6Directions.GetVector(
                        Base6Directions.GetOppositeDirection(block.Orientation.Forward));
                case DirectionType.Up:
                    return up;
                case DirectionType.Down:
                    return Base6Directions.GetVector(Base6Directions.GetOppositeDirection(block.Orientation.Up));
                case DirectionType.Left:
                    Vector3 left;
                    Vector3.Cross(ref up, ref forward, out left);
                    return left;
                case DirectionType.Right:
                    Vector3 right;
                    Vector3.Cross(ref forward, ref up, out right);
                    return right;
                default:
                    return forward;
            }
        }

        private sealed class PendingBlockPunishment
        {
            internal readonly IMySlimBlock Block;
            internal readonly PunishmentType Harm;
            internal readonly BlockLimit Limit;
            internal readonly bool ConnectorPunishment;

            internal PendingBlockPunishment(IMySlimBlock block, PunishmentType harm, BlockLimit limit,
                bool connectorPunishment = false)
            {
                Block = block;
                Harm = harm;
                Limit = limit;
                ConnectorPunishment = connectorPunishment;
            }
        }

        private sealed class GridLimitSnapshot
        {
            internal readonly GridComponent GridComponent;
            internal readonly ConcurrentDictionary<BlockLimit, LimitBucket> Limits;

            internal GridLimitSnapshot(GridComponent gridComponent,
                ConcurrentDictionary<BlockLimit, LimitBucket> limits)
            {
                GridComponent = gridComponent;
                Limits = limits;
            }
        }

        private bool IsBelowMinimumBlocksRequirement()
        {
            var minBlocks = ShipCore?.MinBlocks ?? -1;
            return minBlocks > 0 && GroupBlocksCount < minBlocks;
        }

        private int GetMinimumBlocksGraceTicks()
        {
            return SecondsToTicks(Session.Config == null ? 30 : Session.Config.MinimumBlocksGraceSeconds);
        }

        private string GetMinimumBlocksGateCountdownKey()
        {
            return "minimum-blocks:" + GetRepresentativeGridId();
        }

        private bool ClearMinimumBlocksLimitedBlockGateState(string reason)
        {
            var changed = _minimumBlocksLimitedBlockGateActive || _minimumBlocksGateActivationTick != 0;
            _minimumBlocksLimitedBlockGateActive = false;
            _minimumBlocksGateActivationTick = 0;
            _nextMinimumBlocksGateNotificationTick = 0;
            _lastMinimumBlocksGateNotificationSeconds = -1;

            if (changed)
            {
                BroadcastGroupCountdown(GetMinimumBlocksGateCountdownKey(), string.Empty, 0,
                    _minimumBlocksGateNotificationRecipients);
                Utils.Log("MinimumBlocksGate: cleared for group " + GetGroupKey() +
                          ". Reason: " + reason, 1);
            }

            return changed;
        }

        private void NotifyMinimumBlocksGateCountdown(bool force)
        {
            if (_minimumBlocksLimitedBlockGateActive || _minimumBlocksGateActivationTick == 0) return;

            var remainingSeconds = TicksToCeilingSeconds(_minimumBlocksGateActivationTick - Session.CurrentTick);
            if (remainingSeconds <= 0) return;

            if (!force &&
                Session.CurrentTick < _nextMinimumBlocksGateNotificationTick &&
                remainingSeconds == _lastMinimumBlocksGateNotificationSeconds)
                return;

            _lastMinimumBlocksGateNotificationSeconds = remainingSeconds;
            _nextMinimumBlocksGateNotificationTick = Session.CurrentTick +
                                                     (remainingSeconds <= 10 ? TicksPerSecond : TicksPerSecond * 5);
            BroadcastGroupCountdown(GetMinimumBlocksGateCountdownKey(), "Minimum block enforcement in",
                remainingSeconds, _minimumBlocksGateNotificationRecipients);
        }

        private bool RefreshMinimumBlocksLimitedBlockGateState()
        {
            var minBlocks = ShipCore?.MinBlocks ?? -1;
            if (minBlocks <= 0)
            {
                return ClearMinimumBlocksLimitedBlockGateState("minimum block requirement disabled");
            }

            if (IsBelowMinimumBlocksRequirement())
            {
                var changed = false;
                if (_minimumBlocksGateActivationTick == 0 && !_minimumBlocksLimitedBlockGateActive)
                {
                    var graceTicks = GetMinimumBlocksGraceTicks();
                    _minimumBlocksGateActivationTick = Session.CurrentTick + graceTicks;
                    _nextMinimumBlocksGateNotificationTick = 0;
                    _lastMinimumBlocksGateNotificationSeconds = -1;
                    changed = true;
                    Utils.Log("MinimumBlocksGate: countdown started for group " + GetGroupKey() +
                              ". Blocks=" + GroupBlocksCount + "/" + minBlocks +
                              ", activatesAtTick=" + _minimumBlocksGateActivationTick + ".", 1);
                    NotifyMinimumBlocksGateCountdown(true);
                }

                if (_minimumBlocksGateActivationTick != 0 &&
                    Session.CurrentTick < _minimumBlocksGateActivationTick)
                {
                    NotifyMinimumBlocksGateCountdown(false);
                    return changed;
                }

                if (!_minimumBlocksLimitedBlockGateActive)
                {
                    _minimumBlocksLimitedBlockGateActive = true;
                    BroadcastGroupCountdown(GetMinimumBlocksGateCountdownKey(), string.Empty, 0,
                        _minimumBlocksGateNotificationRecipients);
                    Utils.Log("MinimumBlocksGate: enforcement enabled for group " + GetGroupKey() +
                              ". Blocks=" + GroupBlocksCount + "/" + minBlocks + ".", 1);
                    return true;
                }

                return changed;
            }

            return ClearMinimumBlocksLimitedBlockGateState("minimum block requirement satisfied");
        }

        private bool IsMinimumBlocksLimitedBlockGateTriggered()
        {
            return _minimumBlocksLimitedBlockGateActive && IsBelowMinimumBlocksRequirement();
        }

        private string GetBelowMinimumBlocksLimitedBlockPunishmentReason()
        {
            return $"Below minimum blocks ({GroupBlocksCount}/{ShipCore.MinBlocks})";
        }

        private void ClearCoreRecoveryGracePunishmentState()
        {
            var changed = PunishSpeed || PunishModifiers || PunishLimitedBlocks ||
                          _minimumBlocksLimitedBlockGateActive || _minimumBlocksGateActivationTick != 0;

            PunishSpeed = false;
            PunishModifiers = false;
            PunishLimitedBlocks = false;
            if (_minimumBlocksLimitedBlockGateActive || _minimumBlocksGateActivationTick != 0)
                BroadcastGroupCountdown(GetMinimumBlocksGateCountdownKey(), string.Empty, 0,
                    _minimumBlocksGateNotificationRecipients);
            _minimumBlocksLimitedBlockGateActive = false;
            _minimumBlocksGateActivationTick = 0;
            _nextMinimumBlocksGateNotificationTick = 0;
            _lastMinimumBlocksGateNotificationSeconds = -1;
            InvalidateSpeedStateCache();
            InvalidateModifierStateCache();

            if (changed)
            {
                Session.MarkRuntimeStateDirty(this);
                Utils.Log("CoreRecoveryGrace: cleared punishment state for group " +
                          GetGroupKey() + ".", 1);
            }
        }

        private void RefreshLimitedBlockPunishmentState()
        {
            if (IsCoreRecoveryGraceActive())
            {
                var wasPunishing = PunishLimitedBlocks;
                PunishLimitedBlocks = false;
                if (wasPunishing)
                {
                    Session.MarkRuntimeStateDirty(this);
                    Utils.Log("RefreshLimitedBlockPunishmentState: cleared limited block punishment during core recovery grace for group " +
                              GetGroupKey() + ".", 1);
                }
                return;
            }

            if (Deactivated || IsIgnoredByAiOrFactionTagThreadSafe())
            {
                var wasPunishing = PunishLimitedBlocks;
                PunishLimitedBlocks = false;
                if (wasPunishing)
                {
                    Session.MarkRuntimeStateDirty(this);
                    Utils.Log("RefreshLimitedBlockPunishmentState: cleared limited block punishment for ignored/deactivated group " +
                              GetGroupKey() + ".", 1);
                }
                return;
            }

            var previous = PunishLimitedBlocks;
            PunishLimitedBlocks = IsMinimumBlocksLimitedBlockGateTriggered();
            if (previous != PunishLimitedBlocks)
            {
                Session.MarkRuntimeStateDirty(this);
                var reasons = GetLimitedBlockPunishmentGateDescriptions();
                Utils.Log("RefreshLimitedBlockPunishmentState: " +
                          (PunishLimitedBlocks ? "enabled" : "cleared") +
                          " limited block punishment for group " + GetGroupKey() +
                          (reasons.Count == 0 ? "." : ". Reasons: " + string.Join("; ", reasons)), 1);
            }
        }


        internal bool ShouldForceLimitedBlocksOff()
        {
            return !IsCoreRecoveryGraceActive() && !Deactivated && !IsIgnoredGroup() && PunishLimitedBlocks;
        }

        internal bool ShouldForceLimitedBlocksOff(BlockLimit limit)
        {
            return ShouldForceLimitedBlocksOff() && ShouldEvaluateBlockLimit(limit) &&
                   (limit == null || !limit.IsCriticalLimit);
        }

        internal void ScheduleExternalLimitValidation()
        {
            if (_closing) return;
            _pendingExternalLimitValidationTick = Session.CurrentTick + ExternalLimitValidationDelayTicks;
            Utils.Log("ScheduleExternalLimitValidation: group=" + GetGroupKey() +
                      ", owner=" + _lastOwnerId +
                      ", tick=" + _pendingExternalLimitValidationTick + ".", 2);
        }

        internal void BeginNexusLimitValidation()
        {
            if (_closing) return;
            _pendingNexusLimitValidation = true;
            _nexusLimitFailureConfirmations = 0;
            ScheduleNexusLimitValidation(true);
        }

        private void ScheduleNexusLimitValidation(bool restartGrace)
        {
            if (_closing) return;
            _pendingNexusLimitValidation = true;
            if (restartGrace) LimitsNexusSync.InvalidateFreshValidationState();
            _pendingExternalLimitValidationTick = Session.CurrentTick +
                                                  (restartGrace
                                                      ? NexusLimitValidationGraceTicks
                                                      : ExternalLimitValidationDelayTicks);
            Utils.Log("ScheduleNexusLimitValidation: group=" + GetGroupKey() +
                      ", confirmation=" + _nexusLimitFailureConfirmations +
                      ", tick=" + _pendingExternalLimitValidationTick + ".", 1);
        }

        private void ClearExternalLimitValidation()
        {
            _pendingExternalLimitValidationTick = 0;
            _pendingNexusLimitValidation = false;
            _nexusLimitFailureConfirmations = 0;
        }

        internal bool IsLimitPunishmentDeferred()
        {
            if (IsInitializingGrids) return true;

            foreach (var grid in GridDictionary.Keys)
                if (grid != null && grid.IsBlockTrasferInProgress)
                    return true;

            return false;
        }

        internal void OnBlockAddedToGroup(IMySlimBlock block, GridComponent.TrackedContribution contribution)
        {
            Session.MarkRuntimeStateDirty(this);
            ApplyGroupContribution(contribution, 1);
            QueuePunishmentStateRefresh();
            InvalidateGameThreadStateCache(true);
            IncrementLimitGeneration();
            InvalidateSpeedStateCache();
            Session.MarkPhysicalSpeedClusterSourceDirty(this);
            UpdateConnectedLimitContributions(block, true);

            var wasPunishingLimitedBlocks = PunishLimitedBlocks;
            if (RefreshMinimumBlocksLimitedBlockGateState())
            {
                RefreshLimitedBlockPunishmentState();
                if (!wasPunishingLimitedBlocks && PunishLimitedBlocks)
                    EnforceGroupPunishment(true);
            }
        }

        internal void OnBlockRemovedFromGroup(IMySlimBlock block, GridComponent.TrackedContribution contribution)
        {
            Session.MarkRuntimeStateDirty(this);
            ApplyGroupContribution(contribution, -1);
            QueuePunishmentStateRefresh();
            InvalidateGameThreadStateCache(true);
            IncrementLimitGeneration();

            InvalidateSpeedStateCache();
            Session.MarkPhysicalSpeedClusterSourceDirty(this);
            UpdateConnectedLimitContributions(block, false);

            var wasPunishingLimitedBlocks = PunishLimitedBlocks;
            if (RefreshMinimumBlocksLimitedBlockGateState())
            {
                RefreshLimitedBlockPunishmentState();
                if (!wasPunishingLimitedBlocks && PunishLimitedBlocks)
                    EnforceGroupPunishment(true);
            }
        }

        internal void OnBlockPcuChanged(int delta)
        {
            if (delta == 0) return;
            AddGroupPCU(delta);
            QueuePunishmentStateRefresh();
            IncrementLimitGeneration();
            Session.MarkRuntimeStateDirty(this);
        }

        internal void RunLimitedBlockPunishmentTick()
        {
            if (!Session.IsServer) return;
            if (IsCoreRecoveryGraceActive())
            {
                ClearCoreRecoveryGracePunishmentState();
                return;
            }

            if (_closing || Deactivated || IsIgnoredGroup())
            {
                ClearMinimumBlocksLimitedBlockGateState("group closing, deactivated, or ignored");
                var clearedLimitedBlockPunishment = PunishLimitedBlocks;
                PunishLimitedBlocks = false;
                if (clearedLimitedBlockPunishment) Session.MarkRuntimeStateDirty(this);
                return;
            }

            var wasPunishingLimitedBlocks = PunishLimitedBlocks;
            RefreshMinimumBlocksLimitedBlockGateState();
            RefreshLimitedBlockPunishmentState();
            if (!wasPunishingLimitedBlocks && PunishLimitedBlocks)
                EnforceGroupPunishment(true);
        }

        internal void RunExternalLimitValidationTick()
        {
            if (!Session.IsServer) return;
            if (_closing)
            {
                ClearExternalLimitValidation();
                return;
            }

            if (_pendingExternalLimitValidationTick == 0 || Session.CurrentTick < _pendingExternalLimitValidationTick)
                return;

            if (!_pendingNexusLimitValidation && LimitsNexusSync.IsSettling)
            {
                Utils.Log("RunExternalLimitValidationTick: Nexus settling, rescheduling validation for group " +
                          GetGroupKey() + ".", 2);
                ScheduleExternalLimitValidation();
                return;
            }

            _pendingExternalLimitValidationTick = 0;

            if (Session.IsGameThread)
            {
                ExecuteExternalLimitValidation();
                return;
            }

            MyAPIGateway.Utilities.InvokeOnGameThread(ExecuteExternalLimitValidation);
        }

        private void ExecuteExternalLimitValidation()
        {
            if (_closing || Session.IsShuttingDown) return;

            var mainCore = MainCoreComponent;
            if (mainCore?.CoreBlock?.SlimBlock == null) return;
            if (mainCore.CoreBlock.MarkedForClose || mainCore.CoreBlock.Closed) return;

            var subtypeId = mainCore.SubtypeId;
            if (string.IsNullOrEmpty(subtypeId)) return;
            if (IsIgnoredNpcGroup()) return;
            if (ShouldDeferOwnerLimitValidation(subtypeId))
            {
                Utils.Log("ExecuteExternalLimitValidation: owner unavailable for " + subtypeId +
                          " on group " + GetGroupKey() + "; rescheduling.", 2);
                if (_pendingNexusLimitValidation)
                    ScheduleNexusLimitValidation(false);
                else
                    ScheduleExternalLimitValidation();
                return;
            }

            if (_pendingNexusLimitValidation)
            {
                string waitReason;
                if (!LimitsNexusSync.TryGetFreshValidationState(out waitReason))
                {
                    Utils.Log("ExecuteExternalLimitValidation: group " + GetGroupKey() + " is " +
                              waitReason + "; keeping core and retrying.", 3);
                    ScheduleNexusLimitValidation(false);
                    return;
                }
            }

            var notify = !_pendingNexusLimitValidation || _nexusLimitFailureConfirmations > 0;
            var factionOk = PerFactionManager.IsGroupWithinFactionLimits(OwningFaction, OwnerId, subtypeId, notify);
            var playerOk = PerPlayerManager.IsGroupWithinPlayerLimits(OwnerId, subtypeId, notify);
            var manifestOk = PerManifestGroupManager.IsGroupWithinManifestLimits(subtypeId, OwnerId, notify);
            if (factionOk && playerOk && manifestOk)
            {
                ClearExternalLimitValidation();
                return;
            }

            LogExternalLimitFailure(subtypeId, factionOk, playerOk, manifestOk);

            if (_pendingNexusLimitValidation && _nexusLimitFailureConfirmations == 0)
            {
                _nexusLimitFailureConfirmations = 1;
                Utils.Log("ExecuteExternalLimitValidation: first fresh failure for " + subtypeId +
                          " on group " + GetGroupKey() + "; requiring a second fresh Nexus round.", 1);
                ScheduleNexusLimitValidation(true);
                return;
            }

            Utils.Log("ExecuteExternalLimitValidation: removing core " + subtypeId +
                      " from group " + GetGroupKey() +
                      " because owner, faction, or manifest limits failed.", 1);
            ClearExternalLimitValidation();
            mainCore.CoreBlock.SlimBlock.RemoveAndRefund();
            ResetCore();
        }

        private void LogExternalLimitFailure(string subtypeId, bool factionOk, bool playerOk, bool manifestOk)
        {
            var ownerId = OwnerId;
            var remotePlayerCount = LimitsNexusSync.GetRemotePlayerCount(ownerId, subtypeId);
            var totalPlayerCount = PerPlayerManager.GetCurrentCount(ownerId, subtypeId);
            var localPlayerCount = totalPlayerCount - remotePlayerCount;
            var core = Session.Config.GetShipCoreByTypeId(subtypeId);
            var maxPerPlayer = core?.MaxPerPlayer ?? -1;

            Utils.Log("ExternalLimitFailure: server=" + LimitsNexusSync.CurrentServerId +
                      ", group=" + GetGroupKey() +
                      ", owner=" + ownerId +
                      ", core=" + subtypeId +
                      ", playerLocal=" + localPlayerCount +
                      ", playerRemote=" + remotePlayerCount +
                      ", playerTotal=" + totalPlayerCount +
                      ", maxPerPlayer=" + maxPerPlayer +
                      ", remoteByServer=" + LimitsNexusSync.DescribeRemotePlayerCounts(ownerId, subtypeId) +
                      ", factionOk=" + factionOk +
                      ", playerOk=" + playerOk +
                      ", manifestOk=" + manifestOk + ".", 1);
        }
        

        internal void EnforceConnectorLimitPunishment()
        {
            EnforceGroupPunishment(false, true);
        }

        private void EnforceGroupPunishment(bool forceShutOffPunishment = false,
            bool connectorOnly = false)
        {
            if (!Session.IsServer || _closing || Session.IsShuttingDown) return;
            if (!Session.IsGameThread)
            {
                MyAPIGateway.Utilities.InvokeOnGameThread(() =>
                    EnforceGroupPunishment(forceShutOffPunishment, connectorOnly));
                return;
            }
            if (IsLimitPunishmentDeferred()) return;
            if (IsCoreRecoveryGraceActive() || Deactivated || IsIgnoredGroup())
            {
                RestoreConnectorShutOffBlocks(null);
                return;
            }

            if (!connectorOnly) RefreshPunishmentFlags();
            forceShutOffPunishment |= ShouldForceLimitedBlocksOff();

            var generation = GetLimitGeneration();
            var directionReferenceBlock = connectorOnly ? null : GetDirectionLockReferenceBlock();
            var pendingPunishments = new List<PendingBlockPunishment>();
            foreach (var kv in Limits)
            {
                var limit = kv.Key;
                var bucket = kv.Value;

                if (limit == null || bucket == null) continue;
                if (!ShouldEvaluateBlockLimit(limit)) continue;

                double total;
                double connectorTotal;
                float effectiveMaxCount;
                var directionTotals = new double[6];
                List<IMySlimBlock> membersCopy;
                HashSet<IMySlimBlock> connectorMembersCopy;
                lock (bucket.BucketLock)
                {
                    if (connectorOnly && bucket.ConnectorWeight <= 0d) continue;
                    total = bucket.TotalWeight;
                    connectorTotal = bucket.ConnectorWeight;
                    effectiveMaxCount = forceShutOffPunishment ? 0f : GetEffectiveMaxCount(limit);
                    // No connector can exceed the remaining capacity; execution still restores old shutdowns.
                    if (connectorOnly && !forceShutOffPunishment &&
                        Math.Max(total, connectorTotal) <= effectiveMaxCount) continue;
                    Array.Copy(bucket.DirectionWeights, directionTotals,
                        Math.Min(bucket.DirectionWeights.Length, directionTotals.Length));
                    membersCopy = connectorOnly
                        ? new List<IMySlimBlock>(bucket.ConnectorMembers)
                        : new List<IMySlimBlock>(bucket.Members);
                    connectorMembersCopy = new HashSet<IMySlimBlock>(bucket.ConnectorMembers);
                }

                if (forceShutOffPunishment)
                {
                    if (limit.IsCriticalLimit) continue;

                    foreach (var block in membersCopy)
                    {
                        if (block == null || block.IsMovedBySplit || block.CubeGrid == null) continue;
                        if (connectorOnly && !connectorMembersCopy.Contains(block)) continue;
                        if (limit.GetWeight(GridComponent.KeyOf(block)) <= 0d) continue;

                        pendingPunishments.Add(new PendingBlockPunishment(block, PunishmentType.ShutOff, limit,
                            connectorMembersCopy.Contains(block)));
                    }

                    continue;
                }

                var localCandidates = new List<KeyValuePair<IMySlimBlock, double>>(membersCopy.Count);
                var connectorCandidates = new List<KeyValuePair<IMySlimBlock, double>>(connectorMembersCopy.Count);
                var directionCandidates = new List<KeyValuePair<IMySlimBlock, double>>[6];
                var alreadyShutOffConnectorWeight = 0d;

                foreach (var block in membersCopy)
                {
                    if (block == null || block.IsMovedBySplit || block.CubeGrid == null) continue;

                    var isConnectorMember = connectorMembersCopy.Contains(block);

                    if (!isConnectorMember && !connectorOnly &&
                        DoesBlockViolateAllowedDirection(directionReferenceBlock, limit, block))
                    {
                        NotifyDirectionalPlacementViolation(directionReferenceBlock, block);
                        pendingPunishments.Add(new PendingBlockPunishment(block, limit.PunishmentType, limit));
                        continue;
                    }

                    var weight = limit.GetWeight(GridComponent.KeyOf(block));
                    if (weight <= 0d) continue;
                    if (isConnectorMember)
                    {
                        var functionalBlock = block.FatBlock as IMyFunctionalBlock;
                        if (functionalBlock == null) continue;
                        if (!functionalBlock.Enabled && !ConnectorShutOffOwners.ContainsKey(functionalBlock))
                        {
                            alreadyShutOffConnectorWeight += weight;
                            continue;
                        }

                        connectorCandidates.Add(new KeyValuePair<IMySlimBlock, double>(block, weight));
                    }
                    else if (!connectorOnly)
                    {
                        localCandidates.Add(new KeyValuePair<IMySlimBlock, double>(block, weight));
                        if (limit.HasDirectionalBudget)
                        {
                            BlockType matchedBlockType = limit.GetMatchingBlockType(GridComponent.KeyOf(block));
                            DirectionType facing;
                            if (matchedBlockType != null && TryResolveBlockFacing(directionReferenceBlock, block,
                                    matchedBlockType.PrimaryDirection, out facing))
                            {
                                var directionIndex = (int)facing;
                                if (directionCandidates[directionIndex] == null)
                                    directionCandidates[directionIndex] =
                                        new List<KeyValuePair<IMySlimBlock, double>>();
                                directionCandidates[directionIndex].Add(
                                    new KeyValuePair<IMySlimBlock, double>(block, weight));
                            }
                        }
                    }
                }

                var directionPunishments = new HashSet<IMySlimBlock>();
                var directionPunishedWeight = 0d;
                if (!connectorOnly && limit.HasDirectionalBudget)
                {
                    for (var directionIndex = 0; directionIndex < directionTotals.Length; directionIndex++)
                    {
                        var directionMax = limit.GetMaxCountForDirection((DirectionType)directionIndex);
                        if (directionMax < 0f) continue;
                        var directionOver = directionTotals[directionIndex] - directionMax;
                        var candidates = directionCandidates[directionIndex];
                        if (directionOver <= 0d || candidates == null) continue;

                        candidates.Sort(ComparePunishmentCandidates);
                        foreach (var candidate in candidates)
                        {
                            if (directionOver <= 0d) break;
                            if (candidate.Key == null || !directionPunishments.Add(candidate.Key)) continue;

                            pendingPunishments.Add(new PendingBlockPunishment(candidate.Key, limit.PunishmentType,
                                limit));
                            directionPunishedWeight += candidate.Value;
                            directionOver -= candidate.Value;
                        }
                    }
                }

                var localTotal = Math.Max(0d, total - connectorTotal);
                if (!connectorOnly && localTotal > effectiveMaxCount)
                {
                    var localOver = localTotal - effectiveMaxCount - directionPunishedWeight;
                    localCandidates.Sort(ComparePunishmentCandidates);
                    foreach (var candidate in localCandidates)
                    {
                        if (localOver <= 0d) break;
                        if (candidate.Key == null || directionPunishments.Contains(candidate.Key)) continue;

                        pendingPunishments.Add(new PendingBlockPunishment(candidate.Key, limit.PunishmentType,
                            limit));
                        localOver -= candidate.Value;
                    }
                }

                var connectorCapacity = Math.Max(0d, effectiveMaxCount - localTotal);
                var connectorOver = connectorTotal - connectorCapacity - alreadyShutOffConnectorWeight;
                if (connectorOver <= 0d) continue;

                connectorCandidates.Sort(ComparePunishmentCandidates);
                foreach (var candidate in connectorCandidates)
                {
                    if (connectorOver <= 0d) break;
                    if (candidate.Key == null) continue;

                    pendingPunishments.Add(new PendingBlockPunishment(candidate.Key, PunishmentType.ShutOff,
                        limit, true));
                    connectorOver -= candidate.Value;
                }
            }

            if (pendingPunishments.Count > 0)
                Utils.Log("EnforceGroupPunishment: queued " + pendingPunishments.Count +
                          " block punishments for group " + GetGroupKey() +
                          ", forceShutOff=" + forceShutOffPunishment + ".", 1);
            ExecutePendingPunishments(pendingPunishments, generation);
        }

        private static int ComparePunishmentCandidates(KeyValuePair<IMySlimBlock, double> left,
            KeyValuePair<IMySlimBlock, double> right)
        {
            var compare = left.Value.CompareTo(right.Value);
            if (compare != 0) return compare;

            var leftGridId = left.Key?.CubeGrid?.EntityId ?? 0L;
            var rightGridId = right.Key?.CubeGrid?.EntityId ?? 0L;
            compare = leftGridId.CompareTo(rightGridId);
            if (compare != 0) return compare;

            var leftPosition = left.Key == null ? Vector3I.Zero : left.Key.Position;
            var rightPosition = right.Key == null ? Vector3I.Zero : right.Key.Position;
            compare = leftPosition.X.CompareTo(rightPosition.X);
            if (compare != 0) return compare;
            compare = leftPosition.Y.CompareTo(rightPosition.Y);
            return compare != 0 ? compare : leftPosition.Z.CompareTo(rightPosition.Z);
        }

        internal bool DoesBlockViolateAllowedDirection(BlockLimit limit, IMySlimBlock block)
        {
            return DoesBlockViolateAllowedDirection(GetDirectionLockReferenceBlock(), limit, block);
        }

        private static bool DoesBlockViolateAllowedDirection(IMyCubeBlock directionReferenceBlock, BlockLimit limit,
            IMySlimBlock block)
        {
            if (limit == null || directionReferenceBlock == null || block == null) return false;

            BlockKey blockKey = GridComponent.KeyOf(block);
            BlockType matchedBlockType = limit.GetMatchingBlockType(blockKey);
            if (matchedBlockType == null) return false;

            if (IsDirectionalSubgridBlocked(directionReferenceBlock, block, limit, blockKey))
                return true;

            return !IsValidDirection(directionReferenceBlock, block, limit.GetAllowedDirections(blockKey), false,
                matchedBlockType.PrimaryDirection);
        }

        private void NotifyDirectionalPlacementViolation(IMyCubeBlock directionReferenceBlock, IMySlimBlock block)
        {
            if (directionReferenceBlock == null || block == null) return;

            var playerId = directionReferenceBlock.SlimBlock.BuiltBy;
            var terminalBlock = directionReferenceBlock as IMyTerminalBlock;
            if (playerId == 0 && terminalBlock != null) playerId = terminalBlock.OwnerId;

            var mainCoreBlock = MainCoreComponent?.CoreBlock;
            var controller = directionReferenceBlock as IMyShipController;
            var referenceName = ReferenceEquals(mainCoreBlock, directionReferenceBlock)
                ? "Core"
                : controller != null && controller.IsMainCockpit
                    ? "Main cockpit"
                    : "Cockpit";

            Utils.ShowNotification(
                referenceName + " orientation violates directional locking for " + Utils.GetLocalizedBlockName(block),
                playerId);
        }

        // EnforceGroupPunishment keeps selection on the game thread because it reads live block state.
        private void ExecutePendingPunishments(List<PendingBlockPunishment> punishments, int generation)
        {
            if (punishments == null) return;

            var representativeGridId = GetRepresentativeGridId();
            MyAPIGateway.Utilities.InvokeOnGameThread(() =>
            {
                if (_closing || Session.IsShuttingDown) return;
                if (generation != GetLimitGeneration()) return;
                if (IsLimitPunishmentDeferred()) return;

                var stillPunished = new HashSet<IMyFunctionalBlock>();
                var appliedPunishments = 0;
                foreach (var punishment in punishments)
                {
                    if (!ShouldEvaluateBlockLimit(punishment.Limit)) continue;
                    var block = punishment.Block;
                    if (block == null || block.IsMovedBySplit || block.CubeGrid == null) continue;
                    if (block.CubeGrid.MarkedForClose || block.CubeGrid.Closed) continue;

                    if (punishment.ConnectorPunishment)
                    {
                        var functionalBlock = block.FatBlock as IMyFunctionalBlock;
                        if (functionalBlock != null)
                        {
                            TrackConnectorShutOff(functionalBlock);
                            stillPunished.Add(functionalBlock);
                            if (!functionalBlock.Enabled) continue;
                        }
                    }
                    block.WhackABlock(punishment.Harm);
                    appliedPunishments++;
                }

                RestoreConnectorShutOffBlocks(stillPunished);

                if (appliedPunishments > 0 && MyGroup != null)
                {
                    MarkLimitsEnforced(appliedPunishments);
                    Session.MarkRuntimeStateDirty(this);
                    Utils.Log("ExecutePendingPunishments: applied " + appliedPunishments +
                              " block punishments for group " + GetGroupKey() + ".", 1);
                    ModAPI.BroadcastLimitsEnforced(representativeGridId, appliedPunishments);
                }
            });
        }


        private float ComputeEffectiveMaxCount(BlockLimit limit)
        {
            return ComputeEffectiveMaxCount(ShipCore, limit, GetEffectiveUpgradeModules(true));
        }

        private static float ComputeEffectiveMaxCount(ShipCore shipCore, BlockLimit limit,
            IEnumerable<UpgradeModuleComponent> modules)
        {
            if (limit == null) return 0f;

            var maxCount = limit.MaxCount;
            foreach (var module in modules)
            {
                var config = module.GetConfig();
                if (config?.BlockLimitModifiers == null) continue;

                foreach (var limitModifier in config.BlockLimitModifiers.Where(limitModifier =>
                             limitModifier != null &&
                             limitModifier.BlockLimitName.Equals(limit.Name, StringComparison.OrdinalIgnoreCase)))
                {
                    maxCount = CubeGridModifiers.ApplyUpgradeModifier(maxCount, limitModifier.Value,
                        limitModifier.ModifierType);
                }
            }

            return maxCount;
        }

        private int ComputeEffectiveMaxBlocks()
        {
            return ComputeEffectiveMaxBlocks(ShipCore, GetEffectiveUpgradeModules(true));
        }

        private static int ComputeEffectiveMaxBlocks(ShipCore shipCore,
            IEnumerable<UpgradeModuleComponent> modules)
        {
            var max = shipCore.MaxBlocks;
            if (max <= 0) return max;
            foreach (var module in modules)
            {
                var config = module.GetConfig();
                if (config?.CapacityModifiers == null) continue;
                foreach (var cm in config.CapacityModifiers)
                {
                    if (cm != null && cm.Stat.Equals("MaxBlocks", StringComparison.OrdinalIgnoreCase))
                        max = (int)CubeGridModifiers.ApplyUpgradeModifier(max, cm.Value, cm.ModifierType);
                }
            }
            return max;
        }

        private float ComputeEffectiveMaxMass()
        {
            return ComputeEffectiveMaxMass(ShipCore, GetEffectiveUpgradeModules(true));
        }

        private static float ComputeEffectiveMaxMass(ShipCore shipCore,
            IEnumerable<UpgradeModuleComponent> modules)
        {
            var max = shipCore.MaxMass;
            if (max <= 0) return max;
            foreach (var module in modules)
            {
                var config = module.GetConfig();
                if (config?.CapacityModifiers == null) continue;
                foreach (var cm in config.CapacityModifiers)
                {
                    if (cm != null && cm.Stat.Equals("MaxMass", StringComparison.OrdinalIgnoreCase))
                        max = CubeGridModifiers.ApplyUpgradeModifier(max, cm.Value, cm.ModifierType);
                }
            }
            return max;
        }

        private int ComputeEffectiveMaxPCU()
        {
            return ComputeEffectiveMaxPCU(ShipCore, GetEffectiveUpgradeModules(true));
        }

        private static int ComputeEffectiveMaxPCU(ShipCore shipCore,
            IEnumerable<UpgradeModuleComponent> modules)
        {
            var max = shipCore.MaxPCU;
            if (max <= 0) return max;
            foreach (var module in modules)
            {
                var config = module.GetConfig();
                if (config?.CapacityModifiers == null) continue;
                foreach (var cm in config.CapacityModifiers)
                {
                    if (cm != null && cm.Stat.Equals("MaxPCU", StringComparison.OrdinalIgnoreCase))
                        max = (int)CubeGridModifiers.ApplyUpgradeModifier(max, cm.Value, cm.ModifierType);
                }
            }
            return max;
        }

        private void RefreshEffectiveLimitCache()
        {
            _cachedEffectiveMaxBlocks = ComputeEffectiveMaxBlocks();
            _cachedEffectiveMaxPCU = ComputeEffectiveMaxPCU();
            _cachedEffectiveMaxMass = ComputeEffectiveMaxMass();

            var effectiveMaxCounts = new Dictionary<BlockLimit, float>();
            var blockLimits = ShipCore.BlockLimits;
            if (blockLimits != null)
            {
                foreach (var limit in blockLimits)
                    if (limit != null)
                        effectiveMaxCounts[limit] = ComputeEffectiveMaxCount(limit);
            }

            _cachedEffectiveMaxCounts = effectiveMaxCounts;
        }


        private void QueueRecalculateAllLimits(bool enforceAfterPublish, bool forceShutOffPunishment,
            bool rebuildConnectorLimits = false)
        {
            if (!Session.IsServer) return;
            var generation = GetLimitGeneration();
            var directionReference = CaptureDirectionReference(GetDirectionLockReferenceBlock());
            MyAPIGateway.Parallel.StartBackground(() =>
            {
                if (!BuildAndPublishLimitSnapshots(generation, rebuildConnectorLimits, directionReference)) return;
                if (enforceAfterPublish)
                    EnforceGroupPunishment(forceShutOffPunishment);
            });
        }

        private bool BuildAndPublishLimitSnapshots(int generation, bool rebuildConnectorLimits,
            DirectionReferenceSnapshot directionReference)
        {
            if (_closing || Session.IsShuttingDown) return false;

            var groupLimits = new ConcurrentDictionary<BlockLimit, LimitBucket>();
            var gridSnapshots = new List<GridLimitSnapshot>();

            foreach (var comp in GridDictionary.Values)
            {
                var gridLimits = comp.BuildLimitsSnapshot(this, directionReference);
                gridSnapshots.Add(new GridLimitSnapshot(comp, gridLimits));

                foreach (var gridLimitKv in gridLimits)
                {
                    var limit = gridLimitKv.Key;
                    var gridBucket = gridLimitKv.Value;

                    var groupBucket = groupLimits.GetOrAdd(limit, _ => new LimitBucket(0d));

                    lock (gridBucket.BucketLock)
                    {
                        lock (groupBucket.BucketLock)
                        {
                            groupBucket.TotalWeight += gridBucket.TotalWeight;
                            for (var directionIndex = 0; directionIndex < groupBucket.DirectionWeights.Length;
                                 directionIndex++)
                                groupBucket.DirectionWeights[directionIndex] +=
                                    gridBucket.DirectionWeights[directionIndex];
                            groupBucket.Members.AddRange(gridBucket.Members);
                        }
                    }
                }
            }

            if (rebuildConnectorLimits)
                ApplyConnectorLimitContributions(groupLimits);
            else
                CopyConnectorLimitContributions(groupLimits);

            lock (_limitSnapshotLock)
            {
                if (_closing || Session.IsShuttingDown || generation != GetLimitGeneration())
                    return false;

                foreach (var snapshot in gridSnapshots)
                    if (snapshot.GridComponent != null)
                        snapshot.GridComponent.PublishLimitsSnapshot(snapshot.Limits);

                PublishLimitsSnapshot(groupLimits);
                MarkLimitsPublished();
                Session.MarkRuntimeStateDirty(this);
            }

            if (MyGroup != null)
            {
                var representativeGridId = GetRepresentativeGridId();
                if (Session.IsGameThread)
                    ModAPI.BroadcastLimitsRecalculated(representativeGridId);
                else
                    MyAPIGateway.Utilities.InvokeOnGameThread(() =>
                    {
                        if (!_closing && !Session.IsShuttingDown)
                            ModAPI.BroadcastLimitsRecalculated(representativeGridId);
                    });
            }

            return true;
        }

    }
}
