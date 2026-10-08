using System.Collections.Generic;
using System.Threading;
using NexusModAPI;
using Sandbox.Game;
using Sandbox.ModAPI;
using VRage.Game;
using VRage.Game.ModAPI;

namespace ShipCoreFramework
{
    public partial class Session
    {
        private static void AppendInitialPhysicalGroups(List<IMyGridGroupData> groups)
        {
            var physicalGroups = new List<IMyGridGroupData>();
            MyAPIGateway.GridGroups.GetGridGroups(GridLinkTypeEnum.Physical, physicalGroups);
            groups.AddRange(physicalGroups);
        }

        private void LoadServerData()
        {
            HasStarted = false;
            _startedNexus = false;
            _serverRuntimeDataLoaded = false;
            _sessionReady = false;
            _serverReadyDataLoaded = false;
            Interlocked.Exchange(ref _serverSimulationBatchRunning, 0);
            MyAPIGateway.Multiplayer.RegisterSecureMessageHandler(CommandsSyncId, Commands.ServerMessageHandler);
            MyAPIGateway.Session.OnSessionReady += SessionReady;
            _myNexusApi = new NexusAPI(OnNexusEnabled);

            InitializeServerRuntimeData();
            Utils.Log("Ship Cores: Awaiting Commands From Clients", 1);
            Config.SaveConfig(broadcast: false);
        }

        private static void InitializeServerRuntimeData()
        {
            if (!IsServer || _serverRuntimeDataLoaded || Config?.SelectedNoCore == null) return;

            ApplyConfigToDefinitions();
            MyAPIGateway.Session.Factions.FactionStateChanged += FactionStateChanged;
            MyAPIGateway.Session.Factions.FactionCreated += FactionCreated;
            MyAPIGateway.Session.Factions.FactionEdited += FactionEdited;
            _serverRuntimeDataLoaded = true;
            if (_myNexusApi.Enabled)
                OnNexusEnabled();
            if (_sessionReady)
                InitializeServerReadyData();
        }

        internal static void ApplyServerConfig()
        {
            ModAPI.MarkConfigReady(!RuntimeInitialized);
            if (TryInitializeRuntime()) return;

            ApplyConfigToDefinitions();
            RefreshGroupsAfterConfigChanged();
            BroadcastConfigToClients();
        }

        private void UnloadServerData()
        {
            MyAPIGateway.Multiplayer.UnregisterSecureMessageHandler(CommandsSyncId, Commands.ServerMessageHandler);
            MyAPIGateway.Session.OnSessionReady -= SessionReady;

            if (_serverRuntimeDataLoaded)
            {
                MyAPIGateway.Session.Factions.FactionStateChanged -= FactionStateChanged;
                MyAPIGateway.Session.Factions.FactionCreated -= FactionCreated;
                MyAPIGateway.Session.Factions.FactionEdited -= FactionEdited;
                MyExplosions.OnExplosion -= CubeGridModifiers.HandleLightningExplosions;

                UntrackAllPhysicalGridGroups();
                LimitsNexusSync.Stop();

                ResetRuntimeStateSync();
                PerFactionManager.Reset();
                PerPlayerManager.Reset();
                PerManifestGroupManager.Reset();
            }

            if (_myNexusApi != null)
                _myNexusApi.Unload();
            _myNexusApi = null;
            _startedNexus = false;
            _serverRuntimeDataLoaded = false;
            _sessionReady = false;
            _serverReadyDataLoaded = false;
            Config.SaveConfig(broadcast: false);
        }
    }
}
