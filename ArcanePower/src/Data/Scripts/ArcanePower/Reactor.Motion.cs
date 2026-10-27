using System;
using System.Collections.Generic;
using System.Text;
using ProtoBuf;
using Sandbox.Game.EntityComponents;
using Sandbox.ModAPI;
using VRage.Game.Components;
using VRage.Game.Entity;
using VRage.Game.ModAPI;
using VRage.ModAPI;
using VRageMath;

namespace ArcanePower
{
    public enum CorePhase { Off, Starting, Running, Stopping, Cooling }
    public enum VentPhase { Idle, ShieldClosing, IntakeOpening, Open, IntakeClosing, ShieldOpening, Ejecting }
    public enum ReactorStatus { ShutOff, Incomplete, OutOfFuel, Active }

    [ProtoContract]
    public sealed class MotionState
    {
        [ProtoMember(1)] public long EntityId;
        [ProtoMember(2)] public CorePhase Core;
        [ProtoMember(3)] public VentPhase Vent;
        [ProtoMember(4)] public int CoreTick;
        [ProtoMember(5)] public int StopTick;
        [ProtoMember(6)] public int StopSpinAge;
        [ProtoMember(7)] public float Shield;
        [ProtoMember(8)] public float Intake;
        [ProtoMember(9)] public bool Requested;
        [ProtoMember(10)] public bool Paused;
        [ProtoMember(11)] public long Sequence;
        [ProtoMember(12)] public int FuelTier = 1;
        [ProtoMember(13)] public float Load;
        [ProtoMember(14)] public float TargetLoad;
        [ProtoMember(15)] public double SpinPhase = -1;
        [ProtoMember(16)] public float SpinRate = 3;
        [ProtoMember(17)] public ReactorStatus Status;
        [ProtoMember(18)] public float CoreSubtick;
        [ProtoMember(19)] public int EjectTick;
        [ProtoMember(20)] public float Heat;
        [ProtoMember(21)] public float VentLoad;
        [ProtoMember(22)] public float VentHeat;
        [ProtoMember(23)] public bool VentHadPayload;
        [ProtoMember(24)] public bool VentDamageApplied;
        [ProtoMember(25)] public double FuelDebt;
        [ProtoMember(26)] public double SecondaryPhase;
        [ProtoMember(27)] public float SecondaryRate;
        [ProtoMember(28)] public float PowerRamp;
        [ProtoMember(29)] public int InstalledTiles;
        [ProtoMember(30)] public float TileWear;
        [ProtoMember(31)] public bool TileStarved;
        [ProtoMember(32)] public long VentOutletId;
        [ProtoMember(33)] public float EjectionTravel = 18;
        [ProtoMember(34)] public double ReserveMJ;
        [ProtoMember(35)] public float PowerDemandMW;
        [ProtoMember(36)] public float PowerInputMW;
        [ProtoMember(37)] public bool PowerReady;
        [ProtoMember(38)] public bool PowerPaused;
        [ProtoMember(39)] public bool PowerStarved;
        [ProtoMember(40)] public int MaintenanceBatch;
        [ProtoMember(41)] public float MaintenanceTick = -1;
        [ProtoMember(42)] public float StarvedLoad;
        [ProtoMember(43)] public bool Critical;
        [ProtoMember(44)] public float CriticalSeconds;
        [ProtoMember(45)] public bool PayloadReleased;
        [ProtoMember(46)] public bool? Enabled;
        [ProtoMember(47)] public bool VentReady;
        [ProtoMember(48)] public int VentDucts;
        [ProtoMember(49, OverwriteList = true)] public int[] TileGrades = new int[20];
        [ProtoMember(50)] public int RingCount = 2;
        [ProtoMember(51), System.ComponentModel.DefaultValue(true)] public bool SecurityMode = true;
        [ProtoMember(52)] public bool ControllersReady;
        [ProtoMember(53)] public ThermalReactorState Thermal;
        // Millionths of one recovered component, earned only by paid T1 burn.
        [ProtoMember(54)] public long ResiduumMicroUnits;
        [ProtoMember(55)] public float ForecastPeakHeat;
        [ProtoMember(56)] public bool ForecastWarning;
        [ProtoMember(57)] public float ForecastOverheatSeconds = -1;
        [ProtoMember(58)] public float ForecastMeltdownSeconds = -1;
        [ProtoMember(59)] public int ForecastCircuit;

        // Timing is decided on the server; clients display the same confirmed
        // warning throughout its recovery hold instead of toggling independently.
        internal bool ThermalWarning
        {
            get { return !PayloadReleased && Core != CorePhase.Off && !Critical
                && ForecastWarning; }
        }
        internal bool ForecastRising { get { return ForecastPeakHeat > Math.Max(1, Heat) + .001f; } }

        // XML-only compatibility with saves made before fuel and hardware tiers
        // were separated. Never write the obsolete field into new saves/packets.
        [System.Xml.Serialization.XmlElement("Profile")]
        public int? LegacyProfile;
        public bool ShouldSerializeLegacyProfile() { return false; }
    }

    public sealed partial class Reactor
    {
        private const float CooldownHeat = .15f;
        private const int PlasmaStartTick = 1038; // Last quartet has latched.
        internal static readonly Guid MotionStorage = new Guid("d85a5399-b527-45ac-bcc0-aa1c442b2710");
        internal MotionState Motion = new MotionState();
        private readonly Dictionary<string, Matrix> restPoses = new Dictionary<string, Matrix>();
        private IMyModel restModel;
        private int networkTick;
        private bool receivedState;
        private bool restoreLegacyHardware;
        internal long Id { get { return Entity.EntityId; } }
        internal IMyReactor Block { get { return reactor; } }

        private void InitializeMotion()
        {
            Motion.EntityId = Id;
            RefreshRestPoses();
            if (MyAPIGateway.Multiplayer.IsServer && Entity.Storage != null)
            {
                string saved;
                if (Entity.Storage.TryGetValue(MotionStorage, out saved))
                {
                    try
                    {
                        var state = MyAPIGateway.Utilities.SerializeFromXML<MotionState>(saved);
                        RestoreMotionState(state);
                    }
                    catch (Exception error)
                    {
                        VRage.Utils.MyLog.Default.WriteLineAndConsole("ArcanePower: cannot restore reactor " + Id + ": " + error.Message);
                    }
                }
            }
            Motion.EntityId = Id;
            if (Motion.SpinPhase < 0)
            {
                // Preserve old saved orientations before adopting load-driven speed.
                int spinAge = Motion.Core == CorePhase.Stopping ? Motion.StopSpinAge : Motion.CoreTick;
                Motion.SpinPhase = Math.Max(0, spinAge - 1170) % 36000;
                if (Motion.Core == CorePhase.Stopping) Motion.SpinRate = 1;
            }
            // Keep the saved appearance until native connections have initialized.
            receivedState = MyAPIGateway.Multiplayer.IsServer;
            motionInitialized = true;
            SaveMotion();
            VentSession.Add(this);
        }

        private void RefreshRestPoses()
        {
            // Welding/grinding replaces the native model. Construction stages
            // have no moving subparts; acquire the completed model's rest poses
            // without resetting saved motion, fuel or installed containment.
            var model = reactor.Model;
            if (model == restModel) return;
            restModel = model;
            restPoses.Clear();
            if (model == null) return;
            var dummies = new Dictionary<string, IMyModelDummy>();
            model.GetDummies(dummies);
            foreach (var pair in dummies)
                if (pair.Key.StartsWith("subpart_")) restPoses[pair.Key.Substring(8)] = pair.Value.Matrix;
        }

        private void RestoreMotionState(MotionState state)
        {
            if (state == null) return;
            if (state.LegacyProfile.HasValue)
            {
                state.FuelTier = state.LegacyProfile.Value;
                state.RingCount = state.FuelTier + 1;
            }
            // A pasted/projected copy must not inherit installed consumables.
            if (state.EntityId != Id) return;
            if (!Valid(state))
            {
                if (ThermalVariant && state.Thermal != null)
                { thermalRestoreFault = true; reactor.Enabled = false; }
                VRage.Utils.MyLog.Default.WriteLineAndConsole("ArcanePower: cannot restore reactor " + Id
                    + ": invalid saved motion state (fuel remainder=" + state.FuelDebt + ")");
                return;
            }
            Motion = state;
            restoreLegacyHardware = state.LegacyProfile.HasValue;
            if (state.Enabled.HasValue) reactor.Enabled = state.Enabled.Value;
        }

        internal static bool Valid(MotionState state)
        {
            // Native withdrawals round to the nearest millionth, leaving up to
            // half a quantum of credit. Keep it, with tolerance for double arithmetic.
            return state != null && state.Core >= CorePhase.Off && state.Core <= CorePhase.Cooling
                && state.Vent >= VentPhase.Idle && state.Vent <= VentPhase.Ejecting
                && state.CoreTick >= 0 && state.CoreTick <= 2000000000 && state.StopTick >= 0 && state.StopTick <= 1260
                && state.StopSpinAge >= 0 && state.StopSpinAge <= 2000000000
                && state.Shield >= 0 && state.Shield <= 1 && state.Intake >= 0 && state.Intake <= 1
                && state.FuelTier >= 1 && state.FuelTier <= 3
                && state.RingCount >= 2 && state.RingCount <= 4
                && state.Load >= 0 && state.Load <= 1 && state.TargetLoad >= 0 && state.TargetLoad <= 1
                && state.SpinPhase >= -1 && state.SpinPhase < 36000 && state.SpinRate >= 0 && state.SpinRate <= 9
                && state.SecondaryPhase >= 0 && state.SecondaryPhase < 36000
                && state.SecondaryRate >= 0 && state.SecondaryRate <= 9
                && state.InstalledTiles >= 0 && state.InstalledTiles <= 80 && state.InstalledTiles % 4 == 0
                && ValidTileGrades(state.TileGrades)
                && state.TileWear >= 0 && state.TileWear <= 1 && state.VentOutletId >= 0
                && state.ReserveMJ >= 0 && state.ReserveMJ <= 9000
                && state.PowerDemandMW >= 0 && state.PowerDemandMW <= 400
                && state.PowerInputMW >= 0 && state.PowerInputMW <= 400.01f
                && state.MaintenanceBatch >= 0 && state.MaintenanceBatch < 20
                && state.MaintenanceTick >= -1 && state.MaintenanceTick <= 90
                && state.VentDucts >= 0 && state.VentDucts <= 15
                && state.EjectionTravel >= 18 && state.EjectionTravel <= 70
                && state.PowerRamp >= 0 && state.PowerRamp <= 1
                && state.CoreSubtick >= 0 && state.CoreSubtick < 1
                && state.EjectTick >= 0 && state.EjectTick <= 120
                && state.StarvedLoad >= 0 && state.StarvedLoad <= 1
                && state.CriticalSeconds >= 0 && state.CriticalSeconds <= 60
                && state.ForecastPeakHeat >= 0 && state.ForecastPeakHeat <= 4
                && state.ForecastOverheatSeconds >= -1 && state.ForecastOverheatSeconds <= 60
                && state.ForecastMeltdownSeconds >= -1 && state.ForecastMeltdownSeconds <= 60
                && state.ForecastCircuit >= 0 && state.ForecastCircuit <= 4
                && state.Heat >= 0 && state.Heat <= 4 && state.VentLoad >= 0 && state.VentLoad <= 1
                && state.VentHeat >= 0 && state.VentHeat <= 4
                && state.FuelDebt >= -(double)VRage.MyFixedPoint.SmallestPossibleValue * .5 - 1e-12 && state.FuelDebt < 1
                && state.ResiduumMicroUnits >= 0 && state.ResiduumMicroUnits <= 1000000000000000L
                && state.Status >= ReactorStatus.ShutOff && state.Status <= ReactorStatus.Active
                // Retain the old per-tier saved-heat bounds across the 10:1 rebalance.
                && (state.Thermal == null || (state.Thermal.Valid(state.EntityId)
                    && state.Thermal.Store.Valid(state.EntityId, PowerMW[state.FuelTier - 1] * 10 / .40 * 8)
                    && state.Thermal.FuelHeatMJ <= PowerMW[state.FuelTier - 1] * 10 / .40 * 8));
        }

        internal void ReceiveState(MotionState state)
        {
            if (!Valid(state) || (receivedState && state.Sequence <= Motion.Sequence)) return;
            Motion = state;
            receivedState = true;
            appearanceRefresh = 0;
            reactor.RefreshCustomInfo();
        }

        internal void RequestVent(bool open)
        {
            // Ejection is a finite committed cycle: another toolbar click must
            // not reverse a hatch onto a core which is still passing through it.
            if (!MyAPIGateway.Multiplayer.IsServer || !open || Motion.Vent != VentPhase.Idle) return;
            if (!HasIntactControllers()) return;
            if (!restPoses.ContainsKey("VentHatch4")) return;
            RefreshVentRoute();
            if (!Motion.VentReady) { PublishMotion(); return; }
            Motion.PayloadReleased = false;
            Motion.Requested = true;
            Motion.EjectTick = 0;
            Motion.VentHadPayload = false;
            Motion.VentDamageApplied = false;
            Motion.VentLoad = Math.Max(Motion.Load, Motion.TargetLoad);
            Motion.VentHeat = Motion.Heat;
            Motion.Vent = VentPhase.ShieldClosing;
            PublishMotion();
        }

        private void BeginShutdown()
        {
            if (Motion.Core == CorePhase.Off || Motion.Core == CorePhase.Stopping || Motion.Core == CorePhase.Cooling) return;
            if (Motion.Core == CorePhase.Running && (Motion.Heat > CooldownHeat || Motion.MaintenanceTick >= 0))
            {
                Motion.Core = CorePhase.Cooling;
                return;
            }
            BeginDismantling();
        }

        private void BeginDismantling()
        {
            Motion.StopSpinAge = Motion.CoreTick;
            Motion.StopTick = Motion.Core == CorePhase.Running || Motion.Core == CorePhase.Cooling ? 0 : 90;
            Motion.CoreTick = Math.Min(1170, Motion.CoreTick);
            Motion.Core = CorePhase.Stopping;
            appearanceRefresh = 0;
        }

        private void UpdateMotion()
        {
            bool server = MyAPIGateway.Multiplayer.IsServer;
            var oldCore = Motion.Core;
            var oldVent = Motion.Vent;
            var oldStatus = Motion.Status;
            if (server)
            {
                // A broken route freezes the committed launch, never its heat/fuse.
                bool ejecting = Motion.Vent != VentPhase.Idle && !Motion.PayloadReleased;
                Motion.Paused = Motion.PowerPaused || (Motion.Vent == VentPhase.Idle && !reactor.IsFunctional)
                    || (ejecting && (!Motion.ControllersReady || !Motion.VentReady));
                if (Motion.Core == CorePhase.Off && Motion.Vent == VentPhase.Idle && reactor.Enabled && !thermalStartRequested && Motion.VentReady && HasUsableFuel() && Motion.PowerReady && !PrepareTiles())
                    reactor.Enabled = false;
                UpdateStatus();
                Motion.TargetLoad = reactor.MaxOutput > 0
                    ? MathHelper.Clamp(reactor.CurrentOutput / reactor.MaxOutput, 0, 1) : 0;
                if (ThermalVariant && Motion.Thermal != null)
                    Motion.TargetLoad = (float)ThermalMath.Clamp(Motion.Thermal.ProducedMW / ThermalHeatMW, 0, 1);
                if (Motion.TileStarved && !Motion.PayloadReleased) Motion.TargetLoad = Motion.StarvedLoad;
                bool ventPowerCut = Motion.Vent != VentPhase.Idle && Motion.Vent != VentPhase.ShieldClosing;
                if (ventPowerCut || ((Motion.Core == CorePhase.Stopping || Motion.Core == CorePhase.Cooling) && Motion.Vent == VentPhase.Idle))
                    reactor.Enabled = false;
                if ((!reactor.Enabled || !reactor.IsFunctional || !CanOperate || !HasUsableFuel()) && Motion.Vent == VentPhase.Idle) BeginShutdown();
                else if (Motion.Core == CorePhase.Off && Motion.Vent == VentPhase.Idle && Motion.VentReady && Motion.PowerReady && !thermalStartRequested)
                {
                    Motion.PayloadReleased = false;
                    Motion.RingCount = controllerRingCapacity;
                    Motion.Core = CorePhase.Starting;
                    Motion.CoreTick = 0;
                    Motion.CoreSubtick = 0;
                    Motion.SpinPhase = 0;
                    Motion.SecondaryPhase = 0;
                    Motion.SecondaryRate = 0;
                    Motion.PowerRamp = 0;
                }
            }
            if (receivedState)
            {
                UpdateThermal();
                if (!Motion.Paused) AdvanceMotion();
            }
            if (server)
            {
                if (Motion.Vent != VentPhase.Idle && Motion.Vent != VentPhase.ShieldClosing)
                    reactor.Enabled = false;
                if (oldVent != VentPhase.Idle && Motion.Vent == VentPhase.Idle)
                {
                    reactor.Enabled = false;
                    ApplyVentDamage();
                }
                TryReleasePayload();
                UpdateCriticalCore();
                RefreshFuelCapacity();
                UpdateStatus();
            }
            if (!MyAPIGateway.Utilities.IsDedicated)
            {
                DrawMotion();
                DrawVentOutlet();
            }
            networkTick++;
            if (server && (oldCore != Motion.Core || oldVent != Motion.Vent || oldStatus != Motion.Status || networkTick % 30 == 0)) PublishMotion();
            else if (!server && !receivedState && networkTick % 120 == 0) VentSession.SendCommand(Id, VentCommand.Sync);
        }

        private void AdvanceMotion()
        {
            // One-second response filters abrupt power demand changes. The server
            // supplies the target and accumulated phase for late joins/reloads.
            Motion.Load += (Motion.TargetLoad - Motion.Load) / 60f;
            bool coreCanAdvance = Motion.Vent == VentPhase.Idle || Motion.Vent == VentPhase.ShieldClosing;
            if (coreCanAdvance && Motion.MaintenanceTick >= 0)
            {
                Motion.MaintenanceTick += Motion.RingCount * .5f;
                if (Motion.MaintenanceTick >= 90)
                {
                    Motion.MaintenanceTick = -1;
                    Motion.MaintenanceBatch = (Motion.MaintenanceBatch + 1) % 20;
                }
            }
            bool generating = Motion.Core == CorePhase.Running && coreCanAdvance && reactor.Enabled;
            Motion.PowerRamp = generating ? Math.Min(1, Motion.PowerRamp + 1f / 600) : Math.Max(0, Motion.PowerRamp - 1f / 600);
            if (Motion.Vent == VentPhase.ShieldClosing)
            {
                Motion.VentLoad = Math.Max(Motion.VentLoad, Motion.TargetLoad);
                Motion.VentHeat = Math.Max(Motion.VentHeat, Motion.Heat);
            }
            if (coreCanAdvance && (Motion.Core == CorePhase.Starting || Motion.Core == CorePhase.Running))
            {
                // Keep long-running spin arithmetic bounded without altering any pose.
                if (Motion.CoreTick >= 100001170) Motion.CoreTick -= 3600000;
                if (Motion.Core == CorePhase.Starting && Motion.CoreTick >= 320 && Motion.CoreTick < 1038)
                {
                    // Only accelerate sphere construction: quartet spacing and
                    // flight share the same authored clock. Keep fractional
                    // poses so Tier 2's 1.5x rate does not alternate visible speeds.
                    float age = Math.Min(1038, Motion.CoreTick + Motion.CoreSubtick + Motion.RingCount * .5f);
                    Motion.CoreTick = (int)age;
                    Motion.CoreSubtick = age - Motion.CoreTick;
                }
                else Motion.CoreTick++;
                if (Motion.CoreTick >= 1170) Motion.Core = CorePhase.Running;
                Motion.SpinRate = 3f * (1 + 2 * Motion.Load);
                if (Motion.CoreTick > 1170) AdvanceSpin();
            }
            else if (coreCanAdvance && Motion.Core == CorePhase.Cooling)
            {
                Motion.CoreTick++;
                Motion.SpinRate += (3f * (.1f + .9f * Math.Min(1, Motion.Heat)) - Motion.SpinRate) / 60f;
                AdvanceSpin();
                if (Motion.Heat <= CooldownHeat && Motion.MaintenanceTick < 0) BeginDismantling();
            }
            else if (coreCanAdvance && Motion.Core == CorePhase.Stopping)
            {
                if (Motion.StopTick < 90) Motion.StopTick++;
                else if (Motion.CoreTick > 0)
                {
                    Motion.CoreTick--;
                    if (Motion.CoreTick == 0) Motion.CoreSubtick = 0;
                }
                else Motion.Core = CorePhase.Off;
            }
            else if ((Motion.Core == CorePhase.Running || Motion.Core == CorePhase.Cooling) && Motion.EjectTick < 120)
                AdvanceSpin();
            switch (Motion.Vent)
            {
                case VentPhase.ShieldClosing:
                    Motion.Shield = Math.Min(1, Motion.Shield + 1f / 240);
                    if (Motion.Shield >= 1)
                    {
                        Motion.VentHadPayload = Motion.Core != CorePhase.Off && Motion.CoreTick >= 90;
                        Motion.Vent = VentPhase.IntakeOpening;
                    }
                    break;
                case VentPhase.IntakeOpening:
                    Motion.Intake = Math.Min(1, Motion.Intake + 1f / 90);
                    if (Motion.Intake >= 1) Motion.Vent = VentPhase.Ejecting;
                    break;
                case VentPhase.Open: // Legacy saves which held the intake open.
                    Motion.VentHadPayload = Motion.Core != CorePhase.Off && Motion.CoreTick >= 90;
                    Motion.Vent = VentPhase.Ejecting;
                    break;
                case VentPhase.Ejecting:
                    Motion.EjectTick++;
                    // Keep the hot core and its fuse intact until the physical handoff.
                    if (Motion.PayloadReleased) Motion.Heat = Math.Max(0, Motion.Heat - .04f);
                    if (Motion.EjectTick >= 120 && Motion.VentHadPayload && !Motion.PayloadReleased)
                        Motion.EjectTick = 119;
                    if (Motion.EjectTick >= 120)
                    {
                        DiscardTiles();
                        Motion.Vent = VentPhase.IntakeClosing;
                    }
                    break;
                case VentPhase.IntakeClosing:
                    Motion.Intake = Math.Max(0, Motion.Intake - 1f / 90);
                    if (Motion.Intake <= 0) Motion.Vent = VentPhase.ShieldOpening;
                    break;
                case VentPhase.ShieldOpening:
                    Motion.Shield = Math.Max(0, Motion.Shield - 1f / 240);
                    if (Motion.Shield <= 0)
                    {
                        Motion.Vent = VentPhase.Idle;
                        Motion.Requested = false;
                        Motion.Core = CorePhase.Off;
                        Motion.CoreTick = 0;
                        Motion.CoreSubtick = 0;
                        Motion.SpinPhase = 0;
                        Motion.SecondaryPhase = 0;
                        Motion.SecondaryRate = 0;
                        Motion.PowerRamp = 0;
                        Motion.EjectTick = 0;
                    }
                    break;
            }
        }

        private void AdvanceSpin()
        {
            Motion.SpinPhase = (Motion.SpinPhase + Motion.SpinRate) % 36000;
            Motion.SecondaryRate = RingMotion.SecondaryRate(Motion.SpinRate, Motion.CoreTick);
            Motion.SecondaryPhase = (Motion.SecondaryPhase + Motion.SecondaryRate) % 36000;
        }

        private void ApplyVentDamage()
        {
            if (Motion.VentDamageApplied || !Motion.VentHadPayload) return;
            Motion.VentDamageApplied = true;
            SaveMotion();
            // Snapshot actual attached modules before damage can change the
            // connection dictionary. Nearby reactors/modules are never scanned.
            var modules = new List<IMySlimBlock>();
            var native = (Sandbox.Game.Entities.MyCubeBlock)Entity;
            if (native.CurrentAttachedUpgradeModules != null)
                foreach (var entry in native.CurrentAttachedUpgradeModules.Values)
                    if (entry.Compatible && entry.Block != null && !entry.Block.Closed
                        && entry.Block.BlockDefinition.SubtypeName.StartsWith("ArcanePower_"))
                        modules.Add(entry.Block.SlimBlock);
            float reactorFraction = .01f + .04f * Motion.VentLoad + .10f * Motion.VentHeat;
            float moduleFraction = .02f + .06f * Motion.VentLoad + .12f * Motion.VentHeat;
            foreach (var module in modules)
                module.DoDamage(module.MaxIntegrity * moduleFraction, VRage.Utils.MyStringHash.GetOrCompute("Overheat"), true, attackerId: Id);
            reactor.SlimBlock.DoDamage(reactor.SlimBlock.MaxIntegrity * reactorFraction,
                VRage.Utils.MyStringHash.GetOrCompute("Overheat"), true, attackerId: Id);
        }

        private void PublishMotion()
        {
            Motion.Sequence++;
            SaveMotion();
            VentSession.Broadcast(Motion);
            reactor.RefreshCustomInfo();
        }

        internal void SaveMotion()
        {
            if (!motionInitialized || restoreLegacyHardware || thermalRestoreFault || reactor == null || MyAPIGateway.Multiplayer == null || MyAPIGateway.Utilities == null || !MyAPIGateway.Multiplayer.IsServer) return;
            if (Entity.Storage == null) Entity.Storage = new MyModStorageComponent();
            Motion.Enabled = reactor.Enabled;
            Entity.Storage[MotionStorage] = MyAPIGateway.Utilities.SerializeToXML(Motion);
        }

        private static float Ease(float t)
        {
            t = MathHelper.Clamp(t, 0, 1);
            return (1 - (float)Math.Cos(Math.PI * t)) * .5f;
        }
        private static float Span(float age, float start, float end) { return Ease((age - start) / (end - start)); }

        private Matrix Rest(string name)
        {
            Matrix pose;
            return restPoses.TryGetValue(name, out pose) ? pose : Matrix.Identity;
        }

        private void Part(string name, Matrix pose, bool visible = true)
        {
            MyEntitySubpart part;
            if (!restPoses.ContainsKey(name) || !((MyEntity)Entity).Subparts.TryGetValue(name, out part)) return;
            part.PositionComp.SetLocalMatrix(ref pose);
            if (part.Render.Visible != visible) part.Render.Visible = visible;
        }

        private Matrix RingOrientation(int index, float age)
        {
            return RingMotion.Orientation(Rest("Ring" + (index + 1)), index, Span(age, 1060, 1150),
                age > 1170 ? Motion.SpinPhase : 0, age > 1170 ? Motion.SecondaryPhase : 0);
        }

        private Matrix ShutdownRingOrientation(int index)
        {
            var spec = AnimationGeometry.Rings[index];
            Matrix pose = Rest("Ring" + (index + 1));
            pose.Translation = Vector3.Zero;
            float settle = Span(Motion.CoreTick, 1060, 1150);
            pose *= Matrix.CreateFromAxisAngle(spec.Axis, MathHelper.ToRadians(spec.Tilt) * settle);
            double spin = Motion.SpinPhase * (double)spec.Speed;
            if (Motion.StopSpinAge >= 1170)
            {
                // Integrate a linear velocity ramp to zero; do not snap a
                // running hoop back to its startup angle when shutdown begins.
                float t = Math.Min(90, Motion.StopTick);
                spin += spec.Speed * Motion.SpinRate * (t - t * t / 180f);
            }
            float angle = MathHelper.WrapAngle(MathHelper.ToRadians((float)(spin % 360)));
            if (Motion.StopTick >= 90) angle *= settle;
            pose *= Matrix.CreateFromAxisAngle(spec.Axis, angle);
            float brake = Math.Min(90, Motion.StopTick);
            double secondary = Motion.SecondaryPhase;
            if (Motion.StopSpinAge >= 1170) secondary += Motion.SecondaryRate * (brake - brake * brake / 180f);
            pose *= RingMotion.SecondaryRotation(index, secondary, Motion.StopTick >= 90 ? settle : 1);
            return pose;
        }

        private Vector3 ContainmentOffset(float age)
        {
            if (Motion.Core == CorePhase.Off) return Vector3.Zero;
            bool stopping = Motion.Core == CorePhase.Stopping;
            double ticks = stopping ? Motion.StopSpinAge + Math.Min(90, Motion.StopTick)
                : (double)Motion.CoreTick + Motion.CoreSubtick + Motion.EjectTick;
            double time = ticks / 60.0;
            float weight = stopping && Motion.StopSpinAge >= 1170
                ? 1 - Span(Motion.StopTick, 0, 90) : Span(age, 1160, 1170);
            // Smooth, irregular drift shared by all tiles and the plasma. The
            // combined maximum offset stays below 6 cm inside the innermost ring.
            float drift = .004f + .026f * Motion.Load;
            return weight * new Vector3(
                drift * (float)(.5 * Math.Sin(1.73 * time) + .3 * Math.Sin(3.91 * time) + .2 * Math.Sin(7.07 * time)),
                (.012f + .02f * Motion.Load) * (float)Math.Sin(.9 * time)
                    + .008f * Motion.Load * (float)Math.Sin(4.31 * time),
                drift * (float)(.5 * Math.Sin(1.31 * time + .7) + .3 * Math.Sin(4.57 * time) + .2 * Math.Sin(6.73 * time)));
        }

        private Matrix ContainmentRotation(float age)
        {
            double time = (Motion.Core == CorePhase.Stopping ? Motion.StopSpinAge + Math.Min(90, Motion.StopTick)
                : (double)Motion.CoreTick + Motion.CoreSubtick + Motion.EjectTick) / 60;
            float rotationWeight = Span(age, 1160, 1170);
            if (Motion.Core == CorePhase.Stopping) rotationWeight *= 1 - Span(Motion.StopTick, 0, 90);
            float rotationSize = MathHelper.ToRadians(6f + 3.25f * Motion.Load) * rotationWeight;
            Matrix fieldRotation = Matrix.CreateFromYawPitchRoll(
                rotationSize * (float)(.7 * Math.Sin(1.13 * time) + .3 * Math.Sin(3.79 * time)),
                rotationSize * (float)(.65 * Math.Sin(1.91 * time + .4) + .35 * Math.Sin(4.37 * time)),
                rotationSize * (float)(.6 * Math.Sin(1.57 * time) + .4 * Math.Sin(3.17 * time + .8)));
            // Reuse the saved/synchronized, load-driven phase. Unequal broad
            // sweeps overpower the slow underlying spin at intervals, producing
            // reversals, half-turns and quieter adjustments on different axes.
            // Frequencies close at the 36,000-degree phase wrap without a jump.
            double coreSpin = Motion.SpinPhase;
            if (Motion.Core == CorePhase.Stopping && Motion.StopSpinAge >= 1170)
            {
                float brake = Math.Min(90, Motion.StopTick);
                coreSpin += Motion.SpinRate * (brake - brake * brake / 180f);
            }
            double spinRadians = coreSpin * Math.PI / 180;
            Matrix spinRotation = Matrix.CreateFromYawPitchRoll(
                MathHelper.ToRadians((float)((coreSpin * .06 + 145 * Math.Sin(spinRadians * .04)
                    + 45 * Math.Sin(spinRadians * .11)) % 360)),
                MathHelper.ToRadians((float)(105 * (Math.Sin(spinRadians * .05 + .6) - Math.Sin(.6)))),
                MathHelper.ToRadians((float)((coreSpin * .02
                    + 60 * (Math.Sin(spinRadians * .09 + .9) - Math.Sin(.9))) % 360)));
            if (Motion.Core == CorePhase.Stopping && Motion.StopTick >= 90)
            {
                // After braking, align the still-complete shell before the first
                // tile returns to a dispenser during reverse assembly.
                spinRotation = Matrix.CreateFromQuaternion(Quaternion.Slerp(Quaternion.Identity,
                    Quaternion.CreateFromRotationMatrix(spinRotation), Span(age, 1038, 1170)));
            }
            return spinRotation * fieldRotation;
        }

        private Vector3 EjectionOffset()
        {
            return Motion.VentHadPayload ? Vector3.Up * (Motion.EjectionTravel * Motion.EjectTick * Motion.EjectTick / 14400f) : Vector3.Zero;
        }

        private Matrix PayloadRingPose(int i, float age)
        {
            string name = "Ring" + (i + 1);
            Matrix ring = Motion.Core == CorePhase.Stopping ? ShutdownRingOrientation(i) : RingOrientation(i, age);
            ring.Translation = Vector3.Lerp(Rest(name).Translation, AnimationGeometry.Center, Span(age, 90, 210));
            ring.Translation += EjectionOffset();
            return ring;
        }

        private Matrix PayloadTilePose(TilePose tile, float age, Matrix fieldRotation)
        {
            float t = age - (320 + 36 * tile.Batch);
            Matrix rest = Rest(tile.Name);
            Matrix pose = rest;
            if (t > 0)
            {
                var rotation = Quaternion.Slerp(Quaternion.CreateFromRotationMatrix(rest),
                    Quaternion.CreateFromRotationMatrix(tile.Final), Span(t, 6, 34));
                pose = Matrix.CreateFromQuaternion(rotation);
                if (t < 6) pose.Translation = Vector3.Lerp(rest.Translation, tile.Exit, MathHelper.Clamp(t / 6, 0, 1));
                else if (t < 18) pose.Translation = Vector3.Lerp(tile.Exit, tile.Staging, Span(t, 6, 18));
                else pose.Translation = Vector3.Lerp(tile.Staging, tile.Final.Translation, Span(t, 18, 34));
            }
            pose.Translation -= AnimationGeometry.Center;
            pose *= fieldRotation;
            pose.Translation += AnimationGeometry.Center + ContainmentOffset(age) + EjectionOffset();
            if (Motion.MaintenanceTick >= 0 && tile.Batch == Motion.MaintenanceBatch)
                pose = MaintenancePose(tile, pose);
            return pose;
        }

        private float PlasmaScale(float age)
        {
            if (Motion.Core == CorePhase.Off || Motion.PayloadReleased) return 0;
            float scale = Span(age, PlasmaStartTick, 1170);
            // A partial startup reverses its growth at the current authored age.
            // A running core shrinks during braking, before tiles disassemble.
            if (Motion.Core == CorePhase.Stopping && Motion.StopSpinAge >= 1170)
                scale *= 1 - Span(Motion.StopTick, 0, 90);
            return scale;
        }

        private Matrix PayloadPlasmaPose(float age)
        {
            Matrix plasma = Rest("Plasma");
            float scale = PlasmaScale(age);
            Vector3 position = plasma.Translation;
            plasma.Translation = Vector3.Zero;
            plasma *= Matrix.CreateScale(Math.Max(.001f, scale));
            // The core shares the field's drift/bob, but keeps its own rest orientation.
            plasma.Translation = position + ContainmentOffset(age) + EjectionOffset();
            return plasma;
        }

        private void DrawMotion()
        {
            float age = Motion.Core == CorePhase.Off ? 0 : Motion.CoreTick + Motion.CoreSubtick;
            float alive = Motion.PayloadReleased ? 0 : 1;
            Matrix fieldRotation = ContainmentRotation(age);
            for (int i = 0; i < 4; i++)
            {
                string name = "Floor" + (i + 1);
                Matrix floor = Rest(name);
                float drop = Span(age, 0, 24) - Span(age, 274, 298);
                float slide = Span(age, 26, 76) - Span(age, 220, 270);
                floor.Translation += new Vector3(0, -.32f * drop, 0) + AnimationGeometry.FloorSlides[i] * slide;
                Part(name, floor);
                name = "Ring" + (i + 1);
                Matrix ring = PayloadRingPose(i, age);
                Part(name, ring, i < Motion.RingCount && alive > 0);
            }
            foreach (var tile in AnimationGeometry.Tiles)
            {
                float t = age - (320 + 36 * tile.Batch);
                Matrix pose = PayloadTilePose(tile, age, fieldRotation);
                Part(tile.Name, pose, t >= 0 && alive > 0);
            }
            Matrix plasma = PayloadPlasmaPose(age);
            Part("Plasma", plasma, PlasmaScale(age) > 0);
            for (int i = 0; i < 6; i++)
            {
                string name = "BlastShield" + (i + 1);
                Matrix pose = Rest(name);
                pose.Translation -= new Vector3(0, AnimationGeometry.ShieldTravel[i] * Ease(Motion.Shield), 0);
                Part(name, pose);
            }
            for (int i = 0; i < 4; i++)
            {
                string name = "VentHatch" + (i + 1);
                Matrix pose = Rest(name);
                pose.Translation += Vector3.Down * AnimationGeometry.HatchDrop * Span(Motion.Intake, 0, .3f)
                    + AnimationGeometry.HatchSlides[i] * Span(Motion.Intake, .3f, 1);
                Part(name, pose);
                name = "CeilingHatch" + (i + 1);
                pose = Rest(name);
                pose.Translation += Vector3.Up * AnimationGeometry.CeilingHatchLift * Span(Motion.Intake, 0, .3f)
                    + AnimationGeometry.CeilingHatchSlides[i] * Span(Motion.Intake, .3f, 1);
                Part(name, pose);
            }
        }

    }
}
