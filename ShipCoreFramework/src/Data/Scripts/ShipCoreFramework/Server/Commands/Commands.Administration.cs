using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using Sandbox.ModAPI;
using VRageMath;

namespace ShipCoreFramework
{
    internal static partial class Commands
    {
        private static string ReloadConfig()
        {
            var loadedConfig = new ModConfig();
            loadedConfig.LoadConfig();
            if (Session.IsServer)
            {
                if (loadedConfig.SelectedNoCore == null)
                {
                    var error = loadedConfig.GetNoCoreConfigurationError();
                    if (!Session.RuntimeInitialized)
                    {
                        Session.Config = loadedConfig;
                        ModAPI.MarkConfigUnavailable(error);
                    }
                    return "Config reload rejected: " + error;
                }

                Session.Config = loadedConfig;
                Session.ApplyServerConfig();
            }
            else
                Session.Config = loadedConfig;
            if (Session.MpActive && !Session.IsServer) Session.Networking.SendToServer(new PacketRequestConfig(), onlyToServer: true);
            return "Config reloaded from disk.";
        }

        private static string CreateNoFlyZone(string[] args)
        {
            if (args.Length < 3)
                return "Usage: /core createnfz <radius> <forceoff:true|false> [GPS:...] [allowedSubtype1 allowedSubtype2 ...]";

            double radius;
            if (!double.TryParse(args[1], NumberStyles.Float, CultureInfo.InvariantCulture, out radius) || radius <= 0d)
                return "Radius must be a positive number.";

            bool forceOff;
            var forceArg = args[2].Trim();
            if (!forceArg.StartsWith("forceoff:", StringComparison.OrdinalIgnoreCase) ||
                !bool.TryParse(forceArg.Substring("forceoff:".Length), out forceOff))
            {
                return "Second argument must be 'forceoff:true' or 'forceoff:false'.";
            }

            Vector3D center;
            if (!Utils.TryParseGpsFromArgs(args.Skip(3).ToArray(), out center))
            {
                var player = MyAPIGateway.Session == null ? null : MyAPIGateway.Session.Player;
                if (player == null) return "Player not found.";
                center = player.GetPosition();
            }

            var allowed = new List<string>();
            foreach (var arg in args.Skip(3))
            {
                if (arg.StartsWith("GPS:", StringComparison.OrdinalIgnoreCase)) continue;
                if (arg.StartsWith("forceoff:", StringComparison.OrdinalIgnoreCase)) continue;
                if (!string.IsNullOrWhiteSpace(arg)) allowed.Add(arg.Trim());
            }

            if (Session.Config.NoFlyZones == null) Session.Config.NoFlyZones = new List<Zones>();

            var nextId = 1;
            if (Session.Config.NoFlyZones.Count > 0)
                nextId = Session.Config.NoFlyZones.Max(z => z.Id) + 1;

            var newZone = new Zones
            {
                Id = nextId,
                Position = center,
                Radius = radius,
                AllowedCoresSubtype = allowed,
                ForceOff = forceOff
            };

            Session.Config.NoFlyZones.Add(newZone);
            Session.Config.SaveConfig();
            return "Created NoFlyZone with ID " + nextId +
                   " at the chosen center (ForceOff=" + forceOff + ").";
        }

        private static string DeleteNoFlyZone(string[] args)
        {
            if (args.Length < 2) return "Usage: /core deletenfz <id>";

            int id;
            if (!int.TryParse(args[1], NumberStyles.Integer, CultureInfo.InvariantCulture, out id))
                return "Invalid id.";

            if (Session.Config.NoFlyZones == null || Session.Config.NoFlyZones.Count == 0)
                return "No NoFlyZones defined.";

            var zone = Session.Config.NoFlyZones.FirstOrDefault(z => z.Id == id);
            if (zone == null) return "NoFlyZone with ID " + id + " not found.";

            Session.Config.NoFlyZones.Remove(zone);
            Session.Config.SaveConfig();
            return "Deleted NoFlyZone ID " + id + ".";
        }

        private static string Debug(string[] args)
        {
            if (args.Length < 2)
            {
                return $"Debug mode is {(Session.Config.DebugMode ? "ON" : "OFF")}";
            }

            var debugVal = args[1].ToLowerInvariant();
            if (debugVal != "on" && debugVal != "off")
            {
                return "Usage: /core debug on|off";
            }

            if (!Session.IsServer)
            {
                return $"Requested world debug mode {(debugVal == "on" ? "ON" : "OFF")} from server.";
            }

            Session.Config.DebugMode = (debugVal == "on");
            Session.Config.SaveConfig(true);
            return $"World debug mode set to {(Session.Config.DebugMode ? "ON" : "OFF")}";
        }

        private static string CombatLog(string[] args)
        {
            if (args.Length < 2)
            {
                return $"Combat logging is {(Session.Config.CombatLogging ? "ON" : "OFF")}";
            }
            var clVal = args[1].ToLower();
            Session.Config.CombatLogging = (clVal == "on");
            Session.Config.SaveConfig(true);
            return $"Combat logging set to {(Session.Config.CombatLogging ? "ON" : "OFF")}";
        }

        private static string LogLevel(string[] args)
        {
            if (args.Length < 2)
            {
                return $"Server log level: {Session.Config.LogLevel}, client log level: {Session.Config.ClientOutputLogLevel}";
            }

            var target = args[1].ToLowerInvariant();
            if (target != "server" && target != "client")
            {
                return "Usage: /core loglevel <server|client> [0-3]";
            }

            if (args.Length < 3)
            {
                return target == "server"
                    ? $"Server log level is {Session.Config.LogLevel}"
                    : $"Client log level is {Session.Config.ClientOutputLogLevel}";
            }

            int newLevel;
            if (!int.TryParse(args[2], out newLevel) || newLevel < 0 || newLevel > 3)
            {
                return "Log level must be a number from 0 to 3.";
            }

            if (target == "server")
            {
                Session.Config.LogLevel = newLevel;
            }
            else
            {
                Session.Config.ClientOutputLogLevel = newLevel;
            }

            Session.Config.SaveConfig(true);
            return $"{(target == "server" ? "Server" : "Client")} log level set to {newLevel}.";
        }

        private static string Select(string[] args)
        {
            if (args.Length < 2)
            {
                return "Usage: /core select <NoCoreName|Subtype>";
            }

            var key = string.Join(" ", args.Skip(1));
            var found = Session.Config.NoCoreConfigs.FirstOrDefault(
                c => c.UniqueName.Equals(key, StringComparison.OrdinalIgnoreCase) ||
                     c.SubtypeId.Equals(key, StringComparison.OrdinalIgnoreCase));

            if (found == null)
            {
                return $"No 'no core' config found matching '{key}'. Use /core listnocores.";
            }

            Session.Config.SelectedNoCoreUniqueName = found.UniqueName ?? string.Empty;
            if (!Session.Config.ResolveSelectedNoCore())
                return Session.Config.GetNoCoreConfigurationError();

            var saved = Session.Config.SaveConfig(broadcast: false);
            Session.ApplyServerConfig();
            return $"Selected and applied 'no core' config: {found.UniqueName} ({found.SubtypeId}). " +
                   (saved ? "Selection saved; no world reload is needed." : "Selection could not be saved; check the server log.");
        }

        private static string SetWorldSpeed(string[] args)
        {
            if (args.Length == 1)
            {
                return $"Current world speed limit: {Session.Config.MaxPossibleSpeedMetersPerSecond} m/s";
            }

            float newSpeed;
            if (!float.TryParse(args[1], out newSpeed) || newSpeed <= 0)
            {
                return "Usage: /core setworldspeed <positive number>";
            }

            Session.Config.MaxPossibleSpeedMetersPerSecond = newSpeed;
            Session.ApplyConfigToDefinitions();
            Session.RefreshGroupsAfterConfigChanged();
            Session.BroadcastConfigToClients();
            return $"World speed limit set to {newSpeed} m/s (session config only).";
        }

        private static string IgnoreTags(long playerId, string[] args)
        {
            if (args.Length < 2)
            {
                return "Usage: /core ignoretags list|add <tag>|remove <tag>";
            }

            var action = args[1].ToLower();
            var modMessage ="";
            switch (action)
            {
                case "list":
                    modMessage += ListIgnoredTags();
                    break;
                case "add":
                    if (!CheckIfAdmin(playerId)) return "You are not Admin";
                    modMessage += AddIgnoredTag(args);
                    break;
                case "remove":
                    if (!CheckIfAdmin(playerId)) return "You are not Admin";
                    modMessage += RemoveIgnoredTag(args);
                    break;
                default:
                    modMessage+="Usage: /core ignoretags list|add <tag>|remove <tag>";
                    break;
            }
            return modMessage;
        }

        private static string IgnoreAi()
        {
            Session.Config.IgnoreAiFactions = !Session.Config.IgnoreAiFactions;
            Session.Config.SaveConfig(true);
            return $"Set AI factions ignore to {Session.Config.IgnoreAiFactions}.";
        }

        private static string UnattachedModules(string[] args)
        {
            if (args.Length < 2)
            {
                return $"Unattached upgrade modules mode is {(Session.Config.AllowUnattachedUpgradeModules ? "ON" : "OFF")}";
            }

            var val = args[1].ToLowerInvariant();
            if (val != "on" && val != "off")
            {
                return "Usage: /core unattachedmodules on|off";
            }

            Session.Config.AllowUnattachedUpgradeModules = (val == "on");
            Session.Config.SaveConfig(true);
            return $"Unattached upgrade modules mode set to {(Session.Config.AllowUnattachedUpgradeModules ? "ON" : "OFF")}";
        }

        private static string CoreCountLimits(string[] args)
        {
            if (!MyAPIGateway.Session.CreativeMode)
                return "Faction and player core count limits are always ON in survival worlds.";

            if (args.Length < 2)
                return $"Faction and player core count limits are {(Session.Config.CreativeCoreCountLimitsEnabled ? "ON" : "OFF")}.";

            var value = args[1].ToLowerInvariant();
            if (value != "on" && value != "off")
                return "Usage: /core corecountlimits on|off";

            Session.Config.CreativeCoreCountLimitsEnabled = value == "on";
            Session.Config.SaveConfig(true);
            Session.RefreshGroupsAfterConfigChanged();
            return $"Faction and player core count limits set to {(Session.Config.CreativeCoreCountLimitsEnabled ? "ON" : "OFF")}.";
        }

        private static string ListIgnoredTags()
        {
            var tags = Session.Config.IgnoredFactionTags ?? (Session.Config.IgnoredFactionTags = new List<string>());
            if (tags.Count == 0)
            {
                return "No ignored faction tags.";
            }
            return "Ignored faction tags: " + string.Join(", ", tags);
        }

        private static string AddIgnoredTag(string[] args)
        {
            if (args.Length < 3)
            {
                return "Usage: /core ignoretags add <tag>";
            }

            var tag = string.Join(" ", args.Skip(2)).Trim();
            if (string.IsNullOrWhiteSpace(tag))
            {
               return "Tag cannot be empty.";
            }

            var tags = Session.Config.IgnoredFactionTags ?? (Session.Config.IgnoredFactionTags = new List<string>());
            if (tags.Any(t => t.Equals(tag, StringComparison.OrdinalIgnoreCase)))
            {
                return $"Tag '{tag}' is already ignored.";

            }

            tags.Add(tag);
            Session.Config.SaveConfig(true);
            return $"Added ignored faction tag '{tag}'.";
        }

        private static string RemoveIgnoredTag(string[] args)
        {
            if (args.Length < 3)
            {
                return "Usage: /core ignoretags remove <tag>";
            }

            var tag = string.Join(" ", args.Skip(2)).Trim();
            if (string.IsNullOrWhiteSpace(tag))
            {
                return "Tag cannot be empty.";

            }

            var tags = Session.Config.IgnoredFactionTags ?? (Session.Config.IgnoredFactionTags = new List<string>());
            var removed = tags.RemoveAll(t => t.Equals(tag, StringComparison.OrdinalIgnoreCase));
            if (removed == 0)
            {
                return $"Tag '{tag}' was not in the ignore list.";
            }

            Session.Config.SaveConfig(true);
            return $"Removed ignored faction tag '{tag}'.";
        }
    }
}
