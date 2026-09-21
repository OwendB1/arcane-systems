using System;
using Sandbox.ModAPI;

namespace ShipCoreFramework
{
    internal partial class GroupComponent
    {
        private readonly object _modifierOverrideLock = new object();
        private GridModifiers _gridModifiersOverride;
        private SpeedModifiers _speedModifiersOverride;
        private GridDefenseModifiers _passiveDefenseModifiersOverride;
        private GridDefenseModifiers _activeDefenseModifiersOverride;

        internal GridModifiers GetGridModifiersOverride()
        {
            lock (_modifierOverrideLock) return _gridModifiersOverride;
        }

        internal SpeedModifiers GetSpeedModifiersOverride()
        {
            lock (_modifierOverrideLock) return _speedModifiersOverride;
        }

        internal GridDefenseModifiers GetPassiveDefenseModifiersOverride()
        {
            lock (_modifierOverrideLock) return _passiveDefenseModifiersOverride;
        }

        internal GridDefenseModifiers GetActiveDefenseModifiersOverride()
        {
            lock (_modifierOverrideLock) return _activeDefenseModifiersOverride;
        }

        internal void SetGridModifiersOverride(GridModifiers value)
        {
            SetModifierOverride(() =>
            {
                lock (_modifierOverrideLock) _gridModifiersOverride = value;
            });
        }

        internal void SetSpeedModifiersOverride(SpeedModifiers value)
        {
            SetModifierOverride(() =>
            {
                lock (_modifierOverrideLock) _speedModifiersOverride = value;
            });
        }

        internal void SetPassiveDefenseModifiersOverride(GridDefenseModifiers value)
        {
            SetModifierOverride(() =>
            {
                lock (_modifierOverrideLock) _passiveDefenseModifiersOverride = value;
            });
        }

        internal void SetActiveDefenseModifiersOverride(GridDefenseModifiers value)
        {
            SetModifierOverride(() =>
            {
                lock (_modifierOverrideLock) _activeDefenseModifiersOverride = value;
            });
        }

        private void SetModifierOverride(Action update)
        {
            if (!Session.IsServer || update == null) return;
            if (!Session.IsGameThread)
            {
                MyAPIGateway.Utilities.InvokeOnGameThread(() => SetModifierOverride(update));
                return;
            }

            update();
            InvalidateModifierStateCache();
            RefreshModifierStateCache();
            ApplyModifiers(Modifiers);
            DefenseValuesChanged();
            SpeedEnforcement.RefreshSpeedState(this);
            Session.MarkRuntimeStateDirty(this);
        }
    }
}
