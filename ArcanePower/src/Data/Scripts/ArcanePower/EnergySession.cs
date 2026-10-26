using System;
using System.Collections.Generic;
using System.Text;
using ProtoBuf;
using Sandbox.ModAPI;
using Sandbox.ModAPI.Interfaces.Terminal;
using VRage.Game.Components;
using VRage.ModAPI;
using VRage.Utils;

namespace ArcanePower
{
    public enum EnergyCommand { Sync, Surge, Burst, Reserve, EmergencyOn, EmergencyOff }

    [ProtoContract]
    public sealed class EnergyPacket
    {
        [ProtoMember(1)] public long EntityId;
        [ProtoMember(2)] public EnergyCommand Command;
        // Protocol tag 3 belonged to the retired single-drive selector.
        [ProtoMember(4)] public float Value;
        [ProtoMember(5)] public EnergyGameplayState State;
        [ProtoMember(6)] public float Stored;
    }

    [MySessionComponentDescriptor(MyUpdateOrder.NoUpdate)]
    public sealed class EnergySession : MySessionComponentBase
    {
        private const ushort Channel = 49374;
        private static readonly Dictionary<long, EnergyCore> Cells = new Dictionary<long, EnergyCore>();
        internal static readonly Dictionary<long, JumpDriveSurge> Drives = new Dictionary<long, JumpDriveSurge>();
        private static bool ready;
        private readonly List<IMyTerminalControl> controls = new List<IMyTerminalControl>();
        private readonly List<IMyTerminalAction> actions = new List<IMyTerminalAction>();

        public override void BeforeStart()
        {
            MyAPIGateway.Multiplayer.RegisterSecureMessageHandler(Channel, Receive);
            AddButton("ArcanePower_Surge", "Surge jump drives", "Charge all affordable drives on this physical grid in 5 seconds at 90% efficiency, smallest deficits first. Temporarily boosts bank discharge for the selected batch. Protects reserve; requires Auto or Discharge and drive Recharge on. Recovery increases 25% per extra drive; see the core's batch summary.", EnergyCommand.Surge);
            AddButton("ArcanePower_Burst", "Burst discharge", "Double the bank discharge ceiling for 10 seconds. Input ceiling stays normal. Protects reserve; shares surge recovery. Reactor containment support takes priority.", EnergyCommand.Burst);
            var reserve = MyAPIGateway.TerminalControls.CreateControl<IMyTerminalControlSlider, IMyBatteryBlock>("ArcanePower_EnergyReserve");
            reserve.Title = MyStringId.GetOrCompute("Emergency reserve");
            reserve.Tooltip = MyStringId.GetOrCompute("Energy held from ordinary discharge and surges (0–90%). Passive storage loss still applies. Reactor support may release this reserve to the grid.");
            reserve.SetLimits(0, 90);
            reserve.Getter = b => { var core = Find(b.EntityId); return core == null ? 10 : core.ReservePercent; };
            reserve.Setter = (b, value) => Send(b.EntityId, EnergyCommand.Reserve, value);
            reserve.Writer = (b, text) => { var core = Find(b.EntityId); if (core != null) text.Append(core.ReservePercent.ToString("N0")).Append('%'); };
            controls.Add(reserve);
            var emergency = MyAPIGateway.TerminalControls.CreateControl<IMyTerminalControlOnOffSwitch, IMyBatteryBlock>("ArcanePower_EmergencySupport");
            emergency.Title = MyStringId.GetOrCompute("Reactor emergency support");
            emergency.Tooltip = MyStringId.GetOrCompute("Release reserve and switch Recharge to Auto for Arcane reactor startup, cooldown or venting. Released energy supplies the whole grid.");
            emergency.OnText = MyStringId.GetOrCompute("On");
            emergency.OffText = MyStringId.GetOrCompute("Off");
            emergency.Getter = b => { var core = Find(b.EntityId); return core != null && core.EmergencySupport; };
            emergency.Setter = (b, value) => Send(b.EntityId, value ? EnergyCommand.EmergencyOn : EnergyCommand.EmergencyOff);
            controls.Add(emergency);
            MyAPIGateway.TerminalControls.CustomControlGetter += Controls;
            MyAPIGateway.TerminalControls.CustomActionGetter += Actions;
            ready = true;
            if (!MyAPIGateway.Multiplayer.IsServer)
                foreach (var cell in Cells.Values) Send(cell.Block.EntityId, EnergyCommand.Sync);
        }

        private void AddButton(string id, string title, string tooltip, EnergyCommand command)
        {
            var control = MyAPIGateway.TerminalControls.CreateControl<IMyTerminalControlButton, IMyBatteryBlock>(id);
            control.Title = MyStringId.GetOrCompute(title);
            control.Tooltip = MyStringId.GetOrCompute(tooltip);
            control.Enabled = b => { var core = Find(b.EntityId); return core != null && core.Ready; };
            control.Action = b => Send(b.EntityId, command);
            controls.Add(control);
            var action = MyAPIGateway.TerminalControls.CreateAction<IMyBatteryBlock>(id);
            action.Name = new StringBuilder(title);
            action.Icon = @"Textures\GUI\Icons\Actions\Toggle.dds";
            action.ValidForGroups = true;
            action.Enabled = control.Enabled;
            action.Action = b => Send(b.EntityId, command);
            action.Writer = (b, text) => { var core = Find(b.EntityId); if (core != null) text.Append(core.Ready ? "Ready" : (core.Gameplay.RecoveryTicks / 60f).ToString("N0") + " s / unavailable"); };
            actions.Add(action);
        }

        private void Controls(IMyTerminalBlock block, List<IMyTerminalControl> list)
        {
            var core = Find(block.EntityId);
            if (core == null || !core.Controller) return;
            list.AddRange(controls);
        }
        private void Actions(IMyTerminalBlock block, List<IMyTerminalAction> list)
        {
            var core = Find(block.EntityId);
            if (core != null && core.Controller) list.AddRange(actions);
        }
        private static EnergyCore Find(long id) { EnergyCore cell; return Cells.TryGetValue(id, out cell) ? cell : null; }
        internal static void Add(EnergyCore cell)
        {
            Cells[cell.Block.EntityId] = cell;
            if (ready && !MyAPIGateway.Multiplayer.IsServer) Send(cell.Block.EntityId, EnergyCommand.Sync);
        }
        internal static void Remove(EnergyCore cell) { if (cell.Block != null) Cells.Remove(cell.Block.EntityId); }

        private static void Send(long id, EnergyCommand command, float value = 0)
        {
            if (!ready) return;
            var core = Find(id);
            if (core == null) return;
            var packet = new EnergyPacket { EntityId = id, Command = command, Value = value };
            if (MyAPIGateway.Multiplayer.IsServer)
            {
                var player = MyAPIGateway.Session.Player;
                if (player == null || core.Block.HasPlayerAccess(player.IdentityId)) Apply(core, packet);
            }
            else MyAPIGateway.Multiplayer.SendMessageToServer(Channel, MyAPIGateway.Utilities.SerializeToBinary(packet));
        }

        private static void Apply(EnergyCore core, EnergyPacket packet)
        {
            if (!core.Controller) return;
            if (packet.Command == EnergyCommand.Surge) core.RequestSurge();
            else if (packet.Command == EnergyCommand.Burst) core.RequestBurst();
            else if (packet.Command == EnergyCommand.Reserve) core.SetPolicy(packet.Value, null);
            else if (packet.Command == EnergyCommand.EmergencyOn || packet.Command == EnergyCommand.EmergencyOff)
                core.SetPolicy(null, packet.Command == EnergyCommand.EmergencyOn);
            Broadcast(core);
        }

        private static EnergyPacket Snapshot(EnergyCore core)
        {
            return new EnergyPacket { EntityId = core.Block.EntityId, State = core.Gameplay, Stored = core.Block.CurrentStoredPower };
        }
        internal static void Broadcast(EnergyCore core)
        {
            if (ready && MyAPIGateway.Multiplayer.IsServer)
                MyAPIGateway.Multiplayer.SendMessageToOthers(Channel, MyAPIGateway.Utilities.SerializeToBinary(Snapshot(core)));
        }
        private void Receive(ushort channel, byte[] bytes, ulong sender, bool fromServer)
        {
            if (bytes == null || bytes.Length == 0 || bytes.Length > 4096) return;
            try
            {
                var packet = MyAPIGateway.Utilities.SerializeFromBinary<EnergyPacket>(bytes);
                if (packet == null) return;
                MyAPIGateway.Utilities.InvokeOnGameThread(() =>
                {
                    if (!ready) return;
                    var core = Find(packet.EntityId);
                    if (core == null) return;
                    if (MyAPIGateway.Multiplayer.IsServer)
                    {
                        if (fromServer || packet.Command < EnergyCommand.Sync || packet.Command > EnergyCommand.EmergencyOff) return;
                        long identity = MyAPIGateway.Players.TryGetIdentityId(sender);
                        if (identity == 0 || !core.Block.HasPlayerAccess(identity)) return;
                        if (packet.Command == EnergyCommand.Sync)
                            MyAPIGateway.Multiplayer.SendMessageTo(Channel, MyAPIGateway.Utilities.SerializeToBinary(Snapshot(core)), sender);
                        else Apply(core, packet);
                    }
                    else if (fromServer) core.ReceiveGameplay(packet.State, packet.Stored);
                });
            }
            catch (Exception error) { MyLog.Default.WriteLine("ArcanePower: ignored invalid energy packet: " + error.Message); }
        }

        public override VRage.Game.MyObjectBuilder_SessionComponent GetObjectBuilder() { SaveData(); return base.GetObjectBuilder(); }
        public override void SaveData()
        {
            foreach (var cell in Cells.Values) cell.SaveGameplay();
            foreach (var drive in Drives.Values) drive.SaveRecovery();
        }
        protected override void UnloadData()
        {
            if (ready)
            {
                MyAPIGateway.Multiplayer.UnregisterSecureMessageHandler(Channel, Receive);
                MyAPIGateway.TerminalControls.CustomControlGetter -= Controls;
                MyAPIGateway.TerminalControls.CustomActionGetter -= Actions;
            }
            ready = false; Cells.Clear(); Drives.Clear(); controls.Clear(); actions.Clear();
        }
    }
}
