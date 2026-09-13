using System;
using System.Collections.Generic;
using System.Linq;
using Sandbox.ModAPI;
using VRage.Game;
using VRage.Game.ModAPI;

namespace ShipCoreFramework
{
    internal static partial class Utils
    {
        internal static bool IsNpcGrid(this IMyCubeGrid grid)
        {
            if (grid == null) return false;

            var players = MyAPIGateway.Players;
            if (players == null || grid.BigOwners == null) return grid.IsNpcSpawnedGrid;

            var hasNpcOwner = false;
            foreach (var ownerId in grid.BigOwners)
            {
                if (ownerId == 0) continue;
                // Offline players retain Steam mappings and override both NPC owners and the vanilla flag.
                if (players.TryGetSteamId(ownerId) != 0 && players.TryGetIdentityId(ownerId)?.IsBot != true)
                    return false;
                hasNpcOwner = true;
            }

            return hasNpcOwner || grid.IsNpcSpawnedGrid;
        }

        internal static GroupComponent GetGroupComponent(this IMyTerminalBlock block)
        {
            var groupData = block?.CubeGrid.GetGridGroup(GridLinkTypeEnum.Mechanical);
            if (groupData == null) return null;
            GroupComponent groupComponent;
            var success = Session.GroupDict.TryGetValue(groupData, out groupComponent);
            return success ? groupComponent : null;
        }

        internal static GroupComponent GetGroupComponent(this IMyCubeGrid grid)
        {
            var groupData = grid.GetGridGroup(GridLinkTypeEnum.Mechanical);
            if (groupData == null) return null;
            GroupComponent groupComponent;
            var success = Session.GroupDict.TryGetValue(groupData, out groupComponent);
            return success ? groupComponent : null;
        }

        internal static bool IsCoreBlock(IMyFunctionalBlock block)
        {
            return block != null
                   && Session.Config != null
                   && Session.Config.IsValidCoreType(block.BlockDefinition.SubtypeId);
        }

        internal static bool IsCoreBlock(IMySlimBlock block)
        {
            return IsCoreBlock(block?.FatBlock as IMyFunctionalBlock);
        }

        internal static bool IsTrackedUpgradeModuleBlock(IMyFunctionalBlock block)
        {
            return block != null
                   && Session.Config != null
                   && Session.Config.IsTrackedUpgradeModuleDefinition(GetBlockTypeId(block), GetBlockSubtypeId(block));
        }

        internal static bool IsTrackedUpgradeModuleBlock(IMySlimBlock block)
        {
            return IsTrackedUpgradeModuleBlock(block?.FatBlock as IMyFunctionalBlock);
        }

        internal static string GetBlockTypeId(MyDefinitionId definitionId)
        {
            return Convert.ToString(definitionId.TypeId).Replace("MyObjectBuilder_", "");
        }

        internal static string GetBlockSubtypeId(MyDefinitionId definitionId)
        {
            return Convert.ToString(definitionId.SubtypeId);
        }

        internal static string GetBlockTypeId(IMySlimBlock block)
        {
            return GetBlockTypeId(block.BlockDefinition.Id);
        }

        internal static string GetBlockTypeId(IMyCubeBlock block)
        {
            if (block?.SlimBlock?.BlockDefinition != null)
                return GetBlockTypeId(block.SlimBlock);

            return Convert.ToString(block.BlockDefinition.TypeId).Replace("MyObjectBuilder_", "");
        }

        internal static string GetBlockSubtypeId(IMySlimBlock block)
        {
            return Convert.ToString(block.BlockDefinition.Id.SubtypeId);
        }

        internal static string GetBlockSubtypeId(IMyCubeBlock block)
        {
            if (block?.SlimBlock?.BlockDefinition != null)
                return GetBlockSubtypeId(block.SlimBlock);

            return Convert.ToString(block.BlockDefinition.SubtypeId);
        }

        internal static string GetLocalizedBlockName(IMySlimBlock block)
        {
            if (block == null) return string.Empty;

            var definitionDisplayName = block.FatBlock?.DefinitionDisplayNameText;
            if (!string.IsNullOrWhiteSpace(definitionDisplayName)) return definitionDisplayName;

            var blockDefinitionDisplayName = block.BlockDefinition?.DisplayNameText;
            if (!string.IsNullOrWhiteSpace(blockDefinitionDisplayName)) return blockDefinitionDisplayName;

            return GetBlockSubtypeId(block);
        }

        internal static long GetMajorityOwnerId(this GroupComponent groupComponent)
        {
            var ownersPerGrid = new Dictionary<long, int>();
            foreach (var grid in groupComponent.GridDictionary.Select(kvp => kvp.Key)
                         .Where(grid => grid.BigOwners != null && grid.BigOwners.Count > 0))
            {
                foreach (var player in grid.BigOwners)
                {
                    if (ownersPerGrid.ContainsKey(player)) ownersPerGrid[player]++;
                    else ownersPerGrid.Add(player, 1);
                }
            }

            return ownersPerGrid.Count == 0 ? 0 : ownersPerGrid.MaxBy(kvp => kvp.Value).Key;
        }

        internal static bool TryFindByGridId(long gridEntityId, out GroupComponent group)
        {
            foreach (var gc in Session.GroupDict.Select(kv => kv.Value))
            {
                var gridIds = gc.GetCachedMechanicalGridIds();
                for (var i = 0; i < gridIds.Length; i++)
                {
                    if (gridIds[i] != gridEntityId) continue;
                    group = gc;
                    return true;
                }
            }

            foreach (var gc in Session.GroupDict.Select(kv => kv.Value))
            {
                if (!Session.IsGameThread) continue;
                if (!gc.GridDictionary.Keys.Any(g => g != null && g.EntityId == gridEntityId)) continue;
                group = gc;
                return true;
            }

            group = null;
            return false;
        }
    }
}
