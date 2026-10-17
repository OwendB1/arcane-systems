using System.Collections.Generic;
using VRage.Game.ModAPI;

namespace ShipCoreFramework
{
    internal partial class GridComponent
    {
        internal void Clean()
        {
            _appliedModifiers = null;
            if (Grid != null)
            {
                Grid.OnMarkForClose -= GridMarkedForClose;
                Grid.OnBlockAdded -= BlockAddedEvent;
                Grid.OnBlockRemoved -= BlockRemoved;
                if (Session.IsServer)
                {
                    ((IMyCubeGrid)Grid).OnBlockIntegrityChanged -= BlockIntegrityChanged;
                    Grid.OnBlockOwnershipChanged -= GridOwnershipChanged;
                    Grid.OnStaticChanged -= GridStaticChanged;
                }
            }

            List<IMySlimBlock> blocksCopy;
            lock (_blocksLock)
            {
                blocksCopy = new List<IMySlimBlock>(_blocks.Keys);
                _blocks.Clear();
                _trackedPcu = 0;
                _trackedDryMass = 0f;
            }

            foreach (var block in blocksCopy)
            {
                CubeGridModifiers.UnregisterProductionModifierState(block?.FatBlock as IMyCubeBlock);
                if (Session.IsServer) DetachAuthoritativeBlockEvents(block);
            }

            if (Session.IsServer) CleanAuthoritativeState();
            foreach (var coreComponent in CoreDictionary.Values) coreComponent.Clean();
            CoreDictionary.Clear();
        }
    }
}
