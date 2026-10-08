using System;
using Sandbox.ModAPI;

namespace ShipCoreFramework
{
    public partial class ModConfig
    {
        internal bool SaveConfig(bool showInChat = false, bool broadcast = true)
        {
            if (!Session.IsServer) return false;

            try
            {
                EnsurePersistedWorldSettings();
                SelectedNoCoreUniqueName = SelectedNoCore?.UniqueName ?? SelectedNoCoreUniqueName;
                var globalConfigWriter = MyAPIGateway.Utilities.WriteFileInWorldStorage(GlobalConfigFileName, typeof(ModConfig));
                globalConfigWriter.Write(MyAPIGateway.Utilities.SerializeToXML(this));
                globalConfigWriter.Close();
                Utils.Log($"Save Config: Saved {GlobalConfigFileName}", showInChat ? 3 : 0);
                RemoveLegacySandboxSettings(showInChat);

                if (broadcast && Session.MpActive) Session.BroadcastConfigToClients();
                return true;
            }
            catch (Exception e)
            {
                Utils.Log($"Save Error: {e}");
                return false;
            }
        }

        private static void RemoveLegacySandboxSettings(bool showInChat)
        {
            MyAPIGateway.Utilities.RemoveVariable(LegacyIgnoreAiKey);
            Utils.Log($"Removed legacy sandbox variable {LegacyIgnoreAiKey}", showInChat ? 3 : 0);
            MyAPIGateway.Utilities.RemoveVariable(LegacyIgnoredFactionsKey);
            Utils.Log($"Removed legacy sandbox variable {LegacyIgnoredFactionsKey}", showInChat ? 3 : 0);
            MyAPIGateway.Utilities.RemoveVariable(LegacySelectedNoCoreKey);
            Utils.Log($"Removed legacy sandbox variable {LegacySelectedNoCoreKey}", showInChat ? 3 : 0);
        }
    }
}
