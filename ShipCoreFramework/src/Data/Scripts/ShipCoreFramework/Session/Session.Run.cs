using System;
using System.Collections.Generic;
using Sandbox.ModAPI;
using VRage.Game.Components;
using VRage.Game.ModAPI;

namespace ShipCoreFramework
{
    [MySessionComponentDescriptor(MyUpdateOrder.AfterSimulation, 0)]
    public partial class Session : MySessionComponentBase
    {
        private static bool _runtimeInitialized;
        internal static bool RuntimeInitialized => _runtimeInitialized;

        public override void BeforeStart()
        {
            ModAPI.Initialize();
            TryInitializeRuntime();
        }

        internal static bool TryInitializeRuntime()
        {
            if (_runtimeInitialized || Config?.SelectedNoCore == null) return false;
            if (IsServer)
                InitializeServerRuntimeData();
            _runtimeInitialized = true;
            MyAPIGateway.GridGroups.OnGridGroupCreated += GridGroupsOnOnGridGroupCreated;
            MyAPIGateway.GridGroups.OnGridGroupDestroyed += GridGroupsOnOnGridGroupDestroyed;
            
            var initialMechanicalGroups = new List<IMyGridGroupData>();
            MyAPIGateway.GridGroups.GetGridGroups(GridLinkTypeEnum.Mechanical, initialMechanicalGroups);
            var initialPhysicalGroups = new List<IMyGridGroupData>();
            if (IsServer)
                AppendInitialPhysicalGroups(initialPhysicalGroups);
            Utils.Log("BeforeStart: found " + (initialMechanicalGroups.Count + initialPhysicalGroups.Count) +
                      " grid groups for initial scan.", 1);

            IsInitialGroupScan = true;
            try
            {
                MyAPIGateway.Parallel.ForEach(initialMechanicalGroups, group =>
                {
                    GridGroupsOnOnGridGroupCreated(group);
                });

                // Physical clusters resolve their members through GroupDict, so this pass must stay second.
                MyAPIGateway.Parallel.ForEach(initialPhysicalGroups, group =>
                {
                    GridGroupsOnOnGridGroupCreated(group);
                });
            }
            finally
            {
                IsInitialGroupScan = false;
            }

            if (IsServer)
            {
                ModAPI.MarkRuntimeSnapshotReady();
                BroadcastConfigToClients();
            }
            return true;
        }
        
        public override void LoadData()
        {
            GameThreadId = Environment.CurrentManagedThreadId;
            IsShuttingDown = false;
            _tick = 0;
            CurrentTick = 0;
            _runtimeInitialized = false;
            MpActive = MyAPIGateway.Multiplayer.MultiplayerActive;
            IsServer = (MpActive && MyAPIGateway.Multiplayer.IsServer) || !MpActive;
            IsClient = (MpActive && !MyAPIGateway.Utilities.IsDedicated) || !MpActive;
            ResetConfigSyncState();
            ModAPI.ResetReadiness();

            if (Networking == null)
                Networking = new Networking(32124);
            Networking.Register();
            var loadedConfig = new ModConfig();
            loadedConfig.LoadConfig(IsServer);
            Config = loadedConfig;
            if (IsServer)
            {
                if (Config.SelectedNoCore != null)
                    ModAPI.MarkConfigReady();
                else
                    ModAPI.MarkConfigUnavailable(Config.GetNoCoreConfigurationError());
            }
            if (IsClient)
                LoadClientData();
            if (IsServer)
                LoadServerData();

            Utils.Log("LoadData: MpActive=" + MpActive + ", IsServer=" + IsServer +
                      ", IsClient=" + IsClient + ", Dedicated=" + MyAPIGateway.Utilities.IsDedicated + ".", 1);
            if (IsClient && !IsServer && MpActive)
            {
                BeginConfigSync();
            }
        }

        protected override void UnloadData()
        {
            Utils.Log("UnloadData: shutting down Ship Core Framework session.", 1);
            IsShuttingDown = true;
            
            try //Because this throws a NRE in keen code if you alt-F4
            {
                MyAPIGateway.GridGroups.OnGridGroupCreated -= GridGroupsOnOnGridGroupCreated;
                MyAPIGateway.GridGroups.OnGridGroupDestroyed -= GridGroupsOnOnGridGroupDestroyed;
            }
            catch { /**/ }

            if (IsClient)
                UnloadClientData();
            if (IsServer)
                UnloadServerData();

            RevertAmmoSpeedAdjustments();
            ModAPI.Close();
            Networking?.Unregister();
            Networking = null;
            ResetConfigSyncState();
            
            foreach (var kvp in GroupDict)
            {
                kvp.Value.Clean();
            }
            GroupComponent.ClearPendingMergeValidations();
            GroupDict.Clear();
            _runtimeInitialized = false;
            GameThreadId = 0;
            Utils.Log("UnloadData: Ship Core Framework session unloaded.", 1);
        }
        
        public override void UpdateAfterSimulation()
        {
            RunConfigSyncTick();
            if (!ConfigSyncReady) return;
            if (!_runtimeInitialized || Config?.SelectedNoCore == null) return;

            _tick++;
            CurrentTick = _tick;
            if (IsClient)
                RunClientSimulationTick();

            if (!IsServer) return;
            if (!HasStarted) HasStarted = true;
            RunServerSimulationTick();
        }
    }
}
