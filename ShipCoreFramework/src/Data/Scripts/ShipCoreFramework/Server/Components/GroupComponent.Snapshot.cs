using System;
using System.Collections.Generic;
using System.Threading;

namespace ShipCoreFramework
{
    internal partial class GroupComponent
    {
        internal GroupRuntimeState BuildRuntimeState(int revision)
        {
            if (!Session.IsServer || _closing) return null;

            var gridIds = new List<long>();
            foreach (var grid in GridDictionary.Keys)
                if (grid != null && !grid.MarkedForClose && !grid.Closed)
                    gridIds.Add(grid.EntityId);
            gridIds.Sort();
            if (gridIds.Count == 0) return null;

            var runtimeLimits = new List<RuntimeLimitState>();
            int limitRevision;
            lock (_limitSnapshotLock)
            {
                var configuredLimits = ShipCore?.BlockLimits;
                if (configuredLimits != null)
                {
                    for (var i = 0; i < configuredLimits.Length; i++)
                    {
                        var limit = configuredLimits[i];
                        if (limit == null) continue;
                        var total = 0d;
                        var connectorTotal = 0d;
                        var directionCounts = limit.HasDirectionalBudget
                            ? new double[6]
                            : Array.Empty<double>();
                        LimitBucket bucket;
                        if (Limits.TryGetValue(limit, out bucket) && bucket != null)
                            lock (bucket.BucketLock)
                            {
                                total = bucket.TotalWeight;
                                connectorTotal = bucket.ConnectorWeight;
                                if (directionCounts.Length > 0)
                                    Array.Copy(bucket.DirectionWeights, directionCounts,
                                        Math.Min(bucket.DirectionWeights.Length, directionCounts.Length));
                            }
                        runtimeLimits.Add(new RuntimeLimitState
                        {
                            Name = limit.Name ?? string.Empty,
                            CurrentCount = total,
                            MaxCount = GetEffectiveMaxCount(limit),
                            ConnectorCount = connectorTotal,
                            DirectionCounts = directionCounts,
                            EvaluationDisabled = !ShouldEvaluateBlockLimit(limit)
                        });
                    }
                }
                limitRevision = Interlocked.CompareExchange(ref _publishedLimitRevision, 0, 0);
            }
            runtimeLimits.Sort((left, right) => string.Compare(left.Name, right.Name, StringComparison.Ordinal));

            int limitEnforcementRevision;
            int lastBlocksPunished;
            var limitEnforcementEvents = GetRuntimeLimitEnforcementEvents(
                out limitEnforcementRevision, out lastBlocksPunished);

            var directionReference = GetDirectionLockReferenceBlock();
            var modifiers = Modifiers;
            var speedModifiers = SpeedModifiers;
            var ownerId = OwnerId;
            var faction = OwningFaction;
            // Read the field once: failover can null or swap it while this snapshot is being
            // built, and every consumer below must see the same core.
            var mainCore = MainCoreComponent;
            var subtypeId = mainCore == null ? string.Empty : mainCore.SubtypeId;
            var countSubtypeId = ShipCore == null ? subtypeId : ShipCore.SubtypeId;
            var factionPlayerCount = PerFactionManager.GetFactionPlayerCount(faction, ownerId);
            var effectiveFactionCoreLimit = PerFactionManager.GetEffectiveFactionCoreLimit(ShipCore,
                factionPlayerCount);
            var manifestCounts = new List<RuntimeManifestCount>();
            foreach (var manifest in PerManifestGroupManager.GetManifestGroups(ShipCore))
            {
                if (manifest == null) continue;
                manifestCounts.Add(new RuntimeManifestCount
                {
                    Name = manifest.Name ?? string.Empty,
                    Count = PerManifestGroupManager.GetCurrentCount(manifest.Name)
                });
            }
            float baseSpeed;
            float effectiveSpeed;
            long speedSourceGridId;
            bool frictionEnabled;
            bool boostActive;
            bool effectiveBoostActive;
            bool speedRampDownActive;
            float speedRampDownTarget;
            float boostDurationTimer;
            float boostCooldownTimer;
            float frictionMaximumDecelerationOverride;
            float minimumFrictionSpeedAbsoluteOverride;
            float maximumFrictionSpeedAbsoluteOverride;
            float minimumFrictionSpeedModifierOverride;
            float maximumFrictionSpeedModifierOverride;
            lock (SpeedStateLock)
            {
                baseSpeed = BaseSpeedLimitMetersPerSecond;
                effectiveSpeed = EffectiveSpeedLimitMetersPerSecond;
                speedSourceGridId = SpeedSourceGroupGridId;
                frictionEnabled = FrictionEnforcementEnabled;
                boostActive = BoostEnabled;
                effectiveBoostActive = EffectiveBoostEnabled;
                speedRampDownActive = EffectiveSpeedRampDownActive;
                speedRampDownTarget = EffectiveSpeedRampDownTargetCap;
                boostDurationTimer = _boostDurationTimer;
                boostCooldownTimer = _boostCooldownTimer;
                frictionMaximumDecelerationOverride = FrictionMaximumDecelerationOverride;
                minimumFrictionSpeedAbsoluteOverride = MinimumFrictionSpeedAbsoluteOverride;
                maximumFrictionSpeedAbsoluteOverride = MaximumFrictionSpeedAbsoluteOverride;
                minimumFrictionSpeedModifierOverride = MinimumFrictionSpeedModifierOverride;
                maximumFrictionSpeedModifierOverride = MaximumFrictionSpeedModifierOverride;
            }
            bool activeDefense;
            float activeDefenseDurationTimer;
            float activeDefenseCooldownTimer;
            bool powerOverclockActive;
            float powerOverclockDurationTimer;
            float powerOverclockCooldownTimer;
            lock (_abilityStateLock)
            {
                activeDefense = _activeDefenseEnabled;
                activeDefenseDurationTimer = _activeDefenseDurationTimer;
                activeDefenseCooldownTimer = _activeDefenseCooldownTimer;
                powerOverclockActive = _powerOverclockActive;
                powerOverclockDurationTimer = _powerOverclockDurationTimer;
                powerOverclockCooldownTimer = _powerOverclockCooldownTimer;
            }
            return new GroupRuntimeState
            {
                GroupId = gridIds[0],
                Revision = revision,
                GridIds = gridIds.ToArray(),
                CoreSubtypeId = subtypeId,
                MainCoreBlockId = mainCore?.CoreBlock?.EntityId ?? 0L,
                CoreCount = CoreDictionary.Count,
                DirectionReferenceBlockId = directionReference?.EntityId ?? 0L,
                OwnerId = ownerId,
                Deactivated = Deactivated,
                Ignored = GetCachedIsIgnoredGroup(),
                PunishModifiers = PunishModifiers,
                PunishSpeed = PunishSpeed,
                PunishLimitedBlocks = PunishLimitedBlocks,
                BlockCount = GroupBlocksCount,
                Pcu = GroupPCU,
                Mass = GroupMass,
                DryMass = GroupDryMass,
                MaxBlocks = GetEffectiveMaxBlocks(),
                MaxPcu = GetEffectiveMaxPCU(),
                MaxMass = GetEffectiveMaxMass(),
                Limits = runtimeLimits.ToArray(),
                Modifiers = ModAPI.ConvertToGridModifiersData(modifiers),
                SpeedModifiers = ModAPI.ConvertToSpeedModifiersData(speedModifiers),
                PassiveDefenseModifiers = ModAPI.ConvertToDefenseModifiersData(GetPassiveDefenseModifiers()),
                ActiveDefenseModifiers = ModAPI.ConvertToDefenseModifiersData(GetActiveDefenseModifiers()),
                BaseSpeed = baseSpeed,
                EffectiveSpeed = effectiveSpeed,
                SpeedSourceGridId = speedSourceGridId,
                FrictionEnabled = frictionEnabled,
                FrictionMaximumDecelerationOverride = frictionMaximumDecelerationOverride,
                MinimumFrictionSpeedAbsoluteOverride = minimumFrictionSpeedAbsoluteOverride,
                MaximumFrictionSpeedAbsoluteOverride = maximumFrictionSpeedAbsoluteOverride,
                MinimumFrictionSpeedModifierOverride = minimumFrictionSpeedModifierOverride,
                MaximumFrictionSpeedModifierOverride = maximumFrictionSpeedModifierOverride,
                BoostActive = boostActive,
                BoostDurationTimer = boostDurationTimer,
                BoostCooldownTimer = boostCooldownTimer,
                ActiveDefense = activeDefense,
                ActiveDefenseDurationTimer = activeDefenseDurationTimer,
                ActiveDefenseCooldownTimer = activeDefenseCooldownTimer,
                PowerOverclockActive = powerOverclockActive,
                PowerOverclockDurationTimer = powerOverclockDurationTimer,
                PowerOverclockCooldownTimer = powerOverclockCooldownTimer,
                RepresentativeGridId = GetCachedRepresentativeGridId(),
                EffectiveBoostActive = effectiveBoostActive,
                PlayerCoreCount = PerPlayerManager.GetCurrentCount(ownerId, countSubtypeId),
                FactionCoreCount = faction == null ? 0 : PerFactionManager.GetCurrentCount(faction.FactionId, countSubtypeId),
                ManifestCounts = manifestCounts.ToArray(),
                SpeedPunishmentReasons = GetSpeedPunishmentGateDescriptions().ToArray(),
                ModifierPunishmentReasons = GetModifierPunishmentGateDescriptions().ToArray(),
                LimitedBlockPunishmentReasons = GetLimitedBlockPunishmentGateDescriptions().ToArray(),
                LimitRevision = limitRevision,
                LimitEnforcementRevision = limitEnforcementRevision,
                LastBlocksPunished = lastBlocksPunished,
                LimitEnforcementEvents = limitEnforcementEvents,
                FactionPlayerCount = factionPlayerCount,
                EffectiveFactionCoreLimit = effectiveFactionCoreLimit,
                SpeedRampDownActive = speedRampDownActive,
                SpeedRampDownTarget = speedRampDownTarget
            };
        }
    }
}
