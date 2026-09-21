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
        private bool ventRouteIncomplete;
        private MyEntity ventOutlet;
        private readonly Dictionary<string, Matrix> outletRest = new Dictionary<string, Matrix>();

        private void RefreshVentRoute()
        {
            Motion.VentOutletId = 0;
            Motion.EjectionTravel = 18;
            ventRouteIncomplete = false;
            Vector3I up = Base6Directions.GetIntVector(reactor.Orientation.Up);
            for (int i = 0; i < 16; i++)
            {
                Vector3I position = reactor.Position + up * (2 + i);
                var slim = reactor.CubeGrid.GetCubeBlock(position);
                var block = slim == null ? null : slim.FatBlock;
                string subtype = block == null ? "" : block.BlockDefinition.SubtypeName;
                if (subtype != "ArcanePower_VentDuct" && subtype != "ArcanePower_VentOutlet")
                {
                    ventRouteIncomplete = i > 0;
                    return;
                }
                if (block.Position != position || block.Orientation.Up != reactor.Orientation.Up || !block.IsFunctional)
                {
                    ventRouteIncomplete = true;
                    return;
                }
                if (subtype == "ArcanePower_VentOutlet")
                {
                    Motion.VentOutletId = block.EntityId;
                    Motion.EjectionTravel = System.Math.Max(18, (i + 4) * 2.5f);
                    return;
                }
            }
            ventRouteIncomplete = true;
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
            bool venting = Motion.Vent != VentPhase.Idle;
            Color color = venting || Motion.Critical ? Color.Red : Motion.Status == ReactorStatus.Active ? FuelColors[Motion.Profile - 2]
                : Motion.Status == ReactorStatus.OutOfFuel ? Color.Yellow : Color.Red;
            float intensity = EmissiveIntensity * (venting || Motion.Critical || Motion.Status == ReactorStatus.Incomplete
                ? .5f + .5f * (float)System.Math.Cos(pulseTick * System.Math.PI / 60) : 1f);
            ventOutlet.SetEmissiveParts("Emissive", color, intensity);
            ventOutlet.SetEmissivePartsForSubparts("Emissive", color, intensity);
        }
    }
}
