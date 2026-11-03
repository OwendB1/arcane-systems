namespace ArcanePower
{
    public abstract partial class ThermalBlock
    {
        internal void ExpireTelemetry()
        {
            receivedRotor = receivedRadiator = false;
            coolingState = null;
        }
    }
}
