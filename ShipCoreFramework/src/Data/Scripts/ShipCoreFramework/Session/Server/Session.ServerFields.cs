using System;
using System.Collections.Concurrent;
using NexusModAPI;
using VRage.Game.ModAPI;

namespace ShipCoreFramework
{
    public partial class Session
    {
        private static NexusAPI _myNexusApi;
        private static bool _startedNexus;
        private static bool _serverRuntimeDataLoaded;
        private static bool _sessionReady;
        private static bool _serverReadyDataLoaded;
        private int _serverSimulationBatchRunning;

        internal static bool HasStarted;
        internal static readonly Guid CoreStateStorageGUID =
            new Guid("a8807ad4-524d-441a-a89a-0671fbfb1dd3");
        internal static readonly ConcurrentDictionary<IMyGridGroupData, PhysicalSpeedCluster> PhysicalSpeedClusterDict =
            new ConcurrentDictionary<IMyGridGroupData, PhysicalSpeedCluster>();
    }
}
