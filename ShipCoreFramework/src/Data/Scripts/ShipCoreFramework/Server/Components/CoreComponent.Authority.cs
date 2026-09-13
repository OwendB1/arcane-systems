using System;
using System.Linq;
using Sandbox.Game.EntityComponents;
using Sandbox.ModAPI;
using VRage.Game;
using VRage.Game.ModAPI;

namespace ShipCoreFramework
{
    internal partial class CoreComponent
    {
        private bool InitAuthoritative()
        {
            var isIgnoredNpcGrid = Session.Config.IgnoreAiFactions && CoreBlock.CubeGrid.IsNpcGrid();
            var builder = ResolvePlacementOwnerIdentityId();
            if (builder == 0 && !isIgnoredNpcGrid)
            {
                var name = CoreBlock.CustomName;
                Utils.Log($"Core init deferred for {name}: owner/builder identity is not available yet.", 1);
                _groupComponent.ScheduleMissingCoreRescan();
                return false;
            }

            var foundComputerComps = false;
            for (var i = 0; i < CoreBlock.SlimBlock.ComponentStack.GroupCount; i++)
            {
                if (CoreBlock.SlimBlock.ComponentStack.GetComponentStackInfo(i).ComponentName != "Computer") continue;
                foundComputerComps = true;
                break;
            }

            if (!foundComputerComps)
            {
                var subType = Utils.GetBlockSubtypeId(CoreBlock.SlimBlock);
                Utils.Log($"Core {subType} does not have any computer components by the looks of it, double check this is correct?", 2);
            }

            if (Session.Config.SelectedNoCore == null)
            {
                Utils.Log("NOCORE is NULL for CORE", 3);
                return false;
            }

            IsMainCore = false;
            var shipCoreConfig = Session.Config.GetShipCoreByTypeId(SubtypeId);
            var rankOwnerId = CoreBlock.CubeGrid.BigOwners.FirstOrDefault();
            if (rankOwnerId == 0) rankOwnerId = builder;
            var rankFaction = rankOwnerId == 0 || MyAPIGateway.Session?.Factions == null
                ? null
                : MyAPIGateway.Session.Factions.TryGetPlayerFaction(rankOwnerId);
            string rankFailureReason;
            if (!isIgnoredNpcGrid &&
                PerFactionManager.TryGetMinFactionRankViolation(shipCoreConfig, rankFaction, rankOwnerId, out rankFailureReason))
            {
                Utils.Log($"Core init rejected for {SubtypeId} on {CoreBlock.CubeGrid.CustomName}: {rankFailureReason}", 1);
                Utils.ShowNotification(rankFailureReason, builder);
                CoreBlock.SlimBlock.RemoveAndRefund();
                return false;
            }

            CubeGridModifiers.RegisterUpgradeModuleLink(CoreBlock);

            var persistedMain = CoreBlock.Storage != null
                                && CoreBlock.Storage.ContainsKey(Session.CoreStateStorageGUID)
                                && CoreBlock.Storage[Session.CoreStateStorageGUID] == "1";
            var existingMainCore = _groupComponent.MainCoreComponent;
            var groupHasMain = existingMainCore != null;

            if (groupHasMain && !_groupComponent.HasSameOrientationAsMain(this))
            {
                Utils.Log($"Core init rejected for {SubtypeId} on {CoreBlock.CubeGrid.CustomName}: orientation differs from active main core.", 1);
                Utils.ShowNotification("Core must match the active main core orientation: " +
                                       CoreBlock.CubeGrid.CustomName, builder);
                CoreBlock.SlimBlock.RemoveAndRefund();
                return false;
            }

            if (CheckIfCoreOfOtherTypeExists())
            {
                Utils.Log($"Core init rejected for {SubtypeId} on {CoreBlock.CubeGrid.CustomName}: other core type exists in mechanical group.", 1);
                Utils.ShowNotification($"Other Core Type Exists In Mechanical Group: {CoreBlock.CubeGrid.CustomName}", builder);
                CoreBlock.SlimBlock.RemoveAndRefund();
                return false;
            }

            if (_groupComponent.CoreDictionary.Count > _groupComponent.ShipCore?.MaxBackupCores &&
                _groupComponent.ShipCore?.MaxBackupCores > 0)
            {
                Utils.Log($"Core init rejected for {SubtypeId} on {CoreBlock.CubeGrid.CustomName}: backup core count {_groupComponent.CoreDictionary.Count}/{_groupComponent.ShipCore.MaxBackupCores}.", 1);
                Utils.ShowNotification($"This core exceeds max number of backup cores: {CoreBlock.CubeGrid.CustomName}", builder);
                CoreBlock.SlimBlock.RemoveAndRefund();
                return false;
            }

            var relationship = CoreBlock.GetUserRelationToOwner(CoreBlock.CubeGrid.BigOwners.FirstOrDefault());
            if (!isIgnoredNpcGrid &&
                (relationship == MyRelationsBetweenPlayerAndBlock.Neutral ||
                 relationship == MyRelationsBetweenPlayerAndBlock.Enemies))
            {
                var builderSteamId = MyAPIGateway.Players.TryGetSteamId(builder);
                if (MyAPIGateway.Session.IsUserAdmin(builderSteamId) &&
                    MyAPIGateway.Session.IsUserIgnorePCULimit(builderSteamId))
                {
                    Utils.ShowNotification("WARNING CORE IS PLACED BY ADMIN NOT OWNED!", builder);
                }
                else
                {
                    Utils.Log($"Core init rejected for {SubtypeId} on {CoreBlock.CubeGrid.CustomName}: builder {builder} is not friendly to owner.", 1);
                    Utils.ShowNotification("Cores can only be built by friendlies!", builder);
                    CoreBlock.SlimBlock.RemoveAndRefund();
                    return false;
                }
            }
            
            Utils.Log($"Core Initial: {SubtypeId}, GroupHasMain: {groupHasMain}, PersistedMain: {persistedMain}", 1);
            if (!groupHasMain || _groupComponent.ShouldCoreBecomeMain(this, persistedMain))
            {
                IsMainCore = true;
                _groupComponent.Activate(this);
            }
            else
            {
                IsMainCore = false;
                Utils.Log($"Core Initial: {SubtypeId} registered as backup core on {CoreBlock.CubeGrid.CustomName}.", 2);
            }

            if (!isIgnoredNpcGrid && _groupComponent.ShouldDeferOwnerLimitValidation(SubtypeId))
            {
                _groupComponent.ScheduleExternalLimitValidation();
                Utils.Log($"Deferring core limit validation for {SubtypeId} on {CoreBlock.CubeGrid.CustomName} until ownership is available.", 1);
                AttachBlockEvents();
                _groupComponent.DefenseValuesChanged();
                return true;
            }

            if (!isIgnoredNpcGrid &&
                (!PerFactionManager.IsGroupWithinFactionLimits(_groupComponent.OwningFaction, _groupComponent.OwnerId,
                     SubtypeId, !LimitsNexusSync.Ready)
                 || !PerPlayerManager.IsGroupWithinPlayerLimits(_groupComponent.OwnerId, SubtypeId,
                     !LimitsNexusSync.Ready)
                 || !PerManifestGroupManager.IsGroupWithinManifestLimits(SubtypeId, _groupComponent.OwnerId,
                     !LimitsNexusSync.Ready)))
            {
                if (LimitsNexusSync.Ready)
                {
                    _groupComponent.BeginNexusLimitValidation();
                    Utils.Log($"Deferring core limit validation for {SubtypeId} on {CoreBlock.CubeGrid.CustomName} until fresh Nexus state is confirmed.", 1);
                    AttachBlockEvents();
                    _groupComponent.DefenseValuesChanged();
                    return true;
                }

                Utils.Log($"Core init rejected for {SubtypeId} on {CoreBlock.CubeGrid.CustomName}: owner, faction, or manifest limits failed.", 1);
                CoreBlock.SlimBlock.RemoveAndRefund();
                _groupComponent.ResetCore();
                return false;
            }

            AttachBlockEvents();
            _groupComponent.DefenseValuesChanged();
            return true;
        }

        private bool CheckIfCoreOfOtherTypeExists()
        {
            var knownOtherCoreSubtypeIds = Session.Config?.ShipCores
                .Where(core => core != null &&
                               !string.Equals(core.SubtypeId, SubtypeId, StringComparison.OrdinalIgnoreCase))
                .Select(core => core.SubtypeId)
                .Where(subtypeId => !string.IsNullOrWhiteSpace(subtypeId))
                .ToList();

            if (knownOtherCoreSubtypeIds == null || knownOtherCoreSubtypeIds.Count == 0)
                return false;

            foreach (var gridComponent in _groupComponent.GridDictionary.Values)
            {
                if (gridComponent?.Grid == null) continue;

                var fatTerminals = ((IMyCubeGrid)gridComponent.Grid).GetFatBlocks<IMyFunctionalBlock>();
                foreach (var terminal in fatTerminals)
                {
                    if (terminal == null || ReferenceEquals(terminal, CoreBlock)) continue;
                    if (!Utils.IsCoreBlock(terminal)) continue;

                    var subtype = terminal.BlockDefinition.SubtypeId;
                    if (knownOtherCoreSubtypeIds.Any(sub =>
                        string.Equals(sub, subtype, StringComparison.OrdinalIgnoreCase)))
                        return true;
                }
            }

            return false;
        }

        private long ResolvePlacementOwnerIdentityId()
        {
            var builtBy = CoreBlock?.SlimBlock?.BuiltBy ?? 0;
            if (builtBy != 0) return builtBy;

            var ownerId = CoreBlock?.OwnerId ?? 0;
            if (ownerId != 0) return ownerId;

            var bigOwners = CoreBlock?.CubeGrid?.BigOwners;
            return bigOwners?.FirstOrDefault() ?? 0;
        }

        private void SaveCoreState()
        {
            if (!Session.IsServer) return;
            if (CoreBlock.Storage == null) CoreBlock.Storage = new MyModStorageComponent();
            CoreBlock.Storage[Session.CoreStateStorageGUID] = IsMainCore ? "1" : "0";
        }
    }
}
