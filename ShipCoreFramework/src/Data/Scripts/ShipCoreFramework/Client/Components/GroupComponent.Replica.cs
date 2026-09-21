using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Threading;
using Sandbox.Game.Entities;
using VRage.Game.Entity;
using VRage.Game.ModAPI;

namespace ShipCoreFramework
{
    internal partial class GroupComponent
    {
        internal void ApplyRuntimeState(GroupRuntimeState state)
        {
            if (Session.IsServer || state == null || _closing) return;

            var nextModifiers = FromRuntimeData(state.Modifiers);
            var modifiersChanged = !_runtimeStateReceived || !SameModifiers(_cachedActiveGridModifiers, nextModifiers);
            var broadcastChanges = _runtimeStateReceived;
            var previousCoreBlockId = _runtimeMainCoreBlockId;
            var previousCoreSubtypeId = _runtimeCoreSubtypeId;
            var previousBoostActive = BoostEnabled;
            var previousDefenseActive = _activeDefenseEnabled;
            var previousGridIds = _cachedMechanicalGridIds ?? Array.Empty<long>();
            var previousLimitRevision = _runtimeLimitRevision;
            var previousLimitEnforcementRevision = _runtimeLimitEnforcementRevision;
            _runtimeStateReceived = true;
            _runtimeCoreSubtypeId = state.CoreSubtypeId ?? string.Empty;
            _runtimeOwnerId = state.OwnerId;
            _runtimeMainCoreBlockId = state.MainCoreBlockId;
            _runtimeCoreCount = state.CoreCount;
            _runtimePlayerCoreCount = state.PlayerCoreCount;
            _runtimeFactionCoreCount = state.FactionCoreCount;
            _runtimeFactionPlayerCount = state.FactionPlayerCount;
            _runtimeEffectiveFactionCoreLimit = state.EffectiveFactionCoreLimit;
            _runtimeManifestCounts = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
            if (state.ManifestCounts != null)
                foreach (var count in state.ManifestCounts)
                {
                    if (count != null && !string.IsNullOrEmpty(count.Name))
                        _runtimeManifestCounts[count.Name] = count.Count;
                }
            _runtimeSpeedPunishmentReasons = state.SpeedPunishmentReasons ?? Array.Empty<string>();
            _runtimeModifierPunishmentReasons = state.ModifierPunishmentReasons ?? Array.Empty<string>();
            _runtimeLimitedBlockPunishmentReasons = state.LimitedBlockPunishmentReasons ?? Array.Empty<string>();
            _runtimeLimitRevision = state.LimitRevision;
            _runtimeLimitEnforcementRevision = state.LimitEnforcementRevision;
            _lastOwnerId = state.OwnerId;
            Deactivated = state.Deactivated;
            PunishModifiers = state.PunishModifiers;
            PunishSpeed = state.PunishSpeed;
            PunishLimitedBlocks = state.PunishLimitedBlocks;
            lock (_abilityStateLock)
            {
                _activeDefenseEnabled = state.ActiveDefense;
                _activeDefenseDurationTimer = state.ActiveDefenseDurationTimer;
                _activeDefenseCooldownTimer = state.ActiveDefenseCooldownTimer;
                _powerOverclockActive = state.PowerOverclockActive;
                _powerOverclockDurationTimer = state.PowerOverclockDurationTimer;
                _powerOverclockCooldownTimer = state.PowerOverclockCooldownTimer;
            }
            _runtimeAbilityStateTick = Session.CurrentTick;

            Interlocked.Exchange(ref _groupBlocksCount, Math.Max(0, state.BlockCount));
            Interlocked.Exchange(ref _cachedGroupPCU, Math.Max(0, state.Pcu));
            _cachedDryMass = state.DryMass;
            _cachedEffectiveMaxBlocks = state.MaxBlocks;
            _cachedEffectiveMaxPCU = state.MaxPcu;
            _cachedEffectiveMaxMass = state.MaxMass;
            Interlocked.Exchange(ref _cachedRepresentativeGridId,
                state.RepresentativeGridId == 0 ? state.GroupId : state.RepresentativeGridId);
            _cachedMechanicalGridIds = state.GridIds ?? Array.Empty<long>();
            _cachedIsIgnoredGroup = state.Ignored;
            _cachedIsIgnoredByAiOrFactionTag = state.Ignored;
            MyEntity directionEntity;
            _cachedNoCoreDirectionLockReferenceBlock = state.DirectionReferenceBlockId != 0 &&
                                                        MyEntities.TryGetEntityById(state.DirectionReferenceBlockId, out directionEntity)
                ? directionEntity as IMyCubeBlock
                : null;
            _gridStateCacheDirty = false;
            _ignoredStateCacheDirty = false;
            _directionReferenceCacheDirty = false;

            lock (SpeedStateLock)
            {
                BoostEnabled = state.BoostActive;
                _boostDurationTimer = state.BoostDurationTimer;
                _boostCooldownTimer = state.BoostCooldownTimer;
                BaseSpeedLimitMetersPerSecond = state.BaseSpeed;
                EffectiveSpeedLimitMetersPerSecond = state.EffectiveSpeed;
                SpeedSourceGroupGridId = state.SpeedSourceGridId;
                EffectiveBoostEnabled = state.EffectiveBoostActive;
                EffectiveSpeedRampDownActive = state.SpeedRampDownActive;
                EffectiveSpeedRampDownTargetCap = state.SpeedRampDownTarget;
                _runtimeSpeedRampDownLastTick = Session.CurrentTick;
                FrictionEnforcementEnabled = state.FrictionEnabled;
                FrictionMaximumDecelerationOverride = state.FrictionMaximumDecelerationOverride;
                MinimumFrictionSpeedAbsoluteOverride = state.MinimumFrictionSpeedAbsoluteOverride;
                MaximumFrictionSpeedAbsoluteOverride = state.MaximumFrictionSpeedAbsoluteOverride;
                MinimumFrictionSpeedModifierOverride = state.MinimumFrictionSpeedModifierOverride;
                MaximumFrictionSpeedModifierOverride = state.MaximumFrictionSpeedModifierOverride;
            }

            _cachedActiveGridModifiers = nextModifiers;
            _cachedActiveSpeedModifiers = FromRuntimeData(state.SpeedModifiers);
            _cachedPassiveDefenseModifiers = FromRuntimeData(state.PassiveDefenseModifiers);
            _cachedActiveDefenseModifiers = FromRuntimeData(state.ActiveDefenseModifiers);
            _modifierStateCacheDirty = false;
            PublishRuntimeLimits(state.Limits);
            ApplyRuntimeCore(state.MainCoreBlockId);
            if (modifiersChanged) ApplyModifiers(_cachedActiveGridModifiers);
            if (broadcastChanges)
                BroadcastRuntimeStateChanges(state, previousCoreBlockId, previousCoreSubtypeId,
                    previousBoostActive, previousDefenseActive, previousGridIds,
                    previousLimitRevision, previousLimitEnforcementRevision);
        }

        internal void RunRuntimeSpeedRampDownTick()
        {
            if (Session.IsServer || !EffectiveSpeedRampDownActive) return;

            lock (SpeedStateLock)
            {
                if (!EffectiveSpeedRampDownActive) return;
                int elapsedTicks = Session.CurrentTick - _runtimeSpeedRampDownLastTick;
                int elapsedPeriods = elapsedTicks / SpeedEnforcement.SpeedRampDownIntervalTicks;
                if (elapsedPeriods <= 0) return;

                bool rampActive;
                EffectiveSpeedLimitMetersPerSecond = SpeedEnforcement.InterpolateSpeedRampDownCap(
                    EffectiveSpeedLimitMetersPerSecond, EffectiveSpeedRampDownTargetCap,
                    elapsedPeriods, out rampActive);
                EffectiveSpeedRampDownActive = rampActive;
                _runtimeSpeedRampDownLastTick += elapsedPeriods * SpeedEnforcement.SpeedRampDownIntervalTicks;
            }
        }

        private void BroadcastRuntimeStateChanges(GroupRuntimeState state, long previousCoreBlockId,
            string previousCoreSubtypeId, bool previousBoostActive, bool previousDefenseActive,
            long[] previousGridIds, int previousLimitRevision, int previousLimitEnforcementRevision)
        {
            var eventGridId = state.RepresentativeGridId == 0 ? state.GroupId : state.RepresentativeGridId;
            if (previousCoreBlockId != state.MainCoreBlockId)
            {
                if (previousCoreBlockId != 0 && state.MainCoreBlockId == 0)
                {
                    var oldCore = Session.Config.GetShipCoreByTypeId(previousCoreSubtypeId);
                    ModAPI.BroadcastCoreDeactivated(eventGridId, previousCoreSubtypeId,
                        oldCore == null ? previousCoreSubtypeId : oldCore.UniqueName);
                }
                else if (previousCoreBlockId == 0 && state.MainCoreBlockId != 0)
                {
                    var newCore = Session.Config.GetShipCoreByTypeId(state.CoreSubtypeId ?? string.Empty);
                    ModAPI.BroadcastCoreActivated(eventGridId, state.CoreSubtypeId,
                        newCore == null ? state.CoreSubtypeId : newCore.UniqueName);
                }
            }

            if (previousBoostActive != state.BoostActive)
            {
                if (state.BoostActive)
                {
                    var coreGrid = MainCoreComponent?.GridComponent?.Grid;
                    ModAPI.BroadcastBoostActivated(coreGrid?.EntityId ?? eventGridId);
                }
                else ModAPI.BroadcastBoostDeactivated(eventGridId);
            }
            if (previousDefenseActive != state.ActiveDefense)
            {
                if (state.ActiveDefense) ModAPI.BroadcastActiveDefenseActivated(eventGridId);
                else ModAPI.BroadcastActiveDefenseDeactivated(eventGridId);
            }

            var oldGridIds = new HashSet<long>(previousGridIds);
            var newGridIds = new HashSet<long>(state.GridIds ?? Array.Empty<long>());
            foreach (var gridId in newGridIds)
                if (!oldGridIds.Contains(gridId)) ModAPI.BroadcastGridAddedToGroup(gridId);
            foreach (var gridId in oldGridIds)
                if (!newGridIds.Contains(gridId)) ModAPI.BroadcastGridRemovedFromGroup(gridId, eventGridId);

            for (var revision = previousLimitRevision + 1; revision <= state.LimitRevision; revision++)
                ModAPI.BroadcastLimitsRecalculated(eventGridId);
            if (state.LimitEnforcementRevision <= previousLimitEnforcementRevision) return;
            var events = state.LimitEnforcementEvents;
            if (events == null || events.Length == 0)
            {
                ModAPI.BroadcastLimitsEnforced(eventGridId, state.LastBlocksPunished);
            }
            else
            {
                foreach (var runtimeEvent in events)
                {
                    if (runtimeEvent != null && runtimeEvent.Revision > previousLimitEnforcementRevision &&
                        runtimeEvent.Revision <= state.LimitEnforcementRevision)
                        ModAPI.BroadcastLimitsEnforced(eventGridId, runtimeEvent.BlocksPunished);
                }
            }
        }

        internal void ClearRuntimeState()
        {
            if (Session.IsServer || !_runtimeStateReceived) return;
            var previousCoreBlockId = _runtimeMainCoreBlockId;
            var previousCoreSubtypeId = _runtimeCoreSubtypeId;
            var previousBoostActive = BoostEnabled;
            var previousDefenseActive = _activeDefenseEnabled;
            var previousGridIds = _cachedMechanicalGridIds ?? Array.Empty<long>();
            var previousRepresentativeGridId = GetCachedRepresentativeGridId();
            _runtimeStateReceived = false;
            _runtimeCoreSubtypeId = string.Empty;
            _runtimeOwnerId = 0;
            _runtimeCoreCount = 0;
            _runtimePlayerCoreCount = 0;
            _runtimeFactionCoreCount = 0;
            _runtimeFactionPlayerCount = 0;
            _runtimeEffectiveFactionCoreLimit = -1;
            _runtimeManifestCounts.Clear();
            _runtimeSpeedPunishmentReasons = Array.Empty<string>();
            _runtimeModifierPunishmentReasons = Array.Empty<string>();
            _runtimeLimitedBlockPunishmentReasons = Array.Empty<string>();
            _runtimeMainCoreBlockId = 0;
            _runtimeLimitRevision = 0;
            _runtimeLimitEnforcementRevision = 0;
            Deactivated = false;
            PunishModifiers = false;
            PunishSpeed = false;
            PunishLimitedBlocks = false;
            MainCoreComponent = null;
            foreach (var pair in CoreDictionary) pair.Value.ApplyAuthoritativeMainState(false);
            PublishLimitsSnapshot(null);
            _cachedEffectiveMaxCounts.Clear();
            _cachedEffectiveMaxBlocks = -1;
            _cachedEffectiveMaxPCU = -1;
            _cachedEffectiveMaxMass = -1f;
            Interlocked.Exchange(ref _groupBlocksCount, 0);
            Interlocked.Exchange(ref _cachedGroupPCU, 0);
            Interlocked.Exchange(ref _cachedRepresentativeGridId, 0L);
            _cachedDryMass = 0f;
            _cachedMechanicalGridIds = Array.Empty<long>();
            _cachedIsIgnoredGroup = false;
            _cachedIsIgnoredByAiOrFactionTag = false;
            _cachedActiveGridModifiers = new GridModifiers();
            _cachedActiveSpeedModifiers = new SpeedModifiers();
            BaseSpeedLimitMetersPerSecond = 100f;
            EffectiveSpeedLimitMetersPerSecond = 100f;
            SpeedSourceGroupGridId = 0;
            EffectiveBoostEnabled = false;
            EffectiveSpeedRampDownActive = false;
            EffectiveSpeedRampDownTargetCap = -1f;
            _runtimeSpeedRampDownLastTick = 0;
            BoostEnabled = false;
            _boostDurationTimer = 0f;
            _boostCooldownTimer = 0f;
            _activeDefenseEnabled = false;
            _activeDefenseDurationTimer = 0f;
            _activeDefenseCooldownTimer = 0f;
            _powerOverclockActive = false;
            _powerOverclockDurationTimer = 0f;
            _powerOverclockCooldownTimer = 0f;
            _runtimeAbilityStateTick = 0;
            FrictionEnforcementEnabled = true;
            FrictionMaximumDecelerationOverride = -1f;
            MinimumFrictionSpeedAbsoluteOverride = -1f;
            MaximumFrictionSpeedAbsoluteOverride = -1f;
            MinimumFrictionSpeedModifierOverride = -1f;
            MaximumFrictionSpeedModifierOverride = -1f;
            ApplyModifiers(_cachedActiveGridModifiers);
            BroadcastRuntimeStateCleared(previousCoreBlockId, previousCoreSubtypeId,
                previousBoostActive, previousDefenseActive, previousGridIds,
                previousRepresentativeGridId);
        }

        private static void BroadcastRuntimeStateCleared(long previousCoreBlockId,
            string previousCoreSubtypeId, bool previousBoostActive, bool previousDefenseActive,
            long[] previousGridIds, long previousRepresentativeGridId)
        {
            var eventGridId = previousRepresentativeGridId;
            if (eventGridId == 0 && previousGridIds.Length > 0) eventGridId = previousGridIds[0];
            if (previousCoreBlockId != 0)
            {
                var oldCore = Session.Config.GetShipCoreByTypeId(previousCoreSubtypeId);
                ModAPI.BroadcastCoreDeactivated(eventGridId, previousCoreSubtypeId,
                    oldCore == null ? previousCoreSubtypeId : oldCore.UniqueName);
            }
            if (previousBoostActive) ModAPI.BroadcastBoostDeactivated(eventGridId);
            if (previousDefenseActive) ModAPI.BroadcastActiveDefenseDeactivated(eventGridId);
            foreach (var t in previousGridIds)
                ModAPI.BroadcastGridRemovedFromGroup(t, eventGridId);
        }

        private static bool SameModifiers(GridModifiers left, GridModifiers right)
        {
            return left != null && right != null &&
                   left.AssemblerSpeed == right.AssemblerSpeed &&
                   left.DrillHarvestMultiplier == right.DrillHarvestMultiplier &&
                   left.GyroEfficiency == right.GyroEfficiency &&
                   left.GyroForce == right.GyroForce &&
                   left.PowerProducersOutput == right.PowerProducersOutput &&
                   left.RefineEfficiency == right.RefineEfficiency &&
                   left.RefineSpeed == right.RefineSpeed &&
                   left.ThrusterEfficiency == right.ThrusterEfficiency &&
                   left.ThrusterForce == right.ThrusterForce;
        }

        private void ApplyRuntimeCore(long mainCoreBlockId)
        {
            MainCoreComponent = null;
            foreach (var pair in CoreDictionary)
            {
                var isMain = pair.Key != null && pair.Key.EntityId == mainCoreBlockId;
                pair.Value.ApplyAuthoritativeMainState(isMain);
                if (isMain) MainCoreComponent = pair.Value;
            }
        }

        private void PublishRuntimeLimits(RuntimeLimitState[] runtimeLimits)
        {
            var limits = new ConcurrentDictionary<BlockLimit, LimitBucket>();
            var effectiveCounts = new Dictionary<BlockLimit, float>();
            var configured = ShipCore?.BlockLimits;
            if (configured != null && runtimeLimits != null)
            {
                foreach (var limit in configured)
                {
                    if (limit == null) continue;
                    foreach (var runtime in runtimeLimits)
                    {
                        if (runtime == null || !string.Equals(limit.Name, runtime.Name, StringComparison.OrdinalIgnoreCase))
                            continue;
                        var bucket = new LimitBucket(runtime.CurrentCount)
                        {
                            ConnectorWeight = runtime.ConnectorCount
                        };
                        if (runtime.DirectionCounts != null)
                            Array.Copy(runtime.DirectionCounts, bucket.DirectionWeights,
                                Math.Min(runtime.DirectionCounts.Length, bucket.DirectionWeights.Length));
                        limits[limit] = bucket;
                        effectiveCounts[limit] = runtime.MaxCount;
                        break;
                    }
                }
            }
            PublishLimitsSnapshot(limits);
            _cachedEffectiveMaxCounts = effectiveCounts;
        }

        private static GridModifiers FromRuntimeData(GridModifiersData value)
        {
            if (value == null) return new GridModifiers();
            return new GridModifiers
            {
                AssemblerSpeed = value.AssemblerSpeed,
                DrillHarvestMultiplier = value.DrillHarvestMultiplier,
                GyroEfficiency = value.GyroEfficiency,
                GyroForce = value.GyroForce,
                PowerProducersOutput = value.PowerProducersOutput,
                RefineEfficiency = value.RefineEfficiency,
                RefineSpeed = value.RefineSpeed,
                ThrusterEfficiency = value.ThrusterEfficiency,
                ThrusterForce = value.ThrusterForce
            };
        }

        private static FrictionCurve FromRuntimeData(FrictionCurveSegmentData[] value)
        {
            if (value == null || value.Length == 0) return null;
            var segments = new FrictionCurveSegment[value.Length];
            for (var i = 0; i < value.Length; i++)
            {
                var segment = value[i];
                if (segment == null) continue;
                segments[i] = new FrictionCurveSegment
                {
                    StartSpeed = segment.StartSpeed,
                    EndSpeed = segment.EndSpeed,
                    StartDeceleration = segment.StartDeceleration,
                    EndDeceleration = segment.EndDeceleration
                };
            }
            return new FrictionCurve { Segments = segments };
        }

        private static AtmosphericFrictionSettings FromRuntimeData(AtmosphericFrictionData value)
        {
            if (value == null) return null;
            return new AtmosphericFrictionSettings
            {
                Enabled = value.Enabled,
                FrictionCurve = FromRuntimeData(value.FrictionCurve),
                CruiseFrictionMultiplier = value.CruiseFrictionMultiplier,
                CruiseAccelerationThreshold = value.CruiseAccelerationThreshold,
                AirDensityThreshold = value.AirDensityThreshold
            };
        }

        private static SpeedModifiers FromRuntimeData(SpeedModifiersData value)
        {
            if (value == null) return new SpeedModifiers();
            return new SpeedModifiers
            {
                MaxSpeed = value.MaxSpeed,
                MaxAngularVelocity = value.MaxAngularVelocity,
                MaxBoost = value.MaxBoost,
                BoostDuration = value.BoostDuration,
                BoostCoolDown = value.BoostCoolDown,
                MinimumFrictionSpeedAbsolute = value.MinimumFrictionSpeedAbsolute,
                MaximumFrictionSpeedAbsolute = value.MaximumFrictionSpeedAbsolute,
                MaximumFrictionDeceleration = value.MaximumFrictionDeceleration,
                MinimumFrictionSpeedModifier = value.MinimumFrictionSpeedModifier,
                MaximumFrictionSpeedModifier = value.MaximumFrictionSpeedModifier,
                CruiseFrictionMultiplier = value.CruiseFrictionMultiplier,
                CruiseAccelerationThreshold = value.CruiseAccelerationThreshold,
                FrictionCurve = FromRuntimeData(value.FrictionCurve),
                AtmosphericFriction = FromRuntimeData(value.AtmosphericFriction)
            };
        }

        private static GridDefenseModifiers FromRuntimeData(GridDefenseModifiersData value)
        {
            if (value == null) return new GridDefenseModifiers();
            return new GridDefenseModifiers
            {
                Bullet = value.Bullet,
                PostShield = value.PostShield,
                Duration = value.Duration,
                Cooldown = value.Cooldown,
                Rocket = value.Rocket,
                Explosion = value.Explosion,
                Environment = value.Environment,
                Energy = value.Energy,
                Kinetic = value.Kinetic
            };
        }
    }
}
