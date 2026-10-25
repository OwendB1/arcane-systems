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
        internal double Efficiency;
        internal double OutputGrantMW;
        internal double RotorCirculation, RotorHotC = 45;
        private bool receivedRotor;
        internal long SourceId { get { return Store.SourceId; } set { Store.SourceId = value; } }
        internal double StartupInputMW { get { return startupInput; } }
        internal long StartupOwner { get { return startupOwner; } }
        internal string Fault { get { return Store == null ? null : Store.Fault; } set { if (Store != null) Store.Fault = value; } }
        private bool preserveInvalidSave;
        private MyResourceSinkComponent startupSink;
        private long startupOwner;
        private int requestedAt = -100;
        private float startupDemand;
        private double startupInput;
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
            if (Spec.Kind == ThermalKind.Train)
            {
                startupSink = new MyResourceSinkComponent();
                startupSink.Init(MyStringHash.GetOrCompute("ArcaneContainment"), new MyResourceSinkInfo {
                    ResourceTypeId = MyResourceDistributorComponent.ElectricityId, MaxRequiredInput = 50000,
                    RequiredInputFunc = RequiredStartup });
                Block.ResourceSink = startupSink;
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
            ThermalSession.Add(this);
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
                ThermalRotors.Drive(state, Store.HotMJ, Spec.RatingMW, RotorHotC,
                    RotorCirculation, Healthy, 1.0 / 60);
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

        private float RequiredStartup()
        {
            return startupSink == null || !Healthy || MyAPIGateway.Session.GameplayFrameCounter - requestedAt > 1 ? 0 : startupDemand;
        }

        internal bool Healthy
        {
            get { return Fault == null && Block != null && !Block.Closed && Block.Enabled && Block.IsFunctional
                && Block.SlimBlock.BuildLevelRatio >= 1 && Block.CubeGrid.Physics != null; }
        }

        internal ThermalEndpoint Endpoint(long owner)
        {
            Matrix rotation;
            Block.Orientation.GetMatrix(out rotation);
            Vector3 centre = ((MyEntity)Entity).PositionComp.LocalMatrixRef.Translation;
            return ThermalEndpoint.At(Entity.EntityId, Block.CubeGrid.EntityId, Spec, rotation, centre,
                Healthy && owner != 0 && Block.HasPlayerAccess(owner));
        }

        internal double RequestStartup(long owner, double demand)
        {
            if (startupSink == null) return 0;
            int now = MyAPIGateway.Session.GameplayFrameCounter;
            double input = startupOwner == owner && now - requestedAt == 1 ? startupInput : 0;
            startupOwner = owner; requestedAt = now;
            startupDemand = (float)ThermalMath.Clamp(demand, 0,
                Math.Min(50000, Math.Max(0, Spec.CapacityMJ - Store.HotMJ - Store.WasteMJ) * 60));
            startupSink.Update();
            return input;
        }

        internal void AccountStartup()
        {
            startupInput = startupSink == null ? 0 : Math.Max(0, Math.Min(startupDemand,
                startupSink.CurrentInputByType(MyResourceDistributorComponent.ElectricityId)));
            if (startupInput > 0) Store.WasteMJ += startupInput / 60;
        }

        internal void StopStartup()
        {
            if (startupSink == null) return;
            startupDemand = 0; startupOwner = 0; startupSink.Update();
        }

        internal void SetOutput(double mw)
        {
            if (Generator == null) return;
            // Definitions must use an empty FuelInfos list: only this runtime
            // may pay for and expose thermal generator output.
            if (Generator.BlockDefinition.FuelInfos.Length != 0)
            { Fault = "Thermal train requires an empty native FuelInfos list"; mw = 0; }
            float nativeRating = Generator.BlockDefinition.MaxPowerOutput;
            if (nativeRating <= 0) { Fault = "Invalid native train rating"; Generator.Capacity = 0; return; }
            float multiplier = (float)(Spec.RatingMW * .78 / nativeRating);
            if (((IMyReactor)Generator).PowerOutputMultiplier != multiplier) ((IMyReactor)Generator).PowerOutputMultiplier = multiplier;
            Generator.Capacity = (float)(Math.Max(0, mw) / 216000.0);
        }

        internal void AccountOutput()
        {
            if (Generator == null || Generator.CurrentOutput <= 0) return;
            if (!ThermalMath.Convert(Store, Generator.CurrentOutput / 60.0, Efficiency))
            { Fault = "Native output exceeded its paid heat allocation; isolated"; SetOutput(0); }
        }

        internal ThermalUnit Unit()
        {
            UpdateEnvironment();
            return new ThermalUnit { Id = Entity.EntityId, Kind = Spec.Kind, Grade = Spec.Grade,
                RatingMW = EffectiveRatingMW, CoolingMW = Healthy ? coolingMW : 0, ColdC = 45 };
        }

        private void UpdateEnvironment()
        {
            int now = MyAPIGateway.Session.GameplayFrameCounter;
            if ((Spec.Kind == ThermalKind.AirCooler || Spec.Kind == ThermalKind.Radiator) && now - environmentAt >= 60)
            {
                environmentAt = now;
                var planet = MyGamePruningStructure.GetClosestPlanet(Entity.GetPosition());
                double density = planet == null ? 0 : planet.GetAirDensity(Entity.GetPosition());
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
                    coolingMW = ThermalMath.AirCooling(rating, density, clearExhaust);
                }
                else coolingMW = RadiatorCooling(density);
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
            info.Append("\nArcane thermal runtime prototype\n");
            info.AppendLine("Construction: " + ThermalConstruction.Role(Spec));
            info.AppendLine("Aim at a thermal block, or select one for placement, to inspect sockets and construction checks.");
            if (Fault != null) info.AppendLine(Fault);
            if (MyAPIGateway.Multiplayer.IsServer)
                info.Append("Stored heat: ").Append((Store.HotMJ + Store.WasteMJ).ToString("N1")).AppendLine(" MJ");
            else info.AppendLine("Heat inventories are server-owned. Use the thermal reactor dashboard for plant diagnostics.");
            if (Spec.CoolingMW > 0)
                info.Append("Rated cooling per unit/panel: ").Append((Spec.CoolingMW / 1000).ToString("N0")).AppendLine(" GW (ideal exposure)");
            if (Spec.Kind == ThermalKind.Train)
                info.AppendLine(Spec.Grade >= 3 ? "Fuel heat: Aether, Helion or Empyrean" : "Fuel heat: Aether or Helion; Empyrean requires upgraded turbines");
            if (Spec.Kind == ThermalKind.AirCooler)
            {
                // Clients may inspect local clearance; server Unit() remains
                // the sole authority for actual heat rejection and dispatch.
                UpdateEnvironment();
                info.Append("Exhaust clearance: ").Append((clearExhaust * 100).ToString("0")).AppendLine("%");
                info.Append("Available cooling: ").Append((Healthy ? coolingMW : 0).ToString("N1")).AppendLine(" MW");
                if (clearExhaust < .999) info.AppendLine("Exhaust obstructed: clear 2.5 m in front of both fan guards.");
            }
            if (IsRadiator && Store.Radiator != null && (MyAPIGateway.Multiplayer.IsServer || receivedRadiator))
            {
                var radiator = Store.Radiator;
                info.AppendLine(Spec.Kind == ThermalKind.RadiatorPanel
                    ? (radiator.ParentId != 0 ? "Attached to radiator axis" : "Inactive: stack above an aligned radiator (maximum two extensions)")
                    : (Healthy ? "Automatic sun tracking: edge-on / " + radiator.Panels + " panel(s)" : "Sun tracking paused"));
                info.Append("Panel angle: ").Append((radiator.Angle * 180 / Math.PI).ToString("0.0")).AppendLine(" degrees");
                info.Append("Clear sky: ").Append((radiator.Exposure * 100).ToString("0")).Append("% / solar exposure: ")
                    .Append((radiator.SunIncidence * 100).ToString("0")).AppendLine("%");
                info.Append("Cooling after solar load: ").Append((ThermalRadiators.SolarEfficiency(radiator.SunIncidence) * 100).ToString("0")).AppendLine("% (before clearance/sink limits)");
                info.Append("Heat dissipated: ").Append(radiator.RejectedMW.ToString("N1")).AppendLine(" MW");
            }
            if (Spec.Kind == ThermalKind.Train && (MyAPIGateway.Multiplayer.IsServer || receivedRotor))
            {
                var rotor = Store.Rotor;
                info.Append("Visual turbine: ").Append(rotor.Rpm.ToString("0")).Append(" rpm / compressor: ")
                    .Append(rotor.CompressorRpm.ToString("0")).AppendLine(" rpm");
                info.Append("Working temperature: ").Append(rotor.HotC.ToString("0")).AppendLine(" C (gameplay model)");
            }
        }

        public override void Close()
        {
            if (Block == null || Spec == null) return;
            StopStartup(); Save(); ThermalSession.Remove(this);
            Block.AppendingCustomInfo -= AppendInfo;
        }
    }
}
