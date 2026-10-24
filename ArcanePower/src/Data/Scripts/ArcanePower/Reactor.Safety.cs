using Sandbox.Game.Entities;
using Sandbox.ModAPI;

namespace ArcanePower
{
    public sealed partial class Reactor
    {
        private const float AutoEjectionIntegrity = .60f;
        private bool CanOperate { get { return reactor.IsFunctional && reactor.SlimBlock.BuildLevelRatio >= 1f
            && (Motion.VentReady || (!Motion.SecurityMode && Motion.Core == CorePhase.Running && Motion.Vent == VentPhase.Idle)); } }
        private bool NeedsAutoEjection { get { return !Motion.PayloadReleased && Motion.Core != CorePhase.Off
            && Motion.CoreTick >= 90 && reactor.SlimBlock.Integrity <= reactor.SlimBlock.MaxIntegrity * AutoEjectionIntegrity; } }

        private bool IsIntactController(VRage.Game.ModAPI.IMyCubeBlock block)
        {
            return block != null && !block.Closed && block.CubeGrid == reactor.CubeGrid
                && block.IsFunctional && block.SlimBlock.BuildLevelRatio >= 1f
                && block.GameLogic.GetAs<ContainmentController>() != null;
        }

        internal bool HasAdvancedController()
        {
            if (!IsLive) return false;
            var attached = ((MyCubeBlock)Entity).CurrentAttachedUpgradeModules;
            if (attached == null) return false;
            foreach (var entry in attached.Values)
                if (entry.Compatible && IsIntactController(entry.Block)
                    && entry.Block.BlockDefinition.SubtypeName == "ArcanePower_AdvancedContainmentController") return true;
            return false;
        }

        private bool HasIntactControllers()
        {
            var attached = ((MyCubeBlock)Entity).CurrentAttachedUpgradeModules;
            if (attached == null) return false;
            long first = 0;
            foreach (var entry in attached.Values)
            {
                var block = entry.Block;
                if (!entry.Compatible || !IsIntactController(block) || block.EntityId == first) continue;
                if (first != 0) return true;
                first = block.EntityId;
            }
            return false;
        }

        private void UpdateSafety()
        {
            if (!MyAPIGateway.Multiplayer.IsServer || initializationFrames > 0) return;
            Motion.ControllersReady = HasIntactControllers();
            if (NeedsAutoEjection && Motion.ControllersReady && Motion.VentReady && Motion.Vent == VentPhase.Idle)
                RequestVent(true);
        }

        internal void SetSecurityMode(bool enabled)
        {
            if (!MyAPIGateway.Multiplayer.IsServer || Motion.SecurityMode == enabled) return;
            Motion.SecurityMode = enabled;
            CheckVentRoute();
            RefreshFuelCapacity();
            PublishMotion();
        }
    }
}
