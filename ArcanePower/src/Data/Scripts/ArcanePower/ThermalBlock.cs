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
    public abstract class ThermalBlock : MyGameLogicComponent
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
                // A reload requires a newly paid start. Preserve shaft pose and
                // inertia, but never restore a stale source's drive command.
                Store.Rotor.TargetRpm = Store.Rotor.CompressorTargetRpm = 0;
                receivedRotor = MyAPIGateway.Multiplayer.IsServer;
            }
            if (Spec.Kind == ThermalKind.Heater)
            {
                startupSink = new MyResourceSinkComponent();
                startupSink.Init(MyStringHash.GetOrCompute("ArcaneContainment"), new MyResourceSinkInfo {
                    ResourceTypeId = MyResourceDistributorComponent.ElectricityId, MaxRequiredInput = 50000,
                    RequiredInputFunc = RequiredStartup });
                Block.ResourceSink = startupSink;
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
            int now = MyAPIGateway.Session.GameplayFrameCounter;
            if ((Spec.Kind == ThermalKind.AirCooler || Spec.Kind == ThermalKind.Radiator) && now - environmentAt >= 60)
            {
                environmentAt = now;
                var planet = MyGamePruningStructure.GetClosestPlanet(Entity.GetPosition());
                double density = planet == null ? 0 : planet.GetAirDensity(Entity.GetPosition());
                double rating = Spec.RatingMW * .6;
                if (Spec.Kind == ThermalKind.AirCooler) coolingMW = ThermalMath.AirCooling(rating, density);
                else
                {
                    int visible = 0;
                    Vector3D right = Block.WorldMatrix.Right, up = Block.WorldMatrix.Up;
                    foreach (int sign in new[] { -1, 1 })
                        foreach (int x in new[] { -1, 1 })
                            foreach (int y in new[] { -1, 1 })
                            {
                                Vector3D normal = Block.WorldMatrix.Forward * sign;
                                Vector3D from = Entity.GetPosition() + normal * (Spec.Cells.Z * 1.25 + .05)
                                    + right * (x * Spec.Cells.X * .6) + up * (y * Spec.Cells.Y * .6);
                                VRage.Game.ModAPI.IHitInfo hit;
                                if (!MyAPIGateway.Physics.CastRay(from, from + normal * 250, out hit)) visible++;
                            }
                    coolingMW = ThermalMath.RadiativeCooling(rating, visible / 8.0, density > .001 ? 25 : -270.15);
                }
            }
            return new ThermalUnit { Id = Entity.EntityId, Kind = Spec.Kind, Grade = Spec.Grade,
                RatingMW = Spec.RatingMW, CoolingMW = Healthy ? coolingMW : 0, ColdC = 45 };
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
            if (Spec.Kind == ThermalKind.Train && (MyAPIGateway.Multiplayer.IsServer || receivedRotor))
            {
                var rotor = Store.Rotor;
                info.Append("Visual turbine: ").Append(rotor.Rpm.ToString("0")).Append(" rpm / compressor: ")
                    .Append(rotor.CompressorRpm.ToString("0")).AppendLine(" rpm");
                info.Append("Operating estimate: ").Append(rotor.PressureMPa.ToString("0.0"))
                    .Append(" / 8.0 MPa, ").Append(rotor.HotC.ToString("0")).AppendLine(" C (gameplay model)");
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
