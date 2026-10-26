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
        private List<VRage.Game.ModAPI.IHitInfo> solarHits;
        internal bool IsRadiator { get { return Spec.Kind == ThermalKind.Radiator || Spec.Kind == ThermalKind.RadiatorPanel; } }

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
                state.Panels = 1 + RadiatorPanels.Count;
                if (Spec.Kind == ThermalKind.Radiator)
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
            part.SetEmissiveParts("ThermalRadiatorHeatRoot", new Color(255, 41, 18), (float)(state.Glow * .12));
            part.SetEmissiveParts("ThermalRadiatorHeatMid", new Color(255, 19, 9), (float)(state.Glow * .07));
            part.SetEmissiveParts("ThermalRadiatorHeatTip", new Color(255, 9, 5), (float)(state.Glow * .0325));
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
            double total = PanelCooling(density, Store.Radiator.Angle, sun, shadow);
            foreach (var panel in RadiatorPanels)
                total += panel.PanelCooling(density, ThermalRadiators.PanelAngle(Block.WorldMatrix,
                    panel.Block.WorldMatrix, Store.Radiator.Angle), sun, shadow);
            return total;
        }

        private double PanelCooling(double density, double angle, Vector3D sun, bool shadow)
        {
            var state = Store.Radiator;
            if (state == null) return 0;
            bool extension = Spec.Kind == ThermalKind.RadiatorPanel;
            MatrixD panel = ThermalRadiators.Pose(angle, extension) * Block.WorldMatrix;
            Vector3D normal = panel.Backward, right = panel.Right, up = panel.Up;
            int visible = 0;
            foreach (int sign in new[] { -1, 1 })
                foreach (int x in new[] { -1, 1 })
                    foreach (double height in extension ? new[] { -1.02, .98 } : new[] { 1.6, 3.6 })
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
                    foreach (double height in extension ? new[] { -1.52, -.52, .48, 1.48 } : new[] { 1.1, 2.1, 3.1, 4.1 })
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

        internal void InvalidateRadiatorCooling() { environmentAt = -1000; CircuitRevision++; }
    }
}
