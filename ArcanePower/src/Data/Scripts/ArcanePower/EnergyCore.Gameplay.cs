using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;
using ProtoBuf;
using Sandbox.Common.ObjectBuilders;
using Sandbox.Game.EntityComponents;
using Sandbox.ModAPI;
using VRage.Game.Components;
using VRage.Game.Entity;
using VRage.Game.ModAPI;
using VRage.ModAPI;
using VRage.ObjectBuilders;
using VRage.Utils;
using ChargeMode = Sandbox.ModAPI.Ingame.ChargeMode;
using MyJumpDriveStatus = Sandbox.ModAPI.Ingame.MyJumpDriveStatus;

namespace ArcanePower
{
    [ProtoContract]
    public sealed class EnergyGameplayState
    {
        [ProtoMember(1)] public long EntityId;
        [ProtoMember(2)] public long DriveId;
        [ProtoMember(3)] public int SurgeTicks;
        [ProtoMember(4)] public int BurstTicks;
        [ProtoMember(5)] public int RecoveryTicks;
        [ProtoMember(6)] public float SurgeRate;
        [ProtoMember(7)] public string Result = "Ready";
    }

    public sealed partial class EnergyCore
    {
        internal static readonly Guid GameplayKey = new Guid("f2451ae5-ea04-47b8-a5f5-59f75583cdb4");
        internal IMyBatteryBlock Block { get { return block; } }
        internal bool Controller { get { return IsController; } }
        internal EnergyGameplayState Gameplay { get { return gameplay; } }
        private EnergyGameplayState gameplay = new EnergyGameplayState();
        private int stabilizationTier, upkeepTier, surgeDuration = 600;
        private float upkeepMW, replicatedStored = float.NaN;
        private double upkeepDebt;
        private JumpDriveSurge activeDrive;
        private readonly List<IMyJumpDrive> jumpDrives = new List<IMyJumpDrive>();
        internal long SelectedDrive;
        internal float ReservePercent { get { ReadSettings(); return reserve * 100; } }
        internal bool EmergencySupport { get { ReadSettings(); return emergencyEnabled; } }
        private float StoredEnergy { get { return MyAPIGateway.Multiplayer.IsServer || float.IsNaN(replicatedStored) ? block.CurrentStoredPower : replicatedStored; } }
        internal bool Ready { get { return initialized && Healthy(block) && !emergency && gameplay.RecoveryTicks == 0 && block.ChargeMode != ChargeMode.Recharge; } }

        private void InitializeGameplay(bool original)
        {
            gameplay = new EnergyGameplayState();
            string saved;
            if (original && IsController && Entity.Storage.TryGetValue(GameplayKey, out saved))
            {
                try
                {
                    var state = MyAPIGateway.Utilities.SerializeFromXML<EnergyGameplayState>(saved);
                    if (state != null && state.EntityId == Entity.EntityId)
                    {
                        state.SurgeTicks = Math.Max(0, Math.Min(600, state.SurgeTicks));
                        state.BurstTicks = Math.Max(0, Math.Min(600, state.BurstTicks));
                        state.RecoveryTicks = Math.Max(0, Math.Min(7800, state.RecoveryTicks));
                        state.RecoveryTicks = Math.Max(state.RecoveryTicks, Math.Max(state.SurgeTicks, state.BurstTicks));
                        if (float.IsNaN(state.SurgeRate) || float.IsInfinity(state.SurgeRate) || state.SurgeRate < 0) state.SurgeTicks = 0;
                        gameplay = state;
                    }
                }
                catch (Exception error) { MyLog.Default.WriteLine("ArcanePower: cannot restore energy bank: " + error.Message); }
            }
            gameplay.EntityId = Entity.EntityId;
        }

        internal void SetPolicy(float? percent, bool? support)
        {
            if (!MyAPIGateway.Multiplayer.IsServer || !IsController) return;
            if (percent.HasValue && (float.IsNaN(percent.Value) || float.IsInfinity(percent.Value))) return;
            if (!settings.TryParse(block.CustomData) && !string.IsNullOrWhiteSpace(block.CustomData))
            {
                gameplay.Result = "Reserve settings unchanged: Custom Data must be valid INI";
                return;
            }
            if (percent.HasValue) settings.Set("ArcaneEnergyCore", "ReservePercent", Math.Max(0, Math.Min(90, percent.Value)));
            if (support.HasValue) settings.Set("ArcaneEnergyCore", "EmergencySupport", support.Value);
            block.CustomData = settings.ToString();
            UpdateBank();
        }

        // Loss MW is quadratic in fill. Full cells lose 1/.5/.25 percent per
        // simulated minute at bare/standard/advanced stabilization. Detached and
        // disabled cells still leak; no offline wall-clock catch-up is applied.
        private static float UpkeepPower(float energy, float maximum, int tier)
        {
            return maximum > 0 ? (float)(Math.Max(0, energy) * (double)Math.Max(0, energy) / maximum * .6 / (1 << tier)) : 0;
        }

        private void UpdateUpkeep()
        {
            upkeepMW = UpkeepPower(StoredEnergy, block.MaxStoredPower, upkeepTier);
            if (!MyAPIGateway.Multiplayer.IsServer || MyAPIGateway.Session.CreativeMode) return;
            upkeepDebt += upkeepMW / 21600.0; // Ten ticks at 60 Hz, MW -> MWh.
            if (upkeepDebt <= 0) return;
            float before = block.CurrentStoredPower;
            float after = (float)Math.Max(0, before - upkeepDebt);
            if (after != before)
            {
                battery.CurrentStoredPower = after;
                upkeepDebt -= before - after; // Carry fractional native float rounding.
            }
            if (after == 0) upkeepDebt = 0;
        }

        internal void ReceiveGameplay(EnergyGameplayState state, float energy)
        {
            if (state == null || state.EntityId != Entity.EntityId || float.IsNaN(energy) || float.IsInfinity(energy)) return;
            gameplay = state;
            replicatedStored = Math.Max(0, Math.Min(block.MaxStoredPower, energy));
            block.RefreshCustomInfo();
        }

        internal void SaveGameplay()
        {
            if (!initialized || !IsController || !MyAPIGateway.Multiplayer.IsServer || Entity.Storage == null) return;
            Entity.Storage[GameplayKey] = MyAPIGateway.Utilities.SerializeToXML(gameplay);
        }

        private bool EligibleDrive(IMyJumpDrive drive)
        {
            return Healthy(drive) && drive.CubeGrid == block.CubeGrid && drive.HasPlayerAccess(block.OwnerId)
                && drive.Recharge && drive.Status != MyJumpDriveStatus.Jumping
                && drive.MaxStoredPower > 0 && drive.CurrentStoredPower < drive.MaxStoredPower;
        }

        internal void GetJumpDrives(List<IMyJumpDrive> list)
        {
            var terminal = MyAPIGateway.TerminalActionsHelper.GetTerminalSystemForGrid(block.CubeGrid);
            if (terminal != null) terminal.GetBlocksOfType(list, EligibleDrive);
            list.Sort((a, b) => a.EntityId.CompareTo(b.EntityId));
        }

        internal void RequestSurge(long targetId)
        {
            if (!MyAPIGateway.Multiplayer.IsServer || !IsController) return;
            UpdateBank();
            if (!Ready) { gameplay.Result = "Surge unavailable: core, mode, containment support or recovery"; return; }
            jumpDrives.Clear(); GetJumpDrives(jumpDrives);
            foreach (var drive in jumpDrives)
            {
                if (targetId != 0 && drive.EntityId != targetId) continue;
                var surge = drive.GameLogic.GetAs<JumpDriveSurge>();
                if (surge == null || !surge.Claim(Entity.EntityId)) continue;
                if (AvailableEnergy() <= 0) { surge.Release(Entity.EntityId); break; }
                activeDrive = surge;
                gameplay.DriveId = drive.EntityId;
                gameplay.SurgeTicks = surgeDuration;
                gameplay.SurgeRate = (drive.MaxStoredPower - drive.CurrentStoredPower) * 216000f / surgeDuration / .9f * 1.01f;
                gameplay.RecoveryTicks = surgeDuration + RecoveryDuration();
                surge.StartRecovery(gameplay.RecoveryTicks);
                gameplay.Result = "Jump-drive surge active";
                SaveGameplay();
                return;
            }
            gameplay.Result = "No available drive or energy above reserve";
        }

        internal void RequestBurst()
        {
            if (!MyAPIGateway.Multiplayer.IsServer || !IsController) return;
            UpdateBank();
            if (!Ready || AvailableEnergy() <= 0) { gameplay.Result = "Burst unavailable: core, mode, reserve, containment support or recovery"; return; }
            gameplay.BurstTicks = 600;
            gameplay.RecoveryTicks = 600 + RecoveryDuration();
            gameplay.Result = "Burst discharge active";
            UpdateBank();
            SaveGameplay();
        }

        private int RecoveryDuration() { return 7200 - stabilizationTier * 1800; }

        private float AvailableEnergy()
        {
            float result = 0;
            foreach (var cell in cells) result += SpendableEnergy(cell);
            return result;
        }

        private float SpendableEnergy(EnergyCore cell)
        {
            // Native output is billed every 100 ticks. Hold that commitment in
            // addition to the reserve so a direct debit cannot spend it twice.
            return Healthy(cell.block) ? Math.Max(0, cell.block.CurrentStoredPower - reserve * cell.block.MaxStoredPower
                - cell.block.CurrentOutput / 2160f - UpkeepPower(cell.block.CurrentStoredPower, cell.block.MaxStoredPower, cell.upkeepTier) / 2160f) : 0;
        }

        private float DebitEnergy(float requested, float budget)
        {
            float removed = 0;
            foreach (var cell in cells)
            {
                float before = cell.block.CurrentStoredPower;
                float allowance = Math.Min(SpendableEnergy(cell), budget - removed);
                float desired = Math.Min(allowance, requested - removed);
                if (desired <= 0) continue;
                float after = before - desired;
                // Pay for the final representable fraction of charge instead of
                // leaving a drive almost full. Never exceed throughput or reserve.
                if (after == before)
                {
                    int bits = BitConverter.ToInt32(BitConverter.GetBytes(before), 0);
                    after = BitConverter.ToSingle(BitConverter.GetBytes(bits - 1), 0);
                }
                if (before - after > allowance)
                {
                    int bits = BitConverter.ToInt32(BitConverter.GetBytes(after), 0);
                    after = BitConverter.ToSingle(BitConverter.GetBytes(bits + 1), 0);
                }
                float actual = before - after;
                if (actual <= 0 || actual > allowance) continue;
                cell.battery.CurrentStoredPower = after;
                removed += actual;
                cell.ApplyLimits(cell.inputLimit, Math.Max(0, cell.outputLimit - actual * 21600f));
            }
            return removed;
        }

        private void UpdateSurge()
        {
            if (!MyAPIGateway.Multiplayer.IsServer || gameplay.SurgeTicks <= 0) return;
            if (activeDrive == null)
            {
                IMyEntity entity;
                if (MyAPIGateway.Entities.TryGetEntityById(gameplay.DriveId, out entity))
                    activeDrive = entity.GameLogic.GetAs<JumpDriveSurge>();
                if (activeDrive != null && !activeDrive.ResumeClaim(Entity.EntityId)) activeDrive = null;
            }
            var drive = activeDrive == null ? null : activeDrive.Block;
            if (!Healthy(block) || emergency || block.ChargeMode == ChargeMode.Recharge || !EligibleDrive(drive))
            {
                EndSurge(drive != null && drive.CurrentStoredPower >= drive.MaxStoredPower ? "Surge complete" : "Surge stopped: target, hardware, mode or containment support");
                return;
            }
            float gridOutput = 0;
            foreach (var cell in cells) gridOutput += cell.block.CurrentOutput;
            float allowance = Math.Min(gameplay.SurgeRate, Math.Max(0, transfer - gridOutput)) / 21600f;
            float missing = drive.MaxStoredPower - drive.CurrentStoredPower;
            float debit = DebitEnergy(missing / .9f, allowance);
            if (debit <= 0) { EndSurge("Surge stopped: transfer or reserve unavailable"); return; }
            drive.CurrentStoredPower = Math.Min(drive.MaxStoredPower, drive.CurrentStoredPower + debit * .9f);
            gameplay.SurgeTicks = Math.Max(0, gameplay.SurgeTicks - 10);
            if (drive.CurrentStoredPower >= drive.MaxStoredPower || gameplay.SurgeTicks == 0)
                EndSurge(drive.CurrentStoredPower >= drive.MaxStoredPower ? "Surge complete" : "Surge finished; remaining charge uses normal recharge");
        }

        private void EndSurge(string result)
        {
            gameplay.SurgeTicks = 0;
            gameplay.Result = result;
            ReleaseDrive();
            gameplay.DriveId = 0;
            SaveGameplay();
        }

        private void ReleaseDrive()
        {
            if (activeDrive != null) activeDrive.Release(Entity.EntityId);
            activeDrive = null;
        }

        private void UpdateRecovery()
        {
            if (!MyAPIGateway.Multiplayer.IsServer || !IsController) return;
            if (gameplay.RecoveryTicks > 0) gameplay.RecoveryTicks--;
            if (gameplay.BurstTicks > 0)
            {
                gameplay.BurstTicks--;
                if (!Healthy(block) || emergency || block.ChargeMode == ChargeMode.Recharge) gameplay.BurstTicks = 0;
                if (gameplay.BurstTicks == 0) { gameplay.Result = "Burst ended"; UpdateBank(); }
            }
        }

        private void AppendGameplayInfo(StringBuilder text)
        {
            float loss = 0, input = 0, output = 0;
            foreach (var cell in cells) { loss += UpkeepPower(cell.StoredEnergy, cell.block.MaxStoredPower, cell.upkeepTier); input += cell.block.CurrentInput; output += cell.block.CurrentOutput; }
            text.Append("Bank upkeep: ").Append(loss.ToString("N1")).Append(" MW equivalent; loss rises with fill\n");
            text.Append("Net flow (approx.): ").Append((input * .9f - output - loss).ToString("N1")).Append(" MW\n");
            if (output + loss > input * .9f)
                text.Append("Reserve endurance (approx.): ").Append((Math.Max(0, stored - capacity * reserve) / (output + loss - input * .9f) * 3600).ToString("N0")).Append(" s\n");
            text.Append(gameplay.Result).Append("; recovery ").Append((gameplay.RecoveryTicks / 60f).ToString("N1")).Append(" s\n");
            text.Append("Surge ").Append((surgeDuration / 60f).ToString("N1")).Append(" s; 90% transfer efficiency; protects reserve\n");
            if (gameplay.SurgeTicks > 0) text.Append("Surge remaining: ").Append((gameplay.SurgeTicks / 60f).ToString("N1")).Append(" s; target ").Append(gameplay.DriveId).Append('\n');
            if (gameplay.BurstTicks > 0) text.Append("Burst remaining: ").Append((gameplay.BurstTicks / 60f).ToString("N1")).Append(" s; discharge ceiling ").Append((transfer * 2).ToString("N0")).Append(" MW\n");
        }
    }

    // The drive owns its recovery and claim, so changing banks or grid topology
    // cannot bypass the cooldown. Native jump behavior is otherwise untouched.
    [MyEntityComponentDescriptor(typeof(MyObjectBuilder_JumpDrive), false)]
    public sealed class JumpDriveSurge : MyGameLogicComponent
    {
        internal static readonly Guid RecoveryKey = new Guid("619d89c8-88c2-46f5-bdb1-1f60d7b3f00e");
        internal IMyJumpDrive Block;
        private long bankId;
        private int recovery, tick;
        private bool initialized;

        public override void Init(MyObjectBuilder_EntityBase builder)
        {
            Block = (IMyJumpDrive)Entity;
            NeedsUpdate = MyEntityUpdateEnum.BEFORE_NEXT_FRAME;
        }

        public override void UpdateOnceBeforeFrame()
        {
            if (MyAPIGateway.Session == null) { NeedsUpdate |= MyEntityUpdateEnum.BEFORE_NEXT_FRAME; return; }
            if (!MyAPIGateway.Multiplayer.IsServer) return;
            string saved;
            if (Entity.Storage != null && Entity.Storage.TryGetValue(RecoveryKey, out saved))
            {
                var fields = saved.Split(':'); long identity; int ticks;
                if (fields.Length == 2 && long.TryParse(fields[0], out identity) && identity == Entity.EntityId && int.TryParse(fields[1], out ticks))
                    recovery = Math.Max(0, Math.Min(7800, ticks));
            }
            initialized = true;
            EnergySession.Drives[Entity.EntityId] = this;
            NeedsUpdate = recovery > 0 ? MyEntityUpdateEnum.EACH_FRAME : MyEntityUpdateEnum.NONE;
        }

        internal bool Claim(long bank) { return recovery == 0 && ResumeClaim(bank); }
        internal bool ResumeClaim(long bank)
        {
            if (!initialized || (bankId != 0 && bankId != bank)) return false;
            bankId = bank; return true;
        }
        internal void Release(long bank) { if (bankId == bank) bankId = 0; }
        internal void StartRecovery(int ticks) { recovery = ticks; NeedsUpdate = MyEntityUpdateEnum.EACH_FRAME; SaveRecovery(); }
        internal void SaveRecovery()
        {
            if (!initialized || (recovery == 0 && (Entity.Storage == null || !Entity.Storage.ContainsKey(RecoveryKey)))) return;
            if (Entity.Storage == null) Entity.Storage = new MyModStorageComponent();
            Entity.Storage[RecoveryKey] = Entity.EntityId.ToString(CultureInfo.InvariantCulture) + ":" + recovery.ToString(CultureInfo.InvariantCulture);
        }
        public override void UpdateBeforeSimulation()
        {
            if (recovery > 0) recovery--;
            if (++tick % 60 == 0 || recovery == 0) SaveRecovery();
            if (recovery == 0) NeedsUpdate = MyEntityUpdateEnum.NONE;
        }
        public override void Close() { if (initialized) SaveRecovery(); EnergySession.Drives.Remove(Entity.EntityId); }
    }
}
