using System;
using VRage;

namespace ShipCoreFramework
{
    public static partial class ModAPI
    {
        /// <summary>
        /// Enables/disables friction-based speed limiting for a logical grid group.
        /// Friction cores are enabled by default; this is a runtime override.
        /// </summary>
        public static bool SetFrictionEnabledForGroup(long gridId, bool enabled)
        {
            if (!Session.IsServer) return false;

            try
            {
                GroupComponent groupComponent;
                if (!TryGetGroupComponent(gridId, out groupComponent)) return false;

                groupComponent.SetFrictionEnforcementEnabled(enabled);
                return true;
            }
            catch (Exception ex)
            {
                Utils.Log($"ModAPI.SetFrictionEnabledForGroup: Exception - {ex}");
                return false;
            }
        }

        /// <summary>
        /// Sets the maximum friction deceleration override (m/s^2) for a logical grid group.
        /// </summary>
        public static bool SetFrictionMaximumDecelerationForGroup(long gridId, float deceleration)
        {
            if (!Session.IsServer) return false;
            if (deceleration < 0f) return false;

            try
            {
                GroupComponent groupComponent;
                if (!TryGetGroupComponent(gridId, out groupComponent)) return false;

                groupComponent.SetFrictionMaximumDecelerationOverride(deceleration);
                return true;
            }
            catch (Exception ex)
            {
                Utils.Log($"ModAPI.SetFrictionMaximumDecelerationForGroup: Exception - {ex}");
                return false;
            }
        }

        /// <summary>
        /// Clears the maximum friction deceleration override for a logical grid group.
        /// </summary>
        public static bool ClearFrictionMaximumDecelerationForGroup(long gridId)
        {
            if (!Session.IsServer) return false;

            try
            {
                GroupComponent groupComponent;
                if (!TryGetGroupComponent(gridId, out groupComponent)) return false;

                groupComponent.SetFrictionMaximumDecelerationOverride(-1f);
                return true;
            }
            catch (Exception ex)
            {
                Utils.Log($"ModAPI.ClearFrictionMaximumDecelerationForGroup: Exception - {ex}");
                return false;
            }
        }

        public static MyTuple<bool, string> SetFrictionMinimumSpeedAbsoluteForGroup(long gridId, float speedMetersPerSecond)
        {
            if (!Session.IsServer)
                return MyTuple.Create(false, "Runtime friction overrides are server-authoritative.");

            if (Session.Config.FrictionSpeedValueMode != FrictionSpeedValueMode.Absolute)
                return MyTuple.Create(false, "World config uses modifier-based friction speeds; use SetFrictionMinimumSpeedModifierForGroup.");

            GroupComponent groupComponent;
            if (!TryGetGroupComponent(gridId, out groupComponent))
                return MyTuple.Create(false, "Could not resolve logical grid group for the provided grid.");

            if (speedMetersPerSecond < 0f)
            {
                groupComponent.SetMinimumFrictionSpeedAbsoluteOverride(-1f);
                return MyTuple.Create(true, string.Empty);
            }

            groupComponent.SetMinimumFrictionSpeedAbsoluteOverride(speedMetersPerSecond);
            return MyTuple.Create(true, string.Empty);
        }

        public static MyTuple<bool, string> SetFrictionMaximumSpeedAbsoluteForGroup(long gridId, float speedMetersPerSecond)
        {
            if (!Session.IsServer)
                return MyTuple.Create(false, "Runtime friction overrides are server-authoritative.");

            if (Session.Config.FrictionSpeedValueMode != FrictionSpeedValueMode.Absolute)
                return MyTuple.Create(false, "World config uses modifier-based friction speeds; use SetFrictionMaximumSpeedModifierForGroup.");

            GroupComponent groupComponent;
            if (!TryGetGroupComponent(gridId, out groupComponent))
                return MyTuple.Create(false, "Could not resolve logical grid group for the provided grid.");

            if (speedMetersPerSecond < 0f)
            {
                groupComponent.SetMaximumFrictionSpeedAbsoluteOverride(-1f);
                return MyTuple.Create(true, string.Empty);
            }

            groupComponent.SetMaximumFrictionSpeedAbsoluteOverride(speedMetersPerSecond);
            return MyTuple.Create(true, string.Empty);
        }

        public static MyTuple<bool, string> SetFrictionMinimumSpeedModifierForGroup(long gridId, float modifier)
        {
            if (!Session.IsServer)
                return MyTuple.Create(false, "Runtime friction overrides are server-authoritative.");

            if (Session.Config.FrictionSpeedValueMode != FrictionSpeedValueMode.Modifier)
                return MyTuple.Create(false, "World config uses absolute friction speeds; use SetFrictionMinimumSpeedAbsoluteForGroup.");

            GroupComponent groupComponent;
            if (!TryGetGroupComponent(gridId, out groupComponent))
                return MyTuple.Create(false, "Could not resolve logical grid group for the provided grid.");

            if (modifier < 0f)
            {
                groupComponent.SetMinimumFrictionSpeedModifierOverride(-1f);
                return MyTuple.Create(true, string.Empty);
            }

            groupComponent.SetMinimumFrictionSpeedModifierOverride(modifier);
            return MyTuple.Create(true, string.Empty);
        }

        public static MyTuple<bool, string> SetFrictionMaximumSpeedModifierForGroup(long gridId, float modifier)
        {
            if (!Session.IsServer)
                return MyTuple.Create(false, "Runtime friction overrides are server-authoritative.");

            if (Session.Config.FrictionSpeedValueMode != FrictionSpeedValueMode.Modifier)
                return MyTuple.Create(false, "World config uses absolute friction speeds; use SetFrictionMaximumSpeedAbsoluteForGroup.");

            GroupComponent groupComponent;
            if (!TryGetGroupComponent(gridId, out groupComponent))
                return MyTuple.Create(false, "Could not resolve logical grid group for the provided grid.");

            if (modifier < 0f)
            {
                groupComponent.SetMaximumFrictionSpeedModifierOverride(-1f);
                return MyTuple.Create(true, string.Empty);
            }

            groupComponent.SetMaximumFrictionSpeedModifierOverride(modifier);
            return MyTuple.Create(true, string.Empty);
        }

        public static bool SetGridModifiersOverrideForGroup(long gridId, GridModifiersData modifiers)
        {
            if (!Session.IsServer) return false;
            if (!IsValidGridModifiers(modifiers)) return false;

            GroupComponent groupComponent;
            if (!TryGetGroupComponent(gridId, out groupComponent)) return false;
            groupComponent.SetGridModifiersOverride(ConvertFromGridModifiersData(modifiers));
            return true;
        }

        public static bool SetSpeedModifiersOverrideForGroup(long gridId, SpeedModifiersData modifiers)
        {
            if (!Session.IsServer) return false;
            if (!IsValidSpeedModifiers(modifiers)) return false;

            GroupComponent groupComponent;
            if (!TryGetGroupComponent(gridId, out groupComponent)) return false;
            groupComponent.SetSpeedModifiersOverride(ConvertFromSpeedModifiersData(modifiers));
            return true;
        }

        public static bool SetPassiveDefenseModifiersOverrideForGroup(long gridId,
            GridDefenseModifiersData modifiers)
        {
            if (!Session.IsServer) return false;
            if (!IsValidDefenseModifiers(modifiers)) return false;

            GroupComponent groupComponent;
            if (!TryGetGroupComponent(gridId, out groupComponent)) return false;
            groupComponent.SetPassiveDefenseModifiersOverride(ConvertFromDefenseModifiersData(modifiers));
            return true;
        }

        public static bool SetActiveDefenseModifiersOverrideForGroup(long gridId,
            GridDefenseModifiersData modifiers)
        {
            if (!Session.IsServer) return false;
            if (!IsValidDefenseModifiers(modifiers)) return false;

            GroupComponent groupComponent;
            if (!TryGetGroupComponent(gridId, out groupComponent)) return false;
            groupComponent.SetActiveDefenseModifiersOverride(ConvertFromDefenseModifiersData(modifiers));
            return true;
        }

        private static bool IsFinite(float value)
        {
            return !float.IsNaN(value) && !float.IsInfinity(value);
        }

        private static bool IsValidGridModifiers(GridModifiersData modifiers)
        {
            if (modifiers == null) return true;
            return IsValidGridValue(modifiers.AssemblerSpeed) &&
                   IsValidGridValue(modifiers.DrillHarvestMultiplier) &&
                   IsValidGridValue(modifiers.GyroEfficiency) &&
                   IsValidGridValue(modifiers.GyroForce) &&
                   IsValidGridValue(modifiers.PowerProducersOutput) &&
                   IsValidGridValue(modifiers.RefineEfficiency) &&
                   IsValidGridValue(modifiers.RefineSpeed) &&
                   IsValidGridValue(modifiers.ThrusterEfficiency) &&
                   IsValidGridValue(modifiers.ThrusterForce);
        }

        private static bool IsValidGridValue(float value)
        {
            return IsFinite(value) && value >= -1f;
        }

        private static bool IsValidSpeedModifiers(SpeedModifiersData modifiers)
        {
            if (modifiers == null) return true;
            float[] values =
            {
                modifiers.MaxSpeed, modifiers.MaxAngularVelocity, modifiers.MaxBoost,
                modifiers.BoostDuration, modifiers.BoostCoolDown,
                modifiers.MinimumFrictionSpeedAbsolute, modifiers.MaximumFrictionSpeedAbsolute,
                modifiers.MaximumFrictionDeceleration, modifiers.MinimumFrictionSpeedModifier,
                modifiers.MaximumFrictionSpeedModifier, modifiers.CruiseFrictionMultiplier,
                modifiers.CruiseAccelerationThreshold
            };
            foreach (float value in values)
                if (!IsFinite(value) || value < 0f) return false;

            if (modifiers.FrictionCurve != null)
                foreach (FrictionCurveSegmentData segment in modifiers.FrictionCurve)
                    if (segment == null || !IsFinite(segment.StartSpeed) || !IsFinite(segment.EndSpeed) ||
                        !IsFinite(segment.StartDeceleration) || !IsFinite(segment.EndDeceleration) ||
                        segment.StartSpeed < 0f || segment.EndSpeed < 0f ||
                        segment.StartDeceleration < 0f || segment.EndDeceleration < 0f)
                        return false;

            AtmosphericFrictionData atmospheric = modifiers.AtmosphericFriction;
            return atmospheric == null || IsValidAtmosphericFriction(atmospheric);
        }

        private static bool IsValidAtmosphericFriction(AtmosphericFrictionData settings)
        {
            float[] values =
            {
                settings.CruiseFrictionMultiplier,
                settings.CruiseAccelerationThreshold,
                settings.AirDensityThreshold
            };
            foreach (float value in values)
                if (!IsFinite(value) || value < 0f) return false;

            if (settings.FrictionCurve == null) return true;
            foreach (FrictionCurveSegmentData segment in settings.FrictionCurve)
                if (segment == null || !IsFinite(segment.StartSpeed) || !IsFinite(segment.EndSpeed) ||
                    !IsFinite(segment.StartDeceleration) || !IsFinite(segment.EndDeceleration) ||
                    segment.StartSpeed < 0f || segment.EndSpeed < 0f ||
                    segment.StartDeceleration < 0f || segment.EndDeceleration < 0f)
                    return false;
            return true;
        }

        private static bool IsValidDefenseModifiers(GridDefenseModifiersData modifiers)
        {
            if (modifiers == null) return true;
            float[] values =
            {
                modifiers.Bullet, modifiers.PostShield, modifiers.Duration, modifiers.Cooldown,
                modifiers.Rocket, modifiers.Explosion, modifiers.Environment,
                modifiers.Energy, modifiers.Kinetic
            };
            foreach (float value in values)
                if (!IsFinite(value) || value < 0f) return false;
            return true;
        }
    }
}
