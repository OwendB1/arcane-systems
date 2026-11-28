using System;
using System.Collections.Generic;
using Sandbox.Common.ObjectBuilders;
using Sandbox.ModAPI;
using Sandbox.ModAPI.Interfaces.Terminal;
using VRage.Game.Components;
using VRage.Game.Entity;
using VRage.Game.ModAPI;
using VRage.Game.ModAPI.Ingame.Utilities;
using VRage.ModAPI;
using VRage.ObjectBuilders;
using VRageMath;

namespace ArcaneThrusters
{
    [MyEntityComponentDescriptor(typeof(MyObjectBuilder_Thrust), false, "ArcaneThrusters_DualModeThrusterLG",
        "ArcaneThrusters_DrivePriorityLG", "ArcaneThrusters_VacuumLG", "ArcaneThrusters_AtmosphericLG")]
    public sealed class NozzleGimbal : MyGameLogicComponent
    {
        private readonly List<IMyShipController> controllers = new List<IMyShipController>();
        private readonly List<Vector3> pivots = new List<Vector3>();
        private readonly MyIni ini = new MyIni();
        private IMyThrust engine;
        private IMyModel model;
        private float travel, pitch, yaw, trimPitch, trimYaw;
        private FieldReading lastSnapshot;
        private const int CommandTimeout = 120;
        private float commandPitch, commandYaw;
        private int pitchAt = -CommandTimeout, yawAt = -CommandTimeout;
        private int forceFrame = -2, previousFrame = -2, receivedAt = -CommandTimeout;
        private Vector3D force, previousForce;
        private static readonly List<IMyTerminalControl> properties = new List<IMyTerminalControl>();
        private int ticks;
        private bool followPilot;
        private string trimData;
        private static readonly string[] YawParts = { "Yaw01", "Yaw02", "Yaw03" };
        private static readonly string[] PitchParts = { "Pitch01", "Pitch02", "Pitch03" };

        private static int Frame { get { return MyAPIGateway.Session.GameplayFrameCounter; } }

        internal static void RegisterProperties()
        {
            Register<float>("PitchTrim", g => g.Command(true), (g, v) => g.SetCommand(true, v));
            Register<float>("YawTrim", g => g.Command(false), (g, v) => g.SetCommand(false, v));
            Register<float>("AppliedPitch", g => g.pitch);
            Register<float>("AppliedYaw", g => g.yaw);
            Register<float>("TravelLimit", g => g.travel);
            Register<Vector3D>("DeliveredForce", g => g.DeliveredForce());
        }

        private static void Register<T>(string name, Func<NozzleGimbal, T> read, Action<NozzleGimbal, T> write = null)
        {
            var controls = MyAPIGateway.TerminalControls;
            var property = controls.CreateProperty<T, IMyThrust>("ArcaneGimbal." + name);
            property.Getter = block =>
            {
                var gimbal = block.GameLogic?.GetAs<NozzleGimbal>();
                return gimbal == null ? default(T) : read(gimbal);
            };
            property.Setter = (block, value) =>
            {
                if (write == null || !MyAPIGateway.Multiplayer.IsServer) return;
                var gimbal = block.GameLogic?.GetAs<NozzleGimbal>();
                if (gimbal != null) write(gimbal, value);
            };
            controls.AddControl<IMyThrust>(property);
            properties.Add(property);
        }

        internal static void UnregisterProperties()
        {
            foreach (var property in properties) MyAPIGateway.TerminalControls.RemoveControl<IMyThrust>(property);
            properties.Clear();
        }

        private float Command(bool isPitch)
        {
            if (Frame - (isPitch ? pitchAt : yawAt) >= CommandTimeout) return 0;
            return isPitch ? commandPitch : commandYaw;
        }

        private void SetCommand(bool isPitch, float value)
        {
            if (isPitch) { commandPitch = Clamp(value, travel); pitchAt = Frame; }
            else { commandYaw = Clamp(value, travel); yawAt = Frame; }
        }

        private Vector3D DeliveredForce()
        {
            if (!MyAPIGateway.Multiplayer.IsServer) return Frame - receivedAt < CommandTimeout ? force : Vector3D.Zero;
            // Components may call ApplyAdditional on either side of the native correction in a tick.
            int completed = Frame - 1;
            if (forceFrame == completed) return force;
            return previousFrame == completed ? previousForce : Vector3D.Zero;
        }

        public override void Init(MyObjectBuilder_EntityBase builder) { NeedsUpdate = MyEntityUpdateEnum.BEFORE_NEXT_FRAME; }
        public override void UpdateOnceBeforeFrame()
        {
            engine = (IMyThrust)Entity;
            if (engine.CubeGrid.Physics == null) return;
            if (MyAPIGateway.Session == null) { NeedsUpdate |= MyEntityUpdateEnum.BEFORE_NEXT_FRAME; return; }
            travel = engine.BlockDefinition.SubtypeName.Contains("Vacuum") || engine.BlockDefinition.SubtypeName.Contains("Priority") ? 1.5f : 2f;
            ReadTrim(engine);
            NeedsUpdate |= MyEntityUpdateEnum.EACH_FRAME;
        }

        private void ReadTrim(IMyTerminalBlock block)
        {
            trimData = block.CustomData;
            ini.Clear();
            ini.TryParse(trimData);
            trimPitch = Clamp(ini.Get("Arcane Gimbal", "Pitch").ToSingle(), travel);
            trimYaw = Clamp(ini.Get("Arcane Gimbal", "Yaw").ToSingle(), travel);
            followPilot = ini.Get("Arcane Gimbal", "FollowPilot").ToBoolean(true);
        }

        private static float Clamp(float value, float limit)
        {
            return float.IsNaN(value) || float.IsInfinity(value) ? 0 : MathHelper.Clamp(value, -limit, limit);
        }

        public override void UpdateAfterSimulation()
        {
            if (model != Entity.Model)
            {
                model = Entity.Model;
                pivots.Clear();
                if (model != null)
                {
                    var dummies = new Dictionary<string, IMyModelDummy>();
                    model.GetDummies(dummies);
                    for (int i = 1; i <= 3; i++)
                    {
                        IMyModelDummy marker;
                        if (dummies.TryGetValue("subpart_Pitch0" + i, out marker)) pivots.Add(marker.Matrix.Translation);
                    }
                }
            }
            if (pivots.Count == 0) return;
            if (MyAPIGateway.Multiplayer.IsServer)
            {
                if (ticks % 10 == 0 && trimData != engine.CustomData) ReadTrim(engine);
                if (ticks % 60 == 0 && followPilot)
                {
                    controllers.Clear();
                    var terminal = MyAPIGateway.TerminalActionsHelper.GetTerminalSystemForGrid(engine.CubeGrid);
                    if (terminal != null) terminal.GetBlocksOfType(controllers, c => c.CubeGrid == engine.CubeGrid);
                }
                Vector3 steer = Vector3.Zero;
                if (followPilot)
                    foreach (var cockpit in controllers)
                    {
                        if (cockpit.MarkedForClose || !cockpit.IsUnderControl || !cockpit.IsWorking) continue;
                        var input = cockpit.RotationIndicator;
                        var torque = cockpit.WorldMatrix.Right * -input.X + cockpit.WorldMatrix.Up * -input.Y
                            + cockpit.WorldMatrix.Backward * -cockpit.RollIndicator;
                        var lever = engine.GetPosition() - engine.CubeGrid.Physics.CenterOfMassWorld;
                        if (lever.LengthSquared() > .0001)
                            steer = Vector3D.TransformNormal(Vector3D.Cross(torque, Vector3D.Normalize(lever)),
                                MatrixD.Transpose(engine.WorldMatrix));
                        break;
                    }
                pitch = Clamp(trimPitch + Command(true) - travel * Clamp(steer.Y / 9, 1), travel);
                yaw = Clamp(trimYaw + Command(false) + travel * Clamp(steer.X / 9, 1), travel);
                CorrectDirection(engine.CurrentThrust);
                if (MyAPIGateway.Multiplayer.MultiplayerActive && ticks % 10 == 0) PublishPose();
                ticks++;
            }
            if (!MyAPIGateway.Utilities.IsDedicated) Pose();
        }

        private void PublishPose()
        {
            var delivered = DeliveredForce();
            float p = Command(true), y = Command(false);
            if (ticks % 60 != 0 && lastSnapshot != null && pitch == lastSnapshot.Pitch && yaw == lastSnapshot.Yaw
                && p == lastSnapshot.CommandPitch && y == lastSnapshot.CommandYaw && delivered == lastSnapshot.WorldForce) return;
            lastSnapshot = new FieldReading { EntityId = engine.EntityId, GimbalPose = true, Pitch = pitch, Yaw = yaw,
                CommandPitch = p, CommandYaw = y, WorldForce = delivered };
            FieldTelemetry.Send(engine, lastSnapshot);
        }

        internal void Receive(FieldReading reading)
        {
            pitch = Clamp(reading.Pitch, travel);
            yaw = Clamp(reading.Yaw, travel);
            SetCommand(true, reading.CommandPitch);
            SetCommand(false, reading.CommandYaw);
            receivedAt = Frame;
            force = reading.WorldForce;
        }
        private Matrix Rotation() { return Matrix.CreateRotationX(MathHelper.ToRadians(pitch)) * Matrix.CreateRotationY(MathHelper.ToRadians(yaw)); }

        internal void PoseExhaust(int index, ref Vector3 exit, ref Vector3 axis)
        {
            if (index >= pivots.Count) return;
            Matrix rotation = Rotation();
            exit = pivots[index] + Vector3.TransformNormal(exit - pivots[index], rotation);
            axis = Vector3.TransformNormal(axis, rotation);
        }

        private void Pose()
        {
            var body = (MyEntity)Entity;
            var horizontal = Matrix.CreateRotationY(MathHelper.ToRadians(yaw));
            var combined = Matrix.CreateRotationX(MathHelper.ToRadians(pitch)) * horizontal;
            for (int i = 0; i < pivots.Count; i++)
            {
                SetPose(body, YawParts[i], horizontal, pivots[i]);
                SetPose(body, PitchParts[i], combined, pivots[i]);
            }
        }

        private static void SetPose(MyEntity body, string name, Matrix pose, Vector3 pivot)
        {
            MyEntitySubpart part;
            if (!body.Subparts.TryGetValue(name, out part)) return;
            pose.Translation = pivot;
            if (part.PositionComp.LocalMatrixRef != pose) part.PositionComp.SetLocalMatrix(ref pose);
        }

        private void CorrectDirection(double axial)
        {
            if (axial <= 0) return;
            if (forceFrame != Frame)
            {
                previousFrame = forceFrame;
                previousForce = force;
                forceFrame = Frame;
                force = Vector3D.Zero;
            }
            var world = engine.WorldMatrix;
            var direction = pivots.Count == 0 ? world.Backward : Vector3D.TransformNormal(Rotation().Backward, world);
            force += direction * axial;
            if ((pitch == 0 && yaw == 0) || pivots.Count == 0) return;
            var delta = direction - world.Backward;
            var perNozzle = (Vector3)(delta * (axial / pivots.Count));
            foreach (var pivot in pivots)
                engine.CubeGrid.Physics.AddForce(MyPhysicsForceType.APPLY_WORLD_FORCE, perNozzle, Vector3D.Transform(pivot, world), null);
        }

        internal static void ApplyAdditional(IMyThrust engine, double thrust)
        {
            engine.CubeGrid.Physics.AddForce(MyPhysicsForceType.APPLY_WORLD_FORCE,
                (Vector3)(engine.WorldMatrix.Backward * thrust), null, null);
            var gimbal = engine.GameLogic.GetAs<NozzleGimbal>();
            if (gimbal != null) gimbal.CorrectDirection(thrust);
        }

    }
}
