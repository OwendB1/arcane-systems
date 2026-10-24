using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using Sandbox.ModAPI;
using VRage.Game;
using VRage.Game.ModAPI;

namespace ShipCoreFramework
{
    internal static class PerFactionManager
    {
        internal struct FactionChange
        {
            internal long FactionId;
            internal string CoreType;
            internal int Count;
        }

        private static readonly ConcurrentDictionary<CoreCountKey, int> PerFactionCounts =
            new ConcurrentDictionary<CoreCountKey, int>();

        private static readonly ConcurrentDictionary<long, byte> PlayerIdentityIds =
            new ConcurrentDictionary<long, byte>();

        private static readonly ConcurrentDictionary<long, byte> NonPlayerIdentityIds =
            new ConcurrentDictionary<long, byte>();

        private static readonly ConcurrentDictionary<long, byte> RegisteredIdentityIds =
            new ConcurrentDictionary<long, byte>();

        private static readonly ConcurrentDictionary<long, byte> LoggedIdentityClassifications =
            new ConcurrentDictionary<long, byte>();

        private static bool _suppressEvents;
        private static bool _identityCacheInitialized;

        private static ModConfig Config => Session.Config;

        internal static void InitializeIdentityCache()
        {
            if (!Session.IsGameThread)
            {
                MyAPIGateway.Utilities.InvokeOnGameThread(InitializeIdentityCache);
                return;
            }

            PlayerIdentityIds.Clear();
            NonPlayerIdentityIds.Clear();
            RegisteredIdentityIds.Clear();
            LoggedIdentityClassifications.Clear();

            CacheCheckpointIdentities();
            CacheRegisteredIdentities();
            CacheOnlinePlayers();

            _identityCacheInitialized = true;
            Utils.Log("PerFactionManager::InitializeIdentityCache: cached " +
                      PlayerIdentityIds.Count + " player identities, " +
                      NonPlayerIdentityIds.Count + " non-player identities, " +
                      RegisteredIdentityIds.Count + " registered identities.", 1);
        }

        internal static void TrackFactionMembers(long factionId)
        {
            if (factionId <= 0 || MyAPIGateway.Session?.Factions == null)
                return;

            var faction = MyAPIGateway.Session.Factions.TryGetFactionById(factionId);
            if (faction == null)
                return;

            foreach (var member in faction.Members)
                TrackFactionIdentity(member.Key, faction.Tag);

            Utils.Log("PerFactionManager::TrackFactionMembers: scanned faction " + faction.Tag +
                      " (" + factionId + ") with " + faction.Members.Count + " members.", 2);
        }

        internal static void TrackFactionIdentity(long identityId, long factionId)
        {
            string factionTag = null;
            if (factionId > 0 && MyAPIGateway.Session?.Factions != null)
            {
                var faction = MyAPIGateway.Session.Factions.TryGetFactionById(factionId);
                factionTag = faction?.Tag;
            }

            TrackFactionIdentity(identityId, factionTag);
        }

        private static void TrackFactionIdentity(long identityId, string factionTag)
        {
            if (identityId <= 0)
                return;

            if (!Session.IsGameThread)
            {
                MyAPIGateway.Utilities.InvokeOnGameThread(() => TrackFactionIdentity(identityId, factionTag));
                return;
            }

            EnsureIdentityCacheInitialized();

            var steamId = TryGetSteamId(identityId);
            if (steamId != 0)
            {
                MarkPlayerIdentity(identityId);
                LogIdentityClassification(identityId, factionTag, steamId, true, true, "faction-event-steam");
                return;
            }

            var player = TryGetActivePlayer(identityId);
            if (player != null)
            {
                if (player.IsBot)
                    MarkNonPlayerIdentity(identityId);
                else
                    MarkPlayerIdentity(identityId);

                LogIdentityClassification(identityId, factionTag, steamId, true, !player.IsBot,
                    player.IsBot ? "faction-event-active-bot" : "faction-event-active-player");
                return;
            }

            var inRegisteredIdentities = RefreshRegisteredIdentity(identityId);
            if (inRegisteredIdentities && !PlayerIdentityIds.ContainsKey(identityId))
                MarkNonPlayerIdentity(identityId);

            LogIdentityClassification(identityId, factionTag, steamId, inRegisteredIdentities, false,
                inRegisteredIdentities ? "faction-event-registered-no-player" : "faction-event-missing-identity");
        }

        internal static int GetFactionMemberCount(IMyFaction owningFaction)
        {
            if (owningFaction == null)
                return 0;

            var count = 0;
            foreach (var member in owningFaction.Members)
            {
                if (ShouldCountTowardsPlayerLimits(member.Key, owningFaction.Tag))
                    count++;
            }

            return count;
        }

        internal static int GetFactionPlayerCount(IMyFaction owningFaction, long ownerId)
        {
            if (owningFaction != null)
                return GetFactionMemberCount(owningFaction);

            return ShouldCountTowardsPlayerLimits(ownerId, null) ? 1 : 0;
        }

        internal static FactionRank GetFactionRank(IMyFaction owningFaction, long ownerId)
        {
            if (owningFaction == null || ownerId <= 0)
                return FactionRank.None;

            foreach (var member in owningFaction.Members)
            {
                if (member.Key != ownerId)
                    continue;

                if (member.Value.IsFounder || owningFaction.IsFounder(ownerId))
                    return FactionRank.Founder;

                if (member.Value.IsLeader || owningFaction.IsLeader(ownerId))
                    return FactionRank.Leader;

                return FactionRank.Member;
            }

            return FactionRank.None;
        }

        internal static bool TryGetMinFactionRankViolation(ShipCore core, IMyFaction owningFaction, long ownerId, out string reason)
        {
            reason = string.Empty;
            if (core == null || core.MinFactionRank == FactionRank.None)
                return false;

            var ownerRank = GetFactionRank(owningFaction, ownerId);
            if (ownerRank >= core.MinFactionRank)
                return false;

            var coreName = string.IsNullOrWhiteSpace(core.UniqueName) ? core.SubtypeId : core.UniqueName;
            reason = "Core " + coreName + " requires faction rank " + core.MinFactionRank + " or higher.";
            if (ownerRank == FactionRank.None)
                reason += " Owner is not a faction member.";

            return true;
        }

        private static bool ShouldCountTowardsPlayerLimits(long identityId, string factionTag)
        {
            if (identityId <= 0)
                return false;

            EnsureIdentityCacheInitialized();

            var steamId = TryGetSteamId(identityId);
            var inRegisteredIdentities = RegisteredIdentityIds.ContainsKey(identityId);

            if (Config.DebugMode)
            {
                if (!inRegisteredIdentities && Session.IsGameThread)
                    inRegisteredIdentities = RefreshRegisteredIdentity(identityId);

                LogIdentityClassification(identityId, factionTag, steamId, inRegisteredIdentities, true, "debug-mode");
                return true;
            }

            if (NonPlayerIdentityIds.ContainsKey(identityId))
            {
                LogIdentityClassification(identityId, factionTag, steamId, inRegisteredIdentities, false, "known-non-player");
                return false;
            }

            if (PlayerIdentityIds.ContainsKey(identityId))
            {
                LogIdentityClassification(identityId, factionTag, steamId, inRegisteredIdentities, true, "known-player");
                return true;
            }

            if (steamId != 0)
            {
                MarkPlayerIdentity(identityId);
                LogIdentityClassification(identityId, factionTag, steamId, inRegisteredIdentities, true, "steam-id");
                return true;
            }

            var player = TryGetActivePlayer(identityId);
            if (player != null)
            {
                if (player.IsBot)
                {
                    MarkNonPlayerIdentity(identityId);
                    LogIdentityClassification(identityId, factionTag, steamId, true, false, "active-bot");
                    return false;
                }

                MarkPlayerIdentity(identityId);
                LogIdentityClassification(identityId, factionTag, steamId, true, true, "active-player");
                return true;
            }

            if (!inRegisteredIdentities && Session.IsGameThread)
                inRegisteredIdentities = RefreshRegisteredIdentity(identityId);

            LogIdentityClassification(identityId, factionTag, steamId, inRegisteredIdentities, false,
                inRegisteredIdentities ? "registered-no-player" : "missing-identity");
            return false;
        }

        private static void EnsureIdentityCacheInitialized()
        {
            if (_identityCacheInitialized || !Session.IsGameThread || Session.IsShuttingDown)
                return;

            InitializeIdentityCache();
        }

        private static void CacheCheckpointIdentities()
        {
            try
            {
                if (MyAPIGateway.Session == null)
                    return;

                var playerCountBefore = PlayerIdentityIds.Count;
                var nonPlayerCountBefore = NonPlayerIdentityIds.Count;
                var checkpoint = MyAPIGateway.Session.GetCheckpoint(MyAPIGateway.Session.Name);
                if (checkpoint == null)
                    return;

                if (checkpoint.NonPlayerIdentities != null)
                {
                    foreach (var identityId in checkpoint.NonPlayerIdentities)
                        MarkNonPlayerIdentity(identityId);
                }

                if (checkpoint.AllPlayersData?.Dictionary != null)
                {
                    foreach (var entry in checkpoint.AllPlayersData.Dictionary)
                    {
                        if (entry.Value != null)
                            MarkPlayerIdentity(entry.Value.IdentityId);
                    }
                }

                if (checkpoint.AllPlayers != null)
                {
                    foreach (var playerItem in checkpoint.AllPlayers)
                    {
                        if (playerItem.PlayerId > 0 && playerItem.SteamId != 0)
                            MarkPlayerIdentity(playerItem.PlayerId);
                    }
                }

                Utils.Log("PerFactionManager::CacheCheckpointIdentities: added " +
                          (PlayerIdentityIds.Count - playerCountBefore) + " player identities and " +
                          (NonPlayerIdentityIds.Count - nonPlayerCountBefore) + " non-player identities from checkpoint.", 2);
            }
            catch (Exception ex)
            {
                Utils.Log("PerFactionManager::CacheCheckpointIdentities failed: " + ex.Message, 1);
            }
        }

        private static void CacheRegisteredIdentities()
        {
            try
            {
                if (MyAPIGateway.Players == null)
                    return;

                var registeredCountBefore = RegisteredIdentityIds.Count;
                var identities = new List<IMyIdentity>();
                MyAPIGateway.Players.GetAllIdentites(identities);
                foreach (var identity in identities)
                {
                    if (identity != null && identity.IdentityId > 0)
                        RegisteredIdentityIds.TryAdd(identity.IdentityId, 0);
                }

                Utils.Log("PerFactionManager::CacheRegisteredIdentities: added " +
                          (RegisteredIdentityIds.Count - registeredCountBefore) + " registered identities from GetAllIdentites.", 2);
            }
            catch (Exception ex)
            {
                Utils.Log("PerFactionManager::CacheRegisteredIdentities failed: " + ex.Message, 1);
            }
        }

        private static void CacheOnlinePlayers()
        {
            try
            {
                if (MyAPIGateway.Players == null)
                    return;

                var playerCountBefore = PlayerIdentityIds.Count;
                var nonPlayerCountBefore = NonPlayerIdentityIds.Count;
                var players = new List<IMyPlayer>();
                MyAPIGateway.Players.GetPlayers(players);
                foreach (var player in players)
                {
                    if (player == null || player.IdentityId <= 0)
                        continue;

                    if (player.IsBot)
                        MarkNonPlayerIdentity(player.IdentityId);
                    else
                        MarkPlayerIdentity(player.IdentityId);
                }

                Utils.Log("PerFactionManager::CacheOnlinePlayers: scanned " + players.Count +
                          " online players, added " + (PlayerIdentityIds.Count - playerCountBefore) +
                          " player identities and " + (NonPlayerIdentityIds.Count - nonPlayerCountBefore) +
                          " non-player identities.", 2);
            }
            catch (Exception ex)
            {
                Utils.Log("PerFactionManager::CacheOnlinePlayers failed: " + ex.Message, 1);
            }
        }

        private static bool RefreshRegisteredIdentity(long identityId)
        {
            if (identityId <= 0)
                return false;

            if (RegisteredIdentityIds.ContainsKey(identityId))
                return true;

            try
            {
                if (MyAPIGateway.Players == null)
                    return false;

                var identities = new List<IMyIdentity>();
                MyAPIGateway.Players.GetAllIdentites(identities, identity => identity != null && identity.IdentityId == identityId);
                foreach (var identity in identities)
                {
                    if (identity == null || identity.IdentityId <= 0)
                        continue;

                    RegisteredIdentityIds.TryAdd(identity.IdentityId, 0);
                    return true;
                }
            }
            catch (Exception ex)
            {
                Utils.Log("PerFactionManager::RefreshRegisteredIdentity failed for " + identityId + ": " + ex.Message, 1);
            }

            return false;
        }

        private static ulong TryGetSteamId(long identityId)
        {
            try
            {
                return MyAPIGateway.Players != null ? MyAPIGateway.Players.TryGetSteamId(identityId) : 0;
            }
            catch (Exception ex)
            {
                Utils.Log("PerFactionManager::TryGetSteamId failed for " + identityId + ": " + ex.Message, 1);
                return 0;
            }
        }

        private static IMyPlayer TryGetActivePlayer(long identityId)
        {
            try
            {
                return MyAPIGateway.Players != null ? MyAPIGateway.Players.TryGetIdentityId(identityId) : null;
            }
            catch (Exception ex)
            {
                Utils.Log("PerFactionManager::TryGetActivePlayer failed for " + identityId + ": " + ex.Message, 1);
                return null;
            }
        }

        private static void MarkPlayerIdentity(long identityId)
        {
            if (identityId <= 0)
                return;

            PlayerIdentityIds.TryAdd(identityId, 0);
            byte ignored;
            NonPlayerIdentityIds.TryRemove(identityId, out ignored);
        }

        private static void MarkNonPlayerIdentity(long identityId)
        {
            if (identityId <= 0)
                return;

            if (!PlayerIdentityIds.ContainsKey(identityId))
                NonPlayerIdentityIds.TryAdd(identityId, 0);
        }

        private static void LogIdentityClassification(long identityId, string factionTag, ulong steamId,
            bool inRegisteredIdentities, bool counts, string reason)
        {
            if (!Config.DebugMode && counts)
                return;

            if (!LoggedIdentityClassifications.TryAdd(identityId, 0))
                return;

            Utils.Log("PerFactionManager::IdentityClassification: identityId=" + identityId +
                      ", factionTag=" + (string.IsNullOrWhiteSpace(factionTag) ? "<none>" : factionTag) +
                      ", steamId=" + steamId +
                      ", inAllIdentities=" + inRegisteredIdentities +
                      ", knownPlayer=" + PlayerIdentityIds.ContainsKey(identityId) +
                      ", knownNonPlayer=" + NonPlayerIdentityIds.ContainsKey(identityId) +
                      ", counts=" + counts +
                      ", reason=" + reason, counts ? 2 : 1);
        }

        internal static bool HasFactionCoreLimit(ShipCore core)
        {
            return Session.CoreCountLimitsEnabled && core != null &&
                   (core.MaxPerFaction >= 0 || core.FactionPlayersNeededPerCore > 0);
        }

        internal static int GetPlayerScaledFactionCoreLimit(ShipCore core, int playerCount)
        {
            if (core == null || core.FactionPlayersNeededPerCore <= 0)
                return -1;

            return Math.Max(core.MinPerFaction,
                Math.Max(0, playerCount) / core.FactionPlayersNeededPerCore);
        }

        internal static int GetEffectiveFactionCoreLimit(ShipCore core, int playerCount)
        {
            if (!Session.CoreCountLimitsEnabled || core == null)
                return -1;

            var fixedLimit = core.MaxPerFaction;
            var playerScaledLimit = GetPlayerScaledFactionCoreLimit(core, playerCount);

            if (playerScaledLimit < 0)
                return fixedLimit;

            if (fixedLimit < 0)
                return playerScaledLimit;

            return Math.Min(fixedLimit, playerScaledLimit);
        }

        internal static bool IsGroupWithinFactionLimits(IMyFaction owningFaction, long ownerId, string coreType,
            bool notify = true)
        {
            var factionId = owningFaction?.FactionId ?? -1;
            if (!Config.IsValidCoreType(coreType))
            {
                Utils.Log($"PerFactionManager::IsGridWithinFactionLimits: Unknown core type id {coreType}", 3);
                return false;
            }

            var core = Config.GetShipCoreByTypeId(coreType);
            var minNeededPlayers = core.MinPlayers;
            var maxAllowedPlayers = core.MaxPlayers;
            var requiresFaction = HasFactionCoreLimit(core) && core.FactionPlayersNeededPerCore > 0;
            var factionMemberCount = GetFactionMemberCount(owningFaction);

            if (factionId == -1 && (minNeededPlayers > 0 || requiresFaction))
            {
                if (notify)
                    Utils.ShowChatMessage($"Player is not in Faction [OwningPlayer:{ownerId}] and therefore cannot build faction limited core: {coreType}", playerEntityId: ownerId);
                return false;
            }

            var playerCount = GetFactionPlayerCount(owningFaction, ownerId);
            var maxAllowedGrids = GetEffectiveFactionCoreLimit(core, playerCount);
            var playerScaledLimit = GetPlayerScaledFactionCoreLimit(core, playerCount);

            if (factionMemberCount < minNeededPlayers)
            {
                if (notify)
                    Utils.ShowChatMessage($"{factionMemberCount}/{minNeededPlayers} players needed to build: {coreType}", playerEntityId: ownerId);
                return false;
            }

            if (maxAllowedPlayers > 0 && playerCount > maxAllowedPlayers)
            {
                if (notify)
                    Utils.ShowChatMessage(
                        $"{playerCount}/{maxAllowedPlayers} players exceeds the allowed faction size for: {coreType}", playerEntityId: ownerId);
                return false;
            }

            if (maxAllowedGrids < 0) return true;

            var currentCount = GetCurrentCount(factionId, coreType);
            if (currentCount <= maxAllowedGrids) return true;
            if (playerScaledLimit == 0)
            {
                if (notify)
                    Utils.ShowChatMessage($"{playerCount}/{core.FactionPlayersNeededPerCore} faction players needed per {coreType}.", playerEntityId: ownerId);
                return false;
            }

            var message = $"Faction limit reached, you already have {currentCount - 1}/{maxAllowedGrids} {coreType} built!";
            if (playerScaledLimit >= 0)
                message += $" Player-scaled cap: {playerCount} players -> {playerScaledLimit} allowed (1 per {core.FactionPlayersNeededPerCore} players).";

            if (notify) Utils.ShowChatMessage(message, playerEntityId: ownerId);
            return false;
        }

        internal static int GetCurrentCount(long factionId, string coreType)
        {
            if (factionId <= 0 || string.IsNullOrWhiteSpace(coreType))
                return 0;

            int localCount;
            PerFactionCounts.TryGetValue(new CoreCountKey(factionId, coreType), out localCount);
            return localCount + LimitsNexusSync.GetRemoteFactionCount(factionId, coreType);
        }

        internal static void AddGridGroup(IMyFaction owningFaction, string coreType)
        {
            if (owningFaction == null) return;
            AddGridGroup(owningFaction.FactionId, coreType);
        }

        internal static void AddGridGroup(long factionId, string coreType)
        {
            if (!Session.IsGameThread)
            {
                MyAPIGateway.Utilities.InvokeOnGameThread(delegate { AddGridGroup(factionId, coreType); });
                return;
            }

            Utils.Log($"PerFactionManager::AddCubeGrid: Adding grid for faction {factionId} with core type {coreType}", 1);
            if (factionId <= 0 || string.IsNullOrWhiteSpace(coreType)) return;

            var key = new CoreCountKey(factionId, coreType);
            var count = PerFactionCounts.AddOrUpdate(key, 1, delegate(CoreCountKey k, int value) { return value + 1; });
            if (!_suppressEvents) LimitsNexusSync.BroadcastFactionChange(new FactionChange { FactionId = factionId, CoreType = coreType, Count = count });
        }

        internal static void RemoveGridGroup(IMyFaction owningFaction, string coreType)
        {
            if (owningFaction == null) return;
            RemoveGridGroup(owningFaction.FactionId, coreType);
        }

        internal static void RemoveGridGroup(long factionId, string coreType)
        {
            if (!Session.IsGameThread)
            {
                MyAPIGateway.Utilities.InvokeOnGameThread(delegate { RemoveGridGroup(factionId, coreType); });
                return;
            }

            if (factionId <= 0 || string.IsNullOrWhiteSpace(coreType)) return;

            var key = new CoreCountKey(factionId, coreType);
            int previous;
            PerFactionCounts.TryGetValue(key, out previous);
            if (previous <= 0) return;

            var count = PerFactionCounts.AddOrUpdate(key, 0,
                delegate(CoreCountKey k, int value) { return value <= 0 ? 0 : value - 1; });
            if (!_suppressEvents) LimitsNexusSync.BroadcastFactionChange(new FactionChange { FactionId = factionId, CoreType = coreType, Count = count });
        }

        internal static void RemoveFaction(long factionId)
        {
            if (!Session.IsGameThread)
            {
                MyAPIGateway.Utilities.InvokeOnGameThread(delegate { RemoveFaction(factionId); });
                return;
            }

            if (factionId <= 0) return;

            foreach (var entry in GetFactionCountsSnapshot(factionId).ToList())
            {
                if (entry.Value <= 0) continue;
                PerFactionCounts[new CoreCountKey(factionId, entry.Key)] = 0;
                if (!_suppressEvents) LimitsNexusSync.BroadcastFactionChange(new FactionChange { FactionId = factionId, CoreType = entry.Key, Count = 0 });
            }
        }

        internal static void Reset()
        {
            if (!Session.IsGameThread)
            {
                MyAPIGateway.Utilities.InvokeOnGameThread(Reset);
                return;
            }

            PerFactionCounts.Clear();
            PlayerIdentityIds.Clear();
            NonPlayerIdentityIds.Clear();
            RegisteredIdentityIds.Clear();
            LoggedIdentityClassifications.Clear();
            _identityCacheInitialized = false;
        }

        internal static CoreCountEntry[] GetLocalCountsSnapshot()
        {
            var snapshot = PerFactionCounts.ToArray();
            var result = new CoreCountEntry[snapshot.Length];
            for (var i = 0; i < snapshot.Length; i++)
            {
                result[i] = new CoreCountEntry
                {
                    OwnerId = snapshot[i].Key.OwnerId,
                    CoreType = snapshot[i].Key.CoreType,
                    Count = snapshot[i].Value
                };
            }

            return result;
        }

        internal static Dictionary<string, int> GetFactionCountsSnapshot(long factionId)
        {
            var result = new Dictionary<string, int>();
            foreach (var entry in GetLocalCountsSnapshot())
            {
                if (entry.OwnerId != factionId) continue;
                result[entry.CoreType] = entry.Count;
            }

            return result;
        }

        internal static void BeginExternalUpdate() { _suppressEvents = true; }
        internal static void EndExternalUpdate() { _suppressEvents = false; }
    }
}
