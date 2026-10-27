using System;

namespace ArcanePower
{
    // Advisory only: completed, paid production samples feed a four-second
    // window. Forecasting never edits stores, dispatch, core heat or the fuse.
    public sealed class ThermalForecast
    {
        private const int Window = 240;
        private readonly double[,] samples = new double[Window, 6];
        private readonly double[] sums = new double[6];
        private readonly double[] cooling = new double[5];
        private readonly double[] energy = new double[5];
        private readonly double[] production = new double[5];
        private int cursor, forecastTick, riskTicks, safeTicks, previousConnections = -1;
        private bool previousGenerating, previousRunaway;
        public double PeakHeat, OverheatSeconds = -1, MeltdownSeconds = -1;
        public double CooldownSeconds = -1;
        public int Circuit;
        public bool Warning;

        public ThermalForecast(bool warning = false) { Warning = warning; }

        private void Sample(int column, double value)
        {
            sums[column] += value - samples[cursor, column];
            samples[cursor, column] = value;
        }

        // Called once per completed simulation interval, after circuit cooling.
        public void Update(double heat, double operatingTarget, bool runaway,
            ThermalReactorState state, double ratingMW, bool generating)
        {
            if (!ThermalMath.Finite(heat) || !ThermalMath.Finite(operatingTarget)
                || !ThermalMath.Finite(ratingMW) || ratingMW <= 0)
            { PeakHeat = 4; OverheatSeconds = MeltdownSeconds = 0; CooldownSeconds = -1; Circuit = 0; Warning = true; return; }
            int connections = 0;
            double housingWaste = state == null ? 0 : state.RequiredCoolingMW;
            for (int i = 1; i <= ThermalLoops.Count; i++)
            {
                var loop = state == null ? null : state.Loops[i - 1];
                double waste = loop == null ? 0 : loop.RequiredCoolingMW;
                housingWaste -= waste;
                Sample(i, waste);
                if (loop != null && loop.Connected) connections |= 1 << (i - 1);
                double capacity = loop == null ? 0 : loop.CoolingMW;
                if (cooling[i] != capacity) forecastTick = 0;
                cooling[i] = capacity;
            }
            Sample(0, Math.Max(0, housingWaste));
            Sample(5, state == null ? Math.Max(0, operatingTarget) : state.ProducedMW / ratingMW);
            cursor = (cursor + 1) % Window;
            double housingCooling = state != null && state.Mode == ThermalMode.Standalone ? state.CoolingMW : 0;
            if (cooling[0] != housingCooling || connections != previousConnections
                || generating != previousGenerating || runaway != previousRunaway) forecastTick = 0;
            cooling[0] = housingCooling;
            previousConnections = connections; previousGenerating = generating; previousRunaway = runaway;
            if (forecastTick-- <= 0)
            {
                forecastTick = 14;
                Predict(heat, runaway ? operatingTarget : generating ? sums[5] / Window : 0,
                    runaway, state, ratingMW, generating);
                CooldownSeconds = !generating && !runaway ? PredictCooldown(heat, state, ratingMW) : -1;
            }
            bool risk = PeakHeat > Math.Max(1, heat) + .001;
            if (runaway || (risk && MeltdownSeconds >= 0))
            { Warning = true; riskTicks = safeTicks = 0; }
            else if (risk)
            { safeTicks = 0; riskTicks = Math.Min(120, riskTicks + 1); if (riskTicks == 120) Warning = true; }
            else
            { riskTicks = 0; safeTicks = Math.Min(300, safeTicks + 1); if (safeTicks == 300) Warning = false; }
        }

        private void Predict(double heat, double operatingTarget, bool runaway,
            ThermalReactorState state, double ratingMW, bool generating)
        {
            PeakHeat = heat;
            OverheatSeconds = heat > 1.001 ? 0 : -1;
            MeltdownSeconds = heat >= 1.25 ? 0 : -1;
            Circuit = 0;
            double credit = state == null ? 0 : state.Store.HotMJ;
            for (int i = 0; i < energy.Length; i++)
            {
                energy[i] = state == null ? 0 : i == 0 ? state.Store.WasteMJ : state.Loops[i - 1].ExcessMJ;
                bool connected = i == 0 || state == null || state.Loops[i - 1].Connected;
                production[i] = generating && connected ? Math.Max(0, sums[i] / Window) : 0;
            }
            // Midpoint integration uses the live thermal response and actual
            // cooling capacity. Unused cooling cannot create negative heat or
            // offset another circuit's deficit. Paid fuel credit is not waste.
            int driver = 0;
            for (int step = 1; step <= 600; step++)
            {
                AdvanceWaste(state, ratingMW, generating, ref credit);
                double target = operatingTarget;
                int hottest = 0;
                for (int i = 0; i < energy.Length; i++)
                {
                    double level = energy[i] / (ratingMW * (i == 0 ? 2 : .5));
                    if (level > target) { target = level; hottest = i; }
                }
                bool critical = heat >= 1.25;
                if (critical) target = 4;
                target = ThermalMath.Clamp(target, 0, 4);
                double response = ThermalMath.CoreHeatResponse(heat, target, runaway || critical);
                heat = ThermalMath.Clamp(heat + (target - heat) * (1 - Math.Pow(1 - 1 / response, 6)), 0, 4);
                if (!critical) driver = hottest;
                if (heat > PeakHeat) { PeakHeat = heat; Circuit = driver; }
                if (OverheatSeconds < 0 && heat > 1.001) OverheatSeconds = step / 10.0;
                if (MeltdownSeconds < 0 && heat >= 1.25) { MeltdownSeconds = step / 10.0; Circuit = driver; }
                AdvanceWaste(state, ratingMW, generating, ref credit);
            }
        }

        private double PredictCooldown(double heat, ThermalReactorState state, double ratingMW)
        {
            if (heat >= 1.25) return -1;
            if (heat <= ThermalMath.CooldownHeat) return 0;
            double credit = state == null ? 0 : state.Store.HotMJ;
            for (int i = 0; i < energy.Length; i++)
            {
                energy[i] = state == null ? 0 : i == 0 ? state.Store.WasteMJ : state.Loops[i - 1].ExcessMJ;
                production[i] = 0;
            }
            // Advisory midpoint projection, bounded to one hour. It reuses the
            // circuit budgets and passive drain order of the risk forecast.
            // Estimates are simulation seconds, independent of rendering speed.
            for (int step = 0; step < 7200; step++)
            {
                bool empty = true;
                foreach (double stored in energy) if (stored > 0) empty = false;
                if (empty)
                {
                    double tail = Math.Ceiling(Math.Log(ThermalMath.CooldownHeat / heat)
                        / Math.Log(1 - 1 / ThermalMath.CoreHeatResponse(heat, 0, false))) / 60;
                    return step * .5 + tail <= 3600 ? step * .5 + tail : -1;
                }
                AdvanceWaste(state, ratingMW, false, ref credit, .25);
                double target = 0;
                for (int i = 0; i < energy.Length; i++)
                    target = Math.Max(target, energy[i] / (ratingMW * (i == 0 ? 2 : .5)));
                target = ThermalMath.Clamp(target, 0, 4);
                double response = ThermalMath.CoreHeatResponse(heat, target, false);
                heat = ThermalMath.Clamp(heat + (target - heat) * (1 - Math.Pow(1 - 1 / response, 30)), 0, 4);
                if (heat >= 1.25) return -1;
                if (heat <= ThermalMath.CooldownHeat) return (step + 1) * .5;
                AdvanceWaste(state, ratingMW, false, ref credit, .25);
            }
            return -1;
        }

        private void AdvanceWaste(ThermalReactorState state, double ratingMW, bool generating, ref double credit, double seconds = .05)
        {
            for (int i = 0; i < energy.Length; i++)
                energy[i] = Math.Max(0, energy[i] + (production[i] - cooling[i]) * seconds);
            if (state == null || state.Mode != ThermalMode.Brayton || generating) return;
            // Same shared passive cooldown budget/order as CoolHousing: housing
            // waste, unused fuel credit, then retained circuit heat. It is spent
            // once, rather than granting every disconnected loop extra cooling.
            double budget = ratingMW * .02 * seconds;
            double removed = Math.Min(energy[0], budget);
            energy[0] -= removed; budget -= removed;
            removed = Math.Min(credit, budget);
            credit -= removed; budget -= removed;
            for (int i = 1; i < energy.Length; i++)
            {
                removed = Math.Min(energy[i], budget);
                energy[i] -= removed; budget -= removed;
            }
        }
    }
}
