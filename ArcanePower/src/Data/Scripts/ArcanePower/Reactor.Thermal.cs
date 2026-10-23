using System;
using Sandbox.ModAPI;
using VRageMath;

namespace ArcanePower
{
    public sealed partial class Reactor
    {
        private bool thermalRestoreFault;
        internal void FailThermalRuntime()
        {
            reactor.Enabled = false;
            if (nativeReactor != null) nativeReactor.Capacity = 0;
            if (Motion.Thermal != null)
            { Motion.Thermal.Faulted = true; Motion.Thermal.Diagnostic = "Runtime fault; heat inventory isolated and retained"; }
        }
        internal bool ThermalVariant { get { return IsLive && reactor.BlockDefinition.SubtypeName == "ArcanePower_Thermal_ReactorHousing"; } }
        internal bool ThermalInitialized { get { return ThermalVariant && motionInitialized && initializationFrames == 0 && !thermalRestoreFault && Motion.Thermal != null; } }
        internal double ThermalInternalCirculation
        {
            get { return ThermalInitialized && !Motion.PowerPaused && !Motion.Thermal.Faulted
                && (ThermalCanRun || Motion.Thermal.Store.HotMJ + Motion.Thermal.Store.WasteMJ > .001)
                ? ThermalMath.Clamp((Motion.PowerInputMW + (Motion.ReserveMJ > ContainmentMW / 60 ? ContainmentMW : 0)) / ContainmentMW, 0, 1) : 0; }
        }
        internal double ThermalHeatMW { get { return PowerMW[Motion.FuelTier - 1] / .40; } }
        internal double ThermalHotC { get { return Motion.FuelTier == 1 ? 650 : Motion.FuelTier == 2 ? 1000 : 2200; } }
        private bool ThermalNeedsPowerSupport
        {
            get { return ThermalVariant && Motion.Thermal != null && (!Motion.Thermal.Settled
                || (!ThermalCanRun && Motion.Thermal.Store.HotMJ + Motion.Thermal.Store.WasteMJ + Motion.Thermal.AttachedHeatMJ > .001)); }
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
            get { return ThermalVariant ? (float)(ThermalHeatMW * (Motion.Thermal != null && Motion.Thermal.Mode == ThermalMode.Standalone ? .20 : .78)) : PowerMW[Motion.FuelTier - 1]; }
        }
        private bool ThermalCold
        {
            get { return Motion.Thermal != null && Motion.Core == CorePhase.Off && Motion.Vent == VentPhase.Idle
                && !Motion.Critical && Motion.Heat <= CooldownHeat
                && Motion.Thermal.Store.HotMJ + Motion.Thermal.Store.WasteMJ + Motion.Thermal.AttachedHeatMJ <= .001; }
        }
        private bool ThermalManifoldPower
        {
            get { return !Motion.PowerPaused && (Motion.PowerInputMW >= ContainmentMW * .999 || Motion.ReserveMJ > ContainmentMW / 60); }
        }
        internal string ThermalModeTransitionHint
        {
            get { return Motion.Thermal.TransitionHint(ThermalCold, ThermalManifoldPower, ManifoldRigReady); }
        }

        private void InitializeThermalRuntime()
        {
            if (!ThermalVariant) return;
            if (Motion.Thermal == null) Motion.Thermal = new ThermalReactorState();
            if (Motion.Thermal.Store.EntityId == 0) Motion.Thermal.Store.EntityId = Id;
            if (thermalRestoreFault) reactor.Enabled = false;
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
                if (!Motion.Thermal.Settled) reactor.Enabled = false;
                // Movement requires delivered motor power or the existing paid
                // emergency reserve. The normal containment sink owns both.
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
                    && !Motion.Thermal.Faulted && ManifoldRigReady
                    && Motion.Thermal.Mode == ThermalMode.Brayton && Motion.Thermal.Deployment == 1);
        }

        internal void AccountThermalOutput()
        {
            var state = Motion.Thermal;
            if (reactor.CurrentOutput > 0 && !ThermalMath.Convert(state.Store, reactor.CurrentOutput / 60.0, .20))
            { state.Faulted = true; reactor.Enabled = false; state.Diagnostic = "Standalone output exceeded paid heat inventory; isolated"; }
        }

        internal void ProduceThermal(double flowMW)
        {
            if (!ThermalCanRun) return;
            var state = Motion.Thermal;
            // A finite warm inventory supplies the next native distribution
            // interval. No demand eventually fills it and stops fresh fuel use.
            double availableFuelMJ = ThermalHeatMW * 8;
            if (!MyAPIGateway.Session.CreativeMode)
            {
                double energyPerUnit = ThermalHeatMW * 600 * FuelEfficiency;
                double stock = (double)reactor.GetInventory().GetItemAmount(VRage.Game.ModAPI.Ingame.MyItemType.MakeIngot(Fuels[Motion.FuelTier - 1]));
                availableFuelMJ = Math.Max(0, (stock - Motion.FuelDebt) * energyPerUnit - state.FuelHeatMJ);
            }
            double admitted = ThermalMath.AdmitReactionHeat(state.Store, ThermalHeatMW,
                Math.Min(ThermalHeatMW, flowMW) * Motion.PowerRamp / 60, availableFuelMJ);
            state.FuelHeatMJ += admitted;
            state.ProducedMW = admitted * 60;
        }

        private void RefreshThermalCapacity()
        {
            if (!IsLive || nativeReactor == null || Motion.Thermal == null) return;
            var state = Motion.Thermal;
            double limit = ThermalCanRun && state.Mode == ThermalMode.Standalone
                ? ThermalMath.ExportLimit(state.Store, ThermalHeatMW * 8, .20, ThermalHeatMW * .20 * Motion.PowerRamp, 1.0 / 60) : 0;
            nativeReactor.Capacity = (float)(limit / 216000);
        }
    }
}
