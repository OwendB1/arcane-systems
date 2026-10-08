using System.Collections.Generic;
using System.Linq;
using Sandbox.Game;
using Sandbox.ModAPI;
using VRage.Game.ModAPI;

namespace ShipCoreFramework
{
    public partial class Session
    {
        private static void FactionStateChanged(MyFactionStateChange action, long fromFactionId, long toFactionId,
            long factionId, long playerId)
        {
            if (!IsServer) return;
            if (Config.SelectedNoCore == null) return;
            if (playerId > 0)
            {
                var identityFactionId = toFactionId > 0 ? toFactionId : factionId > 0 ? factionId : fromFactionId;
                PerFactionManager.TrackFactionIdentity(playerId, identityFactionId);
            }

            if (!IsRelevantFactionStateChange(action)) return;
            Utils.Log($"FactionStateChanged: {action} from {fromFactionId} to {toFactionId} for faction {factionId} and player {playerId}", 1);

            if (action == MyFactionStateChange.RemoveFaction)
            {
                var removedFactionGroups = GetAffectedGroupsForFactionChange(factionId, 0).ToList();
                PerFactionManager.RemoveFaction(factionId);
                EnforceOverCapacityForGroups(removedFactionGroups);
                return;
            }

            if (action == MyFactionStateChange.FactionMemberAcceptJoin)
            {
                var newFactionId = toFactionId > 0 ? toFactionId : factionId;
                EnforceOverCapacityForGroups(GetAffectedGroupsForFactionChange(newFactionId, playerId));
                return;
            }

            var oldFactionId = fromFactionId > 0 ? fromFactionId : factionId;
            var affectedGroups = GetAffectedGroupsForFactionChange(oldFactionId, playerId).ToList();

            foreach (var comp in affectedGroups
                         .Where(group => group.OwnerId == playerId)
                         .ToList())
            {
                PerFactionManager.RemoveGridGroup(oldFactionId, comp.ShipCore.SubtypeId);
            }

            EnforceOverCapacityForGroups(affectedGroups);
        }

        private static void FactionCreated(long factionId)
        {
            if (!IsServer) return;
            PerFactionManager.TrackFactionMembers(factionId);
        }

        private static void FactionEdited(long factionId)
        {
            if (!IsServer) return;
            PerFactionManager.TrackFactionMembers(factionId);
        }

        private static void SessionReady()
        {
            _sessionReady = true;
            InitializeServerReadyData();
        }

        private static void InitializeServerReadyData()
        {
            if (!IsServer || !_serverRuntimeDataLoaded || _serverReadyDataLoaded) return;
            PerFactionManager.InitializeIdentityCache();
            MyAPIGateway.Session.DamageSystem.RegisterBeforeDamageHandler(-100, CubeGridModifiers.GridCoreDamageHandler);
            MyExplosions.OnExplosion += CubeGridModifiers.HandleLightningExplosions;
            _serverReadyDataLoaded = true;
        }

        private static bool IsRelevantFactionStateChange(MyFactionStateChange action)
        {
            return action == MyFactionStateChange.FactionMemberAcceptJoin ||
                   action == MyFactionStateChange.FactionMemberKick ||
                   action == MyFactionStateChange.FactionMemberLeave ||
                   action == MyFactionStateChange.RemoveFaction;
        }

        private static IEnumerable<GroupComponent> GetAffectedGroupsForFactionChange(long factionId, long playerId)
        {
            return GroupDict.Values.Where(group => group.MainCoreComponent != null &&
                                                   (group.OwnerId == playerId ||
                                                    factionId > 0 &&
                                                    group.OwningFaction != null &&
                                                    group.OwningFaction.FactionId == factionId));
        }

        private static void EnforceOverCapacityForGroups(IEnumerable<GroupComponent> groups)
        {
            foreach (var comp in groups.Where(group => group?.MainCoreComponent != null).Distinct().ToList())
            {
                comp.SyncBeaconComponents();
                comp.RefreshPunishmentState();
            }
        }
    }
}
