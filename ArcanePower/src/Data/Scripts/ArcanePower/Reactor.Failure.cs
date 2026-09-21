using System;
using Sandbox.Common.ObjectBuilders;
using Sandbox.Game.Entities;
using Sandbox.ModAPI;
using VRage;
using VRage.Game;
using VRage.Game.Entity;
using VRage.ModAPI;
using VRageMath;

namespace ArcanePower
{
    public sealed partial class Reactor
    {
        private readonly Random ejectRandom = new Random();

        private void UpdateThermal()
        {
            // Failed tiles leave a hot reaction without adequate containment,
            // even after the electrical source is switched off. Resupply or eject
            // before 125%; after that the reaction is self-sustaining.
            bool runaway = !Motion.PayloadReleased && Motion.Core != CorePhase.Off
                && (Motion.Critical || (Motion.TileStarved && Motion.TileWear >= 1));
            float target = runaway ? (Motion.Critical ? 4 : 2.5f + .5f * Motion.StarvedLoad)
                : reactor.Enabled ? Motion.TargetLoad : 0;
            float response = runaway ? 720 : target > Motion.Heat ? 3600 : 1800;
            Motion.Heat = MathHelper.Clamp(Motion.Heat + (target - Motion.Heat) / response, 0, 4);
        }

        internal void TrackCore(CoreHazard core)
        {
            if (Motion.PayloadReleased) return;
            core.Heat = Motion.Heat;
            core.Position = CoreWorldPosition();
            if (reactor.CubeGrid.Physics != null) core.Velocity = reactor.CubeGrid.Physics.GetVelocityAtPoint(core.Position);
            Motion.Critical = true;
            Motion.CriticalSeconds = CoreHazards.Seconds(core);
        }

        private Vector3D CoreWorldPosition()
        {
            float age = Motion.CoreTick + Motion.CoreSubtick;
            return Vector3D.Transform(AnimationGeometry.Center + ContainmentOffset(age) + EjectionOffset(), Entity.WorldMatrix);
        }

        private void UpdateCriticalCore()
        {
            if (Motion.PayloadReleased) return;
            var core = CoreHazards.Inside(Id);
            if (core == null && Motion.Core != CorePhase.Off && (Motion.Critical || Motion.Heat >= CoreHazards.SupercriticalHeat))
            {
                Vector3D position = CoreWorldPosition();
                Vector3 velocity = reactor.CubeGrid.Physics == null ? Vector3.Zero : reactor.CubeGrid.Physics.GetVelocityAtPoint(position);
                core = CoreHazards.Arm(Id, Motion.Profile - 1, Motion.Heat, position, velocity);
                if (core != null && Motion.Critical)
                    core.Fuse = Math.Min(core.Fuse, Motion.CriticalSeconds
                        * (1 + 4 * Math.Max(0, Motion.Heat - CoreHazards.SupercriticalHeat)));
            }
            if (core != null) TrackCore(core);
        }

        internal void CoreDetonated()
        {
            reactor.Enabled = false;
            Motion.Core = CorePhase.Off;
            Motion.CoreTick = 0;
            Motion.CoreSubtick = 0;
            Motion.PowerRamp = 0;
            Motion.InstalledTiles = 0;
            Motion.TileWear = 0;
            Motion.TileStarved = false;
            Motion.StarvedLoad = 0;
            Motion.MaintenanceTick = -1;
            Motion.PayloadReleased = true;
            Motion.Critical = false;
            Motion.CriticalSeconds = 0;
            Motion.Heat = 0;
            RefreshFuelCapacity();
            PublishMotion();
        }

        private void TryReleasePayload()
        {
            if (Motion.Vent != VentPhase.Ejecting || !Motion.VentHadPayload || Motion.PayloadReleased) return;
            // Keep the authored launch through the housing/duct. Hand off only
            // once the largest hoop is fully beyond the open outlet plane.
            double outletHeight = 3.75;
            IMyEntity outlet;
            if (Motion.VentOutletId != 0 && MyAPIGateway.Entities.TryGetEntityById(Motion.VentOutletId, out outlet))
                outletHeight = Vector3D.Dot(outlet.WorldMatrix.Translation - Entity.WorldMatrix.Translation,
                    Entity.WorldMatrix.Up) + 1.25;
            float age = Motion.CoreTick + Motion.CoreSubtick;
            float ringY = MathHelper.Lerp(Rest("Ring1").Translation.Y, AnimationGeometry.Center.Y, Span(age, 90, 210));
            if (ringY + EjectionOffset().Y < outletHeight + 1.94) return;
            Matrix rotation = ContainmentRotation(age);
            bool plasma = age >= 1160 && (Motion.Core != CorePhase.Stopping || Motion.StopTick < 60);
            if (plasma || Motion.Critical)
            {
                UpdateCriticalCore();
                MatrixD world = WorldPose(PayloadPlasmaPose(age, rotation));
                if (!CoreHazards.Release(Id, Motion.Profile - 1, Motion.Heat, world,
                    LaunchVelocity(world.Translation, .8f), RandomVector(1.3f))) return;
            }
            // Persist the one-way handoff before scheduling asynchronous debris.
            Motion.PayloadReleased = true;
            Motion.Critical = false;
            Motion.CriticalSeconds = 0;
            Motion.InstalledTiles = 0;
            Motion.MaintenanceTick = -1;
            SaveMotion();
            for (int i = 0; i < Motion.Profile; i++)
                SpawnSpent("ArcaneSpentRing" + (i + 1), WorldPose(PayloadRingPose(i, age)), 1.5f);
            foreach (var tile in AnimationGeometry.Tiles)
            {
                // Part-built shells eject only already deployed quartets. A tile
                // still inside its dispenser is not teleported above the roof.
                if (age < 320 + 36 * tile.Batch + 34) continue;
                SpawnSpent("ArcaneSpentTile" + tile.Variant, WorldPose(PayloadTilePose(tile, age, rotation)), 3f);
            }
            PublishMotion();
        }

        private MatrixD WorldPose(Matrix local)
        {
            MatrixD world = (MatrixD)local * Entity.WorldMatrix;
            return MatrixD.CreateWorld(world.Translation, Vector3D.Normalize(world.Forward), Vector3D.Normalize(world.Up));
        }

        private Vector3 RandomVector(float magnitude)
        {
            return new Vector3((float)ejectRandom.NextDouble() * 2 - 1,
                (float)ejectRandom.NextDouble() * 2 - 1, (float)ejectRandom.NextDouble() * 2 - 1) * magnitude;
        }

        private Vector3 LaunchVelocity(Vector3D position, float scatter)
        {
            Vector3 inherited = reactor.CubeGrid.Physics == null ? Vector3.Zero : reactor.CubeGrid.Physics.GetVelocityAtPoint(position);
            // The outlet supplies a final launch impulse, at least 30 m/s.
            // Longer ducts may already exceed that speed under authored acceleration.
            float speed = Math.Max(30, Motion.EjectionTravel * Motion.EjectTick / 120f);
            Vector3 jitter = RandomVector(scatter);
            return inherited + (Vector3)Entity.WorldMatrix.Up * speed + Vector3.TransformNormal(jitter, Entity.WorldMatrix);
        }

        private void SpawnSpent(string subtype, MatrixD world, float scatter)
        {
            Vector3 velocity = LaunchVelocity(world.Translation, scatter);
            Vector3 spin = RandomVector(scatter);
            var item = new MyPhysicalInventoryItem((MyFixedPoint)1, new MyObjectBuilder_Component { SubtypeName = subtype });
            MyFloatingObjects.Spawn(item, world, null, entity =>
            {
                var physical = (IMyEntity)entity;
                if (physical.Closed || physical.Physics == null) return;
                physical.Physics.LinearVelocity = velocity;
                physical.Physics.AngularVelocity = spin;
            });
        }
    }
}
