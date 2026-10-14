using System.Collections.Generic;
using Sandbox.ModAPI;

namespace ShipCoreFramework
{
    internal partial class GroupComponent
    {
        // Game-thread only. A no-core grid can be punished by multiple connected core groups.
        private static readonly Dictionary<IMyFunctionalBlock, HashSet<GroupComponent>> ConnectorShutOffOwners =
            new Dictionary<IMyFunctionalBlock, HashSet<GroupComponent>>();
        private readonly HashSet<IMyFunctionalBlock> _connectorShutOffBlocks = new HashSet<IMyFunctionalBlock>();

        private void TrackConnectorShutOff(IMyFunctionalBlock block)
        {
            if (block == null) return;

            HashSet<GroupComponent> owners;
            if (!ConnectorShutOffOwners.TryGetValue(block, out owners))
            {
                // Only restore blocks that connector punishment actually turned off.
                if (!block.Enabled) return;
                owners = new HashSet<GroupComponent>();
                ConnectorShutOffOwners.Add(block, owners);
            }

            owners.Add(this);
            _connectorShutOffBlocks.Add(block);
        }

        private void RestoreConnectorShutOffBlocks(HashSet<IMyFunctionalBlock> stillPunished)
        {
            foreach (var block in new List<IMyFunctionalBlock>(_connectorShutOffBlocks))
            {
                if (stillPunished != null && stillPunished.Contains(block)) continue;

                _connectorShutOffBlocks.Remove(block);
                HashSet<GroupComponent> owners;
                if (!ConnectorShutOffOwners.TryGetValue(block, out owners)) continue;
                owners.Remove(this);
                if (owners.Count > 0) continue;

                ConnectorShutOffOwners.Remove(block);
                if (Session.IsShuttingDown || block.Closed || block.MarkedForClose ||
                    block.CubeGrid == null || block.CubeGrid.Closed || block.CubeGrid.MarkedForClose)
                    continue;

                // EnabledChanged applies the block's own group's normal limit guards.
                block.Enabled = true;
            }
        }
    }
}
