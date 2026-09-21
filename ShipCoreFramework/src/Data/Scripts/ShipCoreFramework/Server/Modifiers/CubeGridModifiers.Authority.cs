using System.Collections.Generic;
using System.Linq;

namespace ShipCoreFramework
{
    internal enum DefenseModifierTarget
    {
        Passive = 0,
        Active = 1
    }

    internal static partial class CubeGridModifiers
    {
        internal static float ApplyUpgradeModifier(float currentValue, float modifierValue,
            UpgradeModifierOperation modifierType)
        {
            return modifierType == UpgradeModifierOperation.Additive
                ? currentValue + modifierValue
                : currentValue * modifierValue;
        }

        internal static GridDefenseModifiers ScaleDefenseModifiers(GridDefenseModifiers modifiers, float factor)
        {
            return new GridDefenseModifiers
            {
                Bullet = modifiers.Bullet * factor,
                PostShield = modifiers.PostShield * factor,
                Duration = modifiers.Duration * factor,
                Cooldown = modifiers.Cooldown * factor,
                Rocket = modifiers.Rocket * factor,
                Explosion = modifiers.Explosion * factor,
                Environment = modifiers.Environment * factor,
                Energy = modifiers.Energy * factor,
                Kinetic = modifiers.Kinetic * factor
            };
        }

        internal static GridModifiers GetActiveModifiers(GroupComponent groupComponent)
        {
            if (groupComponent == null || groupComponent.Deactivated ||
                groupComponent.IsIgnoredByAiOrFactionTagThreadSafe())
                return new GridModifiers();

            if (groupComponent.PunishModifiers) return Session.Config.SelectedNoCore.Modifiers;
            GridModifiers overrideModifiers = groupComponent.GetGridModifiersOverride();
            if (overrideModifiers != null) return Clone(overrideModifiers);
            ShipCore shipCore = groupComponent.ShipCore;

            GridModifiers modifiers = Clone(shipCore.Modifiers);
            foreach (UpgradeModuleComponent module in groupComponent.GetEffectiveUpgradeModules(true))
            {
                UpgradeModuleConfig config = module.GetConfig();
                if (config?.Modifiers == null) continue;

                foreach (UpgradeStatModifier modifier in config.Modifiers.Where(value => value != null))
                {
                    switch (modifier.Stat)
                    {
                        case "AssemblerSpeed":
                            modifiers.AssemblerSpeed = ApplyUpgradeModifier(modifiers.AssemblerSpeed, modifier.Value, modifier.ModifierType);
                            break;
                        case "DrillHarvestMultiplier":
                            modifiers.DrillHarvestMultiplier = ApplyUpgradeModifier(modifiers.DrillHarvestMultiplier, modifier.Value, modifier.ModifierType);
                            break;
                        case "GyroEfficiency":
                            modifiers.GyroEfficiency = ApplyUpgradeModifier(modifiers.GyroEfficiency, modifier.Value, modifier.ModifierType);
                            break;
                        case "GyroForce":
                            modifiers.GyroForce = ApplyUpgradeModifier(modifiers.GyroForce, modifier.Value, modifier.ModifierType);
                            break;
                        case "PowerProducersOutput":
                            modifiers.PowerProducersOutput = ApplyUpgradeModifier(modifiers.PowerProducersOutput, modifier.Value, modifier.ModifierType);
                            break;
                        case "RefineEfficiency":
                            modifiers.RefineEfficiency = ApplyUpgradeModifier(modifiers.RefineEfficiency, modifier.Value, modifier.ModifierType);
                            break;
                        case "RefineSpeed":
                            modifiers.RefineSpeed = ApplyUpgradeModifier(modifiers.RefineSpeed, modifier.Value, modifier.ModifierType);
                            break;
                        case "ThrusterEfficiency":
                            modifiers.ThrusterEfficiency = ApplyUpgradeModifier(modifiers.ThrusterEfficiency, modifier.Value, modifier.ModifierType);
                            break;
                        case "ThrusterForce":
                            modifiers.ThrusterForce = ApplyUpgradeModifier(modifiers.ThrusterForce, modifier.Value, modifier.ModifierType);
                            break;
                    }
                }
            }

            if (shipCore.PowerOverclockEnabled && groupComponent.IsPowerOverclockActive())
                modifiers.PowerProducersOutput *= shipCore.PowerOverclockMultiplier;

            return modifiers;
        }

        internal static SpeedModifiers GetActiveSpeedModifiers(GroupComponent groupComponent)
        {
            if (groupComponent == null || groupComponent.Deactivated ||
                groupComponent.IsIgnoredByAiOrFactionTagThreadSafe())
                return new SpeedModifiers();

            SpeedModifiers overrideModifiers = groupComponent.GetSpeedModifiersOverride();
            if (overrideModifiers != null) return Clone(overrideModifiers);

            ShipCore shipCore = groupComponent.ShipCore;
            SpeedModifiers modifiers = Clone(shipCore.SpeedModifiers);
            foreach (UpgradeModuleComponent module in groupComponent.GetEffectiveUpgradeModules(true))
            {
                UpgradeModuleConfig config = module.GetConfig();
                if (config?.Modifiers == null) continue;

                foreach (UpgradeStatModifier modifier in config.Modifiers.Where(value => value != null))
                {
                    switch (modifier.Stat)
                    {
                        case "MaxSpeed":
                            modifiers.MaxSpeed = ApplyUpgradeModifier(modifiers.MaxSpeed, modifier.Value, modifier.ModifierType);
                            break;
                        case "MaxAngularVelocity":
                            modifiers.MaxAngularVelocity = ApplyUpgradeModifier(modifiers.MaxAngularVelocity, modifier.Value, modifier.ModifierType);
                            break;
                        case "MaxBoost":
                            modifiers.MaxBoost = ApplyUpgradeModifier(modifiers.MaxBoost, modifier.Value, modifier.ModifierType);
                            break;
                        case "BoostDuration":
                            modifiers.BoostDuration = ApplyUpgradeModifier(modifiers.BoostDuration, modifier.Value, modifier.ModifierType);
                            break;
                        case "BoostCoolDown":
                            modifiers.BoostCoolDown = ApplyUpgradeModifier(modifiers.BoostCoolDown, modifier.Value, modifier.ModifierType);
                            break;
                        case "MinimumFrictionSpeedAbsolute":
                            modifiers.MinimumFrictionSpeedAbsolute = ApplyUpgradeModifier(modifiers.MinimumFrictionSpeedAbsolute, modifier.Value, modifier.ModifierType);
                            break;
                        case "MaximumFrictionSpeedAbsolute":
                            modifiers.MaximumFrictionSpeedAbsolute = ApplyUpgradeModifier(modifiers.MaximumFrictionSpeedAbsolute, modifier.Value, modifier.ModifierType);
                            break;
                        case "MinimumFrictionSpeedModifier":
                            modifiers.MinimumFrictionSpeedModifier = ApplyUpgradeModifier(modifiers.MinimumFrictionSpeedModifier, modifier.Value, modifier.ModifierType);
                            break;
                        case "MaximumFrictionSpeedModifier":
                            modifiers.MaximumFrictionSpeedModifier = ApplyUpgradeModifier(modifiers.MaximumFrictionSpeedModifier, modifier.Value, modifier.ModifierType);
                            break;
                        case "MaximumFrictionDeceleration":
                            modifiers.MaximumFrictionDeceleration = ApplyUpgradeModifier(modifiers.MaximumFrictionDeceleration, modifier.Value, modifier.ModifierType);
                            break;
                        case "CruiseFrictionMultiplier":
                            modifiers.CruiseFrictionMultiplier = ApplyUpgradeModifier(modifiers.CruiseFrictionMultiplier, modifier.Value, modifier.ModifierType);
                            break;
                        case "CruiseAccelerationThreshold":
                            modifiers.CruiseAccelerationThreshold = ApplyUpgradeModifier(modifiers.CruiseAccelerationThreshold, modifier.Value, modifier.ModifierType);
                            break;
                        case "AtmosphericCruiseFrictionMultiplier":
                            EnsureAtmosphericFrictionSettings(modifiers);
                            modifiers.AtmosphericFriction.CruiseFrictionMultiplier = ApplyUpgradeModifier(modifiers.AtmosphericFriction.CruiseFrictionMultiplier, modifier.Value, modifier.ModifierType);
                            break;
                        case "AtmosphericCruiseAccelerationThreshold":
                            EnsureAtmosphericFrictionSettings(modifiers);
                            modifiers.AtmosphericFriction.CruiseAccelerationThreshold = ApplyUpgradeModifier(modifiers.AtmosphericFriction.CruiseAccelerationThreshold, modifier.Value, modifier.ModifierType);
                            break;
                        case "AtmosphericAirDensityThreshold":
                            EnsureAtmosphericFrictionSettings(modifiers);
                            modifiers.AtmosphericFriction.AirDensityThreshold = ApplyUpgradeModifier(modifiers.AtmosphericFriction.AirDensityThreshold, modifier.Value, modifier.ModifierType);
                            break;
                    }
                }
            }

            return modifiers;
        }

        internal static GridDefenseModifiers GetEffectiveDefenseModifiers(GridDefenseModifiers baseModifiers,
            IEnumerable<UpgradeModuleConfig> upgradeModules, DefenseModifierTarget target)
        {
            GridDefenseModifiers modifiers = Clone(baseModifiers);
            foreach (UpgradeModuleConfig module in upgradeModules.Where(value => value?.Modifiers != null))
            {
                foreach (UpgradeStatModifier modifier in module.Modifiers.Where(value => value != null))
                {
                    switch (modifier.Stat)
                    {
                        case "PassiveBulletDamage":
                            if (target != DefenseModifierTarget.Passive) break;
                            modifiers.Bullet = ApplyUpgradeModifier(modifiers.Bullet, modifier.Value, modifier.ModifierType);
                            break;
                        case "ActiveBulletDamage":
                            if (target != DefenseModifierTarget.Active) break;
                            modifiers.Bullet = ApplyUpgradeModifier(modifiers.Bullet, modifier.Value, modifier.ModifierType);
                            break;
                        case "PassiveRocketDamage":
                            if (target != DefenseModifierTarget.Passive) break;
                            modifiers.Rocket = ApplyUpgradeModifier(modifiers.Rocket, modifier.Value, modifier.ModifierType);
                            break;
                        case "ActiveRocketDamage":
                            if (target != DefenseModifierTarget.Active) break;
                            modifiers.Rocket = ApplyUpgradeModifier(modifiers.Rocket, modifier.Value, modifier.ModifierType);
                            break;
                        case "PassiveExplosionDamage":
                            if (target != DefenseModifierTarget.Passive) break;
                            modifiers.Explosion = ApplyUpgradeModifier(modifiers.Explosion, modifier.Value, modifier.ModifierType);
                            break;
                        case "ActiveExplosionDamage":
                            if (target != DefenseModifierTarget.Active) break;
                            modifiers.Explosion = ApplyUpgradeModifier(modifiers.Explosion, modifier.Value, modifier.ModifierType);
                            break;
                        case "PassiveEnvironmentDamage":
                            if (target != DefenseModifierTarget.Passive) break;
                            modifiers.Environment = ApplyUpgradeModifier(modifiers.Environment, modifier.Value, modifier.ModifierType);
                            break;
                        case "ActiveEnvironmentDamage":
                            if (target != DefenseModifierTarget.Active) break;
                            modifiers.Environment = ApplyUpgradeModifier(modifiers.Environment, modifier.Value, modifier.ModifierType);
                            break;
                        case "PassivePostShieldDamage":
                            if (target != DefenseModifierTarget.Passive) break;
                            modifiers.PostShield = ApplyUpgradeModifier(modifiers.PostShield, modifier.Value, modifier.ModifierType);
                            break;
                        case "ActivePostShieldDamage":
                            if (target != DefenseModifierTarget.Active) break;
                            modifiers.PostShield = ApplyUpgradeModifier(modifiers.PostShield, modifier.Value, modifier.ModifierType);
                            break;
                        case "PassiveEnergyDamage":
                            if (target != DefenseModifierTarget.Passive) break;
                            modifiers.Energy = ApplyUpgradeModifier(modifiers.Energy, modifier.Value, modifier.ModifierType);
                            break;
                        case "ActiveEnergyDamage":
                            if (target != DefenseModifierTarget.Active) break;
                            modifiers.Energy = ApplyUpgradeModifier(modifiers.Energy, modifier.Value, modifier.ModifierType);
                            break;
                        case "PassiveKineticDamage":
                            if (target != DefenseModifierTarget.Passive) break;
                            modifiers.Kinetic = ApplyUpgradeModifier(modifiers.Kinetic, modifier.Value, modifier.ModifierType);
                            break;
                        case "ActiveKineticDamage":
                            if (target != DefenseModifierTarget.Active) break;
                            modifiers.Kinetic = ApplyUpgradeModifier(modifiers.Kinetic, modifier.Value, modifier.ModifierType);
                            break;
                        case "ActiveDefenseDuration":
                            if (target != DefenseModifierTarget.Active) break;
                            modifiers.Duration = ApplyUpgradeModifier(modifiers.Duration, modifier.Value, modifier.ModifierType);
                            break;
                        case "ActiveDefenseCooldown":
                            if (target != DefenseModifierTarget.Active) break;
                            modifiers.Cooldown = ApplyUpgradeModifier(modifiers.Cooldown, modifier.Value, modifier.ModifierType);
                            break;
                    }
                }
            }

            return modifiers;
        }

        private static GridModifiers Clone(GridModifiers modifiers)
        {
            if (modifiers == null) return new GridModifiers();

            return new GridModifiers
            {
                AssemblerSpeed = modifiers.AssemblerSpeed,
                DrillHarvestMultiplier = modifiers.DrillHarvestMultiplier,
                GyroEfficiency = modifiers.GyroEfficiency,
                GyroForce = modifiers.GyroForce,
                PowerProducersOutput = modifiers.PowerProducersOutput,
                RefineEfficiency = modifiers.RefineEfficiency,
                RefineSpeed = modifiers.RefineSpeed,
                ThrusterEfficiency = modifiers.ThrusterEfficiency,
                ThrusterForce = modifiers.ThrusterForce
            };
        }

        private static SpeedModifiers Clone(SpeedModifiers modifiers)
        {
            if (modifiers == null) return new SpeedModifiers();

            return new SpeedModifiers
            {
                MaxSpeed = modifiers.MaxSpeed,
                MaxAngularVelocity = modifiers.MaxAngularVelocity,
                MaxBoost = modifiers.MaxBoost,
                BoostDuration = modifiers.BoostDuration,
                BoostCoolDown = modifiers.BoostCoolDown,
                MinimumFrictionSpeedAbsolute = modifiers.MinimumFrictionSpeedAbsolute,
                MaximumFrictionSpeedAbsolute = modifiers.MaximumFrictionSpeedAbsolute,
                MinimumFrictionSpeedModifier = modifiers.MinimumFrictionSpeedModifier,
                MaximumFrictionSpeedModifier = modifiers.MaximumFrictionSpeedModifier,
                MaximumFrictionDeceleration = modifiers.MaximumFrictionDeceleration,
                CruiseFrictionMultiplier = modifiers.CruiseFrictionMultiplier,
                CruiseAccelerationThreshold = modifiers.CruiseAccelerationThreshold,
                FrictionCurve = Clone(modifiers.FrictionCurve),
                AtmosphericFriction = Clone(modifiers.AtmosphericFriction)
            };
        }

        private static void EnsureAtmosphericFrictionSettings(SpeedModifiers modifiers)
        {
            if (modifiers.AtmosphericFriction == null)
                modifiers.AtmosphericFriction = new AtmosphericFrictionSettings();
        }

        private static FrictionCurve Clone(FrictionCurve curve)
        {
            if (curve == null) return null;

            FrictionCurveSegment[] sourceSegments = curve.Segments ?? new FrictionCurveSegment[0];
            FrictionCurveSegment[] segments = new FrictionCurveSegment[sourceSegments.Length];
            for (int i = 0; i < sourceSegments.Length; i++)
            {
                FrictionCurveSegment source = sourceSegments[i];
                if (source == null) continue;

                segments[i] = new FrictionCurveSegment
                {
                    StartSpeed = source.StartSpeed,
                    EndSpeed = source.EndSpeed,
                    StartDeceleration = source.StartDeceleration,
                    EndDeceleration = source.EndDeceleration
                };
            }

            return new FrictionCurve
            {
                Segments = segments
            };
        }

        private static AtmosphericFrictionSettings Clone(AtmosphericFrictionSettings settings)
        {
            if (settings == null) return null;

            return new AtmosphericFrictionSettings
            {
                Enabled = settings.Enabled,
                FrictionCurve = Clone(settings.FrictionCurve),
                CruiseFrictionMultiplier = settings.CruiseFrictionMultiplier,
                CruiseAccelerationThreshold = settings.CruiseAccelerationThreshold,
                AirDensityThreshold = settings.AirDensityThreshold
            };
        }

        private static GridDefenseModifiers Clone(GridDefenseModifiers modifiers)
        {
            if (modifiers == null) return new GridDefenseModifiers();

            return new GridDefenseModifiers
            {
                Bullet = modifiers.Bullet,
                PostShield = modifiers.PostShield,
                Duration = modifiers.Duration,
                Cooldown = modifiers.Cooldown,
                Rocket = modifiers.Rocket,
                Explosion = modifiers.Explosion,
                Environment = modifiers.Environment,
                Energy = modifiers.Energy,
                Kinetic = modifiers.Kinetic
            };
        }
    }
}
