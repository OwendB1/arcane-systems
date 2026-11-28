using System;
using System.Collections.Generic;
using Sandbox.Common.ObjectBuilders;
using Sandbox.Game.Entities;
using Sandbox.ModAPI;
using VRage.Game;
using VRage.Game.Components;
using VRage.Game.ModAPI;
using VRage.ModAPI;
using VRage.ObjectBuilders;
using VRage.Utils;
using VRageMath;
using VRageRender;

namespace ArcaneThrusters
{
    [MySessionComponentDescriptor(MyUpdateOrder.NoUpdate)]
    public sealed class PlumeRenderer : MySessionComponentBase
    {
        internal static readonly HashSet<DrivePlume> Engines = new HashSet<DrivePlume>();

        public override void Draw()
        {
            var camera = MyAPIGateway.Session.Camera;
            if (camera == null) return;
            foreach (var plume in Engines) plume.Draw(camera.Position);
        }

        protected override void UnloadData() { Engines.Clear(); }
    }

    [MyEntityComponentDescriptor(typeof(MyObjectBuilder_Thrust), false,
        "ArcaneThrusters_DualModeThrusterSG", "ArcaneThrusters_DualModeThrusterSG_Hull",
        "ArcaneThrusters_DualModeThrusterLG", "ArcaneThrusters_DualModeThrusterLG_Hull",
        "ArcaneThrusters_VacuumLG", "ArcaneThrusters_VacuumLG_Hull",
        "ArcaneThrusters_AtmosphericLG", "ArcaneThrusters_AtmosphericLG_Hull",
        "ArcaneThrusters_DrivePriorityLG", "ArcaneThrusters_DrivePriorityLG_Hull")]
    public sealed class DrivePlume : MyGameLogicComponent
    {
        private static readonly MyStringId Envelope = MyStringId.GetOrCompute("ArcaneThrusters_Envelope");
        private static readonly MyStringId Cells = MyStringId.GetOrCompute("ArcaneThrusters_Cells");
        private static readonly MyStringId Mouth = MyStringId.GetOrCompute("ArcaneThrusters_Mouth");
        private static readonly Vector4 Hydrogen = new Vector4(.10f, .51f, 1f, 1f);
        private static readonly Vector4 Plasma = new Vector4(.56f, .11f, 1f, 1f);
        private static readonly Vector4 Thermal = new Vector4(1f, .34f, .055f, 1f);
        private static readonly Vector4 CoolCore = new Vector4(.66f, .94f, 1f, 1f);
        private static readonly Vector4 HotCore = new Vector4(1f, .84f, .48f, 1f);
        private readonly List<Matrix> markers = new List<Matrix>(3);
        private IMyThrust engine;
        private IMyModel model;
        private NozzleGimbal gimbal;
        private bool thermal;
        private int paidFrame = -1000;
        private float paidFraction;
        private int nextDensitySample;
        private float airDensity;

        public override void Init(MyObjectBuilder_EntityBase builder) { NeedsUpdate = MyEntityUpdateEnum.BEFORE_NEXT_FRAME; }

        public override void UpdateOnceBeforeFrame()
        {
            engine = (IMyThrust)Entity;
            if (MyAPIGateway.Utilities.IsDedicated || engine.CubeGrid.Physics == null) return;
            gimbal = engine.GameLogic.GetAs<NozzleGimbal>();
            thermal = engine.GameLogic.GetAs<ThermalDrive>() != null;
            PlumeRenderer.Engines.Add(this);
        }

        internal static void Record(IMyThrust engine, double fraction)
        {
            if (engine == null || MyAPIGateway.Utilities.IsDedicated) return;
            var plume = engine.GameLogic.GetAs<DrivePlume>();
            if (plume == null) return;
            int now = MyAPIGateway.Session.GameplayFrameCounter;
            plume.paidFraction = MathHelper.Clamp((float)fraction +
                (plume.paidFrame == now && MyAPIGateway.Multiplayer.IsServer ? plume.paidFraction : 0f), 0f, 1f);
            plume.paidFrame = now;
        }

        internal void Draw(Vector3D camera)
        {
            if (engine.MarkedForClose || !engine.InScene || !engine.IsWorking || engine.CubeGrid.Physics == null
                || Vector3D.DistanceSquared(camera, engine.GetPosition()) > 700 * 700) return;
            // Local burns are sampled per tick. Peers receive the existing one-second field readings.
            float paid = MyAPIGateway.Session.GameplayFrameCounter - paidFrame <= (MyAPIGateway.Multiplayer.IsServer ? 1 : 120)
                ? paidFraction : 0;
            float power = thermal ? paid : engine.MaxEffectiveThrust > 0
                ? MathHelper.Clamp(engine.CurrentThrust / engine.MaxEffectiveThrust, 0f, 1f) : 0;
            if (power <= .001f) return;

            if (model != Entity.Model)
            {
                model = Entity.Model;
                markers.Clear();
                if (model == null) return;
                var dummies = new Dictionary<string, IMyModelDummy>();
                model.GetDummies(dummies);
                for (int i = 1; i <= 3; i++)
                {
                    IMyModelDummy marker;
                    if (dummies.TryGetValue("thruster_flame_0" + i, out marker)) markers.Add(marker.Matrix);
                }
            }

            Vector4 tint = thermal ? Thermal : Vector4.Lerp(Hydrogen, Plasma, paid);
            Vector4 core = thermal ? HotCore : CoolCore;
            float light = (float)Math.Sqrt(power);
            int frame = MyAPIGateway.Session.GameplayFrameCounter;
            if (frame >= nextDensitySample)
            {
                var position = engine.GetPosition();
                var planet = MyGamePruningStructure.GetClosestPlanet(position);
                airDensity = planet == null ? 0f : MathHelper.Clamp(planet.GetAirDensity(position), 0f, 1f);
                nextDensitySample = frame + 30;
            }
            // Keep the compression pattern stable and let the dim outer jet breathe independently.
            double time = frame / 60.0 + engine.EntityId % 101;
            var world = engine.WorldMatrix;
            for (int i = 0; i < markers.Count; i++)
            {
                Matrix marker = markers[i];
                Vector3 exit = marker.Translation, axis = Vector3.Normalize(marker.Forward);
                if (gimbal != null) gimbal.PoseExhaust(i, ref exit, ref axis);
                Vector3 dir = (Vector3)Vector3D.TransformNormal(axis, world);
                float radius = marker.Right.Length() * .5f;
                float recess = radius * .08f;
                var origin = Vector3D.Transform(exit, world) - dir * recess;
                float length = recess + radius * (1f + 15f * light);
                double phase = time + i * 2.1;
                float ripple = (float)(Math.Sin(phase * 9) + .45 * Math.Sin(phase * 17));
                float width = radius * 1.45f;
                var view = camera - origin;
                if (view.LengthSquared() < .000001) continue;
                float facing = (float)Vector3D.Dot(Vector3D.Normalize(view), dir);
                // A side-on sprite loses its depth when sighting down the jet. Crossfade
                // to the recessed source before the camera intersects the billboard.
                float side = MathHelper.SmoothStep(0f, 1f,
                    MathHelper.Clamp((1f - Math.Abs(facing) - .018f) / .17f, 0f, 1f));
                if (side > 0f)
                {
                    // Tuck the feathered ribbon under the lip to avoid a straight cut through
                    // the round aperture at oblique angles. Its far end stays at the same station.
                    float overlap = radius * .40f * light;
                    var start = origin - dir * overlap;
                    var end = start + dir * ((length + overlap) * (1f + .016f * ripple));
                    var edge = Vector3D.Normalize(Vector3D.Cross(dir, camera - start)) * width;
                    var tipEdge = edge * MathHelper.Lerp(2.05f, 1f, airDensity);
                    var envelope = new MyQuadD { Point0 = start - edge, Point1 = end - tipEdge,
                        Point2 = end + tipEdge, Point3 = start + edge };
                    MyTransparentGeometry.AddQuad(Envelope, ref envelope, tint * (light * side), ref start, blendType: MyBillboard.BlendTypeEnum.AdditiveBottom);
                    // Concentrate the compression-cell light in air; it must read against a sunlit sky.
                    float cellIntensity = MathHelper.Lerp(.15f, 16f, airDensity * airDensity);
                    MyTransparentGeometry.AddLineBillboard(Cells, core * (power * side), origin, dir, length, width,
                        MyBillboard.BlendTypeEnum.AdditiveBottom, intensity: cellIntensity);
                }
                if (facing > 0)
                {
                    // Keep the luminous aperture in the plane of the gimballed lip.
                    Vector3 left = Vector3.Normalize(Vector3.Cross((Vector3)world.Up, dir));
                    Vector3 up = Vector3.Cross(dir, left);
                    MyTransparentGeometry.AddBillboardOriented(Mouth, Vector4.Lerp(tint, core, .26f) * (light * facing),
                        origin, left, up, radius, MyBillboard.BlendTypeEnum.AdditiveBottom);
                }
            }
        }

        public override void Close() { PlumeRenderer.Engines.Remove(this); }
    }
}
