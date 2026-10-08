using System.Collections.Generic;
using Sandbox.ModAPI;
using VRage.Game.ModAPI;

namespace ShipCoreFramework
{
    public partial class Session
    {
        private static void OnNexusEnabled()
        {
            if (_startedNexus) return;
            if (!IsServer || !_serverRuntimeDataLoaded) return;
            _startedNexus = true;
            LimitsNexusSync.Start(_myNexusApi);
            LimitsNexusSync.BroadcastSnapshot();
        }
        internal static void BroadcastConfigToClients()
        {
            if (!IsServer || !MpActive)
                return;

            ConfigRevision++;
            var players = new List<IMyPlayer>();
            MyAPIGateway.Players.GetPlayers(players);
            var localSteamId = LocalPlayer?.SteamUserId ?? 0UL;
            foreach (var p in players)
            {
                if (p == null || p.SteamUserId == 0 || p.SteamUserId == localSteamId) continue;
                SendConfigTo(p.SteamUserId);
            }
        }

        internal static void SendConfigTo(ulong steamId)
        {
            if (!IsServer || steamId == 0 || Networking == null) return;
            if (Config != null && Config.SelectedNoCore != null && !RuntimeInitialized) return;

            string error = null;
            string xml = null;
            if (Config == null)
                error = "Server configuration is not available.";
            else if (Config.SelectedNoCore == null)
                error = Config.GetNoCoreConfigurationError();
            else
            {
                try
                {
                    xml = MyAPIGateway.Utilities.SerializeToXML(Config);
                    if (string.IsNullOrWhiteSpace(xml))
                        error = "Server configuration serialization produced an empty payload.";
                    else if (xml.Length > PacketSendConfig.MaxConfigCharacters)
                    {
                        error = "Server configuration exceeds the synchronization size limit.";
                        xml = null;
                    }
                }
                catch (System.Exception exception)
                {
                    error = "Server configuration serialization failed: " + exception.Message;
                    Utils.Log(error, 1, "Config Sync");
                }
            }

            if (error != null && error.Length > 512)
                error = error.Substring(0, 512);

            var packet = new PacketSendConfig(xml, ConfigRevision, error);
            if (Networking.SendToPlayer(packet, steamId)) return;

            var fallback = new PacketSendConfig(null, ConfigRevision,
                "Server could not send the configuration payload because it was oversized or rejected by the transport.");
            Networking.SendToPlayer(fallback, steamId);
        }
    }
}
