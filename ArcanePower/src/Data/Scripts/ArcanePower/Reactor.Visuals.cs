using Sandbox.ModAPI;
using VRage.Game.Entity;
using VRageMath;

namespace ArcanePower
{
    public sealed partial class Reactor
    {
        private void Part(string name, Matrix pose, bool visible = true)
        {
            if (MyAPIGateway.Utilities.IsDedicated) return;
            MyEntitySubpart part;
            if (!restPoses.ContainsKey(name) || !((MyEntity)Entity).Subparts.TryGetValue(name, out part)) return;
            part.PositionComp.SetLocalMatrix(ref pose);
            if (part.Render.Visible != visible) part.Render.Visible = visible;
        }

        private void DrawMotion()
        {
            if (MyAPIGateway.Utilities.IsDedicated) return;
            float age = Motion.Core == CorePhase.Off ? 0 : Motion.CoreTick + Motion.CoreSubtick;
            float alive = Motion.PayloadReleased ? 0 : 1;
            Matrix fieldRotation = ContainmentRotation(age);
            for (int i = 0; i < 4; i++)
            {
                string name = "Floor" + (i + 1);
                Matrix floor = Rest(name);
                float drop = Span(age, 0, 24) - Span(age, 274, 298);
                float slide = Span(age, 26, 76) - Span(age, 220, 270);
                floor.Translation += new Vector3(0, -.32f * drop, 0) + AnimationGeometry.FloorSlides[i] * slide;
                Part(name, floor);
                name = "Ring" + (i + 1);
                Matrix ring = PayloadRingPose(i, age);
                Part(name, ring, i < Motion.RingCount && alive > 0);
            }
            foreach (var tile in AnimationGeometry.Tiles)
            {
                float t = age - (320 + 36 * tile.Batch);
                Matrix pose = PayloadTilePose(tile, age, fieldRotation);
                Part(tile.Name, pose, t >= 0 && alive > 0);
            }
            Matrix plasma = PayloadPlasmaPose(age);
            Part("Plasma", plasma, PlasmaScale(age) > 0);
            for (int i = 0; i < 6; i++)
            {
                string name = "BlastShield" + (i + 1);
                Matrix pose = Rest(name);
                pose.Translation -= new Vector3(0, AnimationGeometry.ShieldTravel[i] * Ease(Motion.Shield), 0);
                Part(name, pose);
            }
            for (int i = 0; i < 4; i++)
            {
                string name = "VentHatch" + (i + 1);
                Matrix pose = Rest(name);
                pose.Translation += Vector3.Down * AnimationGeometry.HatchDrop * Span(Motion.Intake, 0, .3f)
                    + AnimationGeometry.HatchSlides[i] * Span(Motion.Intake, .3f, 1);
                Part(name, pose);
                name = "CeilingHatch" + (i + 1);
                pose = Rest(name);
                pose.Translation += Vector3.Up * AnimationGeometry.CeilingHatchLift * Span(Motion.Intake, 0, .3f)
                    + AnimationGeometry.CeilingHatchSlides[i] * Span(Motion.Intake, .3f, 1);
                Part(name, pose);
            }
        }
    }
}
