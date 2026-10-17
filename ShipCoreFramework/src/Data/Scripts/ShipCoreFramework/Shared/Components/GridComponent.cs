using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using Sandbox.Game.Entities;
using VRage.Game.ModAPI;
using IngameIMyEntity = VRage.Game.ModAPI.Ingame.IMyEntity;

namespace ShipCoreFramework
{
    internal partial class GridComponent
    {
        internal struct TrackedContribution
        {
            internal readonly int Blocks;
            internal readonly int Pcu;
            internal readonly float DryMass;

            internal TrackedContribution(int blocks, int pcu, float dryMass)
            {
                Blocks = blocks;
                Pcu = pcu;
                DryMass = dryMass;
            }
        }

        internal MyCubeGrid Grid;
        private IMyGridGroupData _groupData;
        private readonly object _blocksLock = new object();
        private readonly Dictionary<IMySlimBlock, TrackedContribution> _blocks =
            new Dictionary<IMySlimBlock, TrackedContribution>();
        private int _trackedPcu;
        private float _trackedDryMass;
        internal int BlockCount
        {
            get
            {
                lock (_blocksLock)
                    return _blocks.Count;
            }
        }
        internal TrackedContribution TrackedTotals
        {
            get
            {
                lock (_blocksLock)
                    return new TrackedContribution(_blocks.Count, _trackedPcu, _trackedDryMass);
            }
        }

        internal readonly ConcurrentDictionary<IMyCubeBlock, CoreComponent> CoreDictionary =
            new ConcurrentDictionary<IMyCubeBlock, CoreComponent>();

        private GroupComponent GroupComponent
        {
            get
            {
                if (_groupData == null) return null;
                GroupComponent groupComponent;
                return Session.GroupDict.TryGetValue(_groupData, out groupComponent) ? groupComponent : null;
            }
        }

        internal void Init(IMyCubeGrid grid, IMyGridGroupData groupData, bool processBlocks = true)
        {
            Grid = (MyCubeGrid)grid;
            _groupData = groupData;

            Grid.OnMarkForClose += GridMarkedForClose;
            Grid.OnBlockAdded += BlockAddedEvent;
            Grid.OnBlockRemoved += BlockRemoved;
            if (Session.IsServer)
            {
                ((IMyCubeGrid)Grid).OnBlockIntegrityChanged += BlockIntegrityChanged;
                Grid.OnBlockOwnershipChanged += GridOwnershipChanged;
                Grid.OnStaticChanged += GridStaticChanged;
            }

            if (!processBlocks) return;

            InitializeCoreBlocks();
            InitializeNonCoreBlocks();
        }

        internal bool InitializeCoreBlocks()
        {
            var initializedCore = false;
            var blocks = new List<IMySlimBlock>();
            ((IMyCubeGrid)Grid).GetBlocks(blocks);

            var coreBlocks = blocks.Where(Utils.IsCoreBlock).ToList();
            foreach (var coreBlock in coreBlocks)
                initializedCore |= BlockAddedInternal(coreBlock);

            return initializedCore;
        }

        internal void InitializeNonCoreBlocks()
        {
            var blocks = new List<IMySlimBlock>();
            ((IMyCubeGrid)Grid).GetBlocks(blocks);

            var otherBlocks = blocks.Where(block => !Utils.IsCoreBlock(block)).ToList();
            foreach (var otherBlock in otherBlocks) BlockAddedInternal(otherBlock);
        }

        private void GridMarkedForClose(IngameIMyEntity entity)
        {
            if (entity != Grid) return;
            if (Session.IsServer) NotifyLocalGridCloseAuthoritative();
        }
    }
}
