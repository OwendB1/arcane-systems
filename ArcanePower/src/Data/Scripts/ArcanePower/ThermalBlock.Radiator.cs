using System;
using System.Collections.Generic;
using Sandbox.Game;
using Sandbox.Game.Entities;
using Sandbox.ModAPI;
using VRage.Game.Entity;
using VRage.Game.Components;
using VRageMath;

namespace ArcanePower
{
    public abstract partial class ThermalBlock
    {
        private bool receivedRadiator;
        private double radiatorVisualAngle;
        internal ThermalBlock RadiatorBase;
        internal readonly List<ThermalBlock> RadiatorPanels = new List<ThermalBlock>();
        internal double PanelCoolingMW;
        internal bool RadiatorBreached { get { return Spec.Kind == ThermalKind.Radiator
            && Store.Radiator != null
            && (MyAPIGateway.Multiplayer.IsServer ? RadiatorPanels.Count : Store.Radiator.Panels) < Store.Radiator.RequiredPanels; } }
        private List<VRage.Game.ModAPI.IHitInfo> solarHits;
        internal bool IsRadiator { get { return Spec.Kind == ThermalKind.Radiator || Spec.Kind == ThermalKind.RadiatorPanel
            || Spec.Kind == ThermalKind.HullRadiator; } }

        internal void ReceiveRadiator(ThermalRadiatorState state)
        {
            if (!IsRadiator || state == null || !state.Valid(Entity.EntityId)
                || (receivedRadiator && state.Sequence <= Store.Radiator.Sequence)) return;
            Store.Radiator = state;
            if (!receivedRadiator) radiatorVisualAngle = state.Angle;
            receivedRadiator = true;
        }

        internal void AdvanceRadiator()
        {
            if (!IsRadiator || Store.Radiator == null) return;
            var state = Store.Radiator;
            if (MyAPIGateway.Multiplayer.IsServer)
            {
                state.ParentId = RadiatorBase == null ? 0 : RadiatorBase.Entity.EntityId;
                state.Panels = Spec.Kind == ThermalKind.Radiator ? RadiatorPanels.Count : 1;
                if (Spec.Kind == ThermalKind.HullRadiator)
                {
                    state.Angle = state.Target = 0;
                    state.RejectedMW = CoolingRejectedMW;
                }
                else if (Spec.Kind == ThermalKind.Radiator)
                {
                    Vector3D sun = MyVisualScriptLogicProvider.GetSunDirection();
                    Vector3D local = Vector3D.TransformNormal(sun, MatrixD.Transpose(Block.WorldMatrix));
                    state.Target = Healthy ? ThermalRadiators.Target(local, state.Angle) : state.Angle;
                    state.Angle = ThermalRadiators.Step(state.Angle, state.Target, 1.0 / 60);
                    state.RejectedMW = CoolingRejectedMW;
                }
                else if (RadiatorBase != null)
                {
                    var parent = RadiatorBase.Store.Radiator;
                    state.Target = ThermalRadiators.PanelAngle(RadiatorBase.Block.WorldMatrix, Block.WorldMatrix, parent.Target);
                    state.Angle = ThermalRadiators.PanelAngle(RadiatorBase.Block.WorldMatrix, Block.WorldMatrix, parent.Angle);
                    state.RejectedMW = RadiatorBase.coolingMW > 0 ? parent.RejectedMW * PanelCoolingMW / RadiatorBase.coolingMW : 0;
                }
                else { state.Target = state.Angle; state.RejectedMW = 0; state.Exposure = 0; }
                double ownRejection = Spec.Kind == ThermalKind.Radiator
                    ? (coolingMW > 0 ? state.RejectedMW * PanelCoolingMW / coolingMW : 0) : state.RejectedMW;
                state.Glow = ThermalRadiators.HeatGlow(state.Glow, ownRejection, Spec.CoolingMW, 1.0 / 60);
                state.Sequence++;
                radiatorVisualAngle = state.Angle;
            }
            else if (receivedRadiator)
            {
                // Use the same interpolated pose for the entire assembly so the
                // side-pipe joints cannot separate between network snapshots.
                var parent = ThermalSession.RadiatorParent(state.ParentId);
                radiatorVisualAngle = parent != null && parent.receivedRadiator
                    ? ThermalRadiators.PanelAngle(parent.Block.WorldMatrix, Block.WorldMatrix, parent.radiatorVisualAngle)
                    : ThermalRadiators.Step(radiatorVisualAngle, state.Angle, 1.0 / 60);
            }
            if (Spec.Kind == ThermalKind.HullRadiator)
            {
                if (!MyAPIGateway.Utilities.IsDedicated) RadiatorGlow((MyEntity)Entity, state.Glow);
                return;
            }
            MyEntitySubpart part;
            if (!((MyEntity)Entity).Subparts.TryGetValue(ThermalRadiators.Subpart, out part)) return;
            Matrix pose = ThermalRadiators.Pose(radiatorVisualAngle, Spec.Kind == ThermalKind.RadiatorPanel);
            part.PositionComp.SetLocalMatrix(ref pose);
            // The native tool ray resolves subpart hits to the owning grid and
            // section. Keep real panel hulls in the same frame on servers too;
            // entity/model removal owns their physics cleanup.
            if (Block.CubeGrid.Physics != null && part.Physics == null)
                MyAPIGateway.Physics.CreateModelPhysics(MyAPIGateway.Physics.CreateSettingsForPhysics(
                    part, part.WorldMatrix, Vector3.Zero, rigidBodyFlags:
                    RigidBodyFlag.RBF_KINEMATIC | RigidBodyFlag.RBF_NO_POSITION_UPDATES));
            if (part.Physics != null)
            {
                part.Physics.Enabled = Block.CubeGrid.Physics != null;
                if (part.Physics.Enabled)
                {
                    part.Physics.LinearVelocity = Block.CubeGrid.Physics.LinearVelocity;
                    part.Physics.AngularVelocity = Block.CubeGrid.Physics.AngularVelocity;
                }
            }
            if (MyAPIGateway.Utilities.IsDedicated) return;
            RadiatorGlow(part, state.Glow);
        }

        private static void RadiatorGlow(MyEntity surface, double glow)
        {
            surface.SetEmissiveParts("ThermalRadiatorHeatRoot", new Color(255, 41, 18), (float)(glow * .12));
            surface.SetEmissiveParts("ThermalRadiatorHeatMid", new Color(255, 19, 9), (float)(glow * .07));
            surface.SetEmissiveParts("ThermalRadiatorHeatTip", new Color(255, 9, 5), (float)(glow * .0325));
        }

        private double RadiatorCooling(double density)
        {
            Vector3D sun = MyVisualScriptLogicProvider.GetSunDirection();
            // Native grid eclipse state only updates for registered solar blocks.
            // Check the same planetary shadows even on a radiator-only grid.
            var planets = new List<VRage.ModAPI.IMyVoxelBase>();
            MyAPIGateway.Session.VoxelMaps.GetInstances(planets, voxel => voxel is MyPlanet);
            bool shadow = false;
            foreach (MyPlanet planet in planets)
                if (ThermalRadiators.PlanetShadow(Block.CubeGrid.GetPosition() - planet.PositionComp.GetPosition(), planet.AverageRadius, sun))
                { shadow = true; break; }
            if (Spec.Kind == ThermalKind.HullRadiator) return HullRadiatorCooling(density, sun, shadow);
            double total = 0, rating = 0, exposure = 0, sunlight = 0;
            PanelCoolingMW = 0;
            foreach (var panel in RadiatorPanels)
            {
                panel.PanelCoolingMW = 0;
                if (!panel.Healthy) continue;
                total += panel.PanelCooling(density, ThermalRadiators.PanelAngle(Block.WorldMatrix,
                    panel.Block.WorldMatrix, Store.Radiator.Angle), sun, shadow);
                rating += panel.Spec.CoolingMW;
                if (panel.Store.Radiator != null)
                {
                    exposure += panel.Store.Radiator.Exposure * panel.Spec.CoolingMW;
                    sunlight += panel.Store.Radiator.SunIncidence * panel.Spec.CoolingMW;
                }
            }
            Store.Radiator.Exposure = rating > 0 ? exposure / rating : 0;
            Store.Radiator.SunIncidence = rating > 0 ? sunlight / rating : 0;
            return total;
        }

        private double PanelCooling(double density, double angle, Vector3D sun, bool shadow)
        {
            var state = Store.Radiator;
            if (state == null) return 0;
            MatrixD panel = ThermalRadiators.Pose(angle, true) * Block.WorldMatrix;
            Vector3D normal = panel.Backward, right = panel.Right, up = panel.Up;
            int visible = 0;
            foreach (int sign in new[] { -1, 1 })
                foreach (int x in new[] { -1, 1 })
                    foreach (double height in new[] { -1.02, .98 })
                    {
                        Vector3D from = panel.Translation + normal * (sign * .26) + right * (x * 1.55) + up * height;
                        VRage.Game.ModAPI.IHitInfo hit;
                        if (!MyAPIGateway.Physics.CastRay(from, from + normal * (sign * 250), out hit)) visible++;
                    }
            state.Exposure = visible / 8.0;
            var planet = MyGamePruningStructure.GetClosestPlanet(Block.GetPosition());
            shadow |= planet != null && MyVisualScriptLogicProvider.IsOnDarkSide(planet, Block.GetPosition());
            double cosine = Vector3D.Dot(normal, sun);
            int lit = 0;
            if (!shadow && Math.Abs(cosine) > .000001)
            {
                // Subdivide each former solar sample into four: 32 pivots give
                // 3.125% partial-shadow steps. Keep the vanilla sun-facing side,
                // 100 m/layer-15 rays and own-block exclusion in the moving frame.
                foreach (double x in new[] { -2.725, -1.975, -1.225, -.475, .475, 1.225, 1.975, 2.725 })
                    foreach (double height in new[] { -1.52, -.52, .48, 1.48 })
                    {
                        Vector3D pivot = panel.Translation + normal * (cosine >= 0 ? .26 : -.26) + right * x + up * height;
                        if (SolarPivotLit(pivot, sun)) lit++;
                    }
            }
            state.SunIncidence = ThermalRadiators.SolarExposure(cosine, lit / 32.0,
                MyAPIGateway.Session.WeatherEffects.GetSolarMultiplier(Block.GetPosition()), shadow);
            PanelCoolingMW = ThermalRadiators.Cooling(Spec.CoolingMW, state.Exposure, density, state.SunIncidence);
            return PanelCoolingMW;
        }

        private bool SolarPivotLit(Vector3D pivot, Vector3D sun)
        {
            if (solarHits == null) solarHits = new List<VRage.Game.ModAPI.IHitInfo>();
            solarHits.Clear();
            Vector3D far = pivot + sun * 100;
            MyAPIGateway.Physics.CastRay(pivot, far, solarHits, 15);
            foreach (var hit in solarHits)
            {
                if (hit.HitEntity != Block.CubeGrid) return false;
                Vector3I? cell = Block.CubeGrid.RayCastBlocks(far, pivot);
                if (cell.HasValue && Block.CubeGrid.GetCubeBlock(cell.Value) != Block.SlimBlock) return false;
            }
            return true;
        }

        private double HullRadiatorCooling(double density, Vector3D sun, bool shadow)
        {
            var state = Store.Radiator;
            if (state == null) return 0;
            var frame = Block.WorldMatrix;
            double cosine = Vector3D.Dot(frame.Forward, sun);
            var planet = MyGamePruningStructure.GetClosestPlanet(Block.GetPosition());
            shadow |= planet != null && MyVisualScriptLogicProvider.IsOnDarkSide(planet, Block.GetPosition());
            int clear = 0, lit = 0;
            foreach (var sample in ThermalModels.HullRadiatorSamples)
            {
                Vector3D from = Vector3D.Transform(sample, frame), to = from + frame.Forward * 250;
                VRage.Game.ModAPI.IHitInfo hit;
                // Samples lie outside the front armor plane. Backing and hull
                // behind the block never count as obstructing its active face.
                if (!Block.CubeGrid.RayCastBlocks(from, to).HasValue
                    && !MyAPIGateway.Physics.CastRay(from, to, out hit)
                    && !MyAPIGateway.Physics.CastRay(to, from, out hit)) clear++;
                if (!shadow && cosine > 0 && SolarPivotLit(from, sun)) lit++;
            }
            state.Exposure = clear / (double)ThermalModels.HullRadiatorSamples.Length;
            state.SunIncidence = ThermalRadiators.SolarExposure(Math.Max(0, cosine),
                lit / (double)ThermalModels.HullRadiatorSamples.Length,
                MyAPIGateway.Session.WeatherEffects.GetSolarMultiplier(Block.GetPosition()), shadow);
            PanelCoolingMW = ThermalRadiators.Cooling(Spec.CoolingMW, state.Exposure, density, state.SunIncidence);
            return PanelCoolingMW;
        }

        internal void InvalidateRadiatorCooling() { environmentAt = -1000; CircuitRevision++; }
    }
}
