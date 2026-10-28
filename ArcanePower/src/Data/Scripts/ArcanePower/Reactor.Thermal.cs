using System;
using Sandbox.ModAPI;
using VRageMath;

namespace ArcanePower
{
    public sealed partial class Reactor
    {
        private bool thermalRestoreFault;
        private bool thermalStartRequested;
        private double reservedThermalMJ;
        private ThermalOutputGrant standaloneGrant;
        private int thermalAccountedAt = -1;
        internal void FailThermalRuntime()
        {
            StopForLoopLoss();
            if (Motion.Thermal != null)
            { Motion.Thermal.Faulted = true; Motion.Thermal.Diagnostic = "Runtime fault; generation stopped, cooling retained"; }
        }
        internal bool ThermalVariant { get { return IsLive && reactor.BlockDefinition.SubtypeName == "ArcanePower_Thermal_ReactorHousing"; } }
        internal bool ThermalInitialized { get { return ThermalVariant && motionInitialized && initializationFrames == 0 && !thermalRestoreFault && Motion.Thermal != null; } }
        private bool ThermalFuelModeReady
        {
            get { return Motion.Thermal != null && Motion.Thermal.Settled
                && (Motion.Thermal.Mode != ThermalMode.Brayton || HasAdvancedController()); }
        }
        internal double ThermalVisualLoad
        {
            get { return ThermalInitialized ? ThermalMath.Clamp(Motion.Thermal.ProducedMW / ThermalHeatMW, 0, 1) : 0; }
        }
        internal bool ThermalAuxiliaryReady { get { return ThermalManifoldPower; } }
        internal double ThermalHeatMW { get { return ThermalMath.FuelRatingMW(Motion.FuelTier); } }
        internal double ThermalHotC { get { return Motion.FuelTier == 1 ? 650 : Motion.FuelTier == 2 ? 1000 : 2200; } }
        private bool ThermalNeedsPowerSupport
        {
            get { return ThermalVariant && Motion.Thermal != null && (!Motion.Thermal.Settled
                || (!ThermalCanRun && Motion.Thermal.Store.HotMJ + Motion.Thermal.RetainedHeatMJ + Motion.Thermal.AttachedHeatMJ > .001)); }
        }
        internal bool ThermalCanRun
        {
            get { return ThermalInitialized && Motion.Thermal.Settled && reactor.Enabled && CanOperate
                && Motion.Core == CorePhase.Running && !Motion.PowerPaused && !Motion.TileStarved && !Motion.Critical
                && !Motion.Thermal.Faulted && (Motion.Thermal.Mode != ThermalMode.Brayton || ManifoldRigReady)
                && Motion.Vent == VentPhase.Idle && HasUsableFuel(); }
        }
        private float ElectricalRatingMW
        {
            get { return ThermalVariant ? (float)(ThermalHeatMW * (Motion.Thermal != null && Motion.Thermal.Mode == ThermalMode.Standalone ? ThermalMath.StandaloneEfficiency : ThermalMath.BraytonEfficiency)) : PowerMW[Motion.FuelTier - 1]; }
        }
        private bool ThermalCold
        {
            get { return Motion.Thermal != null && Motion.Core == CorePhase.Off && Motion.Vent == VentPhase.Idle
                && !Motion.Critical && Motion.Heat <= CooldownHeat
                && Motion.Thermal.Store.HotMJ + Motion.Thermal.RetainedHeatMJ + Motion.Thermal.AttachedHeatMJ <= .001; }
        }
        private bool ThermalManifoldPower
        {
            get { return !Motion.PowerPaused && (Motion.PowerInputMW >= ContainmentMW * .999 || Motion.ReserveMJ > ContainmentMW / 60); }
        }
        internal string ThermalModeTransitionHint
        {
            get { return Motion.Thermal.Requested == ThermalMode.Brayton && !HasAdvancedController()
                ? "Brayton locked: install or repair an advanced controller; keep cooldown power supplied"
                : Motion.Thermal.TransitionHint(ThermalCold, ThermalManifoldPower, ManifoldRigReady); }
        }

        private void InitializeThermalRuntime()
        {
            if (!ThermalVariant) return;
            if (Motion.Thermal == null) Motion.Thermal = new ThermalReactorState();
            if (Motion.Thermal.Store.EntityId == 0) Motion.Thermal.Store.EntityId = Id;
            if (MyAPIGateway.Multiplayer.IsServer)
            {
                bool legacy = Motion.Thermal.LoopVersion == 0 && Motion.Thermal.Mode == ThermalMode.Brayton;
                if (Motion.Thermal.Loops == null) Motion.Thermal.Loops = ThermalLoops.Empty();
                Motion.Thermal.MigrateHeat();
                foreach (var loop in Motion.Thermal.Loops) loop.Connected = false;
                // A saved diagnostic is not a new manual startup attempt.
                Motion.Thermal.LoopTrip = false;
                if (Motion.Thermal.Faulted)
                    Motion.Thermal.Diagnostic = "Reactor runtime fault; update a circuit block to recheck; heat retained";
                // Revalidate topology after reload. Preserve every MJ and the
                // critical-core state during network migration.
                if (legacy)
                {
                    Motion.Thermal.Diagnostic = "Split old shared plumbing into four independent manifold circuits; restart manually";
                    StopForLoopLoss();
                }
            }
            if (thermalRestoreFault) reactor.Enabled = false;
        }

        internal void StopForLoopLoss()
        {
            reactor.Enabled = false;
            if (nativeReactor != null) nativeReactor.Capacity = 0;
            BeginShutdown();
        }

        internal void RecheckThermalFault()
        {
            if (!Motion.Thermal.Faulted || thermalRestoreFault || reactor.Enabled || reactor.CurrentOutput != 0
                || Motion.Critical || Motion.Vent != VentPhase.Idle || Motion.EntityId != Id || !Valid(Motion)) return;
            Motion.Thermal.Faulted = false;
            Motion.Thermal.Diagnostic = "Runtime rechecked; restart manually when a circuit is ready";
        }

        private void ThermalEnabledChanged(IMyTerminalBlock block)
        {
            if (!MyAPIGateway.Multiplayer.IsServer) return;
            // Restored Enabled state is loaded before this event is subscribed.
            // Internal safety paths only disable the reactor; an explicit On
            // action while Off is the startup request, including toolbar/PB On.
            thermalStartRequested = ThermalVariant && Motion.Thermal != null && reactor.Enabled
                && Motion.Core == CorePhase.Off && Motion.Vent == VentPhase.Idle
                && Motion.Thermal.Settled && Motion.Thermal.Mode == ThermalMode.Brayton;
        }

        internal void CheckLoopSafety()
        {
            var state = Motion.Thermal;
            if (state.Faulted)
            {
                // A generation/accounting fault must stop the core even though
                // ThermalCanRun is already false. Keep valid cooling paths open.
                StopForLoopLoss();
                return;
            }
            bool start = thermalStartRequested;
            thermalStartRequested = false;
            if (start && reactor.Enabled && Motion.Core == CorePhase.Off
                && state.Settled && state.Mode == ThermalMode.Brayton)
            {
                // One valid sealed circuit is enough to start at its normal
                // quarter allocation; output follows grid demand.
                state.LoopTrip = state.ConnectedLoops == 0;
                if (state.LoopTrip) StopForLoopLoss();
            }
            else if (ThermalCanRun && state.ConnectedLoops == 0)
                StopForLoopLoss(); // Running loss stops safely without a startup latch.
        }

        internal bool ManifoldRigReady
        {
            get
            {
                foreach (int bay in new[] { 0, 1, 2, 3 })
                    foreach (string part in ThermalManifolds.Parts)
                    {
                        string name = ThermalManifolds.Name(bay, part);
                        Matrix rest;
                        if (!restPoses.TryGetValue(name, out rest) || !ThermalManifolds.CompatibleRest(rest)
                            || !((VRage.Game.Entity.MyEntity)Entity).Subparts.ContainsKey(name)) return false;
                    }
                return true;
            }
        }

        internal void RequestThermalMode(ThermalMode mode)
        {
            if (!MyAPIGateway.Multiplayer.IsServer || !ThermalInitialized || mode < ThermalMode.Standalone || mode > ThermalMode.Brayton) return;
            if (mode == ThermalMode.Brayton && !HasAdvancedController())
            { Motion.Thermal.Diagnostic = "Brayton requires at least one fully built, functional advanced controller"; PublishMotion(); return; }
            if (mode == ThermalMode.Brayton && !ManifoldRigReady)
            { Motion.Thermal.Diagnostic = "Native manifold subparts are missing or use incompatible origins"; PublishMotion(); return; }
            if (Motion.Thermal.Requested == mode) return;
            Motion.Thermal.Requested = mode;
            reactor.Enabled = false;
            BeginShutdown();
            RefreshFuelCapacity(); PublishMotion();
        }

        private void UpdateThermalMode()
        {
            if (!ThermalVariant || Motion.Thermal == null) return;
            if (MyAPIGateway.Multiplayer.IsServer)
            {
                if (Motion.Thermal.Faulted) StopForLoopLoss();
                if (!ThermalFuelModeReady) reactor.Enabled = false;
                // Movement requires delivered motor power or the existing paid
                // emergency reserve. The normal containment sink owns both.
                // Controller loss stops generation/deployment, but preserves
                // hot connected cooling. Retraction still requires a cold core.
                if (Motion.Thermal.Requested != ThermalMode.Brayton || HasAdvancedController())
                    Motion.Thermal.AdvanceManifolds(ThermalCold, ThermalManifoldPower, ManifoldRigReady, 1.0 / 60);
            }
            if (!MyAPIGateway.Utilities.IsDedicated && ManifoldRigReady)
                for (int bay = 0; bay < 4; bay++)
                    foreach (string part in ThermalManifolds.Parts)
                        Part(ThermalManifolds.Name(bay, part), ThermalManifolds.Pose(bay, part, Motion.Thermal.Deployment));
        }

        internal ThermalEndpoint ThermalEndpoint()
        {
            var spec = ThermalModels.All["ArcanePower_Thermal_ReactorHousing"];
            Matrix rotation;
            reactor.Orientation.GetMatrix(out rotation);
            Vector3 centre = ((VRage.Game.Entity.MyEntity)Entity).PositionComp.LocalMatrixRef.Translation;
            return ArcanePower.ThermalEndpoint.At(Id, reactor.CubeGrid.EntityId, spec, rotation, centre,
                reactor.IsFunctional && reactor.SlimBlock.BuildLevelRatio >= 1 && reactor.OwnerId != 0
                    && reactor.CubeGrid.Physics != null
                    && ManifoldRigReady
                    && Motion.Thermal.Mode == ThermalMode.Brayton && Motion.Thermal.Deployment == 1);
        }

        internal void BeginThermalFrame()
        {
            Motion.Thermal.BeginFrame();
            reservedThermalMJ = 0;
        }

        internal void AccountThermalOutput()
        {
            int now = MyAPIGateway.Session.GameplayFrameCounter;
            if (thermalAccountedAt == now) return;
            thermalAccountedAt = now;
            var grant = standaloneGrant;
            standaloneGrant = null;
            if (grant != null && !grant.Settle(reactor.CurrentOutput)) FailThermalRuntime();
            else if (grant == null && reactor.CurrentOutput > .001) FailThermalRuntime();
        }

        internal ThermalOutputGrant ReserveThermalOutput(ThermalLoopState loop, double heatMW, double efficiency)
        {
            if (!ThermalCanRun || efficiency <= 0 || efficiency >= 1 || !ThermalMath.Finite(heatMW)) return null;
            double wanted = Math.Max(0, Math.Min(heatMW * Motion.PowerRamp / 60,
                ThermalHeatMW / 60 - reservedThermalMJ));
            // Refill only a one-interval paid reserve. Unused credit stays saved;
            // no-demand operation stops buying fuel once this small reserve is full.
            ProduceThermal(Math.Max(0, reservedThermalMJ + wanted - Motion.Thermal.Store.HotMJ) * 60);
            PayFuel(false);
            double available = Math.Max(0, Math.Min(wanted, Motion.Thermal.Store.HotMJ - reservedThermalMJ));
            reservedThermalMJ += available;
            return new ThermalOutputGrant(Motion.Thermal, loop, available, efficiency);
        }

        internal void GrantStandaloneOutput()
        {
            standaloneGrant = Motion.Thermal.Mode == ThermalMode.Standalone
                ? ReserveThermalOutput(null, ThermalHeatMW, ThermalMath.StandaloneEfficiency) : null;
            RefreshThermalCapacity();
        }

        internal void ProduceThermal(double flowMW)
        {
            if (!ThermalCanRun) return;
            var state = Motion.Thermal;
            // This is fuel credit for the next native interval, not a flow or
            // reaction buffer. Reaction telemetry is measured when output settles.
            double availableFuelMJ = ThermalHeatMW * 8;
            if (!MyAPIGateway.Session.CreativeMode)
            {
                double energyPerUnit = ThermalHeatMW * FuelFullLoadMinutes * 60 * FuelEfficiency;
                double stock = (double)reactor.GetInventory().GetItemAmount(VRage.Game.ModAPI.Ingame.MyItemType.MakeIngot(Fuels[Motion.FuelTier - 1]));
                availableFuelMJ = Math.Max(0, (stock - Motion.FuelDebt) * energyPerUnit - state.FuelHeatMJ);
            }
            double admitted = ThermalMath.AdmitHeat(state.Store, ThermalHeatMW / 60,
                Math.Max(0, flowMW) / 60, availableFuelMJ);
            state.FuelHeatMJ += admitted;
        }

        private void RefreshThermalCapacity()
        {
            if (!IsLive || nativeReactor == null || Motion.Thermal == null) return;
            var state = Motion.Thermal;
            double limit = ThermalCanRun && state.Mode == ThermalMode.Standalone && standaloneGrant != null
                ? standaloneGrant.MaximumMW : 0;
            nativeReactor.Capacity = (float)(limit / 216000);
        }
    }
}
