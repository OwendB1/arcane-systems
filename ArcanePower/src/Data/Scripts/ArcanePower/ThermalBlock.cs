using System;
using System.Text;
using Sandbox.Game.Entities;
using Sandbox.Game.EntityComponents;
using Sandbox.ModAPI;
using VRage.Game.Components;
using VRage.Game.Entity;
using VRage.ObjectBuilders;
using VRage.ModAPI;
using VRage.Utils;
using VRageMath;

namespace ArcanePower
{
    // Registered subclasses are generated alongside their model/socket contract.
    // These subtypes are deliberately separate from the existing production art.
    public abstract partial class ThermalBlock : MyGameLogicComponent
    {
        internal static readonly Guid StorageKey = new Guid("44c41f47-4bd2-431e-9a3e-817e171afde3");
        internal IMyFunctionalBlock Block;
        internal MyReactor Generator;
        internal ThermalModel Spec;
        internal ThermalStore Store;
        internal double OutputGrantMW, CoolingRejectedMW;
        internal double RotorLoad, RotorHotC = 45;
        internal ThermalOutputGrant OutputGrant;
        private int outputAccountedAt = -1;
        internal bool CoolingConnected, CoolingPowered = true;
        internal int CircuitRevision;
        private VRage.Game.ModAPI.IMyComponentStack circuitComponents;
        private bool receivedRotor;
        internal long SourceId { get { return Store.SourceId; } set { Store.SourceId = value; } }
        internal string Fault { get { return Store == null ? null : Store.Fault; } set { if (Store != null) Store.Fault = value; } }
        private bool preserveInvalidSave;
        private int environmentAt = -1000;
        private double coolingMW;
        private double clearExhaust;

        public override void Init(MyObjectBuilder_EntityBase builder)
        {
            Block = Entity as IMyFunctionalBlock;
            if (Block == null || !ThermalModels.All.TryGetValue(Block.BlockDefinition.SubtypeName, out Spec)) return;
            Store = new ThermalStore { EntityId = Entity.EntityId };
            Generator = Entity as MyReactor;
            if (Generator != null) SetOutput(0);
            NeedsUpdate = MyEntityUpdateEnum.BEFORE_NEXT_FRAME;
        }

        public override void UpdateOnceBeforeFrame()
        {
            if (Block == null || Spec == null || MyAPIGateway.Session == null) return;
            if (MyAPIGateway.Multiplayer.IsServer && Entity.Storage != null)
            {
                string xml;
                if (Entity.Storage.TryGetValue(StorageKey, out xml))
                    try
                    {
                        var saved = MyAPIGateway.Utilities.SerializeFromXML<ThermalStore>(xml);
                        if (saved != null && saved.Rotor != null) saved.Rotor.MigrateSavedRpm(Entity.EntityId);
                        if (saved != null && saved.Valid(Entity.EntityId, Spec.CapacityMJ)) Store = saved;
                        else if (saved != null && saved.EntityId == Entity.EntityId)
                        { preserveInvalidSave = true; Fault = "Invalid saved heat inventory; isolated"; }
                    }
                    catch (Exception error) { preserveInvalidSave = true; Fault = "Unreadable heat inventory; isolated"; MyLog.Default.WriteLine("ArcanePower: " + error.Message); }
            }
            if (Spec.Kind == ThermalKind.Train)
            {
                if (Store.Rotor == null) Store.Rotor = new ThermalRotorState { EntityId = Entity.EntityId };
                // Preserve shaft pose and inertia on reload, but never restore
                // a stale source's drive command before circuit validation.
                Store.Rotor.TargetRpm = Store.Rotor.CompressorTargetRpm = 0;
                receivedRotor = MyAPIGateway.Multiplayer.IsServer;
            }
            if (IsRadiator)
            {
                if (Store.Radiator == null) Store.Radiator = new ThermalRadiatorState { EntityId = Entity.EntityId };
                Store.Radiator.RejectedMW = 0;
                Store.Radiator.Target = Store.Radiator.Angle;
                radiatorVisualAngle = Store.Radiator.Angle;
                receivedRadiator = MyAPIGateway.Multiplayer.IsServer;
            }
            Block.AppendingCustomInfo += AppendInfo;
            WatchCircuitChanges();
            ThermalSession.Add(this);
        }

        private void WatchCircuitChanges()
        {
            circuitComponents = Block.SlimBlock.ComponentStack;
            circuitComponents.IsFunctionalChanged += CircuitStateChanged;
            Block.EnabledChanged += CircuitEnabledChanged;
        }

        private void UnwatchCircuitChanges()
        {
            if (circuitComponents == null) return;
            circuitComponents.IsFunctionalChanged -= CircuitStateChanged;
            circuitComponents = null;
            Block.EnabledChanged -= CircuitEnabledChanged;
        }

        private void CircuitEnabledChanged(IMyTerminalBlock block) { CircuitStateChanged(); }

        private void CircuitStateChanged()
        {
            // Invalidate the snapshot even if damage/repair finishes between
            // ticks. Recheck on the next server update, after output accounting.
            // IsWorkingChanged also fires for power loss; that is not a repair.
            unchecked { CircuitRevision++; }
            if (RadiatorBase != null) RadiatorBase.InvalidateRadiatorCooling();
        }

        internal void ReceiveRotor(ThermalRotorState state)
        {
            if (Spec.Kind != ThermalKind.Train || state == null || !state.Valid(Entity.EntityId)
                || (receivedRotor && state.Sequence <= Store.Rotor.Sequence)) return;
            if (receivedRotor)
            {
                state.Phase = ThermalRotors.CorrectPhase(Store.Rotor.Phase, state.Phase);
                state.CompressorPhase = ThermalRotors.CorrectPhase(Store.Rotor.CompressorPhase, state.CompressorPhase);
            }
            Store.Rotor = state;
            receivedRotor = true;
        }

        internal void AdvanceRotor()
        {
            if (Spec.Kind != ThermalKind.Train || Store.Rotor == null) return;
            var state = Store.Rotor;
            if (MyAPIGateway.Multiplayer.IsServer)
            {
                ThermalRotors.Drive(state, RotorLoad, RotorHotC, Healthy, 1.0 / 60);
                state.Sequence++;
            }
            else if (receivedRotor) ThermalRotors.Advance(state, 1.0 / 60);
            if (MyAPIGateway.Utilities.IsDedicated) return;
            for (int i = 0; i < ThermalModels.RotorNames.Length; i++)
            {
                MyEntitySubpart part;
                if (!((MyEntity)Entity).Subparts.TryGetValue(ThermalModels.RotorNames[i], out part)) continue;
                Matrix pose = ThermalRotors.Pose(i, i == 0 ? state.Phase : state.CompressorPhase);
                part.PositionComp.SetLocalMatrix(ref pose);
            }
        }

        internal bool Healthy
        {
            get { return Fault == null && HardwareReady; }
        }

        internal bool HardwareReady
        {
            get { return Block != null && !Block.Closed && Block.Enabled && Block.IsFunctional
                && Block.SlimBlock != null && Block.SlimBlock.BuildLevelRatio >= 1
                && Block.CubeGrid != null && Block.CubeGrid.Physics != null; }
        }

        internal void RecheckCircuitFault()
        {
            if (Fault == null || preserveInvalidSave || !HardwareReady || Store == null
                || !Store.Valid(Block.EntityId, Spec.CapacityMJ)) return;
            if (Generator != null && (Generator.CurrentOutput != 0
                || Generator.BlockDefinition.FuelInfos.Length != 0
                || !(Generator.BlockDefinition.MaxPowerOutput > 0))) return;
            // A repaired circuit may retry; never discard or replenish its heat.
            Fault = null;
        }

        internal ThermalEndpoint Endpoint(long owner)
        {
            Matrix rotation;
            Block.Orientation.GetMatrix(out rotation);
            Vector3 centre = ((MyEntity)Entity).PositionComp.LocalMatrixRef.Translation;
            var endpoint = ThermalEndpoint.At(Entity.EntityId, Block.CubeGrid.EntityId, Spec, rotation, centre,
                HardwareReady && owner != 0 && Block.HasPlayerAccess(owner));
            endpoint.Revision = CircuitRevision;
            return endpoint;
        }

        internal void SetOutput(double mw)
        {
            if (Generator == null || Block == null || Block.Closed || Block.MarkedForClose) return;
            // Definitions must use an empty FuelInfos list: only this runtime
            // may pay for and expose thermal generator output.
            if (Generator.BlockDefinition.FuelInfos.Length != 0)
            { Fault = "Thermal train requires an empty native FuelInfos list"; mw = 0; }
            float nativeRating = Generator.BlockDefinition.MaxPowerOutput;
            if (nativeRating <= 0) { Fault = "Invalid native train rating"; Generator.Capacity = 0; return; }
            float multiplier = (float)(Spec.RatingMW * ThermalMath.BraytonEfficiency / nativeRating);
            if (((IMyReactor)Generator).PowerOutputMultiplier != multiplier) ((IMyReactor)Generator).PowerOutputMultiplier = multiplier;
            Generator.Capacity = (float)(Math.Max(0, mw) / 216000.0);
        }

        internal void AccountOutput()
        {
            if (Generator == null) return;
            int now = MyAPIGateway.Session.GameplayFrameCounter;
            if (outputAccountedAt == now) return;
            outputAccountedAt = now;
            var grant = OutputGrant;
            OutputGrant = null;
            // Removal may already have torn down the native source. Conservatively
            // settle its last reservation at the grant ceiling; never read torn
            // resources or return possibly delivered energy as spendable credit.
            double output = Block.Closed || Block.MarkedForClose
                ? (grant == null ? 0 : grant.MaximumMW) : Generator.CurrentOutput;
            if ((grant != null && !grant.Settle(output))
                || (grant == null && output > .001))
            {
                // Stop generation at the source. An electrical accounting fault
                // does not make an intact cooling circuit physically unsealed.
                const string diagnostic = "Native output exceeded its paid energy reservation; generation stopped";
                if (grant != null) { grant.Source.Faulted = true; grant.Source.Diagnostic = diagnostic; }
                else Fault = diagnostic;
                SetOutput(0);
            }
        }

        internal ThermalUnit Unit()
        {
            UpdateEnvironment();
            return new ThermalUnit { Id = Entity.EntityId, Kind = Spec.Kind, Grade = Spec.Grade,
                RatingMW = Spec.RatingMW, CoolingMW = Healthy ? coolingMW : 0 };
        }

        private void UpdateEnvironment()
        {
            int now = MyAPIGateway.Session.GameplayFrameCounter;
            if ((Spec.Kind == ThermalKind.AirCooler || Spec.Kind == ThermalKind.Radiator) && now - environmentAt >= 60)
            {
                environmentAt = now;
                var planet = MyGamePruningStructure.GetClosestPlanet(Entity.GetPosition());
                double density = planet == null ? 0 : planet.GetAirDensity(Entity.GetPosition());
                airDensity = ThermalMath.Clamp(density, 0, 1);
                double rating = Spec.CoolingMW;
                if (Spec.Kind == ThermalKind.AirCooler)
                {
                    int clear = 0;
                    foreach (Vector3 sample in ThermalModels.AirCoolerExhaustSamples)
                    {
                        Vector3D mouth = Vector3D.Transform(sample, Block.WorldMatrix);
                        Vector3D outside = mouth + Block.WorldMatrix.Forward * 2.5;
                        // Same-grid occupancy also catches armor containing the
                        // ray origin: a physics ray alone can miss that case.
                        if (Block.CubeGrid.RayCastBlocks(mouth, outside).HasValue) continue;
                        VRage.Game.ModAPI.IHitInfo hit;
                        if (MyAPIGateway.Physics.CastRay(mouth, outside, out hit)
                            || MyAPIGateway.Physics.CastRay(outside, mouth, out hit)) continue;
                        clear++;
                    }
                    clearExhaust = clear / (double)ThermalModels.AirCoolerExhaustSamples.Length;
                    coolingMW = ThermalMath.AirCooling(rating, airDensity, clearExhaust);
                }
                else coolingMW = RadiatorCooling(airDensity);
            }
        }

        internal void Save()
        {
            if (Store == null || preserveInvalidSave || !Store.Valid(Entity.EntityId, Spec.CapacityMJ) || !MyAPIGateway.Multiplayer.IsServer) return;
            if (Entity.Storage == null) Entity.Storage = new MyModStorageComponent();
            Entity.Storage[StorageKey] = MyAPIGateway.Utilities.SerializeToXML(Store);
        }

        private void AppendInfo(IMyTerminalBlock block, StringBuilder info)
        {
            if (IsCooling) { AppendCoolingInfo(info); return; }
            info.Append("\nArcane thermal runtime prototype\n");
            info.AppendLine("Construction: " + ThermalConstruction.Role(Spec));
            info.AppendLine("Aim at a thermal block, or select one for placement, to inspect sockets and construction checks.");
            if (Fault != null) info.AppendLine(Fault);
            if (MyAPIGateway.Multiplayer.IsServer)
                info.Append("Stored heat: ").Append((Store.HotMJ + Store.WasteMJ).ToString("N1")).AppendLine(" MJ");
            else info.AppendLine("Heat inventories are server-owned. Use the thermal reactor dashboard for plant diagnostics.");
            if (Spec.CoolingMW > 0)
                info.Append("Rated cooling per unit/panel: ").Append(CoolingPower(Spec.CoolingMW)).AppendLine(" (ideal exposure)");
            if (Spec.Kind == ThermalKind.Train)
                info.AppendLine(Spec.Grade >= 3 ? "Fuel heat: Aether, Helion or Empyrean" : "Fuel heat: Aether or Helion; Empyrean requires upgraded turbines");
            if (Spec.Kind == ThermalKind.Train && (MyAPIGateway.Multiplayer.IsServer || receivedRotor))
            {
                var rotor = Store.Rotor;
                info.Append("Turbine/generator shaft: ").Append(rotor.Rpm.ToString("0")).Append(" rpm / built-in compressor: ")
                    .Append(rotor.CompressorRpm.ToString("0")).AppendLine(" rpm");
                info.Append("Working temperature: ").Append(rotor.HotC.ToString("0")).AppendLine(" C (gameplay model)");
            }
        }

        public override void Close()
        {
            if (Block == null || Spec == null) return;
            UnwatchCircuitChanges();
            ThermalSession.Remove(this); Save();
            Block.AppendingCustomInfo -= AppendInfo;
        }
    }
}
