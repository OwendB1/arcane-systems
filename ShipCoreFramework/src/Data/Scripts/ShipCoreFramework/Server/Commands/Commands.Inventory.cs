using System;
using System.Collections.Generic;
using Sandbox.ModAPI;
using VRage.Game.ModAPI;

namespace ShipCoreFramework
{
    internal static partial class Commands
    {
        private static void Inventory(long playerId, string[] args)
        {
            var recipientSteamId = MyAPIGateway.Players.TryGetSteamId(playerId);
            if (recipientSteamId == 0) return;

            var body ="";
            var bodySort = new Dictionary<string, string>();
            if (args.Length < 3 || !CheckIfAdmin(playerId))
            {
                var playerVal = PerPlayerManager.GetPlayerCountsSnapshot(playerId);
                if(playerVal.Count > 0)
                {
                    foreach (var classCount in playerVal)
                    {
                        var max = Session.GetEffectivePlayerCoreLimit(Session.Config.GetShipCoreByTypeId(classCount.Key));
                        bodySort[classCount.Key]=$"> {classCount.Key}:\n";
                        if(max != -1 && classCount.Value>0)
                        {
                            bodySort[classCount.Key]+=$"            > Per Player:{classCount.Value}/{max}\n";
                        }
                    }
                }

                var faction = MyAPIGateway.Session.Factions.TryGetPlayerFaction(playerId);
                var factionId = faction?.FactionId ?? -1;
                var factionVal = factionId != -1
                    ? PerFactionManager.GetFactionCountsSnapshot(factionId)
                    : new Dictionary<string, int>();
                if(factionVal.Count > 0)
                {
                    foreach (var classCount in factionVal)
                    {
                        var core = Session.Config.GetShipCoreByTypeId(classCount.Key);
                        var max = PerFactionManager.GetEffectiveFactionCoreLimit(core, PerFactionManager.GetFactionPlayerCount(faction, playerId));
                        if(max != -1 && classCount.Value>0)
                        {
                            if (!bodySort.ContainsKey(classCount.Key))
                                bodySort[classCount.Key] = $"> {classCount.Key}:\n";

                            bodySort[classCount.Key]+=$"            > Per Faction:{FormatServerFactionLimit(core, faction, playerId, classCount.Value)}\n";
                        }
                    }
                }
                body = string.Join("", bodySort.Values);
            }
            else
            {
                var sub = args[1].ToLower();
                switch (sub)
                {
                    case "faction":
                        goto case "f";
                    case "f":
                        if (!long.TryParse(args[2], out playerId)) return;
                        var faction = MyAPIGateway.Session.Factions.TryGetPlayerFaction(playerId);
                        var factionId = faction?.FactionId ?? -1;
                        var factionVal = factionId != -1
                            ? PerFactionManager.GetFactionCountsSnapshot(factionId)
                            : new Dictionary<string, int>();
                        if(factionVal.Count > 0)
                        {
                            foreach (var classCount in factionVal)
                            {
                                var core = Session.Config.GetShipCoreByTypeId(classCount.Key);
                                var max = PerFactionManager.GetEffectiveFactionCoreLimit(core, PerFactionManager.GetFactionPlayerCount(faction, playerId));
                                if(max != -1)
                                {
                                    bodySort[classCount.Key]=$"            > Per Faction:{FormatServerFactionLimit(core, faction, playerId, classCount.Value)}\n";
                                }
                            }
                        }
                        break;
                    case "player":
                        goto case "p";
                    case "p":
                        if (!long.TryParse(args[2], out playerId)) return;
                        var playerVal = PerPlayerManager.GetPlayerCountsSnapshot(playerId);
                        if(playerVal.Count > 0)
                        {
                            foreach (var classCount in playerVal)
                            {
                                var max = Session.GetEffectivePlayerCoreLimit(Session.Config.GetShipCoreByTypeId(classCount.Key));
                                bodySort[classCount.Key]=$"> {classCount.Key}:\n";
                                if(max != -1)
                                {
                                    bodySort[classCount.Key]+=$"            > Per Player:{classCount.Value}/{max}\n";
                                }
                            }
                        }
                        break;
                }
            }
            //{
                //PerFactionManager.
            //}
            //else
            //{
            //}
            Session.Networking.SendToPlayer(new PacketMissionScreen(
                "Ship Core Framework",
                $"Inventory - {playerId}\n",
                "Core Counts",
                body,
                ServerConsent()
            ), recipientSteamId);
        }
        private static string ServerConsent()
        {
            string[] options = {"Cool Beans","I Understand","I Understand","OK","OK","OK","OK","OK","OK","OK","OK","OK","OK","OK","I Don't like reading","It's MoMo's fault","Sussy Baka"};
            var rng = new Random();
            return options[rng.Next(options.Length)];
        }
        private static string FormatServerFactionLimit(ShipCore core, IMyFaction faction, long ownerId, int currentCount)
        {
            var playerCount = PerFactionManager.GetFactionPlayerCount(faction, ownerId);
            var max = PerFactionManager.GetEffectiveFactionCoreLimit(core, playerCount);
            if (max < 0)
                return currentCount.ToString();

            if (core != null && core.FactionPlayersNeededPerCore > 0)
            {
                string floor = core.MinPerFaction > 0 ? $", minimum allowance {core.MinPerFaction}" : string.Empty;
                return $"{currentCount}/{max} (1 per {core.FactionPlayersNeededPerCore} players{floor}, faction size {playerCount})";
            }

            return $"{currentCount}/{max}";
        }
    }
}
