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
        private static readonly Dictionary<ulong, Dictionary<long, Observation>> observations = new Dictionary<ulong, Dictionary<long, Observation>>();
        private static int playersAt = -1, cleanedAt = -1;
        private sealed class RequestBudget
        {
            internal int Window, Count, Commands;
            internal readonly Dictionary<long, int> Targets = new Dictionary<long, int>();
        }
        private sealed class Observation
        {
            internal IMyTerminalBlock Anchor;
            internal int Expires;
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
                    if (cleanedAt < 0 || frame - cleanedAt >= 120)
                    {
                        cleanedAt = frame;
                        foreach (var peers in requests.Values)
                            foreach (var id in new List<ulong>(peers.Keys))
                                if (!players.Exists(p => p.SteamUserId == id)) peers.Remove(id);
                        foreach (var id in new List<ulong>(observations.Keys))
                        {
                            var grids = observations[id];
                            foreach (var grid in new List<long>(grids.Keys))
                                if (frame >= grids[grid].Expires || grids[grid].Anchor.Closed) grids.Remove(grid);
                            if (grids.Count == 0 || !players.Exists(p => p.SteamUserId == id)) observations.Remove(id);
                        }
                    }
                }
                return players;
            }
        }

        internal static bool CanObserve(ulong steamId, IMyEntity entity)
        {
            if (entity == null || entity.Closed) return false;
            if (CanObserve(steamId, entity.GetPosition())) return true;
            var block = entity as IMyCubeBlock;
            Dictionary<long, Observation> grids;
            Observation observation;
            if (block == null || block.CubeGrid == null || !observations.TryGetValue(steamId, out grids)
                || !grids.TryGetValue(block.CubeGrid.EntityId, out observation)
                || MyAPIGateway.Session.GameplayFrameCounter >= observation.Expires
                || observation.Anchor.Closed || observation.Anchor.CubeGrid != block.CubeGrid) return false;
            long identity = MyAPIGateway.Players.TryGetIdentityId(steamId);
            var terminal = entity as IMyTerminalBlock;
            return identity != 0 && observation.Anchor.HasPlayerAccess(identity)
                && (terminal == null || terminal.HasPlayerAccess(identity));
        }

        // Vanilla can explicitly replicate remote antenna terminals outside
        // SyncDistance. A loaded client's sync request renews that grid's interest;
        // access is checked again on every distant broadcast and leases expire.
        internal static bool Observe(ulong steamId, IMyEntity entity)
        {
            if (entity == null || entity.Closed) return false;
            var terminal = entity as IMyTerminalBlock;
            long identity = MyAPIGateway.Players.TryGetIdentityId(steamId);
            if (terminal == null || terminal.CubeGrid == null || identity == 0 || !terminal.HasPlayerAccess(identity))
                return CanObserve(steamId, entity.GetPosition());
            Dictionary<long, Observation> grids;
            if (!observations.TryGetValue(steamId, out grids)) observations[steamId] = grids = new Dictionary<long, Observation>();
            grids[terminal.CubeGrid.EntityId] = new Observation { Anchor = terminal,
                Expires = MyAPIGateway.Session.GameplayFrameCounter + 600 };
            return true;
        }

        internal static bool NeedsRemoteRefresh(IMyEntity entity)
        {
            var player = MyAPIGateway.Session.Player;
            return !MyAPIGateway.Multiplayer.IsServer && player != null && entity != null && !entity.Closed
                && !InRange(player.GetPosition(), entity.GetPosition());
        }

        private static bool InRange(Vector3D viewer, Vector3D position)
        {
            double range = MyAPIGateway.Session.SessionSettings.SyncDistance;
            if (range <= 0) range = 3000;
            return Vector3D.DistanceSquared(viewer, position) <= range * range;
        }

        internal static bool CanObserve(ulong steamId, Vector3D position)
        {
            foreach (var player in RemotePlayers)
                if (player.SteamUserId == steamId) return InRange(player.GetPosition(), position);
            return false;
        }

        internal static bool CanRequest(ushort channel, ulong sender, long target, bool command = false)
        {
            bool present = false;
            foreach (var player in RemotePlayers) if (player.SteamUserId == sender) { present = true; break; }
            if (!present) return false;
            Dictionary<ulong, RequestBudget> peers;
            if (!requests.TryGetValue(channel, out peers)) requests[channel] = peers = new Dictionary<ulong, RequestBudget>();
            RequestBudget budget;
            if (!peers.TryGetValue(sender, out budget)) peers[sender] = budget = new RequestBudget();
            int now = MyAPIGateway.Session.GameplayFrameCounter, previous;
            if (now - budget.Window >= 120)
            { budget.Window = now; budget.Count = budget.Commands = 0; budget.Targets.Clear(); }
            if (command) return ++budget.Commands <= 256;
            if (budget.Count >= 64 || (budget.Targets.TryGetValue(target, out previous) && now - previous < 120)) return false;
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

        protected override void UnloadData() { players.Clear(); requests.Clear(); observations.Clear(); playersAt = cleanedAt = -1; }
    }
}
