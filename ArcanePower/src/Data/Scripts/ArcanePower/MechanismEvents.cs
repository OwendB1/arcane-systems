namespace ArcanePower
{
    // Local sound observer: snapshots establish a baseline, never replay a
    // backlog. Per-quartet bits suppress repeats after prediction corrections.
    internal sealed class MechanismEvents
    {
        private bool known;
        private uint dispensed, latched;
        private uint retracted, stored;
        private float previousAge;
        private int maintenanceBatch = -1;
        private float maintenanceTick = -1;
        private bool maintenanceDispensed, maintenanceLatched;

        // Bits: 1 = dispenser release; 2 = containment latch; 4 = retract;
        // 8 = dispenser catch. A quartet shares
        // a cue because its four tiles move simultaneously from four pillars.
        internal int Observe(MotionState state, bool audible)
        {
            int events = 0;
            audible &= known && !state.Paused;
            known = true;
            float age = state.CoreTick + state.CoreSubtick;
            float oldAge = previousAge;
            previousAge = age;
            if (state.Core == CorePhase.Off)
            {
                dispensed = latched = retracted = stored = 0;
                maintenanceBatch = -1;
                maintenanceTick = -1;
                return 0;
            }
            if (state.Core == CorePhase.Starting)
            {
                for (int batch = 0; batch < 20; batch++)
                {
                    uint bit = 1u << batch;
                    float start = 320 + 36 * batch;
                    if (age >= start && (dispensed & bit) == 0)
                    { dispensed |= bit; events |= 1; }
                    if (age >= start + 34 && (latched & bit) == 0)
                    { latched |= bit; events |= 2; }
                }
            }
            if (state.Core == CorePhase.Stopping && state.StopTick >= 90 && !state.PayloadReleased)
            {
                for (int batch = 0; batch < 20; batch++)
                {
                    uint bit = 1u << batch;
                    float start = 320 + 36 * batch;
                    // Crossings avoid replaying earlier quartets on a late join
                    // or retracting tiles that never left their dispenser.
                    if (oldAge >= start + 34 && age < start + 34 && (retracted & bit) == 0)
                    { retracted |= bit; events |= 4; }
                    if (oldAge > start && age <= start && (stored & bit) == 0)
                    { stored |= bit; events |= 8; }
                }
            }
            if (state.MaintenanceTick >= 0)
            {
                if (maintenanceBatch != state.MaintenanceBatch)
                {
                    maintenanceBatch = state.MaintenanceBatch;
                    maintenanceDispensed = maintenanceLatched = false;
                }
                // The replacement grows inside its dispenser at 18-24, then
                // exits at 24. It joins the rotating shell at 90.
                if (state.MaintenanceTick >= 24 && !maintenanceDispensed)
                { maintenanceDispensed = true; events |= 1; }
            }
            else if (maintenanceTick >= 0 && maintenanceBatch >= 0 && !maintenanceLatched
                && state.MaintenanceBatch == (maintenanceBatch + 1) % 20
                && !state.PayloadReleased)
            { maintenanceLatched = true; events |= 2; }
            maintenanceTick = state.MaintenanceTick;
            return audible ? events : 0;
        }

        internal static bool DeckMoving(MotionState state)
        {
            if (state.Paused || (state.Vent != VentPhase.Idle && state.Vent != VentPhase.ShieldClosing)) return false;
            if (state.Core != CorePhase.Starting && (state.Core != CorePhase.Stopping || state.StopTick < 90)) return false;
            float age = state.CoreTick + state.CoreSubtick;
            return (age > 0 && age < 76) || (age > 220 && age < 298);
        }

        internal static bool HatchMoving(MotionState state)
        {
            return !state.Paused && (state.Vent == VentPhase.IntakeOpening || state.Vent == VentPhase.IntakeClosing);
        }
    }
}
