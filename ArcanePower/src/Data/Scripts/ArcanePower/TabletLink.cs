using Sandbox.Game.Entities;
using System.Collections.Generic;
using VRage.Game.ModAPI;

using Sandbox.ModAPI;

namespace ArcanePower
{
    internal static class TabletLink
    {
        // Use the game's bidirectional antenna graph, including relay permissions.
        // Proximity to a reactor alone never grants a connection.
        internal static bool CanRead(Reactor reactor, out string reason)
        {
            reason = "No reactor linked";
            var player = MyAPIGateway.Session.Player;
            var character = player == null ? null : player.Character;
            if (character == null || character.IsDead) { reason = "Suit unavailable"; return false; }
            // SE injects VRage.Game.ModAPI.Interfaces into mod sources. Both
            // namespaces contain this name; only the game interface has broadcast state.
            var controllable = character as Sandbox.Game.Entities.IMyControllableEntity;
            if (controllable == null || !controllable.EnabledBroadcasting)
            { reason = "Switch your suit antenna on"; return false; }
            if (reactor == null || reactor.Block.Closed) return false;
            if (!reactor.Block.HasPlayerAccess(player.IdentityId))
            { reason = "Reactor access denied"; return false; }
            var receiver = character.Components.Get<MyDataReceiver>();
            if (receiver == null || !receiver.Enabled) { reason = "Suit antenna unavailable"; return false; }
            var reachable = new HashSet<MyDataBroadcaster>();
            var pending = new Queue<MyDataReceiver>();
            pending.Enqueue(receiver);
            while (pending.Count > 0)
            {
                var current = pending.Dequeue();
                foreach (var next in current.BroadcastersInRange)
                {
                    if (next.Closed || next.Receiver == null || !next.Receiver.Enabled || current.Broadcaster == null
                        || !next.Receiver.BroadcastersInRange.Contains(current.Broadcaster)
                        || !next.CanBeUsedByPlayer(player.IdentityId) || !reachable.Add(next)) continue;
                    pending.Enqueue(next.Receiver);
                }
            }
            var grids=new List<IMyCubeGrid>();
            MyAPIGateway.GridGroups.GetGroup(reactor.Block.CubeGrid, GridLinkTypeEnum.Logical, grids);
            foreach (var broadcaster in reachable)
            {
                var antenna = broadcaster.Entity as IMyTerminalBlock;
                if (antenna == null || !(antenna is IMyRadioAntenna || antenna is IMyLaserAntenna)) continue;
                if (antenna.IsWorking && antenna.HasPlayerAccess(player.IdentityId)
                    && (antenna.CubeGrid==reactor.Block.CubeGrid || grids.Contains(antenna.CubeGrid)) && broadcaster.CanBeUsedByPlayer(player.IdentityId))
                { reason = "Antenna link online"; return true; }
            }
            reason = "No accessible antenna link / out of range";
            return false;
        }
    }
}
