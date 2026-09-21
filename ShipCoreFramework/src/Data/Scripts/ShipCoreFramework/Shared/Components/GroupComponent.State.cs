using System.Threading;
using VRage.Game.ModAPI;

namespace ShipCoreFramework
{
    internal partial class GroupComponent
    {
        internal int GroupBlocksCount => Interlocked.CompareExchange(ref _groupBlocksCount, 0, 0);
        private float BoostDuration => SpeedModifiers.BoostDuration;
        private float BoostCoolDown => SpeedModifiers.BoostCoolDown;

        private void AddGroupBlocksCount(int delta)
        {
            int current;
            int updated;
            do
            {
                current = Interlocked.CompareExchange(ref _groupBlocksCount, 0, 0);
                updated = current + delta;
                if (updated < 0) updated = 0;
            }
            while (Interlocked.CompareExchange(ref _groupBlocksCount, updated, current) != current);
        }

        internal bool PunishModifiers;
        internal bool PunishSpeed;
        internal bool PunishLimitedBlocks;
        internal bool BoostEnabled;
        internal bool Deactivated;

        internal bool FrictionEnforcementEnabled = true;
        internal float BaseSpeedLimitMetersPerSecond = 100f;
        internal float EffectiveSpeedLimitMetersPerSecond = 100f;
        internal bool EffectiveBoostEnabled;
        internal long SpeedSourceGroupGridId;
        internal IMyGridGroupData SpeedClusterPhysicalGroup;
        internal bool IsSpeedClusterRepresentative;

        internal bool PostBoostRampActive;
        internal float PostBoostRampCap = -1f;
        internal bool SpeedRampDownActive;
        internal float SpeedRampDownCap = -1f;
        internal float SpeedRampDownTargetCap = -1f;
        internal int SpeedRampDownLastTick = -1;
        internal bool EffectiveSpeedRampDownActive;
        internal float EffectiveSpeedRampDownTargetCap = -1f;


        private readonly object _abilityStateLock = new object();
        internal readonly object SpeedStateLock = new object();

        internal float FrictionMaximumDecelerationOverride = -1f;
        internal float MinimumFrictionSpeedAbsoluteOverride = -1f;
        internal float MaximumFrictionSpeedAbsoluteOverride = -1f;
        internal float MinimumFrictionSpeedModifierOverride = -1f;
        internal float MaximumFrictionSpeedModifierOverride = -1f;

        private long _lastOwnerId;

        internal int CoreCount => !Session.IsServer && _runtimeStateReceived
            ? _runtimeCoreCount
            : CoreDictionary.Count;
        internal bool HasRuntimeState => _runtimeStateReceived;
        private float _boostCooldownTimer;
        private float _boostDurationTimer;

        private bool _activeDefenseEnabled;
        private float _activeDefenseCooldownTimer;
        private float _activeDefenseDurationTimer;
        private bool _powerOverclockActive;
        private float _powerOverclockCooldownTimer;
        private float _powerOverclockDurationTimer;
        private float _powerOverclockDamageTimer;
        private int _runtimeAbilityStateTick;
        private int _runtimeSpeedRampDownLastTick;
        private int _groupBlocksCount;

        private bool _closing;

        private int _gridInitializationDepth;

        internal float ActiveDefenseDuration => GetActiveDefenseModifiers().Duration;
        internal float ActiveDefenseCoolDown => GetActiveDefenseModifiers().Cooldown;
        internal bool IsInitializingGrids => _gridInitializationDepth > 0;
    }
}
