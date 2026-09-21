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
            var text = new StatusReport { Name = reactor.CustomName, Tier = Motion.Profile - 1, Heat = Motion.Heat, Reserve = Motion.ReserveMJ / ReserveCapacityMJ, Load = Motion.Load };
            bool creative = MyAPIGateway.Session.CreativeMode;
            double fuel = (double)reactor.GetInventory().GetItemAmount(MyItemType.MakeIngot(Fuels[Motion.Profile - 2]));
            double tiles = (double)reactor.GetInventory().GetItemAmount(TileType);
            int needed = 80 - Motion.InstalledTiles + (Motion.TileWear >= 1 ? 4 : 0);
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
            Row(text, "Output", Power(reactor.CurrentOutput) + " / " + Power(PowerMW[Motion.Profile - 2]));
            Row(text, "Net", Power(reactor.CurrentOutput - Motion.PowerInputMW));
            if (detailed)
            {
                Row(text, "Ramp", Percent(Motion.PowerRamp) + "   Reaction load " + Percent(Motion.Load));
                Row(text, "Containment", Power(Motion.PowerInputMW) + " / " + Power(Motion.PowerDemandMW) + " requested");
            }

            Section(text, "CONTAINMENT");
            Row(text, "Heat", Percent(Motion.Heat) + " / critical 125%", Motion.Critical || Motion.Heat >= 1 ? "red" : Motion.Heat >= .85f ? "yellow" : "white");
            Row(text, "Reserve", Number(Motion.ReserveMJ / ContainmentMW, "0") + " / 90 s", Motion.PowerPaused ? "red" : !Motion.PowerReady ? "yellow" : "white");
            Row(text, "Field", Motion.InstalledTiles + " / 80 tiles   " + Motion.Profile + " rings");
            if (detailed)
            {
                Row(text, "Controllers", Number(Math.Max(0, previousControllers), "0") + " / 2 required   Capacity " + rings + " rings",
                    previousControllers < 2 || Motion.Profile > rings ? "red" : "white");
                Row(text, "Reserve energy", Number(Motion.ReserveMJ / 3600, "0.000") + " / "
                    + Number(ReserveCapacityMJ / 3600, "0.000") + " MWh");
                Row(text, "Quartet wear", Percent(Motion.TileWear));
                if (Motion.MaintenanceTick >= 0)
                    Row(text, "Replacing", "quartet " + (Motion.MaintenanceBatch + 1) + " / 20", "cyan");
                if (Motion.Core == CorePhase.Cooling)
                    Row(text, "Dismantle at", "15% heat, after tile replacement finishes");
            }

            Section(text, "SUPPLIES & VENT");
            Row(text, "Fuel stock", creative ? "Creative supply" : Number(fuel, "0.###") + " units", !creative && fuel <= 0 ? "yellow" : "white");
            Row(text, "Spare tiles", creative ? "Creative supply" : Number(tiles, "0")
                + (needed > tiles ? "   Need " + Number(needed - tiles, "0") + " more" : ""), !creative && tiles < Math.Max(4, needed) ? "yellow" : "white");
            Row(text, "Vent", VentStatus(), ventRouteIncomplete ? "yellow" : "white");
            if (detailed)
            {
                double burn = creative ? 0 : FuelUnitsPerMinute();
                Row(text, "Fuel burn", creative ? "None (creative)" : Number(burn, "0.###") + " units/min");
                Row(text, "Fuel remaining", creative ? "Unlimited" : burn > .000001 ? Duration(fuel / burn * 60) + " at current burn" : "Not burning");
                Row(text, "Tile demand", creative ? "None (creative)" : Number(TileWearRate() * 4, "0.0") + " / min at this load/heat");
                if (!creative && !Motion.TileStarved && Motion.InstalledTiles == 80)
                    Row(text, "Tile reserve", Duration((Math.Floor(tiles / 4) + 1 - Motion.TileWear) / TileWearRate() * 60) + " at this load/heat");
                Row(text, "Startup tiles", needed + " needed   " + Number(Math.Max(0, needed - tiles), "0") + " missing");
                Row(text, "Conveyors", reactor.UseConveyorSystem ? "Automatic supply enabled" : "Automatic supply disabled");
                Row(text, "Route", ventRouteIncomplete ? "Incomplete / misaligned" : Motion.VentOutletId == 0 ? "Direct roof outlet" : "External outlet connected",
                    ventRouteIncomplete ? "yellow" : "white");
                if (Motion.Vent != VentPhase.Idle)
                    Row(text, "Doors", "shield " + Percent(Motion.Shield) + "   intake " + Percent(Motion.Intake));
                if (Motion.TileStarved && Motion.TileWear >= 1)
                    Line(text, "red", "Tile failure: 10% output / 10x fuel at pre-failure load.");
                Line(text, "muted", "Net = output minus containment and reserve charging.");
                Line(text, "muted", "Supply estimates exclude conveyor deliveries.");
                Line(text, "muted", "Venting ejects the core; restart manually afterwards.");
            }
            return text;
        }

        private string OperatingStatus(out string action, out string tone)
        {
            action = null; tone = "white";
            if (!receivedState) { tone = "yellow"; return "WAITING FOR REACTOR STATE"; }
            if (Motion.Critical)
            {
                tone = "red"; action = "Eject the core to move the blast away.";
                return "SUPERCRITICAL  /  ~" + Number(Motion.CriticalSeconds, "0.0") + " s";
            }
            if (Motion.TileStarved && Motion.TileWear >= 1 && !Motion.PayloadReleased)
            { tone = "red"; action = "Replace 4 tiles or eject before 125% heat."; return "TILE FAILURE  /  RUNAWAY HEAT"; }
            if (initializationFrames > 0)
            { tone = "cyan"; action = "Restoring saved state while grid connections initialize."; return "RECONNECTING CONTAINMENT"; }
            if (!reactor.IsFunctional || reactor.SlimBlock.BuildLevelRatio < 1)
            { tone = "red"; action = "Complete or repair the reactor."; return "REACTOR INCOMPLETE"; }
            if (Motion.PowerPaused)
            { tone = "red"; action = "Restore containment power; reserve exhausted."; return "MECHANISMS PAUSED"; }
            if (Motion.Vent != VentPhase.Idle)
            { tone = "yellow"; action = "Reactor stays off after this cycle."; return "VENTING  /  " + VentStatus().ToUpperInvariant(); }
            if (previousControllers < 2 || Motion.Profile > rings)
            { tone = "red"; action = "Attach two compatible, working controllers."; return "CONTAINMENT INCOMPLETE"; }
            if (Motion.Core == CorePhase.Cooling)
            { tone = "yellow"; action = "Holding the shell until heat falls to 15%."; return "COOLING DOWN"; }
            if (Motion.Core == CorePhase.Stopping) { tone = "yellow"; return "DISMANTLING CONTAINMENT"; }
            if (!HasUsableFuel()) { tone = "yellow"; action = "Load compatible refined fuel."; return "OUT OF FUEL"; }
            if (Motion.TileStarved) { tone = "yellow"; action = "Supply startup tiles, then switch on."; return "STARTUP TILES REQUIRED"; }
            if (Motion.Core == CorePhase.Off && reactor.Enabled && !Motion.PowerReady)
            { tone = "yellow"; action = "Grid power and a full reserve are required."; return "PRECHARGING"; }
            if (Motion.Core == CorePhase.Starting) { tone = "cyan"; return "DEPLOYING CONTAINMENT"; }
            if (Motion.Core == CorePhase.Running && reactor.Enabled)
            { tone = "green"; return Motion.PowerRamp < .999f ? "RUNNING  /  RAMPING UP" : "RUNNING"; }
            if (Motion.PowerStarved) { tone = "yellow"; action = "Power was lost. Restore supply and restart."; return "SHUT OFF  /  POWER LOSS"; }
            tone = "red"; return "SHUT OFF";
        }

        private string VentStatus()
        {
            switch (Motion.Vent)
            {
                case VentPhase.ShieldClosing: return "Closing shield";
                case VentPhase.IntakeOpening: return "Opening hatch";
                case VentPhase.Ejecting: return Motion.PayloadReleased ? "Core released" : "Ejecting core";
                case VentPhase.IntakeClosing: return "Closing hatch";
                case VentPhase.ShieldOpening: return "Retracting shield";
                case VentPhase.Open: return "Intake open";
                default: return ventRouteIncomplete ? "Route incomplete" : "Ready";
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
        internal int Tier;
        internal double Heat, Reserve, Load;
        internal readonly List<StatusRow> Rows = new List<StatusRow>();

        internal string Value(string label)
        {
            foreach (var row in Rows) if (row.Label == label) return row.Value;
            return "--";
        }

        internal string Text()
        {
            var text = new StringBuilder("ARCANE POWER / FUEL " + Tier + "\n" + State + "\n");
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
