using System;
using System.Collections.Generic;
using Sandbox.Common.ObjectBuilders;
using Sandbox.Game.Entities;
using Sandbox.ModAPI;
using VRage;
using VRage.Game;
using VRage.Game.Entity;
using VRage.Game.ModAPI;
using VRage.ModAPI;
using VRageMath;

namespace ArcanePower
{
    public sealed partial class Reactor
    {
        private readonly Random ejectRandom = new Random();
        private ThermalForecast heatForecast;
        private int overheatDamageTick;

        private void UpdateThermal()
        {
            // Failed tiles leave a hot reaction without adequate containment,
            // even after the electrical source is switched off. Resupply or eject
            // before 125%; after that the reaction is self-sustaining.
            bool runaway = !Motion.PayloadReleased && Motion.Core != CorePhase.Off
                && (Motion.Critical || (Motion.TileStarved && Motion.TileWear >= 1));
            float target = runaway ? (Motion.Critical ? 4 : 2.5f + .5f * Motion.StarvedLoad)
                : reactor.Enabled ? Motion.TargetLoad : 0;
            // Waste returned by an undersized Brayton cooling bank remains a
            // hazard even when full stores stop new fuel or the player shuts off.
            // Use the existing 125% critical-core/ejection/fuse lifecycle.
            if (!Motion.PayloadReleased && Motion.Core != CorePhase.Off && ThermalVariant && Motion.Thermal != null)
                target = Math.Max(target, (float)ThermalMath.WasteHeatLevel(Motion.Thermal, ThermalHeatMW));
            Motion.Heat = (float)ThermalMath.ApproachCoreHeat(Motion.Heat, target, runaway);
            if (!ThermalVariant) UpdateThermalForecast();
        }

        internal void UpdateThermalForecast()
        {
            if (!MyAPIGateway.Multiplayer.IsServer) return;
            if (Motion.PayloadReleased || Motion.Core == CorePhase.Off)
            {
                heatForecast = null;
                Motion.ForecastPeakHeat = 0; Motion.ForecastWarning = false;
                Motion.ForecastOverheatSeconds = Motion.ForecastMeltdownSeconds = -1;
                Motion.ForecastCircuit = 0;
                Motion.ForecastCooldownSeconds = -1;
                return;
            }
            // Old saves have no shutdown baseline; begin at their restored heat.
            if ((Motion.Core == CorePhase.Cooling || Motion.Core == CorePhase.Stopping)
                && Motion.CooldownStartHeat <= CooldownHeat && Motion.Heat > CooldownHeat)
                Motion.CooldownStartHeat = Motion.Heat;
            if (heatForecast == null) heatForecast = new ThermalForecast(Motion.ForecastWarning);
            bool runaway = Motion.Critical || (Motion.TileStarved && Motion.TileWear >= 1);
            double target = runaway ? (Motion.Critical ? 4 : 2.5 + .5 * Motion.StarvedLoad) : Motion.TargetLoad;
            heatForecast.Update(Motion.Heat, target, runaway, ThermalVariant ? Motion.Thermal : null,
                ThermalHeatMW, ThermalVariant ? ThermalCanRun : reactor.Enabled);
            Motion.ForecastPeakHeat = (float)heatForecast.PeakHeat;
            Motion.ForecastOverheatSeconds = (float)heatForecast.OverheatSeconds;
            Motion.ForecastMeltdownSeconds = (float)heatForecast.MeltdownSeconds;
            Motion.ForecastCircuit = heatForecast.Circuit;
            Motion.ForecastWarning = heatForecast.Warning;
            Motion.ForecastCooldownSeconds = (float)heatForecast.CooldownSeconds;
        }

        internal bool TrackCore(CoreHazard core)
        {
            if (!IsLive || Motion.PayloadReleased) return false;
            core.Heat = Motion.Heat;
            core.Position = CoreWorldPosition();
            if (reactor.CubeGrid.Physics != null) core.Velocity = reactor.CubeGrid.Physics.GetVelocityAtPoint(core.Position);
            Motion.Critical = true;
            Motion.CriticalSeconds = CoreHazards.Seconds(core);
            return true;
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
                core = CoreHazards.Arm(Id, Motion.FuelTier, Motion.Heat, position, velocity);
                if (core != null && Motion.Critical)
                    core.Fuse = Math.Min(core.Fuse, Motion.CriticalSeconds);
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
            DiscardTiles();
            Motion.PayloadReleased = true;
            Motion.Critical = false;
            Motion.CriticalSeconds = 0;
            Motion.Heat = 0;
            RefreshFuelCapacity();
            PublishMotion();
        }

        private void TryReleasePayload()
        {
            if (Motion.Vent != VentPhase.Ejecting || !Motion.VentHadPayload || Motion.PayloadReleased || !Motion.VentReady) return;
            if (!HasIntactControllers()) return;
            // Keep the authored launch through the housing/duct. Hand off only
            // once the largest hoop is fully beyond the open outlet plane.
            IMyEntity outlet;
            if (Motion.VentOutletId == 0 || !MyAPIGateway.Entities.TryGetEntityById(Motion.VentOutletId, out outlet)
                || outlet.Closed) return;
            double outletHeight = Vector3D.Dot(outlet.WorldMatrix.Translation - Entity.WorldMatrix.Translation,
                Entity.WorldMatrix.Up) + 1.25;
            float age = Motion.CoreTick + Motion.CoreSubtick;
            float ringY = MathHelper.Lerp(Rest("Ring1").Translation.Y, AnimationGeometry.Center.Y, Span(age, 90, 210));
            if (ringY + EjectionOffset().Y < outletHeight + 1.94) return;
            Matrix rotation = ContainmentRotation(age);
            bool plasma = PlasmaScale(age) > 0;
            bool critical = Motion.Critical || Motion.Heat >= CoreHazards.SupercriticalHeat;
            if (plasma || critical)
            {
                UpdateCriticalCore();
                MatrixD world = WorldPose(PayloadPlasmaPose(age));
                if (!CoreHazards.Release(Id, Motion.FuelTier, Motion.Heat, world,
                    LaunchVelocity(world.Translation, .8f), RandomVector(1.3f),
                    critical ? CaptureCoreShell(world, age, rotation) : null)) return;
            }
            // Persist the one-way handoff before scheduling asynchronous debris.
            CompletePayloadRelease();
            if (!critical)
            {
                for (int i = 0; i < Motion.RingCount; i++)
                    SpawnSpent("ArcaneSpentRing" + (i + 1), WorldPose(PayloadRingPose(i, age)), 1.5f);
                foreach (var tile in AnimationGeometry.Tiles)
                {
                    // Do not eject tiles still inside their dispensers.
                    if (age < 320 + 36 * tile.Batch + 34) continue;
                    SpawnSpent("ArcaneSpentTile" + tile.Variant, WorldPose(PayloadTilePose(tile, age, rotation)), 3f);
                }
            }
            PublishMotion();
        }

        private List<CoreShellPart> CaptureCoreShell(MatrixD world, float age, Matrix rotation)
        {
            var shell = new List<CoreShellPart>();
            MatrixD inverse = MatrixD.Invert(world);
            for (int i = 0; i < Motion.RingCount; i++)
            {
                MatrixD pose = WorldPose(PayloadRingPose(i, age)) * inverse;
                shell.Add(new CoreShellPart { Subtype = "ArcaneSpentRing" + (i + 1),
                    Pose = (Matrix)pose });
            }
            foreach (var tile in AnimationGeometry.Tiles)
                if (age >= 320 + 36 * tile.Batch + 34)
                {
                    MatrixD pose = WorldPose(PayloadTilePose(tile, age, rotation)) * inverse;
                    shell.Add(new CoreShellPart { Subtype = "ArcaneSpentTile" + tile.Variant,
                        Pose = (Matrix)pose });
                }
            return shell;
        }

        private void CompletePayloadRelease()
        {
            Motion.PayloadReleased = true;
            Motion.Critical = false;
            Motion.CriticalSeconds = 0;
            Motion.Heat = 0;
            DiscardTiles();
            SaveMotion();
        }

        private void TryReleaseFailedHousing()
        {
            if (!MyAPIGateway.Multiplayer.IsServer || !receivedState || Motion.PayloadReleased
                || Motion.Core == CorePhase.Off || reactor.IsFunctional) return;
            float age = Motion.CoreTick + Motion.CoreSubtick;
            if (PlasmaScale(age) <= 0 && !Motion.Critical && Motion.Heat < CoreHazards.SupercriticalHeat) return;
            UpdateCriticalCore();
            Vector3D position = CoreWorldPosition();
            MatrixD world = MatrixD.CreateWorld(position, Entity.WorldMatrix.Forward, Entity.WorldMatrix.Up);
            var physics = reactor.CubeGrid.Physics;
            // No launch impulse: collision with the vessel traps this ball until
            // the housing is opened or destroyed. Grid motion is still inherited.
            if (!CoreHazards.Release(Id, Motion.FuelTier, Motion.Heat, world,
                physics == null ? Vector3.Zero : physics.GetVelocityAtPoint(position),
                physics == null ? Vector3.Zero : physics.AngularVelocity)) return;
            reactor.Enabled = false;
            Motion.Core = CorePhase.Off;
            Motion.CoreTick = 0;
            Motion.CoreSubtick = 0;
            Motion.PowerRamp = 0;
            CompletePayloadRelease();
            RefreshFuelCapacity();
            PublishMotion();
        }

        private void ApplyOverheatDamage()
        {
            if (!MyAPIGateway.Multiplayer.IsServer || Motion.PayloadReleased || Motion.Core == CorePhase.Off
                || Motion.Heat <= 1 || !reactor.IsFunctional)
            { overheatDamageTick = 0; return; }
            // One damage update per simulation second; the rate rises linearly
            // with heat above 100%. At 125%: vessel 1%/s, controllers 1.5%/s.
            if (++overheatDamageTick < 60) return;
            overheatDamageTick = 0;
            float excess = Motion.Heat - 1;
            var modules = new List<IMySlimBlock>();
            var native = (MyCubeBlock)Entity;
            if (native.CurrentAttachedUpgradeModules != null)
                foreach (var entry in native.CurrentAttachedUpgradeModules.Values)
                    if (entry.Compatible && entry.Block != null && !entry.Block.Closed
                        && entry.Block.CubeGrid == reactor.CubeGrid
                        && entry.Block.GameLogic.GetAs<ContainmentController>() != null
                        && !modules.Contains(entry.Block.SlimBlock))
                        modules.Add(entry.Block.SlimBlock);
            foreach (var module in modules)
                module.DoDamage(module.MaxIntegrity * .06f * excess,
                    VRage.Utils.MyStringHash.GetOrCompute("Overheat"), true, attackerId: Id);
            reactor.SlimBlock.DoDamage(reactor.SlimBlock.MaxIntegrity * .04f * excess,
                VRage.Utils.MyStringHash.GetOrCompute("Overheat"), true, attackerId: Id);
            TryReleaseFailedHousing();
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
            // The outlet supplies a final launch impulse, at least 45 m/s.
            // Longer ducts may already exceed that speed under authored acceleration.
            float speed = VentSpeed * Math.Max(30, Motion.EjectionTravel * (Motion.EjectTick + Motion.EjectSubtick) / 120f);
            Vector3 jitter = RandomVector(scatter);
            jitter.Y = 0; // Scatter is lateral; it cannot weaken the launch impulse.
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
