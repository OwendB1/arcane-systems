using System.Collections.Generic;
using Sandbox.ModAPI;
using VRage.Game.Entity;
using VRage.Game.ModAPI;
using VRage.ModAPI;
using VRageMath;

namespace ArcanePower
{
    public sealed partial class Reactor
    {
        private MyEntity ventOutlet;
        private readonly Dictionary<string, Matrix> outletRest = new Dictionary<string, Matrix>();

        // Run before fuel/power/tile updates: a missing route must never fund a
        // new field. Existing containment still receives power during shutdown.
        private void CheckVentRoute()
        {
            if (!MyAPIGateway.Multiplayer.IsServer) return;
            RefreshVentRoute();
            if (initializationFrames == 0 && !CanOperate) reactor.Enabled = false;
        }

        private void RefreshVentRoute()
        {
            Motion.VentReady = false;
            bool committed = Motion.Vent != VentPhase.Idle;
            if (!committed)
            {
                Motion.VentOutletId = 0;
                Motion.VentDucts = 0;
                Motion.EjectionTravel = 18;
            }
            IMyCubeBlock outlet;
            int ducts;
            if (!FindVentOutlet(reactor, out outlet, out ducts)) return;
            if (committed && Motion.VentDucts > 0 && ducts != Motion.VentDucts) return;
            float travel = System.Math.Max(18, (ducts + 4) * 2.5f);
            // Preserve the trajectory of older saves without a stored duct count.
            if (committed && Motion.VentDucts == 0 && travel != Motion.EjectionTravel) return;
            Motion.VentOutletId = outlet.EntityId;
            Motion.VentDucts = ducts;
            Motion.EjectionTravel = travel;
            Motion.VentReady = true;
        }

        // One physical route contract for the startup interlock and vent lamps.
        internal static bool FindVentOutlet(IMyCubeBlock source, out IMyCubeBlock outlet, out int ducts)
        {
            outlet = null;
            ducts = 0;
            Vector3I up = Base6Directions.GetIntVector(source.Orientation.Up);
            for (int i = 0; i < 16; i++)
            {
                Vector3I position = source.Position + up * (2 + i);
                var slim = source.CubeGrid.GetCubeBlock(position);
                var block = slim == null ? null : slim.FatBlock;
                string subtype = block == null ? "" : block.BlockDefinition.SubtypeName;
                if (subtype != "ArcanePower_VentDuct" && subtype != "ArcanePower_VentOutlet") return false;
                if (block.Position != position || block.Orientation.Up != source.Orientation.Up
                    || !block.IsFunctional || slim.BuildLevelRatio < 1f) return false;
                if (subtype == "ArcanePower_VentOutlet")
                {
                    if (i == 0) return false;
                    outlet = block;
                    ducts = i;
                    return true;
                }
            }
            return false;
        }

        private void DrawVentOutlet()
        {
            if (Motion.VentOutletId == 0) { ventOutlet = null; outletRest.Clear(); return; }
            if (ventOutlet == null || ventOutlet.EntityId != Motion.VentOutletId || ventOutlet.Closed || outletRest.Count == 0)
            {
                IMyEntity entity;
                if (!MyAPIGateway.Entities.TryGetEntityById(Motion.VentOutletId, out entity)) return;
                ventOutlet = entity as MyEntity;
                outletRest.Clear();
                if (ventOutlet == null || ((IMyEntity)ventOutlet).Model == null) return;
                var dummies = new Dictionary<string, IMyModelDummy>();
                ((IMyEntity)ventOutlet).Model.GetDummies(dummies);
                foreach (var pair in dummies)
                    if (pair.Key.StartsWith("subpart_")) outletRest[pair.Key.Substring(8)] = pair.Value.Matrix;
            }
            for (int i = 0; i < 4; i++)
            {
                string name = "OutletHatch" + (i + 1);
                Matrix pose;
                MyEntitySubpart part;
                if (!outletRest.TryGetValue(name, out pose) || !ventOutlet.Subparts.TryGetValue(name, out part)) continue;
                // Same Intake clock as both reactor doors. The narrower external
                // pocket uses 1.4m per-axis travel within a 3x3-cell casing.
                pose.Translation += Vector3.Down * .30f * Span(Motion.Intake, 0, .3f)
                    + AnimationGeometry.HatchSlides[i] * (1.40f / 1.95f) * Span(Motion.Intake, .3f, 1);
                part.PositionComp.SetLocalMatrix(ref pose);
            }
            // VentHardware owns both tube and outlet lamps, including orphans.
        }
    }
}
