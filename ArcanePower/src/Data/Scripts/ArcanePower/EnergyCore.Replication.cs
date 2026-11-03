using System.Collections.Generic;
using Sandbox.ModAPI;

namespace ArcanePower
{
    public sealed partial class EnergyCore
    {
        private long bankSequence;
        private int replicaAge;
        internal bool CanReceiveBank(EnergyBankState state) { return state.Sequence > bankSequence; }

        internal EnergyBankState CaptureBank()
        {
            var members = new List<long>();
            var active = new List<long>();
            float loss = 0, input = 0, output = 0;
            foreach (var cell in cells)
            {
                members.Add(cell.block.EntityId);
                loss += UpkeepPower(cell.StoredEnergy, cell.block.MaxStoredPower, cell.upkeepTier);
                input += cell.block.CurrentInput; output += cell.block.CurrentOutput;
            }
            if (IsController)
                foreach (var module in AttachedModules())
                    if (module != null && IsModuleRunning(module)) active.Add(module.EntityId);
            return new EnergyBankState { ControllerId = bankControllerId, Members = members.ToArray(), ActiveModules = active.ToArray(),
                Stored = stored, Capacity = capacity, Transfer = transfer, ChargeCeiling = chargeCeiling,
                InputLimit = inputLimit, OutputLimit = outputLimit, Reserve = reserve, EmergencyEnabled = emergencyEnabled,
                Emergency = emergency, UpkeepTier = upkeepTier, Status = status, Loss = loss, Input = input, Output = output,
                Sequence = ++bankSequence };
        }

        internal void ReceiveBank(EnergyBankState state)
        {
            if (MyAPIGateway.Multiplayer.IsServer || state == null || !state.Valid() || state.Sequence <= bankSequence) return;
            bankSequence = state.Sequence;
            replicaAge = 0;
            bankReplica = state;
            bankControllerId = state.ControllerId;
            stored = state.Stored; capacity = state.Capacity; transfer = state.Transfer; chargeCeiling = state.ChargeCeiling;
            reserve = state.Reserve; emergencyEnabled = state.EmergencyEnabled; emergency = state.Emergency;
            upkeepTier = state.UpkeepTier; status = state.Status;
            ApplyLimits(state.InputLimit, state.OutputLimit);
            block.RefreshCustomInfo();
        }

        private void UpdateReplication()
        {
            if (MyAPIGateway.Multiplayer.IsServer || ++replicaAge <= 180) return;
            if (bankReplica != null)
            {
                bankReplica = null;
                status = "Energy state stale / reconnecting";
                ApplyLimits(0, 0);
                block.RefreshCustomInfo();
            }
            if (replicaAge % 120 == 0) EnergySession.RequestSync(this);
        }
    }
}
