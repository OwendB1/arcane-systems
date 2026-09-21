using System;
using System.Collections.Generic;
using System.Text;
using Sandbox.Game.Entities;
using Sandbox.ModAPI;

namespace ArcanePower
{
    public sealed partial class Reactor
    {
        private readonly List<ContainmentController> powerControllers = new List<ContainmentController>(2);
        private float ContainmentMW { get { return PowerMW[Motion.Profile - 2] * .0001f; } }
        private double ReserveCapacityMJ { get { return ContainmentMW * 90.0; } }

        private void UpdatePower()
        {
            bool server = MyAPIGateway.Multiplayer.IsServer;
            bool active = Motion.Core != CorePhase.Off || Motion.Vent != VentPhase.Idle;
            bool preparing = reactor.Enabled && reactor.IsFunctional && previousControllers >= 2 && HasUsableFuel();
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
            if (active && input < operating * .999f && Motion.Vent == VentPhase.Idle
                && (Motion.Core == CorePhase.Starting || Motion.Core == CorePhase.Running))
            {
                Motion.PowerStarved = true;
                reactor.Enabled = false;
                BeginShutdown();
            }
            if (!active && preparing && Motion.PowerReady) Motion.PowerStarved = false;
        }

    }
}
