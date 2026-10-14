using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;
using Sandbox.Common.ObjectBuilders;
using Sandbox.Game.Entities;
using Sandbox.Game.EntityComponents;
using Sandbox.ModAPI;
using VRage.Game;
using VRage.Game.Components;
using VRage.Game.Entity;
using VRage.Game.ModAPI;
using VRage.ObjectBuilders;
using VRage.ModAPI;
using VRageMath;
using VRage.Game.ModAPI.Ingame.Utilities;
using ChargeMode = Sandbox.ModAPI.Ingame.ChargeMode;

namespace ArcanePower
{
    // Fixed native battery capacities; never edit a shared block definition or
    // move charge between blocks. The bank only allocates transfer limits.
    [MyEntityComponentDescriptor(typeof(MyObjectBuilder_BatteryBlock), false,
        "ArcanePower_EnergyCore", "ArcanePower_EnergyCapacity", "ArcanePower_EnergyCapacityAdvanced",
        "ArcanePower_EnergyCore_Pillar", "ArcanePower_EnergyCapacity_Pillar", "ArcanePower_EnergyCapacityAdvanced_Pillar")]
    public sealed class EnergyCore : MyGameLogicComponent
    {
        internal const string CoreSubtype = "ArcanePower_EnergyCore";
        private static readonly Guid IdentityKey = new Guid("f6e09e9a-76ef-4d21-9ef1-31e5cd759881");
        private static readonly MyDefinitionId Electricity = MyResourceDistributorComponent.ElectricityId;
        private MyBatteryBlock battery;
        private IMyBatteryBlock block;
        private readonly List<IMyReactor> reactors = new List<IMyReactor>();
        private readonly List<EnergyCore> cells = new List<EnergyCore>(3);
        private readonly List<EnergyCore> previousCells = new List<EnergyCore>(3);
        private readonly MyIni settings = new MyIni();
        private string settingsText;
        private float reserve = .10f;
        private bool emergencyEnabled = true, emergency, changingLimit, initialized;
        private float outputLimit, inputLimit, stored, capacity, transfer;
        private int tick;
        private string status = "Connecting storage";
        private Matrix rotorRest;
        private MyEntitySubpart rotor;
        private bool IsController { get { return BaseSubtype(block) == CoreSubtype; } }

        private static bool IsPillar(IMyCubeBlock candidate)
        {
            return candidate.BlockDefinition.SubtypeName.EndsWith("_Pillar", StringComparison.Ordinal);
        }

        private static string BaseSubtype(IMyCubeBlock candidate)
        {
            string name = candidate.BlockDefinition.SubtypeName;
            return IsPillar(candidate) ? name.Substring(0, name.Length - 7) : name;
        }

        public override void Init(MyObjectBuilder_EntityBase builder)
        {
            battery = (MyBatteryBlock)Entity;
            block = (IMyBatteryBlock)Entity;
            // Native socket compatibility/connection feedback. Bank limits remain
            // owned by UpdateBank, including socket roles and ownership checks.
            if (IsController)
            {
                block.AddUpgradeValue("ArcaneEnergyTransfer", 0f);
                block.AddUpgradeValue("ArcaneEnergyStabilizer", 0f);
            }
            block.AppendingCustomInfo += AppendInfo;
            NeedsUpdate = MyEntityUpdateEnum.BEFORE_NEXT_FRAME;
        }

        public override void UpdateOnceBeforeFrame()
        {
            if (MyAPIGateway.Session == null) { NeedsUpdate |= MyEntityUpdateEnum.BEFORE_NEXT_FRAME; return; }
            // New/projected/copied entity IDs start empty. Native save/load with
            // the same ID preserves native charge; grid splits keep block IDs.
            if (MyAPIGateway.Multiplayer.IsServer)
            {
                string id;
                if (Entity.Storage == null || !Entity.Storage.TryGetValue(IdentityKey, out id)
                    || id != Entity.EntityId.ToString(CultureInfo.InvariantCulture))
                    battery.CurrentStoredPower = 0;
                if (Entity.Storage == null) Entity.Storage = new MyModStorageComponent();
                Entity.Storage[IdentityKey] = Entity.EntityId.ToString(CultureInfo.InvariantCulture);
            }
            battery.SourceComp.MaxOutputChanged += ClampNativeOutput;
            initialized = true;
            ApplyLimits(0, 0);
            NeedsUpdate = MyEntityUpdateEnum.EACH_FRAME;
        }

        internal static bool Healthy(IMyCubeBlock candidate)
        {
            var functional = candidate as IMyFunctionalBlock;
            return candidate != null && !candidate.Closed && candidate.IsFunctional
                && candidate.SlimBlock.BuildLevelRatio >= 1 && (functional == null || functional.Enabled);
        }

        private IMyCubeBlock Socket(Vector3I direction)
        {
            var position = block.Position + direction * 2;
            var slim = block.CubeGrid.GetCubeBlock(position);
            var module = slim == null ? null : slim.FatBlock;
            var terminal = module as IMyTerminalBlock;
            if (!Healthy(module) || module.Position != position
                || Base6Directions.GetIntVector(module.Orientation.Forward) != -direction
                || IsPillar(module) != IsPillar(block)
                || (IsPillar(block) && module.Orientation.Up != block.Orientation.Up)
                || terminal == null || !terminal.HasPlayerAccess(block.OwnerId)) return null;
            return module;
        }

        private static int Tier(IMyCubeBlock module, string name)
        {
            if (module == null) return 0;
            string subtype = BaseSubtype(module);
            return subtype == name ? 1 : subtype == name + "Advanced" ? 2 : 0;
        }

        private EnergyCore FindController()
        {
            var direction = Base6Directions.GetIntVector(block.Orientation.Forward);
            var slim = block.CubeGrid.GetCubeBlock(block.Position + direction * 2);
            var candidate = slim == null ? null : slim.FatBlock;
            if (!Healthy(candidate) || BaseSubtype(candidate) != CoreSubtype
                || IsPillar(candidate) != IsPillar(block)
                || candidate.Position != block.Position + direction * 2) return null;
            return candidate.GameLogic.GetAs<EnergyCore>();
        }

        public override void UpdateBeforeSimulation()
        {
            if (!initialized) return;
            tick = (tick + 1) % 7200;
            if (tick % 10 == 1)
            {
                if (IsController) UpdateBank();
                else
                {
                    var controller = FindController();
                    if (controller == null || !controller.cells.Contains(this))
                        Disconnect();
                }
                block.RefreshCustomInfo();
            }
            if (!MyAPIGateway.Utilities.IsDedicated) Draw();
        }

        private void ReadSettings()
        {
            if (settingsText == block.CustomData) return;
            settingsText = block.CustomData;
            settings.Clear();
            reserve = .10f; emergencyEnabled = true;
            if (!settings.TryParse(settingsText)) return;
            float value = settings.Get("ArcaneEnergyCore", "ReservePercent").ToSingle(10);
            if (!float.IsNaN(value) && !float.IsInfinity(value)) reserve = MathHelper.Clamp(value, 0, 90) / 100;
            emergencyEnabled = settings.Get("ArcaneEnergyCore", "EmergencySupport").ToBoolean(true);
        }

        private void UpdateBank()
        {
            ReadSettings();
            previousCells.Clear(); previousCells.AddRange(cells);
            cells.Clear(); cells.Add(this);
            Vector3I up = Base6Directions.GetIntVector(block.Orientation.Up);
            Vector3I forward = Base6Directions.GetIntVector(block.Orientation.Forward);
            Vector3I right;
            Vector3I.Cross(ref forward, ref up, out right);
            int stabilizer = Tier(Socket(IsPillar(block) ? forward : up), "ArcanePower_EnergyStabilizer");
            int transferTier = Tier(Socket(-forward), "ArcanePower_EnergyTransfer");
            transferTier = Math.Min(transferTier, stabilizer);
            transfer = transferTier == 2 ? 1000000 : transferTier == 1 ? 100000 : 10000;
            foreach (var direction in new[] { right, -right })
            {
                var module = Socket(direction);
                int tier = Tier(module, "ArcanePower_EnergyCapacity");
                var cell = tier > 0 && tier <= stabilizer ? module.GameLogic.GetAs<EnergyCore>() : null;
                if (cell != null && cell.initialized) cells.Add(cell);
            }
            // Revoke the old allocation in this same bank update, regardless of
            // the removed cell's update order, ownership or current grid.
            foreach (var cell in previousCells)
                if (!cell.block.Closed && !cells.Contains(cell)) cell.Disconnect();
            stored = 0; capacity = 0;
            foreach (var cell in cells) { stored += cell.block.CurrentStoredPower; capacity += cell.block.MaxStoredPower; }
            if (tick % 100 == 1)
            {
                reactors.Clear();
                var terminal = MyAPIGateway.TerminalActionsHelper.GetTerminalSystemForGrid(block.CubeGrid);
                if (terminal != null) terminal.GetBlocksOfType(reactors,
                    r => r.CubeGrid == block.CubeGrid && r.HasPlayerAccess(block.OwnerId));
            }
            emergency = false;
            if (emergencyEnabled)
                foreach (var reactor in reactors)
                {
                    if (reactor.Closed || reactor.CubeGrid != block.CubeGrid || !reactor.HasPlayerAccess(block.OwnerId)) continue;
                    var logic = reactor.GameLogic.GetAs<Reactor>();
                    if (logic != null && logic.NeedsStorageSupport) { emergency = true; break; }
                }
            if (MyAPIGateway.Multiplayer.IsServer && Healthy(block) && emergency && block.ChargeMode == ChargeMode.Recharge)
                block.ChargeMode = ChargeMode.Auto; // Deliberately visible and persistent; no silent switch back.
            status = !Healthy(block) ? "Core offline" : emergency ? "Emergency reserve available (Auto override)"
                : stored <= capacity * reserve ? "Reserve held; emergency support available" : "Storage online";
            foreach (var cell in cells)
            {
                if (MyAPIGateway.Multiplayer.IsServer && cell != this) cell.block.ChargeMode = block.ChargeMode;
                float share = capacity > 0 ? transfer * cell.block.MaxStoredPower / capacity : 0;
                float protectedEnergy = emergency ? 0 : reserve * cell.block.MaxStoredPower;
                // Native batteries account every 100 ticks. Bound each interval
                // by energy above reserve instead of overshooting a threshold.
                float output = Math.Min(share, Math.Max(0, cell.block.CurrentStoredPower - protectedEnergy) * 2160);
                cell.status = status;
                cell.ApplyLimits(Healthy(block) ? share : 0, Healthy(block) ? output : 0);
            }
        }

        private void Disconnect()
        {
            status = "Disconnected or unsupported capacity module";
            ApplyLimits(0, 0);
        }

        private void ApplyLimits(float input, float output)
        {
            inputLimit = Healthy(block) ? input : 0;
            outputLimit = Healthy(block) ? output : 0;
            battery.ResourceSink.SetMaxRequiredInputByType(Electricity, inputLimit);
            battery.ResourceSink.Update();
            float nativeLimit = block.ChargeMode != ChargeMode.Recharge
                ? outputLimit : 0;
            changingLimit = true;
            battery.SourceComp.SetMaxOutputByType(Electricity, nativeLimit);
            changingLimit = false;
        }

        private void ClampNativeOutput(MyDefinitionId resource, float previous, MyResourceSourceComponent source)
        {
            if (changingLimit || resource != Electricity) return;
            // Native battery refreshes its source on charge/mode/working changes.
            // Clamp synchronously so those refreshes cannot bypass bank limits.
            float limit = Healthy(block) && block.ChargeMode != ChargeMode.Recharge
                ? Math.Min(source.MaxOutputUnlimitedByCapacity(resource), outputLimit) : 0;
            changingLimit = true;
            source.SetMaxOutputByType(resource, limit);
            changingLimit = false;
        }

        private void Draw()
        {
            var camera = MyAPIGateway.Session.Camera;
            if (camera == null || Vector3D.DistanceSquared(camera.Position, Entity.GetPosition()) > 300 * 300) return;
            var model = (MyEntity)Entity;
            bool online = Healthy(block) && inputLimit > 0;
            float fraction = IsController ? (capacity > 0 ? stored / capacity : 0)
                : block.CurrentStoredPower / Math.Max(1, block.MaxStoredPower);
            fraction = MathHelper.Clamp(fraction, 0, 1);
            Color color = block.CurrentInput > block.CurrentOutput + .01f ? new Color(40, 185, 255)
                : block.CurrentOutput > .01f ? new Color(255, 145, 40) : new Color(100, 120, 200);
            float glow = online ? .05f + .7f * fraction : 0;
            if (tick % 10 == 1)
            {
                model.SetEmissiveParts("EnergyGlow", color, glow);
                for (int i = 1; i <= 4; i++)
                    model.SetEmissiveParts("EnergyFill" + i, color, online ? (fraction >= i / 4f ? .6f : .01f) : 0);
            }
            MyEntitySubpart part;
            if (model.Subparts.TryGetValue("EnergyRotor", out part))
            {
                if (part != rotor) { rotor = part; rotorRest = part.PositionComp.LocalMatrixRef; }
                if (online)
                {
                    Matrix pose = Matrix.CreateRotationY(tick * MathHelper.TwoPi / 7200f) * rotorRest;
                    pose.Translation = rotorRest.Translation;
                    part.PositionComp.SetLocalMatrix(ref pose);
                }
                if (tick % 10 == 1) part.SetEmissiveParts("EnergyGlow", color, glow);
            }
        }

        private void AppendInfo(IMyTerminalBlock source, StringBuilder text)
        {
            text.Append("\nARCANE ENERGY STORAGE\n").Append(status).Append('\n');
            if (IsController)
            {
                text.Append("Bank: ").Append(stored.ToString("N1")).Append(" / ").Append(capacity.ToString("N1")).Append(" MWh\n");
                text.Append("Transfer ceiling: ").Append(transfer.ToString("N0")).Append(" MW\nCapacity modules: ").Append(Math.Max(0, cells.Count - 1)).Append(" / 2\n");
                text.Append("Reserve: ").Append((reserve * 100).ToString("N0")).Append("%; emergency support ").Append(emergencyEnabled ? "on" : "off").Append('\n');
                text.Append("Recharge changes to Auto for reactor startup/cooldown/venting and stays Auto.\n");
                text.Append("Custom Data [ArcaneEnergyCore]: ReservePercent=10, EmergencySupport=true\n");
            }
            text.Append("This cell input/output limits: ").Append(inputLimit.ToString("N0")).Append(" / ").Append(outputLimit.ToString("N0")).Append(" MW\n");
            text.Append("Capacity stays in its physical battery. New/projected/copied blocks start empty.");
        }

        public override void Close()
        {
            if (block != null) block.AppendingCustomInfo -= AppendInfo;
            if (battery != null && initialized) battery.SourceComp.MaxOutputChanged -= ClampNativeOutput;
        }
    }
}
