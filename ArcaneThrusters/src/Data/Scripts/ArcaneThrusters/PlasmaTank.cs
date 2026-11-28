using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;
using Sandbox.Common.ObjectBuilders;
using Sandbox.Definitions;
using Sandbox.Game.EntityComponents;
using Sandbox.ModAPI;
using VRage.Game;
using VRage.Game.Components;
using VRage.Game.ModAPI;
using VRage.ModAPI;
using VRage.ObjectBuilders;

namespace ArcaneThrusters
{
    [MyEntityComponentDescriptor(typeof(MyObjectBuilder_OxygenTank), false,
        "ArcaneThrusters_PlasmaTankLG", "ArcaneThrusters_PlasmaTankSG")]
    public sealed class PlasmaTank : MyGameLogicComponent
    {
        private const int HoldFrames = 600;
        private const int CoolingInterval = 60;
        private const float HoldingMWPerLitre = .000002f;
        private const double CoolingFraction = .01;
        private static readonly Guid StorageKey = new Guid("b24b3fe3-5ac6-4505-8acf-7de778537bad");
        private static readonly MyDefinitionId Electricity = MyResourceDistributorComponent.ElectricityId;
        private static readonly MyDefinitionId Hydrogen = MyDefinitionId.Parse("GasProperties/Hydrogen");
        private readonly List<IMyGasTank> receivers = new List<IMyGasTank>();
        private FieldReading reading = new FieldReading();
        private IMyGasTank tank;
        private MyResourceSinkComponent sink;
        private Func<float> nativePower;
        private float nativeMax;
        private int outageFrames, sampleFrames, steadySamples;
        private bool haveReading, coolingStarted;

        public override void Init(MyObjectBuilder_EntityBase builder)
        {
            NeedsUpdate = MyEntityUpdateEnum.BEFORE_NEXT_FRAME;
        }

        public override void UpdateOnceBeforeFrame()
        {
            tank = (IMyGasTank)Entity;
            if (tank.CubeGrid.Physics == null) return;
            sink = tank.Components.Get<MyResourceSinkComponent>();
            if (MyAPIGateway.Session == null || sink == null)
            {
                NeedsUpdate |= MyEntityUpdateEnum.BEFORE_NEXT_FRAME;
                return;
            }
            nativeMax = sink.MaxRequiredInputByType(Electricity);
            nativePower = sink.SetRequiredInputFuncByType(Electricity, RequiredPower);
            sink.SetMaxRequiredInputByType(Electricity, nativeMax + tank.Capacity * HoldingMWPerLitre);
            sink.Update();
            tank.AppendingCustomInfo += AppendInfo;
            if (MyAPIGateway.Multiplayer.IsServer)
            {
                LoadOutage();
                reading.EntityId = tank.EntityId;
                NeedsUpdate |= MyEntityUpdateEnum.EACH_10TH_FRAME;
            }
        }

        private float RequiredPower()
        {
            if (!tank.Enabled || !tank.IsFunctional) return 0;
            return nativePower() + (float)(tank.Capacity * tank.FilledRatio) * HoldingMWPerLitre;
        }

        public override void UpdateAfterSimulation10()
        {
            int previous = outageFrames;
            float demand = RequiredPower();
            float delivered = sink.CurrentInputByType(Electricity);
            // During transfer the fill (and next demand) can change every frame.
            // Compare delivery with the demand from the same distributor allocation.
            bool powered = demand > 0 && delivered > 0 && sink.SuppliedRatioByType(Electricity) >= .99999f;
            if (powered || tank.FilledRatio <= 0) outageFrames = 0;
            else
            {
                outageFrames += 10;
                if (outageFrames >= HoldFrames + CoolingInterval)
                {
                    if (!coolingStarted)
                    {
                        reading.Recovered = 0;
                        reading.Vented = 0;
                        coolingStarted = true;
                    }
                    Cool();
                    outageFrames -= CoolingInterval;
                }
            }
            if (outageFrames == 0) coolingStarted = false;
            if (outageFrames != previous) SaveOutage();

            sampleFrames += 10;
            if (sampleFrames < 60 && haveReading) return;
            sampleFrames = 0;
            string state = tank.FilledRatio <= 0 ? "Empty" : powered ? "Confined"
                : outageFrames < HoldFrames ? "Field power lost" : "Cooling";
            bool changed = !haveReading || state != reading.State || demand != reading.Demand
                || delivered != reading.Delivered || outageFrames > 0;
            reading.State = state;
            reading.HoldSeconds = (Math.Max(0, HoldFrames - outageFrames) + 59) / 60;
            reading.Demand = demand;
            reading.Delivered = delivered;
            haveReading = true;
            if (changed) RefreshTerminal();
            // A periodic steady reading also reaches pilots who just entered sync range.
            if (changed || ++steadySamples >= 10)
            {
                steadySamples = 0;
                FieldTelemetry.Send(tank, reading);
            }
        }

        private void Cool()
        {
            double before = tank.FilledRatio;
            tank.ChangeFilledRatio(Math.Max(0, before - CoolingFraction), true);
            double remaining = (before - tank.FilledRatio) * tank.Capacity;
            if (remaining <= 0) return;
            var terminal = MyAPIGateway.TerminalActionsHelper.GetTerminalSystemForGrid(tank.CubeGrid);
            receivers.Clear();
            if (terminal != null) terminal.GetBlocksOfType(receivers, IsReceiver);
            foreach (IMyGasTank receiver in receivers)
            {
                if (!tank.GetInventory().IsConnectedTo(receiver.GetInventory())) continue;
                double oldRatio = receiver.FilledRatio;
                double newRatio = Math.Min(1, oldRatio + remaining / receiver.Capacity);
                receiver.ChangeFilledRatio(newRatio, true);
                double accepted = Math.Min(remaining, (receiver.FilledRatio - oldRatio) * receiver.Capacity);
                reading.Recovered += accepted;
                remaining -= accepted;
                if (remaining <= 0) break;
            }
            reading.Vented += remaining;
        }

        private bool IsReceiver(IMyGasTank candidate)
        {
            if (candidate == tank || !candidate.IsWorking || candidate.FilledRatio >= 1
                || !candidate.HasPlayerAccess(tank.OwnerId) || !candidate.HasInventory) return false;
            var definition = candidate.SlimBlock.BlockDefinition as MyGasTankDefinition;
            return definition != null && definition.StoredGasId == Hydrogen;
        }

        private void SaveOutage()
        {
            if (Entity.Storage == null) Entity.Storage = new MyModStorageComponent();
            Entity.Storage[StorageKey] = string.Format(CultureInfo.InvariantCulture, "{0}|{1}|{2:R}|{3:R}|{4}",
                Entity.EntityId, outageFrames, reading.Recovered, reading.Vented, coolingStarted);
        }

        private void LoadOutage()
        {
            string saved;
            if (Entity.Storage == null || !Entity.Storage.TryGetValue(StorageKey, out saved)) return;
            string[] values = saved.Split('|');
            if (values.Length != 5 || values[0] != Entity.EntityId.ToString(CultureInfo.InvariantCulture)) return;
            int frames;
            double recovered, vented;
            bool cooling;
            if (!int.TryParse(values[1], out frames) || frames < 0 || frames >= HoldFrames + CoolingInterval
                || !double.TryParse(values[2], NumberStyles.Float, CultureInfo.InvariantCulture, out recovered)
                || !double.TryParse(values[3], NumberStyles.Float, CultureInfo.InvariantCulture, out vented)
                || !bool.TryParse(values[4], out cooling)) return;
            outageFrames = frames;
            reading.Recovered = recovered;
            reading.Vented = vented;
            coolingStarted = cooling;
        }

        internal void ShowReading(FieldReading snapshot)
        {
            reading = snapshot;
            haveReading = true;
            if (tank != null) RefreshTerminal();
        }

        private void RefreshTerminal()
        {
            tank.RefreshCustomInfo();
            tank.SetDetailedInfoDirty();
        }

        private void AppendInfo(IMyTerminalBlock block, StringBuilder info)
        {
            if (!haveReading) { info.AppendLine("Waiting for plasma field telemetry"); return; }
            info.Append("Plasma field: ").AppendLine(reading.State);
            if (reading.State == "Field power lost")
                info.Append("Hold remaining: ").Append(reading.HoldSeconds).AppendLine(" s");
            info.AppendFormat("Power delivered / requested: {0:0.###} / {1:0.###} kW\n",
                reading.Delivered * 1000, reading.Demand * 1000);
            info.AppendFormat("Last cooling: {0:N1} L hydrogen recovered, {1:N1} L vented",
                reading.Recovered, reading.Vented);
        }

        public override void Close()
        {
            if (tank != null) tank.AppendingCustomInfo -= AppendInfo;
            if (nativePower != null)
            {
                sink.SetRequiredInputFuncByType(Electricity, nativePower);
                sink.SetMaxRequiredInputByType(Electricity, nativeMax);
            }
        }
    }
}
