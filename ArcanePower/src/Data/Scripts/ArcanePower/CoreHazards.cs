using System;
using System.Collections.Generic;
using ProtoBuf;
using Sandbox.Game;
using Sandbox.Game.Entities;
using Sandbox.Game.Lights;
using Sandbox.ModAPI;
using VRage;
using VRage.ObjectBuilders;
using VRage.Game;
using VRage.Game.Components;
using VRage.Game.Entity;
using VRage.Game.ModAPI;
using VRage.ModAPI;
using VRage.Utils;
using VRageMath;

namespace ArcanePower
{
    [ProtoContract]
    public sealed class CoreShellPart
    {
        [ProtoMember(1)] public string Subtype;
        [ProtoMember(2)] public Matrix Pose;
    }

    [ProtoContract]
    public sealed class CoreHazard
    {
        [ProtoMember(1)] public long SourceId;
        [ProtoMember(2)] public long CarrierId;
        [ProtoMember(3)] public int Tier;
        [ProtoMember(4)] public float Heat;
        [ProtoMember(5)] public float PeakHeat;
        [ProtoMember(6)] public bool Critical;
        [ProtoMember(7), System.ComponentModel.DefaultValue(CoreHazards.CriticalDurationSeconds)]
        public float Fuse = CoreHazards.CriticalDurationSeconds;
        [ProtoMember(8)] public float Decay = 20;
        [ProtoMember(9)] public Vector3D Position;
        [ProtoMember(10)] public Vector3 Velocity;
        // Missing in legacy saves, where Fuse stored heat-weighted units.
        [ProtoMember(11)] public int FuseVersion;
        [ProtoMember(12)] public Quaternion Rotation = Quaternion.Identity;
        [ProtoMember(13)] public Vector3 Spin;
        [ProtoMember(14)] public List<CoreShellPart> Shell;
    }

    // The hazard is world state, independent of the disposable physics carrier.
    // Grinding, cleanup, reactor destruction and world reload cannot disarm it.
    [MySessionComponentDescriptor(MyUpdateOrder.BeforeSimulation)]
    public sealed class CoreHazards : MySessionComponentBase
    {
        internal const float SupercriticalHeat = 1.25f;
        internal const float CriticalDurationSeconds = 60;
        private const string SaveFile = "ArcanePower-CoreHazards.xml";
        private const ushort Channel = 49372;
        private static CoreHazards instance;
        private List<CoreHazard> cores = new List<CoreHazard>();
        private readonly Dictionary<long, MyLight> lights = new Dictionary<long, MyLight>();
        private readonly Dictionary<long, MyEntity3DSoundEmitter> coreSounds = new Dictionary<long, MyEntity3DSoundEmitter>();
        private readonly Dictionary<long, CoreShellVisuals> shells = new Dictionary<long, CoreShellVisuals>();
        private readonly List<long> unusedLights = new List<long>();
        private readonly List<long> unusedShells = new List<long>();
        private int tick;
        private bool ready;

        public override void BeforeStart()
        {
            instance = this;
            if (MyAPIGateway.Multiplayer.IsServer && MyAPIGateway.Utilities.FileExistsInWorldStorage(SaveFile, typeof(CoreHazards)))
            {
                // Fail visibly if persistent hazards cannot be read; never silently
                // replace a corrupted hazard ledger with an empty, defused world.
                using (var reader = MyAPIGateway.Utilities.ReadFileInWorldStorage(SaveFile, typeof(CoreHazards)))
                    cores = MyAPIGateway.Utilities.SerializeFromXML<List<CoreHazard>>(reader.ReadToEnd()) ?? new List<CoreHazard>();
            }
            MyAPIGateway.Multiplayer.RegisterSecureMessageHandler(Channel, Receive);
            ready = true;
            if (!MyAPIGateway.Multiplayer.IsServer) MyAPIGateway.Multiplayer.SendMessageToServer(Channel, new byte[] { 0 });
        }

        internal static CoreHazard Inside(long sourceId)
        {
            return instance == null ? null : instance.cores.Find(c => c.SourceId == sourceId && c.CarrierId == 0);
        }

        internal static CoreHazard Arm(long sourceId, int tier, float heat, Vector3D position, Vector3 velocity)
        {
            if (instance == null) return null;
            var core = Inside(sourceId);
            if (core == null)
            {
                core = new CoreHazard { SourceId = sourceId, Tier = tier, Critical = true, FuseVersion = 1 };
                instance.cores.Add(core);
            }
            core.Heat = heat;
            core.PeakHeat = Math.Max(core.PeakHeat, heat);
            core.Position = position;
            core.Velocity = velocity;
            return core;
        }

        internal static bool Release(long sourceId, int tier, float heat, MatrixD world, Vector3 velocity, Vector3 spin,
            List<CoreShellPart> shell = null)
        {
            if (instance == null) return false;
            var core = Inside(sourceId);
            bool added = core == null;
            if (added)
                core = new CoreHazard { SourceId = sourceId, Tier = tier, Heat = heat, PeakHeat = heat,
                    Critical = heat >= SupercriticalHeat, FuseVersion = 1 };
            if (!CreateCarrier(core, world, velocity, spin)) return false;
            core.Shell = shell;
            if (added) instance.cores.Add(core);
            instance.Broadcast();
            return true;
        }

        private static bool CreateCarrier(CoreHazard core, MatrixD world, Vector3 velocity, Vector3 spin)
        {
            var builder = new MyObjectBuilder_CubeGrid
            {
                GridSizeEnum = MyCubeSize.Small, IsStatic = false, CreatePhysics = true,
                DestructibleBlocks = !core.Critical, Editable = !core.Critical,
                PositionAndOrientation = new MyPositionAndOrientation(world),
                LinearVelocity = velocity, AngularVelocity = spin,
                DisplayName = "Ejected Arcane Core",
                PersistentFlags = MyPersistentEntityFlags2.Enabled | MyPersistentEntityFlags2.InScene
            };
            builder.CubeBlocks.Add(new MyObjectBuilder_CubeBlock
            {
                SubtypeName = "ArcanePower_EjectedCore", Min = new Vector3I(-1),
                BuildPercent = 1, IntegrityPercent = 1
            });
            var carrier = MyAPIGateway.Entities.CreateFromObjectBuilderAndAdd(builder) as IMyCubeGrid;
            if (carrier == null || carrier.Physics == null)
            {
                if (carrier != null) carrier.Close();
                MyLog.Default.WriteLine("ArcanePower: physical core creation failed; retaining the hazard for retry.");
                return false;
            }
            // Apply the handoff momentum to the ready body, including the
            // outlet impulse. Do not rely only on object-builder initialization.
            carrier.Physics.LinearVelocity = velocity;
            carrier.Physics.AngularVelocity = spin;
            core.CarrierId = carrier.EntityId;
            core.Position = world.Translation;
            core.Velocity = velocity;
            core.Rotation = Quaternion.CreateFromRotationMatrix((Matrix)world);
            core.Spin = spin;
            MyLog.Default.WriteLine("ArcanePower: physical core source=" + core.SourceId + " carrier=" + core.CarrierId
                + " critical=" + core.Critical + " fuse=" + Seconds(core) + " position=" + core.Position);
            return true;
        }

        private static void RestoreCarrier(CoreHazard core)
        {
            MatrixD world = MatrixD.CreateFromQuaternion(core.Rotation);
            world.Translation = core.Position;
            CreateCarrier(core, world, core.Velocity, core.Spin);
        }

        internal static float Seconds(CoreHazard core)
        {
            return Math.Max(0, core.FuseVersion == 0
                ? core.Fuse / (1 + 4 * Math.Max(0, core.PeakHeat - SupercriticalHeat)) : core.Fuse);
        }

        internal static void AdvanceFuse(CoreHazard core)
        {
            // Convert an old armed fuse once, preserving its remaining seconds.
            // Further heating, ejection and reload never reset or accelerate it.
            core.Fuse = Math.Max(0, Seconds(core) - 1f / 60);
            core.FuseVersion = 1;
        }

        public override void UpdateBeforeSimulation()
        {
            if (!ready) return;
            tick++;
            if (MyAPIGateway.Multiplayer.IsServer)
            {
                for (int i = cores.Count - 1; i >= 0; i--)
                {
                    CoreHazard core = cores[i];
                    IMyEntity carrier = null;
                    if (core.CarrierId != 0)
                    {
                        MyAPIGateway.Entities.TryGetEntityById(core.CarrierId, out carrier);
                        if (carrier != null && !carrier.Closed && !carrier.MarkedForClose)
                        {
                            // Also protect carriers restored from older, destructible saves.
                            var grid = carrier as MyCubeGrid;
                            if (core.Critical && grid != null)
                            { grid.DestructibleBlocks = false; grid.Editable = false; }
                            MatrixD world = carrier.WorldMatrix;
                            core.Position = world.Translation;
                            core.Rotation = Quaternion.CreateFromRotationMatrix((Matrix)world);
                            if (carrier.Physics != null)
                            {
                                core.Velocity = carrier.Physics.LinearVelocity;
                                core.Spin = carrier.Physics.AngularVelocity;
                                float interference;
                                MyAPIGateway.Physics.CalculateNaturalGravityAt(core.Position, out interference);
                                Vector3 artificial = MyAPIGateway.Physics.CalculateArtificialGravityAt(core.Position, interference);
                                carrier.Physics.AddForce(MyPhysicsForceType.APPLY_WORLD_FORCE,
                                    artificial * carrier.Physics.Mass, null, null);
                            }
                        }
                        else if (core.Critical)
                        {
                            // Cleanup or removal must not strand an invisible stationary bomb.
                            RestoreCarrier(core);
                            MyAPIGateway.Entities.TryGetEntityById(core.CarrierId, out carrier);
                        }
                        // Ejection cools an ordinary core, but never lengthens an armed fuse.
                        core.Heat = Math.Max(0, core.Heat - 1f / 600);
                        core.Decay = Math.Max(0, core.Decay - 1f / 60);
                    }
                    else
                    {
                        IMyEntity source;
                        if (MyAPIGateway.Entities.TryGetEntityById(core.SourceId, out source) && !source.Closed)
                        {
                            var reactor = source.GameLogic.GetAs<Reactor>();
                            if (reactor == null || !reactor.TrackCore(core)) RestoreCarrier(core);
                        }
                        else if (core.Critical) RestoreCarrier(core);
                        if (core.CarrierId != 0) MyAPIGateway.Entities.TryGetEntityById(core.CarrierId, out carrier);
                    }
                    if (core.Critical)
                    {
                        core.PeakHeat = Math.Max(core.PeakHeat, core.Heat);
                        AdvanceFuse(core);
                        if (core.Fuse > 0 || !Explode(core)) continue;
                    }
                    else if (core.Decay > 0) continue;
                    if (carrier != null && !carrier.Closed) carrier.Close();
                    cores.RemoveAt(i);
                }
                if (tick % 60 == 0) Broadcast();
            }
            if (!MyAPIGateway.Utilities.IsDedicated) DrawCores();
        }

        private static bool Explode(CoreHazard core)
        {
            // Damage scales directly; radius scales with the cube root. Read the
            // large warhead baseline from this world's loaded SE definitions.
            var warhead = Sandbox.Definitions.MyDefinitionManager.Static.GetCubeBlockDefinition(
                new MyDefinitionId(typeof(Sandbox.Common.ObjectBuilders.MyObjectBuilder_Warhead), "LargeWarhead"))
                as Sandbox.Definitions.MyWarheadDefinition;
            float multiplier = core.Tier == 1 ? 5 : core.Tier == 2 ? 20 : 100;
            float damage = (warhead == null ? 15000 : warhead.WarheadExplosionDamage) * multiplier;
            double radius = (warhead == null ? 22.4415 : warhead.ExplosionRadius) * Math.Pow(multiplier, 1.0 / 3);
            var explosion = new MyExplosionInfo(0, damage, new BoundingSphereD(core.Position, radius),
                MyExplosionTypeEnum.CUSTOM, true)
            {
                // OriginEntity excludes its grid under SE's turret friendly-fire
                // setting. A core blast must damage every grid within its radius.
                OriginEntity = 0, Velocity = core.Velocity,
                StrengthImpulse = 1.2f, ObjectsRemoveDelayInMiliseconds = 40,
                CustomSound = new MySoundPair("ArcaneReactorExplosion"),
                CustomEffect = "Explosion_Warhead_50",
                ParticleScale = (float)Math.Pow(multiplier, 1.0 / 3),
                IgnoreFriendlyFireSetting = false
            };
            IMyEntity source;
            if (MyAPIGateway.Entities.TryGetEntityById(core.SourceId, out source)) explosion.OwnerEntity = source as MyEntity;
            // Retry if SE declines the explosion (for example world damage permissions). A failed enqueue
            // must not erase a live critical core from the persistent ledger.
            if (!MyExplosions.AddExplosion(ref explosion)) return false;
            if (core.CarrierId == 0 && source != null && !source.Closed)
            {
                var reactor = source.GameLogic.GetAs<Reactor>();
                if (reactor != null) reactor.CoreDetonated();
            }
            MyLog.Default.WriteLine("ArcanePower: tier " + core.Tier + " core source=" + core.SourceId
                + " carrier=" + core.CarrierId + " detonated at " + core.Position
                + ", damage=" + damage + ", radius=" + radius);
            return true;
        }

        internal static float EjectedCountdown(long sourceId, out int count)
        {
            count = 0;
            float earliest = CriticalDurationSeconds;
            if (instance == null) return earliest;
            foreach (var core in instance.cores)
                if (core.SourceId == sourceId && core.CarrierId != 0 && core.Critical)
                { count++; earliest = Math.Min(earliest, Seconds(core)); }
            return earliest;
        }

        private void DrawCores()
        {
            unusedLights.Clear();
            unusedLights.AddRange(lights.Keys);
            unusedShells.Clear();
            unusedShells.AddRange(shells.Keys);
            foreach (var core in cores)
            {
                if (core.CarrierId == 0) continue;
                IMyEntity entity;
                if (!MyAPIGateway.Entities.TryGetEntityById(core.CarrierId, out entity) || entity.Closed) continue;
                var grid = entity as IMyCubeGrid;
                var block = grid == null ? null : grid.GetCubeBlock(Vector3I.Zero);
                var model = block == null ? null : block.FatBlock as MyEntity;
                if (model == null) continue;
                if (core.Shell != null && core.Shell.Count > 0)
                {
                    CoreShellVisuals shell;
                    if (!shells.TryGetValue(core.CarrierId, out shell))
                    { shell = new CoreShellVisuals(model, core.Shell); shells.Add(core.CarrierId, shell); }
                    unusedShells.Remove(core.CarrierId);
                    shell.Update();
                }
                Color color = Reactor.FuelColors[core.Tier - 1];
                float fade = core.Critical ? 1 : MathHelper.Clamp(core.Decay / 5, 0, 1);
                model.SetEmissiveParts("ArcanePlasma", color, 0);
                MyLight light;
                if (!lights.TryGetValue(core.CarrierId, out light))
                {
                    light = MyLights.AddLight();
                    if (light == null) continue;
                    light.Start("Ejected Arcane plasma"); light.Range = 6; light.Falloff = 2;
                    light.CastShadows = false; light.GlareOn = false;
                    lights.Add(core.CarrierId, light);
                }
                unusedLights.Remove(core.CarrierId);
                light.LightOn = true; light.Position = entity.WorldMatrix.Translation;
                light.Color = color; light.Intensity = 3 * fade; light.UpdateLight();
                var camera = MyAPIGateway.Session.Camera;
                MyEntity3DSoundEmitter sound;
                bool audible = camera != null && Vector3D.DistanceSquared(camera.Position, entity.WorldMatrix.Translation) < 160 * 160;
                if (audible)
                {
                    if (!coreSounds.TryGetValue(core.CarrierId, out sound))
                    {
                        sound = new MyEntity3DSoundEmitter((MyEntity)entity);
                        sound.CustomVolume = (core.Critical ? .6f : .35f) * fade;
                        sound.PlaySound(new MySoundPair(core.Critical ? "ArcaneReactorInstability" : "ArcaneReactorResonance"));
                        coreSounds.Add(core.CarrierId, sound);
                    }
                    sound.CustomVolume = (core.Critical ? .6f : .35f) * fade;
                    if (tick % 10 == 0) sound.Update();
                }
                else if (coreSounds.TryGetValue(core.CarrierId, out sound))
                {
                    sound.StopSound(true);
                    coreSounds.Remove(core.CarrierId);
                }
            }
            foreach (long id in unusedLights)
            {
                MyLights.RemoveLight(lights[id]); lights.Remove(id);
                MyEntity3DSoundEmitter sound;
                if (coreSounds.TryGetValue(id, out sound)) { sound.StopSound(true); coreSounds.Remove(id); }
            }
            foreach (long id in unusedShells) { shells[id].Close(); shells.Remove(id); }
        }

        private void Broadcast()
        {
            MyAPIGateway.Multiplayer.SendMessageToOthers(Channel, MyAPIGateway.Utilities.SerializeToBinary(cores));
        }

        private void Receive(ushort channel, byte[] bytes, ulong sender, bool fromServer)
        {
            if (!ready || bytes == null || bytes.Length == 0) return;
            if (MyAPIGateway.Multiplayer.IsServer)
            {
                if (!fromServer && bytes.Length == 1 && bytes[0] == 0)
                    MyAPIGateway.Multiplayer.SendMessageTo(Channel, MyAPIGateway.Utilities.SerializeToBinary(cores), sender);
                return;
            }
            if (!fromServer) return;
            try
            {
                var snapshot = MyAPIGateway.Utilities.SerializeFromBinary<List<CoreHazard>>(bytes);
                if (snapshot != null) MyAPIGateway.Utilities.InvokeOnGameThread(() => { if (ready) cores = snapshot; });
            }
            catch (Exception e) { MyLog.Default.WriteLine("ArcanePower: invalid core snapshot: " + e.Message); }
        }

        public override void SaveData()
        {
            if (!ready || !MyAPIGateway.Multiplayer.IsServer) return;
            using (var writer = MyAPIGateway.Utilities.WriteFileInWorldStorage(SaveFile, typeof(CoreHazards)))
                writer.Write(MyAPIGateway.Utilities.SerializeToXML(cores));
        }

        protected override void UnloadData()
        {
            if (ready) MyAPIGateway.Multiplayer.UnregisterSecureMessageHandler(Channel, Receive);
            foreach (var light in lights.Values) MyLights.RemoveLight(light);
            foreach (var sound in coreSounds.Values) sound.StopSound(true);
            foreach (var shell in shells.Values) shell.Close();
            shells.Clear();
            coreSounds.Clear();
            lights.Clear(); cores.Clear(); ready = false; instance = null;
        }
    }
}
