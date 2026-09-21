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
    public sealed class CoreHazard
    {
        [ProtoMember(1)] public long SourceId;
        [ProtoMember(2)] public long CarrierId;
        [ProtoMember(3)] public int Tier;
        [ProtoMember(4)] public float Heat;
        [ProtoMember(5)] public float PeakHeat;
        [ProtoMember(6)] public bool Critical;
        [ProtoMember(7)] public float Fuse = 45;
        [ProtoMember(8)] public float Decay = 20;
        [ProtoMember(9)] public Vector3D Position;
        [ProtoMember(10)] public Vector3 Velocity;
    }

    // The hazard is world state, independent of the disposable physics carrier.
    // Grinding, cleanup, reactor destruction and world reload cannot disarm it.
    [MySessionComponentDescriptor(MyUpdateOrder.BeforeSimulation)]
    public sealed class CoreHazards : MySessionComponentBase
    {
        internal const float SupercriticalHeat = 1.25f;
        private const string SaveFile = "ArcanePower-CoreHazards.xml";
        private const ushort Channel = 49372;
        private static CoreHazards instance;
        private List<CoreHazard> cores = new List<CoreHazard>();
        private readonly Dictionary<long, MyLight> lights = new Dictionary<long, MyLight>();
        private readonly List<long> unusedLights = new List<long>();
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
                core = new CoreHazard { SourceId = sourceId, Tier = tier, Critical = true };
                instance.cores.Add(core);
            }
            core.Heat = heat;
            core.PeakHeat = Math.Max(core.PeakHeat, heat);
            core.Position = position;
            core.Velocity = velocity;
            return core;
        }

        internal static bool Release(long sourceId, int tier, float heat, MatrixD world, Vector3 velocity, Vector3 spin)
        {
            if (instance == null) return false;
            var builder = new MyObjectBuilder_CubeGrid
            {
                GridSizeEnum = MyCubeSize.Small, IsStatic = false, CreatePhysics = true,
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
                MyLog.Default.WriteLine("ArcanePower: physical core creation failed; retaining the vent payload for retry.");
                return false;
            }
            var core = Inside(sourceId);
            if (core == null)
            {
                core = new CoreHazard { SourceId = sourceId, Tier = tier, Heat = heat, PeakHeat = heat,
                    Critical = heat >= SupercriticalHeat };
                instance.cores.Add(core);
            }
            core.CarrierId = carrier.EntityId;
            core.Position = world.Translation;
            core.Velocity = velocity;
            instance.Broadcast();
            return true;
        }

        internal static float Seconds(CoreHazard core)
        {
            return Math.Max(0, core.Fuse / (1 + 4 * Math.Max(0, core.PeakHeat - SupercriticalHeat)));
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
                        if (carrier != null && !carrier.Closed)
                        {
                            core.Position = carrier.WorldMatrix.Translation;
                            if (carrier.Physics != null)
                            {
                                core.Velocity = carrier.Physics.LinearVelocity;
                                float interference;
                                MyAPIGateway.Physics.CalculateNaturalGravityAt(core.Position, out interference);
                                Vector3 artificial = MyAPIGateway.Physics.CalculateArtificialGravityAt(core.Position, interference);
                                carrier.Physics.AddForce(MyPhysicsForceType.APPLY_WORLD_FORCE,
                                    artificial * carrier.Physics.Mass, null, null);
                            }
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
                            if (reactor != null) reactor.TrackCore(core);
                        }
                        // If the housing disappears, keep the last known blast position.
                    }
                    if (core.Critical)
                    {
                        core.PeakHeat = Math.Max(core.PeakHeat, core.Heat);
                        core.Fuse = Math.Max(0, core.Fuse - (1 + 4 * Math.Max(0, core.PeakHeat - SupercriticalHeat)) / 60f);
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
                MyExplosionTypeEnum.WARHEAD_EXPLOSION_50, true)
            {
                OriginEntity = core.SourceId, Velocity = core.Velocity,
                StrengthImpulse = 1.2f, ObjectsRemoveDelayInMiliseconds = 40,
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
            MyLog.Default.WriteLine("ArcanePower: tier " + core.Tier + " core detonated at " + core.Position
                + ", damage=" + damage + ", radius=" + radius);
            return true;
        }

        internal static float EjectedCountdown(long sourceId, out int count)
        {
            count = 0;
            float earliest = 45;
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
            foreach (var core in cores)
            {
                if (core.CarrierId == 0) continue;
                IMyEntity entity;
                if (!MyAPIGateway.Entities.TryGetEntityById(core.CarrierId, out entity) || entity.Closed) continue;
                var grid = entity as IMyCubeGrid;
                var block = grid == null ? null : grid.GetCubeBlock(Vector3I.Zero);
                var model = block == null ? null : block.FatBlock as MyEntity;
                if (model == null) continue;
                Color color = Reactor.FuelColors[core.Tier - 1];
                float fade = core.Critical ? 1 : MathHelper.Clamp(core.Decay / 5, 0, 1);
                float flicker = .9f + .1f * (float)Math.Sin(tick * .13);
                model.SetEmissiveParts("ArcanePlasma", color, 18 * fade * flicker);
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
                light.Color = color; light.Intensity = 3 * fade * flicker; light.UpdateLight();
            }
            foreach (long id in unusedLights) { MyLights.RemoveLight(lights[id]); lights.Remove(id); }
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
            lights.Clear(); cores.Clear(); ready = false; instance = null;
        }
    }
}
