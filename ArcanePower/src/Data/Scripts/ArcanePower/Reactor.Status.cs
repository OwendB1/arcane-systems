using System;
using System.Globalization;
using System.Collections.Generic;
using System.Text;
using Sandbox.ModAPI;
using VRage.Game.ModAPI.Ingame;

namespace ArcanePower
{
    public sealed partial class Reactor
    {
        // LCD, tablet and native terminal text share live values and warning priority.
        internal StatusReport ReadStatus(bool detailed)
        {
            var text = new StatusReport { Name = reactor.CustomName, Fuel = FuelNames[Motion.FuelTier - 1], Heat = Motion.Heat,
                HeatTone = Motion.Critical ? "red" : Motion.ThermalWarning ? "yellow" : "white",
                Reserve = Math.Min(1, Math.Max(0, Motion.ReserveMJ / ReserveCapacityMJ)), Load = Motion.Load, Precharging = Precharging,
                Brayton = ThermalVariant && Motion.Thermal != null && Motion.Thermal.Mode == ThermalMode.Brayton };
            bool creative = MyAPIGateway.Session.CreativeMode;
            double fuel = (double)reactor.GetInventory().GetItemAmount(MyItemType.MakeIngot(Fuels[Motion.FuelTier - 1]));
            int[] tileStock = SpareTileQuartets();
            double tiles = (tileStock[0] + tileStock[1] + tileStock[2]) * 4;
            int needed = NeededTileQuartets() * 4;
            string action;
            string tone;
            string status = OperatingStatus(out action, out tone);
            text.State = status; text.Tone = tone;
            if (!string.IsNullOrEmpty(action)) Line(text, tone, action);
            int hazards;
            float fuse = CoreHazards.EjectedCountdown(Id, out hazards);
            if (hazards > 0)
                Line(text, "red", "EJECTED CORE" + (hazards > 1 ? "S (" + hazards + ")" : "")
                    + "  /  detonation ~" + Number(fuse, "0.0") + " s");

            Section(text, "POWER");
            double output = ThermalVariant && Motion.Thermal != null ? Motion.Thermal.NetOutputMW : reactor.CurrentOutput;
            Row(text, "Output", Power(output) + " / " + Power(ThermalVariant && Motion.Thermal != null ? Motion.Thermal.SupportedMW : PowerMW[Motion.FuelTier - 1]));
            Row(text, "Net", Power(output - Motion.PowerInputMW));
            if (text.Precharging)
            {
                double charge = PrechargeMW;
                Row(text, "Startup charge", Number(Math.Floor(text.Reserve * 100), "0") + "%");
                Row(text, "Charge rate", Power(charge) + " net");
                Row(text, "Charge ETA", Motion.ReserveMJ >= ReserveCapacityMJ * .999999 ? "Reserve full"
                    : charge > .000001 ? "~" + Duration(Math.Max(0, ReserveCapacityMJ - Motion.ReserveMJ) / charge)
                    : "Waiting for surplus power");
            }
            if (ThermalVariant && Motion.Thermal != null)
            {
                var thermal = Motion.Thermal;
                Section(text, "THERMAL PLANT");
                Row(text, "Conversion mode", thermal.Mode + (thermal.Settled ? "" : " -> " + thermal.Requested + " / shutdown, drain, move, restart"));
                Row(text, "Brayton access", HasAdvancedController() ? "Advanced controller installed" : "Locked / install an advanced controller",
                    HasAdvancedController() ? "white" : "yellow");
                Row(text, "Fuel safety", "Standalone: Aether only / Helion and Empyrean require Brayton");
                Row(text, "Manifolds", Percent(thermal.Deployment) + " deployed");
                Row(text, "Conversion efficiency", Percent(thermal.Efficiency));
                Row(text, "Reaction heat", Power(thermal.ProducedMW) + " / " + Power(ThermalHeatMW));
                Row(text, "Accumulated heat", Number(thermal.RetainedHeatMJ, "0.0") + " MJ");
                Row(text, "Circuits available", thermal.ConnectedLoops + " / 4 (" + thermal.ConnectedLoops * 25 + "% allocation)");
                if (text.Brayton)
                {
                    bool shortfall = Array.Exists(thermal.Loops, loop => loop.RequiredCoolingMW > loop.CoolingMW + .001);
                    Row(text, "Cooling capacity", Power(thermal.CoolingMW), shortfall ? "yellow" : "white");
                    Row(text, "Cooling required", Power(thermal.RequiredCoolingMW) + " at current load");
                    Row(text, "Full-load cooling", Power(thermal.DesignCoolingMW));
                    Row(text, "Heat removed", Power(thermal.RejectedMW));
                    byte valves = ThermalLoops.OpenValves(thermal);
                    for (int i = 0; i < thermal.Loops.Length; i++)
                    {
                        var loop = thermal.Loops[i];
                        Row(text, "Circuit " + (i + 1), (loop.Connected ? "Ready" : "Unavailable")
                            + " / valve " + ((valves & (1 << i)) != 0 ? "open" : "closed"),
                            loop.Connected ? "white" : "yellow");
                        Line(text, "muted", loop.Diagnostic + " / cooling " + Power(loop.CoolingMW) + " / required " + Power(loop.RequiredCoolingMW) + " / retained " + Number(loop.ExcessMJ, "0.0") + " MJ");
                    }
                }
                Line(text, thermalRestoreFault || thermal.Faulted ? "red" : "muted", thermal.Diagnostic);
                Line(text, "muted", "Setup: one turbine and cooling per manifold circuit. Keep circuits separate; cap unused pipe mouths and match H/C.");
                Line(text, "muted", "Each circuit supplies up to 25% capacity. Retained waste still triggers the existing failure at 125% heat.");
                Line(text, "muted", "Construction guide: aim at thermal blocks or select them in build mode. Verify build, then deployment, cooling and startup power.");
                Section(text, "POWER");
            }
            if (detailed)
                Row(text, "Ramp", Percent(Motion.PowerRamp) + "   Reaction load " + Percent(Motion.Load));
            if (detailed || text.Precharging)
                Row(text, "Containment", Power(Motion.PowerInputMW) + " / " + Power(Motion.PowerDemandMW) + " requested");

            Section(text, "CONTAINMENT");
            Row(text, "Security mode", Motion.SecurityMode ? "On / vent loss shuts down" : "Off / vent loss warns", Motion.SecurityMode ? "white" : "yellow");
            Row(text, "Integrity", Percent(reactor.SlimBlock.Integrity / reactor.SlimBlock.MaxIntegrity) + " / auto eject at 60%", NeedsAutoEjection ? "red" : "white");
            Row(text, "Heat", Percent(Motion.Heat) + " / critical 125%", text.HeatTone);
            Row(text, "60 s heat peak", Percent(Motion.ForecastPeakHeat) + " at recent load / current cooling", text.HeatTone);
            Row(text, "Thermal outlook", ThermalOutlook(), text.HeatTone);
            Row(text, "Reserve", Number(Motion.ReserveMJ / ContainmentMW, "0") + " / 90 s", Motion.PowerPaused ? "red" : !Motion.PowerReady ? "yellow" : "white");
            Row(text, "Field", Motion.InstalledTiles + " / 80 tiles   " + Motion.RingCount + " rings");
            if (detailed || text.Precharging)
                Row(text, "Reserve energy", Number(Motion.ReserveMJ / 3600, "0.000") + " / "
                    + Number(ReserveCapacityMJ / 3600, "0.000") + " MWh");
            if (detailed)
            {
                Row(text, "Controllers", Number(Math.Max(0, previousControllers), "0") + " / 2 required   Capacity " + controllerRingCapacity + " rings",
                    previousControllers < 2 || Motion.FuelTier + 1 > controllerRingCapacity ? "red" : "white");
                Row(text, "Tile grade", Motion.InstalledTiles > 0
                    ? TileNames[InstalledTileGrade(Motion.MaintenanceBatch)] + " / " + Percent(Motion.TileWear) + " wear"
                    : "No installed tiles");
                Row(text, "Quartet wear", Percent(Motion.TileWear));
                if (Motion.MaintenanceTick >= 0)
                    Row(text, "Replacing", "quartet " + (Motion.MaintenanceBatch + 1) + " / 20", "cyan");
                if (Motion.Core == CorePhase.Cooling)
                    Row(text, "Dismantle at", "15% heat, after tile replacement finishes");
            }

            Section(text, "SUPPLIES & VENT");
            if (ThermalVariant)
            {
                Row(text, "Aether Residuum", Number((double)reactor.GetInventory().GetItemAmount(MyItemType.MakeComponent(ResiduumSubtype)), "0") + " recovered units");
                Row(text, "Residuum pending", Number(Motion.ResiduumMicroUnits / (double)ResiduumScale, "0.######") + " units / 10 per Aether canister");
                if (Motion.ResiduumMicroUnits >= ResiduumScale)
                    Line(text, "yellow", "Clear reactor inventory space or connect cargo to collect retained Residuum.");
            }
            Row(text, "Fuel efficiency", Percent(FuelEfficiency) + "   Controller tier " + (Motion.RingCount - 1));
            Row(text, "Fuel stock", creative ? "Creative supply" : Number(fuel, "0.###") + " canisters", !creative && fuel <= 0 ? "yellow" : "white");
            Row(text, "Spare tiles", creative ? "Creative supply" : Number(tiles, "0")
                + (needed > tiles ? "   Need " + Number(needed - tiles, "0") + " more" : ""), !creative && tiles < Math.Max(4, needed) ? "yellow" : "white");
            Row(text, "Vent", VentStatus(), !Motion.VentReady ? "yellow" : "white");
            if (detailed)
            {
                double burn = creative ? 0 : FuelUnitsPerMinute();
                Row(text, "Fuel burn", creative ? "None (creative)" : Number(burn, "0.####") + " canisters/min");
                Row(text, "Fuel remaining", creative ? "Unlimited" : burn > .000001 ? Duration(fuel / burn * 60) + " at current burn" : "Not burning");
                Row(text, "Tile demand", creative ? "None (creative)" : Number(TileWearRate() * 4, "0.###") + " / min at this load/heat");
                if (!creative && !Motion.TileStarved && Motion.InstalledTiles == 80)
                    Row(text, "Tile reserve", Duration(TileReserveSeconds()) + " at this load/heat");
                Row(text, "Tile stock", "Standard " + tileStock[0] * 4 + " / Reinforced " + tileStock[1] * 4 + " / Advanced " + tileStock[2] * 4);
                Row(text, "Startup tiles", needed + " needed   " + Number(Math.Max(0, needed - tiles), "0") + " missing");
                Row(text, "Conveyors", reactor.UseConveyorSystem ? "Automatic supply enabled" : "Automatic supply disabled");
                Row(text, "Route", !Motion.VentReady ? "Missing / unfinished / misaligned" : Motion.VentDucts + " tube(s) + outlet connected",
                    !Motion.VentReady ? "yellow" : "white");
                if (Motion.Vent != VentPhase.Idle)
                    Row(text, "Doors", "shield " + Percent(Motion.Shield) + "   intake " + Percent(Motion.Intake));
                if (Motion.TileStarved && Motion.TileWear >= 1)
                    Line(text, "red", "Tile failure: 10% output / 10x fuel at pre-failure load.");
                Line(text, "muted", "Net = output minus containment and reserve charging.");
                Line(text, "muted", "Tiles install in same-grade sets of four; loose leftovers are excluded.");
                Line(text, "muted", "Supply estimates exclude conveyor deliveries and replacement animation time.");
                Line(text, "muted", "Venting ejects the core; restart manually afterwards.");
            }
            return text;
        }

        private string ThermalOutlook()
        {
            if (Motion.PayloadReleased || Motion.Core == CorePhase.Off) return "No active core";
            if (Motion.Critical) return "Supercritical / countdown active";
            if (!Motion.ForecastRising)
                return Motion.ThermalWarning ? "Forecast safe / confirming recovery" : "No overheating predicted within 60 s";
            string cause = Motion.TileStarved && Motion.TileWear >= 1 ? "Failed containment"
                : Motion.ForecastCircuit > 0 ? "Circuit " + Motion.ForecastCircuit : "Core / housing";
            bool meltdown = Motion.ForecastMeltdownSeconds >= 0;
            double seconds = meltdown ? Motion.ForecastMeltdownSeconds : Motion.ForecastOverheatSeconds;
            if (seconds == 0) return cause + (meltdown ? " / critical heat now" : " / overheating now");
            return cause + (meltdown ? " / critical heat in ~" : " / overheating in ~")
                + Number(Math.Ceiling(Math.Max(0, seconds)), "0") + " s";
        }

        private string OperatingStatus(out string action, out string tone)
        {
            action = null; tone = "white";
            if (!receivedState) { tone = "yellow"; return "WAITING FOR REACTOR STATE"; }
            if (Motion.Critical)
            {
                tone = "red"; action = !Motion.ControllersReady ? "Repair both controllers urgently; core cannot eject."
                    : Motion.VentReady ? "Eject the core to move the blast away." : "Repair the vent route urgently; core cannot eject.";
                return "SUPERCRITICAL  /  ~" + Number(Motion.CriticalSeconds, "0.0") + " s";
            }
            if (Motion.ThermalWarning)
            {
                tone = "yellow";
                if (!Motion.ForecastRising)
                { action = "Forecast is safe; confirming recovery for 5 s."; return "THERMAL WARNING / RECOVERING"; }
                action = Motion.TileStarved && Motion.TileWear >= 1 ? "Replace 4 tiles or eject before 125% heat."
                    : ThermalOutlook() + ". Restore cooling or reduce load.";
                return Motion.ForecastPeakHeat >= 1.25f ? "MELTDOWN RISK / NEXT 60 S" : "OVERHEATING RISK / NEXT 60 S";
            }
            if (initializationFrames > 0)
            { tone = "cyan"; action = "Restoring saved state while grid connections initialize."; return "RECONNECTING CONTAINMENT"; }
            if (Motion.PowerPaused)
            { tone = "red"; action = "Restore containment power; reserve exhausted."; return "MECHANISMS PAUSED"; }
            if (Motion.Vent != VentPhase.Idle && !Motion.PayloadReleased && !Motion.ControllersReady)
            { tone = "red"; action = "Restore both fully built, functional controllers; heat and fuse continue."; return "CONTROLLERS BROKEN / EJECTION PAUSED"; }
            if (!Motion.VentReady && Motion.Vent != VentPhase.Idle && !Motion.PayloadReleased)
            { tone = "red"; action = "Restore the original tube stack and outlet; heat and fuse continue."; return "VENT ROUTE BROKEN / EJECTION PAUSED"; }
            if (Motion.Vent != VentPhase.Idle)
            { tone = "yellow"; action = "Reactor stays off after this cycle."; return "VENTING  /  " + VentStatus().ToUpperInvariant(); }
            if (NeedsAutoEjection && !Motion.ControllersReady)
            { tone = "red"; action = "Restore both fully built, functional controllers to auto eject."; return "AUTO EJECTION BLOCKED / CONTROLLERS"; }
            if (NeedsAutoEjection && !Motion.VentReady)
            { tone = "red"; action = "Repair the complete vent route to auto eject."; return "AUTO EJECTION BLOCKED / VENTS"; }
            if (!reactor.IsFunctional || reactor.SlimBlock.BuildLevelRatio < 1)
            { tone = "red"; action = "Complete or repair the reactor."; return "REACTOR INCOMPLETE"; }
            if (previousControllers < 2 || Motion.FuelTier + 1 > controllerRingCapacity)
            { tone = "red"; action = "Attach two compatible, working controllers."; return "CONTAINMENT INCOMPLETE"; }
            if (!Motion.PayloadReleased && Motion.Core != CorePhase.Off && ThermalVariant && Motion.Thermal != null
                && Motion.Thermal.Mode == ThermalMode.Brayton)
            {
                var thermal = Motion.Thermal;
                if (Array.Exists(thermal.Loops, loop => loop.Connected && loop.CoolingMW + .001 < loop.RequiredCoolingMW)
                    && (thermal.ProducedMW > .001 || thermal.RetainedHeatMJ > .001))
                { action = "Add or unblock cooling units; monitor the 60 s heat forecast."; return "INSUFFICIENT LOOP COOLING"; }
            }
            if (ThermalVariant && Motion.Thermal != null)
            {
                var thermal = Motion.Thermal;
                if (thermal.Faulted)
                { tone = "red"; action = thermal.Diagnostic; return "THERMAL RUNTIME ISOLATED"; }
                if ((thermal.Mode == ThermalMode.Brayton || thermal.Requested == ThermalMode.Brayton) && !HasAdvancedController())
                { tone = "yellow"; action = "Install or repair an advanced controller. Keep cooldown power supplied; restart manually."; return "BRAYTON LOCKED / ADVANCED CONTROLLER REQUIRED"; }
                if (Motion.FuelTier > 1 && (thermal.Mode != ThermalMode.Brayton || thermal.Requested != ThermalMode.Brayton))
                { tone = "yellow"; action = "High-tier fuel blocked to prevent meltdown. Drain retained heat, then use Aether or enable Brayton."; return "FUEL SAFETY INTERLOCK / COOLING"; }
                if (!thermal.Settled)
                { tone = "yellow"; action = ThermalModeTransitionHint; return "MODE CHANGE / RESTART WHEN SETTLED"; }
                if (thermal.Mode == ThermalMode.Brayton && thermal.LoopTrip && !reactor.Enabled)
                { tone = "yellow"; action = "Repair at least one separate circuit, then start manually. Keep cooldown power supplied."; return "STARTUP BLOCKED / ALL FOUR CIRCUITS DEFECTIVE"; }
            }
            if (Motion.Core == CorePhase.Cooling)
            { tone = "yellow"; action = "Holding the shell until heat falls to 15%."; return "COOLING DOWN"; }
            if (Motion.Core == CorePhase.Stopping) { tone = "yellow"; return "DISMANTLING CONTAINMENT"; }
            if (!Motion.VentReady)
            {
                if (!Motion.SecurityMode && Motion.Core == CorePhase.Running && reactor.Enabled)
                { tone = "yellow"; action = "Repair vents; ejection is unavailable. Security mode is off."; return "RUNNING / VENT ROUTE BROKEN"; }
                tone = "red"; action = "Build 1-15 aligned vent tubes above the roof, then an outlet. Weld fully and switch on."; return "VENT TUBE / OUTLET REQUIRED";
            }
            if (!HasUsableFuel())
            {
                tone = "yellow";
                if (ThermalVariant && Motion.Thermal != null && Motion.Thermal.Mode == ThermalMode.Standalone)
                { action = "Load Aether. Helion and Empyrean require Brayton and an advanced controller."; return "AETHER REQUIRED / STANDALONE"; }
                action = "Load compatible refined fuel."; return "OUT OF FUEL";
            }
            if (Motion.TileStarved) { tone = "yellow"; action = "Supply startup tiles, then switch on."; return "STARTUP TILES REQUIRED"; }
            if (Precharging)
            {
                string progress = Number(Math.Floor(Math.Min(1, Math.Max(0, Motion.ReserveMJ / ReserveCapacityMJ)) * 100), "0") + "%";
                if (PrechargeMW <= .000001)
                {
                    action = Motion.ReserveMJ >= ReserveCapacityMJ * .999999
                        ? "Reserve full; supply " + Power(ContainmentMW) + " for containment to start."
                        : "Supply more than " + Power(ContainmentMW) + "; containment is powered before charging.";
                    return "STARTUP WAITING FOR POWER  /  " + progress;
                }
                action = "Charging containment reserve before assembly.";
                return "CHARGING STARTUP RESERVE  /  " + progress;
            }
            if (Motion.Core == CorePhase.Starting) { tone = "cyan"; return "DEPLOYING CONTAINMENT"; }
            if (Motion.Core == CorePhase.Running && reactor.Enabled)
            { tone = "green"; return Motion.PowerRamp < .999f ? "RUNNING  /  RAMPING UP" : "RUNNING"; }
            if (Motion.PowerStarved) { tone = "yellow"; action = "Power was lost. Restore supply and restart."; return "SHUT OFF  /  POWER LOSS"; }
            tone = "red"; return "SHUT OFF";
        }

        private string VentStatus()
        {
            if (!Motion.VentReady) return Motion.Vent != VentPhase.Idle && !Motion.PayloadReleased ? "Route broken / paused" : "Tube + outlet required";
            switch (Motion.Vent)
            {
                case VentPhase.ShieldClosing: return "Closing shield";
                case VentPhase.IntakeOpening: return "Opening hatch";
                case VentPhase.Ejecting: return Motion.PayloadReleased ? "Core released" : "Ejecting core";
                case VentPhase.IntakeClosing: return "Closing hatch";
                case VentPhase.ShieldOpening: return "Retracting shield";
                case VentPhase.Open: return "Intake open";
                default: return "Ready";
            }
        }

        private static string Number(double value, string format) { return value.ToString(format, CultureInfo.InvariantCulture); }
        private static string Percent(double value) { return Number(value * 100, "0") + "%"; }
        private static string Duration(double seconds)
        {
            if (seconds < 60) return Number(Math.Max(0, seconds), "0") + " s";
            if (seconds < 3600) return Number(seconds / 60, "0.0") + " min";
            return Number(seconds / 3600, "0.0") + " h";
        }
        private static string Power(double mw)
        {
            double size = Math.Abs(mw);
            return size >= 1000000 ? Number(mw / 1000000, "0.##") + " TW"
                : size >= 1000 ? Number(mw / 1000, "0.###") + " GW"
                : size > 0 && size < 1 ? Number(mw * 1000, "0.#") + " kW" : Number(mw, "0.##") + " MW";
        }
        private static void Section(StatusReport report, string title) { report.Section = title; }
        private static void Row(StatusReport report, string label, string value, string tone = "white")
        { report.Rows.Add(new StatusRow { Section = report.Section, Label = label, Value = value, Tone = tone }); }
        private static void Line(StatusReport report, string tone, string value)
        { Row(report, "", value, tone); }
    }

    internal sealed class StatusRow
    {
        internal string Section, Label, Value, Tone;
    }

    internal sealed class StatusReport
    {
        internal string Name, State, Tone, Section;
        internal string Fuel;
        internal string HeatTone = "white";
        internal double Heat, Reserve, Load;
        internal bool Precharging, Brayton;
        internal readonly List<StatusRow> Rows = new List<StatusRow>();

        internal string Value(string label)
        {
            foreach (var row in Rows) if (row.Label == label) return row.Value;
            return "--";
        }

        internal string Text()
        {
            var text = new StringBuilder("ARCANE POWER / " + Fuel.ToUpperInvariant() + " FUEL\n" + State + "\n");
            string section = null;
            foreach (var row in Rows)
            {
                if (row.Section != section) { section = row.Section; text.Append("\n").AppendLine(section); }
                if (!string.IsNullOrEmpty(row.Label)) text.Append(row.Label).Append(": ");
                text.AppendLine(row.Value);
            }
            return text.ToString();
        }
    }
}
