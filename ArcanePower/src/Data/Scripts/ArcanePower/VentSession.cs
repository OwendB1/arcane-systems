using System;
using System.Collections.Generic;
using System.Text;
using ProtoBuf;
using Sandbox.ModAPI;
using Sandbox.ModAPI.Interfaces.Terminal;
using VRage.Game.Components;
using VRage.Utils;

namespace ArcanePower
{
    public enum VentCommand { Sync, Start, Stop, Toggle }

    [ProtoContract]
    public sealed class VentPacket
    {
        [ProtoMember(1)] public long EntityId;
        [ProtoMember(2)] public VentCommand Command;
        [ProtoMember(3)] public MotionState State;
    }

    [MySessionComponentDescriptor(MyUpdateOrder.NoUpdate)]
    public sealed class VentSession : MySessionComponentBase
    {
        private const ushort Channel = 49371;
        private static readonly Dictionary<long, Reactor> Reactors = new Dictionary<long, Reactor>();
        private static bool ready;
        private readonly List<IMyTerminalAction> actions = new List<IMyTerminalAction>();
        private IMyTerminalControlButton control;

        public override void BeforeStart()
        {
            MyAPIGateway.Multiplayer.RegisterSecureMessageHandler(Channel, Receive);
            control = MyAPIGateway.TerminalControls.CreateControl<IMyTerminalControlButton, IMyReactor>("ArcanePower_Venting");
            control.Title = MyStringId.GetOrCompute("Vent reactor");
            control.Tooltip = MyStringId.GetOrCompute("Close the shield, cut power, open the top hatch and eject containment. Heat and load determine reactor/module damage. The cycle closes automatically and leaves the reactor off. Keep the top outlet clear. A committed cycle cannot be interrupted.");
            control.SupportsMultipleBlocks = true;
            control.Enabled = b => { Reactor r; return Reactors.TryGetValue(b.EntityId, out r) && r.Motion.Vent == VentPhase.Idle && r.Block.IsFunctional; };
            control.Action = b => SendCommand(b.EntityId, VentCommand.Start);
            AddAction("ArcanePower_StartVent", "Vent reactor", VentCommand.Start);
            AddAction("ArcanePower_ToggleVent", "Vent reactor", VentCommand.Toggle);
            MyAPIGateway.TerminalControls.CustomControlGetter += Controls;
            MyAPIGateway.TerminalControls.CustomActionGetter += Actions;
            ready = true;
            if (!MyAPIGateway.Multiplayer.IsServer)
                foreach (var r in Reactors.Values) SendCommand(r.Id, VentCommand.Sync);
        }

        private void AddAction(string id, string title, VentCommand command)
        {
            var action = MyAPIGateway.TerminalControls.CreateAction<IMyReactor>(id);
            action.Name = new StringBuilder(title);
            action.Icon = @"Textures\GUI\Icons\Actions\Toggle.dds";
            action.ValidForGroups = true;
            action.Enabled = b => { Reactor r; return Reactors.TryGetValue(b.EntityId, out r) && r.Motion.Vent == VentPhase.Idle && r.Block.IsFunctional; };
            action.Action = b => SendCommand(b.EntityId, command);
            action.Writer = (b, text) => { Reactor r; if (Reactors.TryGetValue(b.EntityId, out r)) text.Append(r.Motion.Vent); };
            actions.Add(action);
        }

        private void Controls(IMyTerminalBlock block, List<IMyTerminalControl> list)
        {
            if (Reactors.ContainsKey(block.EntityId)) list.Add(control);
        }
        private void Actions(IMyTerminalBlock block, List<IMyTerminalAction> list)
        {
            if (Reactors.ContainsKey(block.EntityId)) list.AddRange(actions);
        }

        internal static IEnumerable<Reactor> All { get { return Reactors.Values; } }
        internal static Reactor Find(long id) { Reactor result; return Reactors.TryGetValue(id, out result) ? result : null; }

        internal static void Add(Reactor reactor)
        {
            Reactors[reactor.Id] = reactor;
            if (ready && !MyAPIGateway.Multiplayer.IsServer) SendCommand(reactor.Id, VentCommand.Sync);
        }
        internal static void Remove(Reactor reactor) { Reactors.Remove(reactor.Id); }

        internal static void SendCommand(long entityId, VentCommand command)
        {
            if (!ready) return;
            if (MyAPIGateway.Multiplayer.IsServer)
            {
                Reactor r;
                if (!Reactors.TryGetValue(entityId, out r)) return;
                // Server-executed timer/PB actions have no local player; their
                // normal toolbar/terminal access is already handled by SE.
                var player = MyAPIGateway.Session.Player;
                if (player != null && !r.Block.HasPlayerAccess(player.IdentityId)) return;
                Apply(r, command);
            }
            else MyAPIGateway.Multiplayer.SendMessageToServer(Channel,
                MyAPIGateway.Utilities.SerializeToBinary(new VentPacket { EntityId = entityId, Command = command }));
        }

        private static void Apply(Reactor reactor, VentCommand command)
        {
            if (command == VentCommand.Start) reactor.RequestVent(true);
            else if (command == VentCommand.Stop) reactor.RequestVent(false);
            else if (command == VentCommand.Toggle) reactor.RequestVent(!reactor.Motion.Requested);
        }

        private void Receive(ushort channel, byte[] bytes, ulong sender, bool fromServer)
        {
            if (bytes == null || bytes.Length == 0 || bytes.Length > 4096) return;
            try
            {
                var packet = MyAPIGateway.Utilities.SerializeFromBinary<VentPacket>(bytes);
                if (packet == null) return;
                MyAPIGateway.Utilities.InvokeOnGameThread(() =>
                {
                    if (!ready) return;
                    Reactor r;
                    if (!Reactors.TryGetValue(packet.EntityId, out r)) return;
                    if (MyAPIGateway.Multiplayer.IsServer)
                    {
                        if (fromServer || packet.Command < VentCommand.Sync || packet.Command > VentCommand.Toggle) return;
                        if (packet.Command == VentCommand.Sync)
                        {
                            MyAPIGateway.Multiplayer.SendMessageTo(Channel,
                                MyAPIGateway.Utilities.SerializeToBinary(new VentPacket { EntityId = r.Id, State = r.Motion }), sender);
                            return;
                        }
                        long identity = MyAPIGateway.Players.TryGetIdentityId(sender);
                        if (identity == 0 || !r.Block.HasPlayerAccess(identity)) return;
                        Apply(r, packet.Command);
                    }
                    else if (fromServer && packet.State != null && packet.State.EntityId == packet.EntityId)
                        r.ReceiveState(packet.State);
                });
            }
            catch (Exception error) { MyLog.Default.WriteLine("ArcanePower: ignored invalid vent packet: " + error.Message); }
        }

        internal static void Broadcast(MotionState state)
        {
            if (ready && MyAPIGateway.Multiplayer.IsServer)
                MyAPIGateway.Multiplayer.SendMessageToOthers(Channel,
                    MyAPIGateway.Utilities.SerializeToBinary(new VentPacket { EntityId = state.EntityId, State = state }));
        }

        public override VRage.Game.MyObjectBuilder_SessionComponent GetObjectBuilder()
        {
            // SE snapshots the checkpoint before grids, but calls SaveData after
            // both. Flush registered block storage here so it enters this save.
            SaveData();
            return base.GetObjectBuilder();
        }

        public override void SaveData()
        {
            foreach (var r in Reactors.Values) r.SaveMotion();
        }

        protected override void UnloadData()
        {
            if (ready)
            {
                MyAPIGateway.Multiplayer.UnregisterSecureMessageHandler(Channel, Receive);
                MyAPIGateway.TerminalControls.CustomControlGetter -= Controls;
                MyAPIGateway.TerminalControls.CustomActionGetter -= Actions;
            }
            ready = false;
            Reactors.Clear();
            actions.Clear();
        }
    }
}
