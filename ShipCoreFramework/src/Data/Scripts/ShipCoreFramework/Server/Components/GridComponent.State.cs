using System.Collections.Concurrent;
using VRage.Game.ModAPI;

namespace ShipCoreFramework
{
    internal partial class GridComponent
    {
        private ConcurrentDictionary<BlockLimit, LimitBucket> _limits =
            new ConcurrentDictionary<BlockLimit, LimitBucket>();

        internal ConcurrentDictionary<BlockLimit, LimitBucket> Limits => _limits;

        internal readonly ConcurrentDictionary<IMyCubeBlock, BeaconComponent> BeaconDictionary =
            new ConcurrentDictionary<IMyCubeBlock, BeaconComponent>();

        private readonly ConcurrentDictionary<IMyCubeBlock, UpgradeModuleComponent> _upgradeModuleDictionary =
            new ConcurrentDictionary<IMyCubeBlock, UpgradeModuleComponent>();

        private readonly ConcurrentDictionary<long, byte> _trackedConnectorIds =
            new ConcurrentDictionary<long, byte>();

        internal void PublishLimitsSnapshot(ConcurrentDictionary<BlockLimit, LimitBucket> limits)
        {
            System.Threading.Interlocked.Exchange(ref _limits,
                limits ?? new ConcurrentDictionary<BlockLimit, LimitBucket>());
        }

        private static void NotifyLocalGridCloseAuthoritative()
        {
            LimitsNexusSync.NotifyLocalGridClose();
        }

        private void GridOwnershipChanged(Sandbox.Game.Entities.MyCubeGrid grid)
        {
            GroupComponent?.OnOwnershipOrMobilityChanged();
        }

        private void GridStaticChanged(Sandbox.Game.Entities.MyCubeGrid grid, bool isStatic)
        {
            GroupComponent?.OnOwnershipOrMobilityChanged();
        }
    }
}
