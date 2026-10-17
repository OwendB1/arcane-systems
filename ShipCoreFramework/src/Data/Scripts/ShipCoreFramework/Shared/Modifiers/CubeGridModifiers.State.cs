namespace ShipCoreFramework
{
    internal static partial class CubeGridModifiers
    {
        internal static GridModifiers Clone(GridModifiers modifiers)
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

        internal static GridDefenseModifiers Clone(GridDefenseModifiers modifiers)
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

        internal static bool SameModifiers(GridModifiers left, GridModifiers right)
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

        internal static bool SameModifiers(GridDefenseModifiers left, GridDefenseModifiers right)
        {
            return left != null && right != null &&
                   left.Bullet == right.Bullet && left.PostShield == right.PostShield &&
                   left.Duration == right.Duration && left.Cooldown == right.Cooldown &&
                   left.Rocket == right.Rocket && left.Explosion == right.Explosion &&
                   left.Environment == right.Environment && left.Energy == right.Energy &&
                   left.Kinetic == right.Kinetic;
        }
    }
}
