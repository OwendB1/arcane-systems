using Sandbox.ModAPI;
using VRageMath;

namespace ArcanePower
{
    public sealed partial class ThermalSession
    {
        internal static ThermalBlock RadiatorParent(long id)
        {
            ThermalBlock block;
            return Blocks.TryGetValue(id, out block) && block.Spec.Kind == ThermalKind.Radiator ? block : null;
        }

        internal static string RadiatorConnection(long id)
        {
            ThermalBlock block;
            if (!Blocks.TryGetValue(id, out block) || block.Store.Radiator == null)
                return "Place the panel above its radiator base to attach";
            var state = block.Store.Radiator;
            if (!MyAPIGateway.Multiplayer.IsServer && state.Sequence == 0) return "Waiting for radiator connection state";
            return state.ParentId != 0 ? "Attached: yaw aligned automatically; shares the base's rotation and cooling loop"
                : "Unattached: centre above the base or preceding panel, point Up the same way; any yaw; maximum three panels. Weld/repair and enable for cooling";
        }

        private static void LinkRadiators()
        {
            foreach (var block in Blocks.Values) block.RadiatorBase = null;
            foreach (var root in Blocks.Values)
            {
                if (root.Spec.Kind != ThermalKind.Radiator) continue;
                int previous = root.RadiatorPanels.Count;
                // GameLogic.Entity is cleared when a panel is removed. The
                // retained block reference still identifies the previous link.
                long first = previous > 0 ? root.RadiatorPanels[0].Block.EntityId : 0;
                long second = previous > 1 ? root.RadiatorPanels[1].Block.EntityId : 0;
                long third = previous > 2 ? root.RadiatorPanels[2].Block.EntityId : 0;
                root.RadiatorPanels.Clear();
                if (root.CircuitReady)
                {
                    for (int i = 0; i < ThermalRadiators.MaxPanels; i++)
                    {
                        // Extension height is two large-grid cells. Require exact
                        // face contact, upright axis, grid and ownership. Failed
                        // panels retain the pipe path to healthy panels above.
                        // Placed yaw is compensated by the moving panel's pose.
                        Vector3D target = ThermalRadiators.ExtensionCentre(root.Block.WorldMatrix, i);
                        var slim = root.Block.CubeGrid.GetCubeBlock(root.Block.CubeGrid.WorldToGridInteger(target));
                        ThermalBlock panel;
                        if (slim == null || slim.FatBlock == null || !Blocks.TryGetValue(slim.FatBlock.EntityId, out panel)
                            || panel.Spec.Kind != ThermalKind.RadiatorPanel || !panel.CircuitReady
                            || !panel.Block.HasPlayerAccess(root.Block.OwnerId)
                            || !ThermalRadiators.FitsExtension(root.Block.WorldMatrix, panel.Block.WorldMatrix, i)) break;
                        panel.RadiatorBase = root;
                        root.RadiatorPanels.Add(panel);
                    }
                }
                if (previous != root.RadiatorPanels.Count
                    || (root.RadiatorPanels.Count > 0 && first != root.RadiatorPanels[0].Block.EntityId)
                    || (root.RadiatorPanels.Count > 1 && second != root.RadiatorPanels[1].Block.EntityId)
                    || (root.RadiatorPanels.Count > 2 && third != root.RadiatorPanels[2].Block.EntityId)) root.InvalidateRadiatorCooling();
                root.Store.Radiator.RequiredPanels = System.Math.Max(root.Store.Radiator.RequiredPanels, root.RadiatorPanels.Count);
            }
        }
    }
}
