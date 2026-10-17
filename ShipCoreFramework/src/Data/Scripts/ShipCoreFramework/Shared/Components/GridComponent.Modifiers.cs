using Sandbox.ModAPI;

namespace ShipCoreFramework
{
    internal partial class GridComponent
    {
        // Owned by this grid observer, so a newly joined grid always gets an initial application.
        private GridModifiers _appliedModifiers;

        internal void ApplyModifiers(GridModifiers modifiers)
        {
            if (modifiers == null || CubeGridModifiers.SameModifiers(_appliedModifiers, modifiers)) return;

            // Keep a value snapshot: configuration and API callers can reuse mutable modifier objects.
            GridModifiers snapshot = CubeGridModifiers.Clone(modifiers);
            _appliedModifiers = snapshot;
            try
            {
                foreach (var block in GetBlocksCopy())
                {
                    var terminalBlock = block?.FatBlock as IMyTerminalBlock;
                    if (terminalBlock != null) CubeGridModifiers.ApplyModifiers(terminalBlock, snapshot);
                }
            }
            catch
            {
                _appliedModifiers = null;
                throw;
            }
        }
    }
}
