using System.Collections.Generic;
using Sandbox.ModAPI;

namespace ShipCoreFramework
{
    internal partial class GroupComponent
    {
        internal List<string> GetSpeedPunishmentGateDescriptions()
        {
            if (!Session.IsServer)
                return new List<string>(_runtimeSpeedPunishmentReasons);
            var speedReasons = new List<string>();
            CollectTriggeredPunishmentGates(speedReasons, null);
            return speedReasons;
        }

        internal List<string> GetModifierPunishmentGateDescriptions()
        {
            if (!Session.IsServer)
                return new List<string>(_runtimeModifierPunishmentReasons);
            var modifierReasons = new List<string>();
            CollectTriggeredPunishmentGates(null, modifierReasons);
            return modifierReasons;
        }


        internal void ApplyModifiers(GridModifiers modifiers)
        {
            if (Session.IsServer && IsCoreRecoveryGraceActive())
            {
                Utils.Log("ApplyModifiers: suppressed modifier application during core recovery grace for group " +
                          GetGroupKey() + ".", 2);
                return;
            }

            if (!Session.IsGameThread)
            {
                MyAPIGateway.Utilities.InvokeOnGameThread(delegate
                {
                    if (_closing || Session.IsShuttingDown) return;
                    ApplyModifiers(modifiers);
                });
                return;
            }

            foreach (var kvp in GridDictionary)
                kvp.Value.ApplyModifiers(modifiers);
        }

        internal bool IsPowerOverclockActive()
        {
            lock (_abilityStateLock)
            {
                return _powerOverclockActive;
            }
        }

        internal void GetAbilityTimers(out bool boostActive, out float boostDuration,
            out float boostCooldown, out bool defenseActive, out float defenseDuration,
            out float defenseCooldown, out bool powerActive, out float powerDuration,
            out float powerCooldown)
        {
            float elapsed = Session.IsServer || !_runtimeStateReceived
                ? 0f
                : System.Math.Max(0, Session.CurrentTick - _runtimeAbilityStateTick);

            lock (SpeedStateLock)
            {
                boostActive = BoostEnabled;
                boostDuration = System.Math.Max(0f, _boostDurationTimer - (boostActive ? elapsed : 0f));
                boostCooldown = System.Math.Max(0f, _boostCooldownTimer - (boostActive ? 0f : elapsed));
            }

            lock (_abilityStateLock)
            {
                defenseActive = _activeDefenseEnabled;
                defenseDuration = System.Math.Max(0f,
                    _activeDefenseDurationTimer - (defenseActive ? elapsed : 0f));
                defenseCooldown = System.Math.Max(0f,
                    _activeDefenseCooldownTimer - (defenseActive ? 0f : elapsed));
                powerActive = _powerOverclockActive;
                powerDuration = System.Math.Max(0f,
                    _powerOverclockDurationTimer - (powerActive ? elapsed : 0f));
                powerCooldown = System.Math.Max(0f,
                    _powerOverclockCooldownTimer - (powerActive ? 0f : elapsed));
            }
        }

        internal bool HasRunningAbilityTimer()
        {
            bool boostActive;
            float boostDuration;
            float boostCooldown;
            bool defenseActive;
            float defenseDuration;
            float defenseCooldown;
            bool powerActive;
            float powerDuration;
            float powerCooldown;
            GetAbilityTimers(out boostActive, out boostDuration, out boostCooldown,
                out defenseActive, out defenseDuration, out defenseCooldown,
                out powerActive, out powerDuration, out powerCooldown);
            return boostActive && boostDuration > 0f || boostCooldown > 0f ||
                   defenseActive && defenseDuration > 0f || defenseCooldown > 0f ||
                   powerActive && powerDuration > 0f || powerCooldown > 0f;
        }

        internal GridDefenseModifiers GetActiveDefenseModifiers()
        {
            if (Session.IsServer && Session.IsGameThread) RefreshModifierStateCacheIfNeeded();
            return GetCachedActiveDefenseModifiers();
        }


        internal GridDefenseModifiers GetPassiveDefenseModifiers()
        {
            if (Session.IsServer && Session.IsGameThread) RefreshModifierStateCacheIfNeeded();
            return GetCachedPassiveDefenseModifiers();
        }

    }
}
