using System;
using System.Globalization;
using System.Text;
using ProtoBuf;

namespace ArcanePower
{
    // Read-only server measurements for each cooling block's native terminal.
    [ProtoContract]
    public sealed class ThermalCoolingState
    {
        [ProtoMember(1)] public long EntityId;
        [ProtoMember(2)] public long Sequence;
        [ProtoMember(3)] public double RatedMW;
        [ProtoMember(4)] public double AvailableMW;
        [ProtoMember(5)] public double PanelMW;
        [ProtoMember(6)] public double Clearance;
        [ProtoMember(7)] public double SunExposure;
        [ProtoMember(8)] public double AirDensity;
        [ProtoMember(9)] public int Panels = 1;
        [ProtoMember(10)] public bool Attached;
        [ProtoMember(11)] public string Fault;
        [ProtoMember(12)] public double StoredHeatMJ;
        [ProtoMember(13)] public double RejectedMW;
        [ProtoMember(14)] public bool Connected;
        [ProtoMember(15)] public bool Powered;

        public bool Valid(long id)
        {
            return EntityId == id && Sequence >= 0 && Panels >= 1 && Panels <= 3
                && ThermalMath.Finite(RatedMW) && RatedMW > 0 && RatedMW <= 300000
                && ThermalMath.Finite(AvailableMW) && AvailableMW >= 0 && AvailableMW <= RatedMW + .001
                && ThermalMath.Finite(PanelMW) && PanelMW >= 0 && PanelMW <= AvailableMW + .001
                && ThermalMath.Finite(Clearance) && Clearance >= 0 && Clearance <= 1
                && ThermalMath.Finite(SunExposure) && SunExposure >= 0 && SunExposure <= 1
                && ThermalMath.Finite(AirDensity) && AirDensity >= 0 && AirDensity <= 1
                && ThermalMath.Finite(StoredHeatMJ) && StoredHeatMJ >= 0
                && ThermalMath.Finite(RejectedMW) && RejectedMW >= 0 && RejectedMW <= RatedMW + .001
                && (Fault == null || Fault.Length <= 256);
        }
    }

    public abstract partial class ThermalBlock
    {
        private ThermalCoolingState coolingState;
        private long coolingSequence;
        private double airDensity;
        internal bool IsCooling { get { return IsRadiator || Spec.Kind == ThermalKind.AirCooler; } }

        internal ThermalCoolingState CaptureCooling()
        {
            if (!IsCooling) return null;
            if (RadiatorBase != null) RadiatorBase.UpdateEnvironment();
            else UpdateEnvironment();
            bool extension = Spec.Kind == ThermalKind.RadiatorPanel;
            bool attached = !extension || RadiatorBase != null;
            bool available = Healthy && attached && (!extension || RadiatorBase.Healthy)
                && (Spec.Kind != ThermalKind.AirCooler || !CoolingConnected || CoolingPowered);
            double rating = Spec.CoolingMW;
            foreach (var panel in RadiatorPanels) rating += panel.Spec.CoolingMW;
            var radiator = Store.Radiator;
            coolingState = new ThermalCoolingState {
                EntityId = Block.EntityId, Sequence = ++coolingSequence, RatedMW = rating,
                AvailableMW = available ? (extension ? PanelCoolingMW : coolingMW) : 0,
                PanelMW = available ? (IsRadiator ? PanelCoolingMW : coolingMW) : 0,
                Clearance = IsRadiator ? (radiator == null ? 0 : radiator.Exposure) : clearExhaust,
                SunExposure = radiator == null ? 0 : radiator.SunIncidence,
                AirDensity = extension && RadiatorBase != null ? RadiatorBase.airDensity : airDensity,
                Panels = 1 + RadiatorPanels.Count, Attached = attached,
                Fault = Fault ?? (extension && RadiatorBase != null ? RadiatorBase.Fault : null),
                StoredHeatMJ = Store.HotMJ + Store.WasteMJ,
                RejectedMW = extension && RadiatorBase != null
                    ? (RadiatorBase.coolingMW > 0 ? RadiatorBase.CoolingRejectedMW * PanelCoolingMW / RadiatorBase.coolingMW : 0)
                    : CoolingRejectedMW,
                Connected = extension && RadiatorBase != null ? RadiatorBase.CoolingConnected : CoolingConnected,
                Powered = extension && RadiatorBase != null ? RadiatorBase.CoolingPowered : CoolingPowered
            };
            return coolingState;
        }

        internal void ReceiveCooling(ThermalCoolingState state)
        {
            if (!IsCooling || state == null || !state.Valid(Block.EntityId)
                || (coolingState != null && state.Sequence <= coolingState.Sequence)) return;
            coolingState = state;
            Block.RefreshCustomInfo();
        }

        private void AppendCoolingInfo(StringBuilder info)
        {
            bool air = Spec.Kind == ThermalKind.AirCooler;
            bool extension = Spec.Kind == ThermalKind.RadiatorPanel;
            info.Append("\nARCANE POWER / ").AppendLine(air ? "ATMOSPHERIC COOLER" : extension ? "RADIATOR PANEL" : "SPACE RADIATOR");
            var state = coolingState;
            if (state == null) { info.AppendLine("Waiting for cooling readings"); return; }
            info.AppendLine(state.Fault != null ? "ISOLATED / " + state.Fault
                : !Block.IsFunctional || Block.SlimBlock.BuildLevelRatio < 1 ? "FINISH WELDING / REPAIR"
                : !Block.Enabled ? "SWITCHED OFF" : !state.Attached ? "UNATTACHED PANEL"
                : state.AvailableMW <= 0 ? "NO COOLING AVAILABLE" : "COOLING AVAILABLE");
            info.AppendLine("\nCOOLING");
            info.Append("Efficiency: ").AppendLine(CoolingPercent(state.AvailableMW / state.RatedMW));
            info.Append("Available: ").Append(CoolingPower(state.AvailableMW)).Append(" / ")
                .Append(CoolingPower(state.RatedMW)).AppendLine(" rated");
            info.Append("Stored heat: ").Append(state.StoredHeatMJ.ToString("0.0", CultureInfo.InvariantCulture)).AppendLine(" MJ");
            info.Append("Heat removed: ").AppendLine(CoolingPower(state.RejectedMW));
            info.AppendLine(!state.Connected ? "Circuit: disconnected / standby"
                : !state.Powered ? "Circuit: waiting for reactor auxiliary power" : "Circuit: connected");
            if (Spec.Kind == ThermalKind.Radiator)
            {
                info.Append("Panel stack: ").Append(state.Panels).AppendLine(" / 3");
                info.Append("Base panel: ").Append(CoolingPercent(state.PanelMW / Spec.CoolingMW))
                    .Append(" / ").AppendLine(CoolingPower(state.PanelMW));
            }
            if (extension) info.AppendLine(state.Attached ? "Link: attached to radiator axis" : "Link: stack above an aligned radiator and enable");
            if (IsRadiator && Store.Radiator != null)
            {
                info.Append("Panel angle: ").Append((Store.Radiator.Angle * 180 / Math.PI).ToString("0.0", CultureInfo.InvariantCulture)).AppendLine(" degrees");
                if (!extension) info.AppendLine("Tracking: automatic, edge-on to the sun");
            }
            info.AppendLine("\nENVIRONMENT");
            info.Append("Air density: ").AppendLine(CoolingPercent(state.AirDensity));
            if (air)
            {
                info.Append("Exhaust clearance: ").AppendLine(CoolingPercent(state.Clearance));
                info.Append("Airflow factor: ").AppendLine(CoolingPercent(state.Clearance * state.Clearance));
                if (state.AirDensity <= 0) info.AppendLine("Requires atmosphere.");
                if (state.Clearance < .999) info.AppendLine("Clear 2.5 m beyond both exhaust fans.");
            }
            else
            {
                info.Append("Clear sky: ").AppendLine(CoolingPercent(state.Clearance));
                info.Append("Solar exposure: ").AppendLine(CoolingPercent(state.SunExposure));
                info.Append("Solar cooling factor: ").AppendLine(CoolingPercent(ThermalRadiators.SolarEfficiency(state.SunExposure)));
                info.Append("Ambient cooling factor: ").AppendLine(CoolingPercent(
                    ThermalRadiators.AmbientEfficiency(state.AirDensity)));
                if (state.Clearance < .999) info.AppendLine("Expose both panel faces to open space.");
                if (Spec.Kind == ThermalKind.Radiator && state.Panels > 1)
                    info.AppendLine("Environment factors above describe the base panel.");
            }
            info.AppendLine("Available capacity follows the environment. Heat removal follows circuit demand and retained heat.");
        }

        private static string CoolingPercent(double value)
        { return (value * 100).ToString("0.#", CultureInfo.InvariantCulture) + "%"; }
        private static string CoolingPower(double mw)
        { return mw >= 1000 ? (mw / 1000).ToString("0.###", CultureInfo.InvariantCulture) + " GW" : mw.ToString("0.##", CultureInfo.InvariantCulture) + " MW"; }
    }
}
