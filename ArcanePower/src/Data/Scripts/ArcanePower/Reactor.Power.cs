using System;
using System.Collections.Generic;
using System.Text;
using Sandbox.Game.Entities;
using Sandbox.ModAPI;

namespace ArcanePower
{
    public sealed partial class Reactor
    {
        private bool CanPrepareContainment
        {
            get { return CanOperate && reactor.Enabled && !thermalStartRequested && previousControllers >= 2
                && HasIntactControllers() && HasUsableFuel(); }
        }

        internal bool NeedsStorageSupport
        {
            get { return motionInitialized && initializationFrames == 0 && IsLive && (Motion.Vent != VentPhase.Idle
                || Motion.Core == CorePhase.Cooling || Motion.Core == CorePhase.Stopping
                || Motion.Core == CorePhase.Starting
                || (Motion.Core == CorePhase.Off && CanPrepareContainment) || ThermalNeedsPowerSupport); }
        }
        private readonly List<ContainmentController> powerControllers = new List<ContainmentController>(2);
        private float ContainmentMW { get { return PowerMW[Motion.FuelTier - 1] * .0001f; } }
        private double ReserveCapacityMJ { get { return ContainmentMW * 90.0; } }

        // Presentation uses the same replicated reserve/input values as power
        // accounting. Requested power alone must never imply charging progress.
        private bool Precharging
        {
            get { return receivedState && initializationFrames == 0 && reactor.Enabled
                && Motion.Core == CorePhase.Off && Motion.Vent == VentPhase.Idle
                && Motion.Status == ReactorStatus.Active && Motion.ControllersReady && Motion.VentReady
                && !Motion.PowerReady && !Motion.PowerPaused && !Motion.Critical && !Motion.TileStarved
                && (Motion.Thermal == null || (Motion.Thermal.Settled && !Motion.Thermal.Faulted)); }
        }
        private double PrechargeMW
        {
            get { return Precharging ? Math.Max(0, Motion.PowerInputMW - ContainmentMW) : 0; }
        }

        private void UpdatePower()
        {
            bool server = MyAPIGateway.Multiplayer.IsServer;
            bool active = Motion.Core != CorePhase.Off || Motion.Vent != VentPhase.Idle
                || (ThermalVariant && Motion.Thermal != null && !Motion.Thermal.Settled);
            bool preparing = CanPrepareContainment;
            float operating = active || preparing ? ContainmentMW : 0;
            float charging = preparing && Motion.Vent == VentPhase.Idle
                ? (float)Math.Min(ContainmentMW * 3, Math.Max(0, ReserveCapacityMJ - Motion.ReserveMJ) * 60) : 0;
            Motion.PowerDemandMW = operating + charging;
            powerControllers.Clear();
            var attached = ((MyCubeBlock)Entity).CurrentAttachedUpgradeModules;
            if (attached != null)
                foreach (var entry in attached.Values)
                {
                    if (!entry.Compatible || entry.Block == null || entry.Block.Closed || !entry.Block.IsFunctional) continue;
                    var controller = entry.Block.GameLogic.GetAs<ContainmentController>();
                    if (controller != null && !powerControllers.Contains(controller)) powerControllers.Add(controller);
                }
            float input = 0;
            foreach (var controller in powerControllers)
                input += controller.Request(Id, Motion.PowerDemandMW / Math.Max(2, powerControllers.Count));
            // Request once before measuring: a newly created sink has no previous
            // distributed interval yet. Do not mistake that for a running-grid outage.
            if (!server || initializationFrames > 0) return;
            Motion.PowerInputMW = Math.Max(0, input);
            Motion.ReserveMJ = Math.Min(ReserveCapacityMJ, Motion.ReserveMJ);
            double deficit = Math.Max(0, operating - input) / 60.0;
            bool reserveCovers = Motion.ReserveMJ + .000001 >= deficit;
            // Only actual native input can charge the reserve. It never exports
            // electricity, starts the reactor, or restores itself on reload.
            if (operating > 0)
                Motion.ReserveMJ = Math.Max(0, Math.Min(ReserveCapacityMJ, Motion.ReserveMJ
                    + (active ? input - operating : Math.Max(0, input - operating)) / 60.0));
            Motion.PowerPaused = active && !reserveCovers;
            Motion.PowerReady = powerControllers.Count >= 2 && input >= ContainmentMW * .999f
                && Motion.ReserveMJ >= ReserveCapacityMJ * .999999;
            // Let the first thermal dispatch reach the native distributor and
            // controller sinks. End recovery on measured input after two frames,
            // or after two seconds at most. Every bridged MJ is debited above.
            bool restoringPower = reloadPowerFrames > 0 && reactor.Enabled && !Motion.PowerStarved && !Motion.Critical;
            if (reloadPowerFrames > 0)
            {
                if (!restoringPower || (reloadPowerFrames < 119 && input >= operating * .999f)) reloadPowerFrames = 0;
                else reloadPowerFrames--;
            }
            if (active && input < operating * .999f && Motion.Vent == VentPhase.Idle
                && (Motion.Core == CorePhase.Starting || Motion.Core == CorePhase.Running)
                && !(restoringPower && reserveCovers))
            {
                Motion.PowerStarved = true;
                reactor.Enabled = false;
                BeginShutdown();
            }
            if (!active && preparing && Motion.PowerReady) Motion.PowerStarved = false;
        }

    }
}
