using System.Collections.Generic;
using Sandbox.ModAPI;
using VRage.Game;
using VRage.Game.Components;
using VRage.Game.Entity;
using VRage.Game.ModAPI;
using VRage.ObjectBuilders;
using VRage.ModAPI;
using VRageMath;

namespace ArcanePower
{
    // Native motors own physics, attachment, controls, replication and conveyors.
    // This adapter only exposes the sealed duplex union to the thermal graph.
    public abstract class ThermalPipeJoint : MyGameLogicComponent
    {
        private static readonly Dictionary<long, ThermalPipeJoint> parts = new Dictionary<long, ThermalPipeJoint>();
        private IMyCubeBlock block;
        private ThermalModel model;
        private int revision;
        private IMyComponentStack components;
        private IMyMotorBase motor;

        public override void Init(MyObjectBuilder_EntityBase builder)
        {
            block = Entity as IMyCubeBlock;
            if (block == null || !ThermalModels.All.TryGetValue(block.BlockDefinition.SubtypeName, out model) || !model.Rotary) return;
            NeedsUpdate = MyEntityUpdateEnum.BEFORE_NEXT_FRAME;
        }

        public override void UpdateOnceBeforeFrame()
        {
            if (block == null || model == null || MyAPIGateway.Session == null) return;
            parts[block.EntityId] = this;
            components = block.SlimBlock.ComponentStack;
            components.IsFunctionalChanged += Changed;
            motor = block as IMyMotorBase;
            if (motor != null) motor.AttachedEntityChanged += AttachmentChanged;
        }

        private void Changed() { unchecked { revision++; } }
        private void AttachmentChanged(IMyMotorBase ignored) { Changed(); }

        internal static long Peer(IMyCubeBlock block)
        {
            var stator = block as IMyMotorAdvancedStator;
            var head = block as IMyMotorAdvancedRotor;
            if (head != null) stator = head.Base as IMyMotorAdvancedStator;
            if (stator == null || stator.Closed || stator.MarkedForClose || !stator.IsAttached || stator.PendingAttachment) return 0;
            var top = stator.Top as IMyMotorAdvancedRotor;
            if (top == null || top.Closed || top.MarkedForClose || top.Base != stator
                || (head != null && top != head) || stator.CubeGrid == top.CubeGrid
                || stator.BlockDefinition.SubtypeName != "ArcanePower_Thermal_PipeRotor"
                || top.BlockDefinition.SubtypeName != "ArcanePower_Thermal_PipeRotorHead") return 0;
            return head == null ? top.EntityId : stator.EntityId;
        }

        private ThermalEndpoint Endpoint(long owner)
        {
            Matrix rotation;
            block.Orientation.GetMatrix(out rotation);
            var terminal = block as IMyTerminalBlock;
            var relation = block.GetUserRelationToOwner(owner);
            bool access = owner != 0 && (terminal != null ? terminal.HasPlayerAccess(owner)
                : block.OwnerId == 0 || relation == MyRelationsBetweenPlayerAndBlock.Owner
                    || relation == MyRelationsBetweenPlayerAndBlock.FactionShare);
            var endpoint = ThermalEndpoint.At(block.EntityId, block.CubeGrid.EntityId, model, rotation,
                ((MyEntity)Entity).PositionComp.LocalMatrixRef.Translation,
                access && block.IsFunctional && block.SlimBlock.BuildLevelRatio >= 1 && block.CubeGrid.Physics != null);
            endpoint.RotaryPeerId = Peer(block);
            endpoint.Revision = revision;
            return endpoint;
        }

        internal static List<ThermalEndpoint> Snapshot(long owner)
        {
            var nodes = new List<ThermalEndpoint>();
            foreach (var part in parts.Values)
                if (part.block != null && !part.block.Closed && !part.block.MarkedForClose && part.block.CubeGrid != null)
                    nodes.Add(part.Endpoint(owner));
            nodes.Sort((a, b) => a.Id.CompareTo(b.Id));
            return nodes;
        }

        internal static IEnumerable<IMyCubeBlock> All
        {
            get
            {
                foreach (var part in parts.Values)
                    if (part.block != null && !part.block.Closed && !part.block.MarkedForClose)
                        yield return part.block;
            }
        }

        internal static void Unload() { parts.Clear(); }

        public override void Close()
        {
            if (block != null) parts.Remove(block.EntityId);
            if (components != null) components.IsFunctionalChanged -= Changed;
            if (motor != null) motor.AttachedEntityChanged -= AttachmentChanged;
        }
    }
}
