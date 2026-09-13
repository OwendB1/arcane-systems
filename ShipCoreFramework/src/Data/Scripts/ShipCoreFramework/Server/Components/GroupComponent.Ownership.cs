using System.Linq;
using Sandbox.Game.Entities;
using Sandbox.Game.EntityComponents;
using Sandbox.ModAPI;
using VRage.Game;
using VRage.Game.ModAPI;

namespace ShipCoreFramework
{
    internal partial class GroupComponent
    {
        private bool IsNpcGroup()
        {
            return GridDictionary.Keys.Any(grid => grid.IsNpcGrid());
        }

        private bool IsIgnoredNpcGroup()
        {
            return Session.Config.IgnoreAiFactions && IsNpcGroup();
        }

        internal bool IsNpcGroupThreadSafe()
        {
            return Session.IsGameThread ? IsNpcGroup() : GetCachedIsNpcGroup();
        }

        internal bool ShouldEvaluateBlockLimit(BlockLimit limit)
        {
            return limit == null || !limit.IgnoredByNpc || !IsNpcGroupThreadSafe();
        }

        private bool ComputeIsIgnoredGroup()
        {
            if (IsIgnoredByAiOrFactionTag()) return true;
            if (OwnerId == 0) return true;
            var player = MyAPIGateway.Players.TryGetIdentityId(OwnerId);
            return player != null && player.PromoteLevel == MyPromoteLevel.Admin &&
                   MyAPIGateway.Session.IsUserIgnorePCULimit(player.SteamUserId);
        }

        internal bool IsIgnoredByAiOrFactionTag()
        {
            if (IsIgnoredNpcGroup()) return true;

            var faction = OwningFaction;
            if (faction == null) return false;
            return Session.Config.IgnoredFactionTags != null &&
                   Session.Config.IgnoredFactionTags.Contains(faction.Tag);
        }

        internal bool IsIgnoredByAiOrFactionTagThreadSafe()
        {
            return Session.IsGameThread ? IsIgnoredByAiOrFactionTag() : GetCachedIsIgnoredByAiOrFactionTag();
        }

        private long GetAuthoritativeOwnerId()
        {
            var ownerId = ResolveLocalOwnerId();
            if (IsIgnoredNpcGroup())
            {
                _lastOwnerId = 0;
                return 0;
            }

            if (ownerId == 0 && _lastOwnerId != 0)
            {
                Utils.Log($"OwnerId: Changed from {_lastOwnerId} to 0", 2);
                RefreshRegisteredLimitOwnership(0);
            }

            if (ownerId != 0 && _lastOwnerId != ownerId)
            {
                var previousOwnerId = _lastOwnerId;
                if (previousOwnerId != 0)
                    Utils.Log($"OwnerId: Changed from {previousOwnerId} to {ownerId}", 2);

                var newOwningFaction = MyAPIGateway.Session.Factions.TryGetPlayerFaction(ownerId);
                var coreType = ShipCore.SubtypeId;
                RefreshRegisteredLimitOwnership(ownerId);

                var isWithinFactionLimits =
                    PerFactionManager.IsGroupWithinFactionLimits(newOwningFaction, ownerId, coreType);
                var isWithinPlayerLimits = PerPlayerManager.IsGroupWithinPlayerLimits(ownerId, coreType);
                if (!isWithinFactionLimits || !isWithinPlayerLimits)
                {
                    if (previousOwnerId != 0)
                    {
                        Utils.Log($"OwnerId: Limit validation failed for new owner {ownerId}; reverting group {GetGroupKey()} to previous owner {previousOwnerId}. FactionOk={isWithinFactionLimits}, PlayerOk={isWithinPlayerLimits}", 1);
                        var cube = MainCoreComponent?.CoreBlock as MyCubeBlock;
                        cube?.ChangeOwner(previousOwnerId, MyOwnershipShareModeEnum.Faction);
                        ownerId = previousOwnerId;
                        RefreshRegisteredLimitOwnership(ownerId);
                    }
                    else
                    {
                        Utils.Log($"OwnerId: Limit validation failed for owner {ownerId} on group {GetGroupKey()}; scheduling deferred validation. FactionOk={isWithinFactionLimits}, PlayerOk={isWithinPlayerLimits}", 1);
                        ScheduleExternalLimitValidation();
                    }
                }
                SaveOwnerIdToMainCore(ownerId);
            }

            if (_lastOwnerId != ownerId) Session.MarkRuntimeStateDirty(this);
            _lastOwnerId = ownerId;
            return ownerId;
        }

        private long GetFactionId(long ownerId)
        {
            var faction = ownerId == 0 ? null : MyAPIGateway.Session.Factions.TryGetPlayerFaction(ownerId);
            return faction?.FactionId ?? -1;
        }

        internal bool ShouldDeferOwnerLimitValidation(string coreType)
        {
            if (OwnerId != 0) return false;

            var core = Session.Config.GetShipCoreByTypeId(coreType);
            if (core == null) return false;

            return (Session.CoreCountLimitsEnabled &&
                    (core.MaxPerPlayer >= 0 || core.FactionPlayersNeededPerCore > 0)) ||
                   core.MinPlayers > 0 ||
                   core.MaxPlayers > 0;
        }

        private void SaveOwnerIdToMainCore(long ownerId)
        {
            if (!Session.IsServer) return;

            var coreBlock = MainCoreComponent?.CoreBlock;
            if (coreBlock == null) return;
            if (coreBlock.Storage == null) coreBlock.Storage = new MyModStorageComponent();
            coreBlock.Storage[Session.CoreLastOwnerStorageGUID] = ownerId.ToString();
        }
    }
}
