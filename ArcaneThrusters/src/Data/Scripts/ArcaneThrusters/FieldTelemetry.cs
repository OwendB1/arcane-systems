using System.Collections.Generic;
using ProtoBuf;
using Sandbox.ModAPI;
using VRage.Game.Components;
using VRage.Game.ModAPI;
using VRage.ModAPI;
using VRageMath;

namespace ArcaneThrusters
{
    [ProtoContract]
    public sealed class FieldReading
    {
        [ProtoMember(1)] public long EntityId;
        [ProtoMember(2)] public string State;
        [ProtoMember(3)] public int HoldSeconds;
        [ProtoMember(4)] public float Demand;
        [ProtoMember(5)] public float Delivered;
        [ProtoMember(6)] public double Recovered;
        [ProtoMember(7)] public double Vented;
        [ProtoMember(8)] public double LitresPerSecond;
        [ProtoMember(9)] public double BurnSeconds;
        [ProtoMember(10)] public double ForceN;
        [ProtoMember(11)] public bool GimbalPose;
        [ProtoMember(12)] public float Pitch;
        [ProtoMember(13)] public float Yaw;
        [ProtoMember(14)] public float CommandPitch;
        [ProtoMember(15)] public float CommandYaw;
        [ProtoMember(16)] public Vector3D WorldForce;
    }

    [MySessionComponentDescriptor(MyUpdateOrder.NoUpdate)]
    public sealed class FieldTelemetry : MySessionComponentBase
    {
        private const ushort Channel = 49762;
        private static readonly List<IMyPlayer> Players = new List<IMyPlayer>();
        private static int playersAt = -1;

        public override void BeforeStart()
        {
            NozzleGimbal.RegisterProperties();
            if (!MyAPIGateway.Multiplayer.IsServer)
                MyAPIGateway.Multiplayer.RegisterSecureMessageHandler(Channel, Receive);
        }

        internal static void Send(IMyTerminalBlock tank, FieldReading reading)
        {
            if (!MyAPIGateway.Multiplayer.MultiplayerActive) return;
            int frame = MyAPIGateway.Session.GameplayFrameCounter;
            if (frame != playersAt)
            {
                playersAt = frame;
                Players.Clear();
                MyAPIGateway.Players.GetPlayers(Players, p => p.SteamUserId != MyAPIGateway.Multiplayer.MyId);
            }
            double range = MyAPIGateway.Session.SessionSettings.SyncDistance;
            byte[] data = null;
            foreach (IMyPlayer player in Players)
            {
                if (Vector3D.DistanceSquared(player.GetPosition(), tank.GetPosition()) > range * range
                    || !tank.HasPlayerAccess(player.IdentityId)) continue;
                if (data == null) data = MyAPIGateway.Utilities.SerializeToBinary(reading);
                MyAPIGateway.Multiplayer.SendMessageTo(Channel, data, player.SteamUserId, false);
            }
        }

        private static void Receive(ushort channel, byte[] data, ulong sender, bool fromServer)
        {
            if (!fromServer || MyAPIGateway.Multiplayer.IsServer || data == null || data.Length > 512) return;
            FieldReading snapshot = MyAPIGateway.Utilities.SerializeFromBinary<FieldReading>(data);
            IMyEntity entity;
            if (snapshot == null || !MyAPIGateway.Entities.TryGetEntityById(snapshot.EntityId, out entity)) return;
            if (snapshot.GimbalPose)
            {
                var gimbal = entity.GameLogic == null ? null : entity.GameLogic.GetAs<NozzleGimbal>();
                if (gimbal != null) gimbal.Receive(snapshot);
                return;
            }
            PlasmaTank tank = entity.GameLogic == null ? null : entity.GameLogic.GetAs<PlasmaTank>();
            if (tank != null) tank.ShowReading(snapshot);
            var charger = entity.GameLogic == null ? null : entity.GameLogic.GetAs<RecoveryCharger>();
            if (charger != null) charger.ShowReading(snapshot);
            var engine = entity.GameLogic == null ? null : entity.GameLogic.GetAs<PlasmaDrive>();
            if (engine != null) engine.ShowReading(snapshot);
            var thermal = entity.GameLogic == null ? null : entity.GameLogic.GetAs<ThermalDrive>();
            if (thermal != null) thermal.ShowReading(snapshot);
        }

        protected override void UnloadData()
        {
            NozzleGimbal.UnregisterProperties();
            if (MyAPIGateway.Multiplayer != null && !MyAPIGateway.Multiplayer.IsServer)
                MyAPIGateway.Multiplayer.UnregisterSecureMessageHandler(Channel, Receive);
            Players.Clear();
            playersAt = -1;
        }
    }
}
