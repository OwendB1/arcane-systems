using System;
using System.Collections.Generic;
using Sandbox.ModAPI;
using VRage.Game.Components;
using VRage.Game.ModAPI;
using VRage.ModAPI;
using VRage.Utils;
using VRageMath;

namespace ArcanePower
{
    // One transport owner for the mod's channels. All access is on the game thread.
    [MySessionComponentDescriptor(MyUpdateOrder.NoUpdate)]
    public sealed class PowerNetwork : MySessionComponentBase
    {
        internal const int MaxPacketBytes = 65536;
        private static readonly List<IMyPlayer> players = new List<IMyPlayer>();
        private static readonly Dictionary<ushort, Dictionary<ulong, RequestBudget>> requests = new Dictionary<ushort, Dictionary<ulong, RequestBudget>>();
        private static int playersAt = -1;
        private sealed class RequestBudget
        {
            internal int Window, Count;
            internal readonly Dictionary<long, int> Targets = new Dictionary<long, int>();
        }

        internal static List<IMyPlayer> RemotePlayers
        {
            get
            {
                int frame = MyAPIGateway.Session.GameplayFrameCounter;
                if (frame != playersAt)
                {
                    playersAt = frame;
                    players.Clear();
                    MyAPIGateway.Players.GetPlayers(players, p => p.SteamUserId != 0
                        && (MyAPIGateway.Session.Player == null || p.SteamUserId != MyAPIGateway.Session.Player.SteamUserId));
                    if (frame % 120 == 0)
                        foreach (var peers in requests.Values)
                            foreach (var id in new List<ulong>(peers.Keys))
                                if (!players.Exists(p => p.SteamUserId == id)) peers.Remove(id);
                }
                return players;
            }
        }

        internal static bool CanObserve(ulong steamId, IMyEntity entity)
        { return entity != null && !entity.Closed && CanObserve(steamId, entity.GetPosition()); }

        internal static bool CanObserve(ulong steamId, Vector3D position)
        {
            double range = MyAPIGateway.Session.SessionSettings.SyncDistance;
            if (range <= 0) range = 3000;
            foreach (var player in RemotePlayers)
                if (player.SteamUserId == steamId) return Vector3D.DistanceSquared(player.GetPosition(), position) <= range * range;
            return false;
        }

        internal static bool CanRequest(ushort channel, ulong sender, long target, IMyEntity entity = null, bool command = false)
        {
            bool present = false;
            foreach (var player in RemotePlayers) if (player.SteamUserId == sender) { present = true; break; }
            if (!present || (entity != null && !CanObserve(sender, entity))) return false;
            Dictionary<ulong, RequestBudget> peers;
            if (!requests.TryGetValue(channel, out peers)) requests[channel] = peers = new Dictionary<ulong, RequestBudget>();
            RequestBudget budget;
            if (!peers.TryGetValue(sender, out budget)) peers[sender] = budget = new RequestBudget();
            int now = MyAPIGateway.Session.GameplayFrameCounter, previous;
            if (now - budget.Window >= 120)
            { budget.Window = now; budget.Count = 0; budget.Targets.Clear(); }
            if (budget.Count >= (command ? 256 : 64) || (!command && budget.Targets.TryGetValue(target, out previous) && now - previous < 120)) return false;
            budget.Count++; budget.Targets[target] = now;
            return true;
        }

        internal static void OnGameThread(Action action)
        {
            MyAPIGateway.Utilities.InvokeOnGameThread(() => {
                try { action(); }
                catch (Exception error) { MyLog.Default.WriteLine("ArcanePower: packet handling failed: " + error.Message); }
            });
        }

        internal static bool Send<T>(ushort channel, T packet, ulong recipient)
        {
            try
            {
                var bytes = MyAPIGateway.Utilities.SerializeToBinary(packet);
                if (bytes == null || bytes.Length == 0 || bytes.Length > MaxPacketBytes)
                { MyLog.Default.WriteLine("ArcanePower: rejected empty/oversized packet on " + channel); return false; }
                bool sent = MyAPIGateway.Multiplayer.IsServer
                    ? MyAPIGateway.Multiplayer.SendMessageTo(channel, bytes, recipient)
                    : MyAPIGateway.Multiplayer.SendMessageToServer(channel, bytes);
                if (!sent) MyLog.Default.WriteLine("ArcanePower: send failed on " + channel);
                return sent;
            }
            catch (Exception error) { MyLog.Default.WriteLine("ArcanePower: send failed on " + channel + ": " + error.Message); return false; }
        }

        internal static void Broadcast<T>(ushort channel, T packet, IMyEntity entity)
        {
            if (!MyAPIGateway.Multiplayer.IsServer) return;
            byte[] bytes = null;
            foreach (var player in RemotePlayers)
            {
                if (!CanObserve(player.SteamUserId, entity)) continue;
                if (bytes == null)
                {
                    try { bytes = MyAPIGateway.Utilities.SerializeToBinary(packet); }
                    catch (Exception error) { MyLog.Default.WriteLine("ArcanePower: serialization failed: " + error.Message); return; }
                    if (bytes == null || bytes.Length == 0 || bytes.Length > MaxPacketBytes)
                    { MyLog.Default.WriteLine("ArcanePower: rejected empty/oversized packet on " + channel); return; }
                }
                try
                {
                    if (!MyAPIGateway.Multiplayer.SendMessageTo(channel, bytes, player.SteamUserId))
                        MyLog.Default.WriteLine("ArcanePower: send failed on " + channel);
                }
                catch (Exception error) { MyLog.Default.WriteLine("ArcanePower: send failed on " + channel + ": " + error.Message); }
            }
        }

        protected override void UnloadData() { players.Clear(); requests.Clear(); playersAt = -1; }
    }
}
