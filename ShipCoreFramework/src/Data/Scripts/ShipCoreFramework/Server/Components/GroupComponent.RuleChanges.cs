using System.Threading;
using Sandbox.ModAPI;

namespace ShipCoreFramework
{
    internal partial class GroupComponent
    {
        private int _punishmentStateRefreshQueued;

        internal void QueuePunishmentStateRefresh()
        {
            if (!Session.IsServer || _closing || Deactivated || Session.IsShuttingDown || IsInitializingGrids) return;
            if (Interlocked.CompareExchange(ref _punishmentStateRefreshQueued, 1, 0) != 0) return;
            try
            {
                MyAPIGateway.Utilities.InvokeOnGameThread(RunQueuedPunishmentStateRefresh);
            }
            catch
            {
                Interlocked.Exchange(ref _punishmentStateRefreshQueued, 0);
                throw;
            }
        }

        private void RunQueuedPunishmentStateRefresh()
        {
            Interlocked.Exchange(ref _punishmentStateRefreshQueued, 0);
            if (_closing || Session.IsShuttingDown || IsInitializingGrids) return;
            RefreshPunishmentState();
            RefreshModifierStateCacheIfNeeded();
            ApplyModifiers(Modifiers);
            RefreshDefenseModifierCache();
        }

        internal void OnOwnershipOrMobilityChanged()
        {
            if (_closing || Session.IsShuttingDown) return;
            InvalidateGameThreadStateCache(false);
            InvalidateModifierStateCache();
            InvalidateSpeedStateCache();
            Session.MarkPhysicalSpeedClusterSourceDirty(this);
            Session.MarkRuntimeStateDirty(this);
            QueuePunishmentStateRefresh();
        }
    }
}
