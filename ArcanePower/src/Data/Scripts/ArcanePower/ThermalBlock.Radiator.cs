using System;
using System.Collections.Generic;
using Sandbox.Game;
using Sandbox.ModAPI;
using VRage.Game.Entity;
using VRageMath;

namespace ArcanePower
{
    public abstract partial class ThermalBlock
    {
        private bool receivedRadiator;
        private double radiatorVisualAngle;
        internal double RadiatorRejectedMW;
        internal ThermalBlock RadiatorBase;
        internal readonly List<ThermalBlock> RadiatorPanels = new List<ThermalBlock>();
        internal double PanelCoolingMW;
        internal double EffectiveRatingMW { get { return Spec.RatingMW * (1 + RadiatorPanels.Count); } }
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
                    state.RejectedMW = RadiatorRejectedMW;
                }
                else if (RadiatorBase != null)
                {
                    var parent = RadiatorBase.Store.Radiator;
                    state.Target = parent.Target; state.Angle = parent.Angle;
                    state.RejectedMW = RadiatorBase.coolingMW > 0 ? parent.RejectedMW * PanelCoolingMW / RadiatorBase.coolingMW : 0;
                }
                else { state.Target = state.Angle; state.RejectedMW = 0; state.Exposure = 0; }
                double ownRejection = Spec.Kind == ThermalKind.Radiator
                    ? (coolingMW > 0 ? state.RejectedMW * PanelCoolingMW / coolingMW : 0) : state.RejectedMW;
                state.Glow = ThermalRadiators.HeatGlow(state.Glow, ownRejection, Spec.RatingMW * .6, 1.0 / 60);
                state.Sequence++;
                radiatorVisualAngle = state.Angle;
            }
            else if (receivedRadiator)
            {
                // Use the same interpolated pose for the entire assembly so the
                // side-pipe joints cannot separate between network snapshots.
                var parent = ThermalSession.RadiatorParent(state.ParentId);
                radiatorVisualAngle = parent != null && parent.receivedRadiator
                    ? parent.radiatorVisualAngle : ThermalRadiators.Step(radiatorVisualAngle, state.Angle, 1.0 / 60);
            }
            if (MyAPIGateway.Utilities.IsDedicated) return;
            MyEntitySubpart part;
            if (!((MyEntity)Entity).Subparts.TryGetValue(ThermalRadiators.Subpart, out part)) return;
            Matrix pose = ThermalRadiators.Pose(radiatorVisualAngle, Spec.Kind == ThermalKind.RadiatorPanel);
            part.PositionComp.SetLocalMatrix(ref pose);
            part.SetEmissiveParts("ThermalRadiatorHeatRoot", new Color(255, 41, 18), (float)(state.Glow * .12));
            part.SetEmissiveParts("ThermalRadiatorHeatMid", new Color(255, 19, 9), (float)(state.Glow * .07));
            part.SetEmissiveParts("ThermalRadiatorHeatTip", new Color(255, 9, 5), (float)(state.Glow * .0325));
        }

        private double RadiatorCooling(double density)
        {
            double total = PanelCooling(density, Store.Radiator.Angle);
            foreach (var panel in RadiatorPanels) total += panel.PanelCooling(density, Store.Radiator.Angle);
            return total;
        }

        private double PanelCooling(double density, double angle)
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
            state.SunIncidence = ThermalMath.Clamp(Math.Abs(Vector3D.Dot(normal, MyVisualScriptLogicProvider.GetSunDirection())), 0, 1);
            PanelCoolingMW = ThermalRadiators.Cooling(Spec.RatingMW * .6, state.Exposure, density > .001 ? 25 : -270.15, state.SunIncidence);
            return PanelCoolingMW;
        }

        internal void InvalidateRadiatorCooling() { environmentAt = -1000; }
    }
}
